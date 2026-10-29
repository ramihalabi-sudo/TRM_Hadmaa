"""Engine 2.11: the scintillation diagnostic (roadmap item 4 of Table 6 of reports/מחקר טורבולנציה - שלב ב.pdf, Sec. 4.8
and Appendix B): spherical-wave weak-turbulence log-amplitude and intensity variance along the Cn2 path, Churnside's
aperture averaging and the weak-turbulence flag.  The diagnostic is an extension that is off by default, leaves the
ranges unchanged and warns only for point / sub-pixel targets and active illumination."""
import math
import unittest

import numpy as np

from _common import GENERAL, LWIR, SWIR, VIS, P, ranges, template
from trm4 import extensions as X
from trm4.model import run_project


def run(name=VIS, **over):
    return run_project(template(name, **over))


def info(res):
    return {k: v for _g, k, v, _u in res["info"]}


def uniform(c):
    return lambda z: np.full_like(z, c)


def mentions(res):
    """Scintillation in the System data, assumptions, warnings or extensions of a run."""
    texts = list(info(res)) + res["assumptions"] + res["warnings"] + res["dashboard"]["extensions"]
    return [t for t in texts if "cintillation" in t]


WEAK = "  weak-turbulence regime (4 sigma_A^2 < 1)"
THROUGH = "  sigma_I^2 through the aperture (signal of a point target)"
RELEVANCE = "  relevance (point / sub-pixel target, active illumination)"
CN2_ROW = "  Cn2 averaged with the spherical-wave weight [z (L - z) / L]^5/6"


