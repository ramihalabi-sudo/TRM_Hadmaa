"""Scope of the analyses: inputs of the uncertainty study, the atmosphere the analyses evaluate, and the advisor's
extended catalogue (display, fixed pattern noise) and sensitivities (criterion, observer, target, background)."""
import unittest

from _common import LWIR, MWIR, VIS, template
from trm4 import advisor as ADV
from trm4 import analysis as AN
from trm4.model import run_project


class UncertaintyInputs(unittest.TestCase):
    def paths(self, p):
        return [path for path, _l, _pct in AN.applicable_inputs(p)]

    def test_strong_inputs_offered(self):
        paths = self.paths(template(MWIR))
        for path in ("optics.D_mm", "detector.pitch_h_um", "target.tasks.0.lp", "target.tasks.2.lp",
                     "display.snr_th", "display.t_eye_s"):
            self.assertIn(path, paths)
        self.assertNotIn("optics.F_general", paths)

    def test_inputs_follow_the_configuration(self):
        p = template(MWIR, optics__aperture="general", mode__stream="still")
        paths = self.paths(p)
        self.assertIn("optics.F_general", paths)
        self.assertNotIn("optics.D_mm", paths)
        self.assertNotIn("display.t_eye_s", paths)                      # no eye integration on a still frame
        p = template(MWIR)
        p["target"]["tasks"][2]["on"] = False
        self.assertNotIn("target.tasks.2.lp", self.paths(p))

    def test_pitch_keeps_its_physical_group(self):
        p = template(LWIR)
        d0 = dict(p["detector"])
        AN._set_input(p, "detector.pitch_h_um", d0["pitch_h_um"] * 1.1)
        d = p["detector"]
        for k in ("pitch_v_um", "a_h_um", "a_v_um"):
            self.assertAlmostEqual(d[k], d0[k] * 1.1, places=9)

    def test_criterion_moves_only_its_task(self):
        p = template(LWIR)
        item = {"path": "target.tasks.1.lp", "label": "R", "pct": 20}
        u = AN.uncertainty(p, [item])
        c = u["rows"][0]["c"]
        self.assertLess(c["Recognition"], 0)
        self.assertEqual(c["Detection"], 0.0)
        self.assertEqual(c["Identification"], 0.0)


class AnalysisAtmosphere(unittest.TestCase):
    def test_default_is_first_active_slot(self):
        p = template(MWIR)
        self.assertEqual(AN.analysis_slot(p), 0)
        p["atmosphere"]["atm"][0]["on"] = False
        self.assertEqual(AN.analysis_slot(p), 1)
        # the extinction input then belongs to the slot that is evaluated (before: atm.0, without any effect)
        self.assertIn("atmosphere.atm.1.sigma", [x for x, _l, _p in AN.applicable_inputs(p)])

    def test_selected_atmosphere_is_evaluated(self):
        p = template(MWIR)
        _m, res = run_project(p)
        p["analysis_atm"] = 1
        r, _w = AN.model_ranges(p)
        self.assertEqual(r, AN.task_ranges(res["range"]["atm"][1]))
        self.assertNotEqual(r, AN.task_ranges(res["range"]["atm"][0]))
        p["analysis_atm"] = 2                                              # slot 3 is off -> first active slot
        self.assertEqual(AN.analysis_slot(p), 0)

    def test_settings_follow_a_new_slot(self):
        p = template(MWIR)
        p["uncertainty"] = {"inputs": {"atmosphere.atm.0.sigma": {"on": True, "pct": 40.0}}}
        p["analysis_atm"] = 1
        e = AN.uncertainty_settings(p)["inputs"]["atmosphere.atm.1.sigma"]
        self.assertTrue(e["on"])
        self.assertEqual(e["pct"], 40.0)
        self.assertIn("atm 2", e["label"])

    def test_weather_dependence_ignores_near_ties(self):
        base = {"atmosphere": "A1", "atm_ranges": [("A1", {}), ("A2", {})]}

        def act(aid, g1, g2):
            return {"id": aid, "label": aid, "no_effect": False,
                    "by_atm": [("A1", {"I": g1}), ("A2", {"I": g2})]}
        tie = ADV._best_by_atmosphere([act("a", 25.8, 21.5), act("b", 24.8, 23.8)], base, "I")
        self.assertEqual([r["action"] for r in tie["rows"]], ["a", "b"])
        self.assertFalse(tie["depends"])
        flip = ADV._best_by_atmosphere([act("a", 25.0, 5.0), act("b", 20.0, 18.0)], base, "I")
        self.assertTrue(flip["depends"])


