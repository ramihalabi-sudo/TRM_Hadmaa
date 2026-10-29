"""Engine 2.10: the remaining recommendations of the turbulence research, stage B (reports/): the anisoplanatism
diagnostic, the SLC / Greenwood / Brookner Cn2 altitude profiles, the h^-2/3 daytime option of the Cn2 statistics and
Cn2 from the weather (Sadot & Kopeika 1992).  Every item is an extension that is off by default, so the TRM4 template
ranges are unchanged (test_dri_reference).  The r0-from-video lab tool is in test_labtools."""
import math
import unittest

import numpy as np

from _common import VIS, ranges, template
from trm4 import analysis as AN
from trm4 import extensions as X
from trm4 import mtf as M
from trm4.model import ModelError, run_project


def run(**tb):
    p = template(VIS)
    p["turbulence"].update(tb)
    return run_project(p)


def info(res):
    return {k: v for _g, k, v, _u in res["info"]}


def uniform(c):
    return lambda z: np.full_like(z, c)


class Anisoplanatism(unittest.TestCase):
    def test_isoplanatic_angle_and_its_weighting(self):
        lam, L, cn2 = 0.55, 5.0, 1e-14
        th0, h_bar, r0_pw = X.isoplanatic_angle(lam, L, uniform(cn2))
        k2 = (2 * math.pi / (lam * 1e-6)) ** 2
        self.assertAlmostEqual(th0, (2.914 * k2 * cn2 * 3 / 8 * (L * 1e3) ** (8 / 3)) ** -0.6, delta=1e-4 * th0)
        self.assertAlmostEqual(th0, 0.314 * r0_pw / h_bar, delta=2e-3 * th0)        # Fried 1982
        self.assertAlmostEqual(h_bar / (L * 1e3), (3 / 8) ** 0.6, places=4)
        # z from the imager, weight z^5/3: the same turbulence near the target lowers theta0 more than near the imager
        half = L * 500.0
        near_target = lambda z: np.where(z > half, 2 * cn2, 0.0)                  # noqa: E731
        near_imager = lambda z: np.where(z < half, 2 * cn2, 0.0)                  # noqa: E731
        self.assertLess(X.isoplanatic_angle(lam, L, near_target)[0], th0)
        self.assertGreater(X.isoplanatic_angle(lam, L, near_imager)[0], 2 * th0)
        # ... the opposite of the spherical-wave r0 of TRM4 Eq. (4.82), which weights the imager end
        self.assertGreater(M.fried_parameter(lam, L, near_target, 801), M.fried_parameter(lam, L, near_imager, 801))

    def test_hardie_table_2(self):
        # Hardie et al. 2021, Tables 1 / 2: D = 0.2034 m, lambda = 0.525 um, L = 7 km, pixel angle 1.2906 urad
        px = 1.2906e-6
        for cn2, r0_t, theta0_t, tilt_t in ((0.1e-15, 0.1901, 6.6174, 0.9026), (1e-15, 0.0478, 1.6622, 2.8543),
                                            (2e-15, 0.0315, 1.0966, 4.0367)):
            r0 = M.fried_parameter(0.525, 7.0, uniform(cn2))
            self.assertAlmostEqual(r0, r0_t, delta=0.005 * r0_t)
            self.assertAlmostEqual(X.isoplanatic_angle(0.525, 7.0, uniform(cn2))[0] / px, theta0_t,
                                   delta=0.005 * theta0_t)
            self.assertAlmostEqual(X.tilt_rms(0.525, r0, 0.2034) / px, tilt_t, delta=0.005 * tilt_t)
        self.assertAlmostEqual(X.tilt_correlation_angle(0.06, 1.0), 60e-6)          # D / L (literature ~ 2 D / L)
        c = X.cn2_uniform_from_r0(0.0478, 0.525, 7.0)
        self.assertAlmostEqual(c, 1e-15, delta=0.01e-15)

    def test_diagnostic_rows_and_warning(self):
        _m, base = run()
        self.assertFalse(any("theta0" in k for k in info(base)))                    # off by default
        m, res = run(aniso=True)
        self.assertEqual(ranges(res), ranges(base))                                 # diagnostic only
        rows = info(res)
        th_t = float(rows["Tilt-correlation angle ~ D / L (anisoplanatism, extension)"])
        R_id = ranges(res)["Identification"]
        self.assertAlmostEqual(th_t, m.D_eff / R_id, delta=0.005 * th_t)            # mm / km = urad
        self.assertTrue(any(k.startswith("Isoplanatic angle theta0") for k in rows))
        self.assertEqual(rows["Target distorts within itself (anisoplanatism, extension)"], "no")
        self.assertFalse(any("Anisoplanatism" in w for w in res["warnings"]))        # tilt 0.28 IFOV < 0.5 IFOV
        self.assertTrue(any("anisoplanatism" in e for e in res["dashboard"]["extensions"]))
        self.assertTrue(any(a.startswith("Anisoplanatism diagnostic") for a in res["assumptions"]))
        # arid noon (Table C.2, 9.2e-13): the image tilt reaches 1.5 IFOV - the target distorts within itself
        _m, strong = run(aniso=True, cn2=9.2e-13)
        self.assertTrue(any("distorts within itself" in w and "Identification" in w for w in strong["warnings"]))
        self.assertTrue(info(strong)["Target distorts within itself (anisoplanatism, extension)"].startswith("yes"))
        # r0 mode: theta0 from the uniform Cn2 that the r0 scaling implies
        _m, r0m = run(aniso=True, cn2_mode="r0")
        self.assertTrue(any(k.startswith("Isoplanatic angle theta0") for k in info(r0m)))


