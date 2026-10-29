"""Plain-text report of TRM4 results (system data, ranges, figure-of-merit tables)."""
import json
import numpy as np


def _num(v):
    if v is None:
        return "-"
    if isinstance(v, float) and not np.isfinite(v):
        return "inf"
    return "%.5g" % v


def _fmt_range(R0, a):
    if R0 is None:
        return "< %.3g km" % a["R"][0]
    if not np.isfinite(R0):
        return "> %.3g km" % a["R"][-1]
    return "%.3f km" % R0


def _km(v):
    return "-" if v is None or (isinstance(v, float) and not np.isfinite(v)) else "%.3f" % v


def format_analyses(analyses):
    """Report sections of the sensitivity analyses (method, settings, inputs, results, diagnostics)."""
    from . import analysis as AN
    L = []
    for key, an in (analyses or {}).items():
        if not an:
            continue
        L.append("")
        if key == "limiting":
            L.append("[Limiting factors - range gain when the degradation is removed, ranked by %s]" % an["rank_task"])
            L.append("  Method: %s  Calculated %s. Engine: %s" % (an.get("method", ""), an.get("time", ""),
                                                                  an.get("engine", "")))
            for r in an["rows"]:
                L.append("  %-52s %s" % (r["factor"], "  ".join("%s %+.1f %%" % (t, g) for t, g in r["gain_pct"].items())))
            L.append("  Dominant limiting factor: %s" % (an["dominant"] or "none (all gains < 1 %)"))
            for t, v in an.get("limit_type", {}).items():
                L.append("  %-18s limited by %s" % (t, v))
        elif key == "uncertainty":
            tasks = an["tasks"]
            L.append("[Uncertainty study - %s]" % an["label"])
            L.append("  Calculated %s. Engine: %s" % (an["time"], an["engine"]))
            L.append("  One-at-a-time runs (range change for the stated -/+ value; not a probability interval):")
            for r in an["rows"]:
                L.append("    %-34s nominal %-10.5g +/-%5.1f %% (%s, %s; u = %.2f %%)  %s" % (
                    r["label"], r["x0"], r["pct"], dict(AN.MEANINGS)[r["meaning"]], r["dist"], 100 * r["u_rel"],
                    "  ".join("%s %+.3f/%+.3f km, %+.3f %%/%%, %.0f %% of u^2" % (
                        t, r["low"][t] - an["base"][t], r["high"][t] - an["base"][t], r["elasticity"][t],
                        100 * r["contrib"][t]) for t in tasks)))
            for c in an["correlations"]:
                L.append("  Correlation %s <-> %s: rho = %g" % tuple(c))
            for t in tasks:
                lo, hi = AN.oat_envelope(an, t)
                L.append("  %-18s nominal %.3f km | %s | OAT runs span %.3f - %.3f km" % (
                    t, an["base"][t], AN.interval(an, t)[2], lo, hi))
            for n in an["notes"]:
                L.append("  Note: " + n)
        elif key == "sweep":
            tasks = list(an["base"])
            L.append("[Parameter sweep: %s - %s, %s sampling]" % (an["path"], an["policy_label"], an["sampling"]))
            L.append("  Calculated %s. Engine: %s" % (an["time"], an["engine"]))
            for n in an["policy_notes"]:
                L.append("  Hold-constant note: " + n)
            L.append("  %14s  %s" % ("baseline %g" % an["base_value"], "  ".join("%s %s km" % (t, _km(an["base"][t]))
                                                                                  for t in tasks)))
            for r in an["runs"]:
                L.append("  %14.5g  %s%s" % (r["value"], "  ".join("%s %s km (%+.1f %%)" % (
                    t, _km(r["ranges"].get(t)), r["delta_pct"][t]) if r["ok"] else "" for t in tasks),
                    "" if r["ok"] else "REJECTED: " + "; ".join(r["diag"])))
        elif key == "sweep2d":
            L.append("[2-D sweep: %s x %s]" % (an["px"], an["py"]))
            for t, g in an["ranges"].items():
                L.append("  %s [km]; rows %s = %s; columns %s = %s" % (t, an["py"], an["vy"], an["px"], an["vx"]))
                for row in g:
                    L.append("    " + "  ".join("%8s" % _km(v) for v in row))
            for d in an["invalid"]:
                L.append("  Invalid: " + d)
        elif key == "advisor":
            from . import advisor as ADV
            L.extend(ADV.format_text(an))
        elif key == "bands":
            L.append("[Range bands - weather x turbulence; scenario envelope, not a probability interval]")
            L.append("  Method: %s  Calculated %s. Engine: %s" % (an["method"], an["time"], an["engine"]))
            for t in an["tasks"]:
                b = an["band"][t]
                L.append("  %-18s nominal %s km (%s), band %s - %s km" % (t, _km(b["nominal"]), an["analysis_atm"],
                                                                         _km(b["min"]), _km(b["max"])))
                for lab, row in zip(an["turb"], an["grid"][t]):
                    L.append("    %-28s %s" % (lab, "  ".join("%s %s" % (a, _km(v)) for a, v in zip(an["atms"], row))))
        elif key == "global":
            L.append("[Global sensitivity - %s]" % an["label"])
            L.append("  Calculated %s, %d model runs. Engine: %s" % (an["time"], an["n_runs"], an["engine"]))
            for r in an["rows"]:
                if an["method"] == "morris":
                    val = "  ".join("%s mu* %.3f / sigma %.3f km" % (t, r["mu_star"][t], r["sigma"][t])
                                    for t in an["tasks"])
                else:
                    val = "  ".join("%s S1 %.2f / ST %.2f" % (t, r["S1"][t], r["ST"][t]) for t in an["tasks"])
                L.append("  %-34s %.4g - %.4g  %s" % (r["label"], r["lo"], r["hi"], val))
            for n in an["notes"]:
                L.append("  Note: " + n)
        elif key == "scenarios":
            L.append("[Scenario comparison - deltas relative to '%s']" % an["rows"][0]["name"])
            for r in an["rows"]:
                L.append("  %-28s %s" % (r["name"], "  ".join("%s %s km (%+.1f %%)" % (
                    t, _km(r["ranges"].get(t)), r["delta_pct"][t]) for t in an["tasks"]) if r["ok"] else
                    "invalid: " + "; ".join(r["warnings"])))
    return L


