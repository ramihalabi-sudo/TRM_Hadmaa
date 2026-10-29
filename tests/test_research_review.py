"""Acceptance tests for "TRM4v3_Research_Improvements_English.pdf" (independent technical research review).

RR-xx ids follow the review's sections: 3.5 QE basis, 3.6/3.7/7.1 saturation capacity and well fill,
3.1/3.8 operating mode and timing, 4.3/7.3 exposure budget, 3.11 dark current vs temperature,
3.10/7.5 noise port, 3.3/7.4 MTF metadata, 3.18/7.6 atmosphere versioning, 3.20 outer scale,
3.24 preset lifecycle, 7.7 DRI context and the corrected SWIR worked example of Sec. 4.4.
"""
import copy
import math
import unittest

import numpy as np

from _common import P, LWIR, VIS, SWIR, UNCOOLED, TRM4Model, template, setup_model, run_project, ranges
from trm4 import mtf as M
from trm4.model import ModelError
from trm4 import scenario as S


def swir_worked_example(**det):
    """Sec. 4.4: L = 0.4 W/(m^2 sr um) over 1.2-1.7 um, F/2, transmission 0.80, 15 um pixel, QE 0.80, 1e6 e-."""
    p = template(SWIR, mode__environment="lab", optics__aperture="general", optics__F_general=2.0,
                 optics__tau_opt=0.8, optics__tau_filter=1.0,
                 irradiance__mode="single", irradiance__type="broadband", irradiance__spectrum="effective",
                 irradiance__geometry="extended", irradiance__E_eff=0.4 * math.pi * 0.5,
                 target__b_refl_mode="effective", target__b_refl=1.0, target__t_refl_mode="effective",
                 target__t_refl=1.0)
    p["detector"].update(a_h_um=15.0, a_v_um=15.0, pitch_h_um=15.0, pitch_v_um=15.0, qe_preset="Custom",
                         qe_custom="1.2 80\n1.7 80", qe_unit="percent", qe_scale=1.0, storage_e=1.0e6,
                         electron_gain=1.0, dark_A=0.0, tint_mode="direct", tint_ms=10.0)
    p["detector"].update(det)
    return p


class WorkedExample(unittest.TestCase):
    def test_rr44_photon_and_electron_rates(self):
        m = setup_model(swir_worked_example())
        r_ph = m.flux(0.0, None, qe=False)["jB_scene"] * m.A_det
        r_e = m.flux(0.0, None)["jB_scene"] * m.A_det
        self.assertAlmostEqual(r_ph / 5.15969e7, 1.0, delta=2e-3)        # spectrally integrated, not at 1.50 um
        self.assertAlmostEqual(r_e / 4.12775e7, 1.0, delta=2e-3)
        self.assertAlmostEqual(m.well_fill(m.flux(0.0, None)["jB"], 0.010), 41.28, delta=0.1)

    def test_rr44_time_for_70_percent_fill(self):
        m = setup_model(swir_worked_example(tint_mode="wellfill", wellfill_pct=70.0))
        self.assertAlmostEqual(m.t_int_for(m.flux(0.0, None)["jB"]) * 1e3, 16.96, delta=0.05)


class QEBasis(unittest.TestCase):
    def test_rr35_pixel_area_basis_removes_fill_factor(self):
        base = template(SWIR, detector__a_h_um=12.0, detector__a_v_um=12.0)
        act = setup_model(base)
        pix = setup_model(template(SWIR, detector__a_h_um=12.0, detector__a_v_um=12.0,
                                   detector__qe_basis="pixel_area"))
        self.assertAlmostEqual(act.fill_factor, 0.64, places=6)
        self.assertAlmostEqual(pix.A_det / act.A_det, 1 / 0.64, places=6)
        self.assertAlmostEqual(pix.A_active, act.A_active)

    def test_rr35_unspecified_is_trm_convention_and_flagged(self):
        p = template(SWIR, detector__a_h_um=12.0, detector__a_v_um=12.0)
        m, res = run_project(copy.deepcopy(p))
        p["detector"]["qe_basis"] = "active_area"
        _, res2 = run_project(p)
        self.assertEqual(ranges(res), ranges(res2))
        self.assertTrue(any("QE basis not stated" in a for a in res["assumptions"]))
        p["provenance"] = {"detector.qe_preset": "manufacturer"}
        p["detector"]["qe_basis"] = "unspecified"
        _, res3 = run_project(p)
        self.assertTrue(any("QE basis not stated" in w for w in res3["warnings"]))


