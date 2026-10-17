"""Engineering analyses built on repeated full model runs (sensitivity-analysis improvement plan).

Every analysis follows the same engine contract:

    base_case   = validated copy of the project
    base_result = full model run
    for each modified case:
        case = clone(base_case); case[parameter] = value
        case = apply_dependency_policy_and_validate(case)
        result = full model run (geometry, spectra, optics, noise, MTF, AMOP, ranges are all recomputed)
        save(value, D, R, I, diagnostics)

Analyses
--------
* limiting_factors  - what limits the nominal range: each degradation is removed in turn.
* sweep / sweep2d   - DRI range versus one parameter, or a two-parameter grid (heatmap).
* uncertainty       - three separate outputs that are never mixed:
      one-at-a-time (OAT) variation  -> range change for the stated -/+ perturbation (not a probability interval)
      RSS propagation (GUM, JCGM 100) -> approximate combined standard uncertainty u(R) from local sensitivities,
                                         standard uncertainties and correlations; expanded U = k u(R)
      Monte Carlo (JCGM 101)           -> percentiles of the simulated range distribution with stated coverage
* compare_scenarios - DRI ranges of several saved configurations.

Ranges are those of the first active atmosphere.  Standard task criteria (line pairs) are never changed.
These are numerical recalculations of the TRM performance model - not image simulations.
"""
import copy
import datetime
import math
from statistics import NormalDist

import numpy as np

from . import presets as P
from . import derived as DV
from .model import run_project, ModelError

_N = NormalDist()


class AnalysisCancelled(Exception):
    pass


def _noop(msg, frac=None):
    return None


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
def get_path(d, path):
    for k in path.split("."):
        d = d[int(k)] if isinstance(d, list) else d[k]
    return d


def set_path(d, path, value):
    keys = path.split(".")
    for k in keys[:-1]:
        d = d[int(k)] if isinstance(d, list) else d[k]
    k = keys[-1]
    if isinstance(d, list):
        d[int(k)] = value
    else:
        d[k] = value


def has_path(d, path):
    try:
        get_path(d, path)
        return True
    except (KeyError, IndexError, ValueError, TypeError):
        return False


def model_ranges(project):
    """Full model run -> ({task: range km}, warnings).  Raises ModelError for invalid cases."""
    _m, res = run_project(project)
    rg = res.get("range")
    if not rg or not rg["atm"]:
        raise ModelError("Range analyses need 'Field performance' mode and at least one task.")
    a0 = rg["atm"][0]
    out = {}
    for t in a0["tasks"]:
        R0 = t["R0"]
        if R0 is None:
            R0 = float(a0["R"][0])
        elif not np.isfinite(R0):
            R0 = float(a0["R"][-1])
        out[t["name"]] = float(R0)
    return out, list(res["warnings"])


def _evaluator(evaluate):
    """Wrap an evaluator so that it always returns (ranges, warnings)."""
    if evaluate is None:
        return model_ranges

    def ev(p):
        r = evaluate(p)
        return (r if isinstance(r, dict) and not isinstance(r, tuple) else r[0]), []
    return ev


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def describe_engine(project):
    """Short description of the calculation path the analyses run through."""
    p = P.deep_merge(P.DEFAULT_PROJECT, project)
    o, d = p["optics"], p["detector"]
    mtf = {"model": "computed optics MTF (A)", "zemax": "imported optics MTF (B)",
           "measured": "measured lens MTF (B)", "device": "imported device prefilter MTF (C)"}.get(o.get("mtf_source"), "computed optics MTF (A)")
    if p["category"] == "Thermal":
        noise = "measured NETD %.4g mK" % float(d["netd_mK"]) if (p["imager_type"] == "uncooled" or
                                                                 d["noise_mode"] == "measured") else \
            "calculated detector noise"
    else:
        noise = "calculated photon/dark/read noise"
    atm = {"spectral": "spectral atmosphere import", "visibility": "visual range"}.get(
        p["atmosphere"]["mode"], "Beer-Lambert extinction")
    return "%s %s, %s, %s; %s; %s; %s" % (
        p["category"], p["imager_type"], "field" if p["mode"]["environment"] == "field" else "laboratory",
        p["mode"]["stream"], mtf, noise, atm)


# ---------------------------------------------------------------------------------------------
# dependency policies and validation (Section 4 of the improvement plan)
# ---------------------------------------------------------------------------------------------
_PITCH = [("ff2", "Both axes, constant fill factor (active size scales with pitch)"),
          ("ff1", "This axis only, constant fill factor"),
          ("keep_a", "Both axes, keep active size (limited to the pitch)"),
          ("keep_fov", "Both axes, constant fill factor, keep FOV (focal length scales)")]
