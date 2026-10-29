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
* range_bands       - DRI ranges over weather (all active atmospheres) x turbulence (Cn2 / 10, nominal, x 10).
* global_sensitivity - Morris screening (mu*, sigma) or Sobol indices (S_i, S_Ti) over the stated input intervals.

Ranges are those of the first active atmosphere.  Standard task criteria (line pairs) are never changed.
These are numerical recalculations of the TRM performance model - not image simulations.

Independent model runs can be handed to a Runner, which spreads them over a process pool (same results, wall time
divided by the number of cores) and falls back to running them in this process.
"""
import copy
import datetime
import math
import os
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from concurrent.futures.process import BrokenProcessPool
from statistics import NormalDist

import numpy as np

from . import presets as P
from . import derived as DV
from . import extensions as X
from .model import run_project, ModelError

_N = NormalDist()


class AnalysisCancelled(Exception):
    pass


def _noop(msg, frac=None):
    return None


def default_workers():
    """Worker processes for independent model runs: TRM4_WORKERS, else the number of cores - 1 (max. 8)."""
    try:
        return max(1, int(os.environ["TRM4_WORKERS"]))
    except (KeyError, ValueError):
        return max(1, min(8, (os.cpu_count() or 2) - 1))


class Runner:
    """Runs independent model evaluations, in a process pool when workers > 1.

    map([(fn, args), ...]) returns the results in call order; fn must be a module-level function.  The results are
    identical to running the calls one after the other.  If the pool cannot be started or breaks, the remaining work
    runs in this process.  Use as a context manager so the pool is shut down (also on Stop).
    """

    def __init__(self, workers=None):
        self.workers = default_workers() if workers is None else max(1, int(workers))
        self._ex = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self._ex is not None:
            self._ex.shutdown(wait=False, cancel_futures=True)
            self._ex = None

    def map(self, calls, progress=None, stop=None, label="Model runs", f0=0.0, f1=1.0):
        progress, stop = progress or _noop, stop or (lambda: False)
        n = len(calls)
        if self.workers > 1 and n > 1:
            try:
                return self._map_pool(calls, progress, stop, label, f0, f1)
            except (BrokenProcessPool, OSError, RuntimeError):
                self.close()
                self.workers = 1
        out = []
        for i, (fn, args) in enumerate(calls):
            if stop():
                raise AnalysisCancelled()
            progress("%s (%d/%d)" % (label, i + 1, n), f0 + (f1 - f0) * i / max(n, 1))
            out.append(fn(*args))
        return out

    def _map_pool(self, calls, progress, stop, label, f0, f1):
        if self._ex is None:
            self._ex = ProcessPoolExecutor(max_workers=self.workers)
        futs = [self._ex.submit(fn, *args) for fn, args in calls]
        n, pending = len(futs), set(futs)
        progress("%s (0/%d, %d processes)" % (label, n, self.workers), f0)
        while pending:
            if stop():
                for f in pending:
                    f.cancel()
                raise AnalysisCancelled()
            _done, pending = wait(pending, timeout=0.3, return_when=FIRST_COMPLETED)
            if _done:
                k = n - len(pending)
                progress("%s (%d/%d, %d processes)" % (label, k, n, self.workers), f0 + (f1 - f0) * k / n)
        return [f.result() for f in futs]


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


def analysis_slot(project):
    """Atmosphere slot (index in atmosphere.atm) the analyses evaluate: project['analysis_atm'] if that slot is
    active, else the first active slot.  A spectral import has one atmosphere (slot 0)."""
    a = P.deep_merge(P.DEFAULT_PROJECT, project)["atmosphere"]
    if a["mode"] == "spectral":
        return 0
    on = [i for i, at in enumerate(a["atm"]) if at.get("on")]
    want = project.get("analysis_atm")
    return want if want in on else (on[0] if on else 0)


def analysis_atmosphere(project, rg):
    """The range result of the analysis atmosphere (rg['atm'] lists the active slots only)."""
    a = P.deep_merge(P.DEFAULT_PROJECT, project)["atmosphere"]
    if a["mode"] == "spectral":
        return rg["atm"][0]
    slot = analysis_slot(project)
    i = sum(1 for at in a["atm"][:slot] if at.get("on"))
    return rg["atm"][min(i, len(rg["atm"]) - 1)]


def atm_path(project, key):
    """Input path of `key` (sigma, V_km, F_PR, ...) in the analysis atmosphere slot."""
    return "atmosphere.atm.%d.%s" % (analysis_slot(project), key)


def fast(project):
    """Shallow copy that skips outputs the analyses do not use (P80 / P90, TTP and geometric ranges): same TRM4 ranges,
    less run time."""
    p = dict(project)
    p["_what_if"] = dict(project.get("_what_if") or {}, no_prob=True, no_extra=True)
    return p


def model_ranges(project):
    """Full model run -> ({task: range km}, warnings) in the analysis atmosphere.  Raises ModelError for invalid
    cases."""
    _m, res = run_project(fast(project))
    rg = res.get("range")
    if not rg or not rg["atm"]:
        raise ModelError("Range analyses need 'Field performance' mode and at least one task.")
    return task_ranges(analysis_atmosphere(project, rg)), list(res["warnings"])


def task_ranges(a, below="first"):
    """{task: range km} of one atmosphere with the engine's sentinels mapped to numbers: infinite (beyond the grid)
    -> last range; None (task fails already at the first range) -> the first range (below="first", keeps log
    elasticities finite) or 0 (below="zero", no percentage gain from an undefined reference)."""
    out = {}
    for t in a["tasks"]:
        R0 = t["R0"]
        if R0 is None:
            R0 = float(a["R"][0]) if below == "first" else 0.0
        elif not np.isfinite(R0):
            R0 = float(a["R"][-1])
        out[t["name"]] = float(R0)
    return out


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

# inputs that feed consistency checks, the exposure budget or the system data only - a sweep over them returns flat
# ranges (parameter study in reports/, Sec. 4.9); the sweep list does not offer them
NO_RANGE_EFFECT = {"basic.fov_h_deg", "basic.fov_v_deg", "optics.F_spec", "optics.rel_illum", "display.n_h",
                   "display.n_v", "detector.fill_limit_pct", "detector.bright_refl", "detector.bright_dT_K",
                   "detector.snr_req", "stab.smear_allow_px", "basic.exp_min_ms"}

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
    _m, res = run_project(fast(project))
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


def _what_if_ranges(project, what_if):
    """Ranges with the what-if switches applied, None for an invalid case (worker function)."""
    p = copy.deepcopy(project)
    p["_what_if"] = what_if
    try:
        return model_ranges(p)[0]
    except ModelError:
        return None


def limiting_plan(project):
    """(calls, finish) of the limiting-factor analysis: the independent runs for a Runner and the assembly."""
    facs = factor_list(project)
    calls = [(model_ranges, (project,))] + [(_what_if_ranges, (project, wi)) for _name, wi in facs]

    def finish(results):
        base = results[0][0]
        rows = []
        for (name, _wi), r in zip(facs, results[1:]):
            if r is None:
                continue
            gain = {t: 100.0 * (r[t] / base[t] - 1.0) if base[t] > 0 else 0.0 for t in base}
            rows.append({"factor": name, "ranges": r, "gain_pct": gain})
        return _limiting_result(project, base, rows)
    return calls, finish


def limiting_factors(project, progress=None, stop=None, runner=None):
    """Range gain per task when each degradation is removed.  Returns dict with 'base', 'rows'."""
    progress = progress or _noop
    calls, finish = limiting_plan(project)
    out = finish((runner or Runner(1)).map(calls, progress, stop, "Limiting factors"))
    progress("Limiting factors: done", 1.0)
    return out


def _limiting_result(project, base, rows):
    tasks = list(base)
    key = tasks[-1] if tasks else None          # the most demanding (last) task decides the ranking
    rows.sort(key=lambda x: -x["gain_pct"].get(key, 0.0))
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
    ("atmosphere.atm.*.sigma", "Extinction coefficient (atm %d)", 30.0),      # the analysis atmosphere slot
    ("atmosphere.atm.*.V_km", "Visual range (atm %d)", 30.0),
    ("atmosphere.atm.*.rh_pct", "Relative humidity (atm %d)", 20.0),
    ("optics.f_mm", "Focal length", 2.0),
    ("optics.tau_opt", "Optics transmission", 5.0),
    ("optics.q", "Aberration parameter q", 10.0),
    ("stab.rand_h_mrad", "Random jitter h", 30.0),
    ("stab.rand_v_mrad", "Random jitter v", 30.0),
    ("turbulence.cn2", "Turbulence Cn2", 50.0),
    ("optics.D_mm", "Aperture diameter", 2.0),
    ("optics.F_general", "F-number", 2.0),
    ("detector.pitch_h_um", "Pixel pitch (both axes, constant fill factor)", 1.0),
    # cycle criteria: Johnson 1958 quotes about +/-25 % around the 50 % values (e.g. recognition 4.0 +/- 0.8)
    ("target.tasks.*.lp", "%s criterion (cycles)", 25.0),
    ("display.snr_th", "Threshold SNR (observer)", 20.0),
    ("display.t_eye_s", "Eye integration time", 25.0),
]
# inputs whose physical group must move together (the pitch carries the other axis and the active size)
_CONSISTENT = {"detector.pitch_h_um": "ff2"}

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
        visib = cat == "Visible" and p["atmosphere"]["mode"] == "visibility" or p["atmosphere"]["mode"] == "weather"
        if path == "atmosphere.atm.*.sigma" and (visib or p["atmosphere"]["mode"] == "spectral"):
            continue
        if path in ("atmosphere.atm.*.V_km", "atmosphere.atm.*.rh_pct") and not visib or                 path == "atmosphere.atm.*.rh_pct" and p["atmosphere"]["mode"] != "weather":
            continue
        if path.startswith("atmosphere.atm.*."):
            slot = analysis_slot(p)
            path, label = path.replace("*", str(slot)), label % (slot + 1)
        if path == "optics.q" and p["optics"]["aberration"] != "q":
            continue
        if path.startswith("stab.rand") and not p["stab"]["random_on"]:
            continue
        if path == "turbulence.cn2" and not (p["turbulence"]["on"] and (cat != "Thermal" or
                                                                        p["turbulence"].get("thermal"))):
            continue
        mode = p["turbulence"]["cn2_mode"]
        if path == "turbulence.cn2" and (mode == "weather" or mode in X.CN2_PROFILES and not X.CN2_PROFILES[mode][2]):
            continue                                       # the Cn2 field is not used by these modes (extensions)
        if path == "optics.D_mm" and p["optics"].get("aperture") == "general":
            continue
        if path == "optics.F_general" and p["optics"].get("aperture") != "general":
            continue
        if path.startswith("display.") and p["display"].get("observer", "legacy") == "algorithm":
            continue
        if path == "display.t_eye_s" and p["mode"]["stream"] == "still":
            continue
        if path == "target.tasks.*.lp":
            out += [("target.tasks.%d.lp" % i, label % t["name"], pct) for i, t in enumerate(p["target"]["tasks"])
                    if t.get("on", True)]
            continue
        out.append((path, label, pct))
    return out


def _set_input(case, path, value):
    """Set one uncertainty input; the pitch keeps its physical group consistent (see _CONSISTENT)."""
    if path in _CONSISTENT:
        apply_policy(case, path, value, _CONSISTENT[path])
    else:
        set_path(case, path, value)


# Derivative step 5 %: ranges are quantised by the AMOP / range grids (steps of a few %), so a 1 % central
# difference can return a wrong sign for target size, focal length and pitch in sampling-limited systems.
UNC_DEFAULTS = {"method": "rss", "mc_n": 200, "seed": 1, "coverage": 0.95, "k": 2.0, "deriv_step_pct": 5.0,
                "correlations": [], "morris_r": 10, "sobol_n": 32}
GLOBAL_METHODS = ("morris", "sobol")


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
        key = path
        if path not in stored and path.startswith("atmosphere.atm."):
            # another analysis atmosphere was selected: keep the settings stored for the same input of the old slot
            key = next((k for k in stored if k.startswith("atmosphere.atm.") and
                        k.rsplit(".", 1)[-1] == path.rsplit(".", 1)[-1]), path)
        e.update(stored.get(key, {}))
        if key in stored and "on" not in stored[key]:
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
    if s["method"] in GLOBAL_METHODS:
        return global_sensitivity(project, items, s["method"], r=int(s["morris_r"]), n=int(s["sobol_n"]),
                                  seed=int(s["seed"]), progress=progress, stop=stop)
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
    if path.endswith(".rh_pct"):
        return min(max(v, 0.0), 100.0)
    return max(v, 1e-30)        # all offered inputs are positive physical quantities (dark currents ~1e-15 A)


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
                coverage=0.95, k=2.0, stop=None, evaluate=None, deriv_step=0.05, runner=None):
    """Uncertainty study.

    items: [(path, label, pct)] or [{"path", "label", "pct", "meaning", "dist"}]
    Always computed: OAT variation (each input at -/+ its stated value) and RSS propagation with local
    sensitivities; method="mc" adds a Monte Carlo propagation with `mc_n` samples and a fixed seed (with the model as
    evaluator the samples run in a process pool, Runner; the result does not depend on the number of processes).
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
            _set_input(case, path, xv)
            try:
                res[sgn] = (xv, run(case))
            except ModelError as e:
                res[sgn] = (xv, dict(base))
                notes.append("%s at %+g %%: model error (%s) - nominal value used" % (it["label"], sgn * it["pct"], e))
        # local sensitivity dR/dx by central differences; the step stays inside the input's valid interval
        h = abs(x0) * deriv_step if x0 else deriv_step
        r_hi, r_lo, x_hi, x_lo = None, None, x0, x0
        for sgn in (1, -1):
            case = copy.deepcopy(project)
            xs = _clip(path, x0 + sgn * h)
            _set_input(case, path, xs)
            try:
                rr = run(case)
            except ModelError:
                rr, xs = dict(base), x0
            if sgn > 0:
                r_hi, x_hi = rr, xs
            else:
                r_lo, x_lo = rr, xs
        c = {t: (r_hi[t] - r_lo[t]) / (x_hi - x_lo) if x_hi != x_lo else 0.0 for t in tasks}
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
        # draw every sample first (same order as one-by-one), then run them - in the process pool for the model
        changes = []
        for _i in range(int(mc_n)):
            z = L @ rng.standard_normal(len(paths)) if len(paths) else []
            changes.append([(r["path"], _clip(r["path"], r["x0"] * _sample(r["dist"], r["u_rel"], float(zi))))
                            for r, zi in zip(rows, z)])
        if evaluate is None:
            own = runner is None
            runner = runner or Runner()
            f0 = done[0] / max(n_runs, 1)
            try:
                results = runner.map([(_case_ranges, (project, ch)) for ch in changes], progress, stop,
                                     "Monte Carlo samples", f0, 1.0)
            finally:
                if own:
                    runner.close()
        else:
            results = []
            for i, ch in enumerate(changes):
                progress("Monte Carlo sample %d / %d" % (i + 1, mc_n), done[0] / max(n_runs, 1))
                case = copy.deepcopy(project)
                for path, v in ch:
                    _set_input(case, path, v)
                try:
                    results.append(run(case))
                except ModelError:
                    results.append(None)
        failed = sum(1 for rr in results if rr is None)
        for rr in results:
            if rr is not None:
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
# range bands: weather x turbulence (report phase 3)
# ---------------------------------------------------------------------------------------------
def _turbulence_on(p):
    tb = p["turbulence"]
    return p["mode"]["environment"] == "field" and bool(tb["on"]) and (p["category"] != "Thermal" or
                                                                          bool(tb.get("thermal")))


