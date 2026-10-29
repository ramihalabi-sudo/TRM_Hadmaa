"""TRM_HADMAA extensions of the report's phase 3: probability levels, clutter, weather-derived extinction,
turbulence in the Thermal category and its mitigation, compression, the pixels-on-target algorithm criterion, scan
smear, the jitter assumption, range bands and the global sensitivity methods.  Every extension is off by default or
an extra output, so the TRM4 template ranges are unchanged (test_templates_reference)."""
import math
import unittest

import numpy as np

from _common import LWIR, MWIR, UNCOOLED, VIS, ranges, template
from trm4 import analysis as AN
from trm4 import extensions as X
from trm4.model import run_project


def run(name, **kw):
    return run_project(template(name, **kw))


class ProbabilityLevels(unittest.TestCase):
    def test_ttpf(self):
        self.assertAlmostEqual(X.ttpf_ratio(0.5), 1.0, places=6)
        self.assertAlmostEqual(X.ttpf_johnson(X.ttpf_ratio(0.9)), 0.9, places=6)
        self.assertAlmostEqual(X.ttpf_ratio(0.8), 1.45, delta=0.01)
        self.assertAlmostEqual(X.ttpf_ratio(0.9), 1.75, delta=0.01)          # report: N90 = 1.75 N50

    def test_levels_next_to_the_trm4_range(self):
        _m, res = run(LWIR)
        for t in res["range"]["atm"][0]["tasks"]:
            r80, r90 = (l["R0"] for l in t["levels"])
            self.assertLess(r90, r80)
            self.assertLess(r80, t["R0"])
        ident = res["range"]["atm"][0]["tasks"][2]
        self.assertAlmostEqual(ident["levels"][1]["R0"] / ident["R0"], 0.57, delta=0.03)   # resolution-limited
        self.assertTrue(any("P80 / P90" in e for e in res["dashboard"]["extensions"]))

    def test_switch_off_and_analyses_skip_them(self):
        _m, on = run(LWIR)
        _m, off = run(LWIR, target__prob_levels=False)
        self.assertEqual(ranges(on), ranges(off))
        self.assertNotIn("levels", off["range"]["atm"][0]["tasks"][0])
        _m, fast = run_project(AN.fast(template(LWIR)))
        self.assertNotIn("levels", fast["range"]["atm"][0]["tasks"][0])
        self.assertEqual(ranges(on), ranges(fast))


class Clutter(unittest.TestCase):
    def test_factor(self):
        self.assertEqual(X.clutter_factor("not_specified", 2.0), 1.0)
        self.assertEqual(X.clutter_factor("low", 2.0), 1.0)
        self.assertAlmostEqual(X.clutter_factor("high", 2.0), 6.1, delta=0.05)   # ACQUIRE-LC, dT_RSS = 2 K
        self.assertEqual(X.clutter_factor("medium", None), 2.0)                   # high-contrast limit

    def test_detection_only_and_only_when_switched_on(self):
        base = ranges(run(LWIR)[1])
        self.assertEqual(ranges(run(LWIR, target__clutter="medium")[1]), base)     # documentation only
        _m, res = run(LWIR, target__clutter="medium", target__clutter_model=True)
        r = ranges(res)
        self.assertLess(r["Detection"], 0.5 * base["Detection"])
        self.assertEqual((r["Recognition"], r["Identification"]), (base["Recognition"], base["Identification"]))

    def test_capped_at_recognition(self):
        _m, res = run(LWIR, target__clutter="high", target__clutter_model=True)
        t = res["range"]["atm"][0]["tasks"]
        self.assertEqual(t[0]["lp"], t[1]["lp"])                                   # 6.1 x 1 lp > 3 lp
        self.assertAlmostEqual(t[0]["R0"], t[1]["R0"], places=6)
        self.assertTrue(any("capped" in w for w in res["warnings"]))

    def test_not_moved_to_another_task(self):
        p = template(LWIR, target__clutter="high", target__clutter_model=True)
        p["target"]["tasks"][0]["on"] = False
        r = ranges(run_project(p)[1])
        self.assertEqual(r["Recognition"], ranges(run(LWIR)[1])["Recognition"])


