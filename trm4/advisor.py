"""Range Improvement Advisor ("TRM_Range_Improvement_Advisor_Scientific_RTL_Hebrew.pdf").

An advisory layer on top of the existing range engine - it never changes the project it is given.

    baseline   = frozen snapshot of the inputs + full model run (baseline_id, run ID, model version)   (Ch. 2.1)
    diagnosis  = bottleneck candidates per task: dashboard limiter, limiting-factor removal, local normalized
                 sensitivities S_i = (x_i / R) dR/dx_i                                                  (Ch. 4, 5.2)
    actions    = catalogue of physically consistent changes (a lens change moves f, D and F# together, a detector
                 change moves pitch, active size and format together); each one is applied to a copy, validated
                 and recalculated with the same target, environment and model version                  (Ch. 5.1, 6)
    delta      = Delta_R = R(x_a) - R(x_0), Gain % = 100 Delta_R / R_0 (no % when R_0 is 0 / undefined)  (Ch. 2.2)
    evidence   = model-supported / approximate estimate / engineering hypothesis (measure first)        (Ch. 2.3)
    robustness = paired recalculation of base and action under the low / high value of the main assumptions
                 (sensitivity to assumption ranges - no invented probability interval)                 (Ch. 5.4)
    ranking    = top 3 materially different hardware / operational actions for the decisive task, inside the user
                 constraints (min FOV); environment changes are scenarios, never improvements; Pareto flag on
                 (gain, FOV)                                                                            (Ch. 5.3, 8.1)

All numbers are outputs of the TRM performance model, uncalibrated unless validation data say otherwise.
The independent recalculations (limiting factors, sensitivities, what-if actions, robustness samples) run in a
process pool (analysis.Runner); the results do not depend on the number of worker processes.
"""
import copy
import datetime
import math
import re

import numpy as np

from . import presets as P
from . import derived as DV
from . import analysis as AN
from .model import run_project, run_id, ModelError, MODEL_VERSION

SUPPORT = {"model": "Model-supported", "approx": "Approximate estimate", "measure": "Measure first"}
KIND = {"hardware": "Hardware change", "operational": "Operational change", "environment": "Scenario (environment)"}
NO_EFFECT_PCT = 0.5            # |gain| below this on every task = no effect in the model


def _noop(msg, frac=None):
    return None


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------------------------
# baseline and geometry
# ---------------------------------------------------------------------------------------------
def geometry(project):
    """FOV [deg], IFOV [urad], F-number and focal length of a configuration (from the derived-value panel)."""
    p = P.deep_merge(P.DEFAULT_PROJECT, project)
    rows, warns = DV.compute(p)
    val = {lab: v for _g, lab, v, _u in rows}
    out = {"f_mm": float(p["optics"]["f_mm"]), "pitch_um": float(p["detector"]["pitch_h_um"]),
           "n_h": int(p["detector"]["n_h"]), "n_v": int(p["detector"]["n_v"]), "warnings": warns}
    m = re.match(r"\s*([\d.eE+-]+)\s*x\s*([\d.eE+-]+)", val.get("Field of view h x v", ""))
    if m:
        out["fov_h_deg"], out["fov_v_deg"] = float(m.group(1)), float(m.group(2))
    m = re.match(r"\s*([\d.eE+-]+)", val.get("IFOV = p / f (sampling distance) h x v", ""))
    if m:
        out["ifov_urad"] = float(m.group(1))
    try:
        out["F"] = float(val.get("Effective F-number (f / D_eff)", "nan"))
    except ValueError:
        out["F"] = float("nan")
    out["D_mm"] = out["f_mm"] / out["F"] if out["F"] and np.isfinite(out["F"]) else float("nan")
    return out


def _ranges(project):
    """Full model run -> (ranges, warnings, dashboard tasks, run result)."""
    _m, res = run_project(project)
    rg = res.get("range")
    if not rg or not rg["atm"]:
        raise ModelError("The advisor needs 'Field performance' mode and at least one task.")
    return (AN.task_ranges(rg["atm"][0], below="zero"), list(res["warnings"]),
            (res.get("dashboard") or {}).get("tasks", []), res)


def baseline(project):
    """Frozen baseline snapshot (Ch. 2.1): inputs, outputs, versions, run ID, time."""
    snap = copy.deepcopy(project)
    ranges, warns, dtasks, res = _ranges(snap)
    rid = run_id(snap)
    return {"baseline_id": "B-" + rid[:8], "run_id": rid, "model_version": MODEL_VERSION, "time": _now(),
            "ranges": ranges, "warnings": warns, "tasks": dtasks, "geometry": geometry(snap),
            "engine": AN.describe_engine(snap), "project": snap,
            "calibration": (res.get("dashboard") or {}).get("calibration", ""),
            "model": (res.get("dashboard") or {}).get("model", "")}


