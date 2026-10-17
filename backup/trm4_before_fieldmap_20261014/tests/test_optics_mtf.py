"""Optics: the diffraction-limited curve is reproduced; imported MTFs are not diffracted twice."""
import unittest

import numpy as np

from _common import LWIR, template, setup_model, as_file, circ_mtf, run_project
from trm4 import mtf as M


def mtf_file(f_max=50.0, n=26, power=2.0, scale=1.0):
    f = np.linspace(0, f_max, n)
    m = (1 - f / f_max) ** power * scale
    return as_file("lens.txt", ["Spatial frequency in cycles per mm", "Field: 0.0000 deg",
                                "Spatial frequency  Tangential  Sagittal"] +
                   ["%.4f %.6f %.6f" % (a, b, b) for a, b in zip(f, m)]), f, m


class Optics(unittest.TestCase):
    def test_pupil_overlap_circular(self):
        dm = M.DiffractionMTF(50.0, 0.0, 0.0, 0.0)
        r = np.linspace(0, 4.9, 30)                    # 1/mrad
        lam = 10.0                                     # um -> pupil shift = r * lam [mm]
        np.testing.assert_allclose(dm(r, lam), circ_mtf(r * lam / 50.0), atol=2e-3)

    def test_model_single_wavelength_is_diffraction_limited(self):
        m = setup_model(template(LWIR, optics__diffraction="single", optics__lambda_diff_um=10.0))
        m._setup_weights(0.0)
        m._setup_mtf()
        r = np.linspace(0, 4.5, 20)
        np.testing.assert_allclose(m.mtf_opt(r, "h"), circ_mtf(r * 10.0 / 50.0), atol=2e-3)

    def test_imported_optics_mtf_not_rediffracted(self):
        fobj, f, mf = mtf_file()
        m = setup_model(template(LWIR, optics__mtf_source="zemax", optics__zemax_mtf=fobj,
                                 optics__zemax_mtf_unit="mm", optics__mtf_meta="poly 8-12 um, on axis"))
        m._setup_weights(0.0)
        m._setup_mtf()
        r = f * 100.0 / 1000.0                         # cycles/mm -> cycles/mrad with f = 100 mm
        # only grid resampling differences (re-diffraction would change the curve by tens of percent)
        np.testing.assert_allclose(m.mtf_opt(r[:-1], "h"), mf[:-1], atol=1e-4)
        self.assertEqual(m.mtf_mode, "B")
        # the detector MTF is still applied in Mode B
        self.assertLess(float(m.mtf_det(np.array([3.0]), "h")[0]), 0.9)

    def test_device_prefilter_bypasses_detector(self):
        fobj, f, mf = mtf_file()
        m = setup_model(template(LWIR, optics__mtf_source="device", optics__zemax_mtf=fobj,
                                 optics__zemax_mtf_unit="mm"))
        m._setup_weights(0.0)
        m._setup_mtf()
        r = f[:-1] * 0.1
        np.testing.assert_allclose(m.pre_device(r, "h"), mf[:-1], atol=1e-4)
        np.testing.assert_allclose(m.mtf_det(r, "h"), 1.0)
        self.assertEqual(m.mtf_mode, "C")

    def test_mtf_outside_range_and_short_data_warn(self):
        fobj, _f, _m = mtf_file(f_max=20.0)               # ends at 2 1/mrad < Nyquist 3.33
        _m2, res = run_project(template(LWIR, optics__mtf_source="zemax", optics__zemax_mtf=fobj,
                                        optics__zemax_mtf_unit="mm"))
        self.assertTrue(any("below the Nyquist" in w for w in res["warnings"]))
        self.assertTrue(any("not documented" in a for a in res["assumptions"]))
        bad = as_file("bad.txt", ["Spatial frequency in cycles per mm", "f T S", "0 1.00 1.00", "10 1.20 1.20",
                                  "20 0.5 0.5", "30 0.2 0.2", "40 0.05 0.05"])
        _m3, res = run_project(template(LWIR, optics__mtf_source="zemax", optics__zemax_mtf=bad,
                                        optics__zemax_mtf_unit="mm"))
        self.assertTrue(any("values above 1" in w for w in res["warnings"]))

    def test_aberration_is_labelled_approximation(self):
        _m, res = run_project(template(LWIR, optics__aberration="q", optics__q=1.5))
        self.assertTrue(any("approximated" in a for a in res["assumptions"]))


if __name__ == "__main__":
    unittest.main()
