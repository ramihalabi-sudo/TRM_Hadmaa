"""Ask Gemini what can be improved and added to TRM_HADMAAv1, and for a work plan (in Hebrew).

    py tools/gemini_review.py                  # writes reports/gemini_review_<date>.md
    py tools/gemini_review.py --dry-run        # only shows what would be sent and its size in tokens

Sends the documentation (README, CHANGELOG, user guide), an outline of every module (docstrings, classes,
functions) and the full source of the engineering modules.  The guide texts, recordings and help texts are
left out (content, not logic).  Uses the same Gemini key as tools/voice_gemini.py.
"""
import argparse
import ast
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

MODELS = ["gemini-3.1-pro-preview", "gemini-3.8-flash"]   # the first one that answers is used
DOCS = ["README.md", "CHANGELOG.md", "USER_GUIDE_HE.md"]
# full source: the calculation and the main window; the rest is sent as an outline only
FULL = ["physics.py", "model.py", "analysis.py", "advisor.py", "mtf.py", "scenario.py", "derived.py",
        "amop.py", "presets.py", "profiles.py", "imports.py", "zemax.py", "labtools.py", "report.py",
        "extensions.py", "detector_lookup.py", "gui.py"]
TOKEN_BUDGET = 800_000

PROMPT = """אתה מהנדס מערכות אלקטרו-אופטיות בכיר ומהנדס תוכנה. לפניך התיעוד והקוד של TRM_HADMAAv1:
תוכנה בפייתון (Tkinter) שמחשבת טווחי גילוי, הכרה וזיהוי של מצלמות תרמיות ונראות לפי מודל TRM4,
עם ניתוח רגישות, יועץ לשיפור הטווח, דוחות בעברית ומדריך קולי.

כתוב בעברית, בפורמט Markdown, דוח עם הפרקים האלה:

1. **תקציר** – 5–8 שורות: מצב התוכנה והכיוונים החשובים ביותר.
2. **בעיות ונקודות תורפה** – באגים אפשריים, חישובים שאינם תואמים את TRM4 או את הפיזיקה, יחידות,
   מקרי קצה, ביצועים ויציבות. לכל פריט: קובץ ופונקציה, מה הבעיה, למה זה חשוב, ואיך לתקן.
   ציין רק מה שאתה רואה בקוד, וסמן במפורש מה ודאי ומה חשד שצריך לבדוק.
3. **שיפורים לתוכנה הקיימת** – ממשק ונוחות, דוחות, המדריך, בדיקות, אריזה והתקנה.
4. **יכולות חדשות להוספה** – מה חסר למשתמש מקצועי (מהנדס מערכת, אנשי ניסויים, מקבלי החלטות),
   כולל מודלים פיזיקליים, ייבוא וייצוא, השוואת מערכות, אימות מול מדידות. לכל אחת: ערך, מורכבות.
5. **תוכנית עבודה** – טבלה לפי סדר עדיפויות, מחולקת לשלבים (מיידי / קצר טווח / המשך):
   משימה, קבצים מושפעים, היקף משוער (ימים), תלויות, ואיך בודקים שהמשימה הושלמה.

היה ממוקד ומעשי, הימנע מהמלצות כלליות שאינן קשורות לקוד הזה.
"""


def outline(path):
    """Docstring, classes and function signatures (with the first docstring line) of a module."""
    src = open(path, encoding="utf-8").read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return "  (cannot parse: %s)" % e
    out = []
    doc = ast.get_docstring(tree)
    if doc:
        out.append('  """%s"""' % doc.strip().splitlines()[0])

    def walk(nodes, ind):
        for n in nodes:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(n, ast.ClassDef) else "def"
                args = "" if kind == "class" else "(%s)" % ", ".join(a.arg for a in n.args.args)
                d = ast.get_docstring(n)
                line = "%s%s %s%s" % (ind, kind, n.name, args)
                if d:
                    line += "  # " + d.strip().splitlines()[0][:120]
                out.append(line)
                if kind == "class":
                    walk(n.body, ind + "    ")
    walk(tree.body, "  ")
    return "\n".join(out)


def gather():
    parts = []
    for d in DOCS:
        p = os.path.join(ROOT, d)
        if os.path.exists(p):
            parts.append("=== %s ===\n%s" % (d, open(p, encoding="utf-8").read()))
    pkg = os.path.join(ROOT, "trm4")
    mods = sorted(f for f in os.listdir(pkg) if f.endswith(".py"))
    parts.append("=== outline of every module in trm4/ ===\n" +
                 "\n".join("trm4/%s\n%s" % (m, outline(os.path.join(pkg, m))) for m in mods))
    for m in FULL:
        p = os.path.join(pkg, m)
        if os.path.exists(p):
            parts.append("=== trm4/%s (full source) ===\n%s" % (m, open(p, encoding="utf-8").read()))
    tests = os.path.join(ROOT, "tests")
    if os.path.isdir(tests):
        names = sorted(f for f in os.listdir(tests) if f.endswith(".py"))
        parts.append("=== tests/ ===\n" + "\n".join("tests/%s\n%s" % (t, outline(os.path.join(tests, t)))
                                                     for t in names))
    return parts


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", help="one model instead of the default list")
    ap.add_argument("--out", default=os.path.join(ROOT, "reports", "gemini_review_%s.md" % datetime.date.today()))
    a = ap.parse_args()

    import voice_gemini as V
    from google.genai import types
    c = V.client()
    parts = gather()
    models = [a.model] if a.model else MODELS
    while True:
        n = c.models.count_tokens(model=models[-1], contents=[PROMPT] + parts).total_tokens
        if n <= TOKEN_BUDGET or len(parts) <= 2:
            break
        parts.pop()                     # drop the last full-source file until it fits
    print("sending %d parts, %d tokens" % (len(parts), n))
    if a.dry_run:
        for p in parts:
            print("  " + p.splitlines()[0])
        return
    last = None
    for m in models:
        try:
            r = c.models.generate_content(model=m, contents=[PROMPT] + parts,
                                          config=types.GenerateContentConfig(temperature=0.3))
            text = r.text
            if text and text.strip():
                break
        except Exception as e:          # quota or an unavailable model: the next one
            last = e
            print("%s failed: %s" % (m, str(e)[:300]))
    else:
        raise SystemExit("no model answered: %s" % last)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("# סקירת Gemini לשיפור TRM_HADMAAv1\n\n")
        f.write("נוצר ב-%s במודל %s, מתוך %d חלקי תיעוד וקוד (%d tokens).\n\n" % (
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), m, len(parts), n))
        f.write(text)
    print("written", a.out)


if __name__ == "__main__":
    main()