def _scale_turbulence(project, scale):
    """Copy of the project with the turbulence strength Cn2 x scale (r0 x scale^-3/5 in the r0 mode, the whole
    Hufnagel-Valley profile in the hv mode, the whole profile of the other altitude profiles and of the weather
    mode)."""
    case = copy.deepcopy(project)
    tb = case.setdefault("turbulence", {})
    if tb.get("cn2_mode") == "r0":
        tb["r0_cm"] = float(tb.get("r0_cm", 5.0)) * scale ** (-0.6)
    elif tb.get("cn2_mode") == "hv":
        tb["hv_scale"] = float(tb.get("hv_scale", 1.0)) * scale
    elif tb.get("cn2_mode") in X.CN2_PROFILES or tb.get("cn2_mode") == "weather":
        tb["cn2_scale"] = float(tb.get("cn2_scale", 1.0)) * scale
    else:
        tb["cn2"] = float(tb.get("cn2", 1e-14)) * scale
    return case


def _all_atm_ranges(project):
    """[(atmosphere label, {task: range km})] of every active atmosphere, None for an invalid case (worker)."""
    try:
        _m, res = run_project(fast(project))
    except ModelError:
        return None
    rg = res.get("range")
    if not rg or not rg["atm"]:
        return None
    return [(a["label"], task_ranges(a)) for a in rg["atm"]]


