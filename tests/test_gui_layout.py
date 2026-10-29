"""Input layout of the roadmap's phase 2: documentation on its own page, one entry per pixel pair, active values
not hidden, and the counterparts of merged inputs in the derived-value panel.  The layout never changes the
calculation (template ranges: test_templates_reference)."""
import copy
import unittest

from _common import LWIR, MWIR, VIS, template
from trm4 import derived as DV
from trm4 import extensions as X
from trm4 import presets as P
from trm4.model import run_project

try:
    import tkinter                                                          # noqa: F401
except ImportError:                                                         # no Tk on this machine
    G = None
else:
    from trm4 import gui as G                                               # import errors must fail, not skip


def merged(name, **kw):
    return P.deep_merge(P.DEFAULT_PROJECT, template(name, **kw))


@unittest.skipIf(G is None, "GUI not importable")
class Pages(unittest.TestCase):
    def page(self, name):
        return [f.get("path") for n, fields in G.TABS if n == name for f in fields if f.get("path")]

    def test_documentation_on_the_metadata_page(self):
        meta = self.page("Metadata")
        doc = ["optics.mtf_meta", "optics.mtf_band", "atmosphere.meta.source", "atmosphere.meta.resolution",
               "detector.op_mode", "detector.netd_nuc", "basic.roi", "dsp.pl_order", "dsp.pl_version",
               "display.algo_roc", "target.scene_id"]
        for path in doc:
            self.assertIn(path, meta)
        engineering = [p for n, _f in G.TABS if n not in ("Metadata", "Validation data") for p in self.page(n)]
        self.assertFalse(set(doc) & set(engineering))
        self.assertIn("Metadata", G.ENGINEERING_PAGES)

    def test_each_input_on_one_page_only(self):
        # conditional variants of one input on the same page are allowed (e.g. spectral vs per-slot atmosphere)
        seen = {}
        for n, fields in G.TABS:
            for f in fields:
                if f.get("path"):
                    seen.setdefault(f["path"], set()).add(n)
        self.assertEqual({p: pages for p, pages in seen.items() if len(pages) > 1}, {})

    def visible(self, path, p, show_adv=False):
        for _n, fields in G.TABS:
            group = None
            for f in fields:
                if f["kind"] == "header":
                    group = f
                    continue
                if f.get("path") != path:
                    continue
                if not f["cond"](p):
                    return False
                level = f.get("level") or (group or {}).get("level", "base")
                return level == "base" or level == "adv" and (show_adv or group["active"](p)) or \
                    level == "legacy" and group["active"](p)
        raise KeyError(path)

    def test_active_values_are_not_hidden(self):
        p = merged(MWIR)
        self.assertEqual(p["detector"]["fpn_mode"], "estimate")
        self.assertTrue(self.visible("detector.fpn_fraction", p))       # estimated FPN acts on the ranges
        self.assertTrue(self.visible("display.snr_th", p))
        self.assertTrue(self.visible("detector.noise_floor_e", merged(VIS)))
        q = merged(VIS, detector__adc_mode="carriers")
        self.assertTrue(self.visible("detector.lsb_e", q))

    def test_checks_and_overrides_are_out_of_the_way(self):
        p = merged(MWIR)
        self.assertFalse(self.visible("basic.fov_h_deg", p))
        self.assertFalse(self.visible("detector.cte_h", p, show_adv=True))      # CCD transfer: legacy
        self.assertFalse(self.visible("display.neglect_eye", p, show_adv=True))  # field: no eye-less ranges
        self.assertTrue(self.visible("display.neglect_eye", merged(MWIR, mode__environment="lab"), show_adv=True))
        self.assertFalse(self.visible("target.D_m", p))
        self.assertTrue(self.visible("target.D_m", merged(MWIR, target__aspect="side")))

    def test_square_pixels(self):
        d = merged(LWIR)["detector"]
        self.assertTrue(G.square_pixels(d))
        d["pitch_v_um"] = d["pitch_h_um"] + 1.0
        self.assertFalse(G.square_pixels(d))
        p = merged(LWIR)
        p["detector"].update(square=True, pitch_h_um=12.0, a_h_um=11.0, pitch_v_um=17.0, a_v_um=16.0)
        G.apply_square(p)
        self.assertEqual((p["detector"]["pitch_v_um"], p["detector"]["a_v_um"]), (12.0, 11.0))
        q = merged(LWIR)
        q["detector"].update(square=False, pitch_v_um=20.0)
        self.assertEqual(G.apply_square(q)["detector"]["pitch_v_um"], 20.0)

    def test_phase3_inputs(self):
        # clutter and compression act on the ranges (extensions) and moved from 'Metadata' to the pages they act on
        self.assertIn("target.clutter", self.page("Target & scenario"))
        self.assertIn("dsp.comp_blur_px", self.page("Signal processing"))
        self.assertNotIn("dsp.pl_compression", self.page("Metadata"))
        p = merged(MWIR)
        self.assertFalse(self.visible("turbulence.on", p))                     # TRM4: no turbulence in Thermal
        self.assertTrue(self.visible("turbulence.thermal", p))
        self.assertTrue(self.visible("turbulence.on", merged(MWIR, turbulence__thermal=True)))
        self.assertFalse(self.visible("atmosphere.atm.0.rh_pct", p))
        w = merged(MWIR, atmosphere__mode="weather")
        self.assertTrue(self.visible("atmosphere.atm.0.rh_pct", w))
        self.assertFalse(self.visible("atmosphere.atm.0.sigma", w))
        self.assertFalse(self.visible("display.algo_cnr_min", merged(MWIR, display__observer="algorithm"), True))
        pot = merged(MWIR, display__observer="algorithm", display__algo_criterion="pot")
        self.assertTrue(self.visible("display.algo_cnr_min", pot, True))
        self.assertTrue(self.visible("target.tasks.0.pot", pot))
        self.assertFalse(self.visible("target.clutter_model", p))
        self.assertTrue(self.visible("target.clutter_model", merged(MWIR, target__clutter="high")))

    def test_turbulence_stage_b_inputs(self):
        # engine 2.10: the new turbulence inputs sit on the turbulence page and appear only in their mode
        page = self.page("Atmosphere & turbulence")
        for path in ("turbulence.aniso", "turbulence.wx_T_K", "turbulence.wx_rh_pct", "turbulence.wx_wind_ms",
                     "turbulence.wx_hour", "turbulence.wx_W", "turbulence.wx_calib"):
            self.assertIn(path, page)
        v = merged(VIS)
        self.assertTrue(self.visible("turbulence.aniso", v))
        self.assertFalse(self.visible("turbulence.wx_T_K", v))
        w = merged(VIS, turbulence__cn2_mode="weather")
        self.assertTrue(self.visible("turbulence.wx_W", w))
        self.assertTrue(self.visible("turbulence.time", w))                     # height exponent from 15 m
        self.assertFalse(self.visible("turbulence.cn2", w))
        self.assertFalse(self.visible("turbulence.cn2", merged(VIS, turbulence__cn2_mode="slc_night")))
        self.assertTrue(self.visible("turbulence.cn2", merged(VIS, turbulence__cn2_mode="brookner")))
        modes = [m for m, _l in G._BY_PATH["turbulence.cn2_mode"]["opts"]]
        for m in list(X.CN2_PROFILES) + ["weather", "hv", "height", "fixed", "r0"]:
            self.assertIn(m, modes)
        self.assertEqual([k for k, _l in G._BY_PATH["turbulence.wx_hour"]["opts"]], ["custom"] + list(X.SK_W_PRESETS))
        self.assertTrue(all("PROVISIONAL" in G._BY_PATH[p]["label"] for p in ("turbulence.wx_hour", "turbulence.wx_W")))
        self.assertTrue(callable(G.form_dialog) and callable(G.App.lab_r0))

    def test_scintillation_input(self):
        # engine 2.11: the scintillation diagnostic sits on the turbulence page and is shown with turbulence on
        self.assertIn("turbulence.scint", self.page("Atmosphere & turbulence"))
        self.assertTrue(self.visible("turbulence.scint", merged(VIS)))
        self.assertFalse(self.visible("turbulence.scint", merged(VIS, turbulence__on=False)))
        self.assertFalse(self.visible("turbulence.scint", merged(MWIR)))            # Thermal: turbulence extension
        self.assertTrue(self.visible("turbulence.scint", merged(MWIR, turbulence__thermal=True,
                                                                turbulence__on=True)))

    def test_square_flag_does_not_reach_the_ranges(self):
        p = template(LWIR)
        _m, r0 = run_project(copy.deepcopy(p))
        p["detector"]["square"] = not P.DEFAULT_PROJECT["detector"]["square"]
        _m, r1 = run_project(p)
        self.assertEqual([t["R0"] for t in r0["range"]["atm"][0]["tasks"]],
                         [t["R0"] for t in r1["range"]["atm"][0]["tasks"]])


