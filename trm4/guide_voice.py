"""Spoken narration of the interactive guide, in Hebrew or in English (the user chooses what to listen to).

What is said is built from what the guide shows (scripts below): a lesson step, a field card with the live check of
the value and its effect on the ranges, the home page or the review.  A narration is a list of sentences; each
sentence is shown as a caption by the narrator strip of the panel while it is said.

Where the voice comes from, per sentence:
  1. a recording made in advance with a natural (neural) voice - assets/voice/<lang>/<hash>.mp3, made by
     tools/make_guide_voice.py for every fixed text of the guide;
  2. otherwise the voice built into Windows, said live (assets/tts_windows.ps1, Windows.Media.SpeechSynthesis or
     System.Speech) - the sentences that depend on the project: the check of the value, the ranges.
Playback goes through the Windows MCI player (winmm), so no Python package is needed; on other systems the narrator
reports that no voice is available.

speech(text, lang) turns screen text into what a voice should read (units, symbols, ranges, acronyms).
"""
import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading

from . import guide_he as G
from . import guide_teach as T
from . import guide_voice_en as EN

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
VOICE_DIR = os.path.join(ASSETS, "voice")
PS_SCRIPT = os.path.join(ASSETS, "tts_windows.ps1")
LANGS = ("he", "en")
CULTURE = {"he": "he-IL", "en": "en-US"}
NARRATOR = {"he": "המנחה", "en": "Narrator"}
RATES = (0.9, 1.0, 1.15, 1.3)

# --------------------------------------------------------------------------------------------- speech text
_LETTERS_HE = {"A": "איי", "B": "בי", "C": "סי", "D": "די", "E": "אי", "F": "אף", "G": "ג'י", "H": "אייץ'",
               "I": "איי", "J": "ג'יי", "K": "קיי", "L": "אל", "M": "אם", "N": "אן", "O": "או", "P": "פי",
               "Q": "קיו", "R": "אר", "S": "אס", "T": "טי", "U": "יו", "V": "וי", "W": "דאבל-יו", "X": "אקס",
               "Y": "וואי", "Z": "זד"}
# words a Hebrew voice should say as a word, not letter by letter
_WORDS_HE = {"IFOV": "איי-פוב", "FOV": "פוב", "NFOV": "אן-פוב", "WFOV": "דאבל-יו-פוב", "LWIR": "אל-וויר",
             "MWIR": "אם-וויר", "SWIR": "אס-וויר", "NIR": "אן-איי-אר", "VIS": "ויז", "STANAG": "סטנאג",
             "MODTRAN": "מודטרן", "TRM4": "טי אר אם ארבע", "NV-IPM": "אן וי איי פי אם", "CMOS": "סימוס",
             "InGaAs": "אינגאס", "InSb": "אינדיום אנטימוניד", "XBn": "אקס בי אן", "VOx": "וי או אקס",
             "rms": "אר אם אס", "PDF": "פי די אף", "RSS": "אר אס אס", "json": "ג'ייסון", "preset": "פריסט",
             "e-": "אלקטרונים"}
_UNITS = {  # unit after a number: (hebrew, english)
    "µm": ("מיקרון", "microns"), "um": ("מיקרון", "microns"), "mm": ("מילימטר", "millimeters"),
    "cm": ("סנטימטר", "centimeters"), "km": ("קילומטר", "kilometers"), "m": ("מטר", "meters"),
    "mK": ("מילי-קלווין", "millikelvin"), "K": ("קלווין", "kelvin"), "mrad": ("מילירדיאן", "milliradians"),
    "µrad": ("מיקרורדיאן", "microradians"), "urad": ("מיקרורדיאן", "microradians"),
    "ms": ("מילישנייה", "milliseconds"), "Hz": ("הרץ", "hertz"), "°C": ("מעלות צלזיוס", "degrees Celsius"),
    "°": ("מעלות", "degrees"), "%": ("אחוז", "percent"), "1/km": ("לקילומטר", "per kilometer"),
    "e-": ("אלקטרונים", "electrons"), "kg": ("קילוגרם", "kilograms"), "g": ("גרם", "grams"),
    "nm": ("ננומטר", "nanometers"), "s": ("שניות", "seconds"), "W": ("ואט", "watts"),
}
_SYMBOLS = [  # (pattern, hebrew, english) - applied before the units
    (r"Fλ/d", "אף למדא חלקי די", "F lambda over d"), (r"F/#", "אף נאמבר", "F-number"),
    (r"Cn²", "סי-אן בריבוע", "C n squared"), (r"m\^-2/3", "מטר בחזקת מינוס שתיים שליש", "meters to the minus two thirds"),
    (r"ΔT", "דלתא טי", "delta T"), (r"σ", "סיגמה", "sigma"), (r"τ0", "טאו אפס", "tau zero"), (r"τ", "טאו", "tau"),
    (r"λ", "למדא", "lambda"), (r"±", "פלוס מינוס ", "plus or minus "), (r"≤", " עד ", " at most "),
    (r"≈", " בערך ", " about "), (r"~", "בערך ", "about "), (r"²", " בריבוע", " squared"),
    (r"³", " בשלישית", " cubed"), (r'לק"ג', "לקילוגרם", "per kilogram"), (r'ק"ג', "קילוגרם", "kilograms"),
    (r'ק"מ', "קילומטר", "kilometers"), (r'מ"מ', "מילימטר", "millimeters"), (r'ס"מ', "סנטימטר", "centimeters"),
]
_NUM = r"[-+]?\d+(?:\.\d+)?"