def range_bands(project, progress=None, stop=None, factor=10.0, runner=None):
    """DRI ranges over weather x turbulence: every active atmosphere slot (one run computes all of them) and, when
    turbulence acts, Cn2 / factor, Cn2 and Cn2 x factor (one decade of Cn2 ~ +/-35 % range in the visible, report
    Sec. 4.3).  The band of a task is the smallest / largest range of the grid - a scenario envelope, not a
    probability interval."""
    progress = progress or _noop
    p = P.deep_merge(P.DEFAULT_PROJECT, project)
    if p["mode"]["environment"] != "field":
        raise ModelError("Range bands need 'Field performance' mode.")
    factor = float(factor)
    if not factor > 1:
        raise ValueError("The turbulence factor must be > 1.")
    levels = [("Cn2 / %g" % factor, 1.0 / factor), ("Cn2 nominal", 1.0), ("Cn2 x %g" % factor, factor)] \
        if _turbulence_on(p) else [("no turbulence" if p["category"] != "Thermal" or p["turbulence"].get("thermal")
                                    else "no turbulence (Thermal, TRM4)", 1.0)]
    calls = [(_all_atm_ranges, (_scale_turbulence(project, s) if s != 1.0 else project,)) for _l, s in levels]
    res = (runner or Runner(1)).map(calls, progress, stop, "Range bands")
    nominal = res[[s for _l, s in levels].index(1.0)]
    if nominal is None:
        raise ModelError("The nominal case has no valid ranges.")
    atms = [lab for lab, _r in nominal]
    tasks = list(nominal[0][1])
    grid_ = {t: [[r[i][1][t] if r is not None else np.nan for i in range(len(atms))] for r in res] for t in tasks}
    i_an = min(sum(1 for at in p["atmosphere"]["atm"][:analysis_slot(p)] if at.get("on")), len(atms) - 1) \
        if p["atmosphere"]["mode"] != "spectral" else 0
    base = {t: nominal[i_an][1][t] for t in tasks}
    band = {}
    for t in tasks:
        v = np.array(grid_[t], float)
        ok = v[np.isfinite(v)]
        band[t] = {"min": float(ok.min()) if ok.size else np.nan, "max": float(ok.max()) if ok.size else np.nan,
                   "nominal": base[t]}
    progress("Range bands: done", 1.0)
    return {"kind": "bands", "tasks": tasks, "base": base, "atms": atms, "turb": [l for l, _s in levels],
            "factor": factor, "grid": grid_, "band": band, "analysis_atm": atms[i_an], "time": _now(),
            "invalid": [l for (l, _s), r in zip(levels, res) if r is None], "engine": describe_engine(project),
            "method": "Scenario envelope over the active atmospheres%s (full model run per turbulence level)." % (
                " x Cn2 / %g, nominal, x %g" % (factor, factor) if len(levels) > 1 else "")}