class Cn2Profiles(unittest.TestCase):
    def test_formulas(self):
        self.assertEqual(float(X.cn2_slc(10.0)), 8.40e-15)
        self.assertAlmostEqual(float(X.cn2_slc(50.0)), 2.87e-12 / 50 ** 2, delta=1e-22)
        self.assertEqual(float(X.cn2_slc(500.0)), 2.5e-16)
        self.assertAlmostEqual(float(X.cn2_slc(3000.0)), 8.87e-7 / 3000 ** 3, delta=1e-24)
        self.assertAlmostEqual(float(X.cn2_slc(10000.0)), 2.0e-16 / 100, delta=1e-24)
        self.assertEqual(float(X.cn2_slc(10.0, day=True)), 1.70e-14)
        self.assertAlmostEqual(float(X.cn2_slc(100.0, day=True)), 3.13e-13 / 100, delta=1e-22)
        self.assertEqual(float(X.cn2_slc(500.0, day=True)), 1.30e-15)
        self.assertAlmostEqual(float(X.cn2_slc(2000.0, day=True)), 8.87e-7 / 2000 ** 3, delta=1e-24)
        for day, edges in ((False, (18.5, 110.0, 1500.0, 7200.0)), (True, (18.5, 240.0, 880.0, 7200.0))):
            for h in edges:                                                         # the pieces join within 6 %
                self.assertLess(abs(float(X.cn2_slc(h + 1e-6, day) / X.cn2_slc(h - 1e-6, day)) - 1.0), 0.06, (day, h))
        self.assertAlmostEqual(float(X.cn2_greenwood(0.0)), 2.2e-13 * 10 ** -1.3 + 4.3e-17, delta=1e-24)
        self.assertAlmostEqual(float(X.cn2_greenwood(1000.0, poor=True)),
                               (2.2e-12 * 1010 ** -1.3 + 7e-16) * math.exp(-0.5), delta=1e-24)
        self.assertAlmostEqual(float(X.cn2_brookner(64.0, 1e-13)), 1e-13 * 64 ** (-5 / 6) * math.exp(-0.2),
                               delta=1e-24)
        np.testing.assert_allclose(X.cn2_profile("greenwood_good", np.array([2.0, 20.0])),
                                   X.cn2_greenwood(np.array([2.0, 20.0])))
        with self.assertRaises(ValueError):
            X.cn2_profile("hv", 2.0)

    def test_ranges_follow_the_near_ground_cn2(self):
        # horizontal path at 1 m (Visible template): SLC day 1.7e-14 > fixed 1e-14 > SLC night 8.4e-15
        base = ranges(run()[1])
        _m, day = run(cn2_mode="slc_day")
        night = ranges(run(cn2_mode="slc_night")[1])
        for t in base:
            self.assertLess(ranges(day)[t], base[t])
            self.assertGreater(night[t], base[t])
        self.assertTrue(any("underestimate the turbulence close to the ground" in a for a in day["assumptions"]))
        self.assertTrue(any("SLC day" in e for e in day["dashboard"]["extensions"]))
        # Brookner with Cn0^2 = 1e-14 exp(1/320): exactly 1e-14 at the 1 m path -> the fixed-Cn2 ranges (the profile
        # modes integrate r0 on 801 instead of 201 path points: ~1e-6 relative)
        brook = ranges(run(cn2_mode="brookner", cn2=1e-14 * math.exp(1.0 / 320.0))[1])
        for t in base:
            self.assertAlmostEqual(brook[t], base[t], delta=1e-4 * base[t])

    def test_bands_and_inputs(self):
        p = template(VIS, turbulence__cn2_mode="greenwood_poor")
        q = AN._scale_turbulence(p, 10.0)
        self.assertEqual(q["turbulence"]["cn2_scale"], 10.0)
        self.assertEqual(q["turbulence"]["cn2"], p["turbulence"]["cn2"])            # the Cn2 field is not used
        weak, nominal = ranges(run_project(AN._scale_turbulence(p, 0.1))[1]), ranges(run_project(p)[1])
        for t in nominal:
            self.assertGreater(weak[t], nominal[t])
        paths = [x[0] for x in AN.applicable_inputs(p)]
        self.assertNotIn("turbulence.cn2", paths)
        self.assertIn("turbulence.cn2", [x[0] for x in AN.applicable_inputs(template(VIS, turbulence__cn2_mode=
                                                                                  "brookner"))])


