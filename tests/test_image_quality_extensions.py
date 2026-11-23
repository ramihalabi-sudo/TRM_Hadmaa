"""Engine 2.32 - image quality and detection extensions (reports/TRM_Hadmaa_Field_Effects_and_Upgrades_HE_2026-11-23.pdf):

U5  focus error: the optics MTF of a defocused pupil;
U6  ambient light on the display (diagnostic);
U7  detection range of a point (sub-pixel) target;
U8  dark current of HgCdTe from the sensor temperature (Rule 07).

Every one is off by default, and then nothing changes.
"""
import math
import unittest

import numpy as np

from _common import LWIR, MWIR, as_file, ranges, run_project, setup_model, template
from trm4 import extensions as X
from trm4 import mtf as M
from trm4.model import ModelError, TRM4Model


class Defocus(unittest.TestCase):
    D, F_MM, LAM = 50.0, 100.0, 10.0

    def test_in_focus_is_the_diffraction_mtf(self):
        r = np.linspace(0.0, 0.95 * self.D / self.LAM, 12)
        a = M.DefocusMTF(self.D, 0.0, 0.0, 0.0)(r, self.LAM, 0.0, self.F_MM)
        b = M.DiffractionMTF(self.D, 0.0, 0.0, 0.0)(r, self.LAM)
        self.assertLess(np.max(np.abs(a - b)), 2e-4)

    def test_against_the_autocorrelation_of_the_defocused_pupil(self):
        # independent calculation: 2-D FFT autocorrelation of the pupil with the phase 2 pi dz rho^2 / (2 f^2 lambda)
        N, L = 512, 4 * self.D
        x = (np.arange(N) - N / 2) * L / N
        X2, Y2 = np.meshgrid(x, x)
        rho2 = X2 ** 2 + Y2 ** 2
        ks = np.array([4, 8, 16, 24, 40])
        d = ks * L / N
        dof = 2 * self.LAM * (self.F_MM / self.D) ** 2
        for dz in (dof, 3 * dof, 10 * dof):
            pupil = (rho2 <= (self.D / 2) ** 2) * np.exp(1j * 2 * np.pi * dz * rho2 / (2 * self.F_MM ** 2) / self.LAM)
            ac = np.fft.fftshift(np.fft.ifft2(np.abs(np.fft.fft2(pupil)) ** 2))
            ref = np.real(ac[N // 2, N // 2 + ks] / ac[N // 2, N // 2])
            got = M.DefocusMTF(self.D, 0.0, 0.0, 0.0)(d / self.LAM, self.LAM, dz, self.F_MM)
            self.assertLess(np.max(np.abs(got - ref)), 6e-3, "dz = %.0f um" % dz)

    def test_depth_of_focus_and_ranges(self):
        base = ranges(run_project(template(LWIR))[1])
        m, res = run_project(template(LWIR, optics__defocus_um=40.0))            # about half the depth of focus
        self.assertAlmostEqual(m.defocus["depth_um"], 2 * m.defocus["lam_um"] * m.F_eff ** 2, places=9)
        small = ranges(res)
        big = ranges(run_project(template(LWIR, optics__defocus_um=320.0))[1])
        for k in base:
            self.assertGreater(small[k], 0.97 * base[k])                     # inside the depth of focus: small loss
            self.assertLessEqual(small[k], base[k] * (1 + 1e-6))
            self.assertLess(big[k], 0.5 * base[k])                           # four depths of focus: the range collapses
        self.assertTrue(any(a.startswith("Focus error 40 um") for a in m.assumptions))
        # the sign of the focus error does not matter
        neg = ranges(run_project(template(LWIR, optics__defocus_um=-320.0))[1])
        for k in big:
            self.assertAlmostEqual(neg[k], big[k], delta=1e-6 * big[k])

    def test_more_defocus_never_gives_a_longer_range(self):
        last = None
        for dz in (0.0, 60.0, 120.0, 200.0, 320.0, 500.0):
            r = ranges(run_project(template(LWIR, optics__defocus_um=dz))[1])["Recognition"]
            if last is not None:
                self.assertLessEqual(r, last * (1 + 1e-6), "dz = %g" % dz)
            last = r

    def test_not_applied_to_an_imported_mtf(self):
        m0 = TRM4Model(template(LWIR))
        m0.run()
        lines = ["# cycles/mrad MTF"] + ["%.5g %.5g" % (x, y) for x, y in zip(*m0.opt_tab["h"]) if x <= 6.0][::40]
        p = template(LWIR, optics__mtf_source="measured", optics__zemax_mtf=as_file("lens.txt", lines),
                     optics__zemax_mtf_unit="mrad", optics__defocus_um=300.0)
        m, _res = run_project(p)
        self.assertIsNone(m.defocus)
        self.assertTrue(any("Focus error 300 um is not applied" in w for w in m.warnings))


class Rule07(unittest.TestCase):
    def test_formula(self):
        k = X.RULE07
        # above the threshold wavelength: J0 exp(C q 1.24 / (k lambda T))
        self.assertAlmostEqual(X.rule07_current_density(5.0, 150.0),
                               k["J0"] * math.exp(k["C"] * 1.24 * k["q"] / (k["k"] * 5.0 * 150.0)), places=15)
        self.assertAlmostEqual(X.rule07_current_density(5.0, 150.0), 1.715e-6, delta=2e-9)
        self.assertAlmostEqual(X.rule07_current_density(10.0, 77.0), 3.06e-6, delta=2e-8)
        # doubles about every 5 K at 150 K, 5 um
        self.assertAlmostEqual(X.rule07_current_density(5.0, 155.0) / X.rule07_current_density(5.0, 150.0), 2.0,
                               delta=0.1)
        self.assertLess(X.rule07_current_density(4.2, 150.0), X.rule07_current_density(5.0, 150.0))
        with self.assertRaises(ValueError):
            X.rule07_current_density(5.0, 0.0)

    def test_dark_current_follows_the_sensor_temperature(self):
        cold = setup_model(template(MWIR, detector__dark_mode="rule07", detector__T_sensor_K=80.0))
        hot = setup_model(template(MWIR, detector__dark_mode="rule07", detector__T_sensor_K=150.0))
        self.assertGreater(hot.dark_A, 1e6 * cold.dark_A)
        self.assertGreater(hot.netd, cold.netd)
        lam_c = hot._cutoff_um()
        self.assertTrue(5.0 < lam_c < 5.7)                                    # 50 % point of the InSb preset curve
        area = 15e-4 * 15e-4
        self.assertAlmostEqual(hot.dark_A, X.rule07_current_density(lam_c, 150.0) * area, delta=1e-6 * hot.dark_A)
        self.assertTrue(any("Rule 07" in a for a in hot.assumptions))

    def test_needs_the_sensor_temperature(self):
        with self.assertRaises(ModelError):
            setup_model(template(MWIR, detector__dark_mode="rule07"))


class AmbientLight(unittest.TestCase):
    def test_reflected_luminance(self):
        a = X.display_ambient(100.0, 10000.0, 0.05)
        self.assertAlmostEqual(a["L_refl"], 0.05 * 10000.0 / math.pi, places=9)
        self.assertAlmostEqual(a["contrast_factor"], 100.0 / (100.0 + a["L_refl"]), places=12)

    def test_diagnostic_only(self):
        _m, base = run_project(template(MWIR))
        m, lit = run_project(template(MWIR, display__ambient_lux=10000.0))
        self.assertEqual(ranges(base), ranges(lit))                           # the ranges are not changed
        self.assertTrue(any(w.startswith("Ambient light") and "optimistic" in w for w in m.warnings))
        m2, _ = run_project(template(MWIR, display__ambient_lux=300.0))        # office light: an assumption, no warning
        self.assertFalse(any(w.startswith("Ambient light") for w in m2.warnings))
        self.assertTrue(any(a.startswith("Ambient light") for a in m2.assumptions))
        self.assertIsNone(setup_model(template(MWIR)).ambient)
        with self.assertRaises(ModelError):
            setup_model(template(MWIR, display__ambient_lux=100.0, display__reflectance=1.5))


class PointTarget(unittest.TestCase):
    def test_off_by_default(self):
        _m, res = run_project(template(MWIR))
        self.assertNotIn("point", res["range"]["atm"][0])

    def test_small_target(self):
        over = dict(target__W_m=0.5, target__H_m=0.5)
        m0, base = run_project(template(MWIR, **over))
        m, res = run_project(template(MWIR, target__point=True, **over))
        self.assertEqual(ranges(base), ranges(res))                            # TRM4 ranges unchanged
        pt = res["range"]["atm"][0]["point"]
        self.assertGreater(pt["R0"], ranges(res)["Detection"])                 # a point is detected beyond one line pair
        self.assertTrue(0.0 < pt["energy"] <= 1.0)
        self.assertTrue(0.0 < pt["fill"] < 1.0)                                # sub-pixel at that range
        # the criterion holds at the reported range: SNR = signal x fill x energy / noise
        atm = m.atms[0]
        s = m.signal_state(pt["R0"], atm)
        n = math.sqrt(s["nes"] ** 2 / m.n_int_frames + s["ies"] ** 2)
        self.assertAlmostEqual(s["eds"] * pt["fill"] * pt["energy"] / n, pt["snr"], delta=0.01 * pt["snr"])
        # a stricter criterion shortens the range, bad weather shortens it
        strict = run_project(template(MWIR, target__point=True, target__point_snr=10.0, **over))[1]
        self.assertLess(strict["range"]["atm"][0]["point"]["R0"], pt["R0"])
        self.assertLess(res["range"]["atm"][1]["point"]["R0"], pt["R0"])
        self.assertTrue(any(row[0] == "Point target (extension)" for row in res["info"]))

    def test_aperture_matters_more_than_focal_length(self):
        over = dict(target__W_m=0.3, target__H_m=0.3, target__point=True)
        base = run_project(template(MWIR, **over))[1]["range"]["atm"][0]["point"]["R0"]
        big = run_project(template(MWIR, optics__D_mm=75.0, **over))[1]["range"]["atm"][0]["point"]["R0"]
        self.assertGreater(big, 1.1 * base)


if __name__ == "__main__":
    unittest.main()
