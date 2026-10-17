"""Edge cases: no contrast, missing data, unit errors and invalid extrapolation are reported clearly."""
import unittest

from _common import LWIR, VIS, template, setup_model, run_project
from trm4 import derived as DV
from trm4.model import ModelError


class EdgeCases(unittest.TestCase):
    def test_no_target_contrast(self):
        _m, res = run_project(template(LWIR, target__dT_K=0.0))
        self.assertTrue(any("No target contrast" in w for w in res["warnings"]))
        self.assertTrue(all(t["R0"] is None for t in res["range"]["atm"][0]["tasks"]))

    def test_low_contrast_below_netd(self):
        _m, res = run_project(template(LWIR, target__dT_K=0.005))
        self.assertTrue(any("below the NETD" in w for w in res["warnings"]))

    def test_missing_import_files(self):
        for over in ({"optics__mtf_source": "zemax"}, {"optics__tau_mode": "zemax"},
                     {"atmosphere__mode": "spectral"}, {"stab__jitter_mode": "measured"}):
            with self.subTest(**over):
                with self.assertRaises(ModelError) as cm:
                    run_project(template(LWIR, **over))
                self.assertIn("imported", str(cm.exception))

    def test_custom_qe_fraction_detected(self):
        qe = "\n".join("%.2f %.2f" % (x, 0.7) for x in (8.0, 9.0, 10.0, 11.0, 12.0))
        m = setup_model(template(LWIR, detector__qe_preset="Custom", detector__qe_custom=qe))
        self.assertAlmostEqual(float(m.eta.max()), 0.7, places=6)
        self.assertTrue(any("fractions" in w for w in m.warnings))

    def test_custom_qe_nm_detected(self):
        qe = "\n".join("%d %d" % (x, 70) for x in (8000, 9000, 10000, 11000))
        m = setup_model(template(LWIR, detector__qe_preset="Custom", detector__qe_custom=qe))
        self.assertAlmostEqual(m.band[0], 8.0, places=6)

    def test_unsupported_band_category(self):
        _rows, warns = DV.compute(template(VIS, detector__qe_preset="CMT LWIR generic"))
        self.assertTrue(any("emission is ignored" in w for w in warns))

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ModelError):
            run_project(template(LWIR, optics__f_mm=0.0))
        with self.assertRaises(ModelError):
            run_project(template(LWIR, atmosphere__atm__0__tau0=1.5))


if __name__ == "__main__":
    unittest.main()
