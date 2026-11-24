"""Engine 2.35 - the items of the upgrade report that were waiting for a readable source
(reports/TRM_Hadmaa_Field_Effects_and_Upgrades_HE_2026-11-23.pdf).

U5   random wavefront error of the optics: MTF x exp{-(2 pi sigma / lambda)^2 [1 - rho(s)]} (Harvey & Kotha 1995);
     the mid and high frequencies fall by the Strehl ratio (Marechal: 0.8 at lambda / 14).
U6   contrast threshold of the eye (Barten model of DICOM PS3.14 Annex A, checked here against Table B-1 of the
     standard) as a second limit next to the noise - Thermal category, PROVISIONAL.
U10  search in a limited time: P(t) = P_inf (1 - e^(-t / (N tau_FOV))) (Friedman, Mark & Skirlo 2019).

All of it is off by default: the template ranges of tests/reference do not change.
"""
import math
import unittest

import numpy as np

from _common import LWIR, MWIR, VIS, ranges, run_project, template
from trm4 import extensions as X
from trm4.model import ModelError, TRM4Model

# DICOM PS3.14 Table B-1: JND index -> luminance [cd/m2].  One JND step is the peak-to-peak threshold modulation of
# the standard target (4 cycles/degree, 2 x 2 degrees): L(j+1) - L(j) = 2 m_t L.
DICOM_B1 = ((1, 0.0500, 0.0547), (100, 1.8508, 1.8868), (300, 23.3990, 23.6179), (500, 119.1326, 120.0109),
            (700, 480.5052, 483.7400), (1000, 3439.2210, 3461.6330))


class BartenModel(unittest.TestCase):
    def test_reproduces_the_dicom_table(self):
        for j, lo, hi in DICOM_B1:
            mean = 0.5 * (lo + hi)
            table = (hi - lo) / (2.0 * mean)
            model = 1.0 / X.barten_sensitivity(4.0, mean, 2.0)
            self.assertAlmostEqual(model / table, 1.0, delta=0.06, msg="JND %d: %.5f vs %.5f" % (j, model, table))

    def test_brighter_display_is_more_sensitive(self):
        s = [X.barten_sensitivity(4.0, L, 2.0) for L in (0.1, 1.0, 10.0, 100.0)]
        self.assertEqual(s, sorted(s))


class ContrastThreshold(unittest.TestCase):
    def run_with(self, name=LWIR, **over):
        return run_project(template(name, display__contrast_limit=True, **over))

    def test_off_by_default(self):
        m, _res = run_project(template(LWIR))
        self.assertIsNone(m.contrast)

    def test_never_lengthens_a_range_and_grows_with_the_span(self):
        base = ranges(run_project(template(LWIR))[1])
        last = base
        for span in (0.5, 5.0, 50.0):
            r = ranges(self.run_with(dsp__tone_span_K=span)[1])
            for task in base:
                self.assertLessEqual(r[task], last[task] + 1e-9, "%s at span %g K" % (task, span))
            last = r
        self.assertLess(last["Detection"], 0.6 * base["Detection"])

    def test_a_very_narrow_span_removes_the_limit(self):
        base = ranges(run_project(template(LWIR))[1])
        r = ranges(self.run_with(dsp__tone_span_K=1e-4)[1])
        for task in base:
            self.assertAlmostEqual(r[task], base[task], delta=0.002 * base[task])

    def test_threshold_is_span_over_sensitivity(self):
        m, _res = self.run_with(dsp__tone_span_K=10.0)
        u = 1.0 / m.m_sys * X.MRAD_PER_DEG
        self.assertGreater(u, m.contrast["u_peak"])
        want = 10.0 / X.barten_sensitivity(u, m.contrast["L_eye"], 3.5 / u)
        self.assertAlmostEqual(m.contrast_floor(1.0), want, delta=1e-9 * want)

    def test_low_frequencies_keep_the_best_sensitivity(self):
        m, _res = self.run_with()
        low = [m.contrast_floor(r) for r in (1e-4, 1e-3, 1e-2)]
        self.assertAlmostEqual(low[0], low[1], delta=1e-12)
        self.assertLessEqual(low[0], m.contrast_floor(1.0))

    def test_ambient_light_now_shortens_the_range(self):
        dark = ranges(self.run_with()[1])
        m, res = self.run_with(display__ambient_lux=5000.0)
        lit = ranges(res)
        self.assertLess(m.contrast["factor"], 1.0)
        for task in dark:
            self.assertLess(lit[task], dark[task])
        # without the option the ambient light stays a diagnostic
        base = ranges(run_project(template(LWIR))[1])
        only_light = ranges(run_project(template(LWIR, display__ambient_lux=5000.0))[1])
        self.assertEqual(base, only_light)

    def test_not_applied_outside_thermal_or_to_an_algorithm(self):
        base = ranges(run_project(template(VIS))[1])
        m, res = self.run_with(VIS)
        self.assertIsNone(m.contrast)
        self.assertEqual(ranges(res), base)
        self.assertTrue(any("not applied outside the Thermal category" in a for a in res["assumptions"]))
        m, _res = self.run_with(display__observer="algorithm")
        self.assertIsNone(m.contrast)

    def test_reported(self):
        _m, res = self.run_with()
        self.assertTrue(any("PROVISIONAL" in a and "Barten" in a for a in res["assumptions"]))
        self.assertTrue(any(row[1].startswith("Contrast threshold of the eye") for row in res["info"]))

    def test_span_must_be_positive(self):
        with self.assertRaises(ModelError):
            self.run_with(dsp__tone_span_K=0.0)


