"""Sensitivity analyses - verification checklist of the sensitivity-analysis improvement plan (Sec. 6.2)."""
import math
import unittest

import numpy as np

from _common import UNCOOLED, LWIR, template
from trm4 import analysis as AN

TOY = {"a": 2.0, "b": 5.0}
LIN = lambda p: {"D": 3 * p["a"] + 2 * p["b"]}                       # noqa: E731
NONLIN = lambda p: {"D": p["a"] ** 3}                                 # noqa: E731


def item(path, pct, meaning="1sigma", dist="normal"):
    return {"path": path, "label": path, "pct": pct, "meaning": meaning, "dist": dist}


class Uncertainty(unittest.TestCase):
    def test_zero_perturbation_reproduces_nominal(self):
        u = AN.uncertainty(TOY, [item("a", 0)], evaluate=LIN)
        self.assertEqual(u["rows"][0]["low"], u["base"])
        self.assertEqual(u["rows"][0]["high"], u["base"])
        p = template(UNCOOLED)
        u = AN.uncertainty(p, [item("target.dT_K", 0.0)])
        base, _w = AN.model_ranges(p)
        self.assertEqual(u["rows"][0]["low"], base)                    # exactly the nominal DRI values
        self.assertEqual(u["rss"]["Detection"]["u"], 0.0)

    def test_linear_model_matches_rss_theory(self):
        u = AN.uncertainty(TOY, [item("a", 10), item("b", 20)], evaluate=LIN)
        self.assertAlmostEqual(u["rss"]["D"]["u"], math.hypot(3 * 0.2, 2 * 1.0), places=9)
        self.assertAlmostEqual(u["rss"]["D"]["U"], 2 * math.hypot(0.6, 2.0), places=9)
        # contributions sum to one; symmetric OAT response for a linear model
        self.assertAlmostEqual(sum(r["contrib"]["D"] for r in u["rows"]), 1.0, places=9)
        r = u["rows"][0]
        self.assertAlmostEqual(r["high"]["D"] - 16.0, 16.0 - r["low"]["D"], places=9)
        self.assertFalse(u["notes"])

    def test_correlation_terms(self):
        full = AN.uncertainty(TOY, [item("a", 10), item("b", 20)], evaluate=LIN, correlations=[("a", "b", 1.0)])
        self.assertAlmostEqual(full["rss"]["D"]["u"], 0.6 + 2.0, places=6)
        anti = AN.uncertainty(TOY, [item("a", 10), item("b", 20)], evaluate=LIN, correlations=[("a", "b", -1.0)])
        self.assertAlmostEqual(anti["rss"]["D"]["u"], 2.0 - 0.6, places=6)

    def test_meaning_and_distribution(self):
        self.assertAlmostEqual(AN.standard_uncertainty(30, "1sigma", "normal"), 0.30)
        self.assertAlmostEqual(AN.standard_uncertainty(30, "bound", "uniform"), 0.30 / math.sqrt(3))
        self.assertAlmostEqual(AN.standard_uncertainty(30, "bound", "triangular"), 0.30 / math.sqrt(6))
        self.assertAlmostEqual(AN.standard_uncertainty(30, "bound", "normal"), 0.10)
        self.assertAlmostEqual(AN.standard_uncertainty(19.6, "95", "normal"), 0.1, places=4)

    def test_nonlinear_asymmetry_is_flagged(self):
        u = AN.uncertainty({"a": 1.0}, [item("a", 50)], evaluate=NONLIN)
        r = u["rows"][0]
        self.assertGreater(r["high"]["D"] - 1.0, 1.0 - r["low"]["D"])  # +50 %: +2.375, -50 %: -0.875
        self.assertTrue(any("asymmetric" in n for n in u["notes"]))
        self.assertTrue(any("large perturbation" in n for n in u["notes"]))

    def test_monte_carlo_reproducible_and_consistent(self):
        args = dict(evaluate=LIN, method="mc", mc_n=3000, seed=7)
        u1 = AN.uncertainty(TOY, [item("a", 10), item("b", 20)], **args)
        u2 = AN.uncertainty(TOY, [item("a", 10), item("b", 20)], **args)
        self.assertEqual(u1["mc"]["D"]["p_lo"], u2["mc"]["D"]["p_lo"])     # fixed seed -> same summary
        self.assertAlmostEqual(u1["mc"]["D"]["std"], u1["rss"]["D"]["u"], delta=0.05 * u1["rss"]["D"]["u"])
        self.assertIn("Monte Carlo 95 % percentile interval", u1["label"])
        for dist in ("uniform", "triangular", "lognormal"):
            u = AN.uncertainty({"a": 2.0}, [item("a", 10, "1sigma", dist)], evaluate=lambda p: {"D": p["a"]},
                               method="mc", mc_n=4000, seed=1)
            self.assertAlmostEqual(u["mc"]["D"]["std"], 0.2, delta=0.02, msg=dist)

    def test_no_credible_interval_wording(self):
        u = AN.uncertainty(TOY, [item("a", 10)], evaluate=LIN)
        self.assertNotIn("credible", u["label"].lower())
        self.assertIn("combined standard uncertainty", u["label"])
        self.assertIn("U(k=2)", AN.interval(u, "D")[2])

    def test_settings_roundtrip_and_old_format(self):
        p = template(UNCOOLED)
        p["uncertainty"] = {"detector.netd_mK": 25.0}                   # format of version 2.0
        s = AN.uncertainty_settings(p)
        self.assertTrue(s["inputs"]["detector.netd_mK"]["on"])
        self.assertFalse(s["inputs"]["target.W_m"]["on"])
        self.assertEqual(AN.items_from_settings(s)[0]["pct"], 25.0)

    def test_model_uncertainty_direction(self):
        p = template(UNCOOLED)
        u = AN.uncertainty(p, [item("atmosphere.atm.0.sigma", 30, "bound", "uniform"), item("target.dT_K", 25)])
        ext = u["rows"][0]
        # more attenuation -> shorter range: the 'input increased' run must be the shorter one
        self.assertLess(ext["high"]["Detection"], ext["low"]["Detection"])
        self.assertLess(ext["c"]["Detection"], 0)
        self.assertGreater(u["rows"][1]["c"]["Detection"], 0)


