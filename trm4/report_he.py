"""Hebrew scholarly PDF report (RTL): DRI results + Range Improvement Advisor recommendations.

Structure follows "TRM_Range_Improvement_Advisor_Scientific_RTL_Hebrew.pdf":

    abstract + key finding                    -> what limits the DRI ranges and what the best action gives
    Ch. 1  purpose and method                 -> advisory only, counterfactual recalculation (Ch. 2.2, 5.1)
    Ch. 2  baseline snapshot                  -> inputs, sources, geometry, run ID, model version (Ch. 2.1)
    Ch. 3  DRI results                        -> per task range, pixels / cycles on target, MTF, CNR, limiter
    Ch. 4  bottleneck diagnosis               -> bottleneck candidate + separation test, limiting factors (Ch. 4)
    Ch. 5  normalized sensitivities           -> S_i = (x_i / R) dR/dx_i (Ch. 5.2)
    Ch. 6  what-if actions                    -> all evaluated actions, evidence level, FOV, Pareto (Ch. 5.1, 6)
    Ch. 7  recommendations for improving DRI  -> decision cards of the top 3 (Ch. 8.1) + guidance per bottleneck
    Ch. 8  measure first                      -> data that limit the confidence (Ch. 8 usability rule, 11.2)
    Ch. 9  limitations and conclusions        -> (Ch. 14)
    App.   model warnings / assumptions, bibliography

Rendered with matplotlib only (no extra dependency).  matplotlib has no bidi support, so this module carries a small
right-to-left layout engine: a simplified Unicode bidi pass (Hebrew right-to-left; Latin words, numbers, units and
formulas left-to-right; mirrored brackets), line breaking, justification, tables, call-out boxes and figures.
"""
import datetime
import logging
import os
import re

import numpy as np
from matplotlib.backends.backend_agg import RendererAgg
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties, fontManager
from matplotlib.patches import Rectangle
import matplotlib

from . import advisor as ADV
from . import __version__

# ---------------------------------------------------------------------------------------------
# palette
# ---------------------------------------------------------------------------------------------
INK, HEAD, MUTED, ACCENT = "#1f2a37", "#13233a", "#667085", "#0f6b7f"
RULE, TH_BG, BAND, BOX_BG, CODE_BG = "#d5dde5", "#e8eff4", "#f6f8fa", "#eef5f8", "#f1f4f7"
SERIES = ["#0f6b7f", "#c2410c", "#6d28d9", "#15803d", "#b45309", "#475569"]

# ---------------------------------------------------------------------------------------------
# fonts
# ---------------------------------------------------------------------------------------------
_FONT_FILES = ("frank.ttf", "david.ttf", "davidbd.ttf", "arial.ttf", "arialbd.ttf", "times.ttf", "timesbd.ttf",
               "timesi.ttf", "consola.ttf")
_FAMILIES = {
    ("r", "he"): (["FrankRuehl", "David", "Arial"], "normal", "normal"),
    ("r", "la"): (["Times New Roman", "DejaVu Serif"], "normal", "normal"),
    ("b", "he"): (["David", "Arial"], "bold", "normal"),
    ("b", "la"): (["Times New Roman", "DejaVu Serif"], "bold", "normal"),
    ("i", "he"): (["FrankRuehl", "David", "Arial"], "normal", "normal"),
    ("i", "la"): (["Times New Roman", "DejaVu Serif"], "normal", "italic"),
    ("h", "he"): (["Arial"], "bold", "normal"),
    ("h", "la"): (["Arial"], "bold", "normal"),
    ("s", "he"): (["Arial"], "normal", "normal"),
    ("s", "la"): (["Arial"], "normal", "normal"),
    ("m", "he"): (["Consolas", "Courier New"], "normal", "normal"),
    ("m", "la"): (["Consolas", "Courier New"], "normal", "normal"),
}
HE_SCALE = 1.13
_fonts_ready = False
_available = set()
_fp_cache, _w_cache = {}, {}
_renderer = None


def _setup_fonts():
    """Register the Windows Hebrew fonts (if present) and silence 'font not found' warnings."""
    global _fonts_ready, _available
    if _fonts_ready:
        return
    root = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    known = {os.path.normcase(f.fname) for f in fontManager.ttflist}
    for name in _FONT_FILES:
        path = os.path.join(root, name)
        if os.path.isfile(path) and os.path.normcase(path) not in known:
            try:
                fontManager.addfont(path)
            except Exception:                              # a broken font file must not stop the report
                pass
    _available = {f.name for f in fontManager.ttflist}
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
    _fonts_ready = True


def _fp(key, size):
    """FontProperties for (role, script); DejaVu Sans is always the last fallback (it covers Hebrew and symbols)."""
    k = (key, round(size, 2))
    if k not in _fp_cache:
        fams, weight, style = _FAMILIES[key]
        fams = [f for f in fams if f in _available] + ["DejaVu Sans"]
        if key[1] == "he" and key[0] in "rbi" and fams[0] in ("FrankRuehl", "David"):
            size *= HE_SCALE                                # Hebrew serif faces run small next to Times
        _fp_cache[k] = FontProperties(family=fams, weight=weight, style=style, size=size)
    return _fp_cache[k]


def _width(text, key, size):
    """Advance width in points (72 dpi renderer, same font metrics as the PDF backend)."""
    global _renderer
    k = (text, key, round(size, 2))
    if k not in _w_cache:
        if _renderer is None:
            _renderer = RendererAgg(10, 10, 72)
        w, _h, _d = _renderer.get_text_width_height_descent(text, _fp(key, size), ismath=False)
        _w_cache[k] = w
    return _w_cache[k]


# ---------------------------------------------------------------------------------------------
# simplified bidi (UAX #9 subset: W5/W7 numbers, N0 brackets, N1/N2 neutrals, L2 reordering, L4 mirroring)
# ---------------------------------------------------------------------------------------------
_MIRROR = {"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{", "<": ">", ">": "<", "\u00ab": "\u00bb",
           "\u00bb": "\u00ab"}
_OPEN, _CLOSE = "([{", ")]}"
_LEAD_PUNCT, _TRAIL_PUNCT = "([{\"'\u201c\u05f4", ".,;:!?)]}\"'\u201d\u05f4"


def is_he(c):
    o = ord(c)
    return 0x0590 <= o <= 0x05FF or 0xFB1D <= o <= 0xFB4F


def _ctype(c):
    if is_he(c):
        return "R"
    if c.isdigit():
        return "EN"
    if c.isalpha():
        return "L"
    if c in "+-\u2212\u00b1\u00d7~\u2248\u2264\u2265=<>":
        return "ES"                                         # signs / operators directly before a number
    if c in "%\u00b0\u2030":
        return "ET"
    if c in ".,:/":
        return "CS"
    return "N"


def resolve(text, base):
    """Direction ('L' / 'R') of every character of a paragraph with base direction `base`."""
    t = [_ctype(c) for c in text]
    n = len(t)
    for i in range(n - 1, -1, -1):                          # sign / operator before a number belongs to it
        if t[i] == "ES" and i + 1 < n and t[i + 1] == "EN":
            t[i] = "EN"
    for i in range(1, n - 1):                               # 1.25 / 1,000 / 3:2
        if t[i] in ("CS", "ES") and t[i - 1] == "EN" and t[i + 1] == "EN":
            t[i] = "EN"
    for i in range(1, n):                                   # 25 % / 5.5 deg
        if t[i] == "ET" and t[i - 1] == "EN":
            t[i] = "EN"
    for m in re.finditer(r"[^\s֐-׿]+", text):     # Latin tokens such as F/#, MTF_motion, T-07 stay together
        a, b = m.start(), m.end()
        if not any(t[i] == "L" for i in range(a, b)):
            continue
        while a < b and text[a] in _LEAD_PUNCT:
            a += 1
        while b > a and text[b - 1] in _TRAIL_PUNCT:
            b -= 1
        for i in range(a, b):
            t[i] = "L"
    d = [None] * n
    last = base
    for i in range(n):                                      # W7 (numbers after Latin are Latin) + strong types
        if t[i] == "R":
            d[i] = last = "R"
        elif t[i] == "L":
            d[i] = last = "L"
        elif t[i] == "EN":
            d[i] = "L"                                      # numbers always read left-to-right
    stack = []                                              # N0: bracket pairs
    for i, c in enumerate(text):
        if c in _OPEN:
            stack.append((c, i))
        elif c in _CLOSE and stack:
            j = next((k for k in range(len(stack) - 1, -1, -1) if _OPEN.index(stack[k][0]) == _CLOSE.index(c)), None)
            if j is None:
                continue
            o = stack[j][1]
            del stack[j:]
            inner = {d[k] for k in range(o + 1, i) if t[k] in ("R", "L")} | \
                {"L" for k in range(o + 1, i) if t[k] == "EN"}
            if not inner:
                continue
            if base in inner:
                dirn = base
            else:
                before = next((("R" if t[k] == "R" else "L") for k in range(o - 1, -1, -1)
                               if t[k] in ("R", "L", "EN")), base)
                dirn = "L" if before == "L" else base
            d[o] = d[i] = dirn
    i = 0
    while i < n:                                            # N1 / N2: neutrals
        if d[i] is not None:
            i += 1
            continue
        j = i
        while j < n and d[j] is None:
            j += 1
        prev = d[i - 1] if i > 0 else base
        nxt = d[j] if j < n else base
        for k in range(i, j):
            d[k] = prev if prev == nxt else base
        i = j
    return d


def visual_order(idx, dirs, base):
    """Visual left-to-right order of the logical indices `idx` (one line)."""
    runs = []
    for i in idx:
        if runs and runs[-1][0] == dirs[i]:
            runs[-1][1].append(i)
        else:
            runs.append((dirs[i], [i]))
    if base == "R":
        runs = runs[::-1]
    out = []
    for dirn, r in runs:
        out.extend(r[::-1] if dirn == "R" else r)
    return out


def vis(text):
    """Single-line visual string (figure labels)."""
    text = str(text)
    if not any(is_he(c) for c in text):
        return text
    d = resolve(text, "R")
    return "".join(_MIRROR.get(text[i], text[i]) if d[i] == "R" else text[i]
                   for i in visual_order(range(len(text)), d, "R"))


# ---------------------------------------------------------------------------------------------
# paragraph layout
# ---------------------------------------------------------------------------------------------
def spans(markup, role="r"):
    """'plain **bold** plain' -> [(text, role), ...]."""
    out = []
    for i, part in enumerate(str(markup).split("**")):
        if part:
            out.append((part, "b" if i % 2 else role))
    return out