class AdvisorScope(unittest.TestCase):
    def test_display_and_fpn_actions(self):
        acts = {a["id"]: a for a in ADV.catalogue(template(MWIR))}
        self.assertEqual(acts["display_magnification"]["kind"], "operational")
        self.assertEqual(acts["display_magnification"]["changes"][0][0], "display.distance_cm")
        self.assertEqual(acts["fpn_lower"]["changes"][0][0], "detector.fpn_fraction")
        self.assertEqual(acts["fpn_lower"]["support"], "approx")            # the FPN is an estimate
        eyep = {a["id"]: a for a in ADV.catalogue(template(MWIR, display__observation="eyepiece"))}
        self.assertEqual(eyep["display_magnification"]["changes"][0][0], "display.f_eyepiece_mm")
        algo = {a["id"] for a in ADV.catalogue(template(MWIR, display__observer="algorithm"))}
        self.assertNotIn("display_magnification", algo)

    def test_assumption_sensitivities(self):
        import copy
        from trm4 import presets as P
        p = P.deep_merge(P.DEFAULT_PROJECT, template(MWIR))
        paths = [x for x, _l, _pol in ADV.sensitivity_params(p)]
        for path in ("target.W_m", "target.T_bg_K", "target.tasks.0.lp", "display.snr_th", "detector.fpn_fraction"):
            self.assertIn(path, paths)
        self.assertNotIn("atmosphere.atm.0.F_PR", paths)                 # path radiance is not used in Thermal
        v = P.deep_merge(P.DEFAULT_PROJECT, copy.deepcopy(template(VIS)))
        self.assertIn("atmosphere.atm.0.F_PR", [x for x, _l, _pol in ADV.sensitivity_params(v)])

    def test_measure_first_names_criterion_and_observer(self):
        keys = [k for k, _v in ADV.measure_first(template(MWIR), {})]
        self.assertIn("Task criterion", keys)
        self.assertIn("Observer", keys)


class SweepList(unittest.TestCase):
    def test_excluded_fields_do_not_change_the_ranges(self):
        for name in (MWIR, VIS):
            p = template(name, turbulence__on=False)
            base = AN.model_ranges(p)[0]
            for path in sorted(AN.NO_RANGE_EFFECT):
                with self.subTest(template=name, path=path):
                    q = template(name, turbulence__on=False)
                    x0 = float(AN.get_path(q, path)) if AN.has_path(q, path) else 0.0
                    AN.set_path(q, path, x0 * 0.5 if x0 > 0 else 0.3)
                    self.assertEqual(AN.model_ranges(q)[0], base)

    def test_every_input_field_has_help(self):
        try:
            from trm4 import gui as G
        except Exception as e:                                             # no Tk on this machine
            self.skipTest("GUI not importable: %s" % e)
        from trm4 import help_text as HT
        missing = [f["path"] for _page, fields in G.TABS for f in fields
                   if f["kind"] not in ("header", "derived") and not HT.help_for(f["path"])]
        self.assertEqual(missing, [])


class TurbulenceDiagnostics(unittest.TestCase):
    def test_r0_aperture_and_blur_reported(self):
        _m, res = run_project(template(VIS, turbulence__on=True))
        rows = {r[1]: r[2] for r in res["info"]}
        d_r0 = next(v for k, v in rows.items() if k.startswith("Aperture / r0"))
        blur = rows["Turbulence blur lambda/r0 vs IFOV"]
        self.assertGreater(float(d_r0), 0)
        self.assertIn("IFOV", blur)


if __name__ == "__main__":
    unittest.main()