def _sci(m, lang):
    mant, exp = m.group(1), int(m.group(2))
    he = lang == "he"
    p = ("עשר בחזקת %s%d" if he else "ten to the %s%d") % (("מינוס " if he else "minus ") if exp < 0 else "", abs(exp))
    if mant in ("1", "1.0"):
        return p
    return "%s %s %s" % (mant, "כפול" if he else "times", p)


def speech(text, lang):
    """What a voice should say for screen text `text`."""
    s = " " + str(text) + " "
    he = lang == "he"
    s = re.sub(r"[★⚠ⓘ✓✕•]", " ", s)
    s = s.replace("…", ".").replace("...", ".")
    s = re.sub(r"(\d(?:\.\d+)?)e([-+]?\d+)", lambda m: _sci(m, lang), s)           # 1e-14
    s = re.sub(r"\$(\d+(?:\.\d+)?)k(?![A-Za-z])", lambda m: "$%d" % round(float(m.group(1)) * 1000), s)  # $1.4k
    s = re.sub(r"\$([\d,]+)\s*[-–]\s*\$([\d,]+)", (r"\1 עד \2 דולר" if he else r"\1 to \2 dollars"), s)
    s = re.sub(r"\$([\d,]+)", (r"\1 דולר" if he else r"\1 dollars"), s)
    s = s.replace("∝", " פרופורציונלי ל" if he else " proportional to ")
    for pat, h, e in _SYMBOLS:
        s = re.sub(pat, h if he else e, s)
    s = re.sub(r"\bF/(\d+(?:\.\d+)?)", (r"אף \1" if he else r"F \1"), s)              # F/4 -> F 4
    s = re.sub(r"(\d)\s*[-–]\s*(?=(?:אף |F )?\d)", r"\1 %s " % ("עד" if he else "to"), s)  # 8-25 -> 8 to 25
    s = re.sub(r"(\d)\s*[x×]\s*(\d)", r"\1 %s \2" % ("על" if he else "by"), s)       # 640x512
    units = sorted(_UNITS, key=len, reverse=True)
    pat = r"(%s)\s*(%s)(?=[\s.,;:)/]|$)" % (_NUM, "|".join(re.escape(u) for u in units))
    s = re.sub(pat, lambda m: "%s %s" % (m.group(1), _UNITS[m.group(2)][0 if he else 1]), s)
    s = re.sub(r"(\d),(\d{3})", r"\1\2", s)
    s = re.sub(r"(\d+\.\d*?[1-9])0+(?!\d)", r"\1", s)                                # 2.50 -> 2.5
    s = re.sub(r"(\d+)\.0+(?!\d)", r"\1", s)                                         # 4.00 -> 4                                           # 1,500 -> 1500
    s = s.replace(" · ", ", ").replace("·", ", ").replace(" - ", ", ").replace(" – ", ", ")
    s = re.sub(r"(?<![\w.])(\w|\d+(?:\.\d+)?)\s/\s(?=\d)", r"\1 %s " % ("חלקי" if he else "divided by"), s)
    s = s.replace(" = ", " שווה " if he else " equals ").replace(" / ", " או " if he else " or ")
    s = re.sub(r"Ctrl\+(\w)", (r"קונטרול \1" if he else r"Control \1"), s)
    s = re.sub(r"\s<\s*(?=\d)", " קטן מ-" if he else " less than ", s)
    s = re.sub(r"\s>\s*(?=\d)", " גדול מ-" if he else " greater than ", s)
    s = s.replace(" > ", ", ")                                                         # menu paths
    s = re.sub(r"[()\[\]{}\"“”]", " ", s) if not he else re.sub(r"[()\[\]{}“”]", " ", s)
    if he:
        for w in sorted(_WORDS_HE, key=len, reverse=True):
            s = re.sub(r"(?<![A-Za-z])%s(?![A-Za-z])" % re.escape(w), _WORDS_HE[w], s)
        # other all-capital acronyms: letter by letter
        s = re.sub(r"(?<![A-Za-z])([A-Z]{2,5})(?![a-z])",
                   lambda m: " ".join(_LETTERS_HE.get(c, c) for c in m.group(1)), s)
        s = re.sub(r"(?<![\u0590-\u05ff])([\u05d1\u05d4\u05d5\u05dc\u05de\u05db\u05e9])-(?=[\u0590-\u05ff])", r"\1", s)   # "\u05d4-IFOV": one word
    else:
        s = re.sub(r"[\u0590-\u05ff\"]+", " ", s)                                     # no Hebrew in English speech
    s = re.sub(r"\s+([.,;:!?])", r"\1", s)
    s = re.sub(r"([.,;:])\1+", r"\1", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,;")
    return s


_SENT = re.compile(r"(?<=[.!?])\s+(?=\S)")


def sentences(text):
    """Split a paragraph into sentences (captions); decimals and abbreviations stay together."""
    out = []
    for part in _SENT.split(str(text).strip()):
        part = part.strip()
        if part:
            out.append(part)
    return out


# --------------------------------------------------------------------------------------------- scripts
# A script is [segment]; a segment is (caption, text) or a callable returning [(caption, text)] when it is reached
# (the effect on the ranges is computed while the card is being read).

def _add(out, text, lang, prefix=""):
    """Add a paragraph as sentences; the caption is the screen text, the voice reads speech()."""
    if not text:
        return
    for i, s in enumerate(sentences(text)):
        cap = (prefix + s) if i == 0 and prefix else s
        out.append((cap, cap))


def _sentence_join(items, lang):
    items = [str(t).strip().rstrip(".") for t in items if str(t).strip()]
    return ". ".join(items) + "." if items else ""


def kb_key(path):
    """Key of the knowledge-base entry of a parameter path (as guide_he.param resolves it)."""
    m = G._ADDITIONAL.match(path or "")
    if m:
        return "additional." + m.group(2)
    if path in G.PARAMS:
        return path
    return re.sub(r"\.\d+\.", ".N.", path or "")


def value_text(v, lang):
    if lang == "he":
        return G._value_text(v)
    if isinstance(v, bool):
        return "on" if v else "off"
    if isinstance(v, dict):
        return v.get("name") or "no file imported"
    if isinstance(v, list):
        return ", ".join(G._n(x) for x in v)
    if v is None or v == "":
        return "empty"
    return G._n(v)


def _he_blocks(blocks, out):
    """Hebrew narration of screen blocks."""
    for b in blocks:
        kind = b[0]
        if kind in ("title", "h", "p", "li", "muted"):
            _add(out, b[1], "he")
        elif kind == "box":
            lines = list(b[2])
            if len(b) > 3 and b[3] and lines:                     # titled box: "title: text"
                head = lines.pop(0).rstrip(":")
                _add(out, head + ".", "he")
            for ln in lines:
                _add(out, ln, "he")
        elif kind == "chips":
            _add(out, _sentence_join([t for t, _s in b[1]], "he"), "he")
        elif kind == "card":
            _add(out, b[1].lstrip("⚠ⓘ ").strip() + ".", "he")
            _add(out, b[2], "he")


# ---- spoken style: screen text written for reading becomes text written for the ear
_HE_CONTEXT_SKIP = ("בגלל", "בלי", "בדרך", "בעיקר", "ביחד", "בפועל", "בכל", "בזמן", "בערך", "ברוב", "במקום", "בין")


def _lower_first(t):
    t = str(t).strip()
    w = t.split(" ", 1)[0]
    return t if (len(w) > 1 and w[:2].isupper()) else t[:1].lower() + t[1:]


def _clause(t, lang):
    """One screen sentence said aloud: equations, brackets and dashes become spoken connections."""
    t = str(t).strip()
    eq = [x.strip() for x in t.rstrip(".").split(" = ")]
    if len(eq) > 2:                              # "A = B = C = D": a chain of consequences
        mid = (", כלומר " if lang == "he" else ", which means ")
        then = (", ולכן " if lang == "he" else ", and so ")
        t = eq[0] + mid + eq[1] + "".join(then + x for x in eq[2:]) + "."
    elif len(eq) == 2 and len(eq[0].split()) > 1 and not re.search(r"[\d/]", eq[0][-3:]):
        t = eq[0] + (" פירושו " if lang == "he" else " means ") + eq[1] + "."   # "A = B" in prose
    t = re.sub(r"\s*\((גמישות|elasticity)\s+([^)]*)\)", lambda m: (", עם גמישות של " if lang == "he"
                                                                   else ", with an elasticity of ") + m.group(2), t)
    t = re.sub(r"\s*\(([^()]{1,80})\)", r", \1,", t)
    t = re.sub(r",\s*([.;:])", r"\1", t)
    return t


def _connect(sentences, lang):
    """Discourse markers between the sentences of a paragraph: an example, a contrast, a consequence."""
    out, contexts = [], 0
    for i, x in enumerate(sentences):
        x = _clause(x, lang)
        if i == 0:
            out.append(x)
            continue
        w = x.split(" ", 1)[0]
        if lang == "he":
            ctx = (w.startswith("ב-") or (w.startswith("ב") and len(w) > 2 and not w.startswith(_HE_CONTEXT_SKIP)))
            if ctx:
                x = ("למשל, " if contexts == 0 else "לעומת זאת, ") + x
                contexts += 1
            elif w[:1].isdigit() or w in ("מעבר", "חציית", "הזזה"):
                x = "למשל, " + x
            elif w == "בלי":
                x = "ושימו לב: " + x
        else:
            ctx = w in ("In", "At", "On", "For", "With", "By") and i > 0
            if ctx:
                x = ("For example, " if contexts == 0 else "By contrast, ") + _lower_first(x)
                contexts += 1
            elif w[:1].isdigit() or w in ("Going", "Halving", "Moving"):
                x = "For example, " + _lower_first(x)
            elif w == "Without":
                x = "And note: " + _lower_first(x)
        out.append(x)
    return out


def _para(out, text, lang, lead=""):
    """A paragraph of reference text, said with connections; `lead` is the spoken question that opens it."""
    if not text:
        return
    sents = _connect(sentences(text), lang)
    if lead:
        sents[0] = lead + " " + sents[0]
    for x in sents:
        out.append((x, x))


def _typical(items, lang):
    """Typical values as one spoken thought: 'in a handheld camera, 25 to 75 mm; and in ...'."""
    parts = []
    for it in items:
        it = str(it).strip().rstrip(".")
        if ": " not in it:
            parts.append(it)
            continue
        k, v = it.split(": ", 1)
        if lang == "he":
            if k.startswith(("יש ", "אין ")):
                k = "אם " + k
            elif not k.startswith(("כש", "אם ", "ב")):
                k = ("ב-" + k) if not ("\u0590" <= k[:1] <= "\u05ff") else "ב" + k
        else:
            low = _lower_first(k)
            verbish = re.search(r"\b(is|are|gives|has|have|needs|known|sees)\b", low)
            k = ("if " if verbish else "for ") + low
        parts.append("%s, %s" % (k, v))
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0] + "."
    last = ("ו" + parts[-1]) if lang == "he" else ("and " + parts[-1])
    return "; ".join(parts[:-1]) + "; " + last + "."


