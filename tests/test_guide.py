"""Interactive Hebrew guide: the knowledge base covers every field of the parameter form, value checks catch the
common input mistakes and suggest the corrected value, the live impact runs the model with the alternatives, the
full tour and the review cover every shown field, the right-to-left layout orders mixed Hebrew / Latin text, and the
panel walks every lesson in the real window (skipped without a display)."""
import os
import time
import unittest

from _common import LWIR, UNCOOLED, VIS, template
from trm4 import guide_he as GH
from trm4 import guide_impact as GI
from trm4 import presets as P
from trm4 import rtl_tk as R

try:
    import tkinter as tk
except ImportError:                                                         # no Tk on this machine
    G = None
else:
    from trm4 import gui as G                                               # import errors must fail, not skip


def merged(name, **kw):
    return P.deep_merge(P.DEFAULT_PROJECT, template(name, **kw))


def value(p, path):
    for k in path.split("."):
        p = p[int(k)] if isinstance(p, list) else p[k]
    return p


def value_of(p, path):
    try:
        return value(p, path)
    except (KeyError, IndexError, TypeError):
        return None


def form_visible(f, header, p):
    """Visibility of a form row without the window: its condition (the advanced level counted as shown)."""
    return bool(f["cond"](p))


def tour_pages():
    eng = G.WORKFLOWS["engineering"][1]
    return [(n, fl, "engineering") for n, fl in G.ALL_PAGES if n in eng and n != "Camera profile"] + \
        [(n, fl, "lab") for n, fl in G.ALL_PAGES if n == "Validation data"]


class KnowledgeBase(unittest.TestCase):
    def test_entries_complete(self):
        for path, e in GH.PARAMS.items():
            with self.subTest(path=path):
                for key in ("title", "what", "why", "source"):
                    self.assertTrue(e.get(key), key)
                self.assertIn(e["impact"], (0, 1, 2, 3))

    @unittest.skipIf(G is None, "GUI not importable")
    def test_every_form_field_has_a_card(self):
        missing = sorted({f["path"] for _n, fields in G.ALL_PAGES for f in fields
                          if f.get("path") and not GH.param(f["path"])})
        self.assertEqual(missing, [])

    def test_documentation_fields_do_not_claim_a_range_effect(self):
        for path in ("name", "measured.meta.date", "atmosphere.meta.source", "basic.fov_h_deg", "turbulence.scint"):
            self.assertEqual(GH.param(path)["impact"], 0, path)

    def test_ranking_follows_the_sensitivity_study(self):
        # Table 5: task criterion, target size, focal length, aperture and atmosphere lead; NETD is minor
        for path in ("target.tasks.N.lp", "target.task_preset", "target.W_m", "target.H_m", "optics.f_mm",
                     "optics.D_mm", "atmosphere.atm.N.sigma"):
            self.assertEqual(GH.param(path)["impact"], 3, path)
        self.assertEqual(GH.param("detector.netd_mK")["impact"], 1)

    def test_indexed_paths(self):
        self.assertIs(GH.param("target.tasks.2.lp"), GH.PARAMS["target.tasks.N.lp"])
        self.assertIs(GH.param("atmosphere.atm.0.sigma"), GH.PARAMS["atmosphere.atm.N.sigma"])
        self.assertIs(GH.param("additional.post_v_par"), GH.PARAMS["additional.par"])
        self.assertIsNone(GH.param("no.such.path"))