class Sweeps(unittest.TestCase):
    def test_sweep_monotonic_in_focal_length(self):
        s = AN.sweep(template(LWIR), "optics.f_mm", [60.0, 100.0, 160.0])
        self.assertEqual(s["values"], [60.0, 100.0, 160.0])
        ident = s["ranges"]["Identification"]
        self.assertLess(ident[0], ident[1])
        self.assertLess(ident[1], ident[2])
        # the baseline value reproduces the nominal ranges exactly (table and chart agree)
        self.assertEqual(s["runs"][1]["ranges"], s["base"])
        self.assertEqual(s["runs"][1]["delta_pct"]["Detection"], 0.0)

    def test_convergence_repeated_points(self):
        s = AN.sweep(template(LWIR), "target.dT_K", [2.0, 2.0])
        self.assertEqual(s["runs"][0]["ranges"], s["runs"][1]["ranges"])

    def test_pitch_policy(self):
        p = template(LWIR)                                              # pitch 15 um, active 14 um, f 100 mm
        case = dict(p, detector=dict(p["detector"]), optics=dict(p["optics"]))
        notes = AN.apply_policy(case, "detector.pitch_h_um", 30.0, "ff2")
        self.assertEqual(case["detector"]["pitch_v_um"], 30.0)
        self.assertAlmostEqual(case["detector"]["a_h_um"], 28.0)
        self.assertTrue(any("held constant" in n for n in notes))
        case = dict(p, detector=dict(p["detector"]), optics=dict(p["optics"]))
        AN.apply_policy(case, "detector.pitch_h_um", 30.0, "keep_fov")
        self.assertAlmostEqual(case["optics"]["f_mm"], 200.0)
        case = dict(p, detector=dict(p["detector"]), optics=dict(p["optics"]))
        AN.apply_policy(case, "detector.pitch_h_um", 10.0, "keep_a")
        self.assertEqual(case["detector"]["a_h_um"], 10.0)              # limited to the pitch

    def test_focal_length_policy(self):
        p = template(LWIR)
        case = dict(p, optics=dict(p["optics"]))
        AN.apply_policy(case, "optics.f_mm", 200.0, "keep_F")
        self.assertAlmostEqual(case["optics"]["D_mm"], 100.0)
        case = dict(p, optics=dict(p["optics"]))
        AN.apply_policy(case, "optics.f_mm", 200.0, "keep_D")
        self.assertAlmostEqual(case["optics"]["D_mm"], 50.0)
        u = template(UNCOOLED)
        case = dict(u, optics=dict(u["optics"]))
        notes = AN.apply_policy(case, "optics.D_mm", 25.0)
        self.assertTrue(any("measured NETD" in n for n in notes))

    def test_invalid_points_rejected(self):
        s = AN.sweep(template(LWIR), "optics.D_mm", [50.0, 400.0])     # F/0.25 is impossible
        self.assertTrue(s["runs"][0]["ok"])
        self.assertFalse(s["runs"][1]["ok"])
        self.assertTrue(np.isnan(s["runs"][1]["delta_pct"]["Detection"]))
        self.assertTrue(any("impossible" in d for d in s["runs"][1]["diag"]))

    def test_log_grid(self):
        np.testing.assert_allclose(AN.grid(1, 100, 3, "log"), [1, 10, 100])
        with self.assertRaises(ValueError):
            AN.grid(0, 10, 3, "log")

    def test_2d_grid(self):
        s = AN.sweep2d(template(UNCOOLED), "target.dT_K", [1.0, 4.0], "atmosphere.atm.0.sigma", [0.1, 0.8])
        g = s["ranges"]["Detection"]
        self.assertEqual(g.shape, (2, 2))
        self.assertGreater(g[0, 1], g[0, 0])                            # more contrast -> longer range
        self.assertGreater(g[0, 0], g[1, 0])                            # more extinction -> shorter range
        with self.assertRaises(ValueError):
            AN.sweep2d(template(LWIR), "detector.pitch_h_um", [10, 15], "detector.a_h_um", [8, 9])


class LimitingAndScenarios(unittest.TestCase):
    def test_limiting_factors(self):
        lf = AN.limiting_factors(template(UNCOOLED))
        names = [r["factor"] for r in lf["rows"]]
        self.assertIn("Temporal noise halved", names)
        self.assertNotIn("Optics aberrations (diffraction-limited optics)", names)     # no aberration modelled
        for r in lf["rows"]:
            for g in r["gain_pct"].values():
                self.assertGreater(g, -1.0)        # removing a degradation must not shorten the range
        self.assertIn("sampling", lf["limit_type"]["Identification"])

    def test_scenarios(self):
        a = template(UNCOOLED)
        b = template(UNCOOLED, optics__f_mm=100.0)
        r = AN.compare_scenarios([("50 mm", a), ("100 mm", b)])
        self.assertEqual(r["rows"][0]["delta_pct"]["Identification"], 0.0)
        self.assertGreater(r["rows"][1]["delta_pct"]["Identification"], 0.0)
        rows = AN.to_csv_rows(r)
        self.assertTrue(any(row and row[0] == "100 mm" for row in rows))


if __name__ == "__main__":
    unittest.main()
