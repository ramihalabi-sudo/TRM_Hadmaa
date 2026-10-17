"""Transmission (absolute / normalized, no double counting), Beer-Lambert, spectral atmosphere import."""
import math
import unittest

import numpy as np

from _common import LWIR, SWIR, MWIR, template, setup_model, as_file, ranges, run_project
from trm4 import imports as IM
from trm4 import presets as P
from trm4.model import Atmosphere, ModelError


def tau_file(value, lam=(7.0, 12.0)):
    xs = np.linspace(lam[0], lam[1], 11)
    return as_file("tau.csv", ["Wavelength (um), Transmission"] + ["%.3f, %.12f" % (x, value) for x in xs])


class OpticsTransmission(unittest.TestCase):
    def test_absolute(self):
        m = setup_model(template(LWIR, optics__tau_mode="zemax", optics__zemax_tau=tau_file(0.5),
                                 optics__tau_filter=0.9))
        np.testing.assert_allclose(m.tau_o, 0.45)

    def test_normalized_uses_peak_value(self):
        m = setup_model(template(LWIR, optics__tau_mode="zemax", optics__zemax_tau=tau_file(0.5),
                                 optics__tau_kind="normalized", optics__tau_opt=0.8, optics__tau_filter=1.0))
        np.testing.assert_allclose(m.tau_o, 0.8)

    def test_system_throughput_not_counted_twice(self):
        m = setup_model(template(LWIR, optics__tau_mode="zemax", optics__zemax_tau=tau_file(0.5),
                                 optics__tau_scope="system", optics__tau_filter=0.9))
        np.testing.assert_allclose(m.tau_o, 0.5)
        self.assertTrue(any("NOT applied" in w for w in m.warnings))

    def test_transmission_outside_unit_interval_rejected(self):
        with self.assertRaises(ModelError):
            run_project(template(LWIR, optics__tau_opt=1.2))


class Atmospheres(unittest.TestCase):
    def test_beer_lambert(self):
        a = Atmosphere("x", 0.3, 0.9, 288.0, 0.0)
        for R in (0.0, 1.0, 2.5, 10.0):
            self.assertAlmostEqual(a.tau(R), 0.9 * math.exp(-0.3 * R), places=12)

    def test_spectral_single_column_scales_per_wavelength(self):
        p = template(LWIR, atmosphere__mode="spectral", atmosphere__spec_file=tau_file(0.6, (6.0, 13.0)),
                     atmosphere__spec_L_km=1.0)
        m = setup_model(p)
        self.assertAlmostEqual(m.atms[0].tau(2.0), 0.36, places=6)
        self.assertAlmostEqual(m.atms[0].tau(0.5), math.sqrt(0.6), places=6)

    def test_multi_range_table(self):
        lines = ["wavelength_um 1 2 4"] + ["%.2f %.6f %.6f %.6f" % (x, math.exp(-0.2), math.exp(-0.4), math.exp(-0.8))
                                          for x in np.linspace(6, 13, 8)]
        d = IM.parse_spectral_atmosphere("\n".join(lines), 1.0)
        np.testing.assert_allclose(d["R"], [1, 2, 4])
        a = Atmosphere("x", 0, 1, 288, 0, spec={"lam": d["lam"], "R": d["R"], "tau": d["tau"]})
        a.band_w = np.ones_like(d["lam"])
        self.assertAlmostEqual(a.tau(3.0), math.exp(-0.6), places=6)

    def test_spectral_equals_fast_mode_for_grey_atmosphere(self):
        sigma = 0.3
        fast = template(LWIR)
        fast["atmosphere"]["atm"] = [dict(fast["atmosphere"]["atm"][0], on=True, sigma=sigma, tau0=1.0),
                                     dict(fast["atmosphere"]["atm"][1], on=False),
                                     dict(fast["atmosphere"]["atm"][2], on=False)]
        spec = template(LWIR, atmosphere__mode="spectral",
                        atmosphere__spec_file=tau_file(math.exp(-sigma), (6.0, 13.0)), atmosphere__spec_L_km=1.0)
        r_fast = ranges(run_project(fast)[1])
        r_spec = ranges(run_project(spec)[1])
        for k in r_fast:
            self.assertAlmostEqual(r_spec[k], r_fast[k], delta=1e-6 * r_fast[k])

    def test_visibility_not_used_as_ir_extinction(self):
        _m, res = run_project(template(MWIR, atmosphere__mode="visibility"))
        self.assertTrue(any("not converted to an infrared extinction" in w for w in res["warnings"]))

    def test_path_radiance_import_independent(self):
        lam = np.linspace(0.8, 1.8, 11)
        f = as_file("path.txt", ["wavelength L"] + ["%.3f %.5g" % (x, 0.5) for x in lam])
        base = run_project(template(SWIR))[1]
        withp = run_project(template(SWIR, atmosphere__path_mode="import", atmosphere__path_file=f,
                                     atmosphere__path_L_km=1.0))[1]
        # added path radiance increases noise / lowers contrast -> ranges must not increase
        for k, v in ranges(base).items():
            self.assertLessEqual(ranges(withp)[k], v * 1.0001)
        self.assertTrue(any(i["what"] == "Path radiance" for i in withp["provenance"]["imports"]))

    def test_presets_by_band(self):
        atms = P.atmosphere_preset(template(LWIR), "all")
        self.assertEqual([a["sigma"] for a in atms], [0.2, 0.4, 1.0])
        atms = P.atmosphere_preset(template(SWIR), "clear")
        self.assertEqual(atms[0]["sigma"], 0.10)
        self.assertFalse(atms[1]["on"])


if __name__ == "__main__":
    unittest.main()
