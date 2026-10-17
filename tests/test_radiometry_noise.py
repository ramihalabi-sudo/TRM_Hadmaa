"""Radiometry / noise: synthetic signals reproduce shot, read, dark and quantization noise; clipping is flagged."""
import math
import unittest

from _common import VIS, LWIR, template, setup_model, run_project
from trm4 import physics as ph


class Noise(unittest.TestCase):
    def _model(self, **over):
        kw = dict(detector__dark_A=0.0, detector__noise_floor_e=0.0, detector__adc_mode="none")
        kw.update(over)
        return setup_model(template(VIS, **kw))

    def test_pure_shot_noise(self):
        m = self._model()
        j, t = 1e17, 1e-3                       # carriers / (s m^2), s
        N = j * m.A_det * t
        self.assertAlmostEqual(m.noise(j, j, t), math.sqrt(N), delta=1e-9 * math.sqrt(N))

    def test_read_noise_adds_in_quadrature(self):
        m = self._model(detector__noise_floor_e=20.0)
        j, t = 1e16, 1e-3
        N = j * m.A_det * t
        self.assertAlmostEqual(m.noise(j, j, t), math.sqrt(N + 400.0), places=6)

    def test_dark_current_shot_noise(self):
        m = self._model(detector__dark_A=1e-15)
        t = 0.01
        Nd = 1e-15 / ph.E_CHARGE * t
        self.assertAlmostEqual(m.noise(0.0, 0.0, t), math.sqrt(Nd), places=6)

    def test_quantization(self):
        m = self._model(detector__adc_mode="carriers", detector__lsb_e=12.0)
        self.assertAlmostEqual(m.noise(0.0, 0.0, 1e-3), 12.0 / math.sqrt(12), places=9)

    def test_saturation_flagged(self):
        _m, res = run_project(template(VIS, detector__tint_ms=20.0))
        self.assertTrue(any("Saturation" in w for w in res["warnings"]))

    def test_adc_clipping_flagged(self):
        _m, res = run_project(template(VIS, detector__adc_bits=8, detector__lsb_e=5.0))
        self.assertTrue(any("ADC clipping" in w for w in res["warnings"]))

    def test_netd_from_noise_and_responsivity(self):
        m = setup_model(template(LWIR))
        self.assertAlmostEqual(m.netd_calc, m.sigma_B / m.dndt, places=12)


if __name__ == "__main__":
    unittest.main()
