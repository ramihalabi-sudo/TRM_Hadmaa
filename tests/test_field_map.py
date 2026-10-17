"""Acceptance tests of the field map v1.1 (TRM_Imaging_Research_Engineering_Field_Map_HE_v1_1.pdf).

Test IDs follow the document: V-01..V-08 (Appendix C), the software checks of Sec. 13.2 and the
per-panel acceptance tests of Sec. 15.2 (CP-01, GE-01, BI-01, OP-01..03, DG-01, DS-01..03, SP-01,
DO-01, ST-01..03, TS-01, IR-01, AT-01..03).
"""
import copy
import json
import math
import unittest

import numpy as np

from _common import LWIR, UNCOOLED, VIS, template, setup_model, as_file, run_project, ranges
from trm4 import derived as DV
from trm4 import imports as IM
from trm4 import physics as PH
from trm4 import presets as P
from trm4 import profiles as PR
from trm4 import scenario as SC
from trm4.model import ModelError, ModelCoverageError, check_coverage, run_id, TRM4Model


def mtf_model(project):
    """Model set up up to the MTFs (no AMOP / range run)."""
    m = setup_model(project)
    m._setup_weights(0.0)
    m._setup_mtf()
    return m


def lens_file(unit_line="Spatial frequency in cycles per mm", f_max=50.0, n=26, scale=1.0):
    f = np.linspace(0, f_max, n) * scale
    m = (1 - np.linspace(0, 1, n)) ** 2
    head = [unit_line] if unit_line else []
    return as_file("lens.csv", head + ["Field: 0.0000 deg", "Spatial frequency  Tangential  Sagittal"] +
                   ["%.5f %.6f %.6f" % (a, b, b) for a, b in zip(f, m)]), f, m


def psd_file(f_lo=1.0, f_hi=2000.0, level=1.0, n=400):
    f = np.linspace(f_lo, f_hi, n)
    return as_file("psd.txt", ["f_Hz PSD"] + ["%.6g %.6g" % (a, level) for a in f])


class Optics(unittest.TestCase):
    """OP-01..OP-03, V-01, V-05, 13.2 no-double-counting and unit invariance."""

    def test_V01_diffraction_included_not_applied_again(self):
        fobj, f, mf = lens_file()
        r = f[:-1] * 100.0 / 1000.0
        for diff in ("spectral", "single"):            # the diffraction selector must not matter (13.2 #1)
            m = mtf_model(template(LWIR, optics__mtf_source="zemax", optics__zemax_mtf=fobj, optics__diffraction=diff,
                                   optics__mtf_incl_diffraction=True))
            np.testing.assert_allclose(m.mtf_opt(r, "h"), mf[:-1], atol=1e-4)
            self.assertIn("diffraction", m.mtf_cov)

    def test_OP01_diffraction_applied_once_when_not_in_data(self):
        fobj, f, mf = lens_file()
        m = mtf_model(template(LWIR, optics__mtf_source="zemax", optics__zemax_mtf=fobj,
                               optics__mtf_incl_diffraction=False))
        r = f[:-1] * 0.1
        rd, md = m.diff_tab["h"]
        expect = np.interp(r, rd, md) * mf[:-1]
        np.testing.assert_allclose(m.mtf_opt(r, "h"), expect, atol=2e-3)
        self.assertNotIn("diffraction", m.mtf_cov)
        cov = m._coverage()
        self.assertTrue(any(c["components"] == {"diffraction"} for c in cov))

    def test_V05_mtf_without_unit_is_rejected(self):
        fobj, _f, _m = lens_file(unit_line=None)
        with self.assertRaises(ModelError) as cm:
            mtf_model(template(LWIR, optics__mtf_source="zemax", optics__zemax_mtf=fobj, optics__zemax_mtf_unit="auto"))
        self.assertIn("unit", str(cm.exception))
        m = mtf_model(template(LWIR, optics__mtf_source="zemax", optics__zemax_mtf=fobj, optics__zemax_mtf_unit="mm"))
        self.assertEqual(m.mtf_mode, "B")

    def test_GE01_unit_invariance_mm_vs_mrad(self):
        f_mm = 100.0
        a, f, mf = lens_file()
        b, _f, _m = lens_file(unit_line="Spatial frequency in cycles per mrad", scale=f_mm / 1000.0)
        ma = mtf_model(template(LWIR, optics__mtf_source="zemax", optics__zemax_mtf=a))
        mb = mtf_model(template(LWIR, optics__mtf_source="zemax", optics__zemax_mtf=b))
        r = np.linspace(0, 4.5, 40)
        np.testing.assert_allclose(ma.mtf_opt(r, "h"), mb.mtf_opt(r, "h"), atol=1e-9)

    def test_OP02_lens_data_with_detector_bypass_detector_model(self):
        fobj, _f, _m = lens_file()
        m = mtf_model(template(LWIR, optics__mtf_source="measured", optics__zemax_mtf=fobj,
                               optics__mtf_incl_detector=True))
        np.testing.assert_allclose(m.mtf_det(np.linspace(0, 3, 10), "h"), 1.0)
        self.assertNotIn("Detector aperture model", " ".join(c["source"] for c in m._coverage()))

    def test_OP03_single_field_flagged(self):
        fobj, _f, _m = lens_file()
        m = mtf_model(template(LWIR, optics__mtf_source="zemax", optics__zemax_mtf=fobj))
        self.assertTrue(any("one field" in a for a in m.assumptions))

    def test_V08_trace_names_source_and_components(self):
        fobj, _f, _m = lens_file()
        m = mtf_model(template(LWIR, optics__mtf_source="measured", optics__zemax_mtf=fobj))
        cov = m._coverage()
        self.assertEqual(cov[0]["source"], "Measured lens MTF")
        self.assertEqual(cov[0]["file"], "lens.csv")
        self.assertEqual(cov[0]["components"], {"optics", "diffraction"})
        self.assertTrue(any(im["what"] == "Measured lens MTF" for im in m.imports))

    def test_coverage_overlap_is_rejected(self):
        with self.assertRaises(ModelCoverageError):
            check_coverage([{"source": "end-to-end SFR", "components": {"optics", "detector_aperture"}},
                            {"source": "detector model", "components": {"detector_aperture"}}])
        check_coverage([{"source": "a", "components": {"optics"}}, {"source": "b", "components": {"motion"}}])


