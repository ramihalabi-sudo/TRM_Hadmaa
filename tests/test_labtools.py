"""Laboratory frame tools on synthetic frames with known answers: slanted-edge SFR (ISO 12233 e-SFR) against the
analytic Gaussian x pixel-aperture MTF, the EMVA 1288 photon-transfer analysis against the generator's gain,
read noise, full well, PRNU, DSNU and dark current, and the spectral-ratio Fried parameter (Hardie et al. 2021)
against the r0 of synthetic turbulence sequences."""
import math
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np

import _common  # noqa: F401  (puts the project on sys.path)
from trm4 import extensions as X
from trm4 import imports as IM
from trm4 import labtools as LT
from trm4 import mtf as M


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


class FriedParameterFromFrames(unittest.TestCase):
    """Synthetic sequences: a static scene blurred by a known short-exposure OTF (diffraction x Fried near field) and
    shifted by random Gaussian tilts of the variance that belongs to the known r0 (Hardie et al. 2021, Eq. 36)."""
    OPT = dict(lam_um=0.55, focal_mm=500.0, pitch_um=5.0, D_mm=100.0)
    TOL = 0.10            # r0 within +/-10 % with 300 frames of 128 x 128 (5 seeds x 3 r0 here: at most 5.3 %)

    def test_recovers_known_r0(self):
        for r0, seed in ((0.015, 1), (0.03, 2), (0.06, 3)):                       # tilt 1.1 / 0.63 / 0.35 pixels
            frames, tilt = LT.synthetic_turbulence_frames(r0, n=300, seed=seed, **self.OPT)
            res = LT.r0_from_frames(frames, **self.OPT)
            self.assertAlmostEqual(res["r0_m"], r0, delta=self.TOL * r0, msg=(r0, tilt))
            self.assertAlmostEqual(res["tilt_px"], tilt, delta=0.1 * tilt)
            self.assertGreater(res["r2"], 0.98)
            self.assertFalse(res["notes"])
        noisy, _t = LT.synthetic_turbulence_frames(0.03, n=300, seed=4, noise=0.05, **self.OPT)
        self.assertAlmostEqual(LT.r0_from_frames(noisy, **self.OPT)["r0_m"], 0.03, delta=self.TOL * 0.03)

    def test_units(self):
        frames, _t = LT.synthetic_turbulence_frames(0.03, n=100, seed=5, **self.OPT)
        res = LT.r0_from_frames(frames, **self.OPT)
        # Eq. (44) with sigma_G in cycles per metre of the focal plane = (cycles/pixel) / pitch [m]
        sg = res["sigma_G_px"] / 5e-6
        self.assertAlmostEqual(res["sigma_G_per_mm"], sg * 1e-3)
        r0 = (6.88 * (0.55e-6 * 0.5 * sg) ** 2 / 0.1 ** (1 / 3)) ** 0.6
        self.assertAlmostEqual(res["r0_m"], r0, delta=1e-12)
        # only the pixel angle pitch / focal length matters: the same frames with 2x pitch and 2x focal length
        same = LT.r0_from_frames(frames, 0.55, 1000.0, 10.0, 100.0)
        self.assertAlmostEqual(same["r0_m"], res["r0_m"], delta=1e-9)
        self.assertAlmostEqual(res["tilt_urad"], res["tilt_px"] * 5e-6 / 0.5 * 1e6)

    def test_alpha_and_registration(self):
        # frames with the residual tilt of a registration that removed 52 % (global registration, Hardie et al.)
        frames, _t = LT.synthetic_turbulence_frames(0.03, n=300, seed=3, alpha=0.52, **self.OPT)
        self.assertAlmostEqual(LT.r0_from_frames(frames, alpha=0.52, **self.OPT)["r0_m"], 0.03, delta=self.TOL * 0.03)
        self.assertGreater(LT.r0_from_frames(frames, **self.OPT)["r0_m"], 1.3 * 0.03)    # alpha ignored: inflated
        # global registration recovers known camera shifts (sub-pixel) ...
        still, _t = LT.synthetic_turbulence_frames(1.0, n=1, seed=6, **self.OPT)
        rng = np.random.default_rng(7)
        true = rng.uniform(-3.0, 3.0, (24, 2))
        fy, fx = LT._freq_grid(128, 128)
        moved = np.array([LT._shifted(still[0], dy, dx, fy, fx) for dy, dx in true])
        _reg, shifts = LT.register_frames(moved)
        err = (shifts - shifts.mean(axis=0)) - (true - true.mean(axis=0))
        self.assertLess(float(np.abs(err).max()), 0.02)
        # ... so a sequence whose tilt is all global is fully registered: nothing left to measure
        with self.assertRaises(ValueError) as cm:
            LT.r0_from_frames(moved, register=True, **self.OPT)
        self.assertIn("not resolved", str(cm.exception))

    def test_rejects_bad_input(self):
        frames, _t = LT.synthetic_turbulence_frames(0.03, n=12, seed=8, **self.OPT)
        with self.assertRaises(ValueError):
            LT.r0_from_frames(frames[:5], **self.OPT)                               # too few frames
        with self.assertRaises(ValueError):
            LT.r0_from_frames(frames, alpha=1.0, **self.OPT)
        with self.assertRaises(ValueError):
            LT.r0_from_frames(frames[:, :20, :20], **self.OPT)
        tiny, _t = LT.synthetic_turbulence_frames(0.5, n=50, seed=9, **self.OPT)    # tilt 0.06 pixels
        with self.assertRaises(ValueError):
            LT.r0_from_frames(tiny, **self.OPT)
        self.assertTrue(LT.r0_from_frames(frames, **self.OPT)["notes"])           # 12 frames: flagged

    def test_trm_inputs_text_and_cli(self):
        frames, _t = LT.synthetic_turbulence_frames(0.03, n=150, seed=10, **self.OPT)
        res = LT.r0_from_frames(frames, path_km=2.0, **self.OPT)
        t = res["trm"]
        self.assertEqual((t["turbulence.cn2_mode"], t["turbulence.r0_lambda_um"], t["turbulence.r0_L_km"]),
                         ("r0", 0.55, 2.0))
        self.assertAlmostEqual(t["turbulence.r0_cm"], res["r0_cm"], places=3)
        # the path-averaged Cn2 gives back r0 through TRM4 Eq. (4.82)
        r0 = M.fried_parameter(0.55, 2.0, lambda z: np.full_like(z, res["cn2"]))
        self.assertAlmostEqual(r0, res["r0_m"], delta=1e-4 * r0)
        self.assertAlmostEqual(X.cn2_uniform_from_r0(r0, 0.55, 2.0), res["cn2"], delta=1e-4 * res["cn2"])
        self.assertEqual(LT.r0_from_frames(frames, **self.OPT)["trm"], {})        # no path length: no TRM input
        text = LT.r0_to_text(res, "seq")
        data = np.loadtxt(text.splitlines(), comments="#")
        self.assertEqual(data.shape, (len(res["f"]), 4))
        with tempfile.TemporaryDirectory() as d:
            stack = os.path.join(d, "seq.npy")
            np.save(stack, frames)
            np.testing.assert_allclose(LT.load_frames([stack]), frames)
            for k in range(3):
                np.save(os.path.join(d, "f%d.npy" % k), frames[k])
            self.assertEqual(LT.load_frames([os.path.join(d, "f%d.npy" % k) for k in range(3)]).shape,
                             (3, 128, 128))
            out = os.path.join(d, "r0.txt")
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            p = subprocess.run([sys.executable, os.path.join(root, "run_trm4.py"), "--r0-frames", stack, "--lam",
                                "0.55", "--focal", "500", "--pitch", "5", "--aperture", "100", "--path-km", "2",
                                "--out", out], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
            self.assertEqual(p.returncode, 0, p.stderr)
            with open(out, encoding="utf-8") as fh:
                head = fh.read()
            self.assertIn("Fried parameter r0 = %.4g cm" % res["r0_cm"], head)
            self.assertIn("path-averaged Cn2", head)
        self.assertTrue(math.isfinite(res["D_over_r0"]))


if __name__ == "__main__":
    unittest.main()