class DerivedCounterparts(unittest.TestCase):
    def rows(self, p):
        rows, warns = DV.compute(p)
        return {l: v for _g, l, v, _u in rows}, warns

    def test_magnification_matches_the_engine(self):
        m, _res = run_project(template(MWIR))
        rows, _w = self.rows(merged(MWIR))
        self.assertAlmostEqual(float(rows["System magnification M (displayed image angle / object angle)"]), m.m_sys,
                               delta=0.01 * m.m_sys)
        self.assertAlmostEqual(float(rows["Eye MTF at the detector Nyquist frequency"]),
                               float(m.mtf_eye([m.r_N["v"]])[0]), places=2)

    def test_low_magnification_flagged(self):
        _r, warns = self.rows(merged(MWIR, display__distance_cm=400.0))
        self.assertTrue(any("eye MTF at the detector Nyquist" in w for w in warns))

    def test_visual_range_and_extinction(self):
        rows, _w = self.rows(merged(VIS))
        v = merged(VIS)["atmosphere"]["atm"][0]["V_km"]
        self.assertAlmostEqual(float(rows["Atm 1: extinction from the visual range (3.912 / V)"]), 3.912 / v, places=3)
        rows, _w = self.rows(merged(MWIR))
        self.assertFalse(any("visual range" in k for k in rows))               # no Koschmieder outside the visible

    def test_jitter_in_ifov_units(self):
        p = merged(MWIR, stab__jitter_mode="model", stab__random_on=True, stab__rand_h_mrad=0.05,
                   stab__rand_v_mrad=0.0)
        rows, warns = self.rows(p)
        self.assertIn("IFOV", rows["Random jitter h in IFOV units"])
        self.assertTrue(any("Random jitter h" in w for w in warns))             # 50 urad > 1/3 of the IFOV

    def test_throughput_and_dark_current(self):
        p = merged(VIS)
        rows, _w = self.rows(p)
        o = p["optics"]
        self.assertAlmostEqual(float(rows["Signal throughput tau_opt x tau_filter x QE scale"]),
                               o["tau_opt"] * o["tau_filter"] * p["detector"]["qe_scale"], places=3)
        self.assertIn("nA/cm2", rows["Dark current in datasheet units"])


if __name__ == "__main__":
    unittest.main()