def gain(before, after):
    """(delta km, gain % or None).  No percentage when the reference range is zero or undefined (T-03)."""
    if before is None or after is None or not np.isfinite(before) or not np.isfinite(after):
        return None, None
    d = after - before
    return d, (100.0 * d / before if before > 0 else None)


def comparable(a, b):
    """Before/after only compare within one model version (T-10)."""
    return a.get("model_version") == b.get("model_version")


# ---------------------------------------------------------------------------------------------
# bottleneck diagnosis (Ch. 4)
# ---------------------------------------------------------------------------------------------
_FACTOR_TYPE = [("Atmospheric", "environment"), ("Turbulence", "environment"), ("motion", "motion"),
                ("aberration", "optics"), ("Detector footprint", "optics"), ("Display / eye", "observer"),
                ("noise", "snr")]
TYPE_LABEL = {"sampling": "Angular sampling (IFOV)", "optics": "Optical / detector MTF",
              "snr": "Signal-to-noise / contrast", "environment": "Environment and contrast (atmosphere)",
              "motion": "Motion / stabilization", "observer": "Display / observer chain",
              "model": "Model limitation"}
SEPARATION_TEST = {
    "sampling": "Change p/f with MTF and scenario fixed; check the FOV it costs.",
    "optics": "Compare a measured lab MTF with the model; check focus and field position.",
    "snr": "Sensitivity to noise, exposure time, F-number and light collection.",
    "environment": "Compare atmospheric scenarios with the hardware held fixed.",
    "motion": "Compare MTF_motion / RMS jitter with the exposure parameters.",
    "observer": "Check display size / magnification and the observer model before changing hardware.",
    "model": "Check the code dependency; mark the parameter as not supported.",
}


def _factor_type(name):
    for key, typ in _FACTOR_TYPE:
        if key.lower() in name.lower():
            return typ
    return "optics"


def diagnose(base, limiting):
    """Bottleneck candidate per task from the dashboard diagnostics and the limiting-factor ranking."""
    rows = limiting.get("rows", []) if limiting else []
    out = {}
    for t in base["tasks"]:
        name = t["name"]
        lim = t.get("limiter", "")
        reasons = []
        if "cyc_nyq" in t and t["lp"] > t["cyc_nyq"]:
            typ = "sampling"
            reasons.append("the task needs %.1f cycles across the target but the detector Nyquist limit allows only "
                           "%.1f (%.1f x %.1f pixels on target)" % (t["lp"], t["cyc_nyq"], t["pix_h"], t["pix_v"]))
        elif "contrast" in lim or "noise" in lim:
            typ = "snr"
            reasons.append("the target is well sampled (%.1f cycles available, %.1f needed) but the CNR at the range "
                           "is only %.2f" % (t.get("cyc_nyq", float("nan")), t["lp"], t.get("cnr_task", float("nan"))))
        else:
            typ = "optics"
            reasons.append("well sampled; the system MTF at the task frequency is %.2f" % t.get("mtf_task", float("nan")))
        ranked = sorted(rows, key=lambda r: -r["gain_pct"].get(name, 0.0))
        top = ranked[0] if ranked and ranked[0]["gain_pct"].get(name, 0.0) > 1.0 else None
        if top:
            reasons.append("removing '%s' gives the largest gain (%+.1f %%)" % (top["factor"], top["gain_pct"][name]))
            ftyp = _factor_type(top["factor"])
            # a removable degradation that beats the sampling limit by far is the stronger candidate
            if typ != "sampling" and top["gain_pct"][name] > 15.0:
                typ = ftyp
        out[name] = {"type": typ, "label": TYPE_LABEL[typ], "reasons": reasons,
                     "top_factor": top["factor"] if top else None, "test": SEPARATION_TEST[typ],
                     "tag": "bottleneck candidate"}
    return out


# ---------------------------------------------------------------------------------------------
# local normalized sensitivities (Ch. 5.2)
# ---------------------------------------------------------------------------------------------
def sensitivity_params(p):
    cat = p["category"]
    out = [("optics.f_mm", "Focal length (D fixed)", "keep_D"), ("optics.D_mm", "Aperture diameter", "plain"),
           ("detector.pitch_h_um", "Pixel pitch (f fixed)", "ff2"), ("optics.tau_opt", "Optics transmission", "plain")]
    if p["optics"].get("aperture") == "general":
        out[1] = ("optics.F_general", "F-number", "plain")
    if AN._measured_netd(p):
        out.append(("detector.netd_mK", "NETD", "plain"))
    else:
        out.append(("detector.noise_floor_e", "Read noise", "plain"))
    if cat == "Visible" and p["detector"]["tint_mode"] == "direct":
        out.append(("detector.tint_ms", "Integration time", "plain"))
    if p["atmosphere"]["mode"] == "visibility" and cat == "Visible":
        out.append(("atmosphere.atm.0.V_km", "Visual range (atm 1)", "plain"))
    elif p["atmosphere"]["mode"] != "spectral":
        out.append(("atmosphere.atm.0.sigma", "Extinction coefficient (atm 1)", "plain"))
    if cat != "Visible":
        out.append(("target.dT_K", "Target temperature difference", "plain"))
    out.append(("target.H_m", "Target height", "plain"))
    if p["stab"]["random_on"]:
        out.append(("stab.rand_h_mrad", "Random jitter h", "plain"))
    return out