class _Para:
    """A laid-out paragraph: list of lines, each a list of ('t', text, key, width) / ('s', width) items."""

    def __init__(self, sp, size, width, base=None):
        text = "".join(s for s, _r in sp)
        roles = [r for s, r in sp for _c in s]
        self.base = base or ("R" if any(is_he(c) for c in text) else "L")
        dirs = resolve(text, self.base)
        keys = [(roles[i], "he" if is_he(c) else "la") for i, c in enumerate(text)]
        self.size = size
        sp_key = ("r", "he" if self.base == "R" else "la")
        self.space = _width(" ", sp_key, size) or size * 0.25
        words = [(m.start(), m.end()) for m in re.finditer(r"[^ \n]+|\n", text)]
        lines, cur, cur_w = [], [], 0.0
        for a, b in words:
            if text[a:b] == "\n":
                lines.append(cur)
                cur, cur_w = [], 0.0
                continue
            w = self._span_width(text, keys, a, b)
            if cur and cur_w + self.space + w > width:
                lines.append(cur)
                cur, cur_w = [], 0.0
            cur_w += (self.space if cur else 0.0) + w
            cur.append((a, b))
        if cur or not lines:
            lines.append(cur)
        self.lines = []
        for ln in lines:
            if not ln:
                self.lines.append([])
                continue
            idx = []
            for k, (a, b) in enumerate(ln):
                if k:
                    idx.append(-1)                          # word gap
                idx.extend(range(a, b))
            gaps = [k for k, i in enumerate(idx) if i == -1]
            real = [i for i in idx if i >= 0]
            # word gaps take the direction of the run they sit in (between equal neighbours) or the base
            gdir = {}
            for k in gaps:
                p, q = dirs[idx[k - 1]], dirs[idx[k + 1]]
                gdir[k] = p if p == q else self.base
            ext_dirs = {i: dirs[i] for i in real}
            order_keys = list(range(len(idx)))
            kd = [gdir[k] if idx[k] == -1 else ext_dirs[idx[k]] for k in order_keys]
            vo = visual_order(order_keys, kd, self.base)
            items, buf, bkey = [], "", None
            for k in vo:
                i = idx[k]
                if i == -1:
                    if buf:
                        items.append(("t", buf, bkey, _width(buf, bkey, size)))
                        buf, bkey = "", None
                    items.append(("s", self.space))
                    continue
                c = text[i]
                if dirs[i] == "R":
                    c = _MIRROR.get(c, c)
                if bkey is not None and keys[i] != bkey:
                    items.append(("t", buf, bkey, _width(buf, bkey, size)))
                    buf = ""
                buf += c
                bkey = keys[i]
            if buf:
                items.append(("t", buf, bkey, _width(buf, bkey, size)))
            self.lines.append(items)

    def _span_width(self, text, keys, a, b):
        w, s = 0.0, a
        for i in range(a + 1, b + 1):
            if i == b or keys[i] != keys[s]:
                w += _width(text[s:i], keys[s], self.size)
                s = i
        return w


def _layout(sp, size, width, base=None):
    return _Para(sp, size, width, base)


def _line_width(items):
    return sum(it[3] if it[0] == "t" else it[1] for it in items)


def _draw_line(ax, items, x_left, x_right, baseline, size, color, align="right", justify=False):
    nat = _line_width(items)
    gaps = sum(1 for it in items if it[0] == "s")
    extra = 0.0
    if justify and gaps and nat < (x_right - x_left):
        extra = (x_right - x_left - nat) / gaps
        x = x_left
    elif align == "right":
        x = x_right - nat
    elif align == "center":
        x = (x_left + x_right - nat) / 2
    else:
        x = x_left
    for it in items:
        if it[0] == "s":
            x += it[1] + extra
            continue
        ax.text(x, baseline, it[1], fontproperties=_fp(it[2], size), color=color, ha="left", va="baseline",
                parse_math=False)
        x += it[3]


# ---------------------------------------------------------------------------------------------
# document
# ---------------------------------------------------------------------------------------------
class _Doc:
    W, H = 595.28, 841.89
    ML, MR, MT, MB = 62.0, 62.0, 76.0, 66.0

    def __init__(self, header_right, header_left):
        self.pages, self.toc = [], []
        self.header_right, self.header_left = header_right, header_left
        self.n_fig = self.n_tab = 0
        self.ax, self.y = None, 0.0

    @property
    def right(self):
        return self.W - self.MR

    @property
    def width(self):
        return self.W - self.ML - self.MR

    @property
    def bottom(self):
        return self.H - self.MB

    def new_page(self, decor=True):
        fig = Figure(figsize=(self.W / 72.0, self.H / 72.0))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, self.W)
        ax.set_ylim(self.H, 0)
        ax.axis("off")
        self.pages.append({"fig": fig, "ax": ax, "decor": decor})
        self.fig, self.ax, self.y = fig, ax, self.MT

    def need(self, h):
        if self.y + h > self.bottom:
            self.new_page()
            return True
        return False

    def rect(self, x, y, w, h, color, ax=None, **kw):
        (ax or self.ax).add_patch(Rectangle((x, y), w, h, facecolor=color, edgecolor="none", **kw))

    def hline(self, x0, x1, y, color=RULE, lw=0.6, ax=None):
        (ax or self.ax).plot([x0, x1], [y, y], color=color, lw=lw, solid_capstyle="butt")

    # --- text blocks
    def para(self, markup, size=10.5, color=INK, lead=1.6, after=7.0, justify=True, align="right", indent=0.0,
             role="r", width=None, keep=0.0, base=None):
        w = (width or self.width) - indent
        p = _layout(spans(markup, role), size, w, base)
        lh = size * lead
        self.need(min(len(p.lines), 2) * lh + keep)
        x_right = self.right - indent
        for k, items in enumerate(p.lines):
            self.need(lh)
            last = k == len(p.lines) - 1
            _draw_line(self.ax, items, x_right - w, x_right, self.y + size * 1.12, size, color,
                       align="left" if p.base == "L" and align == "ltr" else align,
                       justify=justify and not last)
            self.y += lh
        self.y += after

    def chapter(self, number, title, new_page=False):
        if new_page or self.y > self.bottom - 190:
            self.new_page()
        elif self.y > self.MT + 1:
            self.y += 14
        kicker = "פרק %s" % number if str(number).isdigit() else "נספח %s" % number
        self.toc.append((number, title, len(self.pages)))
        self.para("**%s**" % kicker, size=9.5, color=ACCENT, lead=1.3, after=2, justify=False)
        self.para(title, size=20, color=HEAD, role="h", lead=1.35, after=4, justify=False)
        self.hline(self.ML, self.right, self.y, color=RULE, lw=1.4)
        self.y += 14

    def section(self, title):
        self.need(70)
        self.y += 6
        size = 12.5
        p = _layout(spans(title, "h"), size, self.width - 12)
        top = self.y
        for items in p.lines:
            _draw_line(self.ax, items, self.ML, self.right - 11, self.y + size * 1.1, size, HEAD)
            self.y += size * 1.45
        self.rect(self.right - 3.5, top + 2, 3.5, self.y - top - 3, ACCENT)
        self.y += 6

    def bullets(self, items, numbered=False, size=10.5, after=8.0):
        for k, txt in enumerate(items, start=1):
            mark = vis("%d." % k) if numbered else "\u2022"
            p = _layout(spans(txt), size, self.width - 20)
            lh = size * 1.6
            self.need(min(len(p.lines), 2) * lh)
            mk = ("b", "la") if numbered else ("r", "la")
            mw = _width(mark, mk, size)
            self.ax.text(self.right - mw, self.y + size * 1.12, mark, fontproperties=_fp(mk, size),
                         color=ACCENT, ha="left", va="baseline", parse_math=False)
            for j, line in enumerate(p.lines):
                self.need(lh)
                _draw_line(self.ax, line, self.ML, self.right - 20, self.y + size * 1.12, size, INK,
                           justify=j < len(p.lines) - 1)
                self.y += lh
            self.y += 2
        self.y += after

    def callout(self, title, text, size=10.3):
        pad = 12.0
        w = self.width - 2 * pad - 4
        pt = _layout(spans("**%s**" % title), size, w)
        pb = _layout(spans(text), size, w)
        lh = size * 1.6
        h = (len(pt.lines) + len(pb.lines)) * lh + 2 * pad - 4
        self.need(h + 10)
        self.rect(self.ML, self.y, self.width, h, BOX_BG)
        self.rect(self.right - 4, self.y, 4, h, ACCENT)
        y = self.y + pad - 3
        for k, line in enumerate(pt.lines + pb.lines):
            _draw_line(self.ax, line, self.ML + pad, self.right - pad - 4, y + size * 1.12, size, HEAD if
                       k < len(pt.lines) else INK, justify=len(pt.lines) <= k < len(pt.lines) + len(pb.lines) - 1)
            y += lh
        self.y += h + 12

    def formula(self, lines, size=9.6):
        lh = size * 1.55
        h = len(lines) * lh + 18
        self.need(h + 8)
        self.ax.add_patch(Rectangle((self.ML, self.y), self.width, h, facecolor=CODE_BG, edgecolor=RULE, lw=0.6))
        y = self.y + 9
        for ln in lines:
            w = _width(ln, ("m", "la"), size)
            self.ax.text(self.ML + (self.width - w) / 2, y + size * 1.1, ln, fontproperties=_fp(("m", "la"), size),
                         color=HEAD, ha="left", va="baseline", parse_math=False)
            y += lh
        self.y += h + 10

    def caption(self, kind, text, size=9.0):
        if kind == "table":
            self.n_tab += 1
            label = "**טבלה %d:** %s" % (self.n_tab, text)
        else:
            self.n_fig += 1
            label = "**איור %d:** %s" % (self.n_fig, text)
        p = _layout(spans(label), size, self.width)
        for line in p.lines:
            _draw_line(self.ax, line, self.ML, self.right, self.y + size * 1.1, size, MUTED, align="right")
            self.y += size * 1.5
        self.y += 3

    def _columns(self, widths):
        tot = float(sum(widths))
        return [self.width * w / tot for w in widths]

    @staticmethod
    def _lay_row(row, role, cw, size, bold_first):
        cells = []
        for k, txt in enumerate(row):
            r = "b" if role == "b" or (bold_first and k == 0) else "r"
            cells.append(_layout(spans(str(txt), r), size, cw[k] - 10.0))
        return cells, max(len(c.lines) for c in cells) * size * 1.45 + 9.0

    def table_height(self, header, rows, widths, caption=True, size=8.7, bold_first=False):
        cw = self._columns(widths)
        return (22 if caption else 0) + 16 + sum(self._lay_row(r, "b" if k == 0 else "r", cw, size, bold_first)[1]
                                                 for k, r in enumerate([header] + list(rows)))

    def table(self, header, rows, widths, caption=None, size=8.7, aligns=None, bold_first=False, keep=False):
        """RTL table: column 0 is the rightmost one.  `widths` are fractions of the text width.  `keep` moves a
        table that fits on one page to the next page instead of splitting it."""
        cw, pad_x, pad_y, lh = self._columns(widths), 5.0, 4.5, size * 1.45
        aligns = aligns or ["right"] * len(header)

        def lay(row, role):
            return self._lay_row(row, role, cw, size, bold_first)

        def draw(cells, h, bg, color=INK):
            if bg:
                self.rect(self.ML, self.y, self.width, h, bg)
            x_right = self.right
            for k, c in enumerate(cells):
                y = self.y + pad_y
                for line in c.lines:
                    _draw_line(self.ax, line, x_right - cw[k] + pad_x, x_right - pad_x, y + size * 1.08, size,
                               color, align=aligns[k])
                    y += lh
                x_right -= cw[k]
            self.y += h
            self.hline(self.ML, self.right, self.y, lw=0.5)

        hc, hh = lay(header, "b")
        body = [lay(r, "r") for r in rows]
        cap_h = 22 if caption else 0
        total = cap_h + hh + sum(h for _c, h in body) + 4
        if keep and total <= self.bottom - self.MT:
            self.need(total)
        self.need(cap_h + hh + (body[0][1] if body else 0) + 4)
        if caption:
            self.caption("table", caption)
        self.hline(self.ML, self.right, self.y, color="#9fb3c2", lw=0.9)
        draw(hc, hh, TH_BG, HEAD)
        for k, (cells, h) in enumerate(body):
            if self.need(h):
                self.hline(self.ML, self.right, self.y, color="#9fb3c2", lw=0.9)
                draw(hc, hh, TH_BG, HEAD)
            draw(cells, h, BAND if k % 2 else None)
        self.y += 12

    def figure(self, draw, height, caption):
        self.need(height + 30)
        H, W = self.H, self.W
        pad_l, pad_b, pad_t = 46.0, 34.0, 6.0               # room for tick labels and axis titles inside the box
        rect = [(self.ML + pad_l) / W, 1 - (self.y + height - pad_b) / H, (self.width - pad_l - 8) / W,
                (height - pad_b - pad_t) / H]
        try:
            draw(self.fig, rect)
        except Exception:                                   # a figure must never block the report
            self.ax.text(self.right, self.y + 20, vis("(האיור אינו זמין עבור תצורה זו)"),
                         fontproperties=_fp(("s", "he"), 9), color=MUTED, ha="right", parse_math=False)
        self.y += height + 6
        self.caption("figure", caption)
        self.y += 6

    # --- finishing
    def finish_pages(self):
        n = len(self.pages)
        for k, pg in enumerate(self.pages):
            if not pg["decor"]:
                continue
            ax = pg["ax"]
            hp = _layout(spans(self.header_right, "s"), 7.8, self.width * 0.6)
            _draw_line(ax, hp.lines[0], self.ML, self.right, 40, 7.8, MUTED)
            lp = _layout(spans(self.header_left, "s"), 7.8, self.width * 0.38)
            _draw_line(ax, lp.lines[0], self.ML, self.right, 40, 7.8, MUTED, align="left")
            self.hline(self.ML, self.right, 47, ax=ax, lw=0.5)
            fp = _layout(spans("עמוד %d מתוך %d" % (k + 1, n), "s"), 8, self.width)
            _draw_line(ax, fp.lines[0], self.ML, self.right, self.H - 32, 8, MUTED, align="center")

    def save(self, path):
        with matplotlib.rc_context({"pdf.fonttype": 42}):
            with PdfPages(path, metadata={"Title": "TRM DRI performance and improvement report",
                                          "Creator": "TRM_HADMAAv1 %s" % __version__}) as pdf:
                for pg in self.pages:
                    pdf.savefig(pg["fig"])


