"""Engine 2.32 - the atmospheric path (reports/TRM_Hadmaa_Field_Effects_and_Upgrades_HE_2026-11-23.pdf):

U3   the extinction falls off with the height of the line of sight (scale height);
U13  rain adds the same extinction in every band (ITU-R P.1814-1);
U4   a user-supplied additional extinction, e.g. the gas absorption the weather mode does not contain.

All three are 0 by default, and then nothing changes.
"""
import math
import unittest

from _common import LWIR, MWIR, VIS, as_file, ranges, run_project, setup_model, template
from trm4 import extensions as X
from trm4.model import ModelError


class Rain(unittest.TestCase):
    def test_itu_coefficients(self):
        self.assertEqual(X.rain_extinction(0.0), 0.0)
        # 10 mm/h: 1.2924 x 10^0.6436 = 5.69 dB/km = 1.31 /km
        self.assertAlmostEqual(X.rain_extinction(10.0) * X.DB_PER_NEPER, 1.2924 * 10 ** 0.6436, places=9)
        self.assertAlmostEqual(X.rain_extinction(10.0), 1.31, delta=0.01)
        with self.assertRaises(ValueError):
            X.rain_extinction(-1.0)

    def test_same_loss_in_every_band(self):
        s = X.rain_extinction(5.0)
        for name in (LWIR, MWIR, VIS):
            dry = setup_model(template(name)).atms[0]
            wet = setup_model(template(name, atmosphere__rain_mmh=5.0)).atms[0]
            self.assertAlmostEqual(wet.tau(2.0) / dry.tau(2.0), math.exp(-2.0 * s), places=9, msg=name)

    def test_rain_shortens_the_ranges_and_is_named(self):
        _m, dry = run_project(template(MWIR))
        m, wet = run_project(template(MWIR, atmosphere__rain_mmh=10.0))
        a, b = ranges(dry), ranges(wet)
        for k in a:
            self.assertLess(b[k], a[k])
        self.assertLess(b["Detection"], 0.5 * a["Detection"])          # the signal-limited task loses most
        self.assertTrue(any(x.startswith("Rain 10 mm/h") for x in m.assumptions))

    def test_weather_mode(self):
        over = dict(atmosphere__mode="weather")
        dry = setup_model(template(LWIR, **over)).atms[0]
        wet = setup_model(template(LWIR, atmosphere__rain_mmh=5.0, **over)).atms[0]
        self.assertAlmostEqual(wet.tau(3.0) / dry.tau(3.0), math.exp(-3.0 * X.rain_extinction(5.0)), places=6)


class ScaleHeight(unittest.TestCase):
    def test_height_factor(self):
        self.assertEqual(X.height_factor(0.0, 3000.0, 0.0), 1.0)                 # off
        self.assertAlmostEqual(X.height_factor(0.0, 0.0, 1.2), 1.0, places=12)
        self.assertAlmostEqual(X.height_factor(1200.0, 1200.0, 1.2), math.exp(-1.0), places=9)
        # ground to 3 km with H = 1.2 km: (H / dh) (1 - exp(-dh / H))
        self.assertAlmostEqual(X.height_factor(0.0, 3000.0, 1.2), 1.2 / 3.0 * (1 - math.exp(-2.5)), places=9)
        self.assertAlmostEqual(X.height_factor(3000.0, 0.0, 1.2), X.height_factor(0.0, 3000.0, 1.2), places=12)

    def test_horizontal_path_near_the_ground_is_unchanged(self):
        a = ranges(run_project(template(MWIR))[1])
        b = ranges(run_project(template(MWIR, atmosphere__scale_height_km=1.2))[1])
        for k in a:
            self.assertAlmostEqual(b[k], a[k], delta=2e-3 * a[k])                # exp(-1 m / 1.2 km)

    def test_look_down_path(self):
        over = dict(target__altitude_m=3000.0, target__alt_m=0.0)
        flat = setup_model(template(MWIR, **over)).atms[0]
        tall = setup_model(template(MWIR, atmosphere__scale_height_km=1.2, **over)).atms[0]
        f = 1.2 / 3.0 * (1 - math.exp(-2.5))
        R = 10.0
        self.assertAlmostEqual(math.log(tall.tau(R) / tall.tau0), f * math.log(flat.tau(R) / flat.tau0), places=9)
        a = ranges(run_project(template(MWIR, **over))[1])
        b = ranges(run_project(template(MWIR, atmosphere__scale_height_km=1.2, **over))[1])
        self.assertGreater(b["Detection"], 1.25 * a["Detection"])                # the homogeneous path is pessimistic


class AdditionalExtinction(unittest.TestCase):
    def test_adds_to_the_extinction(self):
        base = setup_model(template(MWIR)).atms[0]
        more = setup_model(template(MWIR, atmosphere__extra_sigma=0.1)).atms[0]
        self.assertAlmostEqual(more.tau(4.0) / base.tau(4.0), math.exp(-0.4), places=9)
        m, _res = run_project(template(MWIR, atmosphere__mode="weather", atmosphere__extra_sigma=0.1))
        self.assertTrue(any("Additional extinction 0.1 /km" in a for a in m.assumptions))

    def test_follows_the_scale_height_and_rain_does_not(self):
        over = dict(target__altitude_m=3000.0, target__alt_m=0.0, atmosphere__scale_height_km=1.2)
        base = setup_model(template(MWIR, **over)).atms[0]
        f = 1.2 / 3.0 * (1 - math.exp(-2.5))
        more = setup_model(template(MWIR, atmosphere__extra_sigma=0.1, **over)).atms[0]
        rain = setup_model(template(MWIR, atmosphere__rain_mmh=5.0, **over)).atms[0]
        self.assertAlmostEqual(more.tau(10.0) / base.tau(10.0), math.exp(-0.1 * 10.0 * f), places=9)
        self.assertAlmostEqual(rain.tau(10.0) / base.tau(10.0), math.exp(-10.0 * X.rain_extinction(5.0)), places=9)


class Defaults(unittest.TestCase):
    def test_off_by_default_and_bounds(self):
        m = setup_model(template(LWIR))
        self.assertEqual((m.atms[0].sigma_rain, m.atms[0].sigma_extra, m.atms[0].height), (0.0, 0.0, None))
        for key in ("rain_mmh", "extra_sigma", "scale_height_km"):
            with self.assertRaises(ModelError):
                setup_model(template(LWIR, **{"atmosphere__" + key: -1.0}))

    def test_imported_spectral_data_are_not_touched(self):
        lines = ["wavelength transmission"] + ["%g 0.6" % w for w in (7.0, 9.0, 11.0, 12.0)]
        over = dict(atmosphere__mode="spectral", atmosphere__spec_file=as_file("atm.txt", lines),
                    atmosphere__spec_L_km=2.0)
        a = setup_model(template(LWIR, **over)).atms[0]
        b = setup_model(template(LWIR, atmosphere__rain_mmh=20.0, atmosphere__extra_sigma=1.0,
                                 atmosphere__scale_height_km=1.0, **over)).atms[0]
        self.assertAlmostEqual(a.tau(3.0), b.tau(3.0), places=12)


if __name__ == "__main__":
    unittest.main()