def sensitivity_plan(project, base, step=0.05):
    """(calls, finish) of the sensitivity analysis: the +/- step runs for a Runner and the assembly."""
    p = P.deep_merge(P.DEFAULT_PROJECT, project)
    plan, calls = [], []
    for path, label, policy in sensitivity_params(p):
        x0 = float(AN.get_path(p, path))
        if x0 == 0:
            continue
        h = abs(x0) * step
        sides = [(sgn, x0 + sgn * h) for sgn in (1, -1) if not ("tau" in path and x0 + sgn * h > 1.0)]
        plan.append((path, label, policy, x0, sides))
        calls += [(AN._run_case, (project, base["warnings"], [(path, x, policy)], None)) for _sgn, x in sides]

    def finish(results):
        it = iter(results)
        side_runs = []
        for path, label, policy, x0, sides in plan:
            side = {}
            for sgn, x in sides:
                run = next(it)
                if run["ok"]:
                    side[sgn] = (x, run["ranges"])
            side_runs.append((path, label, policy, x0, side))
        return _sensitivity_rows(base, side_runs)
    return calls, finish


def sensitivities(project, base, step=0.05, progress=_noop, stop=None, runner=None):
    """S_i,t = (x_i / R_t) [R(x_i + h) - R(x_i - h)] / (2 h), one-sided at range limits.  Zero effect is flagged."""
    calls, finish = sensitivity_plan(project, base, step)
    return finish((runner or AN.Runner(1)).map(calls, progress, stop, "Advisor: sensitivities"))


def _sensitivity_rows(base, side_runs):
    rows = []
    for path, label, policy, x0, side in side_runs:
        if not side:
            rows.append({"path": path, "label": label, "x0": x0, "ok": False, "S": {}, "note": "no valid step"})
            continue
        (xh, rh), (xl, rl) = side.get(1, (x0, base["ranges"])), side.get(-1, (x0, base["ranges"]))
        S = {}
        for t, R0 in base["ranges"].items():
            S[t] = (x0 / R0) * (rh[t] - rl[t]) / (xh - xl) if R0 > 0 and xh != xl else float("nan")
        no_effect = all(abs(v) < 1e-3 for v in S.values() if np.isfinite(v))
        rows.append({"path": path, "label": label, "x0": x0, "ok": True, "S": S, "policy": policy,
                     "one_sided": len(side) == 1, "no_effect": no_effect,
                     "note": "no effect on any task in this model configuration (parameter not connected or "
                             "saturated) - see Ch. 4 'model limitation'" if no_effect else ""})
    return rows


# ---------------------------------------------------------------------------------------------
# action catalogue (Ch. 5.1, 6)
# ---------------------------------------------------------------------------------------------
def _imported_mtf(p):
    return p["optics"].get("mtf_source", "model") in ("zemax", "measured", "device")