def _source(text, lang):
    """The source as a spoken answer: 'the lens datasheet' -> 'the source is the lens datasheet'."""
    if lang != "he":
        return text
    w = str(text).split(" ", 1)[0]
    if (w.endswith("ו") and len(w) > 3) or w.startswith(("אם", "כש", "אלה", "יש", "אין")):   # an instruction
        return text
    return "המקור הוא " + text


def _mistakes(items, lang):
    items = [str(m).strip().rstrip(".") for m in items if str(m).strip()][:2]
    if not items:
        return []
    if lang == "he":
        out = ["ועוד טיפ מניסיון. הטעות שאני פוגש הכי הרבה היא %s." % items[0]]
        if len(items) > 1:
            out.append("וטעות נוספת, שכדאי להיזהר ממנה: %s." % items[1])
    else:
        out = ["And a tip from experience. The mistake I see most often is %s." % _lower_first(items[0])]
        if len(items) > 1:
            out.append("Another one to watch out for: %s." % _lower_first(items[1]))
    return out


def field_script(lang, path, value, project, label=None, impact=None, brief=False):
    """Spoken lesson on a field, built the way a teacher explains (Feynman: simple words and an analogy, then the
    listener's own case, then a short recap), with signposts between the parts:
      opening -> "so what is it?" the idea -> "why does it matter?" -> "which numbers do you meet?" -> "where from?"
      -> "now let's look at yours": the value, the suggestion, the effect on the ranges -> a tip -> "to sum up".
    impact: callable returning the guide_impact result (None while running).  brief: the walk through a group
    (opening, idea, why, the user's value, recap)."""
    e = G.param(path)
    if not e:
        return []
    key = kb_key(path)
    out = []
    imp = e.get("impact", 1)
    res = G.check(path, value, project) if project is not None else None
    sug = G.suggestion(res)
    pick = lambda part, *sub: T.pick(lang, part, key, *sub)
    lesson = (T.LESSON.get(key) or {}).get(lang)
    he = lang == "he"
    if he:
        title, what, why = e["title"], e.get("what"), e.get("why")
        typical, source, mistakes = e.get("typical"), e.get("source"), e.get("mistakes")
    else:
        en = EN.PARAMS.get(key) or {}
        title = en.get("title") or label or path
        what, why = en.get("what"), en.get("why")
        typical, source, mistakes = en.get("typical"), en.get("source"), en.get("mistakes")
    t = _bare(title)
    # 1. opening, and what we are going to cover
    _add(out, lesson[0] if lesson else T.intro(lang, key, imp, t), lang)
    if not brief and imp >= 2:
        _add(out, pick("preview"), lang)
    # 2. the idea
    if lesson:
        _para(out, lesson[1], lang, pick("idea_q"))
    elif what:
        _para(out, what, lang, pick("idea_q"))
    # 3. why it matters
    if why:
        _para(out, why, lang, pick("why"))
    if not brief:
        # 4. a feel for the numbers, and where the value comes from
        if typical:
            _add(out, pick("typical") + " " + _typical(typical, lang), lang)
        if source and imp:
            _para(out, _source(source, lang), lang, pick("source"))
    # 5. the listener's own value
    if res:
        v = value_text(value, lang)
        _add(out, pick("yours"), lang)
        if res[0] == "ok":
            _add(out, pick("ok").format(v=v), lang)
        else:
            _add(out, pick("warn").format(v=v), lang)
            if he:
                _para(out, res[1], lang, "והסיבה:")
            else:
                _add(out, FRAME_EN_WARN, lang)
        if sug is not None:
            _add(out, pick("suggest").format(s=value_text(sug, lang)), lang)
    if not brief:
        if impact is not None and imp != 0:
            def later():                                # None while the model is still running
                r = impact()
                if r is None:
                    return None
                body = impact_script(lang, r)
                return ([(pick("impact"), pick("impact"))] + body) if body else []
            out.append(later)
        if he and project is not None:
            try:
                from . import guide_design_he as DS
                design = DS.blocks(path, project)
            except Exception:
                design = []
            lis = [x[1] for x in design if x[0] == "li"]
            size = [x for x in lis if x.startswith("משקל")][:1]
            cost = [x for x in lis if x.startswith("ייצור")][:1]
            est = [ln for x in design if x[0] == "box" for ln in x[2][1:]
                   if ln.startswith(("חומר הגלם", "מקרר Stirling"))][:1]
            if size or cost or est:
                _add(out, "ודבר אחד שחשוב לדעת, מעבר לטווח: מה הערך הזה מחייב מהמערכת עצמה, במשקל, בייצור ובכסף.",
                     lang)
                for x in size:
                    _para(out, re.sub(r"^משקל / גודל:\s*", "", x), lang, "מבחינת משקל וגודל,")
                for x in cost:
                    _para(out, re.sub(r"^ייצור ועלות:\s*", "", x), lang, "ומבחינת ייצור ועלות,")
                for x in est:
                    _para(out, x, lang, "ובמערכת שלכם, בהערכה גסה:")
        # 6. a tip
        for x in _mistakes(mistakes or [], lang):
            _add(out, x, lang)
        if not he and not EN.PARAMS.get(key):
            _add(out, "The card on the screen has the full explanation of this field, in Hebrew.", lang)
    # 7. recap
    _add(out, lesson[2] if lesson else pick("bottom", imp), lang)
    return out