class Capacity(unittest.TestCase):
    def test_rr36_camera_saturation_limits_wellfill_exposure(self):
        a = setup_model(template(LWIR))
        b = setup_model(template(LWIR, detector__sat_e=0.5e7))
        self.assertEqual(b.cap_limit, "camera saturation capacity (input-referred)")
        self.assertAlmostEqual(b.t_ref / a.t_ref, 0.5e7 / 1.5e7, places=6)
        self.assertTrue(b.cap_verified)
        self.assertFalse(a.cap_verified)

    def test_rr36_adc_full_scale_is_a_limit(self):
        m = setup_model(template(SWIR, detector__adc_bits=12, detector__lsb_e=60.0))
        self.assertAlmostEqual(m.n_use, 4096 * 60.0)
        self.assertIn("ADC", m.cap_limit)

    def test_rr36_unverified_capacity_warns_in_wellfill_mode(self):
        _, res = run_project(template(LWIR))
        self.assertTrue(any("Well fill uses" in w for w in res["warnings"]))
        _, res = run_project(template(LWIR, detector__cap_node="camera"))
        self.assertFalse(any("Well fill uses" in w for w in res["warnings"]))

    def test_rr312_no_full_well_model_for_microbolometer(self):
        m, res = run_project(template(UNCOOLED))
        self.assertIsNone(res["dashboard"]["exposure"])
        self.assertTrue(any("Microbolometer" in a for a in res["assumptions"]))


class TimingAndBudget(unittest.TestCase):
    def test_rr38_non_overlapping_readout_shortens_timing_limit(self):
        m = setup_model(template(SWIR, basic__exp_overlap=False, basic__readout_ms=5.0, basic__guard_ms=1.0))
        self.assertAlmostEqual(m.t_timing * 1e3, 1000 / 30 - 6.0, places=6)
        with self.assertRaises(ModelError):
            setup_model(template(SWIR, basic__exp_overlap=False, basic__readout_ms=40.0))

    def test_rr43_timing_violation_reported(self):
        _, res = run_project(template(SWIR, basic__exp_overlap=False, basic__readout_ms=10.0))
        ex = res["dashboard"]["exposure"]
        self.assertTrue(any("sensor timing limit" in v for v in ex["violations"]))

    def test_rr43_motion_limit(self):
        p = template(SWIR, stab__jitter_mode="model", stab__lin_on=True, stab__lin_h=2.0, stab__lin_v=0.0,
                     stab__smear_allow_px=0.5)
        m, res = run_project(p)
        ex = res["dashboard"]["exposure"]
        ifov = 15.0 / 150.0                                           # mrad
        lim = dict((n.split(" (")[0], t) for n, t in ex["limits"])
        self.assertAlmostEqual(lim["image motion"], 0.5 * ifov / 2.0, places=9)
        self.assertAlmostEqual(ex["smear_px"]["h"], 2.0 * 0.030 / ifov, places=6)
        self.assertTrue(any("smear" in v for v in ex["violations"]))

    def test_rr43_infeasible_and_snr(self):
        _, res = run_project(template(SWIR, basic__exp_min_ms=40.0))
        ex = res["dashboard"]["exposure"]
        self.assertFalse(ex["feasible"])
        self.assertTrue(any("infeasible" in w for w in res["warnings"]))
        _, res = run_project(template(SWIR, detector__snr_req=1e6))
        self.assertFalse(res["dashboard"]["exposure"]["feasible"])

    def test_rr37_brightest_pixel_checked(self):
        _, res = run_project(template(VIS))
        ex = res["dashboard"]["exposure"]
        self.assertGreater(ex["wellfill_bright"], 100)
        self.assertTrue(any("brightest pixel saturates" in w for w in res["warnings"]))
        _, res = run_project(template(VIS, detector__bright_refl=0.05))
        self.assertLess(res["dashboard"]["exposure"]["wellfill_bright"], 100)

    def test_rr_templates_unchanged_by_defaults(self):
        # new inputs at their defaults leave the TRM ranges unchanged (only checks and reports are added)
        p = template(SWIR)
        _, r0 = run_project(copy.deepcopy(p))
        p["detector"].update(qe_basis="active_area", fill_limit_pct=50.0, bright_refl=0.5)
        p["basic"].update(exp_max_ms=100.0)
        _, r1 = run_project(p)
        self.assertEqual(ranges(r0), ranges(r1))