# ---------------------------------------------------------------------------------------------
# Hebrew vocabulary
# ---------------------------------------------------------------------------------------------
TASK_HE = {"Detection": "גילוי", "Recognition": "הבחנה", "Identification": "זיהוי", "Orientation": "התמצאות",
           "Classification": "סיווג"}
TYPE_HE = {"sampling": "דגימה זוויתית (IFOV)", "optics": "מגבלה אופטית / MTF", "snr": "יחס אות לרעש / ניגודיות",
           "environment": "סביבה וקונטרסט (אטמוספרה)", "motion": "תנועה / ייצוב", "observer": "שרשרת תצוגה / צופה",
           "model": "מגבלת מודל"}
TEST_HE = {
    "sampling": "שינוי p/f כשה־MTF והתרחיש קבועים; בדיקת השפעתו על FOV.",
    "optics": "השוואת MTF מעבדה ומודל; בדיקת מיקוד ומיקום בשדה.",
    "snr": "ניתוח רגישות לרעש, זמן חשיפה, F/# וקליטת אור.",
    "environment": "השוואת תרחישים אטמוספריים תוך שמירת פרמטרי החומרה.",
    "motion": "השוואת MTF_motion או RMS jitter מול פרמטרי החשיפה.",
    "observer": "בדיקת גודל התצוגה / ההגדלה ומודל הצופה לפני שינוי חומרה.",
    "model": "בדיקת תלות קוד; סימון הפרמטר כלא נתמך.",
}
GUIDE_HE = {
    "sampling": "המשימה מוגבלת דגימה: הקטנת IFOV = p / f (אורך מוקד ארוך יותר או גלאי בפיקסל קטן יותר) היא הכיוון "
                "המבטיח, ותמיד יחד עם חישוב מחדש של שדה הראייה וה־MTF. הגדלת מספר הפיקסלים באותו pitch אינה "
                "משפרת את IFOV – היא מרחיבה את שדה הראייה בלבד.",
    "optics": "המשימה מוגבלת MTF: יש לבדוק מיקוד ואיכות אופטית, לקלוט עקומת MTF מדודה בתדרי המשימה, ורק לאחר מכן "
              "לשקול אופטיקה איכותית יותר או גלאי בעל MTF פיקסל גבוה יותר.",
    "snr": "המשימה מוגבלת אות־לרעש / ניגודיות: אופטיקה מהירה יותר (F/# נמוך), רעש נמוך יותר (NETD / רעש קריאה), "
           "תמסורת אופטית גבוהה יותר או זמן אינטגרציה ארוך יותר – בכפוף לבדיקת רוויה וטשטוש תנועה.",
    "environment": "הטווח מוגבל בעיקר על ידי הסביבה: שינוי מזג אוויר הוא תרחיש ולא שיפור חומרה. המנופים הם בחירת "
                   "תחום ספקטרלי, ניגודיות המטרה ותיעוד תנאי הניסוי.",
    "motion": "הטווח מוגבל על ידי תנועת קו הראייה: שיפור הייצוב או קיצור זמן החשיפה, על בסיס נתוני jitter מדודים.",
    "observer": "המגבלה בשרשרת התצוגה / הצופה: יש לבדוק גודל תצוגה, הגדלה ומודל הצופה לפני שינוי חומרה.",
    "model": "הפרמטר אינו משפיע על הטווח במודל: יש לבדוק את תלות המודל לפני כל המלצה.",
}
ALIAS_HE = {"low": "נמוך", "moderate": "בינוני", "high": "גבוה"}
SUPPORT_HE = {"model":"נתמכת מודל", "approx": "אומדן מקורב", "measure": "מדוד תחילה"}
KIND_HE = {"hardware": "שינוי חומרה", "operational": "שינוי תפעולי", "environment": "תרחיש סביבתי"}
LIMITER_HE = {"sampling (beyond Nyquist)": "דגימה (מעבר לנייקוויסט)", "sampling (near Nyquist)": "דגימה (סמוך לנייקוויסט)",
              "resolution (MTF)": "רזולוציה (MTF)", "contrast / noise": "ניגודיות / רעש"}
FACTOR_HE = {
    "Optics aberrations (diffraction-limited optics)": "אברציות אופטיות (אופטיקה מוגבלת־עקיפה)",
    "Detector footprint / crosstalk (ideal pixel MTF)": "טביעת פיקסל / זליגה (MTF פיקסל אידיאלי)",
    "Temporal noise halved": "רעש זמני מופחת בחצי",
    "Fixed pattern noise removed": "הסרת רעש תבנית קבועה (FPN)",
    "Display / eye (ideal observer MTF)": "תצוגה / עין (MTF צופה אידיאלי)",
    "Atmospheric transmission (clear path)": "תמסורת אטמוספרית (מסלול צלול)",
    "Line-of-sight motion / jitter": "תנועת קו ראייה / jitter",
    "Turbulence": "טורבולנציה",
}
PARAM_HE = {
    "Focal length (D fixed)": "אורך מוקד f (D קבוע)", "Aperture diameter": "קוטר מפתח D", "F-number": "יחס מוקד F/#",
    "Pixel pitch (f fixed)": "גודל פיקסל p (f קבוע)", "Optics transmission": "תמסורת אופטית", "NETD": "NETD",
    "Read noise": "רעש קריאה", "Integration time": "זמן אינטגרציה", "Visual range (atm 1)": "טווח ראות (אטמוספרה 1)",
    "Extinction coefficient (atm 1)": "מקדם דעיכה (אטמוספרה 1)", "Target temperature difference": "הפרש טמפרטורה ΔT",
    "Target height": "גובה מטרה", "Target reflectivity": "החזרות מטרה", "Random jitter h": "ריטוט אקראי (אופקי)",
    "Focal length": "אורך מוקד f", "Detector pitch (h)": "גודל פיקסל (אופקי)", "Detector format (h)": "פורמט גלאי (אופקי)",
    "Frame rate": "קצב פריימים", "Dark current": "זרם חושך", "Well capacity": "קיבול באר", "Spectral QE": "QE ספקטרלי",
    "Cut-on wavelength": "אורך גל תחתון", "Cut-off wavelength": "אורך גל עליון", "Target width": "רוחב מטרה",
    "Target dT": "הפרש טמפרטורה ΔT", "Atmosphere": "אטמוספרה", "Extinction (atm 1)": "מקדם דעיכה (אטמוספרה 1)",
    "Visibility (atm 1)": "טווח ראות (אטמוספרה 1)", "Turbulence Cn2": "טורבולנציה Cn²",
}
SOURCE_HE = {"preset": "ברירת מחדל", "assumption": "הנחה", "user": "משתמש", "manufacturer": "גיליון נתונים",
             "measurement": "מדידה", "import": "יבוא", "profile": "פרופיל מצלמה"}
UNIT_HE = {"um": "µm", "1/km": "1/km", "e-": "e⁻"}
SHORT_HE = {"lens_long_sameF": "עדשה ארוכה, אותו F/#", "lens_long_sameD": "מוקד ארוך, אותו D",
            "aperture_up": "אופטיקה מהירה יותר", "detector_small_pitch": "פיקסל קטן, אותו FOV",
            "detector_more_pixels": "יותר פיקסלים", "netd_lower": "NETD נמוך יותר",
            "read_noise_lower": "רעש קריאה נמוך", "frame_rate_lower": "קצב פריימים נמוך",
            "tint_longer": "אינטגרציה ארוכה", "transmission_up": "תמסורת גבוהה",
            "optics_quality": "אופטיקה מוגבלת־עקיפה", "stabilization": "ייצוב משופר",
            "env_clear": "אטמוספרה צלולה (תרחיש)"}