def _bare(title):
    """A title as said inside a sentence: without the bracketed symbol, '(f)' or '(τ)'."""
    return re.sub(r"\s*\([^)]{1,6}\)\s*$", "", str(title)).strip()


FRAME_EN_WARN = "The note on the screen explains exactly what looks wrong."


def impact_script(lang, res):
    """Narration of the effect on the ranges (guide_impact result)."""
    out = []
    if not res or res.get("base") is None:
        return out
    from . import guide_impact as GI
    base = res["base"]
    if lang == "he":
        _add(out, "כרגע, עם הערכים שלכם, הטווחים הם: %s." % GI.ranges_line(base), lang)
    else:
        _add(out, "Right now, with your values, the ranges are: %s." % _ranges_en(base), lang)
    worst = 0.0
    for label, v, r, _e, _ch in res.get("alts") or []:
        if not r:
            continue
        parts = []
        for t, R in r.items():
            R0 = base.get(t)
            if R0:
                pct = 100.0 * (R - R0) / R0
                worst = pct if abs(pct) > abs(worst) else worst
                if lang == "he":
                    parts.append("%s %s ק\"מ, %s" % (GI.TASK_HE.get(t, t), GI._km(R), _pct_he(pct)))
                else:
                    parts.append("%s %s kilometers, %s" % (t.lower(), GI._km(R), _pct_en(pct)))
        if not parts:
            continue
        val = value_text(v, lang) if not isinstance(v, str) else (v if label == "הערך המוצע" else label)
        if lang == "he":
            _add(out, "עם %s: %s." % ("הערך המוצע, " + val if label == "הערך המוצע" else val, "; ".join(parts)), lang)
        else:
            _add(out, "With %s: %s." % ("the suggested value, " + val if label == "הערך המוצע" else val,
                                        "; ".join(parts)), lang)
    if res.get("alts"):
        if lang == "he":
            _add(out, "כלומר: " + GI.verdict(worst) + ".", lang)
        else:
            a = abs(worst)
            _add(out, "In other words, " + ("almost no effect in your system." if a < 2 else "a small effect."
                                            if a < 8 else "a medium effect." if a < 20 else "a large effect."), lang)
    return out