POLICIES = {
    "detector.pitch_h_um": _PITCH,
    "detector.pitch_v_um": _PITCH,
    "optics.f_mm": [("keep_D", "Keep aperture diameter (F-number changes)"),
                    ("keep_F", "Keep F-number (aperture diameter scales)")],
    "optics.D_mm": [("plain", "Change the diameter only (F-number changes)")],
    "optics.F_general": [("plain", "Change the F-number only (aperture diameter changes)")],
    "detector.n_h": [("plain", "Change the format only (FOV changes, IFOV constant)")],
    "detector.n_v": [("plain", "Change the format only (FOV changes, IFOV constant)")],
}
DEFAULT_POLICY = [("plain", "Change this parameter only; everything else held constant")]

# parameters that belong to the same physical group (2D sweeps over two of them are rejected)
_GROUPS = [{"detector.pitch_h_um", "detector.pitch_v_um", "detector.a_h_um", "detector.a_v_um", "detector.d_um"},
           {"optics.f_mm", "optics.f_v_mm"}, {"optics.D_mm", "optics.F_general"}]


def policies_for(path):
    return POLICIES.get(path, DEFAULT_POLICY)


def _measured_netd(p):
    return p.get("category") == "Thermal" and (p.get("imager_type") == "uncooled" or
                                               p.get("detector", {}).get("noise_mode") == "measured")


def apply_policy(case, path, value, policy=None):
    """Set `path` = value in `case` and adjust the dependent inputs; returns explanatory notes."""
    notes = []
    if not has_path(case, path):
        set_path(case, path, value)
        return notes
    old = get_path(case, path)
    if isinstance(old, bool):
        raise ValueError("Boolean parameters cannot be swept")
    newv = int(round(value)) if isinstance(old, int) else float(value)
    policy = policy or policies_for(path)[0][0]
    d, o = case.get("detector", {}), case.get("optics", {})
    if path in ("detector.pitch_h_um", "detector.pitch_v_um"):
        z = path.split("_")[1]
        ratio = float(newv) / float(old) if float(old) else 1.0
        axes = [z] if policy == "ff1" else ["h", "v"]
        for ax in axes:
            p_old = float(d["pitch_%s_um" % ax])
            p_new = p_old * ratio if ax != z else float(newv)
            d["pitch_%s_um" % ax] = p_new
            if policy == "keep_a":
                if float(d["a_%s_um" % ax]) > p_new:
                    notes.append("Active size (%s) limited to the new pitch %.3g um." % (ax, p_new))
                    d["a_%s_um" % ax] = p_new
            else:
                d["a_%s_um" % ax] = float(d["a_%s_um" % ax]) * ratio
        if policy != "keep_a" and d.get("shape") in ("circular", "loophole"):
            d["d_um"] = float(d["d_um"]) * ratio
            d["d_hole_um"] = float(d["d_hole_um"]) * ratio
        if policy == "keep_fov":
            o["f_mm"] = float(o["f_mm"]) * ratio
            o["f_v_mm"] = float(o["f_v_mm"]) * ratio
            if o.get("aperture") != "general":
                notes.append("Focal length scaled to keep the FOV; aperture diameter kept, so the F-number changes.")
        notes.append("Detector noise, well capacity, QE and NETD are held constant - a real detector with another "
                     "pitch would change them; they are not inferred from the pitch.")
        return notes
    if path == "optics.f_mm":
        ratio = float(newv) / float(old) if float(old) else 1.0
        o["f_mm"] = float(newv)
        if o.get("diff_focal"):
            o["f_v_mm"] = float(o["f_v_mm"]) * ratio
        if policy == "keep_F":
            if o.get("aperture") != "general":
                o["D_mm"] = float(o["D_mm"]) * ratio
                o["D_obsc_mm"] = float(o.get("D_obsc_mm", 0.0)) * ratio
        else:
            if o.get("aperture") == "general":
                o["F_general"] = float(o["F_general"]) * ratio
            if _measured_netd(case):
                notes.append("The measured NETD is held constant although the F-number changes - it is only valid "
                             "for the optics it was measured with.")
        return notes
    set_path(case, path, newv)
    if path in ("optics.D_mm", "optics.F_general", "optics.tau_opt") and _measured_netd(case):
        notes.append("The measured NETD is held constant although the collected radiation changes - it is only valid "
                     "for the optical configuration it was measured with.")
    if path in ("detector.noise_floor_e", "detector.dark_A", "detector.storage_e") and _measured_netd(case):
        notes.append("This input has no effect: the sensor mode uses a measured aggregate NETD.")
    return notes


_HARD = ("impossible", "must be > 0", "larger than the pitch", "Incomplete", "smaller than the aperture")


def validate_case(case, base_warnings=()):
    """Physical consistency check before a run: (ok, diagnostics)."""
    try:
        _rows, warns = DV.compute(P.deep_merge(P.DEFAULT_PROJECT, case))
    except (KeyError, ValueError, TypeError, ZeroDivisionError) as e:
        return False, ["invalid configuration: %s" % e]
    new = [w for w in warns if w not in base_warnings]
    bad = [w for w in new if any(h in w for h in _HARD)]
    return not bad, (bad or new)