LABEL_HE = {
    "lens_long_sameF": lambda n, l: "עדשה ארוכה יותר באותו יחס מוקד: f ×{0} ו־D ×{1}".format(*n),
    "lens_long_sameD": lambda n, l: "אורך מוקד ארוך יותר באותו מפתח: f ×{0} (F/# ×{1})".format(*n),
    "aperture_up": lambda n, l: ("אופטיקה מהירה יותר: מפתח D ×{0} באותו אורך מוקד" if "aperture D" in l else
                                 "אופטיקה מהירה יותר: F/# ×{0}").format(*n),
    "detector_small_pitch": lambda n, l: "גלאי בפיקסלים קטנים יותר ובאותו שדה ראייה: pitch ×{0}, פורמט {1}×{2}"
                                         .format(*n),
    "detector_more_pixels": lambda n, l: "יותר פיקסלים באותו pitch: פורמט ×{0}".format(*n),
    "netd_lower": lambda n, l: "גלאי / מצלמה ברעש נמוך יותר: NETD ×{0}".format(*n),
    "read_noise_lower": lambda n, l: "רעש קריאה נמוך יותר: ×{0}".format(*n),
    "frame_rate_lower": lambda n, l: "הורדת קצב הפריימים {0} → {1} Hz (אינטגרציה ארוכה יותר לעבר יעד מילוי הבאר)"
                                     .format(*n),
    "tint_longer": lambda n, l: "זמן אינטגרציה ארוך יותר: {0} → {1} ms".format(*n),
    "transmission_up": lambda n, l: "שיפור תמסורת האופטיקה (ניקוי / ציפוי): {0} → {1}".format(*n),
    "optics_quality": lambda n, l: "אופטיקה מוגבלת־עקיפה (הסרת אברציות)",
    "stabilization": lambda n, l: "ייצוב משופר: תנועת קו ראייה שיורית ×{0}".format(*n),
    "env_clear": lambda n, l: ("אטמוספרה צלולה יותר: טווח ראות ×{0} (תרחיש)" if "visual" in l else
                               "אטמוספרה צלולה יותר: מקדם דעיכה ×{0} (תרחיש)").format(*n),
}
TRADE_HE = {
    "Narrower FOV": "שדה ראייה צר יותר",
    "Larger and heavier lens": "עדשה גדולה וכבדה יותר",
    "Angle-dependent vibration sensitivity": "רגישות גבוהה יותר לרעידות זוויתיות",
    "Slower optics (less flux per pixel)": "אופטיקה איטית יותר (פחות שטף לפיקסל)",
    "Mass, cost, depth of field and aberration sensitivity grow": "גידול במסה ובעלות, עומק שדה קטן יותר ורגישות "
                                                                  "גבוהה יותר לאברציות",
    "Data rate and power grow with the pixel count": "קצב הנתונים וההספק גדלים עם מספר הפיקסלים",
    "Smaller wells - check saturation": "בארות קטנות יותר – יש לבדוק רוויה",
    "Wider FOV only; IFOV unchanged (a pixel count is not a resolution)": "שדה ראייה רחב יותר בלבד; IFOV ללא שינוי "
                                                                         "(מספר פיקסלים אינו רזולוציה)",
    "Detector / camera replacement cost": "עלות החלפת גלאי / מצלמה",
    "Detector / read-out replacement": "החלפת גלאי / מעגל קריאה",
    "Less temporal sampling": "דגימה זמנית נמוכה יותר",
    "More motion blur for moving targets / platforms": "יותר טשטוש תנועה במטרות / פלטפורמות נעות",
    "More motion blur": "יותר טשטוש תנועה",
    "Saturation risk": "סיכון לרוויה",
    "Coating cost; in thermal bands lower emission of the optics as well": "עלות ציפוי; בתחום התרמי גם פליטה עצמית "
                                                                           "נמוכה יותר של האופטיקה",
    "Optics cost": "עלות אופטיקה",
    "Gimbal / stabilizer cost and mass": "עלות ומסה של גימבל / מייצב",
}
NOTE_HE = {
    "The imported optics MTF belongs to the current lens; a new lens needs its own MTF curve (the computed effect is "
    "approximate).": "עקומת ה־MTF האופטית המיובאת שייכת לעדשה הנוכחית; עדשה חדשה דורשת עקומת MTF משלה (ההשפעה "
                     "המחושבת מקורבת).",
    "The measured NETD is held constant although the F-number / collected flux changes - it is only valid for the "
    "optics it was measured with.": "ערך ה־NETD המדוד נשמר קבוע אף שיחס המוקד והשטף הנקלט משתנים – הוא תקף רק "
                                    "לאופטיקה שעמה נמדד.",
    "A cooled detector's cold shield must match the faster F-number.": "יש להתאים את מגן הקור (cold shield) של "
                                                                       "הגלאי המקורר ליחס המוקד המהיר יותר.",
    "Incomplete simulation (Ch. 6): define the complete profile of the candidate detector before deciding.":
        "סימולציה לא מלאה (פרק 6 במסמך המתודולוגיה): יש להגדיר פרופיל מלא של הגלאי המועמד לפני קבלת החלטה.",
    "NETD is not MRTD: valid only if the new NETD is measured under the same F-number, background and integration "
    "conditions (ASTM E1543).": "NETD אינו MRTD: ההשוואה תקפה רק אם ה־NETD החדש נמדד באותו יחס מוקד, רקע ותנאי "
                                "אינטגרציה (ASTM E1543).",
    "Noise model is channel dependent; use EMVA 1288 data of the candidate sensor.": "מודל הרעש תלוי ערוץ; יש "
                                                                                     "להשתמש בנתוני EMVA 1288 של "
                                                                                     "החיישן המועמד.",
    "Conditional: check motion blur, saturation and the mission's frame-rate needs (T-07).": "מותנה: יש לבדוק "
        "טשטוש תנועה, רוויה ודרישות קצב הפריימים של המשימה (T-07).",
    "Conditional: saturation in bright scenes and motion blur must be checked (T-07).": "מותנה: יש לבדוק רוויה "
                                                                                        "בסצנות בהירות וטשטוש "
                                                                                        "תנועה (T-07).",
    "Transmission changes the signal, it is not an MTF factor.": "התמסורת משנה את האות; היא אינה גורם MTF.",
    "Upper bound: real optics keep some aberration - measure the lens MTF first.": "חסם עליון: באופטיקה אמיתית "
                                                                                   "נותרות אברציות – יש למדוד "
                                                                                   "תחילה את ה־MTF של העדשה.",
    "Use measured jitter (time series or PSD) if available.": "יש להשתמש בנתוני jitter מדודים (סדרת זמן או PSD) "
                                                              "אם קיימים.",
    "Environment scenario, not a hardware improvement (T-08).": "תרחיש סביבתי, לא שיפור חומרה (T-08).",
    "No range effect in this model configuration: the task is limited elsewhere, or the parameter is not connected "
    "to the range engine (Ch. 4).": "אין השפעה על הטווח בתצורת מודל זו: המשימה מוגבלת במקום אחר, או שהפרמטר "
                                    "אינו מחובר למנוע הטווח (פרק 4).",
    "Detector noise, well capacity, QE and NETD are held constant - a real detector with another pitch would change "
    "them; they are not inferred from the pitch.": "רעש הגלאי, קיבול הבאר, QE ו־NETD נשמרים קבועים – גלאי אמיתי "
                                                   "בגודל פיקסל אחר ישנה אותם; הם אינם נגזרים מגודל הפיקסל.",
    "Focal length scaled to keep the FOV; aperture diameter kept, so the F-number changes.": "אורך המוקד הותאם "
        "לשמירת שדה הראייה; קוטר המפתח נשמר ולכן יחס המוקד משתנה.",
}
VALIDATE_HE = {
    "focal_length": "צילום מטרת בדיקה (או מטרה מייצגת) באותו מסלול עם שני אורכי המוקד; מדידת MTF / SFR של העדשה "
                    "החדשה והשוואת ΔR החזוי לנצפה.",
    "aperture": "מדידת MTF ו־SNR / NETD עם המפתח החדש; וידוא התאמת מגן הקור ובדיקת עומק השדה.",
    "detector": "השגת פרופיל מלא של הגלאי המועמד (QE, רעש, קיבול באר, NETD) והרצה חוזרת; מדידה לפי EMVA 1288 / "
                "ASTM E1543.",
    "detector_format": "בדיקת שדה הראייה וקצב הנתונים; אין לצפות לשיפור טווח.",
    "noise": "מדידת NETD (ASTM E1543) או רעש קריאה (EMVA 1288) של המצלמה המועמדת באותם תנאי רקע ויחס מוקד.",
    "exposure": "ניסוי בקצב / זמן האינטגרציה החדש: בדיקת רוויה, טשטוש תנועה ודרישות המשימה.",
    "transmission": "מדידת תמסורת ספקטרלית של האופטיקה לפני ואחרי ניקוי / ציפוי.",
    "optics_quality": "מדידת MTF / SFR של העדשה (ISO 12233) ובדיקת מיקוד לפני החלטה על החלפת אופטיקה.",
    "motion": "מדידת jitter על הפלטפורמה (סדרת זמן / PSD) לפני ואחרי שיפור הייצוב.",
    "environment": "תיעוד ראות / לחות בזמן הניסוי; אין זה שינוי במערכת.",
}
MF_TITLE_HE = {"Optical MTF": "MTF אופטי", "Noise / NETD": "רעש / NETD", "Noise": "רעש", "Spectral QE": "QE ספקטרלי",
               "Target": "מטרה", "Atmosphere": "אטמוספרה", "Line-of-sight motion": "תנועת קו ראייה",
               "No ranked action": "אין פעולה מדורגת"}
MONTHS_HE = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר",
             "דצמבר"]
REFERENCES = [
    ("D3", "TRM – מנוע המלצות לשיפור טווחי תצפית: מסגרת מדעית לפיתוח Range Improvement Advisor (דוח מחקר יישומי, "
           "אוקטובר 2026).", "המתודולוגיה שעליה מבוסס דוח זה: baseline, ΔR, רמות ראיות, אבחון, רגישויות ודירוג."),
    ("1", "ISO 9334:2012. Optics and photonics — Optical transfer function — Definitions and mathematical "
          "relationships.", "הגדרת OTF ו־MTF ומונחי המדידה."),
    ("2", "ISO 12233:2024. Digital cameras — Resolution and spatial frequency responses.",
     "הפרדת מספר פיקסלים מרזולוציה ומדידת SFR במצלמות דיגיטליות."),
    ("3", "EMVA 1288 Release 4.0, Linear and General. European Machine Vision Association.",
     "אפיון רגישות ורעש של מצלמות."),
    ("4", "NIST / JCGM. Measurement uncertainty; GUM and Monte Carlo propagation.", "עקרון הפצת אי־ודאות."),
    ("5", "ASTM E1543-14. Standard Practice for Noise Equivalent Temperature Difference of Thermal Imaging Systems.",
     "מדידת NETD ומגבלות השוואתה בין מערכות."),
    ("6", "Ansys Zemax OpticStudio, FFT MTF User Guide.", "MTF FFT הכולל עקיפה; הימנעות מספירה כפולה."),
    ("7", "Vollmerhausen, R.H., Jacobs, E., Driggers, R. (2004). New metric for predicting target acquisition "
          "performance. Optical Engineering 43(11), 2806–2818.", "מגבלות קריטריון Johnson ומדד TTP."),
]