def _pct_he(p):
    if abs(p) < 0.5:
        return "ללא שינוי"
    return "%s %.0f אחוז" % ("עלייה של" if p > 0 else "ירידה של", abs(p))


def _pct_en(p):
    if abs(p) < 0.5:
        return "no change"
    return "%s %.0f percent" % ("up" if p > 0 else "down", abs(p))


def _ranges_en(r):
    from . import guide_impact as GI
    return ", ".join("%s %s kilometers" % (t.lower(), GI._km(v)) for t, v in r.items())


def step_script(lang, lesson_id, step, field_args=None, labels=None):
    """Narration of a lesson step.  field_args: dict(path=..., value=..., project=..., label=..., impact=...)
    for a step that shows a field card; labels: {path: form label} for a group step of the tour."""
    out = []
    key = (lesson_id, step["title"])
    spoken = T.HE_STEPS.get(key) if lang == "he" else (EN.STEPS.get(key) or (None, None))[1]
    if spoken:
        for para in spoken:
            _add(out, para, lang)
    elif step.get("group") and step.get("page"):
        page = step["page"]
        first = bool(step.get("blocks")) and step["blocks"][0][0] == "box"
        if lang == "he":
            he, desc = G.PAGE_HE.get(page, (page, ""))
            _add(out, ("נעבור לעמוד %s. בעמוד הזה: %s" % (he, desc)) if first else "נמשיך באותו עמוד, %s." % he, lang)
        else:
            _add(out, ("Let's move to the %s page. This page covers %s" % (page, EN.PAGES.get(page, ""))) if first
                 else "We continue on the %s page." % page, lang)
    elif lang == "he" and step.get("blocks"):
        _he_blocks(list(step["blocks"]), out)
    if step.get("fields") and labels is not None:
        out += group_script(lang, step["fields"], labels, (field_args or {}).get("project"),
                            (field_args or {}).get("values") or {})
    elif field_args and field_args.get("path") and not step.get("group"):
        out += field_script(lang, **{k: v for k, v in field_args.items() if k != "values"})
    elif step.get("path") and not step.get("group") and not spoken:
        _add(out, step["title"] + ".", lang)
    if step.get("action") == "calculate" and not spoken:
        _add(out, "תחשבו עכשיו, עם F5." if lang == "he" else "Calculate now, with F5.", lang)
    if lesson_id and lesson_id != "tour" and step.get("path") and not step.get("group"):
        _add(out, T.pick(lang, "next", step.get("path")), lang)
    return out


def group_script(lang, paths, labels, project, values):
    """Narration of a group of fields of the tour: each field in one or two sentences."""
    out = []
    n_warn = 0
    for path in paths:
        e = G.param(path)
        if not e:
            continue
        res = G.check(path, values.get(path), project) if project is not None else None
        warn = res and res[0] == "warn"
        n_warn += bool(warn)
        imp = e.get("impact", 1)
        if lang == "he":
            text = "%s: אצלכם %s. %s." % (e["title"], G._value_text(values.get(path)), G.IMPACT_TEXT[imp])
            if warn:
                text += " ופה כדאי לעצור: " + res[1]
        else:
            en = EN.PARAMS.get(kb_key(path))
            title = (en or {}).get("title") or labels.get(path) or path
            text = "%s: you have %s. %s." % (title, value_text(values.get(path), lang), EN.IMPACT[imp])
            if warn:
                text += " This one is worth a second look."
        _add(out, text, lang)
    if lang == "he":
        _add(out, "רוצים להעמיק באחד מהם? לחצו עליו, ואסביר לכם אותו לעומק.", lang)
    else:
        _add(out, "Want to go deeper into one of them? Click it, and I will explain it in detail.", lang)
    return out


def _names(titles, lang):
    titles = [t for t in titles if t]
    if len(titles) <= 1:
        return "".join(titles)
    if lang == "he":
        last = titles[-1]
        return ", ".join(titles[:-1]) + (" ו-" if not ("\u0590" <= last[:1] <= "\u05ff") else " ו") + last
    return ", ".join(titles[:-1]) + " and " + titles[-1]


def _title_of(path, lang, label=None):
    e = G.param(path) or {}
    if lang == "he":
        return _bare(e.get("title", path))
    return _bare((EN.PARAMS.get(kb_key(path)) or {}).get("title") or label or path)


