"""Engine 2.31 - corrections of the displayed range (reports/TRM_Hadmaa_Field_Effects_and_Upgrades_HE_2026-11-23.pdf):

U0  a resolution-limited range of the Visible / General categories varies continuously with the inputs (it took
    the range of a point of the 56-point range grid, 18 % steps);
U1  a measured camera NETD of an uncooled imager can be converted to the F-number of the scenario;
U2  line of sight: task ranges beyond the horizon over flat terrain are flagged (the ranges are not changed).
"""
import math
import unittest

import numpy as np

from _common import GENERAL, MWIR, SWIR, UNCOOLED, VIS, ranges, run_project, set_path, template
from trm4 import analysis as AN
from trm4 import extensions as X
from trm4.model import ModelError, TRM4Model

SUN = {"irradiance.preset": "Direct sunlight", "irradiance.E_peak": 1239.0, "detector.tint_mode": "wellfill"}


def swir_day(f_mm):
    """InGaAs camera in daylight (well-fill exposure): ample signal, every task limited by the resolution."""
    p = template(SWIR)
    for k, v in SUN.items():
        set_path(p, k, v)
    p["optics"]["f_mm"] = p["optics"]["f_v_mm"] = float(f_mm)
    for i in (1, 2):
        p["atmosphere"]["atm"][i]["on"] = False
    return ranges(run_project(p)[1])


class ResolutionLimitedRange(unittest.TestCase):
    """U0."""

    def test_range_follows_the_focal_length(self):
        f = [140.0, 145.0, 150.0, 155.0, 160.0, 165.0]
        rid = [swir_day(x)["Identification"] for x in f]
        grid = TRM4Model(template(SWIR))._range_grid(56)
        for a, b, fa, fb in zip(rid, rid[1:], f, f[1:]):
            self.assertGreater(b, a)                                    # no plateau (was 2.970 km from 140 to 160 mm)
            # sampling-limited: the range grows like the focal length, far below the 18 % grid step
            self.assertAlmostEqual(b / a, fb / fa, delta=0.02)
        for r in rid:
            self.assertGreater(np.min(np.abs(grid / r - 1.0)), 1e-4)     # not a grid point

    def test_general_template_identification(self):
        # the only template range that was a grid point (3.511 km)
        r = ranges(run_project(template(GENERAL))[1])
        self.assertAlmostEqual(r["Identification"], 3.987, delta=0.02)
        self.assertLess(r["Identification"], r["Recognition"])

    def test_signal_limited_range_unchanged(self):
        # a well-sampled camera limited by the signal does not reach the resolution limit: same result as before
        r = ranges(run_project(template(VIS))[1])
        self.assertAlmostEqual(r["Detection"], 14.732, delta=0.01)
        self.assertAlmostEqual(r["Identification"], 5.003, delta=0.01)


