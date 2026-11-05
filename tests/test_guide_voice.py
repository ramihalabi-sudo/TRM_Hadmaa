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
        self.assertIn("דלתא טי שווה 2 קלווין", s("ΔT = 2 K", "he"))
        self.assertIn("עשר בחזקת מינוס 14", s("Cn² = 1e-14", "he"))
        self.assertIn("אף 4 עד אף 5.5", s("F/4-F/5.5", "he"))
        self.assertIn("f חלקי 4", s("D = f / 4", "he"))
        self.assertIn("640 על 512", s("640x512", "he"))
        self.assertIn("אן אי טי די", s("NETD", "he"))             # an acronym letter by letter
        self.assertIn("האיי-פוב", s("ה-IFOV", "he"))               # a known word, joined to its prefix
        self.assertNotRegex(s("⚠ ★★ ערך", "he"), "[★⚠]")

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
        self.assertIn("welcome", said[-1][1][0])
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
            end = time.time() + 60
            while time.time() < end:
                app.update()
                if gp.voice.state == "idle" and not gp._walk_page and seen:
                    break
                time.sleep(0.02)
            self.assertGreater(len(seen), 5)
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


if __name__ == "__main__":
    unittest.main()