class Geometry(unittest.TestCase):
    """V-02 / DG-01 / TS-01."""

    def test_V02_ifov_100_urad(self):
        p = template(LWIR, detector__pitch_h_um=10.0, detector__pitch_v_um=10.0, detector__a_h_um=10.0,
                     detector__a_v_um=10.0, optics__f_mm=100.0)
        m = setup_model(p)
        self.assertAlmostEqual(m.alpha_s["h"], 0.1, places=12)          # mrad = 100 urad
        rows = {r[1]: r[2] for r in DV.compute(p)[0]}
        self.assertEqual(rows["IFOV = p / f (sampling distance) h x v"], "100.0 x 100.0")

    def test_DG01_nyquist_forms_agree(self):
        p = template(LWIR, detector__pitch_h_um=10.0, detector__pitch_v_um=10.0, detector__a_h_um=10.0,
                     detector__a_v_um=10.0, optics__f_mm=100.0)
        rows = {r[1]: r[2] for r in DV.compute(p)[0]}
        self.assertEqual(rows["Nyquist 1 / (2 p) (focal plane) h x v"], "50.0 x 50.0")       # 1/(2*0.01 mm)
        self.assertEqual(rows["Angular Nyquist f / (2000 p) h x v"], "5.000 x 5.000")        # 100/(2000*0.01)
        self.assertAlmostEqual(setup_model(p).r_N["h"], 5.0, places=9)                     # f_angle = f_sensor f/1000

    def test_TS01_orientation_changes_target_not_optics(self):
        a = setup_model(template(LWIR, target__D_m=6.0, target__aspect="front"))
        b = setup_model(template(LWIR, target__D_m=6.0, target__aspect="side"))
        self.assertEqual(a.alpha_s, b.alpha_s)
        self.assertEqual(a.f, b.f)
        self.assertNotAlmostEqual(a.target_dims(0.0)[0], b.target_dims(0.0)[0])

    def test_geometry_monotonicity(self):
        m = setup_model(template(LWIR))
        px = [m.target_dims(0.0)[0] / (R * m.alpha_s["h"]) for R in (1.0, 2.0, 4.0)]
        self.assertTrue(px[0] > px[1] > px[2])                          # smaller angle -> fewer pixels