def tn(name):
    return TASK_HE.get(name, name)


def _km(v, spec="%.2f"):
    return "-" if v is None or (isinstance(v, float) and not np.isfinite(v)) else spec % v


def _pct(v):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "-"
    return "0.0%" if abs(v) < 0.05 else "%+.1f%%" % v


def _sens(v):
    if v is None or not np.isfinite(v):
        return "-"
    return "0.00" if abs(v) < 0.005 else "%+.2f" % v


def action_he(a):
    fn = LABEL_HE.get(a["id"])
    if fn:
        try:
            return fn(re.findall(r"(?<![\w.])[-+]?\d+(?:\.\d+)?", a["label"].replace("x", " ")), a["label"])
        except (IndexError, ValueError):
            pass
    return a["label"]


def trade_he(s):
    m = re.match(r"FOV ([\d.]+) -> ([\d.]+) deg \(([+-]?\d+) %\)", s)
    if m:
        return "שדה ראייה (FOV) %s° → %s° (%s%%)" % m.groups()
    m = re.match(r"F-number ([\d.]+) -> ([\d.]+)", s)
    if m:
        return "יחס מוקד F/# %s → %s" % m.groups()
    m = re.match(r"Larger and heavier lens \(D x([\d.]+)\)", s)
    if m:
        return "עדשה גדולה וכבדה יותר (D ×%s)" % m.group(1)
    return TRADE_HE.get(s, s)


def calibration_he(s):
    if not s:
        return "סטטוס כיול לא ידוע"
    if s.startswith("Uncalibrated engineering estimate"):
        return "אומדן הנדסי לא מכויל (אינו הסתברות גילוי מאומתת)"
    m = re.match(r"Sensor figure of merit measured \((.*)\); task criteria not calibrated", s)
    if m:
        return "מדד ביצועי החיישן נמדד (%s); קריטריוני המשימה אינם מכוילים" % m.group(1)
    if s.startswith("Uncalibrated estimate - algorithm observer"):
        return "אומדן לא מכויל – צופה אלגוריתמי" + s[len("Uncalibrated estimate - algorithm observer"):]
    return s


def note_he(s):
    m = re.match(r"FOV ([\d.]+) deg below the minimum ([\d.]+) deg \(T-09\)", s)
    if m:
        return "שדה הראייה %s° קטן מהמינימום שהוגדר %s° (T-09)" % m.groups()
    return NOTE_HE.get(s, s)


def assumption_he(s):
    m = re.match(r"(.*) \+/-([\d.]+) %", s)
    if m:
        return "%s ±%s%%" % (PARAM_HE.get(m.group(1), m.group(1)), m.group(2))
    return s


def measure_first_he(key, text, rank_task):
    title = MF_TITLE_HE.get(key, key)
    if key == "Optical MTF":
        body = ("ה־MTF האופטי תיאורטי (עקיפה%s). יש להזין עקומת MTF מדודה או Zemax FFT MTF בתדרי המשימה "
                "(ISO 9334 / ISO 12233 SFR) – ולוודא מיקוד לפני כל המלצה על עדשה." %
                ("" if "aberration" not in text else " + מודל אברציות"))
    elif key == "Noise / NETD":
        body = ("ה־NETD מחושב ממודל גלאי כללי. יש למדוד את NETD המצלמה (ASTM E1543) ביחס המוקד, בזמן האינטגרציה "
                "וברקע המבצעיים." if "calculated" in text else
                "ערך ה־NETD הוא ברירת מחדל / הנחה. יש להזין NETD מדוד יחד עם תנאי הבדיקה שלו.")
    elif key == "Noise":
        body = "רעש הקריאה וזרם החושך הם ערכי ברירת מחדל. יש להשתמש בנתוני EMVA 1288 של החיישן."
    elif key == "Spectral QE":
        m = re.search(r"'([^']*)'", text)
        body = ("עקומת ה־QE היא ברירת מחדל כללית (%s). יש להזין את התגובה הספקטרלית המדודה של הגלאי." %
                (m.group(1) if m else "preset"))
    elif key == "Target":
        body = ("ממדי המטרה וחתימתה הם ברירות מחדל. יש לאשר את הממד המאפיין ואת הניגודיות של סט המטרות האמיתי – "
                "הטווח תלוי בהם ישירות.")
    elif key == "Atmosphere":
        body = ("מקדם הדעיכה הוא ברירת מחדל. יש לתעד ראות / לחות בזמן הניסוי או לייבא תמסורת ספקטרלית מסוג MODTRAN "
                "(ברמת האות, לא כגורם MTF).")
    elif key == "Line-of-sight motion":
        body = ("לא מודלה תנועת פלטפורמה. יש להזין jitter מדוד (סדרת זמן או PSD) אם המצלמה אינה על תושבת קשיחה – "
                "אחרת השיפור מאורך מוקד ארוך מוערך ביתר.")
    elif key == "No ranked action":
        body = ("אף פעולה ישימה אינה משפרת את טווח משימת %s בתוך האילוצים – יש להשלים את הנתונים שלהלן לפני דירוג "
                "חלופות." % tn(rank_task))
    else:
        body = text
    return title, body


def _date_he(d=None):
    d = d or datetime.date.today()
    return "%d ב%s %d" % (d.day, MONTHS_HE[d.month - 1], d.year)


def _fmt_val(v):
    if isinstance(v, float):
        return "%.4g" % v
    return str(v)


def _range_text(R0, a):
    if R0 is None:
        return "< %.2f" % a["R"][0]
    if not np.isfinite(R0):
        return "> %.1f" % a["R"][-1]
    return "%.2f" % R0


# ---------------------------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------------------------
def _style(ax, size=7.5):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#8a96a3")
        ax.spines[s].set_linewidth(0.7)
    ax.tick_params(labelsize=size, colors="#3b4754", width=0.6, length=3)
    ax.grid(alpha=0.25, lw=0.5)
    ax.set_axisbelow(True)
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_fontproperties(_fp(("s", "he"), size))


def _fig_range(res):
    def draw(fig, rect):
        a = res["range"]["atm"][0]
        ax = fig.add_axes(rect)
        R, sig = np.asarray(a["R"], float), np.asarray(a["signal"], float)
        ok = np.isfinite(sig) & (sig > 0)
        ax.loglog(R[ok], sig[ok], color=INK, lw=1.6, label=vis("אות זמין במטרה"))
        r0s = []
        for i, t in enumerate(a["tasks"]):
            Ra, mn = np.asarray(t["R_avg"], float), np.asarray(t["mn_avg"], float)
            m = np.isfinite(mn) & (mn > 0) & np.isfinite(Ra) & (Ra > 0)
            col = SERIES[i % len(SERIES)]
            ax.loglog(Ra[m], mn[m], color=col, lw=1.2, ls="--", label=vis("סף משימת %s" % tn(t["name"])))
            if t["R0"] is not None and np.isfinite(t["R0"]):
                r0s.append(t["R0"])
                ax.axvline(t["R0"], color=col, lw=0.8, alpha=0.7)
                ax.annotate("%.2f km" % t["R0"], xy=(t["R0"], 1), xycoords=("data", "axes fraction"),
                            xytext=(2, -10 - 9 * i), textcoords="offset points", fontsize=7, color=col)
        lo, hi = (max(R.min(), min(r0s) / 20), min(R.max(), max(r0s) * 4)) if r0s else (R.min(), R.max())
        ax.set_xlim(lo, hi)
        vis_sig = sig[ok & (R >= lo) & (R <= hi)]
        if vis_sig.size:                                    # thresholds diverge near the limit: clip to the signal
            ax.set_ylim(vis_sig.min() / 8, vis_sig.max() * 8)
        ax.set_xlabel(vis("טווח [km]"), fontproperties=_fp(("s", "he"), 8))
        q = "%s [%s]" % (res["range"].get("quantity", ""), res["range"].get("unit", ""))
        ax.set_ylabel(vis("אות / סף %s" % q), fontproperties=_fp(("s", "he"), 8))
        _style(ax)
        ax.legend(prop=_fp(("s", "he"), 7.2), frameon=False, loc="best")
    return draw


def _fig_dri(adv):
    def draw(fig, rect):
        tasks = adv["tasks"]
        top = [ADV.action_by_id(adv, i) for i in adv["top"]]
        ax = fig.add_axes(rect)
        series = [(vis("ייחוס"), [adv["base"][t] for t in tasks], "#9aa5b1")]
        for k, a in enumerate(top):
            series.append((vis("המלצה %d" % (k + 1)), [a["results"][t]["after"] or 0.0 for t in tasks],
                           SERIES[k % len(SERIES)]))
        n = len(series)
        w = 0.8 / n
        x = np.arange(len(tasks))
        for k, (lab, vals, col) in enumerate(series):
            b = ax.bar(x + (k - (n - 1) / 2) * w, vals, w * 0.92, color=col, label=lab)
            for rect_, v in zip(b, vals):
                ax.annotate("%.2f" % v, xy=(rect_.get_x() + rect_.get_width() / 2, v), xytext=(0, 2),
                            textcoords="offset points", ha="center", fontsize=6.3, color="#3b4754")
        ax.set_xticks(x)
        ax.set_xticklabels([vis("%s" % tn(t)) for t in tasks])
        ax.set_ylabel(vis("טווח [km]"), fontproperties=_fp(("s", "he"), 8))
        _style(ax)
        ax.legend(prop=_fp(("s", "he"), 7.2), frameon=False, ncol=n, loc="upper right")
        ax.set_ylim(0, max(max(v) for _l, v, _c in series) * 1.18)
    return draw


def _fig_whatif(adv):
    def draw(fig, rect):
        t = adv["rank_task"]
        ok = [a for a in adv["actions"] if a["ok"]]
        ok.sort(key=lambda a: a["results"][t]["gain_pct"] or 0.0)
        r = list(rect)
        r[0] += r[2] * 0.30
        r[2] *= 0.68
        ax = fig.add_axes(r)
        for i, a in enumerate(ok):
            g = a["results"][t]["gain_pct"] or 0.0
            env = a["kind"] == "environment"
            col = ACCENT if a.get("rank") else ("#e8d5b5" if env else "#c3c9d4")
            ax.barh(i, g, color=col, hatch="///" if env or a.get("constraint") else None, edgecolor="white", lw=0)
            ax.annotate("%s%s" % (_pct(g), "  #%d" % a["rank"] if a.get("rank") else ""), xy=(max(g, 0), i),
                        xytext=(3, 0), textcoords="offset points", va="center", fontsize=6.8, color="#3b4754")
        ax.set_yticks(np.arange(len(ok)))
        ax.set_yticklabels([vis(SHORT_HE.get(a["id"], a["label"][:30])) for a in ok])
        ax.axvline(0, color="#555", lw=0.7)
        ax.set_xlabel(vis("שינוי בטווח משימת %s לעומת הייחוס [%%]" % tn(t)), fontproperties=_fp(("s", "he"), 8))
        _style(ax)
        ax.yaxis.tick_left()
        lo, hi = ax.get_xlim()
        ax.set_xlim(lo, hi + (hi - lo) * 0.15)
    return draw


