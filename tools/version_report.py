"""Version history report: CHANGELOG.md -> reports/version_history.html (Hebrew, right-to-left) and a console summary.

    python tools/version_report.py                   write the HTML report and print the summary
    python tools/version_report.py --text            print the summary only
    python tools/version_report.py --diff 2.13 2.14  what changed between two versions (changelog, commits, files)

Each entry of CHANGELOG.md is what changed against the previous version.  Every version has a git tag vX.Y (on its
"Engine X.Y: ..." commit; 2.0 - 2.4 are in the initial commit, tagged v2.4).  Against the previous tagged version the
report adds the commits in between, the changed files, the size of the change, the compare command (git diff vA vB)
and the GitHub compare link.  A version without a tag falls back to its "Engine X.Y:" commit.
"""
import argparse
import html
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")
REPO_URL = "https://github.com/ramihalabi-sudo/TRM_Hadmaa"
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


def _vkey(v):
    return tuple(int(x) for x in v.split("."))


def version_commits():
    """{version: (ref, commit)}: the vX.Y tags, else the "Engine X.Y:" commits."""
    out = {}
    for line in _git("log", "--reverse", "--format=%h %s").splitlines():
        commit, _, subject = line.partition(" ")
        m = re.match(r"Engine (\d+\.\d+(?:\.\d+)?):", subject)
        if m:
            out[m.group(1)] = (commit, commit)
    for tag in _git("tag", "-l", "v*").split():
        m = re.match(r"v(\d+\.\d+(?:\.\d+)?)$", tag)
        if m:
            out[m.group(1)] = (tag, _git("rev-list", "-n", "1", "--abbrev-commit", tag))
    return out


def compare(a_ref, b_ref):
    """{"stat", "commits": [hash subject], "files": [(status, path)]} of the change a_ref..b_ref."""
    commits = _git("log", "--reverse", "--format=%h %s", "%s..%s" % (a_ref, b_ref)).splitlines()
    files = [tuple(ln.split("\t", 1)) for ln in _git("diff", "--name-status", a_ref, b_ref).splitlines() if "\t" in ln]
    return {"stat": _git("diff", "--shortstat", a_ref, b_ref), "commits": commits, "files": files}


def git_versions():
    """{version: (commit, shortstat, compare, previous version, ref, previous ref)} against the previous version."""
    refs = version_commits()
    found, prev = {}, None
    for v in sorted(refs, key=_vkey):
        ref, commit = refs[v]
        cmp = compare(refs[prev][0], ref) if prev else None
        found[v] = (commit, cmp["stat"] if cmp else "", cmp, prev, ref, refs[prev][0] if prev else None)
        prev = v
    return found


def diff_text(a, b, entries=None, refs=None):
    """Console text of what changed from version a to version b: changelog entries, commits and files."""
    entries = entries if entries is not None else parse_changelog()
    refs = refs if refs is not None else version_commits()
    for v in (a, b):
        if v not in refs:
            return "Version %s has no tag / commit. Tagged versions: %s" % (v, ", ".join(sorted(refs, key=_vkey)))
    lo, hi = sorted((a, b), key=_vkey)
    c = compare(refs[lo][0], refs[hi][0])
    lines = ["TRM_HADMAAv1 %s -> %s   (git diff %s %s)" % (lo, hi, refs[lo][0], refs[hi][0]), c["stat"], ""]
    for e in reversed(entries):
        if _vkey(lo) < _vkey(e["version"]) <= _vkey(hi):
            lines.append("%s  %s  %s" % (e["version"], e["date"], e["title"]))
            lines.append("    ranges: " + e["impact"])
            lines += ["    - " + x for x in e["changes"]]
    lines += ["", "Commits:"] + ["    " + x for x in c["commits"]]
    lines += ["", "Files:"] + ["    %-3s %s" % f for f in c["files"]]
    return "\n".join(lines)


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
        commit, stat = gitinfo.get(e["version"], ("", ""))[:2]
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
details{margin-top:10px}summary{cursor:pointer;color:var(--acc)}details table{margin:6px 0 0}
details code{direction:ltr;unicode-bidi:embed}
"""


def html_report(entries, gitinfo):
    e0 = entries[0]
    rows, cards = [], []
    for i, e in enumerate(entries):
        v, kind = html.escape(e["version"]), impact_kind(e["impact"])
        prev = entries[i + 1]["version"] if i + 1 < len(entries) else ""
        info = gitinfo.get(e["version"], ("", ""))
        commit, stat = info[:2]
        cmp, gprev, ref, pref = info[2:6] if len(info) >= 6 else (None, None, None, None)
        badge = '<span class="badge %s">%s</span>' % (kind, {"yes": "משנה טווחים", "no": "ללא שינוי בטווחים",
                                                             "base": "בסיס"}[kind])
        rows.append('<tr><td class="ver"><a href="#v%s">%s</a></td><td>%s</td><td>%s</td><td>%s</td></tr>'
                    % (v, v, html.escape(e["date"]), html.escape(e["title"]), badge))
        meta = [html.escape(e["date"])]
        if prev:
            meta.append("שינוי לעומת %s" % html.escape(prev))
        if commit:
            meta.append("commit <code>%s</code>" % html.escape(commit) + (" · %s" % html.escape(stat) if stat else ""))
        git_html = ""
        if cmp:
            git_html = ('<details><summary>מה השתנה בקוד מול %s: %d commits, %d קבצים</summary>'
                        '<p class="meta">השוואה: <code>git diff %s %s</code> · '
                        '<code>py tools/version_report.py --diff %s %s</code> · '
                        '<a href="%s/compare/%s...%s">GitHub</a></p><ul>%s</ul><table><tbody>%s</tbody></table>'
                        '</details>'
                        % (html.escape(gprev), len(cmp["commits"]), len(cmp["files"]), html.escape(pref),
                           html.escape(ref), html.escape(gprev), v, REPO_URL, html.escape(pref), html.escape(ref),
                           "".join("<li><code>%s</code></li>" % html.escape(c) for c in cmp["commits"]),
                           "".join('<tr><td class="ver">%s</td><td><code>%s</code></td></tr>'
                                   % (html.escape(s), html.escape(p)) for s, p in cmp["files"])))
        cards.append('<section class="card%s" id="v%s"><h2>גרסה %s - %s</h2><div class="meta">%s</div>'
                     '<div>%s %s</div><ul>%s</ul>%s</section>'
                     % (" cur" if i == 0 else "", v, v, html.escape(e["title"]), " · ".join(meta), badge,
                        html.escape(e["impact"]), "".join("<li>%s</li>" % html.escape(c) for c in e["changes"]),
                        git_html))
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
    ap.add_argument("--diff", nargs=2, metavar=("FROM", "TO"), help="what changed between two versions, e.g. 2.13 2.14")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.diff:
        print(diff_text(*args.diff))
        return
    entries, gitinfo = parse_changelog(), git_versions()
    print(text_summary(entries, gitinfo))
    if not args.text:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            f.write(html_report(entries, gitinfo))
        print("Report: %s" % OUT)


if __name__ == "__main__":
    main()
