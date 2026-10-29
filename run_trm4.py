"""TRM4 application launcher.

    python run_trm4.py                         start the graphical user interface
    python run_trm4.py --list                  list the built-in templates
    python run_trm4.py --cli <template-number | project.json> [--out report.txt] [--save project.json]
                       [--limiting] [--uncertainty] [--advisor] [--min-fov DEG] [--scenario scenario.json]
                       [--pdf-he report.pdf] [--ttp] [--quick] [--cn2-stats Arid:summer [--overcast]]
    python run_trm4.py --sfr edge.png [--out sfr.txt]   slanted-edge SFR of an edge image (ISO 12233 e-SFR)
    python -m unittest discover -s tests       run the regression / acceptance test suite
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trm4 import presets as P                       # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="TRM4.v3 range performance model")
    ap.add_argument("--cli", metavar="PROJECT", help="run without GUI: template number or project JSON file")
    ap.add_argument("--list", action="store_true", help="list built-in templates")
    ap.add_argument("--out", help="write text report to this file (CLI mode)")
    ap.add_argument("--save", help="save the (template) project as JSON (CLI mode)")
    ap.add_argument("--scenario", help="write the unit-labelled scenario record with coverage and trace (JSON)")
    ap.add_argument("--limiting", action="store_true", help="add the limiting-factor analysis to the report")
    ap.add_argument("--uncertainty", action="store_true",
                    help="add an uncertainty study (settings stored in the project, else typical defaults; RSS or "
                         "Monte Carlo as stored)")
    ap.add_argument("--advisor", action="store_true",
                    help="add the Range Improvement Advisor (bottleneck diagnosis, ranked what-if recommendations)")
    ap.add_argument("--min-fov", type=float, default=0.0, metavar="DEG",
                    help="advisor constraint: minimum horizontal FOV [deg] of a recommended configuration")
    ap.add_argument("--pdf-he", metavar="PDF",
                    help="write the Hebrew scholarly DRI report with the advisor recommendations (implies --advisor)")
    ap.add_argument("--ttp", action="store_true", help="also report TTP / V50 ranges (extension)")
    ap.add_argument("--quick", action="store_true",
                    help="geometric quick estimate only (Nyquist / diffraction, no model run, extension)")
    ap.add_argument("--cn2-stats", metavar="CLIMATE:SEASON",
                    help="add the ranges for the Cn2 statistics of TRM4 Table C.2, e.g. Arid:summer (climates Arid, "
                         "Moderate, Subarctic; seasons summer, winter)")
    ap.add_argument("--overcast", action="store_true", help="with --cn2-stats: add the overcast-noon rows")
    ap.add_argument("--sfr", metavar="IMAGE",
                    help="slanted-edge SFR of an edge region (.npy / .csv / .png / .tif); --out writes the curve "
                         "in cycles/pixel for the measured-MTF import")
    a = ap.parse_args()
    names = list(P.TEMPLATES)
    if a.list:
        for i, n in enumerate(names):
            print("%d  %s" % (i, n))
        return
    if a.sfr:
        from trm4 import labtools as LT
        res = LT.slanted_edge_sfr(LT.load_frame(a.sfr))
        text = LT.sfr_to_text(res, os.path.basename(a.sfr))
        for n in res["notes"]:
            print("note:", n, file=sys.stderr)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as fh:
                fh.write(text)
            print("SFR written to %s (MTF50 %s cycles/pixel)" % (a.out, "%.4f" % res["mtf50"] if res["mtf50"] else "-"))
        else:
            print(text)
        return
    if a.cli is None:
        from trm4.gui import main as gui_main
        gui_main()
        return
    from trm4.model import run_project
    from trm4.report import format_report
    if a.cli.isdigit():
        project = P.make_template(names[int(a.cli)])
    else:
        with open(a.cli, "r", encoding="utf-8") as fh:
            project = P.deep_merge(P.DEFAULT_PROJECT, json.load(fh))
    if a.ttp:
        project["target"]["ttp"] = True
    if a.save:
        with open(a.save, "w", encoding="utf-8") as fh:
            json.dump(project, fh, indent=2)
    if a.quick:
        from trm4.model import quick_estimate
        q = quick_estimate(project)
        print("Geometric quick estimate (extension, not a TRM4 range): IFOV %.4g mrad, aperture %.4g mm, "
              "mean wavelength %.3g um" % (q["ifov_mrad"], q["D_mm"], q["lambda_um"]))
        for t in q["tasks"]:
            print("  %-16s %5g lp  %s  (%s)" % (t["name"], t["lp"], "-" if t["R0"] is None else "%.3f km" % t["R0"],
                                              t["limit"]))
        return
    log = lambda msg, f=None: print("..", msg, file=sys.stderr)     # noqa: E731
    _, res = run_project(project, log)
    analyses = {}
    a.advisor = a.advisor or bool(a.pdf_he)
    if a.limiting or a.uncertainty or a.advisor or a.cn2_stats:
        from trm4 import analysis as AN
        if a.limiting:
            analyses["limiting"] = AN.limiting_factors(project, log)
        if a.cn2_stats:
            climate, _sep, season = a.cn2_stats.partition(":")
            with AN.Runner() as rn:
                analyses["cn2stats"] = AN.cn2_statistics(project, climate.strip().capitalize(),
                                                         (season or "summer").strip().lower(), a.overcast, log,
                                                         runner=rn)
        if a.uncertainty:
            analyses["uncertainty"] = AN.run_uncertainty(project, log)
        if a.advisor:
            from trm4 import advisor as ADV
            analyses["advisor"] = ADV.advise(project, log, min_fov_deg=a.min_fov)
    if a.scenario:
        from trm4 import scenario as SC
        SC.write(a.scenario, project, res)
        print("Scenario record written to", a.scenario)
    if a.pdf_he:
        from trm4 import report_he
        n = report_he.write_pdf(a.pdf_he, project, res, analyses["advisor"])
        print("Hebrew DRI report written to %s (%d pages)" % (a.pdf_he, n))
    text = format_report(project, res, analyses)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("Report written to", a.out)
    else:
        print(text.split("[Project parameters]")[0])


if __name__ == "__main__":
    main()
