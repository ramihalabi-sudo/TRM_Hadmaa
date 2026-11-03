"""Interactive Hebrew guide panel of the GUI (optional: Help > Interactive guide, toolbar "Guide", Ctrl+G).

The panel docks at the right of the main window.  It has four views:
  home   - the lessons (guide_he.LESSONS) as cards, with progress, and the review of all values
  step   - one step of a lesson: it switches workflow / page / result tab, highlights the parameter in the form
           and shows its field card with a live check of the entered value; a step of the full tour lists the
           fields of one group of the form instead
  field  - the card of any parameter the user clicks while the guide is open
  review - every shown field of the project checked at once, the warnings sorted by their impact on the range
A field card also shows the live effect of the value on the DRI ranges and the image-quality values
(guide_impact: model runs in a worker thread) and, when the check suggests a value, applies / undoes it.
The text is drawn by rtl_tk (Tk on Windows does not lay out right-to-left paragraphs).
"""
import json
import tkinter as tk
from tkinter import ttk

from . import guide_he as G
from . import guide_impact as GI
from .rtl_tk import RtlCanvas, RtlButton, draw_line

HEAD_BG = "#16202f"
HEAD_FG = "#ffffff"
HEAD_MUTED = "#9fb0c8"
ACCENT = "#1f6feb"
TRACK = "#2a3a52"
SURFACE = "#ffffff"
BORDER = "#d7dde5"
HILITE = "#fff1c2"


def _get(d, path):
    for k in path.split("."):
        d = d[int(k)] if isinstance(d, list) else d[k]
    return d


