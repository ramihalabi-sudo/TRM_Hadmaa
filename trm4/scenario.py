"""Unit-labelled scenario record (field map Sec. 12.8).

The project dictionary is the editing format of the application; this module exports the same
inputs in the layered schema proposed by the field map - sensor, optical transfer, atmosphere,
noise, motion, target, task and trace - with explicit units, the data source of every block and
the component coverage that the engine resolved.  It is a documentation / exchange record: the
engine does not read it back, the project file remains the input.
"""
import json
import math

from . import presets as P
from .model import COMPONENTS, MODEL_VERSION, VALIDATION_VERSION, run_id


def _file_id(fobj, imports, what=None):
    """File name and SHA-256 of an imported file (from the traceability list of the run)."""
    name = (fobj or {}).get("name", "")
    if not (fobj or {}).get("text"):
        return None
    for im in imports:
        if im["name"] == name and (what is None or what in im["what"]):
            return {"name": name, "sha256": im["sha256"]}
    return {"name": name, "sha256": None}


def _range(R0, a):
    if R0 is None:
        return "< %.3g" % a["R"][0]
    if not math.isfinite(R0):
        return "> %.3g" % a["R"][-1]
    return float(R0)


def build(project, res):
    """Scenario record of a finished run (`res` from TRM4Model.run)."""
    p = P.deep_merge(P.DEFAULT_PROJECT, project)
    pv = res.get("provenance") or {}
    imports = pv.get("imports", [])
    o, d, b, st, tg, am, tb, disp = (p["optics"], p["detector"], p["basic"], p["stab"], p["target"], p["atmosphere"],
                                     p["turbulence"], p["display"])
    win = P.qe_window(p)
    cov = pv.get("coverage", [])
    src = o.get("mtf_source", "model")
    mtf_src = {"model": "theoretical", "zemax": "zemax", "measured": "measured", "device": "measured"}[src]
    included = cov[0]["components"] if cov else []           # the optics source is resolved first
    mode = st.get("jitter_mode", "model")
    tasks = [t for t in tg["tasks"] if t.get("on")]
    t_int = None
    for _sec, name, val, unit in res.get("info", []):
        if name == "Integration time" and unit == "ms":
            t_int = float(val)
            break
    rec = {
        "schema": "TRM_HADMAA scenario 1.0 (field map Sec. 12.8)",
        "sensor": {
            "band": P.band_of(*win) if win else None, "band_um": list(win) if win else None,
            "category": p["category"], "imager_type": p["imager_type"],
            "pixel_pitch_um": [d["pitch_h_um"], d["pitch_v_um"]], "format": [d["n_h"], d["n_v"]],
            "focal_length_mm": o["f_mm"],
            "f_number": o["F_general"] if o["aperture"] == "general" else None, "aperture_mm": o["D_mm"],
            "qe_curve_id": d["qe_preset"] if not (p["category"] == "Thermal" and p["imager_type"] == "uncooled"
                                                  and d["uncooled_response"] == "flat") else
            "flat %g-%g um" % (d["cuton_um"], d["cutoff_um"]),
            "integration_ms": t_int, "frame_rate_hz": b["frame_rate"],
            "readout": b.get("readout", "global"), "readout_ms": b.get("readout_ms", 0.0),
            # operating-mode profile and input semantics (research review Sec. 3.1, 3.5 - 3.8)
            "operating_mode": d.get("op_mode") or None, "roi": b.get("roi") or None,
            "exposure_overlaps_readout": b.get("exp_overlap", True), "guard_ms": b.get("guard_ms", 0.0),
            "hardware_exposure_ms": [b.get("exp_min_ms", 0.0) or None, b.get("exp_max_ms", 0.0) or None],
            "binning": {"factor": [b["bin_h"], b["bin_v"]], "kind": b.get("bin_kind", "charge")},
            "qe_basis": d.get("qe_basis", "unspecified"),
            "capacity": {"storage_e": d["storage_e"], "node": d.get("cap_node", "unknown"),
                         "camera_saturation_e": d.get("sat_e") or None,
                         "adc_full_scale_e": (2 ** int(d["adc_bits"])) * d["lsb_e"] if d.get("adc_bits") and
                         d["adc_mode"] == "carriers" else None,
                         "usable_limit": pv.get("capacity_limit"), "verified": pv.get("capacity_verified")},
            "dark_current": {"mode": d.get("dark_mode", "value"), "A": d["dark_A"] if d.get("dark_mode", "value") ==
                             "value" else None, "T_sensor_K": d.get("T_sensor_K") or None}},
        "optical_transfer": {
            "source": mtf_src, "domain": "end_to_end" if src == "device" else "lens_only",
            "file_id": _file_id(o.get("zemax_mtf"), imports, "MTF") if src != "model" else None,
            "included_components": included,
            "field": o.get("zemax_mtf_field") if src != "model" else None,
            "metadata": o.get("mtf_meta") or None,
            "conditions": {k: o.get("mtf_" + k) or None for k in ("band", "focus", "temp", "uncert")}
            if src != "model" else None,
            "documentation": pv.get("mtf_doc"),
            "frequency_unit": o.get("zemax_mtf_unit") if src != "model" else None,
            "transmission": {"source": "spectral" if o.get("tau_mode") == "zemax" else "scalar",
                             "file_id": _file_id(o.get("zemax_tau"), imports, "transmission"),
                             "peak": o["tau_opt"], "filter": o["tau_filter"]}},
        "atmosphere": {
            "mode": "spectral" if am["mode"] == "spectral" else "quick",
            "fast_mode": None if am["mode"] == "spectral" else {
                "via": am["mode"], "preset": am.get("preset"),
                "extinction_per_km": [a["sigma"] for a in am["atm"] if a.get("on")]},
            "tau_file": _file_id(am.get("spec_file"), imports, "Atmospheric"),
            "path_radiance_file": _file_id(am.get("path_file"), imports, "Path radiance")
            if am.get("path_mode") == "import" else None,
            "geometry_id": (am.get("meta") or {}).get("geometry") or None,
            "data_source": (am.get("meta") or {}).get("source") or None,
            "rt_versioning": {k: (am.get("meta") or {}).get(k) or None
                              for k in ("database", "rt_code", "profile", "aerosol", "resolution")},
            "turbulence_outer_scale_m": tb.get("L0_m") or None if tb["on"] else None,
            "turbulence_profile_id": None if not tb["on"] else (
                "r0 %g cm @ %g um, %g km" % (tb["r0_cm"], tb["r0_lambda_um"], tb["r0_L_km"]) if tb["cn2_mode"] == "r0"
                else "Cn2 %g m^-2/3 (%s)" % (tb["cn2"], tb["cn2_mode"]))},
        "noise": {
            "source": "measured_netd" if (p["category"] == "Thermal" and (
                p["imager_type"] == "uncooled" or d["noise_mode"] == "measured")) else "detector_model",
            "description": pv.get("noise_source"),
            "netd_mK": d["netd_mK"] if p["category"] == "Thermal" else None,
            "acquisition_config": {"blackbody_K": d.get("netd_TB_K"), "f_number": d.get("netd_F"),
                                   "integration_ms": d.get("netd_tint_ms"), "frames_averaged": d.get("netd_frames"),
                                   "gain_nuc": d.get("netd_nuc"), "measurement_port": d.get("noise_port", "raw")},
            "nps_file": _file_id(d.get("nps_file"), imports, "NPS")},
        "motion": {
            "source": "none" if (st["neglect"] or mode == "none") else
            {"model": "rms_jitter_assumption", "measured": "time_series", "psd": "angular_psd"}[mode],
            "exposure_ms": t_int, "linked_to_exposure": True,
            "los_rate_mrad_s": [st["lin_h"], st["lin_v"]] if st["lin_on"] else None,
            "jitter_rms_mrad": [st["rand_h_mrad"], st["rand_v_mrad"]] if st["random_on"] else None,
            "jitter_file": _file_id(st.get("jitter_file"), imports, "jitter") if mode == "measured" else None,
            "jitter_psd_file": _file_id(st.get("psd_file"), imports, "PSD") if mode == "psd" else None,
            "residual_los": st.get("residual_los", True)},
        "target": {
            "geometry_m": {"width": tg["W_m"], "height": tg["H_m"], "depth": tg["D_m"]},
            "spectrum": "blackbody dT %g K at %g K" % (tg["dT_K"], tg["T_bg_K"]) if p["category"] == "Thermal" else
            "reflective/emissive (%s)" % p["category"],
            "emissivity_reflectivity": {k: tg[k] for k in ("t_emis_mode", "t_refl_mode", "b_emis_mode", "b_refl_mode")},
            "background_model": "uniform (clutter %s)" % tg.get("clutter", "not_specified"),
            "scene_id": tg.get("scene_id") or None, "orientation": tg["aspect"]},
        "task": {
            "observer": {"legacy": "human", "human": "human", "algorithm": "algorithm"}[disp.get("observer", "legacy")],
            "observer_profile": disp.get("observer", "legacy"),
            "model": "johnson_legacy", "preset_version": tg.get("task_preset", "legacy"),
            "criteria_lp": {t["name"]: t["lp"] for t in tasks},
            "critical_dimension": "sqrt(projected width x projected height) per range",
            "calibration_id": disp.get("algo_calib") or None},
        "trace": {
            "run_id": pv.get("run_id") or run_id(project), "model_version": pv.get("model_version", MODEL_VERSION),
            "validation_version": pv.get("validation_version", VALIDATION_VERSION),
            "input_hashes": {im["what"]: im["sha256"] for im in imports},
            "component_coverage": pv.get("coverage", []), "components": list(COMPONENTS),
            "assumptions": list(res.get("assumptions", [])), "warnings": list(res.get("warnings", [])),
            "preset_data": pv.get("presets", [])},
    }
    rg = res.get("range")
    if rg and rg["atm"]:
        rec["results"] = {"atmosphere": rg["atm"][0]["label"],
                          "ranges_km": {t["name"]: _range(t["R0"], rg["atm"][0]) for t in rg["atm"][0]["tasks"]},
                          "status": (res.get("dashboard") or {}).get("calibration"),
                          "context": (res.get("dashboard") or {}).get("context")}
    ex = (res.get("dashboard") or {}).get("exposure")
    if ex:
        rec["exposure_budget"] = {"limits_ms": {n: t * 1e3 if math.isfinite(t) else None for n, t in ex["limits"]},
                                  "selected_ms": ex["t_sel"] * 1e3, "limiter": ex["limiter"],
                                  "feasible": ex["feasible"], "violations": ex["violations"]}
    return rec


def write(path, project, res):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(build(project, res), fh, indent=2, default=float)
