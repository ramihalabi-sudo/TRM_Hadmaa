"""Turbulence / motion: zero motion adds no blur; non-zero jitter reduces detail as expected."""
import math
import unittest

import numpy as np

from _common import LWIR, VIS, template, setup_model, as_file, run_project


def jitter_file(amp_urad, freq_hz, rate=10000.0, dur=0.5):
    t = np.arange(int(rate * dur)) / rate
    x = amp_urad * np.sin(2 * math.pi * freq_hz * t)
    return as_file("jitter.txt", ["t h v"] + ["%.6f %.5f %.5f" % (a, b, b) for a, b in zip(t, x)])


class Motion(unittest.TestCase):
    def _mtf_model(self, **over):
        m = setup_model(template(LWIR, **over))
        m._setup_weights(0.0)
        m._setup_mtf()
        return m

    def test_zero_motion_no_blur(self):
        r = np.linspace(0, 6, 50)
        m = self._mtf_model()
        np.testing.assert_allclose(m.mtf_stab(r, "h"), 1.0)
        m = self._mtf_model(stab__jitter_mode="measured", stab__jitter_file=jitter_file(0.0, 100.0))
        np.testing.assert_allclose(m.mtf_stab(r, "h"), 1.0, atol=1e-9)

    def test_random_jitter_gaussian(self):
        m = self._mtf_model(stab__random_on=True, stab__rand_h_mrad=0.05, stab__rand_v_mrad=0.05)
        rN = m.r_N["h"]
        self.assertAlmostEqual(float(m.mtf_stab(np.array([rN]), "h")[0]),
                               math.exp(-2 * math.pi ** 2 * 0.05 ** 2 * rN ** 2), places=12)

    def test_measured_jitter_reduces_detail(self):
        m = self._mtf_model(stab__jitter_mode="measured", stab__jitter_file=jitter_file(50.0, 400.0))
        rN = m.r_N["h"]
        v = float(m.mtf_stab(np.array([rN]), "h")[0])
        self.assertLess(v, 0.95)
        self.assertGreater(v, 0.0)
        _m, res = run_project(template(LWIR, stab__jitter_mode="measured", stab__jitter_file=jitter_file(50.0, 400.0)))
        base = run_project(template(LWIR))[1]
        self.assertLess(res["range"]["atm"][0]["tasks"][2]["R0"], base["range"]["atm"][0]["tasks"][2]["R0"])
        self.assertTrue(any("Jitter h" in r[1] for r in res["info"]))

    def test_turbulence_reduces_range(self):
        on = run_project(template(VIS))[1]
        off = run_project(template(VIS, turbulence__on=False))[1]
        self.assertLess(on["range"]["atm"][0]["tasks"][2]["R0"], off["range"]["atm"][0]["tasks"][2]["R0"])


if __name__ == "__main__":
    unittest.main()