def walk_script(lang, items, on_field, on_end, intro=()):
    """Narration that walks through fields one by one, as a teacher at the board: it says what the group holds
    (preview), explains each field while it is highlighted (on_field(path, i, n) is called when the narration reaches
    it), closes each one before opening the next (callback), and recaps the group at the end (on_end())."""
    out = list(intro)
    he = lang == "he"
    titles = [_title_of(it["path"], lang, it.get("label")) for it in items]
    n = len(items)
    if n == 1:
        _add(out, "בקבוצה הזו יש שדה אחד: %s. אסמן אותו בטופס ונעבור עליו." % titles[0] if he else
             "This group has one field: %s. I will highlight it in the form and we will go over it." % titles[0], lang)
    elif n > 1:
        if n <= 5:
            _add(out, ("בקבוצה הזו יש %d שדות: %s." % (n, _names(titles, lang))) if he else
                 ("This group has %d fields: %s." % (n, _names(titles, lang))), lang)
        else:
            _add(out, ("בקבוצה הזו יש %d שדות." % n) if he else ("This group has %d fields." % n), lang)
        _add(out, "אעבור איתכם על כל אחד מהם, ואסמן אותו בטופס כדי שתראו בדיוק על מה מדובר." if he else
             "I will go through each of them with you, and highlight it in the form so you can see exactly what "
             "we are talking about.", lang)
    for i, it in enumerate(items):
        if i:
            _add(out, T.transition(lang, it["path"], titles[i - 1], titles[i]), lang)
        out.append({"do": lambda p=it["path"], i=i: on_field(p, i, n)})
        out += field_script(lang, it["path"], it.get("value"), it.get("project"), it.get("label"), brief=True)
    if n > 1:
        _add(out, ("זהו, סיימנו את הקבוצה. עברנו על %s." % _names(titles, lang)) if he and n <= 5 else
             "זהו, סיימנו את הקבוצה." if he else
             ("That's it for this group. We covered %s." % _names(titles, lang)) if n <= 5 else
             "That's it for this group.", lang)
    out.append({"do": on_end})
    return out


def home_script(lang, lessons, done):
    out = []
    if lang == "he":
        _add(out, "שלום, אני המנחה של המדריך. בחרו שיעור: כל שיעור מוביל אתכם על המסכים האמיתיים, מסמן את השדה "
                  "ובודק את הערך שהזנתם.", lang)
        for les in lessons:
            _add(out, "%s%s. %s" % (les["title"], ", הושלם" if les["id"] in done else "", les["summary"]), lang)
        _add(out, "אפשר גם לבדוק את כל הערכים בבת אחת, וכשהמדריך פתוח, לחיצה על שדה בטופס מציגה כאן הסבר עליו.", lang)
    else:
        _add(out, "Hello, I am the narrator of the guide. " + EN.HOME, lang)
        for les in lessons:
            t, s = EN.LESSONS.get(les["id"], (les["id"], ""))
            _add(out, "%s%s. %s" % (t, ", completed" if les["id"] in done else "", s), lang)
    return out


def review_script(lang, review, ranges=None):
    """Narration of the review (guide_he.review result)."""
    out = []
    warn = review["warn"]
    if lang == "he":
        _add(out, "בדיקת כל הערכים. נבדקו %d שדות: %d תקינים ו-%d לבדיקה." % (review["n"], review["ok"], len(warn)),
             lang)
        if ranges and ranges.get("base"):
            from . import guide_impact as GI
            _add(out, "הטווחים עכשיו: %s." % GI.ranges_line(ranges["base"]), lang)
        if not warn:
            _add(out, "לא נמצאו ערכים חשודים. עדיין כדאי להחליף ערכי פריסט בנתוני המערכת שלכם.", lang)
        for i, (_imp, path, _page, res) in enumerate(warn[:6]):
            _add(out, "%s: %s" % (("ההערה הראשונה, " if i == 0 else "") + G.param(path)["title"], res[1]), lang)
        if len(warn) > 6:
            _add(out, "ועוד %d הערות ברשימה." % (len(warn) - 6), lang)
    else:
        _add(out, "Checking all the values. %d fields were checked: %d are fine and %d need a check." %
             (review["n"], review["ok"], len(warn)), lang)
        if ranges and ranges.get("base"):
            _add(out, "The ranges now: %s." % _ranges_en(ranges["base"]), lang)
        if not warn:
            _add(out, "No suspicious values were found. It is still worth replacing preset values with the data of "
                      "your system.", lang)
        else:
            names = []
            for _imp, path, _page, _res in warn[:6]:
                en = EN.PARAMS.get(kb_key(path))
                names.append((en or {}).get("title") or path.split(".")[-1])
            _add(out, "The notes are sorted by their impact on the range. Start with: %s." % ", ".join(names), lang)
            _add(out, "Click a note to open the field, with the explanation on the screen.", lang)
    return out


