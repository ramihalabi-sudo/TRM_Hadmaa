"""Engine 2.37 - the partly implemented items of the upgrade report, extended as far as readable sources allow.

Search      systematic stepping of the field of regard: tau_FOR = (2 - Ps) / (2 Ps) (N - 1) t0 + tau_FOV,
            Ps = 1 - e^(-t0 / tau_FOV) (Friedman, Mark & Skirlo, Opt. Eng. 58(9) 093103 (2019), Eq. 4).
Contrast    the AGC span is 2 x the scene contrast temperature of the TTP metric, and with automatic gain it follows
            the scene through the atmosphere - the "apparent SCT" (Jordan, MSc thesis, University of Arizona 2024,
            quoting Vollmerhausen & Jacobs).
EIS         linear interpolation of the registered frames (derived, checked here on simulated shifts) and the crop
            margin of the field of view.
Denoising   the recursive temporal filter is the TRM4 IIR filter (Eq. 3.141); its help text and guide check had the
            weight the wrong way round.

All of it is off by default: the template ranges do not change.
"""
import math
import unittest

import numpy as np

from _common import LWIR, MWIR, ranges, run_project, template
from test_processing_blocks import psd_file
from trm4 import extensions as X
from trm4 import guide_kb_he as KB
from trm4.help_text import HELP
from trm4.model import ModelError, TRM4Model


class SystematicSearch(unittest.TestCase):
    KW = dict(target__search=True, target__search_time_s=120.0, target__search_tau_s=3.0,
              target__search_for_h_deg=30.0, target__search_for_v_deg=10.0)

    def test_formula(self):
        tau, n, t0 = 3.0, 50.0, 3.0
        ps = 1.0 - math.exp(-t0 / tau)
        want = (2.0 - ps) / (2.0 * ps) * (n - 1.0) * t0 + tau
        self.assertAlmostEqual(X.search_tau_for(tau, n, "systematic", t0), want, places=12)
        self.assertAlmostEqual(X.search_tau_for(tau, n), n * tau)
        # one field of view: no stepping, the acquisition time of the field of view itself
        self.assertAlmostEqual(X.search_tau_for(tau, 1.0, "systematic", t0), tau)
        # a very short stay tends to the random-search value N tau
        self.assertAlmostEqual(X.search_tau_for(tau, n, "systematic", 1e-6) / (n * tau), 1.0, places=4)

    def test_longer_stay_takes_longer(self):
        t = [X.search_tau_for(3.0, 50.0, "systematic", d) for d in (0.5, 1.0, 3.0, 6.0)]
        self.assertEqual(t, sorted(t))

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            X.search_tau_for(3.0, 10.0, "systematic", 0.0)
        with self.assertRaises(ValueError):
            X.search_tau_for(3.0, 10.0, "spiral", 1.0)
        with self.assertRaises(ModelError):
            run_project(template(MWIR, target__search_mode="systematic", **self.KW))

    def test_in_the_model(self):
        _m, a = run_project(template(MWIR, **self.KW))
        _m, b = run_project(template(MWIR, target__search_mode="systematic", target__search_dwell_s=3.0, **self.KW))
        sa, sb = (r["range"]["atm"][0]["tasks"][0]["search"] for r in (a, b))
        self.assertEqual(sa["mode"], "random")
        self.assertAlmostEqual(sa["tau_for_s"], sa["n_fov"] * 3.0)
        self.assertAlmostEqual(sb["tau_for_s"], X.search_tau_for(3.0, sb["n_fov"], "systematic", 3.0))
        self.assertLess(sb["R0"], sa["R0"])
        self.assertEqual(ranges(a), ranges(b))
        self.assertTrue(any("stepped systematically" in x for x in b["assumptions"]))


class SceneFollowingSpan(unittest.TestCase):
    def run_mode(self, mode, **over):
        return run_project(template(LWIR, display__contrast_limit=True, display__contrast_span_mode=mode, **over))[1]

    def test_fixed_is_the_default_and_unchanged(self):
        _m, res = run_project(template(LWIR, display__contrast_limit=True))
        self.assertEqual(ranges(res), ranges(self.run_mode("fixed")))

    def test_scene_lies_between_fixed_and_no_limit(self):
        base = run_project(template(LWIR))[1]
        fixed, scene = self.run_mode("fixed"), self.run_mode("scene")
        for atm in (0, 1):
            b, f, s = ranges(base, atm), ranges(fixed, atm), ranges(scene, atm)
            for task in b:
                self.assertLessEqual(f[task], s[task] + 1e-9, "%s atm %d" % (task, atm))
                self.assertLessEqual(s[task], b[task] + 1e-9, "%s atm %d" % (task, atm))
            self.assertGreater(s["Detection"], f["Detection"])

    def test_with_thermal_turbulence(self):
        tb = dict(turbulence__on=True, turbulence__thermal=True, turbulence__cn2=1e-14)
        f, s = ranges(self.run_mode("fixed", **tb)), ranges(self.run_mode("scene", **tb))
        self.assertGreater(s["Detection"], f["Detection"])

    def test_reported_and_validated(self):
        res = self.run_mode("scene")
        self.assertTrue(any("apparent scene contrast" in a and "scene contrast temperature" in a
                            for a in res["assumptions"]))
        with self.assertRaises(ModelError):
            self.run_mode("auto")