class ValueChecks(unittest.TestCase):
    def check(self, path, v, p=None):
        return GH.check(path, v, p or merged(LWIR))

    def test_unit_mistakes_are_flagged(self):
        self.assertEqual(self.check("optics.f_mm", 0.5)[0], "warn")             # cm instead of mm
        self.assertEqual(self.check("target.T_bg_K", 15.0)[0], "warn")          # Celsius instead of Kelvin
        self.assertEqual(self.check("optics.tau_opt", 85.0)[0], "warn")         # percent instead of fraction
        self.assertEqual(self.check("target.t_refl", 30.0)[0], "warn")
        self.assertEqual(self.check("target.W_m", 0.0)[0], "warn")
        self.assertEqual(self.check("target.dT_K", 0.0)[0], "warn")
        self.assertEqual(self.check("turbulence.cn2", -1e-14)[0], "warn")

    def test_unit_mistakes_suggest_the_corrected_value(self):
        p = merged(LWIR)
        self.assertEqual(GH.suggestion(GH.check("optics.f_mm", 0.5, p)), 5.0)           # cm -> mm
        self.assertAlmostEqual(GH.suggestion(GH.check("target.T_bg_K", 15.0, p)), 288.15)
        self.assertAlmostEqual(GH.suggestion(GH.check("optics.tau_opt", 85.0, p)), 0.85)
        self.assertEqual(GH.suggestion(GH.check("detector.netd_mK", 0.05, p)), 50.0)     # K -> mK
        self.assertAlmostEqual(GH.suggestion(GH.check("stab.rand_h_mrad", 70.0, p)), 0.07)  # urad -> mrad
        self.assertAlmostEqual(GH.suggestion(GH.check("turbulence.cn2", 14.0, p)), 1e-14)
        self.assertAlmostEqual(GH.suggestion(GH.check("atmosphere.atm.0.sigma", 0.0002, p)), 0.2)  # 1/m -> 1/km
        self.assertIsNone(GH.suggestion(GH.check("optics.f_mm", 100.0, p)))

    def test_cross_field_checks(self):
        p = merged(LWIR, basic__frame_rate=50.0)
        self.assertEqual(GH.check("detector.tint_ms", 30.0, p)[0], "warn")             # longer than the frame
        p = merged(LWIR, detector__pitch_h_um=15.0)
        self.assertEqual(GH.check("detector.a_h_um", 17.0, p)[0], "warn")              # active > pitch
        self.assertEqual(GH.check("detector.netd_frames", 4, p)[0], "warn")            # averaged NETD
        self.assertEqual(GH.check("display.t_eye_s", 100.0, p)[2], 0.1)                # ms instead of s
        p = merged(VIS, target__t_refl=0.2, target__b_refl=0.2, target__t_refl_mode="effective",
                   target__b_refl_mode="effective")
        self.assertEqual(GH.check("target.t_refl", 0.2, p)[0], "warn")                 # no contrast

    def test_f_number_from_focal_length_and_diameter(self):
        p = merged(LWIR, optics__f_mm=100.0, optics__D_mm=500.0)
        self.assertEqual(GH.check("optics.f_mm", 100.0, p)[0], "warn")         # F/0.2
        self.assertIn("F/2", GH.check("optics.f_mm", 100.0, merged(LWIR))[1])

    def test_same_target_and_background_material(self):
        p = merged(VIS, target__t_refl_mode="spectral", target__b_refl_mode="spectral",
                   target__t_refl_preset="Asphalt", target__b_refl_preset="Asphalt")
        self.assertEqual(GH.check("target.t_refl_preset", "Asphalt", p)[0], "warn")

    def test_templates_pass_except_narrow_fov_without_jitter(self):
        # the only warning on the shipped templates is the advice of the study: narrow IFOV needs LOS jitter
        for name in P.TEMPLATES:
            p = P.make_template(name)
            for path, e in GH.PARAMS.items():
                if "check" not in e:
                    continue
                pth = path.replace(".N.", ".0.")
                try:
                    v = value(p, pth)
                except (KeyError, IndexError):
                    v = None
                r = GH.check(pth, v, p)
                if r and r[0] == "warn":
                    with self.subTest(template=name, path=pth):
                        self.assertIn(pth, ("stab.rand_h_mrad", "stab.jitter_preset"))

    def test_field_card_puts_the_check_first(self):
        blocks = GH.field_blocks("optics.f_mm", 0.5, merged(LWIR))
        self.assertEqual(blocks[0][0], "chips")
        self.assertEqual(blocks[1][:2], ("box", "warn"))


