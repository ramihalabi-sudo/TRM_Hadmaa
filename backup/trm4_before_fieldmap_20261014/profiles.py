"""Camera profiles: the main input method of the Quick Prediction workflow.

A profile describes one camera: the sensor (category, detector, frame rate, processing) and one
or more optical configurations (zoom / focus positions, e.g. WFOV / NFOV), each with its own
focal length, aperture and transmission.  Applying a profile copies these values into the
project and records where every value came from (provenance), so that dependent values (FOV,
IFOV, Nyquist, F-number) are calculated, not typed in.

Built-in profiles are generic examples derived from the templates; user profiles are JSON files
in the 'profiles' folder next to the application (one file per camera).
"""
import copy
import glob
import json
import os
import re

from . import presets as P

PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "profiles")

# project sections that belong to the camera (everything else is scene, task or observer)
SENSOR_KEYS = ("category", "imager_type", "basic", "detector", "dsp")
CONFIG_OPTICS = ("aperture", "D_mm", "D_obsc_mm", "W_trunc_h_mm", "W_trunc_v_mm", "F_general", "f_mm",
                 "diff_focal", "f_v_mm", "tau_mode", "tau_opt", "tau_filter", "zemax_tau", "tau_kind", "tau_scope",
                 "mtf_source", "zemax_mtf", "zemax_mtf_unit", "zemax_mtf_field", "zemax_mtf_h", "mtf_meta",
                 "diffraction", "lambda_diff_um", "aberration", "q", "blur_um", "F_spec")


def leaf_paths(d, prefix=""):
    """Dotted paths of all leaf values of a nested dict (lists of dicts are expanded)."""
    out = []
    if isinstance(d, dict) and not (set(d) == {"name", "text"}):
        for k, v in d.items():
            out += leaf_paths(v, prefix + k + ".")
    elif isinstance(d, list) and d and all(isinstance(x, dict) for x in d):
        for i, v in enumerate(d):
            out += leaf_paths(v, prefix + "%d." % i)
    else:
        out.append(prefix[:-1])
    return out


def _from_template(tname):
    t = P.make_template(tname)
    sensor = {k: copy.deepcopy(t[k]) for k in SENSOR_KEYS}
    optics = {k: copy.deepcopy(t["optics"][k]) for k in CONFIG_OPTICS if k in t["optics"]}
    return {"name": "Generic: " + P.TEMPLATES[tname].get("name", tname), "vendor": "generic example", "source": "preset",
            "notes": "Generic example camera derived from the template '%s'. Replace with your camera's data." % tname,
            "sensor": sensor, "configs": [{"name": "Nominal", "optics": optics}], "builtin": True}


def builtin_profiles():
    out = [_from_template(n) for n in P.TEMPLATES if not n.startswith("NIIRS")]
    # example of a camera with several optical configurations (continuous zoom / dual FOV)
    base = _from_template("Thermal - MWIR cooled staring 640x512 (InSb)")
    base["name"] = "Generic: MWIR cooled 640x512, dual FOV"
    base["notes"] = "Example of a camera with two optical configurations (WFOV / NFOV) at F/4."
    base["configs"] = [
        {"name": "WFOV  f = 60 mm", "optics": dict(base["configs"][0]["optics"], aperture="general",
                                                   F_general=4.0, f_mm=60.0, F_spec=4.0)},
        {"name": "NFOV  f = 240 mm", "optics": dict(base["configs"][0]["optics"], aperture="general",
                                                    F_general=4.0, f_mm=240.0, F_spec=4.0)},
    ]
    out.append(base)
    return out


def user_profiles():
    out = []
    for fn in sorted(glob.glob(os.path.join(PROFILE_DIR, "*.json"))):
        try:
            with open(fn, "r", encoding="utf-8") as fh:
                prof = json.load(fh)
            validate(prof)
            prof["file"] = fn
            prof["builtin"] = False
            out.append(prof)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return out


def all_profiles():
    return user_profiles() + builtin_profiles()


def validate(prof):
    """Raise ValueError when a profile is incomplete or inconsistent."""
    for k in ("name", "sensor", "configs"):
        if k not in prof:
            raise ValueError("Profile is missing '%s'" % k)
    if not prof["configs"]:
        raise ValueError("Profile needs at least one optical configuration")
    for c in prof["configs"]:
        o = c.get("optics", {})
        if float(o.get("f_mm", 1)) <= 0:
            raise ValueError("Configuration %r: focal length must be > 0" % c.get("name"))
    d = prof["sensor"].get("detector", {})
    for z in ("h", "v"):
        a, p = d.get("a_%s_um" % z), d.get("pitch_%s_um" % z)
        if a is not None and p is not None and float(a) > float(p) * 1.0001:
            raise ValueError("Active detector size (%s) larger than the pitch" % z)
    return True


def apply(project, prof, config_name=None):
    """Return a copy of `project` with the profile's sensor and optical configuration applied.

    Provenance of every applied value is set to the profile's source ('manufacturer' for
    datasheet profiles, 'preset' for generic ones) unless the profile stores its own per-value
    provenance.
    """
    cfg = next((c for c in prof["configs"] if c["name"] == config_name), prof["configs"][0])
    new = P.deep_merge(project, copy.deepcopy(prof["sensor"]))
    new["optics"] = P.deep_merge(new["optics"], copy.deepcopy(cfg.get("optics", {})))
    if "basic" in cfg:
        new["basic"] = P.deep_merge(new["basic"], copy.deepcopy(cfg["basic"]))
    prov = dict(new.get("provenance", {}))
    src = prof.get("source", "profile")
    own = prof.get("provenance", {})
    applied = leaf_paths({k: prof["sensor"][k] for k in prof["sensor"]})
    applied += ["optics." + p for p in leaf_paths(cfg.get("optics", {}))]
    for path in applied:
        prov[path] = own.get(path, src)
    new["provenance"] = prov
    new["profile"] = {"name": prof["name"], "config": cfg["name"]}
    return new


def from_project(project, name, config_name="Nominal", vendor="", source="manufacturer", notes=""):
    """Create a profile from the camera part of the current project."""
    sensor = {k: copy.deepcopy(project[k]) for k in SENSOR_KEYS}
    optics = {k: copy.deepcopy(project["optics"][k]) for k in CONFIG_OPTICS if k in project["optics"]}
    prov = {p: s for p, s in project.get("provenance", {}).items()
            if p.split(".")[0] in SENSOR_KEYS or p.split(".")[0] == "optics"}
    prof = {"name": name, "vendor": vendor, "source": source, "notes": notes, "sensor": sensor,
            "configs": [{"name": config_name, "optics": optics}], "provenance": prov}
    validate(prof)
    return prof


def add_config(prof, project, config_name):
    """Add (or replace) an optical configuration taken from the project's optics."""
    optics = {k: copy.deepcopy(project["optics"][k]) for k in CONFIG_OPTICS if k in project["optics"]}
    prof["configs"] = [c for c in prof["configs"] if c["name"] != config_name] + \
        [{"name": config_name, "optics": optics}]
    return prof


def save(prof):
    os.makedirs(PROFILE_DIR, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.\- ]+", "_", prof["name"]).strip() or "profile"
    fn = prof.get("file") or os.path.join(PROFILE_DIR, safe + ".json")
    data = {k: v for k, v in prof.items() if k not in ("file", "builtin")}
    with open(fn, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    prof["file"] = fn
    return fn


def delete(prof):
    if prof.get("builtin") or not prof.get("file"):
        raise ValueError("Built-in profiles cannot be deleted")
    os.remove(prof["file"])