def catalogue(project, step=0.25):
    """Feasible actions for this configuration: list of dicts with the consistent parameter changes."""
    p = P.deep_merge(P.DEFAULT_PROJECT, project)
    o, d, cat = p["optics"], p["detector"], p["category"]
    up, dn = 1.0 + step, 1.0 - step
    acts = []

    def add(aid, group, kind, label, changes, support="model", notes=(), tradeoffs=()):
        acts.append({"id": aid, "group": group, "kind": kind, "label": label, "changes": list(changes),
                     "support": support, "notes": list(notes), "tradeoffs": list(tradeoffs)})

    lens_note = ["The imported optics MTF belongs to the current lens; a new lens needs its own MTF curve "
                 "(the computed effect is approximate)."] if _imported_mtf(p) else []
    meas = AN._measured_netd(p)
    netd_note = ["The measured NETD is held constant although the F-number / collected flux changes - it is only valid "
                 "for the optics it was measured with."] if meas else []
    if o.get("aperture") != "general":
        add("lens_long_sameF", "focal_length", "hardware",
            "Longer lens, same F-number: f x%.2f and D x%.2f" % (up, up),
            [("optics.f_mm", float(o["f_mm"]) * up, "keep_F")],
            "approx" if lens_note else "model", lens_note,
            ["Narrower FOV", "Larger and heavier lens (D x%.2f)" % up, "Angle-dependent vibration sensitivity"])
        add("lens_long_sameD", "focal_length", "hardware",
            "Longer focal length, same aperture: f x%.2f (F-number x%.2f)" % (up, up),
            [("optics.f_mm", float(o["f_mm"]) * up, "keep_D")],
            "approx" if (lens_note or netd_note) else "model", lens_note + netd_note,
            ["Narrower FOV", "Slower optics (less flux per pixel)"])
        add("aperture_up", "aperture", "hardware",
            "Faster optics: aperture D x%.2f at the same focal length" % up,
            [("optics.D_mm", float(o["D_mm"]) * up, "plain")],
            "approx" if (lens_note or netd_note) else "model",
            lens_note + netd_note + (["A cooled detector's cold shield must match the faster F-number."]
                                     if cat == "Thermal" and p["imager_type"] == "cooled" else []),
            ["Mass, cost, depth of field and aberration sensitivity grow"])
    else:
        add("aperture_up", "aperture", "hardware", "Faster optics: F-number x%.2f" % dn,
            [("optics.F_general", float(o["F_general"]) * dn, "plain")],
            "approx" if (lens_note or netd_note) else "model", lens_note + netd_note,
            ["Mass, cost, depth of field and aberration sensitivity grow"])
    pitch = float(d["pitch_h_um"])
    nh, nv = int(d["n_h"]), int(d["n_v"])
    add("detector_small_pitch", "detector", "hardware",
        "Detector with smaller pixels and the same FOV: pitch x%.2f, format %dx%d" % (
            dn, int(round(nh / dn)), int(round(nv / dn))),
        [("detector.pitch_h_um", pitch * dn, "ff2"), ("detector.n_h", nh / dn, "plain"),
         ("detector.n_v", nv / dn, "plain")],
        "approx", ["Incomplete simulation (Ch. 6): define the complete profile of the candidate detector before "
                   "deciding."],
        ["Data rate and power grow with the pixel count", "Smaller wells - check saturation"])
    add("detector_more_pixels", "detector_format", "hardware",
        "More pixels at the same pitch: format x%.2f" % up,
        [("detector.n_h", nh * up, "plain"), ("detector.n_v", nv * up, "plain")], "model", [],
        ["Wider FOV only; IFOV unchanged (a pixel count is not a resolution)"])
    if meas:
        add("netd_lower", "noise", "hardware", "Lower-noise detector / camera: NETD x%.2f" % dn,
            [("detector.netd_mK", float(d["netd_mK"]) * dn, "plain")], "model",
            ["NETD is not MRTD: valid only if the new NETD is measured under the same F-number, background and "
             "integration conditions (ASTM E1543)."], ["Detector / camera replacement cost"])
    else:
        add("read_noise_lower", "noise", "hardware", "Lower read noise: x0.50",
            [("detector.noise_floor_e", float(d["noise_floor_e"]) * 0.5, "plain")], "model",
            ["Noise model is channel dependent; use EMVA 1288 data of the candidate sensor."],
            ["Detector / read-out replacement"])
    if cat == "Thermal" and d["tint_mode"] == "wellfill" and p["mode"]["stream"] == "video":
        fr = float(p["basic"]["frame_rate"])
        add("frame_rate_lower", "exposure", "operational",
            "Lower frame rate %.0f -> %.0f Hz (longer integration toward the well-fill target)" % (fr, fr * 0.5),
            [("basic.frame_rate", fr * 0.5, "plain")], "approx",
            ["Conditional: check motion blur, saturation and the mission's frame-rate needs (T-07)."],
            ["Less temporal sampling", "More motion blur for moving targets / platforms"])
    if cat != "Thermal" and d["tint_mode"] == "direct":
        t_ms = float(d["tint_ms"])
        tmax = 1000.0 / float(p["basic"]["frame_rate"])
        if t_ms * 2 <= tmax:
            add("tint_longer", "exposure", "operational", "Longer integration time: %.3g -> %.3g ms" % (t_ms, 2 * t_ms),
                [("detector.tint_ms", 2 * t_ms, "plain")], "approx",
                ["Conditional: saturation in bright scenes and motion blur must be checked (T-07)."],
                ["More motion blur", "Saturation risk"])
    tau = float(o["tau_opt"])
    if tau < 0.97:
        add("transmission_up", "transmission", "hardware",
            "Better optics transmission (cleaning / coating): %.2f -> %.2f" % (tau, min(0.98, tau * 1.10)),
            [("optics.tau_opt", min(0.98, tau * 1.10), "plain")], "model" if not meas else "approx",
            ["Transmission changes the signal, it is not an MTF factor."] + netd_note,
            ["Coating cost; in thermal bands lower emission of the optics as well"])
    if o.get("mtf_source", "model") == "model" and o["aberration"] != "none":
        add("optics_quality", "optics_quality", "hardware", "Diffraction-limited optics (aberrations removed)",
            [("_what_if.no_aberr", True, "plain")], "approx",
            ["Upper bound: real optics keep some aberration - measure the lens MTF first."], ["Optics cost"])
    st = p["stab"]
    if not st["neglect"] and st.get("jitter_mode", "model") == "model" and (st["random_on"] or st["lin_on"] or
                                                                           st["sin_on"]):
        ch = []
        for key in ("rand_h_mrad", "rand_v_mrad", "lin_h", "lin_v", "sin_h", "sin_v"):
            if float(st.get(key, 0.0)):
                ch.append(("stab." + key, float(st[key]) * 0.5, "plain"))
        if ch:
            add("stabilization", "motion", "hardware", "Better stabilization: residual LOS motion x0.50", ch, "model",
                ["Use measured jitter (time series or PSD) if available."], ["Gimbal / stabilizer cost and mass"])
    atm = p["atmosphere"]
    if atm["mode"] == "visibility" and cat == "Visible":
        add("env_clear", "environment", "environment", "Clearer atmosphere: visual range x2 (scenario)",
            [("atmosphere.atm.0.V_km", float(atm["atm"][0]["V_km"]) * 2.0, "plain")], "model",
            ["Environment scenario, not a hardware improvement (T-08)."], [])
    elif atm["mode"] != "spectral":
        add("env_clear", "environment", "environment", "Clearer atmosphere: extinction x0.5 (scenario)",
            [("atmosphere.atm.0.sigma", float(atm["atm"][0]["sigma"]) * 0.5, "plain")], "model",
            ["Environment scenario, not a hardware improvement (T-08)."], [])
    return acts


