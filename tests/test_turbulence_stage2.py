"""Turbulence stage 2 (engine 2.9): exposure-time turbulence MTF, near / far-field short-exposure factor, the
physical mitigation model (registration + lucky-region selection) and the ranges for the Cn2 statistics of TRM4
Table C.2.  The TRM4 defaults (short exposure, factor 1/2, no mitigation) are unchanged
(test_templates_reference)."""
import math
import unittest

import numpy as np

from _common import MWIR, VIS, ranges, template
from trm4 import analysis as AN
from trm4 import extensions as X
from trm4 import mtf as M
from trm4.model import ModelError, run_project


def run(**tb):
    dsp = tb.pop("_dsp", {})
    p = template(VIS)
    p["turbulence"].update(tb)
    p["dsp"].update(dsp)
    return run_project(p)


class TurbulenceMTF(unittest.TestCase):
    r = np.linspace(0.0, 40.0, 300)
    lam, r0, D_mm = 0.55, 0.03, 100.0

    def mtf(self, exposure="short", **kw):
        return M.mtf_turbulence(self.r, self.lam, self.r0, self.D_mm, exposure, **kw)

    def test_limits_of_the_general_form(self):
        np.testing.assert_allclose(self.mtf("long", tilt=1.0), self.mtf("short"))
        np.testing.assert_allclose(self.mtf("short", tilt=0.0), self.mtf("long"))
        mid = self.mtf(tilt=0.5)
        self.assertTrue(np.all(self.mtf("long") <= mid + 1e-15) and np.all(mid <= self.mtf("short") + 1e-15))

    def test_residual_tilt_is_hardie_gaussian(self):
        # Hardie et al. 2021, Eq. (34): H_SE G_a with G_a = exp[-3.44 (1 - a) (lambda f rho)^2 / (r0^5/3 D^1/3)]
        a, D = 0.3, self.D_mm * 1e-3
        sep = self.lam * self.r * 1e-3
        g = np.exp(-3.44 * (1 - a) * sep ** 2 / (self.r0 ** (5 / 3) * D ** (1 / 3)))
        np.testing.assert_allclose(self.mtf(se_factor=1.0, tilt=a), self.mtf(se_factor=1.0) * g, rtol=1e-9)

    def test_exposure_fraction_and_factor(self):
        self.assertEqual(X.tilt_removed_exposure(0.1, 0.0, 0.1), 1.0)
        self.assertAlmostEqual(X.tilt_removed_exposure(0.1, 2.0, 0.1), (0.1 / 0.3) ** (1 / 3))
        self.assertLess(X.tilt_removed_exposure(0.1, 10.0, 10.0), 0.1)
        f, q = X.se_factor_auto(0.03, 0.55, 5.0)
        self.assertAlmostEqual(q, 0.03 / math.sqrt(0.55e-6 * 5000.0))
        self.assertLess(q, 1.0)
        self.assertAlmostEqual(f, 0.5 + 0.5 * q)
        self.assertEqual(X.se_factor_auto(0.1, 0.55, 5.0)[0], 1.0)                 # D / sqrt(lambda L) = 1.9: near field

    def test_lucky_probability(self):
        self.assertAlmostEqual(X.LUCKY_DR0, 3.34, delta=0.01)
        self.assertAlmostEqual(1.0 / X.lucky_probability(7.0), 366.0, delta=10.0)    # Fried: about 1 in 350
        self.assertLess(X.lucky_probability(10.0), 2e-6)                              # about 1 in 10^6
        self.assertEqual(X.lucky_probability(3.0), 1.0)


class TurbulenceRanges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.short = ranges(run()[1])

    def test_regimes_are_ordered(self):
        long_ = ranges(run(exposure="long")[1])
        t2 = ranges(run(exposure="time", wind_ms=2.0)[1])
        t0 = ranges(run(exposure="time", wind_ms=0.0)[1])
        self.assertEqual(t0, self.short)                      # frozen turbulence = short exposure
        for t in self.short:
            self.assertLess(long_[t], t2[t])
            self.assertLess(t2[t], self.short[t])

    def test_short_exposure_factor(self):
        near = ranges(run(se_factor="near")[1])
        _m, res = run(se_factor="auto")
        auto = ranges(res)
        for t in self.short:
            self.assertLess(self.short[t], auto[t])
            self.assertLess(auto[t], near[t])
        self.assertAlmostEqual(near["Recognition"] / self.short["Recognition"], 1.08, delta=0.02)
        self.assertTrue(any("Fresnel ratio" in k for _g, k, _v, _u in res["info"]))

    def test_physical_mitigation(self):
        full = ranges(run(mit_model="physical", mit_alpha=1.0, mit_select=False)[1])
        self.assertEqual(full, self.short)                    # all tilt removed = short exposure
        half = ranges(run(mit_model="physical", mit_alpha=0.5, mit_select=False)[1])
        _m, res = run(mit_model="physical", mit_alpha=0.5, mit_select=True, _dsp={"frames_on": True, "n_frames": 10})
        lucky = ranges(res)
        for t in self.short:
            self.assertLess(half[t], self.short[t])
            self.assertGreaterEqual(lucky[t], half[t])
        self.assertGreater(lucky["Recognition"], half["Recognition"])
        self.assertTrue(any("physical" in e for e in res["dashboard"]["extensions"]))
        _m, res = run(mit_model="physical", mit_select=True)
        self.assertTrue(any("frame integration" in w for w in res["warnings"]))
        self.assertEqual(ranges(run(mitigation=2.0, mit_model="physical", mit_alpha=1.0, mit_select=False)[1]),
                         self.short)                          # the empirical gain does not apply in the physical model

    def test_validation(self):
        with self.assertRaises(ModelError):
            run(exposure="time", wind_ms=-1.0)
        with self.assertRaises(ModelError):
            run(mit_model="physical", mit_alpha=1.5)


class Cn2Statistics(unittest.TestCase):
    def test_arid_summer(self):
        with AN.Runner(2) as rn:
            s = AN.cn2_statistics(template(VIS), "Arid", "summer", overcast=True, runner=rn)
        rows = {(r["time"], r["pct"]): r["ranges"]["Recognition"] for r in s["rows"]}
        self.assertLess(rows[("Noon", "90 %")], rows[("Noon", "50 %")])          # stronger turbulence, shorter range
        self.assertLess(rows[("Noon", "50 %")], rows[("Noon overcast", "50 %")])
        self.assertLess(rows[("Noon", "50 %")], rows[("Night", "50 %")])
        self.assertLess(rows[("Night", "50 %")], rows[("Sunrise", "typical")])
        noon = next(r for r in s["rows"] if r["time"] == "Noon" and r["pct"] == "50 %")
        self.assertEqual(noon["cn2"], 9.2e-13)                                 # Table C.2, arid noon, 50 % summer
        self.assertEqual(s["base"], ranges(run_project(template(VIS))[1]))
        self.assertEqual(AN.to_csv_rows(s)[0][1], "cn2stats")

    def test_other_climates_and_thermal(self):
        with AN.Runner(2) as rn:
            s = AN.cn2_statistics(template(VIS), "Moderate", "winter", runner=rn)
        self.assertEqual(len(s["rows"]), 4)                                    # no sunrise row outside arid summer
        self.assertEqual(s["rows"][1]["cn2"], 2.2e-13)                          # moderate noon, 90 % winter
        with self.assertRaises(ModelError):
            AN.cn2_statistics(template(MWIR), "Arid", "summer")
        with self.assertRaises(ValueError):
            AN.cn2_statistics(template(VIS), "Tropical", "summer")


if __name__ == "__main__":
    unittest.main()
