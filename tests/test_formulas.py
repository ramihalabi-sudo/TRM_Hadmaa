"""Engine 2.33 - every input field shows the step of the calculation it enters and its formula (trm4/formulas.py).

The texts are shown after the '?' help of a field, in the field card of the guide and in Help > How the range is
calculated.  The formulas quoted to the user are checked here against what the engine computes.
"""
import math
import re
import unittest

import numpy as np

from _common import LWIR, MWIR, VIS, run_project, setup_model, template
from trm4 import extensions as X
from trm4 import formulas as FO
from trm4 import guide_he as GH
from trm4 import mtf as M
from trm4.help_text import help_for

try:
    from trm4 import gui as G
except Exception:                                    # no display / Tk
    G = None


def form_paths():
    return sorted({f["path"] for _n, fields in G.ALL_PAGES for f in fields if f.get("path")})


class Coverage(unittest.TestCase):
    @unittest.skipIf(G is None, "GUI not importable")
    def test_every_form_field_has_a_step(self):
        missing = [p for p in form_paths() if FO.formula_for(p) is None]
        self.assertEqual(missing, [])

    @unittest.skipIf(G is None, "GUI not importable")
    def test_no_entry_for_a_field_that_does_not_exist(self):
        shown = {re.sub(r"\.\d+\.", ".N.", p) for p in form_paths()}
        stale = [k for k in FO.FIELD if not k.startswith("additional.") and k not in shown]
        self.assertEqual(stale, [])

    def test_entries_are_complete(self):
        for path, (stage, text) in FO.FIELD.items():
            with self.subTest(path=path):
                self.assertIn(stage, FO.STAGES)
                # a field that enters the calculation says how; documentation needs no formula
                self.assertTrue(text or stage == "doc")
                self.assertNotRegex(text, "[֐-׿]")              # formulas are written left to right
        for key, (en, he, desc, he_desc) in FO.STAGES.items():
            self.assertTrue(en and he and desc and he_desc, key)

    @unittest.skipIf(G is None, "GUI not importable")
    def test_fields_the_guide_calls_without_effect_do_not_claim_a_formula_step(self):
        # the guide marks a field with impact 0 as "not in the range": its step must not be one of the range chain
        chain = {"signal", "noise", "mtf_pre", "mtf_post", "threshold", "atmosphere"}
        # limits of the integration time act only when they bind (well-fill exposure), and the kind of a measured
        # curve only names what the file holds: the guide rates them 0, the engine does read them
        allowed = {"basic.exp_max_ms", "basic.exp_min_ms", "basic.exp_overlap", "basic.guard_ms", "basic.readout_ms",
                   "measured.fom_kind"}
        wrong = []
        for p in form_paths():
            e = GH.param(p)
            stage = FO.formula_for(p)[0]
            if e and e.get("impact") == 0 and stage in chain and re.sub(r"\.\d+\.", ".N.", p) not in allowed:
                wrong.append((p, stage))
        self.assertEqual(wrong, [])


class WhereItIsShown(unittest.TestCase):
    def test_help_of_a_field(self):
        text = help_for("optics.f_mm") + FO.help_addendum("optics.f_mm")
        self.assertIn("In the calculation - Step 1 - geometry and sampling", text)
        self.assertIn("IFOV = p / f", text)
        self.assertIn("exp(-sigma R)", FO.help_addendum("atmosphere.atm.1.sigma"))        # any atmosphere slot
        self.assertIn("Traceability only", FO.help_addendum("measured.meta.date"))
        self.assertEqual(FO.help_addendum("no.such.field"), "")

    def test_guide_card(self):
        blocks = GH.field_blocks("stab.rand_h_mrad", 0.02, template(MWIR))
        i = blocks.index(("h", "איך זה נכנס לחישוב"))
        self.assertIn("שלב 4", blocks[i + 1][1])
        self.assertEqual(blocks[i + 2], ("p", FO.FIELD["stab.rand_h_mrad"][1]))
        doc = GH.field_blocks("measured.meta.date", "", template(MWIR))
        j = doc.index(("h", "איך זה נכנס לחישוב"))
        self.assertIn("תיעוד", doc[j + 1][1])

    def test_additional_mtf_before_and_after_sampling(self):
        self.assertEqual(FO.formula_for("additional.pre_h_par")[0], "mtf_pre")
        self.assertEqual(FO.formula_for("additional.post_v_type")[0], "mtf_post")

    def test_chain_text(self):
        text = FO.chain_text()
        for key in ("geometry", "signal", "noise", "mtf_pre", "mtf_post", "threshold", "atmosphere", "criterion"):
            self.assertIn(FO.STAGES[key][0], text)
        self.assertIn("MTDP(r) = (pi / 2) SNR_th sqrt(Psi(r)) / AMOP(r)", text)