class StabilizationInterpolation(unittest.TestCase):
    BASE = dict(stab__jitter_mode="psd", stab__psd_unit="urad2", stab__eis=True)

    def test_transfer_matches_simulated_shifts(self):
        n = 256
        x = np.arange(n)
        for k in (4, 40, 100, 128):
            sig = np.cos(2 * np.pi * k * x / n + 0.4) if k < n // 2 else np.cos(np.pi * x)
            amp = []
            for d in (np.arange(64) + 0.5) / 64.0:
                y = (1.0 - d) * sig + d * np.roll(sig, -1)
                amp.append(abs(np.fft.fft(y)[k]) / abs(np.fft.fft(sig)[k]))
            self.assertAlmostEqual(float(np.mean(amp)), float(X.shift_interp_mtf(k / n, 1.0)), places=9)

    def test_limits(self):
        self.assertAlmostEqual(float(X.shift_interp_mtf(0.0, 0.3)), 1.0)
        self.assertAlmostEqual(float(X.shift_interp_mtf(0.5 / 0.3, 0.3)), 0.5, places=3)

    def test_in_the_model(self):
        over = dict(self.BASE, stab__psd_file=psd_file())
        a = TRM4Model(template(MWIR, **over))
        a.run()
        b = TRM4Model(template(MWIR, stab__eis_interp="bilinear", **over))
        b.run()
        rn = a.r_N["h"]
        self.assertAlmostEqual(float(b.mtf_dig(rn, "h") / a.mtf_dig(rn, "h")), 0.5, places=3)
        ra, rb = ranges(run_project(template(MWIR, **over))[1]), \
            ranges(run_project(template(MWIR, stab__eis_interp="bilinear", **over))[1])
        for task in ra:
            self.assertLessEqual(rb[task], ra[task] + 1e-9)
        self.assertLess(rb["Identification"], ra["Identification"])

    def test_no_effect_without_stabilization(self):
        base = ranges(run_project(template(MWIR))[1])
        res = run_project(template(MWIR, stab__eis_interp="bilinear", stab__eis_crop_pct=10.0))[1]
        self.assertEqual(ranges(res), base)

    def test_crop_shrinks_the_field_of_view_for_the_search_only(self):
        over = dict(self.BASE, stab__psd_file=psd_file(), target__search=True, target__search_time_s=300.0,
                    target__search_tau_s=3.0, target__search_for_h_deg=30.0, target__search_for_v_deg=10.0)
        _m, a = run_project(template(MWIR, **over))
        _m, b = run_project(template(MWIR, stab__eis_crop_pct=10.0, **over))
        self.assertEqual(ranges(a), ranges(b))
        na, nb = (r["range"]["atm"][0]["tasks"][0]["search"]["n_fov"] for r in (a, b))
        self.assertAlmostEqual(nb / na, 1.0 / 0.81, places=6)
        self.assertTrue(any("after the stabilization crop" in row[1] for row in b["info"]))
        with self.assertRaises(ModelError):
            run_project(template(MWIR, stab__eis_crop_pct=95.0, **over))


class RecursiveFilterText(unittest.TestCase):
    """The engine follows TRM4 Eq. 3.141: equivalent frames = (1 + alpha) / (1 - alpha), alpha = feedback weight."""

    def test_engine(self):
        m = TRM4Model(template(MWIR, dsp__iir_on=True, dsp__iir_alpha=0.8))
        m.run()
        self.assertAlmostEqual(m.fr_int / m.n_frames, 9.0)

    def test_variance_of_a_simulated_filter(self):
        rng = np.random.default_rng(1)
        a, x, y, out = 0.8, rng.normal(size=200000), 0.0, []
        for v in x:
            y = (1.0 - a) * v + a * y
            out.append(y)
        self.assertAlmostEqual(1.0 / np.var(out[1000:]), (1.0 + a) / (1.0 - a), delta=0.3)

    def test_help_and_guide_agree_with_the_engine(self):
        self.assertIn("(1 + alpha) / (1 - alpha)", HELP["dsp.iir_alpha"])
        self.assertIn("Larger = stronger", HELP["dsp.iir_alpha"])
        out = KB._check_iir(0.8, {"dsp": {"iir_on": True}})
        self.assertEqual(out[0], "ok")
        self.assertIn("9.0", out[1])
        self.assertEqual(KB._check_iir(1.0, {"dsp": {"iir_on": True}})[0], "warn")


if __name__ == "__main__":
    unittest.main()