class WavefrontError(unittest.TestCase):
    def test_transfer_function(self):
        sigma, lam, corr = 0.7, 10.0, 10.0
        self.assertAlmostEqual(float(X.wfe_transfer(0.0, sigma, lam, corr)), 1.0)
        plateau = float(X.wfe_transfer(100.0, sigma, lam, corr))
        self.assertAlmostEqual(plateau, X.strehl(sigma, lam), places=12)
        s = np.linspace(0.0, 40.0, 50)
        h = X.wfe_transfer(s, sigma, lam, corr)
        self.assertTrue(np.all(np.diff(h) <= 1e-15))

    def test_marechal(self):
        self.assertAlmostEqual(X.strehl(1.0 / 14.0, 1.0), 0.8, delta=0.02)
        self.assertAlmostEqual(X.strehl(0.0, 1.0), 1.0)

    def test_zero_is_unchanged(self):
        m, res = run_project(template(LWIR, optics__wfe_rms_um=0.0))
        self.assertIsNone(m.wfe)
        self.assertEqual(ranges(res), ranges(run_project(template(LWIR))[1]))

    def test_mtf_falls_by_the_strehl_ratio(self):
        a = TRM4Model(template(LWIR))
        a.run()
        b = TRM4Model(template(LWIR, optics__wfe_rms_um=0.7))
        b.run()
        r = np.array([0.5, 0.7]) * a.opt_tab["h"][0][-1] if a.opt_tab["h"][0][-1] < 50 else np.array([2.0, 3.0])
        ratio = np.interp(r, *b.opt_tab["h"]) / np.interp(r, *a.opt_tab["h"])
        for x in ratio:
            self.assertAlmostEqual(x, b.wfe["strehl"], delta=0.03)
        self.assertAlmostEqual(b.wfe["waves"], 0.7 / b.wfe["lam_um"])
        # near zero frequency nothing is lost
        lo = np.interp(1e-3, *b.opt_tab["h"]) / np.interp(1e-3, *a.opt_tab["h"])
        self.assertAlmostEqual(lo, 1.0, delta=0.01)

    def test_ranges_fall_with_the_error(self):
        last = ranges(run_project(template(LWIR))[1])
        for w in (0.35, 0.7, 1.4):
            _m, res = run_project(template(LWIR, optics__wfe_rms_um=w))
            r = ranges(res)
            for task in r:
                self.assertLess(r[task], last[task])
            last = r
        self.assertTrue(any("rough guide" in a for a in res["assumptions"]))
        self.assertTrue(any(row[1].startswith("Wavefront error rms") for row in res["info"]))

    def test_negative_is_refused(self):
        with self.assertRaises(ModelError):
            run_project(template(LWIR, optics__wfe_rms_um=-0.1))