class FormulasMatchTheEngine(unittest.TestCase):
    """The numbers behind the formulas the user is shown."""

    def test_geometry(self):
        p = template(MWIR)
        m = setup_model(p)
        pitch, f = p["detector"]["pitch_h_um"], p["optics"]["f_mm"]
        self.assertAlmostEqual(m.alpha_s["h"], pitch / f, places=12)               # IFOV = p / f [mrad]
        self.assertAlmostEqual(m.r_N["h"], f / (2 * pitch), places=9)              # Nyquist = f / (2 p)
        # FOV = [(n - 1) p + a] / f (Eq. 3.11)
        self.assertAlmostEqual(m.fov["h"], ((p["detector"]["n_h"] - 1) * pitch + p["detector"]["a_h_um"]) / f, places=9)
        self.assertAlmostEqual(m.F_eff, f / p["optics"]["D_mm"], places=4)         # F = f / D

    def test_component_mtfs(self):
        r = np.array([0.5, 1.5, 3.0])
        sigma, ifov = 0.03, 0.075
        self.assertTrue(np.allclose(M.mtf_random_vibration(r, sigma), np.exp(-2 * np.pi ** 2 * sigma ** 2 * r ** 2)))
        # at Nyquist, r = 1 / (2 IFOV): exp[-4.93 (sigma / IFOV)^2]
        self.assertAlmostEqual(float(M.mtf_random_vibration(np.array([1 / (2 * ifov)]), sigma)[0]),
                               math.exp(-4.93 * (sigma / ifov) ** 2), places=3)
        D, lam = 50.0, 10.0
        x = lam * r / D
        diff = 2 / np.pi * (np.arccos(x) - x * np.sqrt(1 - x ** 2))
        self.assertTrue(np.allclose(M.DiffractionMTF(D, 0.0, 0.0, 0.0)(r, lam), diff, atol=2e-4))
        self.assertTrue(np.allclose(M.mtf_blur(r, 5.0, 100.0), np.exp(-2 * (np.pi * 5.0 * r / 100.0) ** 2)))
        self.assertTrue(np.allclose(M.mtf_eye(r, 1.2, 4.0), np.exp(-1.2 * r / 4.0)))

    def test_threshold_and_magnification(self):
        p = template(LWIR)
        m, _res = run_project(p)
        d = p["display"]
        # M_sys = n_v p_display / (FOV_v d): mm / (mrad x m)
        self.assertAlmostEqual(m.m_sys, m.n_fov["v"] * d["pitch_v_mm"] / (m.fov["v"] * d["distance_cm"] / 100.0),
                               places=9)
        rp, nes, ies = 2.0, m.netd, m.ietd
        a = m.amop_at(0.0, rp, "h")
        self.assertAlmostEqual(m.mdsp(0.0, rp, "h", nes, ies),
                               0.5 * math.pi * m.snr_th * math.sqrt(m.psi(rp, "h", nes, ies)) / a, places=12)
        self.assertAlmostEqual(m.n_int_frames, p["basic"]["frame_rate"] * d["t_eye_s"], places=9)

    def test_atmosphere_and_criterion(self):
        m = setup_model(template(MWIR))
        a = m.atms[0]
        self.assertAlmostEqual(a.tau(3.0), a.tau0 * math.exp(-a.sigma * 3.0), places=12)
        v = setup_model(template(VIS)).atms[0]
        self.assertAlmostEqual(v.sigma, 3.912 / 23.0, places=9)                      # sigma = 3.912 / V
        self.assertAlmostEqual(X.rain_extinction(1.0), 1.2924 / 4.343, places=4)
        self.assertAlmostEqual(X.ttpf_ratio(0.8), 1.45, delta=0.01)
        self.assertAlmostEqual(X.ttpf_ratio(0.9), 1.75, delta=0.01)
        self.assertAlmostEqual(X.horizon_km(1.0, 1.0), 2 * 3.86, places=9)

    def test_resolution_limited_range_follows_f_over_p(self):
        # R ~ f sqrt(W H) / (p N_task): the uncooled template is limited by the sampling
        from _common import UNCOOLED, ranges
        a = ranges(run_project(template(UNCOOLED))[1])["Identification"]
        b = ranges(run_project(template(UNCOOLED, optics__f_mm=55.0, optics__f_v_mm=55.0, optics__D_mm=55.0))[1])[
            "Identification"]
        self.assertAlmostEqual(b / a, 1.1, delta=0.03)


if __name__ == "__main__":
    unittest.main()
