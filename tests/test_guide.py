"""Interactive Hebrew guide: the knowledge base and lessons match the parameter form, value checks catch the
common input mistakes, the right-to-left layout orders mixed Hebrew / Latin text, and the panel walks every lesson
in the real window (skipped without a display)."""
import os
import unittest

from _common import LWIR, VIS, template
from trm4 import guide_he as GH
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


class KnowledgeBase(unittest.TestCase):
    def test_entries_complete(self):
        for path, e in GH.PARAMS.items():
            with self.subTest(path=path):
                for key in ("title", "what", "why", "impact", "source"):
                    self.assertTrue(e.get(key), key)
                self.assertIn(e["impact"], (1, 2, 3))

    def test_ranking_follows_the_sensitivity_study(self):
        # Table 5: task criterion, target size, focal length, aperture and atmosphere lead; NETD is minor
        for path in ("target.tasks.N.lp", "target.task_preset", "target.W_m", "target.H_m", "optics.f_mm",
                     "optics.D_mm", "atmosphere.atm.N.sigma"):
            self.assertEqual(GH.param(path)["impact"], 3, path)
        self.assertEqual(GH.param("detector.netd_mK")["impact"], 1)

    def test_indexed_paths(self):
        self.assertIs(GH.param("target.tasks.2.lp"), GH.PARAMS["target.tasks.N.lp"])
        self.assertIs(GH.param("atmosphere.atm.0.sigma"), GH.PARAMS["atmosphere.atm.N.sigma"])
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
                        self.assertEqual(pth, "stab.rand_h_mrad")

    def test_field_card_puts_the_check_first(self):
        blocks = GH.field_blocks("optics.f_mm", 0.5, merged(LWIR))
        self.assertEqual(blocks[0][0], "chips")
        self.assertEqual(blocks[1][:2], ("box", "warn"))


class Lessons(unittest.TestCase):
    def test_lessons_have_steps_for_every_category(self):
        for name in P.TEMPLATES:
            p = P.make_template(name)
            for les in GH.LESSONS:
                with self.subTest(template=name, lesson=les["id"]):
                    st = GH.steps(les["id"], p)
                    self.assertGreater(len(st), 3)
                    for s in st:
                        if s.get("path"):
                            self.assertIsNotNone(GH.param(s["path"]), s["path"])

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


if __name__ == "__main__":
    unittest.main()