class Impact(unittest.TestCase):
    """Live effect of a value on the ranges (model runs)."""

    def test_alternatives(self):
        p = merged(LWIR)
        f = {"kind": "float", "unit": "mm"}
        e = GH.param("optics.f_mm")
        self.assertEqual(GI.alternatives("optics.f_mm", 50.0, f, e, p, None), [("+20%", 60.0)])
        bad = GH.check("optics.f_mm", 0.5, p)
        self.assertEqual(GI.alternatives("optics.f_mm", 0.5, f, e, p, bad), [("הערך המוצע", 5.0)])
        self.assertEqual(GI.alternatives("name", "x", {"kind": "text"}, GH.param("name"), p, None), [])
        tb = {"kind": "float", "unit": "K"}
        self.assertEqual(GI.alternatives("target.T_bg_K", 288.0, tb, GH.param("target.T_bg_K"), p, None)[0][1],
                         298.0)                                                    # absolute step for kelvin

    def test_longer_focal_length_gives_longer_identification_range(self):
        p = merged(UNCOOLED)
        res = GI.evaluate(GI.ImpactCache(), p, "optics.f_mm", [("+20%", p["optics"]["f_mm"] * 1.2)])
        self.assertIsNone(res["error"])
        _label, _v, r, _err, changes = res["alts"][0]
        self.assertGreater(r["Identification"], res["base"]["Identification"])
        self.assertIn("IFOV", [c[0] for c in changes])
        self.assertTrue(any("%" in ln for ln in GI.blocks(res, "mm")[0][2]))

    def test_presets_are_applied_like_the_form(self):
        p = merged(LWIR)
        c = GI.apply_value(P.deep_merge(p, {}), "target.task_preset", "johnson1958")
        self.assertEqual([t["lp"] for t in c["target"]["tasks"]], list(P.task_preset_values(c)))
        c = GI.apply_value(P.deep_merge(p, {}), "detector.pitch_h_um", 12.0)
        self.assertEqual(c["detector"]["pitch_v_um"], 12.0)


class Lessons(unittest.TestCase):
    def test_lessons_have_steps_for_every_category(self):
        for name in P.TEMPLATES:
            p = P.make_template(name)
            for les in GH.LESSONS:
                if les.get("dynamic"):                                      # the tour: test_tour_covers_...
                    continue
                with self.subTest(template=name, lesson=les["id"]):
                    st = GH.steps(les["id"], p)
                    self.assertGreater(len(st), 3)
                    for s in st:
                        if s.get("path"):
                            self.assertIsNotNone(GH.param(s["path"]), s["path"])

    @unittest.skipIf(G is None, "GUI not importable")
    def test_tour_covers_every_shown_field_once(self):
        for name in (LWIR, VIS):
            p = merged(name)
            st = GH.steps("tour", p, tour_pages(), form_visible)
            listed = [x for s in st for x in s.get("fields", [])]
            self.assertEqual(len(listed), len(set(listed)))
            shown = {f["path"] for _n, fl, _w in tour_pages() for f in fl if f.get("path") and
                     f.get("kind") not in ("header", "derived") and form_visible(f, None, p)}
            self.assertEqual(set(listed), shown)
            self.assertTrue(st[-1].get("review"))
            for s in st[1:-1]:
                self.assertEqual(s["path"], s["fields"][0])

    @unittest.skipIf(G is None, "GUI not importable")
    def test_review_sorts_the_warnings_by_impact(self):
        p = merged(LWIR, optics__f_mm=0.5, display__t_eye_s=100.0)
        r = GH.review(tour_pages(), p, form_visible, lambda path: value_of(p, path))
        paths = [w[1] for w in r["warn"]]
        self.assertIn("optics.f_mm", paths)
        self.assertLess(paths.index("optics.f_mm"), paths.index("display.t_eye_s"))
        self.assertEqual([w[0] for w in r["warn"]], sorted((w[0] for w in r["warn"]), reverse=True))
        q = merged(UNCOOLED)                                        # wide IFOV: not even the jitter advice
        self.assertEqual(GH.review(tour_pages(), q, form_visible, lambda path: value_of(q, path))["warn"], [])

    def test_reflective_steps_follow_the_reflectivity_mode(self):
        eff = [s.get("path") for s in GH.steps("first", merged(VIS, target__t_refl_mode="effective"))]
        spec = [s.get("path") for s in GH.steps("first", merged(VIS, target__t_refl_mode="spectral"))]
        self.assertIn("target.t_refl", eff)
        self.assertNotIn("target.t_refl_preset", eff)
        self.assertIn("target.t_refl_preset", spec)
        thermal = [s.get("path") for s in GH.steps("first", merged(LWIR))]
        self.assertIn("target.dT_K", thermal)
        self.assertNotIn("target.t_refl", thermal)

    @unittest.skipIf(G is None, "GUI not importable")
    def test_steps_point_at_real_fields(self):
        pages = {name: {f.get("path") for f in fields} for name, fields in G.ALL_PAGES}
        for les in GH.LESSONS:
            for s in les["steps"]:
                with self.subTest(lesson=les["id"], step=s["title"]):
                    self.assertIn(s.get("workflow", "quick"), G.WORKFLOWS)
                    if s.get("page"):
                        self.assertIn(s["page"], G.WORKFLOWS[s["workflow"]][1])
                    if s.get("path"):
                        self.assertIn(s["path"], pages[s["page"]])
                    if s.get("tab"):
                        self.assertIn(s["tab"], G.RESULT_TABS[s["workflow"]])


