"""Laboratory frame tools on synthetic frames with known answers: slanted-edge SFR (ISO 12233 e-SFR) against the
analytic Gaussian x pixel-aperture MTF, and the EMVA 1288 photon-transfer analysis against the generator's gain,
read noise, full well, PRNU, DSNU and dark current."""
import os
import tempfile
import unittest

import numpy as np

import _common  # noqa: F401  (puts the project on sys.path)
from trm4 import imports as IM
from trm4 import labtools as LT


class SlantedEdge(unittest.TestCase):
    def true_sfr(self, f, sigma):
        return np.exp(-2 * np.pi ** 2 * sigma ** 2 * f ** 2) * np.abs(np.sinc(f))

    def test_recovers_known_mtf(self):
        for sigma, angle in ((0.5, 5.0), (0.9, 8.0), (0.7, -4.0)):
            res = LT.slanted_edge_sfr(LT.synthetic_edge(angle_deg=angle, sigma_px=sigma))
            sel = res["f"] <= 0.5
            err = np.max(np.abs(res["sfr"][sel] - self.true_sfr(res["f"][sel], sigma)))
            self.assertLess(err, 0.03, (sigma, angle, err))
            self.assertAlmostEqual(res["angle_deg"], angle, delta=0.2)
            self.assertFalse(res["notes"])

    def test_horizontal_edge_and_noise(self):
        img = LT.synthetic_edge(angle_deg=6.0, sigma_px=0.6, noise=1.0, seed=3).T
        res = LT.slanted_edge_sfr(img)
        self.assertEqual(res["orientation"], "horizontal")
        sel = res["f"] <= 0.4
        self.assertLess(np.max(np.abs(res["sfr"][sel] - self.true_sfr(res["f"][sel], 0.6))), 0.05)
        f = np.linspace(0.0, 0.5, 50001)
        true50 = f[np.argmax(self.true_sfr(f, 0.6) < 0.5)]                    # ~0.28 cycles/pixel
        self.assertAlmostEqual(res["mtf50"], true50, delta=0.02)

    def test_small_angle_flagged(self):
        res = LT.slanted_edge_sfr(LT.synthetic_edge(angle_deg=0.3, sigma_px=0.6))
        self.assertTrue(any("angle" in n for n in res["notes"]))

    def test_text_feeds_the_mtf_import(self):
        res = LT.slanted_edge_sfr(LT.synthetic_edge())
        c = IM.parse_curve_hv(LT.sfr_to_text(res), "MTF / SFR")
        np.testing.assert_allclose(c["h"], res["sfr"], atol=1e-6)

    def test_load_frame(self):
        img = LT.synthetic_edge(shape=(20, 30))
        with tempfile.TemporaryDirectory() as d:
            for ext in (".npy", ".csv"):
                fn = os.path.join(d, "edge" + ext)
                np.save(fn, img) if ext == ".npy" else np.savetxt(fn, img, delimiter=",")
                np.testing.assert_allclose(LT.load_frame(fn), img, rtol=1e-9)


class PhotonTransfer(unittest.TestCase):
    def test_recovers_camera_parameters(self):
        flats, dark, series = LT.synthetic_ptc(K=0.25, read_e=5.0, full_well=20000.0, prnu=0.01, dsnu_e=3.0,
                                               dark_e_s=2000.0)
        r = LT.photon_transfer(flats, dark, t_int_s=0.01, dark_series=series)
        self.assertAlmostEqual(r["K_DN_per_e"], 0.25, delta=0.25 * 0.03)
        self.assertAlmostEqual(r["read_noise_e"], 5.0, delta=0.6)            # incl. the DN rounding
        self.assertAlmostEqual(r["sat_e"], 20000.0, delta=20000.0 * 0.12)    # level grid ~10 %
        self.assertAlmostEqual(r["prnu_pct"], 1.0, delta=0.15)
        self.assertAlmostEqual(r["dsnu_e"], 3.0, delta=0.5)
        self.assertAlmostEqual(r["dark_current_e_s"], 2000.0, delta=100.0)
        self.assertFalse(r["notes"])
        t = r["trm"]
        self.assertEqual((t["detector.adc_mode"], t["detector.cap_node"], t["detector.fpn_mode"]),
                         ("carriers", "camera", "measured"))
        self.assertAlmostEqual(t["detector.lsb_e"], 4.0, delta=0.15)
        self.assertGreater(t["detector.dark_A"], 0)

    def test_needs_levels(self):
        flats, dark, _s = LT.synthetic_ptc(levels=2)
        with self.assertRaises(ValueError):
            LT.photon_transfer(flats, dark)


if __name__ == "__main__":
    unittest.main()
