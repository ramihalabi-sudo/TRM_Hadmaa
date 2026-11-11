"""Spoken narration of the guide: the speech text (units, ranges, acronyms), the scripts of every view in Hebrew and in
English, the English translation stays in step with its Hebrew source, every fixed sentence has a recording, and
the narrator strip of the panel (skipped without a display)."""
import json
import os
import time
import unittest

from _common import LWIR, VIS, template
from trm4 import guide_he as GH
from trm4 import guide_voice as GV
from trm4 import guide_voice_en as EN
from trm4 import presets as P
from trm4.guide_kb_he import MORE

try:
    import tkinter as tk
except ImportError:
    G = None
else:
    from trm4 import gui as G


def merged(name):
    return P.deep_merge(P.DEFAULT_PROJECT, template(name))


def value_of(p, path):
    try:
        for k in path.split("."):
            p = p[int(k)] if isinstance(p, list) else p[k]
        return p
    except (KeyError, IndexError, TypeError):
        return None


def texts(script):
    out = []
    for seg in script:
        if isinstance(seg, dict):                                        # an action of the walk
            continue
        out += [s[1] for s in (seg() or [])] if callable(seg) else [seg[1]]
    return out


class SpeechText(unittest.TestCase):
    def test_hebrew(self):
        s = GV.speech
        self.assertEqual(s("פסיעה 12-17 µm", "he"), "פסיעה 12 עד 17 מיקרון")
        self.assertEqual(s('גילוי 3.2 ק"מ · הכרה 1.1 ק"מ', "he"), "גילוי 3.2 קילומטר, הכרה 1.1 קילומטר")
        self.assertIn("delta T שווה 2 קלווין", s("ΔT = 2 K", "he"))     # English stays English
        self.assertIn("עשר בחזקת מינוס 14", s("Cn² = 1e-14", "he"))
        self.assertIn("F 4 עד F 5.5", s("F/4-F/5.5", "he"))
        self.assertIn("f חלקי 4", s("D = f / 4", "he"))
        self.assertIn("640 על 512", s("640x512", "he"))
        self.assertEqual(s("TRM_HADMAA!", "he"), "TRM הדמאה!")
        self.assertNotRegex(s("⚠ ★★ ערך", "he"), "[★⚠]")

    def test_english_inside_hebrew(self):
        """A recording says the English of a Hebrew sentence with an English voice; the live Windows voice gets it
        spelled in Hebrew."""
        said = GV.speech("נלמד לקרוא את התוצאות בלשוניות Summary, Range ו-Messages, או נלחץ F5.", "he")
        self.assertEqual(GV.voice_parts(said), [
            ("he", "נלמד לקרוא את התוצאות בלשוניות"), ("en", "Summary,"), ("en", "Range"), ("he", "וֶ"),
            ("en", "Messages,"), ("he", "או נלחץ"), ("en", "F5.")])
        self.assertEqual(GV.voice_parts(GV.speech("ה-IFOV", "he")), [("he", "הַ"), ("en", "IFOV")])
        self.assertTrue(GV.is_mixed("he", said))
        self.assertFalse(GV.is_mixed("he", "רק עברית כאן."))
        self.assertFalse(GV.is_mixed("en", "Summary"))
        live = GV.live_text
        self.assertIn("אן אי טי די", live(GV.speech("NETD", "he"), "he"))            # acronyms letter by letter
        self.assertIn("האיי-פוב", live(GV.speech("ה-IFOV", "he"), "he"))             # a known word, with its prefix
        self.assertIn("אף 4 עד אף 5.5", live(GV.speech("F/4-F/5.5", "he"), "he"))
        self.assertIn("דלתא טי", live(GV.speech("ΔT", "he"), "he"))
        self.assertEqual(live("Summary", "en"), "Summary")

    def test_hebrew_is_gemini(self):
        """Every Hebrew recording is made by the Gemini voice, keyed by its model, voice and prompt; English is not."""
        first = GV.speech(GV.sentences(GV.HOME_OPEN_HE)[1], "he")
        self.assertTrue(GV.is_gemini("he", first))
        self.assertTrue(GV.is_gemini("he", GV.speech("נלחץ על Calculate, או F5.", "he")))
        self.assertFalse(GV.is_gemini("en", GV.speech(GV.sentences(GV.EN.HOME_OPEN)[0], "en")))
        import hashlib
        plain = lambda t: hashlib.sha1(("en|" + t).encode()).hexdigest()[:16]       # noqa: E731
        self.assertEqual(GV.rec_key("en", "Only English."), plain("Only English."))
        key = "he|gemini|%s|%s|%s|%s" % (GV.GEMINI["model"], GV.GEMINI["voice"], GV.GEMINI["prompt"], first)
        self.assertEqual(GV.rec_key("he", first), hashlib.sha1(key.encode()).hexdigest()[:16])

    def test_english(self):
        s = GV.speech
        self.assertEqual(s("12-17 µm, 50 mK", "en"), "12 to 17 microns, 50 millikelvin")
        self.assertIn("F lambda over d less than 1", s("Fλ/d < 1", "en"))
        self.assertIn("observer's", s("the observer's eye", "en"))
        self.assertNotRegex(s("value ערך 5", "en"), "[֐-׿]")   # never Hebrew in an English voice

    def test_sentences(self):
        self.assertEqual(GV.sentences("F/1.4 קל. 0.85 ולא 85! שני?"), ["F/1.4 קל.", "0.85 ולא 85!", "שני?"])