def _apply(case, changes, notes):
    for path, value, policy in changes:
        if path.startswith("_what_if."):
            case.setdefault("_what_if", {})[path.split(".", 1)[1]] = value
        else:
            notes += AN.apply_policy(case, path, value, policy)


def evaluate_action(project, base, act):
    """Apply one action to a copy, validate, recalculate (same target / environment / version) and compare."""
    case = copy.deepcopy(project)
    notes = []
    out = dict(act)
    try:
        _apply(case, act["changes"], notes)
    except (ValueError, KeyError, TypeError) as e:
        out.update(ok=False, reason="rejected: %s" % e)
        return out, None
    ok, diag = AN.validate_case(case, base["warnings"])
    if not ok:
        out.update(ok=False, reason="not a valid physical configuration: " + "; ".join(diag))
        return out, None
    try:
        ranges, warns, dtasks, _res = _ranges(case)
    except ModelError as e:
        out.update(ok=False, reason="model error: %s" % e)
        return out, None
    geo = geometry(case)
    after = {"model_version": MODEL_VERSION}
    if not comparable(base, after):
        out.update(ok=False, reason="model version differs from the baseline - comparison blocked (T-10)")
        return out, None
    res = {}
    for t, R0 in base["ranges"].items():
        dR, g = gain(R0, ranges.get(t))
        res[t] = {"before": R0, "after": ranges.get(t), "delta_km": dR, "gain_pct": g}
    no_effect = all(abs(v["gain_pct"] or 0.0) < NO_EFFECT_PCT for v in res.values())
    b0 = base["geometry"]
    trade = list(act["tradeoffs"])
    fov_ratio = geo.get("fov_h_deg", float("nan")) / b0.get("fov_h_deg", float("nan"))
    if abs(fov_ratio - 1.0) > 0.005:
        trade.insert(0, "FOV %.2f -> %.2f deg (%+.0f %%)" % (b0["fov_h_deg"], geo["fov_h_deg"], 100 * (fov_ratio - 1)))
    if abs(geo["F"] - b0["F"]) > 0.005 * b0["F"]:
        trade.append("F-number %.2f -> %.2f" % (b0["F"], geo["F"]))
    out.update(ok=True, results=res, geometry=geo, fov_ratio=fov_ratio, notes=act["notes"] + notes,
               tradeoffs=trade, no_effect=no_effect, new_warnings=[w for w in warns if w not in base["warnings"]],
               after_tasks=dtasks, model_version=MODEL_VERSION)
    if no_effect and act["kind"] != "environment":
        out["notes"] = out["notes"] + ["No range effect in this model configuration: the task is limited elsewhere, "
                                       "or the parameter is not connected to the range engine (Ch. 4)."]
    return out, case


# ---------------------------------------------------------------------------------------------
# paired robustness under assumption ranges (Ch. 5.4)
# ---------------------------------------------------------------------------------------------
def assumption_inputs(project, n=3):
    """The main scenario / target assumptions with their typical relative ranges (from the uncertainty defaults)."""
    keep = ("atmosphere.", "target.dT_K", "target.H_m", "target.t_refl", "turbulence.cn2")
    s = AN.uncertainty_settings(project)
    out = [(path, e["label"], float(e["pct"])) for path, e in s["inputs"].items()
           if path.startswith(keep) and float(e["pct"]) > 0]
    return out[:n]