class Noise(unittest.TestCase):
    """V-04 / DS-01..DS-03 / 13.2 noise monotonicity."""

    def test_V04_more_noise_never_raises_cnr(self):
        out = []
        for rn in (5.0, 50.0, 500.0):
            m = setup_model(template(VIS, detector__noise_floor_e=rn, turbulence__on=False))
            s = m.signal_state(2.0, m.atms[0])
            out.append(s["eds"] / math.hypot(s["nes"], s["ies"]))
        self.assertTrue(out[0] >= out[1] >= out[2])
        self.assertGreater(out[0], out[2])

    def test_DS01_measured_netd_excludes_read_noise(self):
        netd = []
        for rn in (10.0, 5000.0):
            m = setup_model(template(LWIR, detector__noise_mode="measured", detector__netd_mK=25.0,
                                     detector__noise_floor_e=rn))
            netd.append(m.netd)
            self.assertIn("Measured camera NETD", m.noise_source)
        self.assertEqual(netd[0], netd[1])
        self.assertAlmostEqual(netd[0], 0.025)

    def test_DS02_partial_conditions_marked(self):
        m = setup_model(template(LWIR, detector__noise_mode="measured"))
        self.assertTrue(m.noise_quality.startswith("partial"))
        full = setup_model(template(LWIR, detector__noise_mode="measured", detector__netd_TB_K=300.0,
                                    detector__netd_F=2.0, detector__netd_tint_ms=0.2, detector__netd_nuc="2-pt NUC"))
        self.assertEqual(full.noise_quality, "documented test conditions")

    def test_DS03_condition_mismatch_flagged_not_converted(self):
        m = setup_model(template(LWIR, detector__noise_mode="measured", detector__netd_mK=25.0, detector__netd_F=4.0,
                                 detector__netd_frames=4))
        self.assertAlmostEqual(m.netd, 0.025)                         # used unchanged, no false precision
        self.assertTrue(any("F/4.00" in w for w in m.warnings))
        self.assertTrue(any("4-frame averaging" in w for w in m.warnings))

    def test_nps_whiteness(self):
        f = np.linspace(0, 5, 60)
        self.assertAlmostEqual(IM.nps_whiteness(f, np.ones_like(f), 3.33), 1.0)
        self.assertLess(IM.nps_whiteness(f, np.exp(-(f / 1.5) ** 2), 3.33), 0.5)


class Motion(unittest.TestCase):
    """V-03 / ST-01..ST-03 / BI-01."""

    def test_V03_zero_motion_is_identity(self):
        r = np.linspace(0, 5, 30)
        for over in ({"stab__lin_on": True, "stab__lin_h": 0.0, "stab__lin_v": 0.0},
                     {"stab__jitter_mode": "none", "stab__random_on": True, "stab__rand_h_mrad": 0.05},
                     {"stab__jitter_mode": "psd", "stab__psd_file": psd_file(level=0.0)}):
            m = mtf_model(template(LWIR, **over))
            np.testing.assert_allclose(m.mtf_stab(r, "h"), 1.0)

    def test_ST01_uniform_motion_is_sinc(self):
        w = 20.0                                                        # mrad/s
        m = mtf_model(template(LWIR, stab__lin_on=True, stab__lin_h=w, detector__tint_mode="direct",
                               detector__tint_ms=1.0, basic__frame_rate=50.0))
        t = m.t_exposure()
        self.assertAlmostEqual(t, 1e-3)
        r = np.linspace(0, 5, 20)
        K = m.n_frames
        expect = np.sinc(t * w * r) * PH.sinc_ratio(K, w * r / m.frame_rate)
        np.testing.assert_allclose(m.mtf_stab(r, "h"), expect, atol=1e-9)

    def test_ST02_psd_units_and_split(self):
        a = mtf_model(template(LWIR, stab__jitter_mode="psd", stab__psd_file=psd_file(level=1.0),
                               stab__psd_unit="urad2"))
        b = mtf_model(template(LWIR, stab__jitter_mode="psd", stab__psd_file=psd_file(level=1e-6),
                               stab__psd_unit="mrad2"))
        r = np.linspace(0, 4, 15)
        np.testing.assert_allclose(a.mtf_stab(r, "h"), b.mtf_stab(r, "h"), rtol=1e-9)
        s_i, s_f, s_t = IM.psd_sigmas(np.linspace(0.1, 1.0, 50), np.ones(50), 1e-3)      # slow motion
        self.assertGreater(s_f, 0.99 * s_t)                                              # -> frame-to-frame
        s_i, s_f, s_t = IM.psd_sigmas(np.linspace(5e3, 2e4, 200), np.ones(200), 1e-3)    # fast motion
        self.assertGreater(s_i, 0.95 * s_t)                                              # -> blur
        bad = as_file("bad.txt", ["f PSD", "1 1", "2 -1", "3 1"])
        with self.assertRaises(ModelError):
            mtf_model(template(LWIR, stab__jitter_mode="psd", stab__psd_file=bad)).mtf_stab(r, "h")

    def test_ST03_motion_in_imported_mtf_not_applied_twice(self):
        fobj, _f, _m = lens_file()
        m = mtf_model(template(LWIR, optics__mtf_source="device", optics__zemax_mtf=fobj, optics__mtf_incl_motion=True,
                               stab__random_on=True, stab__rand_h_mrad=0.05, stab__rand_v_mrad=0.05))
        np.testing.assert_allclose(m.mtf_stab(np.linspace(0, 3, 10), "h"), 1.0)
        m._coverage()
        self.assertTrue(any("contained in the imported MTF" in w for w in m.warnings))

    def test_BI01_exposure_changes_noise_and_motion_only(self):
        out = []
        for t in (0.1, 1.0):
            m = mtf_model(template(LWIR, detector__tint_mode="direct", detector__tint_ms=t, stab__lin_on=True,
                                   stab__lin_h=20.0))
            out.append((dict(m.alpha_s), dict(m.f), m.netd_calc, float(m.mtf_stab(np.array([3.0]), "h")[0])))
        self.assertEqual(out[0][0], out[1][0])
        self.assertEqual(out[0][1], out[1][1])
        self.assertNotAlmostEqual(out[0][2], out[1][2])
        self.assertGreater(out[0][3], out[1][3])                           # longer exposure -> more smear

    def test_rolling_shutter(self):
        with self.assertRaises(ModelError):
            setup_model(template(LWIR, basic__readout="rolling", basic__readout_ms=0.0))
        m = mtf_model(template(LWIR, basic__readout="rolling", basic__readout_ms=15.0, stab__lin_on=True,
                               stab__lin_h=30.0))
        m._motion_checks()
        self.assertTrue(any("Rolling shutter" in w for w in m.warnings))