class GuidePanel(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        self.app, self.k = app, app.k
        st = app.settings.setdefault("guide", {})
        self.done = set(st.get("done", []))
        self.lesson_id = st.get("lesson")
        self.index = int(st.get("step", 0))
        self.mode = "home"
        self.field_path = None
        self.back = None                                # view the field card returns to ("review")
        self.hilited = None
        self._flash_job = None
        self.impact = GI.ImpactWorker(self)
        self._imp_key = None                            # (path, project state) of the shown impact result
        self._imp_res = None
        self._undo = None                               # (path, previous value) after "apply the suggested value"
        self._review_ranges = None
        self._typing_job = None
        self._live = None                               # project with the value being typed (before refresh)

        self.head = tk.Canvas(self, height=int(78 * self.k), bg=HEAD_BG, highlightthickness=0)
        self.head.pack(fill="x")
        self.head.bind("<Configure>", lambda e: self._draw_head())
        body = tk.Frame(self, bg=SURFACE)
        body.pack(fill="both", expand=True)
        self.doc = RtlCanvas(body, scale=self.k)
        sb = ttk.Scrollbar(body, orient="vertical", command=self.doc.yview)
        self.doc.configure(yscrollcommand=sb.set)
        sb.pack(side="left", fill="y")
        self.doc.pack(side="left", fill="both", expand=True)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        self.foot = tk.Frame(self, bg=SURFACE)
        self.foot.pack(fill="x", padx=int(10 * self.k), pady=int(10 * self.k))

        self.head.bind("<ButtonRelease-1>", self._head_click)
        self.show_home() if not self.lesson_id or not G.lesson(self.lesson_id) else self.show_step(self.index)

    # ------------------------------------------------------------------ state
    def _save(self):
        self.app.settings["guide"] = {"lesson": self.lesson_id, "step": self.index, "done": sorted(self.done)}

    def _pages(self):
        """[(page, fields, workflow)] of the form for the tour and the review."""
        from . import gui as GUI                      # loaded already: the panel lives in its window
        eng = GUI.WORKFLOWS["engineering"][1]
        pages = [(n, fl, "engineering") for n, fl in GUI.ALL_PAGES if n in eng and n != "Camera profile"]
        return pages + [(n, fl, "lab") for n, fl in GUI.ALL_PAGES if n == "Validation data"]

    def _steps(self):
        if not self.lesson_id:
            return []
        return G.steps(self.lesson_id, self.app.project, self._pages(), self.app._row_visible)

    def _n_steps(self, lesson_id):
        return len(G.steps(lesson_id, self.app.project, self._pages(), self.app._row_visible))

    def _field_spec(self, path):
        for f, _w, _v, _g in self.app.rows:
            if f.get("path") == path:
                return f
        return None

    # ------------------------------------------------------------------ header
    def _draw_head(self):
        c, k = self.head, self.k
        c.delete("all")
        W = c.winfo_width()
        f_title = self.doc.fonts["title"]
        f_sub = self.doc.fonts["muted"]
        pad = int(16 * k)
        draw_line(c, "מדריך אינטראקטיבי", W - pad, int(12 * k), f_title, HEAD_FG)
        if self.mode == "step" and self.lesson_id:
            les, steps = G.lesson(self.lesson_id), self._steps()
            n = max(len(steps), 1)
            sub = "%s · שלב %d מתוך %d" % (les["title"], min(self.index + 1, n), n)
            frac = (self.index + 1) / n
        elif self.mode == "field":
            sub, frac = "כרטיס שדה", None
        elif self.mode == "review":
            sub, frac = "בדיקת כל הערכים", None
        else:
            sub = "%d מתוך %d שיעורים הושלמו" % (len(self.done & {l["id"] for l in G.LESSONS}), len(G.LESSONS))
            frac = len(self.done) / len(G.LESSONS)
        draw_line(c, sub, W - pad, int(44 * k), f_sub, HEAD_MUTED)
        # close button (left) and progress track (bottom)
        x0 = pad
        c.create_text(x0, int(24 * k), text="✕", fill=HEAD_MUTED, font=("Segoe UI", 12), anchor="w",
                      tags=("close",))
        c.tag_bind("close", "<Enter>", lambda e: c.itemconfigure("close", fill=HEAD_FG))
        c.tag_bind("close", "<Leave>", lambda e: c.itemconfigure("close", fill=HEAD_MUTED))
        if frac is not None:
            y = int(70 * k)
            h = max(3, int(4 * k))
            c.create_rectangle(pad, y, W - pad, y + h, fill=TRACK, outline="")
            w = (W - 2 * pad) * max(0.0, min(frac, 1.0))
            c.create_rectangle(W - pad - w, y, W - pad, y + h, fill="#4c8dff", outline="")

    def _head_click(self, e):
        items = self.head.find_overlapping(e.x - 2, e.y - 2, e.x + 2, e.y + 2)
        if any("close" in self.head.gettags(i) for i in items):
            self.app.toggle_guide(False)

    # ------------------------------------------------------------------ footer
    def _buttons(self, spec):
        """spec: [(text, command, accent)] right to left."""
        for w in self.foot.winfo_children():
            w.destroy()
        for text, cmd, accent in spec:
            RtlButton(self.foot, text, cmd, accent=accent, scale=self.k).pack(side="right", padx=(int(6 * self.k), 0))

    # ------------------------------------------------------------------ views
    def show_home(self):
        self.mode = "home"
        self.back = None
        self._unhilite()
        self.impact.cancel()
        blocks = [("p", "בחרו שיעור. כל שיעור מוביל אתכם על המסכים האמיתיים, מסמן את השדה ובודק את "
                        "הערך שהזנתם."),
                  ("gap", 4),
                  ("card", "בדיקת כל הערכים שלי", "כל השדות שהפרויקט שלכם מציג נבדקים בבת אחת. ההערות מסודרות לפי "
                   "ההשפעה על הטווח, עם הסבר למה הערך חשוד ומה לעשות.", "בדיקה מיידית", self.show_review, False)]
        for les in G.LESSONS:
            done = les["id"] in self.done
            meta = ("✓ הושלם" if done else "%d דקות · %d שלבים" % (les["minutes"], self._n_steps(les["id"])))
            blocks.append(("card", les["title"], les["summary"], meta, lambda i=les["id"]: self.start(i), done))
        blocks += [("h", "כרטיסי שדה"),
                   ("p", "כשהמדריך פתוח, לחיצה על שדה בטופס מציגה כאן הסבר עליו: מה הוא, כמה הוא משפיע על "
                         "הטווח, ערכים טיפוסיים, בדיקה של הערך שלכם וחישוב חי של ההשפעה שלו על טווחי התצפית."),
                   ("muted", "פותחים וסוגרים את המדריך: Help > Interactive guide, הכפתור Guide או Ctrl+G.")]
        self.doc.set_blocks(blocks)
        self._buttons([("סגור את המדריך", lambda: self.app.toggle_guide(False), False)])
        self._draw_head()

    def start(self, lesson_id):
        self.lesson_id = lesson_id
        self.show_step(0)

    def show_step(self, i):
        steps = self._steps()
        if not steps:
            return self.show_home()
        self.mode = "step"
        self.field_path = None
        self.back = None
        self.index = max(0, min(i, len(steps) - 1))
        st = steps[self.index]
        self._save()
        app = self.app
        if st.get("workflow") and st["workflow"] != app.workflow:
            app.set_workflow(st["workflow"])
        if st.get("page"):
            app.goto_page(st["page"])
        if st.get("tab") and st["tab"] in app.result_tabs:
            try:
                app.right.select(app.result_tabs[st["tab"]])
            except tk.TclError:
                pass
        self._unhilite()
        hidden = False
        if st.get("path"):
            hidden = not self._hilite(st.get("page"), st["path"])
        self.step_hidden = hidden
        self._render_step(st, hidden)
        self._step_buttons()
        self._draw_head()

    def _step_buttons(self):
        steps = self._steps()
        if not steps:
            return
        st = steps[min(self.index, len(steps) - 1)]
        last = self.index == len(steps) - 1
        spec = [("סיום" if last else "הבא", self.finish if last else lambda: self.show_step(self.index + 1), True)]
        if self.index > 0:
            spec.append(("הקודם", lambda: self.show_step(self.index - 1), False))
        spec += self._value_buttons(st.get("path") if st.get("path") and not st.get("group") else None)
        if st.get("action") == "calculate":
            spec.append(("חשב עכשיו", self.app.calculate, False))
        elif st.get("path") and not getattr(self, "step_hidden", False):
            spec.append(("הצג את השדה", lambda: self._hilite(st.get("page"), st["path"]), False))
        spec.append(("שיעורים", self.show_home, False))
        self._buttons(spec)

    def _render_step(self, st, hidden=False, keep_scroll=False):
        blocks = [("title", st["title"])] + list(st.get("blocks", []))
        path = st.get("path")
        if st.get("review"):
            blocks += self._review_blocks()
        elif st.get("fields"):
            blocks += self._field_list(st["fields"])
        elif path:
            e = G.param(path)
            if e and not st.get("blocks"):
                blocks[0] = ("title", e["title"])
            if hidden:
                blocks.append(("box", "plain", ["השדה לא מוצג כרגע בטופס - הוא לא רלוונטי לבחירות הנוכחיות "
                                                "(קטגוריה, מצב או פרמטרים מתקדמים)."]))
            blocks += self._card(path)
        self.doc.set_blocks(blocks, keep_scroll=keep_scroll)

    def finish(self):
        self.done.add(self.lesson_id)
        self.lesson_id, self.index = None, 0
        self._save()
        self.app.settings["guide"]["done"] = sorted(self.done)
        self.show_home()

    def show_field(self, path, back=None):
        if not G.param(path):
            return
        self.mode = "field"
        self.field_path = path
        if back is not None:
            self.back = back
        self._render_field()
        self._field_buttons()
        self._draw_head()

    def _field_buttons(self):
        spec = []
        if self.back == "review":
            spec.append(("חזרה לבדיקה", self.show_review, True))
        if self.lesson_id:
            spec.append(("חזרה לשיעור", lambda: self.show_step(self.index), self.back != "review"))
        spec += self._value_buttons(self.field_path)
        spec.append(("שיעורים", self.show_home, not self.lesson_id and self.back != "review"))
        self._buttons(spec)

    def _render_field(self, keep_scroll=False):
        e = G.param(self.field_path)
        self.doc.set_blocks([("title", e["title"])] + self._card(self.field_path), keep_scroll=keep_scroll)

    def open_field(self, path, back=None):
        """Show a field of a list (tour, review): go to its page, highlight it and show its card."""
        page = self._page_of(path)
        if page:
            self.app.goto_page(page)
            self._hilite(page, path)
        self.show_field(path, back=back)

    def _page_of(self, path):
        """The page that shows `path` for this project (the current page first)."""
        names = [self.app.current_page] + [n for n, _fl, _wf in self._pages()]
        for name in names:
            w = self._row(name, path) if name else None
            if w and w[0].grid_info():
                return name
        return None

    # ------------------------------------------------------------------ field card with the live effect
    def _project(self):
        return self._live if self._live is not None else self.app.project

    def _card(self, path):
        value = self._value(path)
        project = self._project()
        res = G.check(path, value, project)
        e = G.param(path)
        f = self._field_spec(path)
        alts = GI.alternatives(path, value, f, e, project, res)
        extra = []
        if e and e.get("impact", 1) == 0:
            extra = [("box", "plain", ["ההשפעה על טווחי התצפית", "השדה הזה לא נכנס לחישוב הטווח - תיעוד, בדיקה "
                                       "צולבת או אבחון בלבד."], True)]
        elif f and f.get("kind") not in ("text", "multiline", "file"):
            key = (path, json.dumps(project, sort_keys=True, default=str), json.dumps(alts, default=str))
            if key != self._imp_key:
                self._imp_key, self._imp_res = key, None
                self.impact.request(project, path, alts, lambda r, key=key: self._impact_done(key, r))
            extra = GI.blocks(self._imp_res, (f or {}).get("unit", ""))
            if self._imp_res is not None and not alts and self._imp_res.get("base"):
                extra[-1][2].append("אין חלופה לחישוב לערך הזה (אפס, טקסט או בחירה ארוכה). שנו את הערך כדי לראות "
                                    "את ההשפעה.")
        return G.field_blocks(path, value, project, extra=extra)

    def _impact_done(self, key, res):
        if key != self._imp_key:
            return
        self._imp_res = res
        if self.mode == "field" and self.field_path == key[0]:
            self._render_field(keep_scroll=True)
        elif self.mode == "step" and self._step_path() == key[0]:
            steps = self._steps()
            self._render_step(steps[self.index], getattr(self, "step_hidden", False), keep_scroll=True)
        elif self.mode == "review" and key[0] == "":
            self._review_ranges = res
            self._render_review(keep_scroll=True)

    def _value_buttons(self, path):
        """'Apply the suggested value' / 'Undo' of the shown field."""
        if not path:
            return []
        out = []
        s = G.suggestion(G.check(path, self._value(path), self._project()))
        if s is not None and self._field_spec(path) is not None:
            out.append(("החל את הערך המוצע", lambda: self.apply_value(path, s), False))
        if self._undo and self._undo[0] == path:
            out.append(("בטל", self.undo, False))
        return out

    def apply_value(self, path, value):
        self._undo = (path, self._value(path))
        self._set(path, value)
        self.app.status.set("Guide: %s = %s" % (path, value))

    def undo(self):
        if self._undo:
            path, value = self._undo
            self._undo = None
            self._set(path, value)

    def _set(self, path, value):
        app = self.app
        entries = app.vars.get(path) or []
        if entries and entries[0][0]["kind"] == "choice":
            # through the form's own selection: presets (jitter, task criteria ...) fill their values
            f, var, w = entries[0]
            label = next((l for v, l in f["opts"] if v == value), None)
            if label is not None:
                w.set(label)
                app._choice_selected(w, f, var, 0)
        else:
            app._set_value(path, value)
            app._user_edit(path, 0)
        app.refresh()                                   # re-checks and re-renders the card (on_project_change)
        if self.mode == "field":
            self._field_buttons()
        elif self.mode == "step":
            self._step_buttons()

    # ------------------------------------------------------------------ lists: tour group, review
    def _field_list(self, paths):
        out = []
        for path in paths:
            s = G.field_summary(path, self._value(path), self.app.project)
            if s:
                state, title, text, meta = s
                out.append(("card", title, text, meta, lambda p=path: self.open_field(p), state == "ok", state))
        out.append(("muted", "לחיצה על שדה פותחת את הכרטיס המלא עם חישוב ההשפעה על הטווח."))
        return out

    def show_review(self):
        self.mode = "review"
        self.field_path = None
        self.back = None
        self._unhilite()
        self._review_ranges = None
        key = self._imp_key = ("", json.dumps(self.app.project, sort_keys=True, default=str), "[]")
        self.impact.request(self.app.project, "", [], lambda r: self._impact_done(key, r))
        self._render_review()
        spec = [("בדוק שוב", self.show_review, True), ("חשב עכשיו", self.app.calculate, False)]
        if self.lesson_id:
            spec.append(("חזרה לשיעור", lambda: self.show_step(self.index), False))
        spec.append(("שיעורים", self.show_home, False))
        self._buttons(spec)
        self._draw_head()

    def _render_review(self, keep_scroll=False):
        self.doc.set_blocks([("title", "בדיקת כל הערכים")] + self._review_blocks(), keep_scroll=keep_scroll)

    def _review_blocks(self):
        app = self.app
        r = G.review(self._pages(), app.project, app._row_visible, self._value)
        out = [("chips", [("%d לבדיקה" % len(r["warn"]), "high" if r["warn"] else "ok"),
                          ("%d תקינים" % r["ok"], "ok"), ("%d שדות נבדקו" % r["n"], "info")])]
        rr = self._review_ranges
        if rr is not None and rr.get("base"):
            out.append(("box", "info", ["הטווחים עכשיו", GI.ranges_line(rr["base"])], True))
        elif rr is not None:
            out.append(("box", "plain", ["הטווחים עכשיו", "אי אפשר לחשב: " + (rr.get("error") or "")], True))
        else:
            out.append(("box", "plain", ["הטווחים עכשיו", "מחשב..."], True))
        if not r["warn"]:
            out.append(("box", "ok", ["לא נמצאו ערכים חשודים", "כל הערכים שהמדריך יודע לבדוק בתחום הסביר. זה לא "
                                      "מבטיח שהם נכונים - עדיין כדאי להחליף ערכי preset בנתוני המערכת שלכם."], True))
        else:
            out.append(("p", "ההערות מסודרות מהשדה המשפיע ביותר על הטווח. לחיצה פותחת את השדה בטופס, עם הסבר, ערך "
                             "מוצע (אם יש) והשפעה מחושבת על הטווחים."))
            for imp, path, page, res in r["warn"]:
                e = G.param(path)
                he = G.PAGE_HE.get(page, (page, ""))[0]
                meta = "%s · ערך: %s · %s" % (he, G._value_text(self._value(path)),
                                              ("★" * imp + " " if imp else "") + G.IMPACT_TEXT[imp])
                text = res[1] + (" מוצע: %s." % G._value_text(res[2]) if G.suggestion(res) is not None else "")
                out.append(("card", "⚠ " + e["title"], text, meta,
                            lambda p=path: self.open_field(p, back="review"), False, "warn"))
        return out

    # ------------------------------------------------------------------ app hooks
    def on_project_change(self):
        """Called by App.refresh: re-check the value of the shown parameter."""
        if self.mode == "step":
            steps = self._steps()
            if self.index < len(steps) and (steps[self.index].get("path") or steps[self.index].get("review")):
                self._render_step(steps[self.index], getattr(self, "step_hidden", False), keep_scroll=True)
                self._step_buttons()
        elif self.mode == "field":
            self._render_field(keep_scroll=True)
            self._field_buttons()

    TYPING_MS = 300

    def on_field_typing(self, path):
        """A key was typed in an entry: re-check the card once typing pauses, without waiting for the field to lose
        focus (App.refresh)."""
        if self._typing_job:
            self.after_cancel(self._typing_job)
        self._typing_job = self.after(self.TYPING_MS, lambda: self._typed(path))

    def _typed(self, path):
        self._typing_job = None
        self._live = self.app.collect()                 # the typed text, as the form will read it
        try:
            if path != self.field_path and path != self._step_path():
                self.show_field(path)                   # the card of the field being edited
            else:
                self.on_project_change()
        finally:
            self._live = None

    def on_field_focus(self, path):
        if G.param(path) and not (self.mode == "step" and self._step_path() == path) and path != self.field_path:
            self.show_field(path)

    def _step_path(self):
        steps = self._steps()
        if self.mode != "step" or self.index >= len(steps) or steps[self.index].get("group"):
            return None
        return steps[self.index].get("path")

    def _value(self, path):
        try:
            return _get(self._project(), path)
        except (KeyError, IndexError, TypeError, ValueError):
            return None

    # ------------------------------------------------------------------ highlight in the form
    def _row(self, page, path):
        inner = self.app.pages[page].inner if page in self.app.pages else None
        for f, widgets, _vw, _g in self.app.rows:
            if f.get("path") == path and widgets and (inner is None or widgets[0].master is inner):
                return widgets
        return None

    def _hilite(self, page, path):
        widgets = self._row(page, path)
        if not widgets:
            return False
        lab = widgets[0]
        self.app.update_idletasks()
        if not lab.grid_info():                         # grid_remove()d: not shown for this project
            return False
        self._unhilite()
        self.hilited = lab
        lab.configure(style="Guide.TLabel")
        sf = self.app.pages.get(page)
        if sf is not None:
            h = max(sf.inner.winfo_height(), 1)
            sf.canvas.yview_moveto(max(0.0, (lab.winfo_y() - sf.canvas.winfo_height() / 3) / h))
        self._flash(6)
        return True

    def _flash(self, n):
        if self._flash_job:
            self.after_cancel(self._flash_job)
            self._flash_job = None
        if not self.hilited or n <= 0:
            return
        try:
            self.hilited.configure(style="Guide.TLabel" if n % 2 == 0 else "GuideFlash.TLabel")
        except tk.TclError:
            return
        self._flash_job = self.after(220, lambda: self._flash(n - 1))

    def _unhilite(self):
        if self._flash_job:
            self.after_cancel(self._flash_job)
            self._flash_job = None
        if self.hilited is not None:
            try:
                self.hilited.configure(style="")
            except tk.TclError:
                pass
        self.hilited = None

    def close(self):
        self.impact.cancel()
        if self._typing_job:
            self.after_cancel(self._typing_job)
            self._typing_job = None
        self._unhilite()
        self._save()


def configure_styles(style, font_semi):
    style.configure("Guide.TLabel", background=HILITE, foreground="#1d2433", font=font_semi)
    style.configure("GuideFlash.TLabel", background="#ffd666", foreground="#1d2433", font=font_semi)