class CameraNetdToScenarioOptics(unittest.TestCase):
    """U1."""

    def run_unc(self, **over):
        m, res = run_project(template(UNCOOLED, **over))
        return m, ranges(res)

    def test_same_f_number_changes_nothing(self):
        m0, r0 = self.run_unc()
        m1, r1 = self.run_unc(detector__noise_mode="device_scaled", detector__netd_F=1.0)
        self.assertAlmostEqual(m1.netd, m0.netd, delta=1e-6)
        for k in r0:
            self.assertAlmostEqual(r1[k], r0[k], delta=1e-3 * r0[k])

    def test_slower_lens_raises_the_netd_like_f_squared(self):
        m0, r0 = self.run_unc()
        held, r_held = self.run_unc(optics__D_mm=35.7)                                   # F/1.4, NETD held
        conv, r_conv = self.run_unc(optics__D_mm=35.7, detector__noise_mode="device_scaled", detector__netd_F=1.0)
        det, r_det = self.run_unc(optics__D_mm=35.7, detector__noise_mode="detector", detector__meas_F=1.0)
        self.assertAlmostEqual(held.netd, m0.netd, places=12)
        self.assertAlmostEqual(conv.netd / m0.netd, (conv.F_eff / 1.0) ** 2, delta=1e-6)
        self.assertAlmostEqual(conv.netd, det.netd, delta=1e-9)             # the detector-level route, Eq. (3.142)
        for k in r0:
            self.assertLess(r_conv[k], r_held[k])                           # the lens change now costs sensitivity
            self.assertAlmostEqual(r_conv[k], r_det[k], delta=1e-6)
        self.assertTrue(any("converted to the optics" in a for a in conv.assumptions))
        self.assertFalse(any("measured at F/" in w for w in conv.warnings))

    def test_needs_the_test_f_number(self):
        with self.assertRaises(ModelError):
            run_project(template(UNCOOLED, detector__noise_mode="device_scaled"))

    def test_analysis_notes_follow_the_mode(self):
        held = template(UNCOOLED)
        conv = template(UNCOOLED, detector__noise_mode="device_scaled", detector__netd_F=1.0)
        self.assertTrue(any("held constant" in n for n in AN.apply_policy(held, "optics.D_mm", 40.0)))
        notes = AN.apply_policy(conv, "optics.D_mm", 40.0)
        self.assertEqual(notes, [AN._NETD_F_NOTE])
        # the transmission of the test lens is unknown: a transmission change is still not converted
        self.assertTrue(any("held constant" in n for n in AN.apply_policy(conv, "optics.tau_opt", 0.7)))

    def test_cooled_measured_netd_is_not_converted(self):
        m, _ = run_project(template(MWIR, detector__noise_mode="measured", detector__netd_mK=25.0, detector__netd_F=2.0))
        self.assertAlmostEqual(m.netd, 0.025)
        self.assertTrue(any("F/2.00" in w for w in m.warnings))


class Horizon(unittest.TestCase):
    """U2."""

    def test_horizon_distance(self):
        self.assertAlmostEqual(X.horizon_km(1.8, 0.0, refraction=False), 3.57 * math.sqrt(1.8), places=9)
        self.assertAlmostEqual(X.horizon_km(2.0, 2.3), 3.86 * (math.sqrt(2.0) + math.sqrt(2.3)), places=9)
        self.assertEqual(X.horizon_km(0.0, 0.0), 0.0)
        self.assertGreater(X.horizon_km(10.0, 2.0), X.horizon_km(10.0, 2.0, refraction=False))

    def test_range_beyond_the_horizon_is_flagged_not_changed(self):
        m, res = run_project(template(MWIR))                       # imager and target 1 m above flat ground
        r = ranges(res)
        self.assertAlmostEqual(m.horizon["refracted_km"], 2 * 3.86, places=6)
        self.assertGreater(r["Detection"], m.horizon["refracted_km"])
        warn = [w for w in m.warnings if w.startswith("Line of sight")]
        self.assertEqual(len(warn), 1)
        self.assertIn("Detection", warn[0])
        tasks = {t["name"]: t for t in res["range"]["atm"][0]["tasks"]}
        self.assertTrue(tasks["Detection"]["horizon"]["beyond"])
        self.assertFalse(tasks["Identification"]["horizon"]["beyond"])
        m2, res2 = run_project(template(MWIR, target__altitude_m=20.0))        # imager on a 20 m mast
        self.assertFalse(any(w.startswith("Line of sight") for w in m2.warnings))
        self.assertAlmostEqual(m2.horizon["h_imager_m"], 21.0, places=6)
        # the check never changes a range (the mast changes the slant geometry by < 0.1 %)
        self.assertAlmostEqual(ranges(res2)["Detection"], r["Detection"], delta=1e-3 * r["Detection"])
        self.assertTrue(any("Horizon over flat terrain" in row[1] for row in res2["info"]))

    def test_short_ranges_and_lab_mode_are_silent(self):
        m, _ = run_project(template(UNCOOLED))                     # 5.2 km detection, horizon 7.7 km
        self.assertFalse(any(w.startswith("Line of sight") for w in m.warnings))
        m, _ = run_project(template(MWIR, mode__environment="lab"))
        self.assertIsNone(m.horizon)


if __name__ == "__main__":
    unittest.main()