class Processing(unittest.TestCase):
    """SP-01 and DO-01."""

    BOOST = {"dsp__filter_on": True, "dsp__h_coef": [1.6, -0.3, 0.0, 0.0, 0.0],
             "dsp__v_coef": [1.6, -0.3, 0.0, 0.0, 0.0]}

    def test_SP01_sharpening_not_credited_automatically(self):
        base = ranges(run_project(template(LWIR))[1])
        _m, res = run_project(template(LWIR, **self.BOOST))
        self.assertEqual(ranges(res), base)
        self.assertTrue(any("NOT credited" in w for w in res["warnings"]))
        _m, res_c = run_project(template(LWIR, dsp__credit_boost=True, **self.BOOST))
        self.assertNotEqual(ranges(res_c), base)

    def test_DO01_display_pitch_does_not_change_ifov(self):
        a = setup_model(template(LWIR, display__pitch_h_mm=0.27, display__pitch_v_mm=0.27))
        b = setup_model(template(LWIR, display__pitch_h_mm=0.5, display__pitch_v_mm=0.5))
        self.assertEqual(a.alpha_s, b.alpha_s)
        self.assertNotAlmostEqual(a.m_sys, b.m_sys)
        alg = mtf_model(template(LWIR, display__observer="algorithm"))
        r = np.linspace(0, 5, 10)
        np.testing.assert_allclose(alg.mtf_eye(r), 1.0)
        np.testing.assert_allclose(alg.mtf_display(r, "h"), 1.0)
        self.assertEqual(alg.n_int_frames, alg.fr_int)
        self.assertTrue(any("uncalibrated" in w for w in alg.warnings))


class Radiometry(unittest.TestCase):
    """V-07 / IR-01 / AT-01..AT-03."""

    def test_V07_path_radiance_changes_signal_not_mtf(self):
        out = []
        for fpr in (0.1, 1.0):
            atm = [P._atm(True, 0.3, V=10.0, F_PR=fpr), P._atm(False, 0.5), P._atm(False, 0.5)]
            m = mtf_model(template(VIS, turbulence__on=False, atmosphere__mode="extinction", atmosphere__atm=atm))
            fl = m.flux(3.0, m.atms[0])
            out.append((fl["radiance"]["L_path"], fl["jB"], m.pre_system(np.linspace(0, 5, 20), "h", 3.0)))
        self.assertGreater(out[1][0], out[0][0])
        self.assertGreater(out[1][1], out[0][1])
        np.testing.assert_allclose(out[0][2], out[1][2])

    def test_AT01_transmission_outside_unit_interval_rejected(self):
        with self.assertRaises(ValueError):
            IM.parse_spectral_atmosphere("lam tau\n8 0.5\n10 1.4\n12 0.6\n", 1.0)

    def test_AT03_r0_needs_reference_and_scales(self):
        p = template(VIS, turbulence__on=True, turbulence__cn2_mode="r0", turbulence__r0_cm=5.0,
                     turbulence__r0_lambda_um=0.55, turbulence__r0_L_km=2.0)
        m = mtf_model(p)
        r0 = m._turb_table(2.0)[2]                                     # at the peak wavelength
        self.assertAlmostEqual(r0, 0.05 * (m.lam_peak / 0.55) ** 1.2, places=9)
        self.assertAlmostEqual(m._turb_table(4.0)[2] / r0, 2.0 ** -0.6, places=9)
        bad = template(VIS, turbulence__on=True, turbulence__cn2_mode="r0", turbulence__r0_L_km=0.0)
        with self.assertRaises(ModelError):
            mtf_model(bad)._turb_table(2.0)

    def test_IR01_illumination_assumption_and_radiance_units(self):
        m = setup_model(template(VIS, turbulence__on=False))
        self.assertTrue(any("Illumination is specified at the target" in a for a in m.assumptions))
        rad = m.flux(1.0, m.atms[0])["radiance"]
        self.assertGreater(rad["L_T"], 0.0)
        self.assertGreater(rad["L_B"], 0.0)


