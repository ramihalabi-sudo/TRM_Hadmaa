"""Consistency of inputs and outputs: physical bounds, one 'no range' convention, NIIRS independent of the DRI
ranges, Detector Atlas mapping, F lambda / d regime and flagged generic defaults."""
import unittest

from _common import LWIR, MWIR, VIS, template, ranges, run_project
from trm4 import analysis as AN
from trm4 import detector_atlas as DA
from trm4.model import ModelError, TRM4Model


class InputBounds(unittest.TestCase):
    def test_out_of_range_inputs_rejected(self):
        cases = [{"target__W_m": 0.0}, {"target__H_m": -1.0}, {"target__T_bg_K": 0.0}, {"display__snr_th": 0.0},
                 {"display__t_eye_s": 0.0}, {"optics__aberration": "q", "optics__q": 0.8},
                 {"detector__cte_on": True, "detector__cte_h": 1.2},
                 {"detector__tint_mode": "duty", "detector__duty": 1.5},
                 {"detector__tint_mode": "wellfill", "detector__wellfill_pct": 150.0}]
        for over in cases:
            with self.subTest(**over):
                with self.assertRaises(ModelError):
                    run_project(template(LWIR, **over))

    def test_negative_cn2_rejected(self):
        with self.assertRaises(ModelError):
            run_project(template(VIS, turbulence__on=True, turbulence__cn2=-1e-14))


class RangeSentinels(unittest.TestCase):
    def test_visible_without_signal_is_none(self):
        # equal target and background reflectivity: no task can be performed - reported like Thermal dT = 0
        _m, res = run_project(template(VIS, turbulence__on=False, target__t_refl_mode="effective", target__t_refl=0.3,
                                       target__b_refl_mode="effective", target__b_refl=0.3))
        self.assertTrue(all(v is None for v in ranges(res).values()), ranges(res))

    def test_one_mapping_for_analyses_and_advisor(self):
        a = {"R": [0.01, 1.0, 100.0], "tasks": [{"name": "D", "R0": None}, {"name": "R", "R0": float("inf")},
                                                 {"name": "I", "R0": 2.5}]}
        self.assertEqual(AN.task_ranges(a), {"D": 0.01, "R": 100.0, "I": 2.5})
        self.assertEqual(AN.task_ranges(a, below="zero"), {"D": 0.0, "R": 100.0, "I": 2.5})


class NiirsIndependent(unittest.TestCase):
    def test_niirs_does_not_change_dri(self):
        base = ranges(run_project(template(MWIR))[1])
        _m, res = run_project(template(MWIR, mode__niirs=True))
        self.assertEqual(ranges(res), base)
        self.assertEqual(res["provenance"]["stream"], "video")


class AtlasMapping(unittest.TestCase):
    REC = {"band": "MWIR", "technology": "InSb", "cooling_class": "cryogenic", "width": 1280, "height": 1024,
           "pitch_um": 10, "max_fps": 120, "fpa_operating_k": 77}

    def test_fpa_temperature_is_not_cold_shield(self):
        paths = {s[1]: s[4] for s in DA.suggestions(self.REC)}
        self.assertNotIn("detector.T_cs_K", paths)
        self.assertEqual(paths["detector.T_sensor_K"], 77)

    def test_active_size_follows_pitch(self):
        paths = {s[1]: s[4] for s in DA.suggestions(self.REC)}
        self.assertEqual(paths["detector.a_h_um"], 10)
        self.assertEqual(paths["detector.a_v_um"], 10)

    def test_max_frame_rate_not_ticked(self):
        self.assertIn("basic.frame_rate", DA.NOT_TICKED)


class Indicators(unittest.TestCase):
    def test_fld_regime(self):
        self.assertTrue(TRM4Model.fld_regime(0.6)["regime"].startswith("detector"))
        self.assertTrue(TRM4Model.fld_regime(1.5)["regime"].startswith("balanced"))
        self.assertTrue(TRM4Model.fld_regime(2.5)["regime"].startswith("optics"))
        m, res = run_project(template(LWIR))
        fl = res["dashboard"]["fld"]
        self.assertAlmostEqual(fl["value"], m.F_eff * fl["lambda_um"] / fl["pitch_um"], places=9)
        self.assertTrue(8.0 < fl["lambda_um"] < 12.0)                     # band-weighted, inside the LWIR band

    def test_single_wavelength_diffraction_defaults_to_band_mean(self):
        m, res = run_project(template(VIS, turbulence__on=False, optics__diffraction="single", optics__lambda_diff_um=0.0))
        note = [a for a in res["assumptions"] if "signal-weighted mean wavelength" in a]
        self.assertEqual(len(note), 1)
        lam0 = float(note[0].rsplit("wavelength ", 1)[1].split(" um")[0])
        self.assertTrue(m.band[0] <= lam0 <= m.band[1], (lam0, m.band))
        self.assertFalse(any("outside the imager spectral band" in w for w in res["warnings"]))

    def test_generic_read_noise_is_flagged(self):
        _m, res = run_project(template(LWIR, detector__noise_floor_e=500.0))
        self.assertTrue(any("generic default" in a for a in res["assumptions"]))
        _m, res = run_project(template(LWIR, detector__noise_floor_e=500.0,
                                       provenance={"detector.noise_floor_e": "manufacturer"}))
        self.assertFalse(any("Read noise" in a and "generic default" in a for a in res["assumptions"]))

    def test_uncertainty_step_stays_in_valid_interval(self):
        # tau = 1: the +5 % step is clipped to 1, the derivative uses the actual one-sided step
        lin = lambda p: {"D": 10.0 * p["optics"]["tau_opt"]}
        item = {"path": "optics.tau_opt", "label": "tau", "pct": 10, "meaning": "bound", "dist": "normal"}
        u = AN.uncertainty({"optics": {"tau_opt": 1.0}}, [item], evaluate=lin)
        self.assertAlmostEqual(u["rows"][0]["c"]["D"], 10.0, places=9)
        self.assertEqual(u["settings"]["deriv_step_pct"], 5.0)


if __name__ == "__main__":
    unittest.main()