def static_texts(lang):
    """Every fixed sentence of the guide, as said: the texts that get a recording (tools/make_guide_voice.py)."""
    out = []

    def take(script):
        for seg in script:
            if not callable(seg) and not isinstance(seg, dict):
                out.append(speech(seg[1], lang))

    for path in G.PARAMS:
        if lang == "en" and path not in EN.PARAMS:
            continue
        take(field_script(lang, path.replace(".N.", ".0."), None, None))
    for les in G.LESSONS:
        for st in les["steps"]:
            take(step_script(lang, les["id"], st))
    take(home_script(lang, G.LESSONS, set()))
    out.append(speech("אעבור איתכם על כל אחד מהם, ואסמן אותו בטופס כדי שתראו בדיוק על מה מדובר." if lang == "he" else
                      "I will go through each of them with you, and highlight it in the form so you can see exactly "
                      "what we are talking about.", lang))
    for path in G.PARAMS:
        if lang == "en" and path not in EN.PARAMS:
            continue
        take(field_script(lang, path.replace(".N.", ".0."), None, None, brief=True))
    for les in G.LESSONS:
        take(home_script(lang, [les], {les["id"]}))
    if lang == "en":
        for page in EN.PAGES:
            take(step_script(lang, "tour", {"title": "", "group": True, "page": page,
                                            "blocks": [("box", "info", [""], True)]}))
            take(step_script(lang, "tour", {"title": "", "group": True, "page": page}))
    for page, (he, desc) in G.PAGE_HE.items():
        if lang == "he":
            take(step_script(lang, "tour", {"title": "", "blocks": [("box", "info", ["עמוד %s (%s)" % (he, page),
                                                                                       desc], True)]}))
    for st in G.tour_steps([], {}, lambda *a: True):
        take(step_script(lang, "tour", st))
    seen, uniq = set(), []
    for s in out:
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def en_sources():
    """{key: hash of the Hebrew text} of everything guide_voice_en translates (to find stale translations)."""
    out = {}
    for path in EN.PARAMS:
        e = G.PARAMS.get(path)
        if e:
            src = {f: e.get(f) for f in ("title", "impact_note", "what", "why", "typical", "source", "mistakes")}
            out["param:" + path] = hashlib.sha1(json.dumps(src, ensure_ascii=False, sort_keys=True)
                                                .encode("utf-8")).hexdigest()[:12]
    steps = {(les["id"], st["title"]): st for les in G.LESSONS for st in les["steps"]}
    for st in G.tour_steps([], {}, lambda *a: True):
        steps[("tour", st["title"])] = st
    for (lid, title) in EN.STEPS:
        st = steps.get((lid, title))
        if st:
            src = json.dumps([title] + [list(b) if isinstance(b, tuple) else b for b in st.get("blocks", [])],
                             ensure_ascii=False, default=str)
            out["step:%s|%s" % (lid, title)] = hashlib.sha1(src.encode("utf-8")).hexdigest()[:12]
    return out


# --------------------------------------------------------------------------------------------- voices
NEURAL = {"he": "he-IL-AvriNeural", "en": "en-US-AndrewNeural"}     # voices of the recordings


def rec_key(lang, text):
    return hashlib.sha1(("%s|%s" % (lang, text)).encode("utf-8")).hexdigest()[:16]


_rec_index = {}


def recording(lang, text):
    """Path of the recording of a sentence (as said), or None."""
    if lang not in _rec_index:
        d = os.path.join(VOICE_DIR, lang)
        try:
            _rec_index[lang] = {f[:-4] for f in os.listdir(d) if f.endswith(".mp3")}
        except OSError:
            _rec_index[lang] = set()
    k = rec_key(lang, text)
    return os.path.join(VOICE_DIR, lang, k + ".mp3") if k in _rec_index[lang] else None


def has_recordings(lang):
    recording(lang, "")
    return bool(_rec_index.get(lang))


_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_voices = None
_voices_lock = threading.Lock()


def _powershell(args, timeout):
    exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0",
                       "powershell.exe")
    cmd = [exe if os.path.exists(exe) else "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
           "Bypass", "-File", PS_SCRIPT] + args
    return subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=_NO_WINDOW)


def live_voices():
    """{lang: voice name} of the voices built into Windows (cached; runs PowerShell once)."""
    global _voices
    with _voices_lock:
        if _voices is None:
            _voices = {}
            if sys.platform == "win32" and os.path.exists(PS_SCRIPT):
                try:
                    r = _powershell(["-List"], 30)
                    for line in r.stdout.decode("utf-8", "replace").splitlines():
                        if "|" in line:
                            cult, name = line.strip().split("|", 1)
                            lang = cult.split("-")[0].lower()
                            _voices.setdefault(lang, name)
                except (OSError, subprocess.SubprocessError):
                    pass
        return dict(_voices)


def available(lang):
    """'recorded' | 'live' | None: how this language can be heard on this computer."""
    if sys.platform != "win32":
        return None
    if has_recordings(lang):
        return "recorded"
    return "live" if lang in live_voices() else None


def synthesize(lang, texts, rate, folder):
    """Say `texts` with the Windows voice into WAV files of `folder` -> [path] (files appear one by one)."""
    outs = [os.path.join(folder, "s%03d.wav" % i) for i in range(len(texts))]
    job = os.path.join(folder, "job.json")
    with open(job, "w", encoding="utf-8") as f:
        json.dump({"lang": CULTURE[lang], "rate": rate,
                   "items": [{"text": t, "out": o} for t, o in zip(texts, outs)]}, f, ensure_ascii=False)
    try:
        _powershell(["-Job", job], 60 + 10 * len(texts))
    except (OSError, subprocess.SubprocessError):
        pass
    return outs


# --------------------------------------------------------------------------------------------- player
class _Mci:
    """Windows MCI player (winmm): open / play / pause / status of one file at a time."""

    def __init__(self):
        self.ok = sys.platform == "win32"
        self.n = 0
        self.alias = None
        if self.ok:
            try:
                self._send = ctypes.windll.winmm.mciSendStringW
            except (AttributeError, OSError):
                self.ok = False

    def cmd(self, s):
        buf = ctypes.create_unicode_buffer(256)
        err = self._send(s, buf, 255, 0)
        return err, buf.value

    def play(self, path, speed=1.0):
        self.close()
        self.n += 1
        alias = "trmvoice%d" % self.n
        err, _ = self.cmd('open "%s" type mpegvideo alias %s' % (path, alias))
        if err:
            return False
        self.alias = alias
        if abs(speed - 1.0) > 0.01:
            self.cmd("set %s speed %d" % (alias, int(round(speed * 1000))))
        err, _ = self.cmd("play %s" % alias)
        return not err

    def mode(self):
        if not self.alias:
            return "stopped"
        err, val = self.cmd("status %s mode" % self.alias)
        return "stopped" if err else val

    def pause(self):
        if self.alias:
            self.cmd("pause %s" % self.alias)

    def resume(self):
        if self.alias:
            self.cmd("resume %s" % self.alias)

    def close(self):
        if self.alias:
            self.cmd("stop %s" % self.alias)
            self.cmd("close %s" % self.alias)
            self.alias = None


