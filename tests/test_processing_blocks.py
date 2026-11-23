"""Engine 2.34 - processing blocks (reports/TRM_Hadmaa_Field_Effects_and_Upgrades_HE_2026-11-23.pdf, U12 and U14).

U12  electronic image stabilization removes the frame-to-frame jitter of measured / PSD motion; the documented
     denoising flag points to the existing inputs that describe it.
U14  range-dependent noise: in the Thermal category the background flux does not depend on the range (target,
     background and air are blackbodies at one temperature), so the NETD of zero range is the NETD at every range -
     nothing to add.  The General category already evaluates the noise at every range.
"""
import unittest

import numpy as np

from _common import GENERAL, LWIR, MWIR, as_file, ranges, run_project, setup_model, template
from trm4.model import TRM4Model


def psd_file(level=2000.0):
    """Line-of-sight PSD level / f^2 [urad^2/Hz] from 1 Hz to 2 kHz: about 45 urad rms, most of it slow motion
    (frame to frame), a little of it fast (blur within the exposure)."""
    f = np.logspace(0, np.log10(2000.0), 120)
    return as_file("psd.txt", ["f PSD_h PSD_v"] + ["%.6g %.6g %.6g" % (x, level / x ** 2, level / x ** 2) for x in f])


def jitter_file(amp_urad=60.0, freq_hz=7.0, rate=5000.0, dur=1.0):
    t = np.arange(0, dur, 1.0 / rate)
    x = amp_urad * np.sin(2 * np.pi * freq_hz * t)
    return as_file("jitter.txt", ["t h v"] + ["%.6f %.5f %.5f" % (a, b, b) for a, b in zip(t, x)])


class ElectronicStabilization(unittest.TestCase):
    def mtf(self, **over):
        m = TRM4Model(template(MWIR, **over))
        m.run()
        return m

    def test_psd_motion(self):
        base = dict(stab__jitter_mode="psd", stab__psd_file=psd_file(), stab__psd_unit="urad2")
        off, on = self.mtf(**base), self.mtf(stab__eis=True, **base)
        r = np.linspace(0.2, 6.0, 12)
        self.assertTrue(np.all(on.mtf_stab(r, "h") >= off.mtf_stab(r, "h") - 1e-12))
        self.assertGreater(on.mtf_stab(r, "h")[-1], 1.05 * off.mtf_stab(r, "h")[-1])
        s_i, s_f, _s_t = on.psd_stats("h")
        # with stabilization only the blur within the exposure is left
        np.testing.assert_allclose(on.mtf_stab(r, "h"), np.exp(-2 * np.pi ** 2 * s_i ** 2 * r ** 2), rtol=1e-9)
        self.assertGreater(s_f, 0.0)
        self.assertTrue(any(a.startswith("Electronic image stabilization") for a in on.assumptions))
        self.assertFalse(any(a.startswith("Electronic image stabilization") for a in off.assumptions))

    def test_ranges_never_shorter(self):
        base = dict(stab__jitter_mode="psd", stab__psd_file=psd_file(), stab__psd_unit="urad2")
        a = ranges(run_project(template(MWIR, **base))[1])
        b = ranges(run_project(template(MWIR, stab__eis=True, **base))[1])
        for k in a:
            self.assertGreaterEqual(b[k], a[k] * (1 - 1e-9))
        self.assertGreater(b["Identification"], 1.02 * a["Identification"])

    def test_measured_time_series(self):
        base = dict(stab__jitter_mode="measured", stab__jitter_file=jitter_file())
        off, on = self.mtf(**base), self.mtf(stab__eis=True, **base)
        r = np.linspace(0.5, 6.0, 8)
        self.assertTrue(np.all(on.mtf_stab(r, "h") >= off.mtf_stab(r, "h") - 1e-12))
        self.assertGreater(on.mtf_stab(r, "h")[-1], off.mtf_stab(r, "h")[-1])

    def test_no_effect_on_the_vibration_model_or_a_still_frame(self):
        vib = dict(stab__random_on=True, stab__rand_h_mrad=0.03, stab__rand_v_mrad=0.03)
        self.assertEqual(ranges(run_project(template(MWIR, **vib))[1]),
                         ranges(run_project(template(MWIR, stab__eis=True, **vib))[1]))
        still = dict(stab__jitter_mode="psd", stab__psd_file=psd_file(), mode__stream="still")
        self.assertEqual(ranges(run_project(template(MWIR, **still))[1]),
                         ranges(run_project(template(MWIR, stab__eis=True, **still))[1]))


class DocumentedProcessing(unittest.TestCase):
    def test_denoising_points_to_the_inputs_that_describe_it(self):
        m, _res = run_project(template(LWIR, dsp__pl_denoise=True))
        note = [a for a in m.assumptions if a.startswith("Processing not modelled")]
        self.assertEqual(len(note), 1)
        self.assertIn("frame integration", note[0])
        self.assertIn("digital filter", note[0])
        # the flag itself still changes nothing
        self.assertEqual(ranges(run_project(template(LWIR))[1]),
                         ranges(run_project(template(LWIR, dsp__pl_denoise=True))[1]))


class RangeDependentNoise(unittest.TestCase):
    def test_thermal_background_flux_does_not_depend_on_the_range(self):
        m = setup_model(template(MWIR))
        for atm in m.atms:
            for R in (0.5, 2.0, 10.0, 30.0):
                self.assertAlmostEqual(m.flux(R, atm)["jB"] / m.lab_flux["jB"], 1.0, places=9)

    def test_general_category_evaluates_the_noise_at_every_range(self):
        m = setup_model(template(GENERAL))
        near, far = m.signal_state(0.5, m.atms[0]), m.signal_state(15.0, m.atms[0])
        self.assertNotAlmostEqual(near["flux"]["jB"], far["flux"]["jB"], delta=1e-6 * near["flux"]["jB"])


if __name__ == "__main__":
    unittest.main()
