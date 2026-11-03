"""Right-to-left Hebrew text for Tk on Windows.

Tk 8.6 hands text to Windows in chunks, and Windows reorders each chunk with its own guess of the paragraph
direction, so a Hebrew sentence with Latin terms, numbers or punctuation comes out in the wrong word order.  This
module lays the text out itself: the bidi pass of report_he gives the visual order of every character, Latin / digit
runs are drawn as one canvas item each and Hebrew runs one character at a time, placed from right to left.  Windows
never sees a mixed-direction string.

RtlCanvas draws a list of blocks (headings, paragraphs, bullets, boxes, chips) and re-wraps on resize.
"""
import tkinter as tk
import tkinter.font as tkfont

from .report_he import resolve, visual_order, _MIRROR, is_he


def _segments(line):
    """[(text, rtl)] of one line in visual left-to-right order; rtl segments are single characters."""
    if not any(is_he(c) for c in line):
        return [(line, False)]
    dirs = list(resolve(line, "R"))
    for i in range(1, len(line)):                   # maqaf after a prefix letter: "ה-IFOV", "בכ-80%"
        if line[i] in "-־" and is_he(line[i - 1]):
            dirs[i] = "R"
    segs = []
    for i in visual_order(range(len(line)), dirs, "R"):
        c = line[i]
        if dirs[i] == "R":
            segs.append((_MIRROR.get(c, c), True))
        elif segs and not segs[-1][1]:
            segs[-1] = (segs[-1][0] + c, False)
        else:
            segs.append((c, False))
    return segs


def wrap(text, font, width):
    """Greedy word wrap of a logical string to lines no wider than `width` pixels."""
    lines = []
    text = str(text).replace(" > ", " > ")      # keep menu paths ("Run > Detector lookup") together
    for para in text.split("\n"):
        cur = ""
        for w in para.split(" "):
            cand = w if not cur else cur + " " + w
            if cur and font.measure(cand) > width:
                lines.append(cur)
                cur = w
            else:
                cur = cand
        lines.append(cur)
    return lines


def draw_line(canvas, line, x_right, y, font, fill, tags=()):
    """Draw one logical line right-aligned at x_right (top at y); returns the left edge."""
    segs = _segments(line)
    widths = [font.measure(s) for s, _ in segs]
    x = x_right - sum(widths)
    left = x
    for (s, _rtl), w in zip(segs, widths):
        if s.strip():
            canvas.create_text(x, y, text=s, font=font, fill=fill, anchor="nw", tags=tags)
        x += w
    return left


def line_width(line, font):
    return sum(font.measure(s) for s, _ in _segments(line))