class RightToLeft(unittest.TestCase):
    def visual(self, line):
        return "".join(t for t, _rtl in R._segments(line))

    def test_latin_only_unchanged(self):
        self.assertEqual(R._segments("Run > Detector lookup"), [("Run > Detector lookup", False)])

    def test_hebrew_words_right_to_left(self):
        # visual left-to-right order: the second word is drawn left of the first
        v = self.visual("אורך מוקד")
        self.assertEqual(v, "דקומ ךרוא")

    def test_prefix_maqaf_stays_with_the_hebrew_letter(self):
        self.assertEqual(self.visual("ה-IFOV"), "IFOV-ה")
        self.assertEqual(self.visual("בכ-80%"), "80%-כב")

    def test_brackets_mirrored_in_hebrew(self):
        self.assertEqual(self.visual("מוקד (f)"), "(f) דקומ")

    @unittest.skipIf(G is None, "GUI not importable")
    def test_wrap_keeps_menu_paths(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        try:
            import tkinter.font as tkfont
            f = tkfont.Font(root=root, family="Segoe UI", size=10)
            lines = R.wrap("פתחו את Run > Detector lookup כדי למלא את נתוני הגלאי מהקטלוג", f, 120)
            self.assertTrue(any("Run > Detector" in ln for ln in lines))
            self.assertTrue(all(f.measure(ln) <= 120 or " " not in ln for ln in lines))
        finally:
            root.destroy()


@unittest.skipIf(G is None or os.environ.get("TRM4_NO_GUI"), "GUI not available")
class Panel(unittest.TestCase):
    """The real main window: open the guide, walk every step of every lesson, close it."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.app = G.App()
        except tk.TclError:
            raise unittest.SkipTest("no display")
        cls.app.settings = dict(cls.app.settings, guide={}, guide_open=False)
        cls.app.confirm_discard = lambda: True          # edits made by a test must not open the save dialog

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def test_walk_all_lessons(self):
        app = self.app
        for name in (LWIR, VIS):
            app.load_template(name)
            app.toggle_guide(True)
            g = app.guide
            self.assertEqual(len(app.paned.panes()), 3)
            for les in GH.LESSONS:
                g.start(les["id"])
                for i, st in enumerate(g._steps()):
                    with self.subTest(template=name, lesson=les["id"], step=st["title"]):
                        g.show_step(i)
                        app.update_idletasks()
                        self.assertEqual(g.mode, "step")
                        if st.get("page"):
                            self.assertEqual(app.current_page, st["page"])
                        if st.get("path") and not g.step_hidden:
                            self.assertIsNotNone(g.hilited)
                g.finish()
                self.assertIn(les["id"], g.done)
            app.toggle_guide(False)
            self.assertIsNone(app.guide)
            self.assertEqual(len(app.paned.panes()), 2)

    def test_field_card_and_live_check(self):
        app = self.app
        app.load_template(LWIR)
        app.toggle_guide(True)
        try:
            app._guide_focus("optics.f_mm")
            self.assertEqual(app.guide.mode, "field")
            app._set_value("optics.f_mm", 0.5)
            app.refresh()                                                   # the card re-checks the value
            self.assertEqual(GH.check("optics.f_mm", app.project["optics"]["f_mm"], app.project)[0], "warn")
            app._guide_focus("no.such.path")                                # no card: stays on the last one
            self.assertEqual(app.guide.field_path, "optics.f_mm")
        finally:
            app._set_value("optics.f_mm", 100.0)
            app.toggle_guide(False)

    def wait_for(self, cond, timeout=60.0):
        t0 = time.time()
        while not cond() and time.time() - t0 < timeout:
            self.app.update()
            time.sleep(0.05)
        return cond()

    def test_live_impact_suggestion_and_undo(self):
        app = self.app
        app.load_template(UNCOOLED)
        app.toggle_guide(True)
        g = app.guide
        try:
            f0 = app.project["optics"]["f_mm"]
            app._set_value("optics.f_mm", 2.5)                              # 25 mm entered in cm
            app.refresh()
            app._guide_focus("optics.f_mm")
            self.assertEqual(g.mode, "field")
            self.assertTrue(self.wait_for(lambda: g._imp_res is not None), "impact did not arrive")
            self.assertIsNotNone(g._imp_res["base"])
            label, v, r, _e, _c = g._imp_res["alts"][0]
            self.assertEqual(label, "הערך המוצע")
            self.assertGreater(r["Recognition"], g._imp_res["base"]["Recognition"])
            self.assertEqual(v, 25.0)
            g.apply_value("optics.f_mm", v)
            self.assertAlmostEqual(app.project["optics"]["f_mm"], 25.0)
            g.undo()
            self.assertAlmostEqual(app.project["optics"]["f_mm"], 2.5)
        finally:
            app._set_value("optics.f_mm", f0)
            app.refresh()
            app.toggle_guide(False)

    def test_warning_while_typing(self):
        app = self.app
        app.load_template(UNCOOLED)
        app.toggle_guide(True)
        g = app.guide
        f0 = app.project["optics"]["f_mm"]
        try:
            app._guide_focus("optics.f_mm")
            self.assertFalse(any(b[:2] == ("box", "warn") for b in g.doc.blocks))
            app._set_value("optics.f_mm", 2.5)                              # typed, the field keeps the focus
            app._guide_typing("optics.f_mm")
            self.assertTrue(self.wait_for(lambda: g._typing_job is None, 5.0))
            self.assertEqual(app.project["optics"]["f_mm"], f0)              # not refreshed yet
            warn = [b for b in g.doc.blocks if b[:2] == ("box", "warn")]
            self.assertTrue(warn, "no warning while typing")
            self.assertIn("25", warn[0][2][-1])                             # the suggested value
        finally:
            app._set_value("optics.f_mm", f0)
            app.refresh()
            app.toggle_guide(False)

    def test_review_view(self):
        app = self.app
        app.load_template(LWIR)
        app.toggle_guide(True)
        g = app.guide
        try:
            g.show_review()
            self.assertEqual(g.mode, "review")
            self.assertTrue(self.wait_for(lambda: g._review_ranges is not None), "ranges did not arrive")
            cards = [b for b in g.doc.blocks if b[0] == "card"]
            self.assertIn("⚠", cards[0][1])                                # narrow IFOV without jitter
            self.assertIn(GH.param("stab.jitter_preset")["title"], cards[0][1])
            cards[0][4]()                                                    # open the field from the list
            self.assertEqual(g.mode, "field")
            self.assertEqual(g.back, "review")
            self.assertEqual(app.current_page, "Stabilization & MTFs")
            g.apply_value("stab.jitter_preset", "nvipm70")                  # the form fills the preset
            self.assertTrue(app.project["stab"]["random_on"])
            self.assertAlmostEqual(app.project["stab"]["rand_h_mrad"], 0.07)
        finally:
            app.toggle_guide(False)


if __name__ == "__main__":
    unittest.main()
