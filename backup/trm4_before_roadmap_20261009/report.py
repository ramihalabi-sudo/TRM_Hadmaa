"""Plain-text report of TRM4 results (system data, ranges, figure-of-merit tables)."""
import json
import numpy as np


def _num(v):
    if v is None:
        return "-"
    if isinstance(v, float) and not np.isfinite(v):
        return "inf"
    return "%.5g" % v


def format_report(project, res):
    L = []
    L.append("TRM_HADMAAv1 performance report - %s" % project.get("name", ""))
    L.append("=" * 78)
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
    for key in ("zemax_mtf", "zemax_tau"):           # imported files: name only, not the raw contents
        ent = shown.get("optics", {}).get(key)
        if isinstance(ent, dict) and ent.get("text"):
            ent["text"] = "<%d characters imported>" % len(ent["text"])
    L.append(json.dumps(shown, indent=2))
    return "\n".join(L)


def write_report(path, project, res):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(format_report(project, res))
