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
import copy
import re
import sys
import tkinter as tk
from tkinter import ttk

from . import presets as P

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


# The closing sentence of a step ("that's it, you have finished..."): everything shown is removed.
END_WORDS = ("וזהו", "זהו", "סיימתם", "That's it", "You have finished", "You are done", "You're done")

# The opening screen of the guide: what its lesson previews name.
HOME_SHOW = [(("סימן השאלה", "question mark"), "help:"), (("Calculate", "F5"), "tool:Calculate"),
             ("Summary", "tab:Summary"), (("בין עברית לאנגלית", "Hebrew and English"), ["guide:lang", "guide:rate", "guide:auto"])]

# Parts of the screen named inside the field cards (any field): framed when the card's sentence says them.
CARD_SHOW = [("Detector lookup", ["menu:Run>Detector lookup...", "tool:Detector lookup"]), ("System data", "tab:System data"),
             ("Credit sharpening", "field:dsp.credit_boost"), ("Messages", "tab:Messages")]

_GENERIC = {"None", "Other", "Custom", "Yes", "No", "On", "Off", "User", "Default"}


def option_show(app, path):
    """For a field with a list: the options its card names ("תבחרו Measured"), each opening the list at that
    option while its sentence is said.  An option is named by its whole label or by its first word."""
    out = []
    for _f, _var, w in app.vars.get(path, []):
        if not isinstance(w, ttk.Combobox):
            continue
        for label in [str(v) for v in w.cget("values")]:
            first = re.split(r"[\s(:/,-]+", label.strip())[0]
            words = {label}
            if len(first) >= 3 and first not in _GENERIC and re.match(r"[A-Za-z0-9]", first):
                words.add(first)
            out.append((tuple(sorted(words, key=len, reverse=True)), "pick:%s=%s" % (path, label)))
        break
    return out


def card_show(app, path):
    """Everything a field card can demonstrate: its own options, and the parts of the screen it names."""
    return option_show(app, path) + [s for s in CARD_SHOW if s[1] != "field:" + path]