class RtlCanvas(tk.Canvas):
    """Scrollable right-to-left document.  set_blocks([...]) with blocks:

    ("title", text) ("h", text) ("p", text) ("muted", text) ("li", text)
    ("box", style, [lines]) - tinted card, style in BOX_STYLES
    ("chips", [(text, style), ...]) - small rounded labels in one row
    ("gap", pixels)
    """
    BOX_STYLES = {"info": ("#eef4ff", "#1f6feb", "#1d2433"), "warn": ("#fff4e5", "#b54708", "#5a2d05"),
                  "ok": ("#ecfdf3", "#067647", "#05472b"), "tip": ("#f5f3ff", "#6d28d9", "#2e1065"),
                  "plain": ("#f7f9fc", "#d7dde5", "#1d2433")}
    CHIP_STYLES = {"high": ("#fee4e2", "#b42318"), "mid": ("#fef0c7", "#93370d"), "low": ("#e4e7ec", "#344054"),
                   "info": ("#e8f0fe", "#1f6feb"), "ok": ("#dcfae6", "#067647")}

    def __init__(self, master, bg="#ffffff", fg="#1d2433", muted="#6a7383", accent="#1f6feb", scale=1.0, **kw):
        super().__init__(master, background=bg, highlightthickness=0, borderwidth=0, **kw)
        self.bg, self.fg, self.muted, self.accent, self.k = bg, fg, muted, accent, scale
        size = lambda s: -int(round(s * 1.333 * scale))          # points -> pixels, DPI aware
        self.fonts = {"title": tkfont.Font(family="Segoe UI Semibold", size=size(14)),
                      "h": tkfont.Font(family="Segoe UI Semibold", size=size(10.5)),
                      "p": tkfont.Font(family="Segoe UI", size=size(10)),
                      "muted": tkfont.Font(family="Segoe UI", size=size(9)),
                      "chip": tkfont.Font(family="Segoe UI Semibold", size=size(8.5))}
        self.blocks = []
        self.pad = int(16 * scale)
        self.bind("<Configure>", lambda e: self.render())
        self.bind("<Enter>", lambda e: self.bind_all("<MouseWheel>", self._wheel))
        self.bind("<Leave>", lambda e: self.unbind_all("<MouseWheel>"))

    def _wheel(self, e):
        if self.bbox("all") and self.bbox("all")[3] > self.winfo_height():
            self.yview_scroll(int(-e.delta / 120), "units")

    def set_blocks(self, blocks, keep_scroll=False):
        top = self.yview()[0]
        self.blocks = list(blocks)
        self.render()
        self.yview_moveto(top if keep_scroll else 0)

    def _text(self, text, x_right, y, width, font, fill, tags=()):
        lh = font.metrics("linespace")
        for ln in wrap(text, font, width):
            draw_line(self, ln, x_right, y, font, fill, tags=tags)
            y += lh
        return y

    def render(self):
        self.delete("all")
        W = max(self.winfo_width(), 200)
        p, k = self.pad, self.k
        xr, width = W - p, W - 2 * p
        y = p
        for b in self.blocks:
            kind = b[0]
            if kind == "gap":
                y += int(b[1] * k)
            elif kind == "title":
                y = self._text(b[1], xr, y, width, self.fonts["title"], self.fg) + int(4 * k)
            elif kind == "h":
                y += int(8 * k)
                y = self._text(b[1], xr, y, width, self.fonts["h"], self.accent) + int(3 * k)
            elif kind in ("p", "muted"):
                y = self._text(b[1], xr, y, width, self.fonts[kind], self.fg if kind == "p" else self.muted)
                y += int(5 * k)
            elif kind == "li":
                f = self.fonts["p"]
                ind = int(16 * k)
                r = int(2.5 * k)
                cy = y + f.metrics("linespace") // 2
                self.create_oval(xr - 4 * k - r, cy - r, xr - 4 * k + r, cy + r, fill=self.accent, outline="")
                y = self._text(b[1], xr - ind, y, width - ind, f, self.fg) + int(3 * k)
            elif kind == "box":
                fill, edge, ink = self.BOX_STYLES.get(b[1], self.BOX_STYLES["plain"])
                f, ip = self.fonts["p"], int(12 * k)
                top = y
                item = self.create_rectangle(p, top, xr, top, fill=fill, outline="")
                bar = self.create_rectangle(xr - int(4 * k), top, xr, top, fill=edge, outline="")
                y += ip
                for i, ln in enumerate(b[2]):
                    font = self.fonts["h"] if i == 0 and len(b) > 3 and b[3] else f
                    y = self._text(ln, xr - ip - int(4 * k), y, width - 2 * ip - int(4 * k), font,
                                   edge if font is self.fonts["h"] else ink) + int(2 * k)
                y += ip - int(2 * k)
                self.coords(item, p, top, xr, y)
                self.coords(bar, xr - int(4 * k), top, xr, y)
                y += int(10 * k)
            elif kind == "card":                         # ("card", title, text, meta, callback, done)
                _k, title, text, meta, cb = b[:5]
                done = len(b) > 5 and b[5]
                ip, tag = int(14 * k), "card%d" % id(b)
                top = y
                frame = self._round(p, top, xr, top + 10, int(8 * k), "#f7f9fc", tags=(tag,), outline="#d7dde5")
                y += ip
                y = self._text(title, xr - ip, y, width - 2 * ip, self.fonts["h"], self.fg, tags=(tag,))
                y = self._text(text, xr - ip, y + int(2 * k), width - 2 * ip, self.fonts["p"], self.muted,
                               tags=(tag,))
                if meta:
                    f = self.fonts["chip"]
                    draw_line(self, meta, xr - ip, y + int(4 * k), f, "#067647" if done else self.accent, tags=(tag,))
                    y += f.metrics("linespace") + int(4 * k)
                y += ip
                self.delete(frame)
                frame = self._round(p, top, xr, y, int(8 * k), "#f7f9fc", tags=(tag,), outline="#d7dde5")
                self.tag_lower(frame)
                self.tag_bind(tag, "<Enter>", lambda e, fr=frame: (self.itemconfigure(fr, outline=self.accent),
                                                                   self.configure(cursor="hand2")))
                self.tag_bind(tag, "<Leave>", lambda e, fr=frame: (self.itemconfigure(fr, outline="#d7dde5"),
                                                                   self.configure(cursor="")))
                self.tag_bind(tag, "<ButtonRelease-1>", lambda e, cb=cb: cb())
                y += int(10 * k)
            elif kind == "chips":
                f = self.fonts["chip"]
                x, h = xr, f.metrics("linespace") + int(6 * k)
                for text, style in b[1]:
                    bgc, fgc = self.CHIP_STYLES.get(style, self.CHIP_STYLES["low"])
                    w = line_width(text, f) + int(16 * k)
                    if x - w < p:
                        x, y = xr, y + h + int(6 * k)
                    self._round(x - w, y, x, y + h, h // 2, bgc)
                    draw_line(self, text, x - int(8 * k), y + int(3 * k), f, fgc)
                    x -= w + int(6 * k)
                y += h + int(10 * k)
        self.configure(scrollregion=(0, 0, W, y + p))

    def _round(self, x0, y0, x1, y1, r, fill, tags=(), outline=""):
        r = min(r, (x1 - x0) // 2, (y1 - y0) // 2)
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1, x0, y1,
               x0, y1 - r, x0, y0 + r, x0, y0]
        return self.create_polygon(pts, smooth=True, fill=fill, outline=outline, tags=tags)


class RtlButton(tk.Canvas):
    """Flat button with a right-to-left Hebrew label."""

    def __init__(self, master, text, command, accent=False, scale=1.0, bg="#ffffff"):
        self.font = tkfont.Font(family="Segoe UI Semibold", size=-int(round(10 * 1.333 * scale)))
        self.text, self.command, self.k = text, command, scale
        self.colors = (("#1f6feb", "#1859c4", "white") if accent else ("#eef1f5", "#dde3ea", "#1d2433"))
        w = line_width(text, self.font) + int(28 * scale)
        h = self.font.metrics("linespace") + int(12 * scale)
        super().__init__(master, width=w, height=h, background=bg, highlightthickness=0, borderwidth=0,
                         cursor="hand2")
        self.enabled = True
        self._paint(self.colors[0])
        self.bind("<Enter>", lambda e: self.enabled and self._paint(self.colors[1]))
        self.bind("<Leave>", lambda e: self._paint(self.colors[0]))
        self.bind("<ButtonRelease-1>", lambda e: self.enabled and self.command())

    def _paint(self, fill):
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        r = int(6 * self.k)
        pts = [r, 0, w - r, 0, w, 0, w, r, w, h - r, w, h, w - r, h, r, h, 0, h, 0, h - r, 0, r, 0, 0]
        self.create_polygon(pts, smooth=True, fill=fill if self.enabled else "#e4e7ec", outline="")
        ink = self.colors[2] if self.enabled else "#98a2b3"
        draw_line(self, self.text, w - int(14 * self.k), int(6 * self.k), self.font, ink)

    def set_enabled(self, on):
        self.enabled = bool(on)
        self._paint(self.colors[0])