def _task_range(case, path, value, task):
    """Range of one task with one assumption changed, None for an invalid case (worker function)."""
    c = copy.deepcopy(case)
    AN.set_path(c, path, value)
    try:
        return AN.model_ranges(c)[0][task]
    except ModelError:
        return None


def robustness_samples(project, inputs):
    """(path, value) of the low / high value of each assumption."""
    out = []
    for path, _label, pct in inputs:
        x0 = float(AN.get_path(project, path))
        out += [(path, AN._clip(path, x0 * (1 + sgn * pct / 100.0))) for sgn in (-1, 1)]
    return out


def paired_robustness(project, base, case, task, inputs, runner=None):
    """Delta_R for base and candidate evaluated on the same assumption samples (low / high of each input)."""
    samples = robustness_samples(project, inputs)
    calls = [(_task_range, (pr, pa, v, task)) for pr in (project, case) for pa, v in samples]
    rr = (runner or AN.Runner(1)).map(calls)
    return _robustness_summary(rr[:len(samples)], rr[len(samples):], inputs)


def _robustness_summary(base_runs, case_runs, inputs):
    deltas = [rc - rb for rb, rc in zip(base_runs, case_runs) if rb is not None and rc is not None]
    if not deltas:
        return None
    return {"min_km": min(deltas), "max_km": max(deltas), "n": len(deltas),
            "inputs": ["%s +/-%g %%" % (l, pct) for _p, l, pct in inputs]}


# ---------------------------------------------------------------------------------------------
# data-quality checks -> "measure first" recommendations (Ch. 2.3, 8 usability rule, 11.2)
# ---------------------------------------------------------------------------------------------
def measure_first(project, diagnosis):
    p = P.deep_merge(P.DEFAULT_PROJECT, project)
    prov = p.get("provenance") or {}
    src = lambda path: prov.get(path, "preset")                              # noqa: E731
    weak = ("preset", "assumption")
    out = []
    types = {d["type"] for d in diagnosis.values()}
    if p["optics"].get("mtf_source", "model") == "model":
        out.append(("Optical MTF", "The optics MTF is theoretical (diffraction%s). Enter a measured or Zemax FFT MTF "
                    "curve at the task frequencies (ISO 9334 / ISO 12233 SFR) - and verify focus before any lens "
                    "recommendation." % ("" if p["optics"]["aberration"] == "none" else " + aberration model")))
    if p["category"] == "Thermal":
        if not AN._measured_netd(p):
            out.append(("Noise / NETD", "NETD is calculated from a generic detector model. Measure the camera NETD "
                        "(ASTM E1543) with the operational F-number, integration time and background."))
        elif src("detector.netd_mK") in weak:
            out.append(("Noise / NETD", "The NETD value is a preset / assumption. Enter the measured NETD together "
                        "with its test conditions."))
    elif src("detector.noise_floor_e") in weak:
        out.append(("Noise", "Read noise and dark current are presets. Use EMVA 1288 data of the sensor."))
    if p["detector"].get("qe_preset", "custom") != "custom" and src("detector.qe_preset") in weak:
        out.append(("Spectral QE", "The QE curve is a generic preset ('%s'). Enter the detector's measured spectral "
                    "response." % p["detector"]["qe_preset"]))
    if any(src(x) in weak for x in ("target.dT_K", "target.W_m", "target.H_m")):
        out.append(("Target", "Target size / signature are presets. Confirm the characteristic dimension and contrast "
                    "of the real target set - the range scales with them."))
    if "environment" in types or any(src("atmosphere.atm.0." + x) in weak for x in ("sigma", "V_km")):
        out.append(("Atmosphere", "The extinction is a preset. Record the visibility / humidity of the test or "
                    "import a MODTRAN-type spectral transmission (signal level, not an MTF factor)."))
    if p["stab"]["neglect"] or not (p["stab"]["random_on"] or p["stab"]["lin_on"] or p["stab"]["sin_on"]):
        out.append(("Line-of-sight motion", "No platform motion is modelled. Enter measured jitter (time series or "
                    "PSD) if the camera is not on a rigid mount - otherwise long-focal-length gains are overstated."))
    return out


# ---------------------------------------------------------------------------------------------
# the advisor
# ---------------------------------------------------------------------------------------------
def _pareto(cands, task):
    """Non-dominated on (gain for the task, FOV ratio)."""
    for a in cands:
        ga, fa = a["results"][task]["gain_pct"] or 0.0, a["fov_ratio"]
        a["pareto"] = not any((b["results"][task]["gain_pct"] or 0.0) >= ga and b["fov_ratio"] >= fa and
                              ((b["results"][task]["gain_pct"] or 0.0) > ga or b["fov_ratio"] > fa)
                              for b in cands if b is not a)


