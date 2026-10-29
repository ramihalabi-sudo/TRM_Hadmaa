"""TRM_HADMAA range metrics next to the TRM4 range (open items of the report's phase 3): the TTP / V50 metric, the
geometric reference range and quick mode, the aerosol MTF diagnostics and the Monte Carlo uncertainty in the
process pool.  All are extra outputs, so the TRM4 template ranges are unchanged (test_templates_reference)."""
import math
import unittest

import numpy as np

from _common import LWIR, MWIR, UNCOOLED, VIS, ranges, template
from trm4 import analysis as AN
from trm4 import extensions as X
from trm4.model import quick_estimate, run_project


def run(name, **kw):
    return run_project(template(name, **kw))


class TTP(unittest.TestCase):
    def test_ttpf(self):
        self.assertAlmostEqual(X.ttpf_ttp(1.0), 0.5, places=9)
        self.assertAlmostEqual(X.ttpf_ttp_ratio(0.5), 1.0, places=6)
        self.assertAlmostEqual(X.ttpf_ttp(X.ttpf_ttp_ratio(0.9)), 0.9, places=6)
        self.assertGreater(X.ttpf_ttp_ratio(0.9), X.ttpf_ttp_ratio(0.8))

    def test_integral(self):
        rp = np.linspace(0.0, 2.0, 201)
        self.assertAlmostEqual(X.ttp_integral(rp, np.ones_like(rp), 4.0), 4.0, places=9)     # sqrt(4 / 1) x 2
        self.assertEqual(X.ttp_integral(rp, np.full_like(rp, 5.0), 4.0), 0.0)                # nothing resolved
        thr = np.where(rp < 1.0, 1.0, np.inf)
        self.assertAlmostEqual(X.ttp_integral(rp, thr, 1.0 + 1e-9), 1.0, delta=0.02)

    def test_extra_output_only(self):
        for name in (LWIR, UNCOOLED, VIS):
            _m, off = run(name)
            _m, on = run(name, target__ttp=True)
            self.assertEqual(ranges(on), ranges(off), name)
            for t in on["range"]["atm"][0]["tasks"]:
                tt = t["ttp"]
                self.assertTrue(tt["R0"] is not None and 0 < tt["R0"] < 100, (name, t["name"]))
                r80, r90 = (lv["R0"] for lv in tt["levels"])
                self.assertLess(r90, r80)
                self.assertLess(r80, tt["R0"])
            self.assertNotIn("ttp", off["range"]["atm"][0]["tasks"][0])
            self.assertTrue(any("TTP" in e for e in on["dashboard"]["extensions"]))

    def test_v50_and_signal(self):
        _m, a = run(LWIR, target__ttp=True)
        _m, b = run(LWIR, target__ttp=True, target__tasks__2__v50=2 * 20.8)
        self.assertLess(b["range"]["atm"][0]["tasks"][2]["ttp"]["R0"], a["range"]["atm"][0]["tasks"][2]["ttp"]["R0"])
        _m, c = run(LWIR, target__ttp=True, target__dT_K=0.5)
        self.assertLess(c["range"]["atm"][0]["tasks"][0]["ttp"]["R0"], a["range"]["atm"][0]["tasks"][0]["ttp"]["R0"])

    def test_bad_v50_and_analyses_skip_it(self):
        from trm4.model import ModelError
        with self.assertRaises(ModelError):
            run(LWIR, target__ttp=True, target__tasks__0__v50=0.0)
        _m, fast = run_project(AN.fast(template(LWIR, target__ttp=True)))
        self.assertNotIn("ttp", fast["range"]["atm"][0]["tasks"][0])
        self.assertNotIn("geo", fast["range"]["atm"][0]["tasks"][0])


class Geometric(unittest.TestCase):
    def test_formula(self):
        R, lim = X.geometric_range(2.3, 1.0, 0.02, 10.0, 100.0)       # 2 px = 0.04 mrad < lambda / D = 0.1 mrad
        self.assertAlmostEqual(R, 2.3 / 0.1, places=9)
        self.assertIn("diffraction", lim)
        R, lim = X.geometric_range(2.3, 1.0, 0.1, 4.0, 100.0)
        self.assertAlmostEqual(R, 2.3 / 0.2, places=9)
        self.assertIn("sampling", lim)

    def test_matches_quick_mode_and_scales_with_criterion(self):
        _m, res = run(MWIR)
        q = quick_estimate(template(MWIR))
        for t, qt in zip(res["range"]["atm"][0]["tasks"], q["tasks"]):
            self.assertAlmostEqual(t["geo"]["R0"], qt["R0"], places=9)
        d, i = q["tasks"][0], q["tasks"][2]
        self.assertAlmostEqual(d["R0"] / i["R0"], i["lp"] / d["lp"], places=6)     # level line of sight
        self.assertTrue(any("geometric" in e for e in res["dashboard"]["extensions"]))
        _m, off = run(MWIR, target__geo_limit=False)
        self.assertNotIn("geo", off["range"]["atm"][0]["tasks"][0])
        self.assertEqual(ranges(off), ranges(res))

    def test_slant_path(self):
        q = quick_estimate(template(VIS, target__altitude_m=3000.0))
        for t in q["tasks"]:
            self.assertTrue(t["R0"] is None or t["R0"] > 3.0)