def _fig_sens(adv):
    def draw(fig, rect):
        rows = [s for s in adv["sensitivities"] if s["ok"]]
        tasks = adv["tasks"]
        r = list(rect)
        r[0] += r[2] * 0.30
        r[2] *= 0.68
        ax = fig.add_axes(r)
        n = len(tasks)
        h = 0.8 / n
        y = np.arange(len(rows))
        for k, t in enumerate(tasks):
            vals = [s["S"].get(t, np.nan) for s in rows]
            ax.barh(y + (k - (n - 1) / 2) * h, np.nan_to_num(vals), h * 0.92, color=SERIES[k % len(SERIES)],
                    label=vis(tn(t)))
        ax.set_yticks(y)
        ax.set_yticklabels([vis(PARAM_HE.get(s["label"], s["label"])) for s in rows])
        ax.axvline(0, color="#555", lw=0.7)
        ax.set_xlabel(vis("רגישות מנורמלת S  =  (x/R)·dR/dx"), fontproperties=_fp(("s", "he"), 8))
        _style(ax)
        ax.invert_yaxis()
        ax.legend(prop=_fp(("s", "he"), 7.2), frameon=False, loc="lower right")
    return draw


def _fig_limiting(adv):
    def draw(fig, rect):
        lim = adv["limiting"]
        rows = lim["rows"]
        tasks = adv["tasks"]
        r = list(rect)
        r[0] += r[2] * 0.33
        r[2] *= 0.65
        ax = fig.add_axes(r)
        n = len(tasks)
        h = 0.8 / n
        y = np.arange(len(rows))
        for k, t in enumerate(tasks):
            ax.barh(y + (k - (n - 1) / 2) * h, [x["gain_pct"].get(t, 0.0) for x in rows], h * 0.92,
                    color=SERIES[k % len(SERIES)], label=vis(tn(t)))
        ax.set_yticks(y)
        ax.set_yticklabels([vis(FACTOR_HE.get(x["factor"], x["factor"])) for x in rows])
        ax.set_xlabel(vis("שיפור טווח כאשר הגורם מוסר [%]"), fontproperties=_fp(("s", "he"), 8))
        _style(ax)
        ax.invert_yaxis()
        ax.legend(prop=_fp(("s", "he"), 7.2), frameon=False, loc="lower right")
    return draw


# ---------------------------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------------------------
def _reasons_he(t, d, limiting):
    out = []
    if d["type"] == "sampling" and "cyc_nyq" in t:
        out.append("המשימה דורשת %.1f מחזורים לרוחב המטרה, אך גבול נייקוויסט של הגלאי מאפשר רק %.1f "
                   "(%.1f × %.1f פיקסלים על המטרה)." % (t["lp"], t["cyc_nyq"], t["pix_h"], t["pix_v"]))
    elif "cnr_task" in t and ("contrast" in t.get("limiter", "") or "noise" in t.get("limiter", "")):
        out.append("המטרה דגומה היטב (%.1f מחזורים זמינים, %.1f נדרשים), אך ה־CNR בטווח המשימה הוא רק %.2f." % (
            t.get("cyc_nyq", float("nan")), t["lp"], t["cnr_task"]))
    elif "mtf_task" in t:
        out.append("המטרה דגומה היטב; ה־MTF של המערכת בתדר המשימה הוא %.2f." % t["mtf_task"])
    if d.get("top_factor"):
        g = next((r["gain_pct"].get(t["name"]) for r in (limiting or {}).get("rows", [])
                  if r["factor"] == d["top_factor"]), None)
        if g is not None:
            out.append("הסרת הגורם ״%s״ מניבה את השיפור הגדול ביותר (%+.1f%%)." % (
                FACTOR_HE.get(d["top_factor"], d["top_factor"]), g))
    return " ".join(out) or "; ".join(d["reasons"])