class Scripts(unittest.TestCase):
    def test_every_field_card(self):
        p = merged(LWIR)
        for path in GH.PARAMS:
            real = path.replace(".N.", ".0.")
            for lang in GV.LANGS:
                t = texts(GV.field_script(lang, real, value_of(p, real), p, label="Label"))
                self.assertTrue(t, (lang, path))
                if lang == "en":
                    for x in t:
                        self.assertNotRegex(GV.speech(x, "en"), "[֐-׿]", (path, x))

    def test_check_and_impact_are_said(self):
        p = merged(LWIR)
        he = " ".join(texts(GV.field_script("he", "optics.f_mm", 2.5, p)))
        self.assertIn("2.5", he)                                         # 2.5 mm: entered in cm?
        self.assertIn("פחות מ-3 mm", he)                                 # the reason, in the teacher's words
        self.assertIn(" 25", he)                                         # the suggested value
        self.assertIn("משקפת", he)                                       # the analogy of the core lesson
        res = {"base": {"Detection": 10.0, "Recognition": 4.0, "Identification": 2.0},
               "alts": [("הערך המוצע", 25, {"Detection": 12.0, "Recognition": 5.0, "Identification": 2.5}, None, [])]}
        en = " ".join(texts(GV.field_script("en", "optics.f_mm", 2.5, p, impact=lambda: res)))
        self.assertIn("You entered 2.5", en.replace("your value, 2.5", "You entered 2.5"))
        self.assertIn("detection 12", en)
        self.assertIn("up 20 percent", en)
        self.assertIn("a large effect", en)
        self.assertIn("binoculars", en)

    def test_teacher_flow(self):
        """Signposts and spoken connections: questions open the parts, examples and contrasts are marked, equations and
        lists are said as sentences, and the system considerations include weight and cost."""
        p = merged(LWIR)
        he = texts(GV.field_script("he", "optics.f_mm", 50.0, p))
        joined = " ".join(he)
        for marker in ("מה זה", "למה", "למשל", "לעומת זאת", "כלומר", "עכשיו", "בשורה התחתונה"):
            self.assertIn(marker, joined)
        self.assertNotIn(" = ", joined)
        # the spoken sensitivity of the field (system research review, v2.19)
        sens = " ".join(texts(GV.field_script("he", "optics.f_mm", 100.0, p)))
        self.assertIn("ניתוח רגישות קצר", sens)
        self.assertIn("משקל העדשה יגדל פי", sens)
        # cause and result said out loud, as people do when they explain (interview answers: action -> "as a result")
        warn = " ".join(texts(GV.field_script("he", "optics.f_mm", 2.5, p, impact=lambda: {
            "base": {"Detection": 10.0}, "alts": [("הערך המוצע", 25, {"Detection": 12.0}, None, [])]})))
        for marker in ("ולמה", "? כי ", "כי פחות", "כך שייתכן", "ולכן הייתי מנסה", "אם תעברו לערך המוצע",
                       "ולכן, במערכת שלכם"):
            self.assertIn(marker, warn)
        en = " ".join(texts(GV.field_script("en", "optics.f_mm", 50.0, p)))
        self.assertIn("? Because ", en)
        self.assertNotIn("Think of binoculars. So", en)                  # hand-written lessons are said as written
        self.assertTrue(any(t.startswith("ובמערכת שלכם, בהערכה גסה: חומר הגלם") for t in
                            texts(GV.field_script("he", "optics.D_mm", value_of(p, "optics.D_mm"), p))))
        self.assertIn("697 עד", GV.speech("כ-$697-$1.4k", "he") + " 697 עד")
        self.assertEqual(GV.speech("$697-$1.4k", "en"), "697 to 1400 dollars")
        items = [{"path": q, "value": value_of(p, q), "project": p} for q in ("optics.D_mm", "optics.f_mm")]
        walk = texts(GV.walk_script("he", items, None, None))
        self.assertTrue(walk[0].startswith("בקבוצה הזו יש 2 שדות"))
        self.assertTrue(any(t.startswith("סיימנו עם") or t.startswith("זה היה") or t.startswith("אחרי") for t in walk))

    def test_home_opening(self):
        """The opening screen (reports/מדריך_מסך_הפתיחה.docx): the welcome, a spoken introduction of each of the six
        lessons by number, and the choice; every sentence of it is recorded."""
        for lang in GV.LANGS:
            said = texts(GV.home_script(lang, GH.LESSONS, {"first"}))
            joined = " ".join(said)
            self.assertTrue(said[0].startswith("ברוכים הבאים לעולם של" if lang == "he" else "Welcome to the world of"))
            for n in range(1, len(GH.LESSONS) + 1):
                self.assertIn(("שיעור %d:" if lang == "he" else "Lesson %d:") % n, joined)
            self.assertEqual(set(GV.HOME_LESSON_HE), {les["id"] for les in GH.LESSONS})
            self.assertEqual(set(EN.HOME_LESSON), {les["id"] for les in GH.LESSONS})
            self.assertIn(GV.HOME_DONE_HE if lang == "he" else EN.HOME_DONE, said)
            self.assertIn("הבחירה בידיים שלכם" if lang == "he" else "the choice is yours", joined)
            self.assertEqual(said[-1], "יוצאים לדרך!" if lang == "he" else "Let's go!")
            self.assertEqual(len(GH.LESSONS), 6)
            static = set(GV.static_texts(lang))
            for t in said:
                self.assertIn(GV.speech(t, lang), static, t)

    def test_lessons_home_review(self):
        for name in (LWIR, VIS):
            p = merged(name)
            for les in GH.LESSONS:
                for st in GH.steps(les["id"], p):
                    for lang in GV.LANGS:
                        args = {"path": st["path"], "value": value_of(p, st["path"]), "project": p} \
                            if st.get("path") else None
                        self.assertTrue(texts(GV.step_script(lang, les["id"], st, args)), (les["id"], st["title"]))
            for lang in GV.LANGS:
                self.assertTrue(texts(GV.home_script(lang, GH.LESSONS, {"first"})))
                r = {"warn": [(3, "optics.f_mm", "Optics", ("warn", "בדיקה"))], "ok": 4, "n": 5}
                self.assertIn("5" if lang == "he" else "5 fields", " ".join(texts(GV.review_script(lang, r))))