class Aerosol(unittest.TestCase):
    def test_mtf(self):
        xc = X.aerosol_cutoff(0.55, 10.0)
        self.assertAlmostEqual(xc, 10.0 / 0.55 / 1000.0)
        m = X.aerosol_mtf(np.array([0.0, 0.5 * xc, 2 * xc, 100.0]), 2.0, 0.5, xc)
        self.assertAlmostEqual(m[0], 1.0)
        self.assertAlmostEqual(m[2], math.exp(-1.0))
        self.assertAlmostEqual(m[3], math.exp(-1.0))
        self.assertTrue(m[0] > m[1] > m[2])

    def test_diagnostics_in_weather_mode(self):
        _m, res = run(LWIR, atmosphere__mode="weather")
        self.assertTrue(any(s.startswith("Aerosol MTF cutoff") for _g, s, _v, _u in res["info"]))
        _m, res = run(LWIR)
        self.assertFalse(any(s.startswith("Aerosol MTF cutoff") for _g, s, _v, _u in res["info"]))


class HufnagelValley(unittest.TestCase):
    def test_profile(self):
        h = np.linspace(0.0, 30000.0, 300001)
        I = np.trapezoid(X.cn2_hufnagel_valley(h), h)
        self.assertAlmostEqual(100 * 0.185 * (I / 0.5e-6 ** 2) ** (-0.6), 5.0, delta=0.15)   # HV 5/7: r0 = 5 cm
        self.assertAlmostEqual(float(X.cn2_hufnagel_valley(0.0)), 1.7e-14 + 2.7e-16, delta=1e-18)
        self.assertLess(float(X.cn2_hufnagel_valley(5000.0)), 1e-16)

    def test_slant_path_and_bands(self):
        p = template(VIS, target__altitude_m=3000.0, turbulence__on=True, turbulence__cn2_mode="hv",
                     turbulence__cn2=1.7e-14)
        _m, res = run_project(p)
        self.assertTrue(any("Hufnagel-Valley" in a for a in res["assumptions"]))
        _m, strong = run_project(AN._scale_turbulence(p, 10.0))
        self.assertLess(ranges(strong)["Identification"], ranges(res)["Identification"])
        from trm4.model import ModelError
        with self.assertRaises(ModelError):
            run_project(template(VIS, turbulence__on=True, turbulence__cn2_mode="hv", turbulence__hv_wind_ms=-1.0))


class ToneMapping(unittest.TestCase):
    def test_slope_and_noise(self):
        self.assertAlmostEqual(X.tone_slope(500.0, 1000.0, "linear", 8), 255.0 / 1000.0)
        self.assertAlmostEqual(X.tone_noise(500.0, 1000.0, "linear", 8), 1000.0 / 255.0 / math.sqrt(12.0))
        # a gamma curve expands the dark end and compresses the bright end
        self.assertGreater(X.tone_slope(10.0, 1000.0, "gamma", 8), X.tone_slope(900.0, 1000.0, "gamma", 8))
        self.assertGreater(X.tone_slope(10.0, 1000.0, "log", 8), X.tone_slope(10.0, 1000.0, "linear", 8))
        self.assertEqual(X.tone_noise(1200.0, 1000.0, "linear", 8), float("inf"))

    def test_ranges(self):
        base = ranges(run(LWIR)[1])
        narrow = ranges(run(LWIR, dsp__tone_mode="linear", dsp__tone_span_K=20.0)[1])
        wide = ranges(run(LWIR, dsp__tone_mode="linear", dsp__tone_span_K=100.0)[1])
        deep = ranges(run(LWIR, dsp__tone_mode="linear", dsp__tone_span_K=100.0, dsp__tone_bits=14)[1])
        self.assertLess(wide["Detection"], narrow["Detection"])
        self.assertLessEqual(narrow["Detection"], base["Detection"])
        self.assertAlmostEqual(deep["Detection"], base["Detection"], delta=0.01 * base["Detection"])
        _m, res = run(LWIR, dsp__tone_mode="linear")
        self.assertTrue(any("tone mapping" in e for e in res["dashboard"]["extensions"]))


class MonteCarloPool(unittest.TestCase):
    def test_pool_equals_serial(self):
        items = [("target.dT_K", "Target temperature difference", 20.0), ("target.W_m", "Target width", 10.0)]
        p = template(MWIR)
        a = AN.uncertainty(p, items, method="mc", mc_n=4, seed=4, runner=AN.Runner(1))
        b = AN.uncertainty(p, items, method="mc", mc_n=4, seed=4, runner=AN.Runner(2))
        for t in a["tasks"]:
            np.testing.assert_allclose(a["mc"][t]["samples"], b["mc"][t]["samples"], rtol=0, atol=0)
        self.assertEqual(a["mc"]["n_ok"], 4)


if __name__ == "__main__":
    unittest.main()