class MenuWalk:
    """Open a real menu of the window's menu bar, the way a person does (Windows): the menu drops down, the
    highlight walks down to the item, a sub-menu opens and the highlight walks on.  The keys are pressed only while
    this window's own menu is open (GetGUIThreadInfo), never Enter: when the step asks for it, the guide closes
    the menu and does the item itself (`run`).  The narration keeps running while the menu is open (Tk serves its
    timers in the Windows menu loop)."""

    STEP_MS = 330
    _gen = 0                    # a new menu walk: the close checks of the one before stop
    HOLD_MS = 1300              # on the item before the guide chooses it


    def __init__(self, app, path, run=None):
        self.app, self.path, self.run = app, path, run
        self._jobs = []
        self.walked = False         # the highlight has reached the item
        self.ok = sys.platform == "win32"

    # ---- Windows
    @staticmethod
    def _u32():
        import ctypes
        return ctypes.windll.user32

    def _hwnd(self):
        return int(self.app.wm_frame(), 16)

    def in_menu(self):
        if not self.ok:
            return False
        import ctypes
        from ctypes import wintypes

        class GUITHREADINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hwndActive", wintypes.HWND),
                        ("hwndFocus", wintypes.HWND), ("hwndCapture", wintypes.HWND),
                        ("hwndMenuOwner", wintypes.HWND), ("hwndMoveSize", wintypes.HWND),
                        ("hwndCaret", wintypes.HWND), ("rcCaret", wintypes.RECT)]
        u = self._u32()
        tid = u.GetWindowThreadProcessId(self._hwnd(), None)
        gi = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
        if not u.GetGUIThreadInfo(tid, ctypes.byref(gi)):
            return False
        return bool(gi.flags & 0x4) and gi.hwndMenuOwner == self._hwnd()      # GUI_INMENUMODE, our window

    def _key(self, vk):
        if not self.in_menu():                      # the menu is gone (or never ours): press nothing
            self.cancel()
            return
        u = self._u32()
        u.keybd_event(vk, 0, 0, 0)
        u.keybd_event(vk, 0, 2, 0)

    # ---- the walk
    def keys(self):
        """[(vk)] that walk from the first item of the dropped-down menu to the last item of the path."""
        bar = self.app.nametowidget(self.app["menu"])
        menu, keys = bar, []
        for depth, label in enumerate(self.path):
            idx = self._index(menu, label)
            if idx is None:
                return None
            if depth == 0:
                menu = self.app.nametowidget(menu.entrycget(idx, "menu"))
                continue
            steps = sum(1 for i in range(idx) if menu.type(i) != "separator")
            keys += [0x28] * steps                                  # down
            if depth < len(self.path) - 1:
                keys.append(0x27)                                   # right: open the sub-menu
                menu = self.app.nametowidget(menu.entrycget(idx, "menu"))
        self.menu, self.index = menu, idx
        return keys

    @staticmethod
    def _index(menu, label):
        end = menu.index("end")
        for i in range(0 if end is None else end + 1):
            if menu.type(i) in ("command", "cascade", "checkbutton", "radiobutton") and \
                    str(menu.entrycget(i, "label")) == label:
                return i
        return None

    def start(self):
        keys = self.keys()
        if not self.ok or keys is None:
            return False
        MenuWalk._gen += 1
        u = self._u32()
        u.SetForegroundWindow(self._hwnd())
        u.PostMessageW(self._hwnd(), 0x0112, 0xF100, ord(self.path[0][0].lower()))   # WM_SYSCOMMAND, SC_KEYMENU
        t = 350
        for vk in keys:
            t += self.STEP_MS
            self._jobs.append(self.app.after(t, lambda vk=vk: self._key(vk)))
        self._jobs.append(self.app.after(t + 60, self._reached))
        if self.run is not None:
            self._jobs.append(self.app.after(t + self.HOLD_MS, self._choose))
        # a menu that is only shown stays open while it is being explained: the next part of the screen, the
        # closing sentence or the end of the narration closes it
        return True

    def move_to(self, label, delay=0):
        """Walk the highlight, in the open menu, to another item of it (the explanation moved on to it)."""
        def go():
            if not self.walked:                     # still walking to the first item: after it
                self._jobs.append(self.app.after(150, go))
                return
            idx = self._index(self.menu, label)
            if idx is None or not self.in_menu():
                return
            lo, hi = sorted((self.index, idx))
            steps = sum(1 for i in range(lo, hi) if self.menu.type(i) != "separator")
            vk = 0x28 if idx > self.index else 0x26                     # down / up
            self.index = idx
            for k in range(steps):
                self._jobs.append(self.app.after(k * self.STEP_MS, lambda: self._key(vk)))
        self._jobs.append(self.app.after(delay, go))

    def _reached(self):
        self.walked = True

    def _choose(self):
        run, self.run = self.run, None
        self.close()
        if run is not None:
            try:
                run()
            except Exception:                       # a demonstration never breaks the guide
                pass

    def finish(self):
        """The next sentence: close the menu, and when the item was to be chosen and is not yet, choose it now."""
        if self.run is not None:
            self._choose()
        else:
            self.close()

    def cancel(self):
        for j in self._jobs:
            try:
                self.app.after_cancel(j)
            except tk.TclError:
                pass
        self._jobs = []

    def close(self):
        self.cancel()
        if self.ok:
            u = self._u32()
            u.EndMenu()                             # closes only this thread's menus
            if self.in_menu():                      # not always enough: cancel the menu mode of our window too
                u.PostMessageW(self._hwnd(), 0x001F, 0, 0)          # WM_CANCELMODE
            gen = MenuWalk._gen
            self.app.after(150, lambda: self._make_sure_closed(4, gen))

    def _make_sure_closed(self, n, gen):
        """Still open (it happens): Escape, only while the open menu is our window's, until it is gone - and never
        once the next menu has been opened."""
        if n <= 0 or gen != MenuWalk._gen or not self.in_menu():
            return
        u = self._u32()
        u.keybd_event(0x1B, 0, 0, 0)
        u.keybd_event(0x1B, 0, 2, 0)
        u.EndMenu()
        self.app.after(150, lambda: self._make_sure_closed(n - 1, gen))


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
        self._acted = 0            # demonstrations with nothing to frame (an open menu)
        self.menu = None           # the menu walk still open (menuitem moves inside it)
        self._undo = []            # what a demonstration opened, closed before the next one (a tip, a list, a card)
        self._keep = {}            # what a demonstration changed for the whole step (workflow, advanced), restored
        #                            when the step ends

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

    # ---- demonstrations: the guide does what it explains, and undoes it
    def _row_widgets(self, path):
        p = self.panel
        page = p._page_of(path) or self.app.current_page
        if page and page != self.app.current_page:
            self.app.goto_page(page)
        if not p._hilite(page, path):
            return None
        return p._row(page, path)

    def _combo(self, path):
        for _f, _var, w in self.app.vars.get(path, []):
            if isinstance(w, ttk.Combobox) and _mapped(w):
                return w
        return None

    def _demo(self, kind, arg):
        """Perform a demonstration; returns the widget to frame (or None)."""
        app, p = self.app, self.panel
        if kind == "help":                                  # press the "?" of a field: its explanation opens
            if not arg:                                     # no field named: the first one of the open page
                inner = getattr(app.pages.get(app.current_page), "inner", None)
                arg = next((f["path"] for f, ws, _v, _g in app.rows if f.get("path") and ws and inner is not None
                            and str(ws[0]).startswith(str(inner) + ".") and _mapped(ws[0])
                            and any(isinstance(w, tk.Label) and str(w.cget("text")) == "?" for w in ws)), None)
                if arg is None:
                    return None
            row = self._row_widgets(arg) or []
            q = next((w for w in row if isinstance(w, tk.Label) and str(w.cget("text")) == "?"), None)
            if q is None:
                return None
            app.update_idletasks()
            q.event_generate("<ButtonPress-1>")
            self._undo.append(lambda: q.event_generate("<Leave>"))
            return q
        if kind == "card":                                  # click a field: its card opens in the guide
            row = self._row_widgets(arg)
            if not row:
                return None
            back = p.index
            p._quiet = True
            try:
                p.show_field(arg)
            finally:
                p._quiet = False

            def undo():
                if p.mode == "field" and p.field_path == arg and p.lesson_id:
                    p._quiet = True
                    try:
                        p.show_step(back)
                    finally:
                        p._quiet = False
            self._undo.append(undo)
            return row[0]
        if kind == "pick":                                  # open the list of a field and point at an option
            path, _, label = arg.partition("=")
            self._row_widgets(path)
            w = self._combo(path)
            if w is None:
                return None
            values = [str(v) for v in w.cget("values")]
            i = next((k for k, v in enumerate(values) if v == label), None)
            if i is None:
                return w
            try:
                self.panel._own_focus = path                # the guide's move, not the user choosing a field
                w.focus_set()
                w.tk.call("ttk::combobox::Post", w)
                lb = "%s.f.l" % w.tk.call("ttk::combobox::PopdownWindow", w)
                w.tk.call(lb, "selection", "clear", 0, "end")
                w.tk.call(lb, "selection", "set", i)
                w.tk.call(lb, "activate", i)
                w.tk.call(lb, "see", i)
            except tk.TclError:
                return w
            self._undo.append(lambda: w.tk.call("ttk::combobox::Unpost", w))
            return w
        if kind == "workflow":                              # switch the working mode (back at the end of the step)
            if arg not in app.wf_buttons:
                return None
            if "workflow" not in self._keep:
                orig, page = app.workflow, app.current_page
                self._keep["workflow"] = lambda: (app.set_workflow(orig), app.goto_page(page))
            app.set_workflow(arg)
            app.update_idletasks()
            return app.wf_buttons[arg]
        if kind == "page":                                  # open a page of the form (back at the end of the step)
            if "page" not in self._keep:
                orig = app.current_page
                self._keep["page"] = lambda: app.goto_page(orig)
            app.goto_page(arg)
            app.update_idletasks()
            return app.side_items.get(arg)
        if kind == "show_advanced":                         # tick "Show advanced parameters" (back at the end)
            if not app.show_adv.get() and "advanced" not in self._keep:
                app.show_adv.set(True)
                app._toggle_adv()
                self._keep["advanced"] = lambda: (app.show_adv.set(False), app._toggle_adv())
            app.update_idletasks()
            return app.adv_check
        if kind in ("menu", "menudo"):                     # open a real menu and walk to the item (menudo: do it)
            path = arg.split(">")
            run = self._menu_action(path) if kind == "menudo" else None
            walk = MenuWalk(app, path, run)
            if not walk.start():
                return None
            self.menu = walk
            self._undo.append(walk.finish)
            self._acted += 1
            return None
        if kind == "badgemenu":                             # click a source tag: its menu of sources opens
            b = next((x for x in app.badges.get(arg, []) if _mapped(x)), None)
            if b is None:
                return None
            # the menu runs its own loop (Windows): open it after this action returns, close it at the next sentence
            app.after(60, lambda: app._source_menu(arg, b))
            self._undo.append(lambda: MenuWalk(app, []).close())
            return b
        if kind == "profile":                               # the camera-profile bar at the top of the page
            return next((pb for pb in getattr(app, "profile_bars", []) if _mapped(pb)), None)
        if kind == "calculate":                             # run the model, as the Calculate button does
            btn = getattr(app, "calc_btn", None) or self._tool("Calculate")   # its label changes while it runs
            app.calculate()
            return btn
        return None

    def _menu_action(self, path):
        """What choosing a menu item does, done by the guide: a template is loaded without the "save changes?"
        question, and the project the user had comes back when the step ends; other items run as the menu runs
        them."""
        app = self.app
        if path[:2] == ["File", "New from template"] and len(path) == 3:
            def load():
                if "project" not in self._keep:
                    snap = copy.deepcopy(app.collect())
                    fp, saved = app.file_path, app.saved_state

                    def back():
                        app._load_into_form(snap, saved=False)
                        app.file_path, app.saved_state = fp, saved
                        app._set_dirty(app._state_of(app.project) != saved)
                        app._clear_results()
                    self._keep["project"] = back
                app.file_path = None
                app._load_into_form(P.make_template(path[2]))
                app._clear_results()
                app.status.set("New project from template: %s  (guide demonstration - your project comes back)"
                               % path[2])
            return load
        walk = MenuWalk(app, path)
        if walk.keys() is None:
            return None

        def do():
            if "project" not in self._keep:          # an analysis mode may store its defaults in the project
                snap, saved = copy.deepcopy(app.project), app.saved_state

                def back():
                    if app._state_of(app.project) != app._state_of(snap):
                        app._load_into_form(snap, saved=False)
                        app.saved_state = saved
                        app._set_dirty(app._state_of(app.project) != saved)
                self._keep["project"] = back
            walk.menu.invoke(walk.index)
        return do

    def _tool(self, text):
        for c in _walk(self.app):
            lab = getattr(c, "label", None)
            if getattr(c, "parts", None) is not None and lab is not None and lab.cget("text") == text:
                return c
        return None

    DEMOS = ("help", "card", "pick", "page", "workflow", "show_advanced", "calculate", "menu", "menudo",
             "badgemenu", "profile")

    def boxes(self, target):
        """Root boxes of a target (opening the tab or mode it is in); [] when it is not on the screen."""
        app, p = self.app, self.panel
        kind, _, arg = target.partition(":")
        w = None
        try:
            if kind in self.DEMOS:
                w = self._demo(kind, arg)
            elif kind == "wf":
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
                w = self._tool(arg)
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
        """Frame every target that is on the screen; returns how many were framed.  What the last demonstration
        opened stays until this one: `menuitem:<label>` moves the highlight inside the menu that is still open
        (several, one after the other); `clear` only removes everything (the closing sentence of a step)."""
        items = [t for t in targets if t.startswith("menuitem:")]
        if items and len(items) == len(targets):
            if self.menu is None or not self.menu.in_menu():
                return 0
            for k, t in enumerate(items):
                self.menu.move_to(t.partition(":")[2], delay=k * 1600)
            return len(items)
        self.clear()
        self._acted = 0
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
        return len(boxes) + self._acted

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

    def _run(self, fns):
        for fn in fns:
            try:
                fn()
            except (tk.TclError, AttributeError):
                pass

    def reset(self):
        """The step ends: clear the frames and put back everything the demonstrations changed."""
        self.clear()
        keep, self._keep = list(self._keep.values()), {}
        self._run(reversed(keep))

    def clear(self):
        self.menu = None
        undo, self._undo = self._undo, []
        self._run(reversed(undo))
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