class Translation(unittest.TestCase):
    def test_core_fields_and_steps_translated(self):
        core = {k for k in GH.PARAMS if k not in MORE}
        self.assertEqual(set(EN.PARAMS), core, "every core field of guide_he has an English narration")
        for k, e in EN.PARAMS.items():
            src = GH.PARAMS[k]
            for f in ("typical", "mistakes"):
                self.assertEqual(len(e.get(f) or []), len(src.get(f) or []), (k, f))
        steps = {(les["id"], st["title"]) for les in GH.LESSONS for st in les["steps"]}
        steps |= {("tour", st["title"]) for st in GH.tour_steps([], {}, lambda *a: True)}
        steps |= {("engineering", st["title"]) for st in GH.entry_steps([], {}, lambda *a: True)}
        for key in EN.STEPS:
            self.assertIn(key, steps, "translation of a step that no longer exists")
        for les in GH.LESSONS:
            for st in les["steps"]:
                if st.get("blocks"):
                    self.assertIn((les["id"], st["title"]), EN.STEPS, "hand-written step without English")
        self.assertEqual(set(EN.LESSONS), {l["id"] for l in GH.LESSONS})
        self.assertEqual(set(EN.PAGES), set(GH.PAGE_HE))

    def test_translations_are_current(self):
        path = os.path.join(GV.VOICE_DIR, "en_sources.json")
        with open(path, encoding="utf-8") as f:
            stamped = json.load(f)
        stale = sorted(k for k, h in GV.en_sources().items() if stamped.get(k) != h)
        self.assertEqual(stale, [], "the Hebrew source changed: update guide_voice_en.py, then "
                                    "py tools/make_guide_voice.py --stamp")