def advise(project, progress=None, stop=None, rank_task=None, min_fov_deg=0.0, step=0.25, robustness=True,
           workers=None):
    """Run the Range Improvement Advisor; the project is not modified (T-01).

    The limiting-factor, sensitivity and what-if runs are independent and go to the process pool in one batch, the
    robustness samples of the top 3 in a second batch (`workers` = number of processes, 1 = this process only)."""
    progress, stop = progress or _noop, stop or (lambda: False)
    project = copy.deepcopy(project)
    progress("Advisor: baseline", 0.0)
    base = baseline(project)
    tasks = list(base["ranges"])
    if not tasks:
        raise ModelError("No active task.")
    rank_task = rank_task if rank_task in tasks else tasks[-1]
    with AN.Runner(workers) as runner:
        return _advise(project, base, tasks, rank_task, progress, stop, min_fov_deg, step, robustness, runner)


def _advise(project, base, tasks, rank_task, progress, stop, min_fov_deg, step, robustness, runner):
    acts = catalogue(project, step)
    lim_calls, lim_finish = AN.limiting_plan(project)
    sens_calls, sens_finish = sensitivity_plan(project, base)
    act_calls = [(evaluate_action, (project, base, a)) for a in acts]
    out = runner.map(lim_calls + sens_calls + act_calls, progress, stop, "Advisor: model runs", 0.03, 0.8)
    n1, n2 = len(lim_calls), len(lim_calls) + len(sens_calls)
    limiting = lim_finish(out[:n1])
    diag = diagnose(base, limiting)
    sens = sens_finish(out[n1:n2])
    evaluated, cases = [], {}
    for ev, case in out[n2:]:
        if ev["ok"] and min_fov_deg and ev["geometry"].get("fov_h_deg", 1e9) < min_fov_deg:
            ev["constraint"] = "FOV %.2f deg below the minimum %.2f deg (T-09)" % (ev["geometry"]["fov_h_deg"],
                                                                                min_fov_deg)
        evaluated.append(ev)
        if case is not None:
            cases[ev["id"]] = case
    cands = [a for a in evaluated if a["ok"] and a["kind"] != "environment" and not a.get("constraint")]
    _pareto(cands, rank_task) if cands else None
    ranked = sorted(cands, key=lambda a: -(a["results"][rank_task]["gain_pct"] or 0.0))
    top, groups = [], set()
    for a in ranked:                                  # materially different actions: one per group
        if a["group"] in groups or a["no_effect"] or (a["results"][rank_task]["gain_pct"] or 0.0) <= NO_EFFECT_PCT:
            continue
        groups.add(a["group"])
        top.append(a)
        if len(top) == 3:
            break
    for a in evaluated:
        a["rank"] = (top.index(a) + 1) if a in top else None
    if robustness:
        inputs = assumption_inputs(project)
        samples = robustness_samples(project, inputs) if inputs and top else []
        # the base runs on the assumption samples are shared by all candidates
        calls = [(_task_range, (pr, pa, v, rank_task)) for pr in [project] + [cases[a["id"]] for a in top]
                 for pa, v in samples]
        rr = runner.map(calls, progress, stop, "Advisor: paired robustness", 0.8, 0.99) if samples else []
        ns = len(samples)
        for i, a in enumerate(top):
            a["robustness"] = _robustness_summary(rr[:ns], rr[ns * (i + 1):ns * (i + 2)], inputs) if ns else None
    mf = measure_first(project, diag)
    if not top:
        mf.insert(0, ("No ranked action", "No feasible action improves the %s range inside the constraints - "
                      "complete the data below before ranking alternatives." % rank_task))
    progress("Advisor: done", 1.0)
    base_out = {k: v for k, v in base.items() if k != "project"}
    return {"kind": "advisor", "time": _now(), "baseline": base_out, "base": base["ranges"], "tasks": tasks,
            "rank_task": rank_task, "constraints": {"min_fov_deg": min_fov_deg, "step_pct": 100 * step},
            "diagnosis": diag, "limiting": limiting, "sensitivities": sens, "actions": evaluated,
            "top": [a["id"] for a in top], "measure_first": mf, "engine": base["engine"],
            "method": "Counterfactual recalculation through the same TRM range engine (same target, environment and "
                      "model version); physically consistent parameter groups; ranked by the %s range gain inside "
                      "the constraints; environment changes reported as scenarios only." % rank_task}


def action_by_id(adv, aid):
    return next((a for a in adv["actions"] if a["id"] == aid), None)