# ---------------------------------------------------------------------------------------------
# limiting factors
# ---------------------------------------------------------------------------------------------
def factor_list(project):
    """(name, what-if switches) of the degradations that can be removed for the analysis."""
    p = P.deep_merge(P.DEFAULT_PROJECT, project)
    out = []
    src = p["optics"].get("mtf_source", "model")
    if src in ("zemax", "measured") or (src == "model" and p["optics"]["aberration"] != "none"):
        out.append(("Optics aberrations (diffraction-limited optics)", {"no_aberr": True}))
    if src != "device" and not (src in ("zemax", "measured") and p["optics"].get("mtf_incl_detector")):
        out.append(("Detector footprint / crosstalk (ideal pixel MTF)", {"ideal_det": True}))
    out.append(("Temporal noise halved", {"noise_scale": 0.5}))
    if p["detector"]["fpn_mode"] != "none":
        out.append(("Fixed pattern noise removed", {"fpn_scale": 0.0}))
    if not p["display"]["neglect_eye"] and p["display"].get("observer", "legacy") != "algorithm":
        out.append(("Display / eye (ideal observer MTF)", {"ideal_eye": True}))
    if p["mode"]["environment"] == "field":
        out.append(("Atmospheric transmission (clear path)", {"no_atm": True}))
    st = p["stab"]
    mode = st.get("jitter_mode", "model")
    if not st["neglect"] and not p["optics"].get("mtf_incl_motion") and (
            mode in ("measured", "psd") or mode == "model" and (st["random_on"] or st["lin_on"] or st["sin_on"])):
        out.append(("Line-of-sight motion / jitter", {"no_stab": True}))
    if p["turbulence"]["on"] and p["category"] != "Thermal":
        out.append(("Turbulence", {"no_turb": True}))
    return out


def _classify(project):
    """What limits the nominal range: sampling vs sensitivity/MTF per task (from the base run)."""
    _m, res = run_project(project)
    out = {}
    for t in (res.get("dashboard") or {}).get("tasks", []):
        if "cyc_nyq" not in t:
            out[t["name"]] = "range at the grid limit"
        elif t["lp"] > t["cyc_nyq"]:
            out[t["name"]] = "sampling (task needs %.1f cycles, Nyquist allows %.1f)" % (t["lp"], t["cyc_nyq"])
        elif t["sampling_limited"]:
            out[t["name"]] = "near the sampling limit"
        else:
            out[t["name"]] = "sensitivity / MTF (well sampled)"
    return out


def limiting_factors(project, progress=None, stop=None):
    """Range gain per task when each degradation is removed.  Returns dict with 'base', 'rows'."""
    progress, stop = progress or _noop, stop or (lambda: False)
    facs = factor_list(project)
    progress("Limiting factors: nominal run", 0.0)
    base, _w = model_ranges(project)
    rows = []
    for i, (name, wi) in enumerate(facs):
        if stop():
            raise AnalysisCancelled()
        progress("Limiting factors: %s" % name, (i + 1) / (len(facs) + 1))
        p = copy.deepcopy(project)
        p["_what_if"] = wi
        try:
            r, _w = model_ranges(p)
        except ModelError:
            continue
        gain = {t: 100.0 * (r[t] / base[t] - 1.0) if base[t] > 0 else 0.0 for t in base}
        rows.append({"factor": name, "ranges": r, "gain_pct": gain})
    tasks = list(base)
    key = tasks[-1] if tasks else None          # the most demanding (last) task decides the ranking
    rows.sort(key=lambda x: -x["gain_pct"].get(key, 0.0))
    progress("Limiting factors: done", 1.0)
    return {"kind": "limiting", "base": base, "rows": rows, "rank_task": key, "time": _now(),
            "limit_type": _classify(project), "engine": describe_engine(project),
            "dominant": rows[0]["factor"] if rows and rows[0]["gain_pct"].get(key, 0) > 1.0 else None,
            "method": "One degradation removed at a time (full model recalculation per case)."}


# ---------------------------------------------------------------------------------------------
# parameter sweeps
# ---------------------------------------------------------------------------------------------
def grid(lo, hi, n, sampling="linear"):
    n = max(2, int(n))
    if sampling == "log":
        if lo <= 0 or hi <= 0:
            raise ValueError("Logarithmic sampling needs positive start and end values")
        return [float(x) for x in np.geomspace(lo, hi, n)]
    return [float(x) for x in np.linspace(lo, hi, n)]