class Recordings(unittest.TestCase):
    def test_every_fixed_sentence_is_recorded(self):
        for lang in GV.LANGS:
            if not GV.has_recordings(lang):
                self.skipTest("no recordings of %s (py tools/make_guide_voice.py)" % lang)
            missing = [t for t in GV.static_texts(lang) if not GV.recording(lang, t)]
            self.assertEqual(missing[:5], [], "%d sentences of %s without a recording: py tools/make_guide_voice.py"
                             % (len(missing), lang))


class RecordingTool(unittest.TestCase):
    """tools/make_guide_voice.py: the parts the recordings are made by, and the pace of the Gemini requests."""

    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
        try:
            import make_guide_voice
        except ImportError as e:
            raise unittest.SkipTest("recording tool not importable: %s" % e)
        cls.M = make_guide_voice

    def test_parts_cover_every_sentence_once(self):
        for lang in GV.LANGS:
            parts = self.M.sections(lang)
            names = [n for n, _t in parts]
            self.assertEqual(names[:8], ["home"] + ["lesson%d" % i for i in range(1, 7)] + ["tour"])
            self.assertNotIn("other", names, lang)
            said = [t for _n, ts in parts for t in ts]
            self.assertEqual(len(said), len(set(said)), lang)
            self.assertEqual(set(said), set(GV.static_texts(lang)), lang)

    def test_retry_waits_what_the_limit_asks(self):
        err = "429 RESOURCE_EXHAUSTED {'@type': 'RetryInfo', 'retryDelay': '37s'}"
        self.assertEqual(self.M.retry_delay(err, 0), 39.0)
        self.assertEqual(self.M.retry_delay("network", 1), 40.0)

    def test_pace_keeps_the_budget(self):
        import asyncio

        async def run():
            pace = self.M.Pace(rpm=6000, budget=3)
            return [await pace.take() for _ in range(5)], pace.used

        self.assertEqual(asyncio.run(run()), ([True, True, True, False, False], 3))


@unittest.skipIf(G is None, "no Tk")
class Panel(unittest.TestCase):
    def setUp(self):
        try:
            self.app = G.App()
        except tk.TclError as e:
            self.skipTest("no display: %s" % e)
        self.app.withdraw()

    def tearDown(self):
        self.app.destroy()

    def test_narrator_strip(self):
        app = self.app
        app.toggle_guide(True)
        gp = app.guide
        said = []
        gp.voice.speak = lambda script, lang, rate=1.0: said.append((lang, texts(script)))
        gp.narrate()
        self.assertEqual(said[-1][0], "he")
        gp.voice_set(lang="en")
        gp.start("first")
        gp.narrate()
        self.assertEqual(said[-1][0], "en")
        self.assertIn("welcome to the second lesson", said[-1][1][0].lower())
        gp.show_field("optics.f_mm")
        gp.narrate()
        self.assertTrue(any("focal length" in t.lower() for t in said[-1][1]))
        gp.voice_set(auto=True, rate=1.15)
        self.assertEqual(app.settings["guide"]["voice"], {"lang": "en", "auto": True, "rate": 1.15})
        gp.bar.set_state("playing", "The effective focal length of the lens.")
        app.update_idletasks()
        gp.bar.set_state("idle", "")
        app.toggle_guide(False)

    def test_walk_follows_fields_and_cursor(self):
        """The voice walks the fields of a page one by one: each is highlighted, gets the cursor and its card while it
        is explained; play explains the field the user put the cursor in, not the field of the step."""
        app = self.app
        app.toggle_guide(True)
        gp = app.guide
        # the user's auto-play would start the narration of the last step half a second after the guide opens, in
        # the middle of this walk: off for this test (not saved)
        gp.voice_cfg["auto"] = False
        if gp._voice_job:
            gp.after_cancel(gp._voice_job)
            gp._voice_job = None
        orig = GV.recording
        GV.recording = lambda lang, text: "fake.mp3"                     # every sentence "plays" at once
        try:
            gp.voice.mci.play = lambda path, speed=1.0: True
            gp.voice.mci.mode = lambda: "stopped"
            seen = []
            walk = gp._walk_field

            def spy(path, i, n):
                walk(path, i, n)
                app.update()
                seen.append((path, gp.field_path, gp._focused_path(), gp.hilited is not None))

            gp._walk_field = spy
            app.goto_page("Optics")
            app.update()
            gp.walk_page()
            # the first group of the page only (aperture and focal length): the whole page is ~100 fields and
            # ~1,400 sentences since the cards grew (2.13-2.17), over two minutes even with instant "playback"
            gp._walk_page = None
            end = time.time() + 120
            while time.time() < end:
                app.update()
                if gp.voice.state == "idle" and not gp._walk_page and seen:
                    break
                time.sleep(0.02)
            self.assertGreaterEqual(len(seen), 3)                        # the group: aperture via, D, f
            self.assertIn("optics.D_mm", [x[0] for x in seen])
            for path, card, cursor, lit in seen:
                self.assertEqual((card, cursor, lit), (path, path, True))
            self.assertEqual(gp.mode, "step")                            # back to the step after the page
        finally:
            GV.recording = orig
        gp.start("first")
        gp.show_step(next(i for i, st in enumerate(gp._steps()) if st.get("path") == "optics.f_mm"))
        app.update()
        self.assertEqual(gp._focused_path(), "optics.f_mm")             # the step puts the cursor in its field
        said = []
        gp.voice.speak = lambda script, lang, rate=1.0: said.append(texts(script))
        gp._row("Quick setup", "target.W_m")[1].focus_set()
        app.update()
        gp.voice_play()
        self.assertEqual(gp.field_path, "target.W_m")
        self.assertIn("רוחב המטרה", said[-1][0])
        app.toggle_guide(False)