def format_report(project, res, analyses=None):
    L = []
    L.append("TRM_HADMAAv1 performance report - %s" % project.get("name", ""))
    L.append("=" * 78)
    pv = res.get("provenance")
    if pv:
        L.append("")
        L.append("[Traceability]")
        L.append("  %-30s %s" % ("Model version", pv["model_version"]))
        if pv.get("model_reference"):
            L.append("  %-30s %s" % ("Model reference", pv["model_reference"]))
        if pv.get("validation_version"):
            L.append("  %-30s %s" % ("Validation version", pv["validation_version"]))
        if pv.get("run_id"):
            L.append("  %-30s %s  (same inputs + model version = same run ID)" % ("Run ID", pv["run_id"]))
        L.append("  %-30s %s" % ("Calculated", pv["time"]))
        L.append("  %-30s %s / %s / %s / %s" % ("Configuration", pv["category"], pv["imager_type"], pv["environment"],
                                                pv["stream"]))
        if pv["profile"].get("name"):
            L.append("  %-30s %s  [%s]%s" % ("Camera profile", pv["profile"]["name"], pv["profile"].get("config", ""),
                                            "  id %s, content %s" % (pv["profile"]["profile_id"],
                                                                     pv["profile"].get("content_hash", ""))
                                            if pv["profile"].get("profile_id") else ""))
        if pv.get("observer"):
            L.append("  %-30s %s / task preset %s" % ("Observer / criteria", pv["observer"], pv.get("task_preset", "")))
        if pv.get("noise_source"):
            L.append("  %-30s %s" % ("Noise source", pv["noise_source"]))
        for im in pv["imports"]:
            L.append("  %-30s %s  sha256:%s  (%s)" % ("Import: " + im["what"], im["name"], im["sha256"], im["notes"]))
        if pv.get("coverage"):
            L.append("")
            L.append("[Component coverage - each chain component from exactly one source]")
            for c in pv["coverage"]:
                L.append("  %-34s %s%s" % (", ".join(c["components"]), c["source"],
                                           "  [%s]" % c["file"] if c["file"] else ""))
        L.append("")
        L.append("[Key inputs and data sources]")
        for label, path, val, unit, src in pv["key_inputs"]:
            L.append("  %-30s %-22s %-10s %s" % (label, val, unit, src))
    if res.get("assumptions"):
        L.append("")
        L.append("[Assumptions]")
        L.extend("  - " + a for a in res["assumptions"])
    db = res.get("dashboard")
    rg = res.get("range")
    if db and rg and rg["atm"]:
        L.append("")
        L.append("[DRI summary - %s%s]" % (rg["atm"][0]["label"], ", from " + rg["source"] if rg.get("source") else ""))
        for t in db["tasks"]:
            line = "  %-18s %5g %s  R = %-12s" % (t["name"], t["pot"] if "pot" in t else t["lp"],
                                                 "px" if "pot" in t else "lp", _fmt_range(t["R0"], rg["atm"][0]))
            if t.get("levels"):
                line += "  " + "  ".join("P%d %s" % (round(100 * l["p"]), _fmt_range(l["R0"], rg["atm"][0]))
                                         for l in t["levels"])
            if t.get("clutter", 1.0) != 1.0:
                line += "  (criterion %g lp x%.3g clutter)" % (t["lp_input"], t["clutter"])
            if "ttp" in t:
                tt = t["ttp"]
                line += "  TTP (V50 %g) %s" % (tt["v50"], " / ".join(_fmt_range(x, rg["atm"][0]) for x in [tt["R0"]] +
                                                                    [lv["R0"] for lv in tt.get("levels", [])]))
            if "geo" in t:
                line += "  geometric %s (%s)" % (_fmt_range(t["geo"]["R0"], rg["atm"][0]), t["geo"]["limit"])
            if "pix_h" in t:
                line += "  target pixels %.1f x %.1f, Nyquist-limited cycles %.1f%s" % (
                    t["pix_h"], t["pix_v"], t["cyc_nyq"], "  (sampling limited)" if t["sampling_limited"] else "")
            L.append(line)
            if "mtf_task" in t:
                L.append("  %-18s pixels %.1f x %.1f | cycles %.1f | MTF@task %.2f (%.3g cy/mrad) | CNR %.3g | "
                         "limiter: %s" % ("", t["pix_h"], t["pix_v"], t["cyc_nyq"], t["mtf_task"], t["f_task"],
                                          t["cnr_task"], t["limiter"]))
        L.append("  Model: %s" % db.get("model", ""))
        L.append("  Extensions (not TRM4): %s" % ("; ".join(db.get("extensions") or []) or "none"))
        if db.get("extensions") and any(t.get("levels") for t in db["tasks"]):
            L.append("  R is the TRM4 range (P50 criterion); P80 / P90 from the Johnson TTPF are an extension.")
        if any("ttp" in t for t in db["tasks"]):
            L.append("  TTP: targeting task performance metric (Vollmerhausen 2004) on the TRM4 thresholds, P50 / P80 / "
                     "P90; the V50 values are uncalibrated (extension).")
        if any("geo" in t for t in db["tasks"]):
            L.append("  Geometric: Nyquist / diffraction reference range without noise, contrast or atmosphere - not a "
                     "TRM4 range and not a bound (extension).")
        L.append("  Calibration status: %s" % db.get("calibration", ""))
        L.append("  Confidence / uncertainty method: %s" % ("nominal (input uncertainties not specified)" if not (
            analyses or {}).get("uncertainty") else "with stated input uncertainties (see below)"))
        L.append("  Aliasing risk (presampled MTF): %s" % db.get("aliasing", "-"))
        ctx = db.get("context")
        if ctx:
            L.append("")
            L.append("[DRI context - reported with every range]")
            for k, lab in (("task", "Task"), ("target", "Target geometry"), ("operating_point", "Operating point"),
                           ("scene", "Illumination / atmosphere"), ("mtf_source", "MTF source"),
                           ("observer", "Observer"), ("extensions", "Extensions (not TRM4)"),
                           ("uncertainty", "Uncertainty"), ("validation", "Validation status")):
                L.append("  %-30s %s" % (lab, ctx.get(k, "")))
            L.append("  " + ctx.get("statement", ""))
    ex = (db or {}).get("exposure")
    if ex:
        L.append("")
        L.append("[Exposure budget - t_int <= min(saturation, timing, motion, hardware); SNR >= required]")
        for n, t in ex["limits"]:
            L.append("  %-50s %s" % (n, "%.4g ms" % (t * 1e3) if np.isfinite(t) else "none"))
        L.append("  %-50s %.4g ms" % ("selected integration time", ex["t_sel"] * 1e3))
        L.append("  %-50s %s" % ("status", ("feasible" if ex["feasible"] else "INFEASIBLE") +
                                 ("; " + "; ".join(ex["violations"]) if ex["violations"] else "")))
    L.extend(format_analyses(analyses))
    val = res.get("validation")
    if val:
        L.append("")
        L.append("[Validation - measured vs predicted]")
        for it in val["items"]:
            if np.ndim(it["measured"]) == 0:
                L.append("  %-40s measured %.4g  predicted %.4g %s  (%+.1f %%)" % (
                    it["what"], it["measured"], it["predicted"], it["unit"], it["mean_dev_pct"]))
            else:
                L.append("  %-40s mean |dev| %.1f %s, max %.1f %s" % (
                    it["what"], it["mean_dev_pct"], "%-pts" if it.get("abs_points") else "%",
                    it["max_dev_pct"], "%-pts" if it.get("abs_points") else "%"))
        meta = val.get("meta") or {}
        L.append("  Calibration metadata: " + ", ".join("%s=%s" % (k, v) for k, v in meta.items() if str(v).strip()))
        if val.get("missing_meta"):
            L.append("  Missing metadata: " + ", ".join(val["missing_meta"]))
    sec = None
    for s, name, val, unit in res["info"]:
        if s != sec:
            L.append("")
            L.append("[%s]" % s)
            sec = s
        L.append("  %-58s %s %s" % (name, val, unit))
    L.append("")
    L.append("[Warnings]")
    L.extend("  - " + w for w in res["warnings"]) if res["warnings"] else L.append("  none")

    f = res["fom"]
    L.append("")
    L.append("[%s versus spatial frequency]  (%s)" % (f["name"], f["unit"]))
    L.append("  %12s %14s   %12s %14s" % ("r_h [1/mrad]", f["name"] + "_h", "r_v [1/mrad]", f["name"] + "_v"))
    for i in range(len(f["h"]["rp"])):
        L.append("  %12s %14s   %12s %14s" % (_num(f["h"]["rp"][i]), _num(f["h"]["val"][i]),
                                              _num(f["v"]["rp"][i]), _num(f["v"]["val"][i])))
    if "mcp" in res:
        L.append("")
        L.append("[MCP versus spatial frequency]")
        for z in "hv":
            for x, v in zip(res["mcp"][z]["rp"], res["mcp"][z]["val"]):
                L.append("  %s  %12s %12s" % (z, _num(x), _num(v)))
    rg = res.get("range")
    if rg:
        L.append("")
        L.append("[Range performance]")
        for a in rg["atm"]:
            for t in a["tasks"]:
                L.append("  %-32s %-18s %6g lp : R = %s km" % (a["label"], t["name"], t["lp"], _num(t["R0"])))
    ni = res.get("niirs")
    if ni and ni["atm"]:
        L.append("")
        L.append("[NIIRS (GIQE 5)]")
        for a in ni["atm"]:
            L.append("  %s" % a["label"])
            L.append("  %10s %8s %10s %8s %10s" % ("R [km]", "NIIRS", "GSD [m]", "RER", "DSNR"))
            for R, n, g, r, d in zip(a["R"], a["niirs"], a["gsd"], a["rer"], a["dsnr"]):
                L.append("  %10s %8s %10s %8s %10s" % (_num(R), _num(n), _num(g), _num(r), _num(d)))
    L.append("")
    L.append("[Project parameters]")
    shown = json.loads(json.dumps(project))

    def strip_files(d):                              # imported files: name only, not the raw contents
        for k, v in list(d.items()) if isinstance(d, dict) else []:
            if isinstance(v, dict) and set(v) == {"name", "text"}:
                if v.get("text"):
                    v["text"] = "<%d characters imported>" % len(v["text"])
            elif isinstance(v, dict):
                strip_files(v)
    strip_files(shown)
    if shown.get("scenarios"):                       # saved scenario configurations: names only
        shown["scenarios"] = ["<scenario '%s'>" % s.get("name", "") for s in shown["scenarios"]]
    L.append(json.dumps(shown, indent=2))
    return "\n".join(L)


def write_report(path, project, res, analyses=None):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(format_report(project, res, analyses))