def _run_case(base_project, base_warn, changes, evaluate):
    """changes = [(path, value, policy)] -> run dict."""
    case = copy.deepcopy(base_project)
    notes = []
    try:
        for path, value, policy in changes:
            notes += apply_policy(case, path, value, policy)
    except (ValueError, KeyError, TypeError) as e:
        return {"ok": False, "ranges": {}, "diag": ["rejected: %s" % e], "notes": notes}
    if evaluate is None:
        ok, diag = validate_case(case, base_warn)
        if not ok:
            return {"ok": False, "ranges": {}, "diag": ["rejected: " + d for d in diag], "notes": notes}
    else:
        diag = []
    try:
        r, warns = _evaluator(evaluate)(case)
    except ModelError as e:
        return {"ok": False, "ranges": {}, "diag": ["model error: %s" % e], "notes": notes}
    new_w = [w for w in warns if w not in base_warn]
    return {"ok": True, "ranges": r, "diag": diag + new_w, "notes": notes}


def sweep(project, path, values, progress=None, policy=None, stop=None, evaluate=None, sampling="linear"):
    """DRI ranges for each value of one parameter (full recalculation, dependency policy applied)."""
    progress, stop = progress or _noop, stop or (lambda: False)
    base, base_warn = _evaluator(evaluate)(project)
    policy = policy or policies_for(path)[0][0]
    runs = []
    for i, v in enumerate(values):
        if stop():
            raise AnalysisCancelled()
        progress("Sweep %s = %.5g" % (path, v), i / max(len(values), 1))
        run = _run_case(project, base_warn, [(path, v, policy)], evaluate)
        run["value"] = float(v)
        run["delta_pct"] = {t: 100.0 * (run["ranges"][t] / base[t] - 1.0) if run["ok"] and base[t] > 0 else np.nan
                            for t in base}
        runs.append(run)
    progress("Sweep done", 1.0)
    notes = []
    for r in runs:
        for n in r["notes"]:
            if n not in notes:
                notes.append(n)
    return {"kind": "sweep", "path": path, "values": [r["value"] for r in runs], "sampling": sampling,
            "policy": policy, "policy_label": dict(policies_for(path)).get(policy, policy), "policy_notes": notes,
            "base_value": float(get_path(project, path)) if has_path(project, path) else None, "base": base,
            "runs": runs, "ranges": {t: [r["ranges"].get(t, np.nan) for r in runs] for t in base},
            "engine": describe_engine(project) if evaluate is None else "custom evaluator", "time": _now(),
            "method": "Full model recalculation per value; '%s'." % dict(policies_for(path)).get(policy, policy)}


def sweep2d(project, px, vx, py, vy, progress=None, policy_x=None, policy_y=None, stop=None, evaluate=None):
    """Two-parameter grid: ranges[task] is an (ny, nx) array, NaN for rejected combinations."""
    progress, stop = progress or _noop, stop or (lambda: False)
    if px == py:
        raise ValueError("Choose two different parameters")
    for g in _GROUPS:
        if px in g and py in g:
            raise ValueError("%s and %s describe the same physical quantity - not a valid 2-D sweep" % (px, py))
    base, base_warn = _evaluator(evaluate)(project)
    policy_x = policy_x or policies_for(px)[0][0]
    policy_y = policy_y or policies_for(py)[0][0]
    out = {t: np.full((len(vy), len(vx)), np.nan) for t in base}
    diag = []
    n, k = len(vx) * len(vy), 0
    for j, y in enumerate(vy):
        for i, x in enumerate(vx):
            if stop():
                raise AnalysisCancelled()
            k += 1
            progress("Grid %d / %d" % (k, n), k / n)
            run = _run_case(project, base_warn, [(px, x, policy_x), (py, y, policy_y)], evaluate)
            if run["ok"]:
                for t in base:
                    out[t][j, i] = run["ranges"][t]
            else:
                diag.append("(%s = %.4g, %s = %.4g): %s" % (px, x, py, y, "; ".join(run["diag"])))
    progress("Grid done", 1.0)
    return {"kind": "sweep2d", "px": px, "py": py, "vx": list(map(float, vx)), "vy": list(map(float, vy)),
            "ranges": out, "base": base, "invalid": diag, "policy_x": policy_x, "policy_y": policy_y,
            "base_x": float(get_path(project, px)), "base_y": float(get_path(project, py)),
            "engine": describe_engine(project) if evaluate is None else "custom evaluator", "time": _now()}


# ---------------------------------------------------------------------------------------------
# uncertainty
# ---------------------------------------------------------------------------------------------
# Inputs offered for the uncertainty study, with typical relative uncertainties [%].
UNCERTAINTY_DEFAULTS = [
    ("detector.netd_mK", "NETD", 20.0),
    ("detector.noise_floor_e", "Read noise", 20.0),
    ("detector.dark_A", "Dark current", 50.0),
    ("target.dT_K", "Target temperature difference", 25.0),
    ("target.t_refl", "Target reflectivity", 15.0),
    ("target.b_refl", "Background reflectivity", 15.0),
    ("target.W_m", "Target width", 10.0),
    ("target.H_m", "Target height", 10.0),
    ("atmosphere.atm.0.sigma", "Extinction coefficient (atm 1)", 30.0),
    ("atmosphere.atm.0.V_km", "Visual range (atm 1)", 30.0),
    ("optics.f_mm", "Focal length", 2.0),
    ("optics.tau_opt", "Optics transmission", 5.0),
    ("optics.q", "Aberration parameter q", 10.0),
    ("stab.rand_h_mrad", "Random jitter h", 30.0),
    ("stab.rand_v_mrad", "Random jitter v", 30.0),
    ("turbulence.cn2", "Turbulence Cn2", 50.0),
]

