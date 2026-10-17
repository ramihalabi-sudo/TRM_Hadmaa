"""Geometry and sampling: FOV / IFOV / Nyquist / target pixels reproduce independent calculations."""
import math
import unittest

from _common import LWIR, MWIR, VIS, template, setup_model, run_project
from trm4 import derived as DV


class Geometry(unittest.TestCase):
    def test_fov_ifov_nyquist(self):
        m = setup_model(template(LWIR))                 # f 100 mm, 640x512, pitch 15 um, active 14 um
        self.assertAlmostEqual(m.fov["h"], ((640 - 1) * 15 + 14) / 100.0, places=9)        # mrad
        self.assertAlmostEqual(m.fov["v"], ((512 - 1) * 15 + 14) / 100.0, places=9)
        self.assertAlmostEqual(m.das["h"], 14 / 100.0, places=12)                         # IFOV mrad
        self.assertAlmostEqual(m.alpha_s["h"], 15 / 100.0, places=12)
        self.assertAlmostEqual(m.r_N["h"], 1 / (2 * 0.15), places=9)                      # cycles/mrad

    def test_angle_unit_conversion(self):
        rows, _ = DV.compute(template(LWIR))
        fov = dict((r[1], r[2]) for r in rows)["Field of view h x v"]
        h = float(fov.split(" x ")[0])
        self.assertAlmostEqual(h, math.degrees(95.99e-3), places=3)

    def test_binning_updates_sampling(self):
        m = setup_model(template(LWIR, basic__bin_h=2, basic__bin_v=2))
        self.assertEqual(m.n_sam["h"], 320)
        self.assertAlmostEqual(m.alpha_s["h"], 0.30, places=12)
        self.assertAlmostEqual(m.r_N["h"], 1 / 0.6, places=9)
        self.assertAlmostEqual(m.a_eff["h"], 14 + 15, places=12)                           # a + (n-1) pitch

    def test_derived_matches_engine(self):
        for name in (LWIR, MWIR, VIS):
            p = template(name)
            m = setup_model(p)
            rows, warns = DV.compute(p)
            d = dict((r[1], r[2]) for r in rows)
            self.assertEqual(warns, [], name)
            nyq = float(d["Nyquist frequency h x v"].split(" x ")[0])
            self.assertAlmostEqual(nyq, m.r_N["h"], places=2)
            F = float(d["Effective F-number (f / D_eff)"])
            self.assertAlmostEqual(F, m.F_eff, places=3)

    def test_target_pixels(self):
        _m, res = run_project(template(LWIR))
        for t in res["dashboard"]["tasks"]:
            # flat 2.3 x 2.3 m target seen from the front at ground level
            self.assertAlmostEqual(t["pix_h"], 2.3 / (t["R0"] * 0.15), places=6)
            self.assertAlmostEqual(t["cyc_nyq"], 0.5 * math.sqrt(t["pix_h"] * t["pix_v"]), places=9)

    def test_measured_fov_conflict_warns(self):
        p = template(LWIR, basic__fov_mode="measured", basic__fov_h_deg=7.0, basic__fov_v_deg=4.4)
        _m, res = run_project(p)
        self.assertTrue(any("deviates" in w for w in res["warnings"]))
        _rows, warns = DV.compute(p)
        self.assertTrue(any("Measured h-FOV" in w for w in warns))

    def test_inconsistent_f_number_warns(self):
        _m, res = run_project(template(LWIR, optics__F_spec=2.8))       # f/D = 100/50 = 2
        self.assertTrue(any("inconsistent" in w for w in res["warnings"]))
        _rows, warns = DV.compute(template(LWIR, optics__F_spec=2.0))
        self.assertEqual(warns, [])

    def test_impossible_geometry_warns(self):
        _rows, warns = DV.compute(template(LWIR, optics__D_mm=400.0))   # F/0.25
        self.assertTrue(any("impossible" in w for w in warns))


if __name__ == "__main__":
    unittest.main()
