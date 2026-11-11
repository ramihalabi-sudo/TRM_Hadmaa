"""The guide points at the part of the screen it talks about: a blinking frame drawn over the window.

A lesson step lists what it shows with "show": [(keywords, targets), ...].  When the narration reaches the first
sentence that contains one of the keywords (a whole word, case as written; the Hebrew and the English text both),
the targets are framed while that sentence is said (guide_voice.step_script inserts the action into the script).

Targets (strings):
    wf, wf:<quick|engineering|lab>      the WORKFLOW selector of the sidebar, or one of its buttons
    pages                               the page list of the sidebar (PARAMETERS)
    advanced                            "Show advanced parameters"
    derived                             the read-only calculated values at the bottom of the open page
    badge:<path>                        the data-source tag of a field
    field:<path>                        a field of the form (its label is highlighted, as a lesson step does)
    tool:<text>                         a toolbar button (New, Open, Save, Report, Calculate, Guide...)
    tabs, tab:<name>                    the result tabs, or one of them (it is opened)
    sens:<mode>                         a mode of the Sensitivity tab (opened and shown: advisor, limiting...)
    sensbtn:<text>                      a button of the Sensitivity tab (Run analysis, Hebrew PDF report...)
    guide:<play|walk>                   the play button / "Explain page" of the narrator strip
    gbtn:<text>                         a button at the foot of the guide panel ("חשב עכשיו")
"""
import re
import tkinter as tk
from tkinter import ttk

COLOR = "#ff7a1a"
DIM = "#ffc59a"
THICK = 3
PAD = 3
BLINKS = 7
BLINK_MS = 230


def keyword_re(words):
    """One regex for a tuple of keywords: a whole word (letters of any script), case as written; a Hebrew word may
    carry its one-letter prefixes (ו, ה, ב, ל, מ, ש, כ: "ועקומת הטווח")."""
    alts = "|".join(re.escape(w) for w in words)
    return re.compile(r"(?<![\w])[ובלמהשכ]{0,2}(?:%s)(?![\w])" % alts)


def _walk(w):
    yield w
    for c in w.winfo_children():
        yield from _walk(c)


def _mapped(w):
    try:
        return bool(w.winfo_ismapped()) and w.winfo_width() > 1
    except tk.TclError:
        return False


def _box(w):
    """(x0, y0, x1, y1) of a widget, in root coordinates."""
    x, y = w.winfo_rootx(), w.winfo_rooty()
    return x, y, x + w.winfo_width(), y + w.winfo_height()


def _tab_box(nb, index=None):
    """Root box of the header of a notebook tab (index), or of all its tabs (None)."""
    nb.update_idletasks()
    xs, top, bottom = {}, None, None
    for y in range(2, 40, 2):
        found = False
        for x in range(0, nb.winfo_width(), 2):
            try:
                i = nb.index("@%d,%d" % (x, y))
            except tk.TclError:
                continue
            if index is not None and i != index:
                continue
            found = True
            lo, hi = xs.get(i, (x, x))
            xs[i] = (min(lo, x), max(hi, x))
        if found:
            top = y if top is None else top
            bottom = y
        elif top is not None:
            break
    if not xs or top is None:
        return None
    lo = min(v[0] for v in xs.values())
    hi = max(v[1] for v in xs.values())
    rx, ry = nb.winfo_rootx(), nb.winfo_rooty()
    return rx + lo - 2, ry + max(0, top - 4), rx + hi + 3, ry + bottom + 4