class WeatherExtinction(unittest.TestCase):
    def test_kim_kruse(self):
        self.assertEqual(X.kim_q(60), 1.6)
        self.assertEqual(X.kim_q(20), 1.3)
        self.assertAlmostEqual(X.kim_q(3), 0.82)
        self.assertEqual(X.kim_q(0.3), 0.0)                                         # fog: wavelength-independent
        self.assertAlmostEqual(float(X.aerosol_extinction(0.55, 10.0)), 0.3912)

    def test_water_vapour(self):
        self.assertAlmostEqual(X.water_vapour_density(293.15, 100.0), 17.3, delta=0.1)
        self.assertEqual(float(X.continuum_extinction(4.0, 303.15, 80.0)), 0.0)    # MWIR: no continuum term
        humid = float(X.continuum_extinction(10.0, 303.15, 80.0))
        mild = float(X.continuum_extinction(10.0, 288.15, 70.0))
        self.assertAlmostEqual(humid, 0.47, delta=0.05)                            # tropical: poor IR weather
        self.assertAlmostEqual(mild, 0.092, delta=0.01)
        self.assertGreater(humid, 4 * mild)

    def test_lwir_ranges_follow_humidity(self):
        dry = template(LWIR, atmosphere__mode="weather")
        wet = template(LWIR, atmosphere__mode="weather")
        for p, rh in ((dry, 20.0), (wet, 95.0)):                    # warm air: the continuum grows with e^2
            p["atmosphere"]["atm"][0].update(rh_pct=rh, T_air_K=303.15)
        r_dry, r_wet = ranges(run_project(dry)[1]), ranges(run_project(wet)[1])
        self.assertGreater(r_dry["Detection"], 1.1 * r_wet["Detection"])
        _m, res = run(LWIR, atmosphere__mode="weather")
        self.assertTrue(any(s.startswith("Atm 1 from the weather") for _g, s, _v, _u in res["info"]))

    def test_mwir_is_flagged(self):
        _m, res = run(MWIR, atmosphere__mode="weather")
        self.assertTrue(any("not modelled" in w and "MWIR" in w for w in res["warnings"]))

    def test_uncertainty_inputs(self):
        paths = [p for p, _l, _pct in AN.applicable_inputs(template(LWIR, atmosphere__mode="weather"))]
        self.assertIn("atmosphere.atm.0.V_km", paths)
        self.assertIn("atmosphere.atm.0.rh_pct", paths)
        self.assertNotIn("atmosphere.atm.0.sigma", paths)
        self.assertEqual(AN._clip("atmosphere.atm.0.rh_pct", 130.0), 100.0)


class ThermalTurbulence(unittest.TestCase):
    def test_trm4_default_ignores_it(self):
        self.assertEqual(ranges(run(MWIR, turbulence__on=True, turbulence__cn2=1e-13)[1]), ranges(run(MWIR)[1]))

    def test_extension(self):
        base = ranges(run(MWIR)[1])
        weak = ranges(run(MWIR, turbulence__on=True, turbulence__thermal=True, turbulence__cn2=1e-17)[1])
        mid = ranges(run(MWIR, turbulence__on=True, turbulence__thermal=True, turbulence__cn2=1e-14)[1])
        _m, res = run(MWIR, turbulence__on=True, turbulence__thermal=True, turbulence__cn2=1e-13)
        strong = ranges(res)
        for t in base:
            self.assertAlmostEqual(weak[t] / base[t], 1.0, delta=0.01)
            self.assertLessEqual(strong[t], mid[t] * 1.001)
            self.assertLessEqual(mid[t], base[t] * 1.001)
        self.assertLess(strong["Detection"], 0.9 * base["Detection"])
        self.assertTrue(any(s.startswith("Fried parameter r0") for _g, s, _v, _u in res["info"]))


class MitigationAndCompression(unittest.TestCase):
    def test_mitigation(self):
        base = ranges(run(VIS)[1])
        self.assertEqual(ranges(run(VIS, turbulence__mitigation=1.0)[1]), base)
        r = ranges(run(VIS, turbulence__mitigation=3.0)[1])
        self.assertGreater(r["Recognition"], 1.1 * base["Recognition"])
        self.assertLess(r["Recognition"], 1.3 * base["Recognition"])               # reported +10 ... +25 %
        self.assertEqual(ranges(run(VIS, turbulence__on=False, turbulence__mitigation=3.0)[1]),
                         ranges(run(VIS, turbulence__on=False)[1]))

    def test_compression(self):
        self.assertAlmostEqual(float(X.mtf_compression(0.5, 0.5, 1.0)), math.exp(-2 * math.pi ** 2 / 16), places=6)
        base = ranges(run(LWIR)[1])
        self.assertEqual(ranges(run(LWIR, dsp__pl_compression="lossless", dsp__comp_blur_px=1.0)[1]), base)
        r = ranges(run(LWIR, dsp__pl_compression="lossy", dsp__comp_blur_px=0.7)[1])
        self.assertLess(r["Identification"], 0.95 * base["Identification"])