MEANINGS = [("bound", "Limits (+/- bound)"), ("95", "95 % interval"), ("1sigma", "1 standard deviation")]
DISTRIBUTIONS = [("normal", "Normal"), ("uniform", "Uniform"), ("triangular", "Triangular"),
                 ("lognormal", "Lognormal")]
_UNIT_INTERVAL = ("tau_opt", "tau_filter", "_refl", "tau0", "t_emis", "b_emis")


def applicable_inputs(project):
    """Uncertainty inputs that influence this project (path, label, default %)."""
    p = P.deep_merge(P.DEFAULT_PROJECT, project)
    cat = p["category"]
    thermal_meas = _measured_netd(p)
    out = []
    for path, label, pct in UNCERTAINTY_DEFAULTS:
        if path == "detector.netd_mK" and not thermal_meas:
            continue
        if path in ("detector.noise_floor_e", "detector.dark_A") and thermal_meas:
            continue
        if path == "target.dT_K" and cat == "Visible":
            continue
        if path in ("target.t_refl", "target.b_refl") and (cat != "Visible" or
                                                           p["target"][path.split(".")[1] + "_mode"] != "effective"):
            continue
        visib = cat == "Visible" and p["atmosphere"]["mode"] == "visibility"
        if path == "atmosphere.atm.0.sigma" and (visib or p["atmosphere"]["mode"] == "spectral"):
            continue
        if path == "atmosphere.atm.0.V_km" and not visib:
            continue
        if path == "optics.q" and p["optics"]["aberration"] != "q":
            continue
        if path.startswith("stab.rand") and not p["stab"]["random_on"]:
            continue
        if path == "turbulence.cn2" and not (p["turbulence"]["on"] and cat != "Thermal"):
            continue
        out.append((path, label, pct))
    return out


UNC_DEFAULTS = {"method": "rss", "mc_n": 200, "seed": 1, "coverage": 0.95, "k": 2.0, "deriv_step_pct": 1.0,
                "correlations": []}


def uncertainty_settings(project):
    """Uncertainty settings stored in the project (also accepts the old {path: pct} format)."""
    raw = dict(project.get("uncertainty") or {})
    if raw and "inputs" not in raw and all(isinstance(v, (int, float)) for v in raw.values()):
        raw = {"inputs": {p: {"on": True, "pct": float(v)} for p, v in raw.items()}}
    s = dict(UNC_DEFAULTS)
    s.update({k: v for k, v in raw.items() if k != "inputs"})
    stored = raw.get("inputs", {})
    inputs = {}
    for path, label, pct in applicable_inputs(project):
        e = {"on": not stored, "pct": pct, "meaning": "bound", "dist": "normal"}
        e.update(stored.get(path, {}))
        if path in stored and "on" not in stored[path]:
            e["on"] = True
        e["label"] = label
        inputs[path] = e
    s["inputs"] = inputs
    return s


def items_from_settings(settings):
    return [{"path": p, "label": e["label"], "pct": float(e["pct"]), "meaning": e["meaning"], "dist": e["dist"]}
            for p, e in settings["inputs"].items() if e.get("on") and float(e["pct"]) > 0]


def run_uncertainty(project, progress=None, stop=None):
    """Uncertainty study with the settings stored in the project."""
    s = uncertainty_settings(project)
    items = items_from_settings(s)
    if not items:
        raise ValueError("Select at least one input with a non-zero uncertainty.")
    return uncertainty(project, items, progress, method=s["method"], correlations=s["correlations"],
                       mc_n=int(s["mc_n"]), seed=int(s["seed"]), coverage=float(s["coverage"]), k=float(s["k"]),
                       stop=stop, deriv_step=float(s["deriv_step_pct"]) / 100.0)


def standard_uncertainty(pct, meaning="bound", dist="normal"):
    """Relative standard uncertainty [fraction] of an input stated as +/- pct with a meaning and distribution."""
    a = abs(float(pct)) / 100.0
    if meaning == "1sigma":
        return a
    if meaning == "95":
        return {"normal": a / 1.959964, "lognormal": a / 1.959964, "uniform": a / (0.95 * math.sqrt(3)),
                "triangular": a / ((1 - math.sqrt(0.05)) * math.sqrt(6))}[dist]
    # bound: limits of the distribution (normal / lognormal: taken as 3 sigma)
    return {"normal": a / 3.0, "lognormal": a / 3.0, "uniform": a / math.sqrt(3), "triangular": a / math.sqrt(6)}[dist]