class DetectorDetails(unittest.TestCase):
    def test_rr311_dark_current_table(self):
        tab = "250 1e-15\n270 1e-14\n290 1e-13"
        m = setup_model(template(SWIR, detector__dark_mode="table", detector__dark_table=tab,
                                 detector__T_sensor_K=280.0))
        self.assertAlmostEqual(m.dark_A, math.sqrt(1e-14 * 1e-13), delta=1e-18)   # log-linear
        m = setup_model(template(SWIR, detector__dark_mode="table", detector__dark_table=tab,
                                 detector__T_sensor_K=300.0))
        self.assertAlmostEqual(m.dark_A, 1e-13)
        self.assertTrue(any("outside the dark current table" in w for w in m.warnings))
        with self.assertRaises(ModelError):
            setup_model(template(SWIR, detector__dark_mode="table", detector__dark_table=tab))

    def test_rr31_digital_binning_adds_read_noise(self):
        kw = dict(basic__bin_h=2, basic__bin_v=2, detector__noise_floor_e=30.0, detector__lsb_e=0.0)
        ch = setup_model(template(SWIR, **kw))
        dg = setup_model(template(SWIR, basic__bin_kind="digital", **kw))
        n_ch, n_dg = ch.noise(0.0, 0.0, 1e-3), dg.noise(0.0, 0.0, 1e-3)
        self.assertAlmostEqual(n_dg ** 2 - n_ch ** 2, 3 * 30.0 ** 2, delta=1.0)

    def test_rr310_processed_netd_port_flagged(self):
        _, res = run_project(template(UNCOOLED, detector__noise_port="processed"))
        self.assertTrue(any("processed video output" in w for w in res["warnings"]))


class Metadata(unittest.TestCase):
    def test_rr324_preset_lifecycle_records(self):
        m, res = run_project(template(SWIR))
        recs = res["provenance"]["presets"]
        self.assertTrue(any(r["kind"] == "qe" and r["name"] == "InGaAs generic" for r in recs))
        self.assertTrue(all(r["version"] == P.PRESET_DATA_VERSION and r["uncertainty"] for r in recs))
        self.assertTrue(any(s == "Preset data in use (lifecycle)" for s, *_ in res["info"]))

    def test_rr318_atmosphere_versioning(self):
        p = template(SWIR, atmosphere__path_mode="import",
                     atmosphere__path_file={"name": "p.txt", "text": "# lambda[um] L\n0.9 0.001\n1.8 0.001"},
                     atmosphere__path_L_km=1.0)
        _, res = run_project(p)
        self.assertTrue(any("not fully versioned" in a for a in res["assumptions"]))

    def test_rr77_dri_context(self):
        _, res = run_project(template(LWIR))
        ctx = res["dashboard"]["context"]
        for k in ("task", "target", "operating_point", "scene", "mtf_source", "observer", "uncertainty",
                  "validation", "statement"):
            self.assertTrue(ctx.get(k), k)
        self.assertIn("QE basis", ctx["operating_point"])
        rec = S.build(template(LWIR), res)
        self.assertIn("exposure_budget", rec)
        self.assertEqual(rec["sensor"]["qe_basis"], "unspecified")


class OuterScale(unittest.TestCase):
    def test_rr320_von_karman_reduces_phase_structure(self):
        r = np.linspace(0, 5, 50)
        k = M.mtf_turbulence(r, 1.0, 0.05, 100.0, "long")
        v = M.mtf_turbulence(r, 1.0, 0.05, 100.0, "long", L0_m=10.0)
        self.assertTrue(np.all(v >= k - 1e-12))
        self.assertTrue(np.any(v > k + 1e-3))
        self.assertTrue(np.allclose(M.mtf_turbulence(r, 1.0, 0.05, 100.0, "long", 0.0), k))


if __name__ == "__main__":
    unittest.main()