# ---------------------------------------------------------------------------------------------
# global sensitivity (report phase 3): Morris screening and Sobol variance indices
# ---------------------------------------------------------------------------------------------
CN2_SEASONS = ("summer", "winter")


def cn2_climates():
    return sorted({c for c, _t in P.CN2_TABLE})


def _cn2_case(project, cn2, time):
    """Copy of the project with turbulence from a Table C.2 value: Cn2 at 2 m, simplified height dependence."""
    case = copy.deepcopy(project)
    tb = case.setdefault("turbulence", {})
    tb.update(on=True, cn2_mode="height", cn2=float(cn2), h_ref_m=2.0, time=time, cn2_preset="custom")
    return case


def cn2_statistics_rows(climate="Arid", season="summer", overcast=False, neutral_day=False):
    """Rows of the Cn2 statistics (no model run): label, time, statistic, Cn2 at 2 m and the height exponent h_exp
    ('4/3' clear-sky day, '2/3' night / neutral) of each row - see cn2_statistics."""
    if (climate, "Noon") not in P.CN2_TABLE or season not in CN2_SEASONS:
        raise ValueError("Unknown climate / season: %s / %s" % (climate, season))
    j = CN2_SEASONS.index(season)               # Table C.2 columns: 90 % winter, 90 % summer, 50 % winter, 50 % summer
    col = {"90 %": 1 - j, "50 %": 3 - j}
    rows = []
    # neutral daytime exponent (h^-2/3) for winter noon: passed to the height mode as its 'night' exponent
    win_neutral = bool(neutral_day) and season == "winter"
    for t_lab, t_key, tod in (("Noon", "Noon", "day"), ("Night", "Night", "night")):
        for pct in ("50 %", "90 %"):
            rows.append({"label": "%s, %s of the occasions%s" % (t_lab, pct, ", h^-2/3" if tod == "day" and
                                                                  win_neutral else ""), "time": t_lab, "pct": pct,
                         "cn2": P.CN2_TABLE[(climate, t_key)][col[pct]], "tod": tod,
                         "h_exp": "2/3" if tod == "night" or win_neutral else "4/3"})
    if overcast:
        for pct in ("50 %", "90 %"):
            rows.append({"label": "Noon overcast, %s (Cn2 x %g%s)" % (pct, X.OVERCAST_NOON_FACTOR, ", h^-2/3" if
                                                                     neutral_day else ""), "time": "Noon overcast",
                         "pct": pct, "cn2": P.CN2_TABLE[(climate, "Noon")][col[pct]] * X.OVERCAST_NOON_FACTOR,
                         "tod": "day", "h_exp": "2/3" if neutral_day else "4/3"})
    if climate == "Arid" and season == "summer":
        rows.append({"label": "Sunrise, typical minimum", "time": "Sunrise", "pct": "typical",
                     "cn2": X.CN2_SUNRISE_ARID_SUMMER, "tod": "night", "h_exp": "2/3"})
    return rows