class Traceability(unittest.TestCase):
    """CP-01 / V-06 / 13.2 auditability / AP-01 version line."""

    def test_CP01_profile_reload_reproducible_and_hash_tracks_files(self):
        fobj, _f, _m = lens_file()
        proj = template(LWIR, optics__mtf_source="zemax", optics__zemax_mtf=fobj)
        prof = PR.from_project(proj, "Test camera", calibration_date="2026-10-01")
        for k in ("profile_id", "schema_version", "channel", "source_id", "calibration_date", "files", "content_hash"):
            self.assertIn(k, prof)
        self.assertEqual(prof["channel"], "Thermal LWIR")
        self.assertIn("configs.Nominal.optics.zemax_mtf", prof["files"])
        a = PR.apply(P.make_template(LWIR), prof)
        b = PR.apply(P.make_template(LWIR), copy.deepcopy(prof))
        self.assertEqual(run_id(a), run_id(b))
        prof2 = copy.deepcopy(prof)
        prof2["configs"][0]["optics"]["zemax_mtf"]["text"] += "\n"
        PR.stamp(prof2)
        self.assertNotEqual(prof2["content_hash"], prof["content_hash"])

    def test_run_id(self):
        p = template(LWIR)
        self.assertEqual(run_id(p), run_id(copy.deepcopy(p)))
        q = template(LWIR)
        q["name"] = "other name"
        self.assertEqual(run_id(p), run_id(q))                          # the name is not a model input
        self.assertNotEqual(run_id(p), run_id(template(LWIR, optics__f_mm=101.0)))

    def test_V06_legacy_preset_unchanged(self):
        self.assertEqual(P.task_preset_values(P.make_template(LWIR)), (1.0, 3.0, 6.0))
        m = setup_model(template(LWIR))
        self.assertFalse(any("differ from the selected preset" in w for w in m.warnings))
        m = setup_model(template(LWIR, target__task_preset="sandia148"))
        self.assertTrue(any("differ from the selected preset" in w for w in m.warnings))

    def test_auditability_full_run(self):
        p = template(UNCOOLED)
        _m, res = run_project(p)
        pv = res["provenance"]
        for k in ("model_version", "validation_version", "run_id", "coverage", "imports", "key_inputs"):
            self.assertIn(k, pv)
        self.assertNotEqual(pv["model_version"], pv["validation_version"])
        comps = [c for s in pv["coverage"] for c in s["components"]]
        self.assertEqual(len(comps), len(set(comps)))                    # each component once
        db = res["dashboard"]
        for t in db["tasks"]:
            for k in ("pix_h", "cyc_nyq", "mtf_task", "cnr_task", "limiter"):
                self.assertIn(k, t)
        self.assertIn("Uncalibrated", db["calibration"])
        self.assertNotIn("P=90", json.dumps(SC.build(p, res), default=float))
        rec = SC.build(p, res)
        for k in ("sensor", "optical_transfer", "atmosphere", "noise", "motion", "target", "task", "trace"):
            self.assertIn(k, rec)
        json.dumps(rec, default=float, allow_nan=False)                 # strict JSON

    def test_lab_config_mismatch_flagged(self):
        p = template(LWIR, measured__netd_mK=30.0, measured__meta__config_id="NFOV")
        p["profile"] = {"name": "cam", "config": "WFOV"}
        _m, res = run_project(p)
        self.assertTrue(any("not transferred between zoom" in w for w in res["warnings"]))


if __name__ == "__main__":
    unittest.main()