class Formulas(unittest.TestCase):
    def test_log_amplitude_and_intensity_variance(self):
        # lambda = 1 um, L = 5 km, Cn2 = 1e-14: k = 6.2832e6 1/m, k^(7/6) = 8.5351e7, L^(11/6) = 6.0457e6,
        # sigma_A^2 = 0.124 x 8.5351e7 x 6.0457e6 x 1e-14 = 0.6398, sigma_I^2 = exp(2.5594) - 1 = 11.93
        sa2 = X.scint_log_amplitude_variance(1.0, 5.0, 1e-14)
        self.assertAlmostEqual(sa2, 0.6398, delta=1e-4)
        self.assertAlmostEqual(X.scint_intensity_variance(sa2), 11.93, delta=0.01)
        # weak case, 1.55 um over 1 km: k^(7/6) L^(11/6) Cn2 = 0.16187, sigma_A^2 = 0.02007, sigma_I^2 = exp(0.0803) - 1
        # = 0.0836, close to the 0.5 k^(7/6) L^(11/6) Cn2 = 0.0809 of the report (Appendix B)
        sa2 = X.scint_log_amplitude_variance(1.55, 1.0, 1e-14)
        self.assertAlmostEqual(sa2, 0.02007, delta=1e-5)
        si2 = X.scint_intensity_variance(sa2)
        self.assertAlmostEqual(si2, 0.0836, delta=1e-4)
        self.assertAlmostEqual(si2, 0.5 * sa2 / 0.124, delta=0.04 * si2)
        # lambda^(-7/6) L^(11/6) Cn2
        one = X.scint_log_amplitude_variance(1.0, 5.0, 1e-14)
        self.assertAlmostEqual(X.scint_log_amplitude_variance(2.0, 5.0, 1e-14) / one, 2 ** (-7 / 6), places=12)
        self.assertAlmostEqual(X.scint_log_amplitude_variance(1.0, 10.0, 1e-14) / one, 2 ** (11 / 6), places=12)
        self.assertAlmostEqual(X.scint_log_amplitude_variance(1.0, 5.0, 3e-14) / one, 3.0, places=12)
        self.assertEqual(X.scint_intensity_variance(1000.0), float("inf"))       # no overflow far beyond weak

    def test_spherical_wave_path_weighting(self):
        L, c = 5.0, 1e-14
        self.assertAlmostEqual(X.scint_path_cn2(L, uniform(c)) / c, 1.0, places=12)    # uniform Cn2 unchanged
        # linear Cn2 from 0 to 2c: the symmetric weight [z (L - z) / L]^(5/6) gives exactly the mean c
        self.assertAlmostEqual(X.scint_path_cn2(L, lambda z: 2 * c * z / (L * 1e3)) / c, 1.0, places=9)
        # symmetric: the same turbulence next to the imager or next to the target gives the same scintillation
        # (unlike the spherical-wave r0, which weights the imager end, and theta0 the target end)
        half = L * 500.0
        near_imager = X.scint_path_cn2(L, lambda z: np.where(z < half, 2 * c, 0.0))
        near_target = X.scint_path_cn2(L, lambda z: np.where(z > half, 2 * c, 0.0))
        self.assertAlmostEqual(near_imager, near_target, delta=1e-3 * c)
        self.assertAlmostEqual(near_imager, c, delta=3e-3 * c)
        # the middle of the path weighs most: middle third 46.1 % of the weight, each end third 26.9 %
        third = L * 1e3 / 3.0
        mid = X.scint_path_cn2(L, lambda z: np.where((z > third) & (z < 2 * third), 3 * c, 0.0))
        end = X.scint_path_cn2(L, lambda z: np.where(z < third, 3 * c, 0.0))
        self.assertAlmostEqual(mid / c, 3 * 0.4613, delta=0.01)
        self.assertAlmostEqual(end / c, 3 * 0.2693, delta=0.01)
        self.assertEqual(X.scint_path_cn2(0.0, uniform(c)), 0.0)

    def test_aperture_averaging(self):
        # lambda = 1 um, L = 5 km, D = 0.1 m: k D^2 / 4L = pi, A = 1 / (1 + 0.214 pi^(7/6)) = 1 / (1 + 0.214 x 3.8020)
        # = 0.5514 (Churnside 1991, spherical wave)
        A, x = X.aperture_averaging_spherical(1.0, 5.0, 0.1)
        self.assertAlmostEqual(x, math.pi, places=9)
        self.assertAlmostEqual(A, 0.5514, delta=1e-4)
        # point receiver, D << sqrt(lambda L) = 7 cm: no averaging
        self.assertEqual(X.aperture_averaging_spherical(1.0, 5.0, 0.0), (1.0, 0.0))
        self.assertGreater(X.aperture_averaging_spherical(1.0, 5.0, 1e-4)[0], 0.99999)
        # large aperture, D >> sqrt(lambda L): A -> 1 / (0.214 x^(7/6)) ~ D^(-7/3)
        A1, x1 = X.aperture_averaging_spherical(1.0, 1.0, 10.0)
        A2, _x2 = X.aperture_averaging_spherical(1.0, 1.0, 20.0)
        self.assertAlmostEqual(A1 * 0.214 * x1 ** (7 / 6), 1.0, delta=1e-5)
        self.assertAlmostEqual(A2 / A1, 2 ** (-7 / 3), delta=1e-5)
        As = [X.aperture_averaging_spherical(0.55, 5.0, d)[0] for d in (0.01, 0.025, 0.05, 0.1, 0.3)]
        self.assertEqual(As, sorted(As, reverse=True))

    def test_weak_turbulence_flag(self):
        lam, L, D = 1.0, 5.0, 0.05
        c_crit = 0.25 / X.scint_log_amplitude_variance(lam, L, 1.0)       # 4 sigma_A^2 = 1: Rytov variance 1
        weak = X.scintillation(lam, L, uniform(0.99 * c_crit), D)
        strong = X.scintillation(lam, L, uniform(1.01 * c_crit), D)
        self.assertTrue(weak["weak"])
        self.assertFalse(strong["weak"])
        self.assertAlmostEqual(4 * weak["sigma_A2"], 0.99, places=9)
        self.assertAlmostEqual(weak["sigma_I2_0"], math.expm1(4 * weak["sigma_A2"]), places=12)
        self.assertAlmostEqual(weak["sigma_I2"], weak["A"] * weak["sigma_I2_0"], places=12)
        self.assertEqual(weak["A"], X.aperture_averaging_spherical(lam, L, D)[0])


