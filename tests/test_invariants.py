"""Physical invariants: a worse imager or scene never lengthens a range, and degenerate inputs fail cleanly."""
import math
import unittest

from _common import LWIR, MWIR, UNCOOLED, VIS, template, ranges, run_project
from trm4.model import ModelError

TOL = 1e-3          # relative tolerance for "not longer"


def _not_longer(test, seq, label):
    """Ranges of successive degradations must be non-increasing for every task."""
    for (x0, r0), (x1, r1) in zip(seq, seq[1:]):
        for task, v0 in r0.items():
            v1 = r1[task]
            with test.subTest(what=label, step="%s -> %s" % (x0, x1), task=task):
                test.assertIsNotNone(v0)
                test.assertIsNotNone(v1)
                test.assertLessEqual(v1, v0 * (1 + TOL))


class Invariants(unittest.TestCase):
    def test_zero_throughput_is_a_model_error(self):
        for over in ({"optics__tau_opt": 0.0}, {"detector__qe_scale": 0.0}, {"detector__electron_gain": 0.0}):
            with self.subTest(**over):
                with self.assertRaises(ModelError):
                    run_project(template(MWIR, **over))

    def test_more_linear_motion_never_lengthens_range(self):
        seq = []
        for w in (0.0, 10.0, 20.0, 35.0, 50.0, 80.0):
            p = template(MWIR, stab__lin_on=w > 0, stab__lin_h=w or 1.0, stab__lin_v=w or 1.0)
            seq.append((w, ranges(run_project(p)[1])))
        _not_longer(self, seq, "linear motion [mrad/s]")

    def test_motion_zero_limits_bar_frequency(self):
        m, res = run_project(template(MWIR, stab__lin_on=True, stab__lin_h=35.0, stab__lin_v=35.0))
        zc = m.r_motion_zero["h"]
        t = m.t_ref if m.t_ref else m.t_max
        self.assertAlmostEqual(zc, 1.0 / (t * 35.0), delta=0.01 * zc)           # first zero of sinc(t w r)
        self.assertEqual(m.amop_direct(0.0, 1.2 * zc, "h"), 0.0)
        self.assertTrue(any("motion MTF" in a for a in res["assumptions"]))

    def test_darker_display_never_lengthens_range(self):
        seq = [(L, ranges(run_project(template(UNCOOLED, display__luminance=L))[1])) for L in (100.0, 10.0, 2.0, 0.5)]
        _not_longer(self, seq, "display luminance [cd/m2]")

    def test_higher_netd_never_lengthens_range(self):
        seq = [(n, ranges(run_project(template(UNCOOLED, detector__netd_mK=n))[1])) for n in (15.0, 20.0, 30.0, 50.0)]
        _not_longer(self, seq, "NETD [mK]")

    def test_resolution_limit_is_refined(self):
        m, _res = run_project(template(LWIR))
        for z in "hv":
            rp, am = m.amop_tab[z]
            k = int((am <= 0.001).argmax())
            with self.subTest(z=z):
                self.assertGreater(k, 0)
                self.assertLess(rp[k] / rp[k - 1], 1.01)       # bracket much finer than the 8 % grid step

    def test_turbulence_keeps_detection_for_large_targets(self):
        _m, res = run_project(template(VIS, turbulence__on=True, target__W_m=20.0, target__H_m=20.0))
        r = ranges(res)
        self.assertTrue(all(v is not None and math.isfinite(v) and v > 1.0 for v in r.values()), r)
        self.assertGreaterEqual(r["Detection"], r["Identification"])


if __name__ == "__main__":
    unittest.main()
