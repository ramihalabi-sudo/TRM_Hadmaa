"""Version history report: CHANGELOG.md -> reports/version_history.html (Hebrew, right-to-left) and a console summary.

    python tools/version_report.py            write the HTML report and print the summary
    python tools/version_report.py --text     print the summary only

Each entry of CHANGELOG.md is what changed against the previous version.  Where a git commit "Engine X.Y: ..."
exists, the report adds its id and the size of the change against the previous version's commit.
"""
import argparse
import html
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")
OUT = os.path.join(ROOT, "reports", "version_history.html")
IMPACT = "השפעה על טווחים:"


def parse_changelog(path=CHANGELOG):
    """Entries newest first: {version, date, title, impact, changes}."""
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = re.match(r"^## (\d+\.\d+(?:\.\d+)?) \| (\S+) \| (.+)$", line)
            if m:
                entries.append({"version": m.group(1), "date": m.group(2), "title": m.group(3).strip(),
                                "impact": "", "changes": []})
            elif entries and line.startswith(IMPACT):
                entries[-1]["impact"] = line[len(IMPACT):].strip()
            elif entries and line.startswith("- "):
                entries[-1]["changes"].append(line[2:].strip())
    return entries


def _git(*args):
    try:
        return subprocess.run(("git",) + args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def git_versions():
    """{version: (commit, shortstat against the previous version commit)} from the "Engine X.Y:" commits."""
    log = _git("log", "--reverse", "--format=%h %s")
    found, prev = {}, None
    for line in log.splitlines():
        commit, _, subject = line.partition(" ")
        m = re.match(r"Engine (\d+\.\d+(?:\.\d+)?):", subject)
        if not m:
            continue
        stat = _git("diff", "--shortstat", prev, commit) if prev else ""
        found[m.group(1)] = (commit, stat)
        prev = commit
    return found


def impact_kind(text):
    if text.startswith("כן"):
        return "yes"
    if text.startswith("בסיס"):
        return "base"
    return "no"


def text_summary(entries, gitinfo):
    lines = ["TRM_HADMAAv1 - version history (%d versions, current %s)" % (len(entries), entries[0]["version"]), ""]
    for i, e in enumerate(entries):
        prev = entries[i + 1]["version"] if i + 1 < len(entries) else "-"
        commit, stat = gitinfo.get(e["version"], ("", ""))
        lines.append("%-6s %s  (from %s)  %s" % (e["version"], e["date"], prev, e["title"]))
        lines.append("       ranges: %s" % e["impact"])
        if commit:
            lines.append("       commit %s  %s" % (commit, stat))
        lines += ["       - " + c for c in e["changes"]]
        lines.append("")
    return "\n".join(lines)


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--muted:#5d6779;--line:#dde1e8;--acc:#2f5fb3;
--yes:#b5482f;--yes-bg:#fbe9e4;--no:#2e7d4f;--no-bg:#e5f4ea;--base:#5d6779;--base-bg:#eceef2}
@media (prefers-color-scheme:dark){:root{--bg:#14171d;--card:#1d2129;--fg:#e6e9ef;--muted:#9aa3b2;--line:#2e3440;
--acc:#7fa6ea;--yes:#f0937b;--yes-bg:#3a2520;--no:#7fd0a0;--no-bg:#1d3326;--base:#aab2c0;--base-bg:#2a2f38}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.6 "Segoe UI",Arial,sans-serif}main{max-width:920px;margin:0 auto;padding:28px 16px 48px}
h1{font-size:24px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 20px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px;
overflow:hidden;margin-bottom:28px;font-size:14px}th,td{padding:7px 10px;border-bottom:1px solid var(--line);
text-align:right;vertical-align:top}th{color:var(--muted);font-weight:600}tr:last-child td{border-bottom:0}
a{color:var(--acc);text-decoration:none}.ver{font-weight:700;white-space:nowrap}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 18px;margin-bottom:14px}
.card h2{font-size:17px;margin:0 0 4px}.meta{color:var(--muted);font-size:13px;margin-bottom:8px}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600}
.yes{color:var(--yes);background:var(--yes-bg)}.no{color:var(--no);background:var(--no-bg)}
.base{color:var(--base);background:var(--base-bg)}ul{margin:6px 0 0;padding-inline-start:20px}
code{font-family:Consolas,monospace;font-size:13px}.cur{border-color:var(--acc)}
"""


def html_report(entries, gitinfo):
    e0 = entries[0]
    rows, cards = [], []
    for i, e in enumerate(entries):
        v, kind = html.escape(e["version"]), impact_kind(e["impact"])
        prev = entries[i + 1]["version"] if i + 1 < len(entries) else ""
        commit, stat = gitinfo.get(e["version"], ("", ""))
        badge = '<span class="badge %s">%s</span>' % (kind, {"yes": "משנה טווחים", "no": "ללא שינוי בטווחים",
                                                             "base": "בסיס"}[kind])
        rows.append('<tr><td class="ver"><a href="#v%s">%s</a></td><td>%s</td><td>%s</td><td>%s</td></tr>'
                    % (v, v, html.escape(e["date"]), html.escape(e["title"]), badge))
        meta = [html.escape(e["date"])]
        if prev:
            meta.append("שינוי לעומת %s" % html.escape(prev))
        if commit:
            meta.append("commit <code>%s</code>" % html.escape(commit) + (" · %s" % html.escape(stat) if stat else ""))
        cards.append('<section class="card%s" id="v%s"><h2>גרסה %s - %s</h2><div class="meta">%s</div>'
                     '<div>%s %s</div><ul>%s</ul></section>'
                     % (" cur" if i == 0 else "", v, v, html.escape(e["title"]), " · ".join(meta), badge,
                        html.escape(e["impact"]), "".join("<li>%s</li>" % html.escape(c) for c in e["changes"])))
    return ('<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>היסטוריית גרסאות</title>'
            '<style>%s</style></head><body><main><h1>TRM_HADMAAv1 - היסטוריית גרסאות</h1>'
            '<p class="sub">גרסה נוכחית: <b>%s</b> (%s) · %d גרסאות · נוצר מתוך CHANGELOG.md</p>'
            '<table><thead><tr><th>גרסה</th><th>תאריך</th><th>מה השתנה</th><th>טווחים</th></tr></thead>'
            '<tbody>%s</tbody></table>%s</main></body></html>'
            % (CSS, html.escape(e0["version"]), html.escape(e0["date"]), len(entries), "".join(rows), "".join(cards)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--text", action="store_true", help="print the summary only, do not write the HTML report")
    args = ap.parse_args(argv)
    entries, gitinfo = parse_changelog(), git_versions()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(text_summary(entries, gitinfo))
    if not args.text:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            f.write(html_report(entries, gitinfo))
        print("Report: %s" % OUT)


if __name__ == "__main__":
    main()