class Search(unittest.TestCase):
    def search(self, name=MWIR, **over):
        over = {"target__" + k: v for k, v in over.items()}
        _m, res = run_project(template(name, target__search=True, **over))
        return res, res["range"]["atm"][0]["tasks"]

    def test_time_factor(self):
        self.assertAlmostEqual(X.search_time_factor(3.0, 3.0, 1), 1.0 - math.exp(-1.0))
        # a field of regard of N fields of view needs N times the time (random search)
        self.assertAlmostEqual(X.search_time_factor(30.0, 3.0, 10), X.search_time_factor(3.0, 3.0, 1))
        with self.assertRaises(ValueError):
            X.search_time_factor(10.0, 0.0, 1)

    def test_off_by_default_and_leaves_the_ranges(self):
        _m, base = run_project(template(MWIR))
        self.assertNotIn("search", base["range"]["atm"][0]["tasks"][0])
        res, _tasks = self.search(search_time_s=10.0, search_tau_s=3.0)
        self.assertEqual(ranges(res), ranges(base))

    def test_first_task_only_and_shorter_than_the_static_range(self):
        res, tasks = self.search(search_time_s=10.0, search_tau_s=3.0)
        s = tasks[0]["search"]
        self.assertNotIn("search", tasks[1])
        self.assertAlmostEqual(s["n_fov"], 1.0)
        self.assertAlmostEqual(s["time_factor"], 1.0 - math.exp(-10.0 / 3.0))
        self.assertAlmostEqual(s["p_inf"], 0.5 / s["time_factor"])
        self.assertGreater(s["ratio"], 1.0)
        self.assertLess(s["R0"], ranges(res)["Detection"])
        self.assertTrue(any(row[0] == "Search (extension)" for row in res["info"]))
        self.assertTrue(any("Friedman" in a for a in res["assumptions"]))

    def test_more_time_and_a_smaller_area_give_more_range(self):
        kw = dict(search_tau_s=3.0, search_for_h_deg=30.0, search_for_v_deg=10.0)
        r = [self.search(search_time_s=t, **kw)[1][0]["search"] for t in (150.0, 300.0, 3000.0)]
        self.assertGreater(r[0]["n_fov"], 5.0)
        self.assertLess(r[0]["R0"], r[1]["R0"])
        self.assertLess(r[1]["R0"], r[2]["R0"])
        small = self.search(search_time_s=150.0, search_tau_s=3.0, search_for_h_deg=10.0,
                            search_for_v_deg=10.0)[1][0]["search"]
        self.assertGreater(small["R0"], r[0]["R0"])

    def test_field_of_regard_counts_fields_of_view(self):
        m = TRM4Model(template(MWIR))
        m.run()
        fov_h = math.degrees(m.fov["h"] * 1e-3)
        fov_v = math.degrees(m.fov["v"] * 1e-3)
        s = self.search(search_time_s=100.0, search_tau_s=3.0, search_for_h_deg=4 * fov_h,
                        search_for_v_deg=2 * fov_v)[1][0]["search"]
        self.assertAlmostEqual(s["n_fov"], 8.0, places=6)
        # an area smaller than the field of view is one field of view
        s = self.search(search_time_s=100.0, search_tau_s=3.0, search_for_h_deg=0.1 * fov_h)[1][0]["search"]
        self.assertAlmostEqual(s["n_fov"], 1.0)

    def test_too_little_time_is_reported_not_guessed(self):
        res, tasks = self.search(search_time_s=10.0, search_tau_s=3.0, search_for_h_deg=30.0, search_for_v_deg=10.0)
        s = tasks[0]["search"]
        self.assertGreater(s["p_inf"], 1.0)
        self.assertIsNone(s["ratio"])
        self.assertIsNone(s["R0"])
        self.assertTrue(any(row[0] == "Search (extension)" and row[2] == "not reached" for row in res["info"]))
        self.assertTrue(any("the time is too short" in a for a in res["assumptions"]))

    def test_acquisition_time_has_no_default(self):
        with self.assertRaises(ModelError):
            self.search(search_time_s=10.0)

    def test_visible_category(self):
        res, tasks = self.search(VIS, search_time_s=10.0, search_tau_s=3.0)
        self.assertLess(tasks[0]["search"]["R0"], ranges(res)["Detection"])


if __name__ == "__main__":
    unittest.main()