class Diagnostic(unittest.TestCase):
    def test_off_by_default_and_ranges_unchanged(self):
        self.assertIs(P.DEFAULT_PROJECT["turbulence"]["scint"], False)
        _m, base = run()
        self.assertEqual(mentions(base), [])
        m, res = run(turbulence__scint=True)
        for a, b in zip(res["range"]["atm"], base["range"]["atm"]):                 # a diagnostic only
            self.assertEqual([(t["R0"], t.get("levels")) for t in a["tasks"]],
                             [(t["R0"], t.get("levels")) for t in b["tasks"]])
        rows = info(res)
        R_id = ranges(res)["Identification"]
        key = next(k for k in rows if k.startswith("Scintillation at the Identification range"))
        want = X.scint_log_amplitude_variance(m.lam_peak, R_id, 1e-14)                # fixed Cn2: the path average
        self.assertAlmostEqual(float(rows[key]), want, delta=0.005 * want)
        self.assertAlmostEqual(float(rows[CN2_ROW]), 1e-14, delta=1e-17)
        key = next(k for k in rows if k.startswith("  aperture averaging A for D = %.3g mm" % m.D_eff))
        self.assertAlmostEqual(float(rows[key]), X.aperture_averaging_spherical(m.lam_peak, R_id, m.D_eff / 1e3)[0],
                               delta=0.005)
        # Cn2 1e-14 over 5 km near the ground: 4 sigma_A^2 = 4.2 - strong scintillation, no sigma_I percentage
        self.assertTrue(rows[WEAK].startswith("no - 4 sigma_A^2 = "))
        self.assertIn("not valid", rows[THROUGH])
        # the 2.3 m target is extended: it averages the scintillation out - no warning
        self.assertTrue(rows[RELEVANCE].startswith("extended target"))
        self.assertFalse(any("cintillation" in w for w in res["warnings"]))
        self.assertTrue(any("scintillation diagnostic" in e for e in res["dashboard"]["extensions"]))
        a = [x for x in res["assumptions"] if x.startswith("Scintillation diagnostic")]
        self.assertEqual(len(a), 1)
        for word in ("0.124 k^(7/6) L^(11/6) Cn2", "exp(4 sigma_A^2) - 1", "Churnside 1991", "4 sigma_A^2 < 1",
                     "ranges are not changed"):
            self.assertIn(word, a[0])

    def test_weak_regime_rows(self):
        m, res = run(turbulence__scint=True, turbulence__cn2=1e-16)
        rows = info(res)
        self.assertEqual(rows[WEAK], "yes")
        s = X.scintillation(m.lam_peak, ranges(res)["Identification"], uniform(1e-16), m.D_eff / 1000.0)
        self.assertEqual(rows[THROUGH], "%.3g (sigma_I %.3g %%)" % (s["sigma_I2"], 100 * math.sqrt(s["sigma_I2"])))

    def test_point_target_warning(self):
        # reference range 60 km: the 2.3 m target subtends 0.038 mrad, less than one pixel (0.05 mrad)
        m, res = run(turbulence__scint=True, turbulence__cn2=1e-17, mode__ref_range_km=60.0)
        self.assertTrue(info(res)[RELEVANCE].startswith("point target"))
        w = [x for x in res["warnings"] if x.startswith("Scintillation (extension): point / sub-pixel target")]
        self.assertEqual(len(w), 1)
        self.assertIn("reference range 60 km: sigma_I = ", w[0])
        self.assertEqual([lab for lab, _s in m.scint["points"]], ["reference range 60 km"])
        self.assertTrue(all(s is not m.scint for _lab, s in m.scint["points"]))       # copies, no reference cycle
        # strong turbulence: flagged without a (meaningless) weak-turbulence percentage
        _m, strong = run(turbulence__scint=True, mode__ref_range_km=60.0)
        w = [x for x in strong["warnings"] if x.startswith("Scintillation (extension)")]
        self.assertEqual(len(w), 1)
        self.assertIn("strong scintillation", w[0])
        self.assertNotIn("sigma_I =", w[0])
        # a sub-pixel target at a task range (dashboard occupancy): General template with a 2.3 x 1 m target
        gen = dict(turbulence__on=True, turbulence__cn2=1e-15, target__H_m=1.0)
        _m, res = run(GENERAL, turbulence__scint=True, **gen)
        det = next(t for t in res["dashboard"]["tasks"] if t["name"] == "Detection")
        self.assertLess(det["occupancy"], 1.0)
        w = [x for x in res["warnings"] if x.startswith("Scintillation (extension): point / sub-pixel target")]
        self.assertEqual(len(w), 1)
        self.assertIn("Detection range %.3g km: sigma_I = " % det["R0"], w[0])
        self.assertTrue(any(k.startswith("Scintillation of the point target at the Detection range") for k in info(res)))
        self.assertEqual(ranges(res), ranges(run(GENERAL, **gen)[1]))

    def test_active_illumination_warning(self):
        # SWIR template with a 1.064 um laser illuminator (monochromatic source).  1.064 um lies on the sub-sampled
        # spectral grid of the MTF weighting; laser lines off that grid give no ranges at all (pre-existing).
        laser = dict(turbulence__on=True, turbulence__scint=True, irradiance__type="monochromatic",
                     irradiance__lambda_um=1.064, irradiance__E_mono=0.01)
        m, res = run(SWIR, turbulence__cn2=1e-15, **laser)
        w = [x for x in res["warnings"] if x.startswith("Scintillation (extension): active illumination")]
        self.assertEqual(len(w), 1)
        s = X.scintillation(1.064, ranges(res)["Identification"], uniform(1e-15), m.D_eff / 1000.0)
        self.assertIn("sigma_I = %.3g %% rms" % (100 * math.sqrt(s["sigma_I2_0"])), w[0])      # point value, 31 %
        rows = info(res)
        self.assertTrue(any(k.startswith("Scintillation at the Identification range") and "1.06 um" in k
                            for k in rows))
        self.assertIn("active illumination", rows[RELEVANCE])
        # sigma_I below 10 %: System data only, no warning
        _m, calm = run(SWIR, turbulence__cn2=1e-18, **laser)
        self.assertFalse(any("cintillation" in x for x in calm["warnings"]))
        # a broadband (passive) source is no active illumination
        _m, passive = run(SWIR, turbulence__on=True, turbulence__scint=True, turbulence__cn2=1e-15)
        self.assertFalse(any("cintillation" in x for x in passive["warnings"]))
        self.assertNotIn("active illumination", info(passive)[RELEVANCE])

    def test_needs_turbulence_and_r0_mode(self):
        _m, res = run(LWIR, turbulence__scint=True)                  # TRM4: no turbulence in the Thermal category
        self.assertEqual(mentions(res), [])
        # r0 mode: the uniform Cn2 that the r0 scaling implies (as the anisoplanatism diagnostic)
        _m, r0m = run(turbulence__scint=True, turbulence__cn2_mode="r0")
        tb = P.DEFAULT_PROJECT["turbulence"]
        c = X.cn2_uniform_from_r0(tb["r0_cm"] / 100.0, tb["r0_lambda_um"], tb["r0_L_km"])
        self.assertAlmostEqual(float(info(r0m)[CN2_ROW]), c, delta=0.005 * c)


if __name__ == "__main__":
    unittest.main()