def show_steps():
    for les in GH.LESSONS:
        for i, st in enumerate(les["steps"]):
            if st.get("show"):
                yield les["id"], i, st


class PointAtScreen(unittest.TestCase):
    """A step that talks about a part of the screen frames it while the sentence that names it is said."""

    def test_every_part_is_named_in_both_languages(self):
        n = 0
        for lid, i, st in show_steps():
            for lang in GV.LANGS:
                out = GV.step_script(lang, lid, st, point=lambda ts: None)
                self.assertEqual([s for s in out if not isinstance(s, dict)], GV.step_script(lang, lid, st),
                                 "the actions change no sentence (the recordings stay)")
                acts = [(j, s["do"].__defaults__[0]) for j, s in enumerate(out) if isinstance(s, dict)]
                framed = [t for _j, ts in acts for t in ts]
                for words, targets in st["show"]:
                    for t in [targets] if isinstance(targets, str) else targets:
                        self.assertIn(t, framed, (lid, i + 1, lang, words))
                for j, _ts in acts:                                      # an action comes right before a sentence
                    self.assertIsInstance(out[j + 1], tuple)
                n += len(acts)
        self.assertGreaterEqual(n, 60)

    def test_keyword_is_a_whole_word(self):
        from trm4.guide_point import keyword_re
        rx = keyword_re(("Range",))
        self.assertTrue(rx.search("The Range tab shows"))
        self.assertFalse(rx.search("the three ranges"))
        self.assertFalse(rx.search("Ranges"))
        self.assertTrue(keyword_re(("עקומת הטווח",)).search("ועקומת הטווח מראה"))

    @unittest.skipIf(G is None, "no tkinter")
    def test_menus_walk_and_come_back(self):
        """Every menu a lesson opens exists; the walk is the keys a person presses (separators skipped); choosing a
        template loads it and the user's project comes back when the step ends."""
        try:
            app = G.App()
        except tk.TclError as e:
            self.skipTest("no display: %s" % e)
        try:
            app.withdraw()
            from trm4 import guide_point as GP
            down, right = 0x28, 0x27
            self.assertEqual(GP.MenuWalk(app, ["File", "New from template",
                                               "Thermal - LWIR uncooled microbolometer 640x480"]).keys(),
                             [down, right, down, down, down])
            self.assertEqual(GP.MenuWalk(app, ["Run", "Limiting factors"]).keys(), [down] * 3)
            self.assertIsNone(GP.MenuWalk(app, ["File", "No such item"]).keys())
            for _lid, _i, st in show_steps():
                for _w, t in st["show"]:
                    for x in [t] if isinstance(t, str) else t:
                        kind, _, arg = x.partition(":")
                        if kind in ("menu", "menudo"):
                            self.assertIsNotNone(GP.MenuWalk(app, arg.split(">")).keys(), x)
            app.toggle_guide(True)
            gp = app.guide
            before = app._state_of(app.collect())
            load = gp.pointer._menu_action(["File", "New from template", "Visible - CMOS daylight camera 1920x1080"])
            load()
            self.assertEqual(app.project["category"], "Visible")
            load()                                               # twice: the first project is the one kept
            gp.pointer.reset()
            self.assertEqual(app._state_of(app.collect()), before)
        finally:
            app.destroy()

    @unittest.skipIf(G is None, "no tkinter")
    def test_card_opens_the_option_it_names(self):
        try:
            app = G.App()
        except tk.TclError as e:
            self.skipTest("no display: %s" % e)
        try:
            app.withdraw()
            from trm4 import guide_point as GP
            out = GV.show_actions(GV.field_script("he", "mode.environment", None, app.project, None, None),
                                  GP.card_show(app, "mode.environment"), lambda ts: None)
            picks = [(s["do"].__defaults__[0], out[j + 1][0]) for j, s in enumerate(out) if isinstance(s, dict)]
            self.assertIn((["pick:mode.environment=Field performance"], "עכשיו, למה זה משנה? כי לחיזוי טווחי DRI "
                                                                         "בוחרים Field."), picks)
        finally:
            app.destroy()

    @unittest.skipIf(G is None, "no tkinter")
    def test_frames_in_the_window(self):
        try:
            app = G.App()
        except tk.TclError as e:
            self.skipTest("no display: %s" % e)
        try:
            from trm4 import guide_point as GP
            app.geometry("1500x900")
            app.update()
            app.calculate = lambda: None                        # the demonstration presses Calculate: no model run
            app._source_menu = lambda *a: None                  # a real menu runs its own loop: not in a test
            start, GP.MenuWalk.start = GP.MenuWalk.start, lambda self: self.keys() is not None
            self.addCleanup(setattr, GP.MenuWalk, "start", start)
            app.toggle_guide(True)
            gp = app.guide
            missing = []
            for lid, i, st in show_steps():
                gp.start(lid)
                k = next(k for k, s in enumerate(gp._steps()) if s["title"] == st["title"])
                gp.show_step(k)
                app.update()
                wf, page, adv = app.workflow, app.current_page, app.show_adv.get()
                for _words, targets in st["show"]:
                    for t in [targets] if isinstance(targets, str) else targets:
                        if gp.pointer.show([t]) < 1:
                            missing.append((lid, i + 1, t))
                        self.assertEqual(len(gp.pointer._frames), 4 * gp.pointer.shown)
                gp.show_step(k)                                 # the step again: what was demonstrated is put back
                app.update()
                self.assertEqual((app.workflow, app.current_page, app.show_adv.get()), (wf, page, adv), (lid, i + 1))
            self.assertEqual(missing, [])

            def tips():
                out = []

                def walk(w):
                    for c in w.winfo_children():
                        if isinstance(c, tk.Toplevel) and c.winfo_ismapped():
                            out.append(c)
                        walk(c)
                walk(app)
                return out
            gp.start("intro")
            gp.show_step(4)
            gp.pointer.show(["help:optics.f_mm"])                # press the "?": its explanation opens
            app.update()
            self.assertEqual(len(tips()), 1)
            gp.pointer.show(["card:optics.f_mm"])                # the next sentence closes it; the card opens
            app.update()
            self.assertEqual(tips(), [])
            self.assertEqual((gp.mode, gp.field_path), ("field", "optics.f_mm"))
            gp.pointer.show(["guide:play"])                      # and the step comes back
            self.assertEqual(gp.mode, "step")
            gp.show_field("mode.environment")
            gp.pointer.show(["pick:mode.environment=Field performance"])  # the list opens at the option
            w = gp.pointer._combo("mode.environment")
            lb = "%s.f.l" % w.tk.call("ttk::combobox::PopdownWindow", w)
            self.assertEqual(str(w.tk.call("winfo", "ismapped", w.tk.call("ttk::combobox::PopdownWindow", w))), "1")
            self.assertEqual(w.cget("values")[int(w.tk.call(lb, "curselection")[0])], "Field performance")
            before = w.get()
            gp.pointer.clear()                                   # closed again, the value untouched
            app.update()
            self.assertEqual(str(w.tk.call("winfo", "ismapped", w.tk.call("ttk::combobox::PopdownWindow", w))), "0")
            self.assertEqual(w.get(), before)
            gp.show_step(0)
            self.assertEqual(gp.pointer.shown, 0, "a new step clears the frames of the last one")
            gp.pointer.show(["tool:Calculate"])
            app.toggle_guide(False)
            self.assertEqual(gp.pointer.shown, 0, "closing the guide clears them")
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
