"""TRM4 application launcher.

    python run_trm4.py                         start the graphical user interface
    python run_trm4.py --list                  list the built-in templates
    python run_trm4.py --cli <template-number | project.json> [--out report.txt] [--save project.json]
                       [--limiting] [--uncertainty]
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
    ap.add_argument("--limiting", action="store_true", help="add the limiting-factor analysis to the report")
    ap.add_argument("--uncertainty", action="store_true",
                    help="add an uncertainty study (settings stored in the project, else typical defaults; RSS or "
                         "Monte Carlo as stored)")
    a = ap.parse_args()
    names = list(P.TEMPLATES)
    if a.list:
        for i, n in enumerate(names):
            print("%d  %s" % (i, n))
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
    if a.save:
        with open(a.save, "w", encoding="utf-8") as fh:
            json.dump(project, fh, indent=2)
    log = lambda msg, f=None: print("..", msg, file=sys.stderr)     # noqa: E731
    _, res = run_project(project, log)
    analyses = {}
    if a.limiting or a.uncertainty:
        from trm4 import analysis as AN
        if a.limiting:
            analyses["limiting"] = AN.limiting_factors(project, log)
        if a.uncertainty:
            analyses["uncertainty"] = AN.run_uncertainty(project, log)
    text = format_report(project, res, analyses)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("Report written to", a.out)
    else:
        print(text.split("[Project parameters]")[0])


if __name__ == "__main__":
    main()