class AlgorithmObserver(unittest.TestCase):
    def test_pixels_on_target(self):
        m, res = run(LWIR, display__observer="algorithm", display__algo_criterion="pot", display__algo_cnr_min=1e-6)
        a = res["range"]["atm"][0]
        tg = m.p["target"]
        for i, t in enumerate(a["tasks"]):
            want = math.sqrt(tg["W_m"] * tg["H_m"] / (X.POT_DEFAULTS[i] * m.alpha_s["h"] * m.alpha_s["v"]))
            self.assertAlmostEqual(t["R0"], want, delta=0.01 * want)
            self.assertEqual(t["limit"], "pixels on target")
            self.assertNotIn("levels", t)                                           # no TTPF for pixel counts
        self.assertIn("pixels on target", res["dashboard"]["model"])

    def test_cnr_condition(self):
        loose = ranges(run(LWIR, display__observer="algorithm", display__algo_criterion="pot")[1])
        # zero-range pixel CNR of this template ~73; 60 is reached at ~1 km, before the 60-pixel limit (~2 km)
        _m, res = run(LWIR, display__observer="algorithm", display__algo_criterion="pot", display__algo_cnr_min=60.0)
        self.assertLess(ranges(res)["Detection"], loose["Detection"])
        self.assertEqual(res["range"]["atm"][0]["tasks"][0]["limit"], "pixel CNR")


class MotionChecks(unittest.TestCase):
    def test_scan_smear(self):
        m, res = run(UNCOOLED, stab__lin_on=True, stab__lin_h=174.5)                 # 10 deg/s
        sm = m.scan_smear_px()
        self.assertAlmostEqual(sm["h"], 174.5 * m.t_th / m.alpha_s["h"])
        self.assertGreater(sm["h"], 4.0)
        self.assertTrue(any("scan smear" in w for w in res["warnings"]))

    def test_zero_jitter_assumption(self):
        _m, res = run(MWIR)
        self.assertTrue(any(a.startswith("No line-of-sight jitter") for a in res["assumptions"]))
        _m, res = run(MWIR, stab__random_on=True, stab__rand_h_mrad=X.TYPICAL_JITTER_MRAD,
                      stab__rand_v_mrad=X.TYPICAL_JITTER_MRAD)
        self.assertFalse(any(a.startswith("No line-of-sight jitter") for a in res["assumptions"]))


class RangeBands(unittest.TestCase):
    def test_weather_and_turbulence(self):
        b = AN.range_bands(template(VIS))
        self.assertEqual(len(b["turb"]), 3)
        nominal = AN.model_ranges(template(VIS))[0]
        for t in b["tasks"]:
            self.assertAlmostEqual(b["base"][t], nominal[t], places=9)
            self.assertLessEqual(b["band"][t]["min"], b["base"][t])
            self.assertGreaterEqual(b["band"][t]["max"], b["base"][t])
            weak, nom, strong = (row[0] for row in b["grid"][t])
            self.assertGreaterEqual(weak, nom)
            self.assertGreaterEqual(nom, strong)
        self.assertEqual(AN.to_csv_rows(b)[3][0], "# method")

    def test_thermal_weather_only(self):
        b = AN.range_bands(template(MWIR))
        self.assertEqual(len(b["turb"]), 1)
        self.assertEqual(len(b["atms"]), 2)


class GlobalSensitivity(unittest.TestCase):
    def test_sobol_estimators(self):
        rng = np.random.default_rng(3)
        n, k = 4000, 3
        A, B = rng.random((n, k)), rng.random((n, k))
        f = lambda x: x[:, 0] + 2 * x[:, 1] + x[:, 0] * x[:, 2]
        exact_s1 = (0.1875 / 0.5486, 0.3333 / 0.5486, 0.0208 / 0.5486)
        exact_st = (1 - 0.3542 / 0.5486, 0.3333 / 0.5486, 1 - 0.5208 / 0.5486)
        for i in range(k):
            s1, st, _c1, _ct = AN._sobol_indices(f(A), f(B), f(np.where(np.arange(k) == i, B, A)), rng, n_boot=20)
            self.assertAlmostEqual(s1, exact_s1[i], delta=0.04)
            self.assertAlmostEqual(st, exact_st[i], delta=0.04)

    def test_morris(self):
        items = [("target.W_m", "Target width", 10.0), ("target.tasks.2.lp", "Identification criterion", 25.0),
                 ("target.dT_K", "Target temperature difference", 25.0)]
        g = AN.global_sensitivity(template(MWIR), items, "morris", r=3, runner=AN.Runner(1))
        self.assertLessEqual(g["n_runs"], g["n_planned"])
        row = {r["path"]: r for r in g["rows"]}
        crit = row["target.tasks.2.lp"]["mu_star"]
        self.assertEqual((crit["Detection"], crit["Recognition"]), (0.0, 0.0))   # acts on its own task only
        self.assertGreater(crit["Identification"], 0.0)
        self.assertGreater(row["target.dT_K"]["mu_star"]["Detection"], row["target.dT_K"]["mu_star"]["Identification"])
        self.assertEqual(AN.to_csv_rows(g)[3][0], "# method")


if __name__ == "__main__":
    unittest.main()
