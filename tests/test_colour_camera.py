"""Engine 2.36 - colour camera with a Bayer colour filter array (upgrade report item U9, PROVISIONAL).

Source: Palum, "Image sampling with the Bayer color filter array", IS&T PICS 2001 - the resolution comes from the
green plane, whose Nyquist frequency on the axes is that of the monochrome array; adaptive interpolation takes the
average of the two green neighbours along the smaller gradient.  The transfer of the bilinear interpolation,
(3 + cos(2 pi r alpha)) / 4, is derived in trm4/extensions.py and checked here on a simulated mosaic.  The noise
power factor 2 is an assumption.  Off by default: the template ranges do not change.
"""
import math
import unittest

import numpy as np

from _common import LWIR, SWIR, VIS, ranges, run_project, template
from trm4 import extensions as X
from trm4.model import ModelError, TRM4Model

N = 64


def green_mosaic(img):
    """Green plane of a Bayer mosaic: known on the quincunx (i + j even), zero elsewhere."""
    i, j = np.indices(img.shape)
    mask = (i + j) % 2 == 0
    return np.where(mask, img, 0.0), mask


def neighbours(g):
    return np.roll(g, 1, 0), np.roll(g, -1, 0), np.roll(g, 1, 1), np.roll(g, -1, 1)      # north, south, west, east


def amplitude(img, k):
    """Amplitude of the horizontal frequency k cycles per N pixels (constant along the columns)."""
    return 2.0 * abs(np.fft.fft2(img)[0, k]) / img.size


class Interpolation(unittest.TestCase):
    def bars(self, k):
        x = np.arange(N)
        return np.tile(1.0 + 0.5 * np.cos(2 * np.pi * k * x / N + 0.3), (N, 1))

    def test_bilinear_transfer_matches_a_simulated_mosaic(self):
        for k in (1, 5, 11, 16, 24, 31):
            img = self.bars(k)
            g, mask = green_mosaic(img)
            n, s, w, e = neighbours(g)
            out = np.where(mask, g, 0.25 * (n + s + w + e))
            got = amplitude(out, k) / amplitude(img, k)
            want = float(X.bayer_bilinear_mtf(k / N, 1.0))                 # alpha = 1 pixel
            self.assertAlmostEqual(got, want, places=9, msg="k = %d" % k)

    def test_bilinear_limits(self):
        self.assertAlmostEqual(float(X.bayer_bilinear_mtf(0.0, 0.2)), 1.0)
        self.assertAlmostEqual(float(X.bayer_bilinear_mtf(0.5 / 0.2, 0.2)), 0.5)          # Nyquist

    def test_adaptive_reproduces_bars_along_an_axis(self):
        for k in (3, 16, 29):
            img = self.bars(k)
            g, mask = green_mosaic(img)
            n, s, w, e = neighbours(g)
            along = np.where(np.abs(n - s) <= np.abs(w - e), 0.5 * (n + s), 0.5 * (w + e))
            out = np.where(mask, g, along)
            self.assertTrue(np.allclose(out, img, atol=1e-12), "k = %d" % k)

    def test_green_plane_keeps_the_axis_nyquist_but_not_the_diagonal(self):
        i, j = np.indices((N, N))
        # the pattern at the monochrome Nyquist frequency along x is still seen by the green plane ...
        g, mask = green_mosaic(np.cos(np.pi * j))
        self.assertGreater(np.ptp(g[mask]), 1.9)
        # ... the diagonal pattern at the monochrome diagonal Nyquist is not: every green pixel sees the same value
        g, mask = green_mosaic(np.cos(np.pi * (i + j)))
        self.assertAlmostEqual(float(np.ptp(g[mask])), 0.0)


class ColourCamera(unittest.TestCase):
    def test_off_by_default(self):
        m, _res = run_project(template(VIS))
        self.assertIsNone(m.cfa)

    def test_adaptive_keeps_the_mtf_and_doubles_the_noise_power(self):
        a = TRM4Model(template(VIS))
        a.run()
        b = TRM4Model(template(VIS, detector__cfa="bayer"))
        b.run()
        self.assertEqual(b.cfa, "adaptive")
        r = np.linspace(0.1, a.r_N["h"], 7)
        self.assertTrue(np.allclose(a.mtf_dig(r, "h"), b.mtf_dig(r, "h")))
        rp = 0.5 * a.r_N["h"]
        self.assertAlmostEqual(b.psi(rp, "h", 10.0, 0.0) / a.psi(rp, "h", 10.0, 0.0), X.BAYER_NOISE_POWER, places=9)

    def test_bilinear_halves_the_mtf_at_nyquist(self):
        a = TRM4Model(template(VIS))
        a.run()
        b = TRM4Model(template(VIS, detector__cfa="bayer", detector__demosaic="bilinear"))
        b.run()
        rn = a.r_N["h"]
        self.assertAlmostEqual(float(b.mtf_dig(rn, "h") / a.mtf_dig(rn, "h")), 0.5, places=6)

    def test_ranges_never_longer_and_bilinear_is_the_shortest(self):
        for name in (VIS, SWIR):
            mono = ranges(run_project(template(name))[1])
            adaptive = ranges(run_project(template(name, detector__cfa="bayer"))[1])
            bilinear = ranges(run_project(template(name, detector__cfa="bayer", detector__demosaic="bilinear"))[1])
            for task in mono:
                self.assertLessEqual(adaptive[task], mono[task] + 1e-9, "%s %s" % (name, task))
                self.assertLessEqual(bilinear[task], adaptive[task] + 1e-9, "%s %s" % (name, task))
            self.assertLess(bilinear["Identification"], mono["Identification"])

    def test_reported(self):
        _m, res = run_project(template(VIS, detector__cfa="bayer"))
        self.assertTrue(any("PROVISIONAL" in a and "Bayer" in a for a in res["assumptions"]))
        self.assertTrue(any(row[1].startswith("Bayer array (extension)") for row in res["info"]))

    def test_ignored_in_the_thermal_category(self):
        base = ranges(run_project(template(LWIR))[1])
        m, res = run_project(template(LWIR, detector__cfa="bayer"))
        self.assertIsNone(m.cfa)
        self.assertEqual(ranges(res), base)
        self.assertTrue(any("Colour filter array ignored" in a for a in res["assumptions"]))

    def test_unknown_values_are_refused(self):
        with self.assertRaises(ModelError):
            run_project(template(VIS, detector__cfa="foveon"))
        with self.assertRaises(ModelError):
            run_project(template(VIS, detector__cfa="bayer", detector__demosaic="magic"))

    def test_noise_factor_is_the_stated_assumption(self):
        self.assertEqual(X.BAYER_NOISE_POWER, 2.0)
        self.assertAlmostEqual(math.sqrt(X.BAYER_NOISE_POWER), 1.41421356, places=7)


if __name__ == "__main__":
    unittest.main()