def cn2_statistics(project, climate="Arid", season="summer", overcast=False, progress=None, stop=None, runner=None,
                   neutral_day=False):
    """DRI ranges for the measured turbulence statistics of a climate (TRM4 Table C.2, Fraunhofer IOSB long-term
    scintillometer data): noon and night, the Cn2 not exceeded on 50 % and 90 % of the occasions.  The 90 % row is
    the range reached on at least 90 % of the occasions at that time of day.  Optional rows: overcast noon (Cn2 x 0.1,
    clouds reduce the midday Cn2 by 1 - 2 orders) and, for arid summer, the typical sunrise minimum (~1.1e-15 at 2 m,
    Negev measurements of FGAN-FOM).  The
    turbulence settings of the project (exposure, short-exposure factor, mitigation) are kept.

    neutral_day (extension): the daytime height dependence h^-2/3 instead of h^-4/3 for the overcast noon rows and, in
    winter, the noon rows - FGAN-FOM (Weiss-Wrana 2005): the -4/3 exponent holds under a clear sky only."""
    progress = progress or _noop
    p = P.deep_merge(P.DEFAULT_PROJECT, project)
    if p["mode"]["environment"] != "field":
        raise ModelError("Cn2 statistics need 'Field performance' mode.")
    if p["category"] == "Thermal" and not p["turbulence"].get("thermal"):
        raise ModelError("TRM4 neglects turbulence in the Thermal category: tick 'Apply turbulence in the Thermal "
                         "category' (extension) to evaluate the Cn2 statistics.")
    rows = cn2_statistics_rows(climate, season, overcast, neutral_day)
    calls = [(_all_atm_ranges, (_cn2_case(project, r["cn2"], "day" if r["h_exp"] == "4/3" else "night"),))
             for r in rows]
    calls.append((_all_atm_ranges, (project,)))
    res = (runner or Runner(1)).map(calls, progress, stop, "Cn2 statistics")
    nominal = res[-1]
    if nominal is None:
        raise ModelError("The nominal case has no valid ranges.")
    atms = [lab for lab, _r in nominal]
    i_an = min(sum(1 for at in p["atmosphere"]["atm"][:analysis_slot(p)] if at.get("on")), len(atms) - 1) \
        if p["atmosphere"]["mode"] != "spectral" else 0
    tasks = list(nominal[0][1])
    for r, rr in zip(rows, res[:-1]):
        r["ranges"] = {t: (rr[i_an][1][t] if rr is not None else np.nan) for t in tasks}
    progress("Cn2 statistics: done", 1.0)
    return {"kind": "cn2stats", "climate": climate, "season": season, "overcast": bool(overcast), "tasks": tasks,
            "neutral_day": bool(neutral_day),
            "base": {t: nominal[i_an][1][t] for t in tasks}, "rows": rows, "analysis_atm": atms[i_an],
            "invalid": [r["label"] for r, rr in zip(rows, res[:-1]) if rr is None], "time": _now(),
            "engine": describe_engine(project),
            "method": "TRM4 Table C.2 (%s climate, %s): Cn2 at 2 m with the simplified height dependence (day h^-4/3, "
                      "night h^-2/3%s); full model run per row; the project's other turbulence settings are kept." % (
                          climate, season, "; extension: h^-2/3 also for the %s - FGAN-FOM 2005: h^-4/3 holds under "
                          "a clear sky only" % ("overcast and winter noon rows" if season == "winter" else
                                                "overcast noon rows") if neutral_day else "")}