def to_csv_rows(adv):
    tasks = adv["tasks"]
    rows = [["# TRM Range Improvement Advisor"], ["# time", adv["time"]], ["# baseline", adv["baseline"]["baseline_id"],
                                                                           adv["baseline"]["run_id"]],
            ["# model", adv["baseline"]["model_version"]], ["# rank task", adv["rank_task"]],
            ["rank", "action", "kind", "evidence", "valid"] + sum([["%s_before_km" % t, "%s_after_km" % t,
                                                                    "%s_delta_km" % t, "%s_gain_pct" % t]
                                                                   for t in tasks], []) + ["fov_h_deg", "tradeoffs",
                                                                                           "notes"]]
    for a in adv["actions"]:
        if a["ok"]:
            vals = sum([[a["results"][t]["before"], a["results"][t]["after"], a["results"][t]["delta_km"],
                         "" if a["results"][t]["gain_pct"] is None else a["results"][t]["gain_pct"]] for t in tasks], [])
            rows.append([a["rank"] or "", a["label"], KIND[a["kind"]], SUPPORT[a["support"]], "yes"] + vals +
                        [a["geometry"].get("fov_h_deg", ""), " | ".join(a["tradeoffs"]),
                         " | ".join(a["notes"] + ([a["constraint"]] if a.get("constraint") else []))])
        else:
            rows.append(["", a["label"], KIND[a["kind"]], SUPPORT[a["support"]], "no"] + [""] * (4 * len(tasks)) +
                        ["", "", a["reason"]])
    return rows


def format_text(adv):
    """Report section (plain text)."""
    from .report import _km
    L = ["[Range Improvement Advisor - ranked by %s]" % adv["rank_task"]]
    b = adv["baseline"]
    g = b["geometry"]
    L.append("  Baseline %s (run ID %s, %s), calculated %s" % (b["baseline_id"], b["run_id"], b["model_version"],
                                                              b["time"]))
    L.append("  Baseline configuration: f %.4g mm, F/%.3g, pitch %.4g um, %dx%d, FOV %.3f deg, IFOV %.4g urad" % (
        g["f_mm"], g["F"], g["pitch_um"], g["n_h"], g["n_v"], g.get("fov_h_deg", float("nan")),
        g.get("ifov_urad", float("nan"))))
    L.append("  Baseline ranges: " + "  ".join("%s %s km" % (t, _km(r)) for t, r in adv["base"].items()))
    L.append("  Method: " + adv["method"])
    if adv["constraints"]["min_fov_deg"]:
        L.append("  Constraint: FOV >= %.3g deg" % adv["constraints"]["min_fov_deg"])
    L.append("  Bottleneck candidates:")
    for t, d in adv["diagnosis"].items():
        L.append("    %-16s %s - %s.  Separation test: %s" % (t, d["label"], "; ".join(d["reasons"]), d["test"]))
    L.append("  Local normalized sensitivities S = (x/R) dR/dx (+/-5 % step):")
    for s in adv["sensitivities"]:
        if s["ok"]:
            L.append("    %-34s %s%s" % (s["label"], "  ".join("%s %+.2f" % (t, v) for t, v in s["S"].items()),
                                         "  [" + s["note"] + "]" if s["note"] else ""))
    L.append("  Top recommendations:")
    for i, aid in enumerate(adv["top"], start=1):
        a = action_by_id(adv, aid)
        L.append("    %d. %s  [%s, %s%s]" % (i, a["label"], KIND[a["kind"]], SUPPORT[a["support"]],
                                             ", Pareto" if a.get("pareto") else ""))
        L.append("       " + "  ".join("%s %s -> %s km (%s)" % (t, _km(r["before"]), _km(r["after"]),
                                                               "%+.1f %%" % r["gain_pct"] if r["gain_pct"] is not None
                                                               else "no %% (R0 = 0)")
                                       for t, r in a["results"].items()))
        if a.get("robustness"):
            rb = a["robustness"]
            L.append("       %s gain under assumption ranges (%s): %+.3f ... %+.3f km" % (
                adv["rank_task"], ", ".join(rb["inputs"]), rb["min_km"], rb["max_km"]))
        for x in a["tradeoffs"]:
            L.append("       trade-off: " + x)
        for x in a["notes"]:
            L.append("       note: " + x)
    if not adv["top"]:
        L.append("    none")
    L.append("  All evaluated actions:")
    for a in adv["actions"]:
        if a["ok"]:
            L.append("    %-78s %s%s" % (a["label"][:78], "  ".join(
                "%s %s" % (t, "%+.1f %%" % r["gain_pct"] if r["gain_pct"] is not None else "n/a")
                for t, r in a["results"].items()), "  (" + a["constraint"] + ")" if a.get("constraint") else ""))
        else:
            L.append("    %-78s %s" % (a["label"][:78], a["reason"]))
    L.append("  Measure first (data that limit the confidence of any recommendation):")
    for k, v in adv["measure_first"]:
        L.append("    - %s: %s" % (k, v))
    L.append("  Status: advisory only - uncalibrated model predictions, not validated range gains.")
    return L