def _clip(path, v):
    if any(k in path for k in _UNIT_INTERVAL):
        return min(max(v, 0.0), 1.0)
    return max(v, 1e-12)                        # all offered inputs are positive physical quantities


def _sample(dist, u, z):
    """Relative factor (1 + delta) for standard-normal z with standard uncertainty u."""
    if dist == "normal":
        return 1.0 + u * z
    p = min(max(_N.cdf(z), 1e-12), 1 - 1e-12)
    if dist == "uniform":
        return 1.0 + u * math.sqrt(3) * (2 * p - 1)
    if dist == "triangular":
        w = u * math.sqrt(6)
        return 1.0 + (-w + w * math.sqrt(2 * p) if p < 0.5 else w - w * math.sqrt(2 * (1 - p)))
    s = math.sqrt(math.log(1 + u * u))            # lognormal with mean 1 and standard deviation u
    return math.exp(s * z - 0.5 * s * s)


def correlation_matrix(paths, correlations):
    """Correlation matrix from [(path_a, path_b, rho)]; made positive semi-definite if needed."""
    n = len(paths)
    C = np.eye(n)
    idx = {p: i for i, p in enumerate(paths)}
    for a, b, rho in correlations or []:
        if a in idx and b in idx and a != b:
            rho = max(-1.0, min(1.0, float(rho)))
            C[idx[a], idx[b]] = C[idx[b], idx[a]] = rho
    w, V = np.linalg.eigh(C)
    if w.min() < 1e-10:                         # e.g. inconsistent correlations or rho = 1 links
        C = V @ np.diag(np.maximum(w, 1e-10)) @ V.T
        d = np.sqrt(np.diag(C))
        C = C / np.outer(d, d)
    return C


def _normalize_items(items):
    out = []
    for it in items:
        if isinstance(it, dict):
            d = {"meaning": "bound", "dist": "normal"}
            d.update(it)
            d["pct"] = float(d["pct"])
            out.append(d)
        else:
            path, label, pct = it[:3]
            out.append({"path": path, "label": label, "pct": float(pct), "meaning": "bound", "dist": "normal"})
    for it in out:
        it.setdefault("meaning", "bound")
        it.setdefault("dist", "normal")
    return out


