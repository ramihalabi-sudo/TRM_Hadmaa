"""Range Improvement Advisor - test specification of the advisor research report (Appendix A, T-01 ... T-10)."""
import copy
import json
import unittest

from _common import MWIR, UNCOOLED, template
from trm4 import advisor as ADV
from trm4 import analysis as AN


class _Shared:
    adv = None

    @classmethod
    def advice(cls):
        if _Shared.adv is None:
            p = template(MWIR)
            _Shared.project = copy.deepcopy(p)
            _Shared.adv = ADV.advise(p, robustness=False)
            _Shared.after = p
        return _Shared.adv


class Advisor(unittest.TestCase):
    def test_T01_baseline_unchanged(self):
        adv = _Shared.advice()
        self.assertEqual(json.dumps(_Shared.after, sort_keys=True), json.dumps(_Shared.project, sort_keys=True))
        base, _w = AN.model_ranges(_Shared.project)
        for t, R in base.items():
            self.assertEqual(adv["base"][t], R)                 # same output as the engine without the advisor

    def test_T02_geometry(self):
        p = template(MWIR, optics__f_mm=200.0, detector__pitch_h_um=12.0, detector__pitch_v_um=12.0,
                     detector__a_h_um=11.0, detector__a_v_um=11.0)
        self.assertAlmostEqual(ADV.geometry(p)["ifov_urad"], 60.0, places=3)
        p["optics"]["f_mm"] = 250.0
        self.assertAlmostEqual(ADV.geometry(p)["ifov_urad"], 48.0, places=3)

    def test_T03_zero_reference_blocks_percent(self):
        self.assertEqual(ADV.gain(0.0, 1.2), (1.2, None))
        d, g = ADV.gain(4.30, 4.70)
        self.assertAlmostEqual(d, 0.40, places=9)
        self.assertAlmostEqual(g, 9.302, places=2)

    def test_T06_detector_change_is_not_model_supported(self):
        a = next(x for x in _Shared.advice()["actions"] if x["id"] == "detector_small_pitch")
        self.assertEqual(a["support"], "approx")
        self.assertTrue(any("Incomplete simulation" in n for n in a["notes"]))

    def test_T07_exposure_change_is_conditional(self):
        a = next(x for x in _Shared.advice()["actions"] if x["group"] == "exposure")
        self.assertEqual(a["kind"], "operational")
        self.assertTrue(any("Conditional" in n for n in a["notes"]))

    def test_T08_weather_is_a_scenario_not_an_improvement(self):
        adv = _Shared.advice()
        env = [a for a in adv["actions"] if a["kind"] == "environment"]
        self.assertTrue(env)
        self.assertTrue(all(a["rank"] is None for a in env))
        self.assertTrue(all(ADV.action_by_id(adv, i)["kind"] != "environment" for i in adv["top"]))

    def test_T09_fov_constraint(self):
        p = template(MWIR)
        fov = ADV.geometry(p)["fov_h_deg"]
        adv = ADV.advise(p, min_fov_deg=fov * 0.99, robustness=False)
        lens = next(a for a in adv["actions"] if a["id"] == "lens_long_sameF")
        self.assertIn("T-09", lens["constraint"])
        self.assertNotIn("lens_long_sameF", adv["top"])

    def test_T10_version_mismatch_blocks_comparison(self):
        self.assertFalse(ADV.comparable({"model_version": "a"}, {"model_version": "b"}))
        self.assertTrue(ADV.comparable({"model_version": "a"}, {"model_version": "a"}))

    def test_consistent_lens_change(self):
        a = next(x for x in _Shared.advice()["actions"] if x["id"] == "lens_long_sameF")
        b0 = _Shared.advice()["baseline"]["geometry"]
        self.assertAlmostEqual(a["geometry"]["F"], b0["F"], places=3)          # f and D move together
        self.assertAlmostEqual(a["geometry"]["f_mm"], 1.25 * b0["f_mm"], places=6)
        self.assertAlmostEqual(a["fov_ratio"], 0.8, delta=0.01)

    def test_more_pixels_do_not_change_ifov_or_range(self):
        a = next(x for x in _Shared.advice()["actions"] if x["id"] == "detector_more_pixels")
        self.assertTrue(a["no_effect"])
        self.assertGreater(a["fov_ratio"], 1.2)

    def test_top3_materially_different(self):
        adv = _Shared.advice()
        groups = [ADV.action_by_id(adv, i)["group"] for i in adv["top"]]
        self.assertEqual(len(groups), len(set(groups)))
        self.assertLessEqual(len(groups), 3)

    def test_bottleneck_and_measure_first(self):
        adv = _Shared.advice()
        self.assertEqual(set(adv["diagnosis"]), set(adv["tasks"]))
        self.assertTrue(all(d["tag"] == "bottleneck candidate" for d in adv["diagnosis"].values()))
        self.assertTrue(any(k == "Optical MTF" for k, _v in adv["measure_first"]))

    def test_measured_netd_noted(self):
        adv = ADV.advise(template(UNCOOLED), robustness=False)
        a = next(x for x in adv["actions"] if x["id"] == "aperture_up")
        self.assertEqual(a["support"], "approx")
        self.assertTrue(any("NETD" in n for n in a["notes"]))

    def test_report_and_csv(self):
        adv = _Shared.advice()
        text = "\n".join(ADV.format_text(adv))
        self.assertIn("Range Improvement Advisor", text)
        self.assertIn("advisory only", text)
        self.assertEqual(len(ADV.to_csv_rows(adv)), 6 + len(adv["actions"]))


if __name__ == "__main__":
    unittest.main()