class Cn2StatisticsNeutralDay(unittest.TestCase):
    def test_rows(self):
        for season in ("summer", "winter"):
            plain = {(r["time"], r["pct"]): r for r in AN.cn2_statistics_rows("Arid", season, overcast=True)}
            rows = {(r["time"], r["pct"]): r for r in AN.cn2_statistics_rows("Arid", season, overcast=True,
                                                                              neutral_day=True)}
            self.assertEqual(set(plain), set(rows))
            for key, r in plain.items():                                            # TRM4: day 4/3, night 2/3
                self.assertEqual(r["h_exp"], "4/3" if r["tod"] == "day" else "2/3", key)
                self.assertNotIn("h^-2/3", r["label"])
                self.assertEqual(rows[key]["cn2"], r["cn2"])
            for pct in ("50 %", "90 %"):
                self.assertEqual(rows[("Noon overcast", pct)]["h_exp"], "2/3")       # overcast noon: both seasons
                self.assertIn("h^-2/3", rows[("Noon overcast", pct)]["label"])
                # clear noon: h^-2/3 in winter only
                self.assertEqual(rows[("Noon", pct)]["h_exp"], "2/3" if season == "winter" else "4/3")
                self.assertEqual(rows[("Night", pct)]["h_exp"], "2/3")

    def test_winter_noon_ranges(self):
        p = template(VIS)
        with AN.Runner(2) as rn:
            s = AN.cn2_statistics(p, "Arid", "winter", runner=rn, neutral_day=True)
        self.assertTrue(s["neutral_day"])
        self.assertIn("FGAN-FOM 2005", s["method"])
        noon = next(r for r in s["rows"] if (r["time"], r["pct"]) == ("Noon", "50 %"))
        # the winter noon row is the TRM4 height mode with the h^-2/3 exponent; on the 1 m path it sees less
        # turbulence than with the clear-sky h^-4/3 (Cn2 given at 2 m)
        neutral = AN.model_ranges(AN._cn2_case(p, noon["cn2"], "night"))[0]
        clear = AN.model_ranges(AN._cn2_case(p, noon["cn2"], "day"))[0]
        for t in s["tasks"]:
            self.assertEqual(noon["ranges"][t], neutral[t])
            self.assertGreater(noon["ranges"][t], clear[t])