def uncertainty(project, items, progress=None, method="rss", correlations=None, mc_n=200, seed=1,
                coverage=0.95, k=2.0, stop=None, evaluate=None, deriv_step=0.01):
    """Uncertainty study.

    items: [(path, label, pct)] or [{"path", "label", "pct", "meaning", "dist"}]
    Always computed: OAT variation (each input at -/+ its stated value) and RSS propagation with local
    sensitivities; method="mc" adds a Monte Carlo propagation with `mc_n` samples and a fixed seed.
    """
    progress, stop = progress or _noop, stop or (lambda: False)
    ev = _evaluator(evaluate)
    items = _normalize_items(items)
    base, base_warn = ev(project)
    tasks = list(base)
    n_runs = 4 * len(items) + (int(mc_n) if method == "mc" else 0)
    done = [0]

    def run(case):
        if stop():
            raise AnalysisCancelled()
        done[0] += 1
        return ev(case)[0]

    rows, notes = [], []
    for it in items:
        path = it["path"]
        x0 = float(get_path(project, path))
        a = abs(float(it["pct"])) / 100.0
        u_rel = standard_uncertainty(it["pct"], it["meaning"], it["dist"])
        progress("Uncertainty: %s (one-at-a-time)" % it["label"], done[0] / max(n_runs, 1))
        res = {}
        for sgn in (-1, 1):
            case = copy.deepcopy(project)
            xv = _clip(path, x0 * (1 + sgn * a))
            set_path(case, path, xv)
            try:
                res[sgn] = (xv, run(case))
            except ModelError as e:
                res[sgn] = (xv, dict(base))
                notes.append("%s at %+g %%: model error (%s) - nominal value used" % (it["label"], sgn * it["pct"], e))
        # local sensitivity dR/dx by central differences (small step)
        h = abs(x0) * deriv_step if x0 else deriv_step
        r_hi, r_lo = None, None
        for sgn in (1, -1):
            case = copy.deepcopy(project)
            set_path(case, path, x0 + sgn * h)
            try:
                rr = run(case)
            except ModelError:
                rr = dict(base)
            if sgn > 0:
                r_hi = rr
            else:
                r_lo = rr
        c = {t: (r_hi[t] - r_lo[t]) / (2 * h) for t in tasks}
        row = {"path": path, "label": it["label"], "pct": float(it["pct"]), "meaning": it["meaning"],
               "dist": it["dist"], "x0": x0, "x_low": res[-1][0], "x_high": res[1][0],
               "low": res[-1][1], "high": res[1][1], "u_rel": u_rel, "u_abs": u_rel * abs(x0), "c": c,
               "elasticity": {t: c[t] * x0 / base[t] if base[t] else 0.0 for t in tasks}}
        for t in tasks:
            dl, dh = row["low"][t] - base[t], row["high"][t] - base[t]
            if min(abs(dl), abs(dh)) > 0 and max(abs(dl), abs(dh)) / min(abs(dl), abs(dh)) > 1.5:
                note = "%s: asymmetric response (-%g %%: %+.3g km, +%g %%: %+.3g km) - the linear RSS approximation " \
                       "is questionable; use Monte Carlo." % (it["label"], it["pct"], dl, it["pct"], dh)
                if note not in notes:
                    notes.append(note)
                break
        if it["pct"] > 30:
            notes.append("%s: large perturbation (+/-%g %%) - check the full recalculated response." %
                         (it["label"], it["pct"]))
        rows.append(row)

    # RSS / GUM propagation with correlations
    paths = [r["path"] for r in rows]
    C = correlation_matrix(paths, correlations)
    rss = {}
    for t in tasks:
        g = np.array([r["c"][t] * r["u_abs"] for r in rows])        # c_i u_i
        var = float(g @ C @ g) if len(g) else 0.0
        u = math.sqrt(max(var, 0.0))
        contrib = (g * (C @ g)) / var if var > 0 else np.zeros_like(g)
        for r, s in zip(rows, contrib):
            r.setdefault("contrib", {})[t] = float(s)
        rss[t] = {"u": u, "U": k * u, "k": k, "rel_pct": 100 * u / base[t] if base[t] else 0.0}

    out = {"kind": "uncertainty", "method": method, "base": base, "tasks": tasks, "rows": rows, "rss": rss,
           "correlations": [list(c) for c in (correlations or [])], "notes": notes, "time": _now(),
           "engine": describe_engine(project) if evaluate is None else "custom evaluator",
           "settings": {"deriv_step_pct": 100 * deriv_step, "k": k, "coverage": coverage, "mc_n": int(mc_n),
                        "seed": int(seed)}}

    if method == "mc":
        rng = np.random.default_rng(int(seed))
        L = np.linalg.cholesky(C) if len(paths) else np.zeros((0, 0))
        samples = {t: [] for t in tasks}
        failed = 0
        for i in range(int(mc_n)):
            progress("Monte Carlo sample %d / %d" % (i + 1, mc_n), done[0] / max(n_runs, 1))
            z = L @ rng.standard_normal(len(paths)) if len(paths) else []
            case = copy.deepcopy(project)
            for r, zi in zip(rows, z):
                set_path(case, r["path"], _clip(r["path"], r["x0"] * _sample(r["dist"], r["u_rel"], float(zi))))
            try:
                rr = run(case)
            except ModelError:
                failed += 1
                continue
            for t in tasks:
                samples[t].append(rr[t])
        a = (1 - coverage) / 2
        mc = {"n_ok": int(mc_n) - failed, "n_fail": failed, "seed": int(seed), "coverage": coverage}
        for t in tasks:
            s = np.array(samples[t])
            if s.size:
                mc[t] = {"p_lo": float(np.quantile(s, a)), "p50": float(np.median(s)), "p_hi": float(np.quantile(s, 1 - a)),
                         "mean": float(s.mean()), "std": float(s.std(ddof=1)) if s.size > 1 else 0.0, "samples": s}
        out["mc"] = mc
    progress("Uncertainty: done", 1.0)
    out["label"] = method_label(out)
    return out


def method_label(u):
    """Accurate, method-dependent name of the reported interval."""
    if u.get("method") == "mc" and "mc" in u:
        return "Monte Carlo %.0f %% percentile interval (%d samples, seed %d)" % (
            100 * u["mc"]["coverage"], u["mc"]["n_ok"], u["mc"]["seed"])
    k = u["settings"]["k"]
    return "RSS combined standard uncertainty u(R); expanded U = %g u(R)%s" % (
        k, " (about 95 % if R is approximately normal)" if abs(k - 2) < 1e-9 else "")


def interval(u, task):
    """(low, high, text) of the method-labelled interval of one task."""
    R0 = u["base"][task]
    if u.get("method") == "mc" and task in u.get("mc", {}):
        m = u["mc"][task]
        return m["p_lo"], m["p_hi"], "MC %.0f %%: %.3g - %.3g km" % (100 * u["mc"]["coverage"], m["p_lo"], m["p_hi"])
    r = u["rss"][task]
    return R0 - r["U"], R0 + r["U"], "u = %.3g km, U(k=%g) = +/-%.3g km" % (r["u"], r["k"], r["U"])


def oat_envelope(u, task):
    """Smallest / largest range of all one-at-a-time runs (not a probability interval)."""
    vals = [u["base"][task]] + [r["low"][task] for r in u["rows"]] + [r["high"][task] for r in u["rows"]]
    return min(vals), max(vals)