def build(project, res, adv):
    """Lay out the complete report; returns the _Doc (pages kept in memory until save)."""
    _setup_fonts()
    name = project.get("name") or "TRM"
    b = adv["baseline"]
    g = b["geometry"]
    tasks = adv["tasks"]
    rank = adv["rank_task"]
    pv = res.get("provenance") or {}
    db = res.get("dashboard") or {}
    rg = res.get("range") or {"atm": []}
    top = [ADV.action_by_id(adv, i) for i in adv["top"]]
    ok_actions = [a for a in adv["actions"] if a["ok"]]
    cat = "%s / %s" % (pv.get("category", project.get("category", "")), pv.get("imager_type", ""))
    doc = _Doc("TRM | דוח ביצועי טווח DRI והמלצות לשיפור", name)

    # --- title page
    doc.new_page(decor=False)
    doc.y = 205
    doc.para("**דוח טכני · הנדסת אופטיקה והדמיה**", size=10.5, color=ACCENT, justify=False, after=40)
    doc.rect(doc.right - 82, doc.y, 82, 4.5, ACCENT)
    doc.y += 44
    doc.para("ביצועי טווח DRI והמלצות לשיפור המערכת", size=27, color=HEAD, role="h", lead=1.3, justify=False,
             after=14)
    doc.para("סיכום תוצאות מנוע הטווח TRM וניתוח Range Improvement Advisor: אבחון צווארי בקבוק, רגישויות, "
             "תרחישי What-if והמלצות מדורגות", size=14, color="#4b5d70", role="s", lead=1.5, justify=False, after=34)
    doc.hline(doc.ML, doc.right, doc.y, lw=0.8)
    doc.y += 18
    meta = [("פרויקט", name), ("תצורה", "%s · %s" % (cat, pv.get("environment", ""))),
            ("מזהה ייחוס (baseline)", "%s · Run ID %s" % (b["baseline_id"], b["run_id"])),
            ("גרסת מודל", b["model_version"]), ("משימה לדירוג", tn(rank)),
            ("תאריך הפקה", _date_he()),
            ("שפה", "עברית · מימין לשמאל · נוסחאות, יחידות ומזהים משמאל לימין")]
    for k, v in meta:
        doc.para("**%s:** %s" % (k, v), size=10.5, color="#3b4754", justify=False, lead=1.55, after=2)
    doc.y += 10
    doc.para("כל המספרים בדוח הם פלטי מודל הביצועים של TRM ואינם מכוילים אלא אם צוין אחרת (%s). הדוח ייעוצי "
             "בלבד: הפרויקט עצמו אינו משתנה, וכל המלצה מחייבת אימות במדידה לפני החלטה על חומרה." %
             calibration_he(b.get("calibration")), size=9, color=MUTED, after=0)

    # --- abstract
    doc.new_page()
    doc.para("תקציר", size=20, color=HEAD, role="h", lead=1.35, after=4, justify=False)
    doc.hline(doc.ML, doc.right, doc.y, lw=1.4)
    doc.y += 14
    rng = " · ".join("%s %s km" % (tn(t), _km(adv["base"][t])) for t in tasks)
    doc.para("דוח זה מסכם את תוצאות מנוע הטווח TRM עבור התצורה ״%s״ (%s) ומציג המלצות מבוססות־חישוב לשיפור טווחי "
             "הגילוי, ההבחנה והזיהוי (DRI). כל החלופות חושבו מחדש באותו מנוע, עם אותה מטרה, אותה סביבה ואותה גרסת "
             "מודל (%s), ותצורת הייחוס נשמרה כצילום מצב %s." % (name, cat, b["model_version"], b["baseline_id"]))
    d_rank = adv["diagnosis"].get(rank, {})
    doc.para("טווחי הייחוס המחושבים הם: %s. מועמד צוואר הבקבוק במשימת %s הוא **%s**. נבחנו %d פעולות What-if "
             "עקביות פיזיקלית (%d מהן תקפות), ונבחרו עד שלוש פעולות שונות מהותית המשפרות את טווח משימת %s בתוך "
             "האילוצים%s." % (rng, tn(rank), TYPE_HE.get(d_rank.get("type"), "-"), len(adv["actions"]),
                               len(ok_actions), tn(rank),
                               " (שדה ראייה מינימלי %.3g°)" % adv["constraints"]["min_fov_deg"]
                               if adv["constraints"]["min_fov_deg"] else ""))
    if top:
        a = top[0]
        x = a["results"][rank]
        doc.callout("ממצא מרכזי",
                    "ההמלצה המובילה היא %s: טווח משימת %s משתנה מ־%s km ל־%s km (ΔR = %+.2f km, %s), ברמת ראיות "
                    "״%s״. %s" % (action_he(a), tn(rank), _km(x["before"]), _km(x["after"]), x["delta_km"] or 0.0,
                                   _pct(x["gain_pct"]), SUPPORT_HE[a["support"]],
                                   "שתי ההמלצות הבאות: " + "; ".join(
                                       "%s (%s)" % (SHORT_HE.get(o["id"], o["label"]), _pct(o["results"][rank]
                                                                                           ["gain_pct"]))
                                       for o in top[1:]) + "." if len(top) > 1 else ""))
    else:
        doc.callout("ממצא מרכזי", "אף פעולה ישימה אינה משפרת את טווח משימת %s בתוך האילוצים. יש להשלים תחילה את "
                                 "נתוני המדידה המפורטים בפרק 8." % tn(rank))
    doc.para("**מעמד ראיות:** אלו תחזיות מודל לא מכוילות ולא רווחי טווח מאומתים. שינויי סביבה מוצגים כתרחישים "
             "בלבד ולעולם לא כשיפור. אי־הוודאות מוצגת כרגישות לטווחי ההנחות ולא כרווח סמך סטטיסטי.", size=10)
    doc.para("**מילות מפתח:** TRM · DRI · Range Prediction · Counterfactual Analysis · IFOV · MTF · NETD · SNR · "
             "Sensitivity Analysis · Pareto", size=10, justify=False)

    # --- table of contents (filled after layout)
    doc.new_page()
    toc_page = len(doc.pages) - 1
    doc.para("תוכן עניינים", size=20, color=HEAD, role="h", lead=1.35, after=4, justify=False)
    doc.hline(doc.ML, doc.right, doc.y, lw=1.4)
    doc.y += 14
    toc_y = doc.y

    # --- Ch. 1
    doc.chapter("01", "מטרת הדוח ושיטת העבודה", new_page=True)
    doc.para("מטרת הדוח היא לענות על שאלה הנדסית אחת: מה מגביל כעת את טווחי ה־DRI של המערכת, ואיזה שינוי פיזיקלי "
             "או תפעולי צפוי לשפר אותם – בכמה, באיזו רמת ראיות ובאיזה מחיר. מנוע ההמלצות הוא שכבה ייעוצית מעל "
             "מנוע הטווח הקיים: הוא אינו משנה את הפרויקט, ואינו מחליף מדידה.")
    doc.section("1.1 חישוב חוזר נגדי (Counterfactual)")
    doc.para("כל פעולה a מוגדרת כשינוי עקבי בקבוצת פרמטרים (למשל החלפת עדשה משנה יחד את f, D ו־F/#; החלפת גלאי "
             "משנה יחד pitch, שטח פעיל ופורמט). התצורה החלופית נבדקת לתקפות פיזיקלית ומחושבת מחדש באותו מנוע:")
    doc.formula(["Delta_R_t(a) = F_t(x_a, s, m, v) - F_t(x_0, s, m, v)",
                 "Gain_t(a) [%] = 100 * Delta_R_t(a) / R_t,0"])
    doc.para("כאשר t היא המשימה, x וקטור מאפייני המערכת, s תרחיש הסביבה, m מודל המשימה והמטרה ו־v גרסת החישוב. "
             "כאשר R_t,0 = 0 או אינו מוגדר לא מחושב אחוז שיפור (T-03).", size=9.8, color="#3b4754")
    doc.section("1.2 רמות ראיות")
    doc.table(["רמת תחזית", "משמעות", "אופן ההצגה בדוח"],
              [["נתמכת מודל", "מנוע הטווח מקבל ישירות את הפרמטר והשפעתו נבדקה.", "לפני/אחרי, יחידות ומגבלות תוקף."],
               ["אומדן מקורב", "קיים קשר פיזיקלי שימושי, אך חלק מהתופעות מחוץ למודל.", "מספר מסומן כמקורב + הערה."],
               ["מדוד תחילה", "אין נתון מבוסס או שהמנוע אינו מחשב את התופעה.", "המלצת מדידה / כיול ללא תחזית."]],
              [0.22, 0.43, 0.35], caption="רמות הראיות של ההמלצות (לפי סעיף 2.3 במסמך המתודולוגיה [D3]).",
              bold_first=True)

    # --- Ch. 2 baseline
    doc.chapter("02", "תצורת המערכת ותרחיש הייחוס")
    doc.para("תצורת הייחוס נשמרה כצילום מצב קפוא (סעיף 2.1 ב־[D3]): קלטים ויחידות, מקורות הערכים, גרסת המודל, "
             "מזהה ריצה דטרמיניסטי (אותם קלטים ואותה גרסה ⇐ אותו מזהה) וחותמת זמן.")
    trace = [["מזהה ייחוס", b["baseline_id"]], ["Run ID", b["run_id"]], ["גרסת מודל", b["model_version"]],
             ["זמן חישוב", b["time"].replace("T", " ")], ["מנוע", b.get("engine", "")],
             ["מודל משימה", b.get("model", "") or db.get("model", "")],
             ["סטטוס כיול", calibration_he(b.get("calibration", "") or db.get("calibration", ""))]]
    doc.table(["פריט", "ערך"], trace, [0.24, 0.76], caption="עקיבות תרחיש הייחוס.", bold_first=True)
    rows = []
    for label, _path, val, unit, src in pv.get("key_inputs", []):
        rows.append([PARAM_HE.get(label, label), _fmt_val(val), UNIT_HE.get(unit, unit), SOURCE_HE.get(src, src)])
    rows += [["שדה ראייה (אופקי × אנכי)", "%.3f × %.3f" % (g.get("fov_h_deg", float("nan")),
                                                         g.get("fov_v_deg", float("nan"))), "°", "נגזר"],
             ["IFOV = p / f", "%.4g" % g.get("ifov_urad", float("nan")), "µrad", "נגזר"],
             ["יחס מוקד אפקטיבי F/#", "%.3g" % g["F"], "", "נגזר"]]
    if rows:
        doc.table(["פרמטר", "ערך", "יחידה", "מקור הנתון"], rows, [0.4, 0.22, 0.14, 0.24],
                  caption="קלטי מפתח, מקורותיהם וגדלים גאומטריים נגזרים.", aligns=["right", "center", "center",
                                                                                      "right"])

    # --- Ch. 3 DRI results
    doc.chapter("03", "תוצאות טווחי DRI")
    if rg["atm"]:
        a0 = rg["atm"][0]
        doc.para("הטווחים חושבו עבור %s. לכל משימה מוצגים הטווח, מספר הפיקסלים והמחזורים על המטרה בטווח זה, ה־MTF "
                 "בתדר המשימה, ה־CNR והגורם המגביל שזיהה המנוע. מודל המשימה מפורט בטבלה 2." % a0["label"])
        trows = []
        for t in db.get("tasks", []):
            trows.append(["%s (%s)" % (tn(t["name"]), t["name"]), "%g" % t["lp"], _range_text(t["R0"], a0),
                          "%.1f × %.1f" % (t["pix_h"], t["pix_v"]) if "pix_h" in t else "-",
                          "%.2f" % t["cyc_nyq"] if "cyc_nyq" in t else "-",
                          "%.2f" % t["mtf_task"] if "mtf_task" in t else "-",
                          "%.3g" % t["cnr_task"] if "cnr_task" in t else "-",
                          LIMITER_HE.get(t.get("limiter", ""), t.get("limiter", "-"))])
        doc.table(["משימה", "קריטריון [lp]", "טווח [km]", "פיקסלים על המטרה", "מחזורים (נייקוויסט)",
                   "MTF בתדר המשימה", "CNR", "גורם מגביל"], trows,
                  [0.19, 0.09, 0.1, 0.13, 0.12, 0.11, 0.08, 0.18], caption="טווחי DRI בתרחיש הייחוס.",
                  aligns=["right"] + ["center"] * 6 + ["right"], bold_first=True)
        doc.figure(_fig_range(res), 215, "האות הזמין במטרה לעומת סף כל משימה כפונקציה של הטווח; נקודת החיתוך היא "
                                         "טווח המשימה (קווים אנכיים).")
        if len(rg["atm"]) > 1:
            other = [["%s" % a["label"]] + [_range_text(t["R0"], a) for t in a["tasks"]] for a in rg["atm"][1:]]
            doc.table(["אטמוספרה"] + ["%s [km]" % tn(t["name"]) for t in a0["tasks"]], other,
                      [0.4] + [0.6 / len(a0["tasks"])] * len(a0["tasks"]),
                      caption="טווחי DRI בתנאי אטמוספרה נוספים שהוגדרו בפרויקט.",
                      aligns=["right"] + ["center"] * len(a0["tasks"]))
        doc.para("**סטטוס כיול:** %s. **סיכון התחזות (aliasing):** %s." % (
            calibration_he(db.get("calibration")), ALIAS_HE.get(db.get("aliasing"), db.get("aliasing", "-"))), size=9.8)

    # --- Ch. 4 diagnosis
    doc.chapter("04", "אבחון צווארי בקבוק")
    doc.para("לכל משימה נקבע **מועמד צוואר בקבוק** (bottleneck candidate) מתוך אבחון לוח התוצאות – מספר המחזורים "
             "הנדרש מול גבול נייקוויסט, ה־CNR וה־MTF בתדר המשימה – ומתוך דירוג הגורמים המגבילים. זהו אבחון ראשוני "
             "ולא חד־משמעי, ולכן לכל מועמד מוצעת בדיקת הפרדה (סעיף 4 ב־[D3]).")
    dtasks = {t["name"]: t for t in b.get("tasks", [])}
    drows = []
    for t, d in adv["diagnosis"].items():
        drows.append([tn(t), TYPE_HE.get(d["type"], d["label"]), _reasons_he(dtasks.get(t, {"name": t}), d,
                                                                            adv["limiting"]),
                      TEST_HE.get(d["type"], d["test"])])
    doc.table(["משימה", "מועמד צוואר בקבוק", "נימוק", "בדיקת הפרדה מוצעת"], drows, [0.12, 0.2, 0.4, 0.28],
              caption="מועמדי צוואר הבקבוק לכל משימה.", bold_first=True)
    lim = adv["limiting"]
    if lim and lim.get("rows"):
        doc.section("4.1 דירוג גורמים מגבילים")
        doc.para("כל גורם השפלה בשרשרת ההדמיה הוסר בתורו (אופטיקה אידיאלית, מסלול צלול, חצי רעש וכו׳) והטווח חושב "
                 "מחדש. שיפור גדול מצביע על גורם מגביל משמעותי; זהו חסם עליון תיאורטי ולא פעולה ישימה.")
        doc.table(["גורם שהוסר"] + ["%s" % tn(t) for t in tasks],
                  [[FACTOR_HE.get(r["factor"], r["factor"])] + [_pct(r["gain_pct"].get(t)) for t in tasks]
                   for r in lim["rows"]], [0.46] + [0.54 / len(tasks)] * len(tasks),
                  caption="שיפור הטווח באחוזים כאשר כל גורם מוסר.", aligns=["right"] + ["center"] * len(tasks))
        doc.figure(_fig_limiting(adv), 34 + 22 * len(lim["rows"]), "שיפור הטווח בהסרת כל גורם מגביל, לכל משימה.")

    # --- Ch. 5 sensitivities
    sens = [s for s in adv["sensitivities"] if s["ok"]]
    if sens:
        doc.chapter("05", "רגישויות מקומיות מנורמלות")
        doc.para("הרגישות המנורמלת מבטאת את השינוי היחסי בטווח לשינוי יחסי של 1% בפרמטר, בנקודת העבודה הנוכחית "
                 "(הפרש מרכזי בצעד ±5%; חד־צדדי בקצה התחום). S = 1 פירושו שהטווח גדל באותו שיעור כמו הפרמטר. הערך "
                 "תלוי בנקודת העבודה ואינו קבוע פיזיקלי.")
        doc.formula(["S_i,t ~= (x_i / R_t) * [R_t(x_i+h) - R_t(x_i-h)] / (2h)"])
        doc.table(["פרמטר", "ערך נוכחי"] + ["S %s" % tn(t) for t in tasks] + ["הערה"],
                  [[PARAM_HE.get(s["label"], s["label"]), "%.4g" % s["x0"]] +
                   [_sens(s["S"].get(t)) for t in tasks] +
                   [("ללא השפעה במודל" if s.get("no_effect") else "") + (" · חד־צדדי" if s.get("one_sided") else "")]
                   for s in sens],
                  [0.3, 0.13] + [0.1] * len(tasks) + [0.57 - 0.1 * len(tasks)],
                  caption="רגישויות מקומיות מנורמלות לכל משימה.",
                  aligns=["right", "center"] + ["center"] * len(tasks) + ["right"])
        doc.figure(_fig_sens(adv), 40 + 20 * len(sens), "רגישויות מנורמלות: אורך העמודה הוא השינוי היחסי בטווח "
                                                        "לכל שינוי יחסי בפרמטר.")

    # --- Ch. 6 what-if
    doc.chapter("06", "ניתוח תרחישי What-if")
    doc.para("כל פעולה מקטלוג הפעולות הוחלה על עותק של הפרויקט, נבדקה לתקפות פיזיקלית וחושבה מחדש. פעולות סביבה "
             "מסומנות כתרחיש ואינן מדורגות; פעולות שאינן עומדות באילוצי המשתמש אינן מועדפות (T-08, T-09). צעד "
             "השינוי: %.0f%%." % adv["constraints"]["step_pct"])
    wrows = []
    for a in sorted(adv["actions"], key=lambda a: (a.get("rank") or 99,
                                                   -(a["results"][rank]["gain_pct"] or 0) if a["ok"] else 1e9)):
        if a["ok"]:
            wrows.append([str(a.get("rank") or ""), action_he(a), KIND_HE[a["kind"]], SUPPORT_HE[a["support"]]] +
                         [_pct(a["results"][t]["gain_pct"]) for t in tasks] +
                         ["%.2f" % a["geometry"].get("fov_h_deg", float("nan")),
                          "כן" if a.get("pareto") else ("אילוץ" if a.get("constraint") else "")])
        else:
            wrows.append(["", action_he(a), KIND_HE[a["kind"]], "נדחתה"] + ["-"] * len(tasks) + ["-", ""])
    doc.table(["#", "פעולה", "סוג", "רמת ראיות"] + ["Δ %s" % tn(t) for t in tasks] + ["FOV [°]", "Pareto"], wrows,
              [0.04, 0.4, 0.11, 0.11] + [0.075] * len(tasks) + [0.07, 0.065][:2],
              caption="כל פעולות ה־What-if: שינוי הטווח לכל משימה ושדה הראייה האופקי.", size=8.2,
              aligns=["center", "right", "right", "right"] + ["center"] * (len(tasks) + 2))
    rejected = [a for a in adv["actions"] if not a["ok"]]
    if rejected:
        doc.para("**פעולות שנדחו:** " + " · ".join("%s – %s" % (action_he(a), a["reason"]) for a in rejected),
                 size=9.5)
    doc.figure(_fig_whatif(adv), 40 + 19 * len(ok_actions), "שינוי טווח משימת %s עבור כל פעולה (כחול: שלוש "
                                                            "ההמלצות המובילות; מקווקו: תרחיש סביבתי או הפרת "
                                                            "אילוץ)." % tn(rank))

    # --- Ch. 7 recommendations
    doc.chapter("07", "המלצות לשיפור טווחי ה־DRI")
    if top:
        doc.para("להלן עד שלוש פעולות שונות מהותית (אחת מכל קבוצת פעולות) המדורגות לפי השיפור בטווח משימת %s בתוך "
                 "האילוצים. לכל המלצה מוצג כרטיס החלטה: לפני/אחרי לכל משימה, רמת הראיות, הפשרות, העמידות לטווחי "
                 "ההנחות ושיטת האימות המוצעת (סעיף 8.1 ב־[D3])." % tn(rank))
        doc.figure(_fig_dri(adv), 190, "טווחי DRI בתרחיש הייחוס ולאחר כל אחת מההמלצות המובילות.")
        for k, a in enumerate(top, start=1):
            res_lines = "\n".join("%s: %s → %s km (ΔR = %s km, %s)" % (
                tn(t), _km(r["before"]), _km(r["after"]), _km(r["delta_km"], "%+.3f"),
                _pct(r["gain_pct"]) if r["gain_pct"] is not None else "ללא אחוז (R0 = 0)")
                for t, r in a["results"].items())
            card = [["פעולה", action_he(a)],
                    ["סוג ורמת ראיות", "%s · %s%s" % (KIND_HE[a["kind"]], SUPPORT_HE[a["support"]],
                                                     " · חזית Pareto (שיפור מול FOV)" if a.get("pareto") else "")],
                    ["לפני / אחרי", res_lines]]
            rb = a.get("robustness")
            if rb:
                card.append(["עמידות לטווחי הנחות", "בחישוב מזווג תחת %s, השינוי בטווח משימת %s נע בין %+.3f ל־%+.3f "
                                                    "km (%d חישובים)." % (", ".join(assumption_he(x) for x in
                                                                                    rb["inputs"]), tn(rank),
                                                                          rb["min_km"], rb["max_km"], rb["n"])])
            if a["tradeoffs"]:
                card.append(["פשרות", "\n".join("• " + trade_he(x) for x in a["tradeoffs"])])
            notes = a["notes"] + ([a["constraint"]] if a.get("constraint") else [])
            if notes:
                card.append(["הערות ומגבלות תוקף", "\n".join("• " + note_he(x) for x in notes)])
            if a.get("new_warnings"):
                card.append(["אזהרות מודל חדשות", "\n".join("• " + w for w in a["new_warnings"])])
            card.append(["שיטת אימות מוצעת", VALIDATE_HE.get(a["group"], "מדידה לפני/אחרי באותה משימה, מטרה "
                                                                         "ורקע.")])
            h = doc.table_height(["פריט", "תוצאה"], card, [0.22, 0.78], size=8.8, bold_first=True)
            if h + 40 <= doc.bottom - doc.MT:                  # heading and card on the same page
                doc.need(h + 40)
            doc.section("7.%d המלצה %d: %s" % (k, k, SHORT_HE.get(a["id"], a["label"])))
            doc.table(["פריט", "תוצאה"], card, [0.22, 0.78], caption="כרטיס החלטה – המלצה %d." % k, size=8.8,
                      bold_first=True, keep=True)
    else:
        doc.callout("אין פעולה מדורגת", "אף פעולה ישימה אינה משפרת את טווח משימת %s בתוך האילוצים. ההמלצה היא "
                                        "להשלים תחילה את נתוני המדידה בפרק 8." % tn(rank))
    types = []
    for t in tasks:
        ty = adv["diagnosis"][t]["type"]
        if ty not in types:
            types.append(ty)
    doc.section("7.%d הנחיות לפי סוג צוואר הבקבוק" % (len(top) + 1))
    doc.bullets(["**%s** (%s): %s" % (TYPE_HE.get(ty, ty), ", ".join(tn(t) for t in tasks
                                                                     if adv["diagnosis"][t]["type"] == ty),
                                      GUIDE_HE.get(ty, "")) for ty in types])
    env = [a for a in ok_actions if a["kind"] == "environment"]
    if env:
        e = env[0]
        doc.para("**תרחיש סביבתי (לא שיפור):** %s – טווח משימת %s %s. התוצאה מראה עד כמה הטווח רגיש לתנאי "
                 "האטמוספרה, אך אינה ניתנת להשגה בשינוי המערכת." % (action_he(e), tn(rank),
                                                                    _pct(e["results"][rank]["gain_pct"])), size=10)

    # --- Ch. 8 measure first
    doc.chapter("08", "מדוד תחילה: נתונים המגבילים את אמינות ההמלצות")
    doc.para("כאשר נתון מרכזי הוא ברירת מחדל או תוצר של מודל כללי, גם המלצה מדורגת היטב עלולה להיות שגויה. הפריטים "
             "הבאים הם הפעולות המעשיות להשלמת הנתונים, לפני השקעה בחומרה (כלל השימושיות, פרק 8 ב־[D3]).")
    doc.bullets(["**%s:** %s" % measure_first_he(k, v, rank) for k, v in adv["measure_first"]], numbered=True)

    # --- Ch. 9 conclusions
    doc.chapter("09", "מגבלות ומסקנות")
    doc.para("הדוח נשען על מנוע הטווח של TRM כעוגן: כל שינוי טווח שמוצג בו הוא הפרש בין שתי ריצות של אותו מנוע, "
             "באותה מטרה ובאותה סביבה. לכן הוא חשוף לאותן הנחות של המודל – קריטריון המשימה, מודל הצופה, מודלי "
             "הרעש וה־MTF – ולסטטוס הכיול שלו. שיפור ברזולוציה או ב־MTF אינו שקול בהכרח לשיפור בטווח, ושיפור טווח "
             "במודל אינו מבטיח שיפור בשטח.")
    doc.para("רגישויות ופעולות What-if נבחנו אחת־אחת סביב נקודת העבודה; אינטראקציות בין שינויים גדולים עשויות "
             "לשנות את הדירוג. עלות, מסה והספק אינם מכומתים במודל ומוצגים כפשרות איכותיות בלבד.")
    if top:
        a = top[0]
        concl = ("לשיפור טווחי ה־DRI מומלץ לבחון תחילה את %s (%s בטווח משימת %s, %s), תוך אימות לפי השיטה המוצעת "
                 "בכרטיס ההחלטה. במקביל יש להשלים את %d פריטי ה״מדוד תחילה״, ובראשם %s – שכן הם קובעים את רמת "
                 "הביטחון בכל ההמלצות." % (
                     action_he(a), _pct(a["results"][rank]["gain_pct"]), tn(rank), SUPPORT_HE[a["support"]],
                     len(adv["measure_first"]),
                     MF_TITLE_HE.get(adv["measure_first"][0][0], adv["measure_first"][0][0])
                     if adv["measure_first"] else "-"))
    else:
        concl = ("לא נמצאה פעולה ישימה המשפרת את טווח משימת %s; יש להשלים את נתוני המדידה ולבחון מחדש." % tn(rank))
    doc.callout("המלצה מסכמת", concl)

    # --- appendices
    doc.chapter("א", "אזהרות והנחות המודל")
    doc.para("האזהרות וההנחות להלן הופקו על ידי מנוע הטווח בריצת הייחוס ומובאות כלשונן (באנגלית).", size=10)
    if res.get("warnings"):
        doc.section("אזהרות")
        for w in res["warnings"]:
            doc.para("• " + w, size=9, base="L", align="ltr", justify=False, after=2)
    if res.get("assumptions"):
        doc.y += 6
        doc.section("הנחות")
        for w in res["assumptions"]:
            doc.para("• " + w, size=9, base="L", align="ltr", justify=False, after=2)
    doc.chapter("ב", "ביבליוגרפיה")
    for key, ref, role in REFERENCES:
        doc.para("**[%s]** %s" % (key, ref), size=9.6, justify=False, after=1, lead=1.45)
        doc.para("**תפקיד בדוח:** %s" % role, size=9, color=MUTED, justify=False, after=7, lead=1.45)

    # --- table of contents
    toc_ax = doc.pages[toc_page]["ax"]
    y = toc_y + 6
    for num, title, page in doc.toc:
        size = 11
        p = _layout(spans("**%s**  %s" % (num, title)), size, doc.width - 60)
        _draw_line(toc_ax, p.lines[0], doc.ML + 40, doc.right, y + size * 1.1, size, INK)
        toc_ax.text(doc.ML, y + size * 1.1, str(page), fontproperties=_fp(("r", "la"), size), color=ACCENT,
                    ha="left", va="baseline", parse_math=False)
        doc.hline(doc.ML, doc.right, y + size * 1.55, ax=toc_ax, color="#e3e8ee", lw=0.5)
        y += size * 2.3
    doc.finish_pages()
    return doc


def write_pdf(path, project, res, adv):
    """Write the Hebrew scholarly PDF report (DRI results + advisor recommendations) to `path`."""
    if not adv or adv.get("kind") != "advisor":
        raise ValueError("The Hebrew report needs a Range Improvement Advisor result.")
    doc = build(project, res, adv)
    doc.save(path)
    return len(doc.pages)