class WeatherCn2(unittest.TestCase):
    def test_regression_and_temporal_hours(self):
        T, rh, U, W = 300.0, 40.0, 3.0, 1.0
        want = (3.8e-14 * W + 2.0e-15 * T - 2.5e-15 * U + 1.2e-15 * U ** 2 - 8.5e-17 * U ** 3 - 2.8e-15 * rh +
                2.9e-17 * rh ** 2 - 1.1e-19 * rh ** 3 - 5.3e-13)
        self.assertAlmostEqual(X.cn2_sadot_kopeika(T, rh, U, W), want, delta=1e-27)
        self.assertAlmostEqual(want, 3.64e-14, delta=0.01e-14)
        self.assertEqual(X.sk_out_of_range(298.15, 40.0, 3.0), [])
        self.assertEqual(len(X.sk_out_of_range(275.0, 95.0, 12.0)), 3)
        self.assertEqual(X.temporal_hour(12.0, 6.0, 18.0), 6.0)
        self.assertEqual(X.sk_weight(X.temporal_hour(11.5, 6.0, 18.0)), (1.0, "h5_6"))
        self.assertEqual(X.sk_weight(-5.0), (0.11, "night"))
        self.assertEqual(X.sk_weight(-2.5), (0.07, "pre_sunrise"))
        self.assertEqual([X.sk_weight(h)[0] for h in (3.5, 4.5, 5.5)], [0.75, 0.95, 1.0])
        self.assertEqual(X.sk_weight(1.0), (None, None))                           # table not entered yet
        self.assertTrue(X.SK_W_PROVISIONAL)

    def test_mode_scales_from_15_m(self):
        c15 = X.cn2_sadot_kopeika(300.0, 40.0, 3.0, 1.0)
        wx = dict(cn2_mode="weather", wx_T_K=300.0, wx_rh_pct=40.0, wx_wind_ms=3.0, wx_W=1.0, time="day")
        _m, res = run(**wx)
        # = the TRM4 height mode with the regression Cn2 at 15 m and the day exponent h^-4/3
        self.assertEqual(ranges(res), ranges(run(cn2_mode="height", cn2=c15, h_ref_m=15.0, time="day")[1]))
        self.assertAlmostEqual(float(info(res)["Cn2 from the weather at 15 m (Sadot & Kopeika, PROVISIONAL W, "
                                               "extension)"]), c15, delta=0.001 * c15)
        a = [x for x in res["assumptions"] if "Sadot & Kopeika" in x][0]
        for word in ("PROVISIONAL", "R^2 = 0.02", "Mauna Loa", "local calibration", "15 m"):
            self.assertIn(word, a)
        self.assertTrue(any("Cn2 from the weather" in e for e in res["dashboard"]["extensions"]))
        # local calibration factor and the range-band scaling multiply the whole profile alike
        cal = ranges(run(wx_calib=10.0, **wx)[1])
        p = template(VIS)
        p["turbulence"].update(wx)
        self.assertEqual(ranges(run_project(AN._scale_turbulence(p, 10.0))[1]), cal)
        self.assertEqual(cal, ranges(run(cn2_mode="height", cn2=10.0 * c15, h_ref_m=15.0, time="day")[1]))

    def test_validity(self):
        with self.assertRaises(ModelError):                                         # regression <= 0 (cool, humid)
            run(cn2_mode="weather", wx_T_K=288.0, wx_rh_pct=70.0, wx_W=0.11, time="night")
        for bad in ({"wx_rh_pct": 120.0}, {"wx_calib": 0.0}, {"wx_wind_ms": -1.0}):
            with self.assertRaises(ModelError):
                run(cn2_mode="weather", **bad)
        _m, res = run(cn2_mode="weather", wx_T_K=313.15, wx_rh_pct=10.0)            # 40 C, RH 10 %
        self.assertTrue(any("validity range" in w for w in res["warnings"]))
        self.assertNotIn("turbulence.cn2", [x[0] for x in AN.applicable_inputs(template(
            VIS, turbulence__cn2_mode="weather"))])


if __name__ == "__main__":
    unittest.main()
