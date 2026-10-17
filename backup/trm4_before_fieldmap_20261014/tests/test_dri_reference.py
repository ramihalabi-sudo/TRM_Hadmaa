"""DRI tasks: the standard templates reproduce the reference range calculations within tolerance."""
import json
import os
import unittest

import numpy as np

from _common import P, run_project

REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference", "template_ranges.json")
TOL = 0.005          # 0.5 % relative


class TemplateRanges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(REF, "r", encoding="utf-8") as fh:
            cls.ref = json.load(fh)

    def test_all_templates(self):
        for name in P.TEMPLATES:
            with self.subTest(template=name):
                _m, res = run_project(P.make_template(name))
                for a in res["range"]["atm"]:
                    for t in a["tasks"]:
                        want = self.ref[name]["ranges"][a["label"]][t["name"]]
                        got = t["R0"]
                        if want is None:
                            self.assertIsNone(got)
                            continue
                        got = 1e99 if not np.isfinite(got) else got
                        self.assertAlmostEqual(got, want, delta=TOL * want,
                                               msg="%s / %s / %s" % (name, a["label"], t["name"]))

    def test_task_criteria_unchanged(self):
        # standard DRI criteria are explicit inputs and are never altered by the application
        p = P.make_template("Thermal - LWIR cooled staring 640x512 (CMT)")
        self.assertEqual([t["lp"] for t in p["target"]["tasks"]], [1.0, 3.0, 6.0])
        self.assertEqual(P.THERMAL_TARGETS["STANAG 4347"]["tasks"], [1.0, 3.0, 6.0])


if __name__ == "__main__":
    unittest.main()