# ---------------------------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------------------------
def compare_scenarios(scenarios, progress=None, stop=None, evaluate=None):
    """scenarios = [(name, project)] -> ranges per scenario and delta vs the first (baseline)."""
    progress, stop = progress or _noop, stop or (lambda: False)
    rows = []
    for i, (name, proj) in enumerate(scenarios):
        if stop():
            raise AnalysisCancelled()
        progress("Scenario: %s" % name, i / max(len(scenarios), 1))
        try:
            r, w = _evaluator(evaluate)(proj)
            rows.append({"name": name, "ok": True, "ranges": r, "warnings": w,
                         "engine": describe_engine(proj) if evaluate is None else ""})
        except ModelError as e:
            rows.append({"name": name, "ok": False, "ranges": {}, "warnings": [str(e)], "engine": ""})
    base = next((r["ranges"] for r in rows if r["ok"]), {})
    for r in rows:
        r["delta_pct"] = {t: 100 * (r["ranges"][t] / base[t] - 1) if r["ok"] and base.get(t) else np.nan
                          for t in base}
    progress("Scenarios done", 1.0)
    return {"kind": "scenarios", "rows": rows, "tasks": list(base), "time": _now()}


# ---------------------------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------------------------
def to_csv_rows(an):
    """Flat table (list of rows) of an analysis result, for CSV export."""
    k = an.get("kind")
    head = [["# TRM sensitivity analysis", k], ["# time", an.get("time", "")], ["# engine", an.get("engine", "")]]
    if k == "sweep":
        tasks = list(an["base"])
        head += [["# parameter", an["path"]], ["# policy", an["policy_label"]], ["# sampling", an["sampling"]]]
        head += [["# note", n] for n in an["policy_notes"]]
        rows = [["value"] + ["%s_km" % t for t in tasks] + ["%s_delta_pct" % t for t in tasks] + ["valid", "diagnostics"]]
        rows.append(["baseline %s" % an["base_value"]] + [an["base"][t] for t in tasks] + [0] * len(tasks) + [1, ""])
        for r in an["runs"]:
            rows.append([r["value"]] + [r["ranges"].get(t, "") for t in tasks] +
                        [r["delta_pct"][t] for t in tasks] + [int(r["ok"]), " | ".join(r["diag"])])
        return head + rows
    if k == "sweep2d":
        rows = [["%s \\ %s" % (an["py"], an["px"])] + an["vx"]]
        for t, g in an["ranges"].items():
            rows.append(["# task", t])
            for j, y in enumerate(an["vy"]):
                rows.append([y] + ["" if not np.isfinite(v) else v for v in g[j]])
        return head + rows + [["# invalid", d] for d in an["invalid"]]
    if k == "uncertainty":
        tasks = an["tasks"]
        head += [["# method", an["label"]]] + [["# note", n] for n in an["notes"]]
        rows = [["input", "path", "nominal", "+/-pct", "meaning", "distribution", "u_rel", "x_low", "x_high"] +
                sum([["%s_low_km" % t, "%s_high_km" % t, "%s_dRdx" % t, "%s_elasticity" % t, "%s_contrib" % t]
                     for t in tasks], [])]
        for r in an["rows"]:
            rows.append([r["label"], r["path"], r["x0"], r["pct"], r["meaning"], r["dist"], r["u_rel"], r["x_low"],
                         r["x_high"]] + sum([[r["low"][t], r["high"][t], r["c"][t], r["elasticity"][t],
                                              r["contrib"][t]] for t in tasks], []))
        rows.append([])
        rows.append(["task", "nominal_km", "u_km", "U_km", "k", "oat_min_km", "oat_max_km", "mc_p_lo", "mc_p50",
                     "mc_p_hi"])
        for t in tasks:
            lo, hi = oat_envelope(an, t)
            mc = an.get("mc", {}).get(t, {})
            rows.append([t, an["base"][t], an["rss"][t]["u"], an["rss"][t]["U"], an["rss"][t]["k"], lo, hi,
                         mc.get("p_lo", ""), mc.get("p50", ""), mc.get("p_hi", "")])
        return head + rows
    if k == "limiting":
        tasks = list(an["base"])
        rows = [["factor"] + ["%s_gain_pct" % t for t in tasks]]
        rows += [[r["factor"]] + [r["gain_pct"][t] for t in tasks] for r in an["rows"]]
        rows += [["# limit type", t, v] for t, v in an.get("limit_type", {}).items()]
        return head + rows
    if k == "scenarios":
        tasks = an["tasks"]
        rows = [["scenario"] + ["%s_km" % t for t in tasks] + ["%s_delta_pct" % t for t in tasks] + ["engine"]]
        rows += [[r["name"]] + [r["ranges"].get(t, "") for t in tasks] + [r["delta_pct"][t] for t in tasks] +
                 [r["engine"]] for r in an["rows"]]
        return head + rows
    return head