def _case_ranges(project, changes):
    """Ranges with [(path, value)] applied, None for an invalid case (worker function)."""
    case = copy.deepcopy(project)
    for path, v in changes:
        _set_input(case, path, v)
    try:
        return model_ranges(case)[0]
    except ModelError:
        return None


def _input_box(project, items):
    """Interval [lo, hi] of each input: its stated +/- limits (sampled uniformly by the global methods)."""
    box = []
    for it in items:
        x0 = float(get_path(project, it["path"]))
        a = abs(float(it["pct"])) / 100.0
        lo, hi = _clip(it["path"], x0 * (1 - a)), _clip(it["path"], x0 * (1 + a))
        box.append((min(lo, hi), max(lo, hi), x0))
    return box


class _Cache:
    """Model runs keyed by the input vector: repeated points (Morris trajectories, Sobol matrices) run once."""

    def __init__(self, project, items, box):
        self.project, self.items, self.box = project, items, box
        self.store, self.n_unique = {}, 0

    def point(self, u):
        return tuple(float("%.12g" % (lo + float(ui) * (hi - lo))) for ui, (lo, hi, _x0) in zip(u, self.box))

    def evaluate(self, points, runner, progress, stop, label, f0, f1):
        new = [x for x in dict.fromkeys(points) if x not in self.store]
        calls = [(_case_ranges, (self.project, [(it["path"], v) for it, v in zip(self.items, x)])) for x in new]
        for x, r in zip(new, runner.map(calls, progress, stop, label, f0, f1) if calls else []):
            self.store[x] = r
        self.n_unique += len(new)
        return [self.store[x] for x in points]