class Narrator:
    """Says a script sentence by sentence.  on_change(state, caption) is called on the Tk thread:
    state 'idle' | 'loading' | 'playing' | 'paused'."""

    POLL_MS = 90

    def __init__(self, widget, on_change):
        self.w = widget
        self.on_change = on_change
        self.mci = _Mci()
        self.state = "idle"
        self.caption = ""
        self.lang = "he"
        self._queue = []
        self._gen = 0
        self._job = None
        self._live = {}            # sentence index -> wav path (being synthesized)
        self._tmp = None
        self.rate = 1.0

    # ---- control
    def speak(self, script, lang, rate=1.0):
        self.stop()
        self._gen += 1
        self.lang, self.rate = lang, rate
        self._queue = list(script)
        self._pos = 0
        self._tmp = tempfile.mkdtemp(prefix="trm_voice_")
        self._prefetch()
        self._set("loading", "")
        self._next()

    def toggle_pause(self):
        if self.state == "playing":
            self.mci.pause()
            self._set("paused", self.caption)
        elif self.state == "paused":
            self.mci.resume()
            self._set("playing", self.caption)

    def stop(self):
        self._gen += 1
        if self._job:
            try:
                self.w.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        self.mci.close()
        self._queue, self._live = [], {}
        if self.state != "idle":
            self._set("idle", "")

    # ---- internals
    def _set(self, state, caption):
        if (state, caption) == (self.state, self.caption):
            return
        self.state, self.caption = state, caption
        try:
            self.on_change(state, caption)
        except Exception:
            pass

    def _prefetch(self, start=0):
        """Synthesize, in a worker thread, the sentences that have no recording (up to the next lazy segment)."""
        items = []
        for i in range(start, len(self._queue)):
            seg = self._queue[i]
            if callable(seg):
                break
            if isinstance(seg, dict) or i in self._live:
                continue
            text = speech(seg[1], self.lang)
            if text and not recording(self.lang, text):
                items.append((i, text))
        if not items:
            return
        gen, folder = self._gen, os.path.join(self._tmp, "b%d" % start)
        os.makedirs(folder, exist_ok=True)
        outs = [os.path.join(folder, "s%03d.wav" % n) for n in range(len(items))]
        for (i, _t), o in zip(items, outs):
            self._live[i] = o

        def work():
            if gen == self._gen:
                synthesize(self.lang, [t for _i, t in items], self.rate, folder)
                for o in outs:                                  # failed sentences: mark as missing
                    if not os.path.exists(o):
                        open(o + ".fail", "w").close()

        threading.Thread(target=work, daemon=True).start()

    def _expand(self, i, early=False):
        """Replace the lazy segment at i by its sentences; early: only if its data is ready (not None)."""
        try:
            segs = self._queue[i]()
        except Exception:
            segs = []
        if segs is None and early:
            return
        segs = segs or []
        self._queue[i:i + 1] = segs
        self._live = {j if j < i else j + len(segs) - 1: p for j, p in self._live.items()}
        if segs:
            self._prefetch(i)

    def _next(self):
        gen = self._gen
        while self._pos < len(self._queue) and (callable(self._queue[self._pos]) or
                                                isinstance(self._queue[self._pos], dict)):
            seg = self._queue[self._pos]
            if isinstance(seg, dict):                          # an action: highlight a field, open its card
                self._pos += 1
                try:
                    seg["do"]()
                except Exception:
                    pass
                if gen != self._gen:                           # the action started something else
                    return
                continue
            self._expand(self._pos)
        if self._pos >= len(self._queue):
            self.mci.close()
            self._set("idle", "")
            return
        cap, text = self._queue[self._pos]
        said = speech(text, self.lang)
        path = recording(self.lang, said) if said else None
        if path is None and said:
            path = self._live.get(self._pos)
            if path is None:
                self._prefetch(self._pos)
                path = self._live.get(self._pos)
            if path is None or not os.path.exists(path):
                if path and os.path.exists(path + ".fail"):
                    self._pos += 1
                    return self._next()
                self._set("loading", cap)
                self._job = self.w.after(self.POLL_MS, lambda: gen == self._gen and self._next())
                return
        if not said:
            self._pos += 1
            return self._next()
        speed = self.rate if path.endswith(".mp3") else 1.0      # live speech is synthesized at the rate
        if not self.mci.play(path, speed):
            self._pos += 1
            return self._next()
        self._set("playing", cap)
        nxt = self._pos + 1                                    # prepare the next computed part while this is said
        if nxt < len(self._queue) and callable(self._queue[nxt]):
            self._expand(nxt, early=True)
        self._job = self.w.after(self.POLL_MS, lambda: self._poll(gen))

    def _poll(self, gen):
        if gen != self._gen:
            return
        if self.state == "paused":
            self._job = self.w.after(self.POLL_MS, lambda: self._poll(gen))
            return
        if self.mci.mode() == "playing":
            self._job = self.w.after(self.POLL_MS, lambda: self._poll(gen))
            return
        self._pos += 1
        self._next()