class Pointer:
    """Frames over the main window around the parts the guide talks about."""

    def __init__(self, app, panel):
        self.app, self.panel = app, panel
        self._frames = []
        self._job = None

    # ---- finding the parts
    def _find_text(self, root, cls, text):
        for w in _walk(root):
            if isinstance(w, cls) and _mapped(w):
                try:
                    if str(w.cget("text")).strip() == text:
                        return w
                except tk.TclError:
                    pass
        return None

    def boxes(self, target):
        """Root boxes of a target (opening the tab or mode it is in); [] when it is not on the screen."""
        app, p = self.app, self.panel
        kind, _, arg = target.partition(":")
        w = None
        try:
            if kind == "wf":
                w = app.wf_buttons.get(arg) if arg else next(iter(app.wf_buttons.values())).master
            elif kind == "pages":
                w = app.side_list
            elif kind == "advanced":
                w = app.adv_check
            elif kind == "derived":
                # only Quick setup and Camera profile carry the panel: go to the one of the workflow when needed
                for name in (app.current_page, "Quick setup" if app.workflow == "quick" else "Camera profile"):
                    if name != app.current_page:
                        app.goto_page(name)
                        app.update_idletasks()
                    page = app.pages.get(app.current_page)
                    inner = page.inner if page is not None else None
                    for dp in getattr(app, "derived_panels", []):
                        if inner is not None and str(dp).startswith(str(inner) + ".") and _mapped(dp):
                            w = dp
                            page.canvas.yview_moveto(1.0)
                            app.update_idletasks()
                            break
                    if w is not None:
                        break
            elif kind == "badge":
                w = next((b for b in app.badges.get(arg, []) if _mapped(b)), None)
            elif kind == "field":
                return [] if not p._hilite(p._page_of(arg) or app.current_page, arg) else [_box(p.hilited)]
            elif kind == "tool":
                for c in _walk(app):
                    lab = getattr(c, "label", None)
                    if getattr(c, "parts", None) is not None and lab is not None and lab.cget("text") == arg:
                        w = c
                        break
            elif kind == "tabs":
                b = _tab_box(app.right)
                return [b] if b else []
            elif kind == "tab":
                tab = app.result_tabs.get(arg)
                if tab is None:
                    return []
                app.right.select(tab)
                b = _tab_box(app.right, app.right.index(tab))
                return [b] if b else []
            elif kind == "sens":
                app.right.select(app.sens)
                app.sens.mode.set(arg)
                app.sens.show_mode(arg)
                app.update_idletasks()
                # a narrow window cuts the row of modes: then the tab itself, showing that mode, is framed
                w = self._find_text(app.sens, ttk.Radiobutton, app.sens.MODE_NAME.get(arg, arg)) or app.sens
            elif kind == "sensbtn":
                app.right.select(app.sens)
                app.update_idletasks()
                w = self._find_text(app.sens, ttk.Button, arg) or app.sens
            elif kind == "guide":
                bar = p.bar
                items = bar.find_withtag(arg)
                if arg == "play":                          # the ▶ button, not the avatar that shares its tag
                    items = [i for i in items if bar.bbox(i)[2] <= getattr(bar, "controls_right", 1e9)]
                b = bar.bbox(*items) if items else None
                if b:
                    rx, ry = bar.winfo_rootx(), bar.winfo_rooty()
                    return [(rx + b[0], ry + b[1], rx + b[2], ry + b[3])]
                return []
            elif kind == "gbtn":
                w = next((c for c in p.foot.winfo_children() if getattr(c, "text", None) == arg), None)
        except (tk.TclError, StopIteration, AttributeError):
            return []
        if w is None:
            return []
        app.update_idletasks()
        return [_box(w)] if _mapped(w) else []

    # ---- drawing
    def show(self, targets):
        """Frame every target that is on the screen; returns how many were framed."""
        self.clear()
        boxes = []
        for t in targets:
            boxes += self.boxes(t)
        top = self.app
        ox, oy = top.winfo_rootx(), top.winfo_rooty()
        for x0, y0, x1, y1 in boxes:
            x0, y0, x1, y1 = x0 - ox - PAD, y0 - oy - PAD, x1 - ox + PAD, y1 - oy + PAD
            for (x, y, w, h) in ((x0, y0, x1 - x0, THICK), (x0, y1 - THICK, x1 - x0, THICK),
                                 (x0, y0, THICK, y1 - y0), (x1 - THICK, y0, THICK, y1 - y0)):
                f = tk.Frame(top, bg=COLOR, highlightthickness=0, bd=0)
                f.place(x=x, y=y, width=max(w, 1), height=max(h, 1))
                f.lift()
                self._frames.append(f)
        if self._frames:
            self._blink(BLINKS)
        return len(boxes)

    def _blink(self, n):
        self._job = None
        if not self._frames:
            return
        try:
            for f in self._frames:
                f.configure(bg=COLOR if n % 2 else DIM)
        except tk.TclError:
            return
        if n > 0:
            self._job = self.app.after(BLINK_MS, lambda: self._blink(n - 1))

    def clear(self):
        if self._job:
            try:
                self.app.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        for f in self._frames:
            try:
                f.destroy()
            except tk.TclError:
                pass
        self._frames = []

    @property
    def shown(self):
        return len(self._frames) // 4