def global_sensitivity(project, items, method="morris", r=10, n=32, seed=1, progress=None, stop=None, runner=None,
                       levels=4):
    """Global sensitivity of the DRI ranges over the stated input intervals (each input uniform on x0 +/- pct).

    morris: r one-at-a-time trajectories on a `levels`-level grid (Morris 1991; mu* = mean |elementary effect|, sigma =
            their spread - a large sigma flags interactions / regime changes); r (k + 1) runs.
    sobol:  first-order S_i (Saltelli 2010) and total S_Ti (Jansen 1999) indices from N (k + 2) runs, with 95 %
            bootstrap intervals; S_Ti - S_i is the share of interactions.
    Runs go through a cache keyed by the input vector and a process pool (Runner)."""
    progress = progress or _noop
    items = _normalize_items(items)
    if not items:
        raise ValueError("Select at least one input with a non-zero uncertainty.")
    base, _w = model_ranges(project)
    tasks = list(base)
    box = _input_box(project, items)
    k = len(items)
    rng = np.random.default_rng(int(seed))
    own = runner is None
    runner = runner or Runner()
    cache = _Cache(project, items, box)
    small = []
    try:
        rows = [{"path": it["path"], "label": it["label"], "pct": it["pct"], "lo": lo, "hi": hi, "x0": x0}
                for it, (lo, hi, x0) in zip(items, box)]
        if method == "morris":
            delta = levels / (2.0 * (levels - 1))
            starts = np.arange(levels // 2) / (levels - 1.0)             # grid values from which +delta stays in [0, 1]
            ee = {t: [[] for _ in range(k)] for t in tasks}
            traj = []
            for _j in range(int(r)):
                x = rng.choice(starts, size=k)
                pts, order = [x.copy()], rng.permutation(k)
                for i in order:
                    x = x.copy()
                    x[i] += delta
                    pts.append(x)
                traj.append((order, pts))
            flat = [cache.point(u) for _o, pts in traj for u in pts]
            vals = cache.evaluate(flat, runner, progress, stop, "Morris screening", 0.0, 1.0)
            pos = 0
            for order, pts in traj:
                ys = vals[pos:pos + len(pts)]
                pos += len(pts)
                for step, i in enumerate(order):
                    a, b = ys[step], ys[step + 1]
                    if a is None or b is None:
                        continue
                    for t in tasks:
                        ee[t][i].append((b[t] - a[t]) / delta)
            for i, row in enumerate(rows):
                row["mu_star"] = {t: float(np.mean(np.abs(ee[t][i]))) if ee[t][i] else np.nan for t in tasks}
                row["mu"] = {t: float(np.mean(ee[t][i])) if ee[t][i] else np.nan for t in tasks}
                row["sigma"] = {t: float(np.std(ee[t][i], ddof=1)) if len(ee[t][i]) > 1 else np.nan for t in tasks}
                row["n_effects"] = len(ee[tasks[0]][i]) if tasks else 0
            n_planned = int(r) * (k + 1)
            label = "Morris screening, %d trajectories x %d levels" % (int(r), levels)
        elif method == "sobol":
            N = int(n)
            A, B = rng.random((N, k)), rng.random((N, k))
            mats = [A, B] + [np.where(np.arange(k) == i, B, A) for i in range(k)]
            flat = [cache.point(u) for M_ in mats for u in M_]
            vals = cache.evaluate(flat, runner, progress, stop, "Sobol indices", 0.0, 1.0)
            blocks = [vals[j * N:(j + 1) * N] for j in range(len(mats))]
            for t in tasks:
                def col(block):
                    return np.array([np.nan if v is None else v[t] for v in block], float)
                fA, fB = col(blocks[0]), col(blocks[1])
                for i, row in enumerate(rows):
                    fAB = col(blocks[2 + i])
                    ok = np.isfinite(fA) & np.isfinite(fB) & np.isfinite(fAB)
                    s1, st, ci1, cit = _sobol_indices(fA[ok], fB[ok], fAB[ok], rng)
                    row.setdefault("S1", {})[t], row.setdefault("ST", {})[t] = s1, st
                    row.setdefault("S1_ci", {})[t], row.setdefault("ST_ci", {})[t] = ci1, cit
            n_planned = N * (k + 2)
            label = "Sobol indices, N = %d base samples (Saltelli 2010 / Jansen 1999), 95 %% bootstrap" % N
            if N < 32:
                small = ["N = %d is small: the indices are indicative only (see the bootstrap intervals)." % N]
        else:
            raise ValueError("Unknown global method %r" % method)
    finally:
        if own:
            runner.close()
    n_fail = sum(1 for v in cache.store.values() if v is None)
    key = tasks[-1] if tasks else None
    score = "mu_star" if method == "morris" else "ST"
    rows.sort(key=lambda x: -(x[score].get(key, 0.0) if np.isfinite(x[score].get(key, np.nan)) else -1.0))
    progress("Global sensitivity: done", 1.0)
    return {"kind": "global", "method": method, "label": label, "tasks": tasks, "base": base, "rows": rows,
            "rank_task": key, "n_planned": n_planned, "n_runs": cache.n_unique, "n_fail": n_fail, "time": _now(),
            "engine": describe_engine(project), "settings": {"r": int(r), "n": int(n), "seed": int(seed),
                                                             "levels": levels},
            "notes": ["Each input is sampled uniformly on its stated +/- interval (whatever its stated meaning)."] + small +
                     (["%d of %d model runs were invalid and are left out." % (n_fail, cache.n_unique)] if n_fail else [])}


def _sobol_indices(fA, fB, fAB, rng, n_boot=200):
    """S_i (Saltelli 2010) and S_Ti (Jansen 1999) with 95 % bootstrap intervals.  The outputs are centred first:
    same expectation, much smaller estimator variance when the range is large compared with its spread."""
    def est(a, b, ab):
        both = np.concatenate([a, b])
        V = float(np.var(both, ddof=1)) if a.size > 1 else 0.0
        if V <= 0:
            return 0.0, 0.0
        m = float(both.mean())
        return float(np.mean((b - m) * (ab - a)) / V), float(0.5 * np.mean((a - ab) ** 2) / V)
    if fA.size < 4:
        return np.nan, np.nan, (np.nan, np.nan), (np.nan, np.nan)
    s1, st = est(fA, fB, fAB)
    bs = []
    for _ in range(n_boot):
        j = rng.integers(0, fA.size, fA.size)
        bs.append(est(fA[j], fB[j], fAB[j]))
    bs = np.array(bs)
    q = lambda c: (float(np.quantile(bs[:, c], 0.025)), float(np.quantile(bs[:, c], 0.975)))
    return s1, st, q(0), q(1)


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
    if k == "cn2stats":
        tasks = an["tasks"]
        head += [["# method", an["method"]], ["# atmosphere", an["analysis_atm"]]]
        rows = [["row", "time", "statistic", "cn2_2m"] + ["%s_km" % t for t in tasks]]
        rows += [[r["label"], r["time"], r["pct"], r["cn2"]] +
                 ["" if not np.isfinite(r["ranges"][t]) else r["ranges"][t] for t in tasks] for r in an["rows"]]
        rows.append(["nominal (project settings)", "", "", ""] + [an["base"][t] for t in tasks])
        return head + rows
    if k == "bands":
        tasks = an["tasks"]
        head += [["# method", an["method"]]]
        rows = [["task", "turbulence"] + ["%s_km" % a for a in an["atms"]]]
        for t in tasks:
            for lab, row in zip(an["turb"], an["grid"][t]):
                rows.append([t, lab] + ["" if not np.isfinite(v) else v for v in row])
        rows.append([])
        rows.append(["task", "nominal_km", "band_min_km", "band_max_km"])
        rows += [[t, an["band"][t]["nominal"], an["band"][t]["min"], an["band"][t]["max"]] for t in tasks]
        return head + rows
    if k == "global":
        tasks = an["tasks"]
        head += [["# method", an["label"]], ["# runs", an["n_runs"]]] + [["# note", n] for n in an["notes"]]
        keys = ("mu_star", "mu", "sigma") if an["method"] == "morris" else ("S1", "ST")
        rows = [["input", "path", "low", "high"] + ["%s_%s" % (t, q) for t in tasks for q in keys]]
        rows += [[r["label"], r["path"], r["lo"], r["hi"]] + [r[q][t] for t in tasks for q in keys] for r in an["rows"]]
        return head + rows
    if k == "scenarios":
        tasks = an["tasks"]
        rows = [["scenario"] + ["%s_km" % t for t in tasks] + ["%s_delta_pct" % t for t in tasks] + ["engine"]]
        rows += [[r["name"]] + [r["ranges"].get(t, "") for t in tasks] + [r["delta_pct"][t] for t in tasks] +
                 [r["engine"]] for r in an["rows"]]
        return head + rows
    return head
