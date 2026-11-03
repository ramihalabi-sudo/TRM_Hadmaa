"""Interactive Hebrew guide panel of the GUI (optional: Help > Interactive guide, toolbar "Guide", Ctrl+G).

The panel docks at the right of the main window.  It has three views:
  home   - the lessons (guide_he.LESSONS) as cards, with progress
  step   - one step of a lesson: it switches workflow / page / result tab, highlights the parameter in the form
           and shows its field card with a live check of the entered value
  field  - the card of any parameter the user clicks while the guide is open
The text is drawn by rtl_tk (Tk on Windows does not lay out right-to-left paragraphs).
"""
import tkinter as tk
from tkinter import ttk

from . import guide_he as G
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
        self.hilited = None
        self._flash_job = None

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

    def _steps(self):
        return G.steps(self.lesson_id, self.app.project) if self.lesson_id else []

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
        self._unhilite()
        blocks = [("p", "בחרו שיעור. כל שיעור מוביל אתכם על המסכים האמיתיים, מסמן את השדה ובודק את "
                        "הערך שהזנתם."),
                  ("gap", 4)]
        for les in G.LESSONS:
            done = les["id"] in self.done
            meta = ("✓ הושלם" if done else "%d דקות · %d שלבים" % (les["minutes"],
                                                                      len(G.steps(les["id"], self.app.project))))
            blocks.append(("card", les["title"], les["summary"], meta, lambda i=les["id"]: self.start(i), done))
        blocks += [("h", "כרטיסי שדה"),
                   ("p", "כשהמדריך פתוח, לחיצה על שדה בטופס מציגה כאן הסבר עליו: מה הוא, כמה הוא משפיע על "
                         "הטווח, ערכים טיפוסיים ובדיקה של הערך שלכם."),
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
        last = self.index == len(steps) - 1
        spec = [("סיום" if last else "הבא", self.finish if last else lambda: self.show_step(self.index + 1), True)]
        if self.index > 0:
            spec.append(("הקודם", lambda: self.show_step(self.index - 1), False))
        if st.get("action") == "calculate":
            spec.append(("חשב עכשיו", app.calculate, False))
        elif st.get("path") and not hidden:
            spec.append(("הצג את השדה", lambda: self._hilite(st.get("page"), st["path"]), False))
        spec.append(("שיעורים", self.show_home, False))
        self._buttons(spec)
        self._draw_head()

    def _render_step(self, st, hidden=False, keep_scroll=False):
        blocks = [("title", st["title"])] + list(st.get("blocks", []))
        path = st.get("path")
        if path:
            e = G.param(path)
            if e and not st.get("blocks"):
                blocks[0] = ("title", e["title"])
            if hidden:
                blocks.append(("box", "plain", ["השדה לא מוצג כרגע בטופס - הוא לא רלוונטי לבחירות הנוכחיות "
                                                "(קטגוריה, מצב או פרמטרים מתקדמים)."]))
            blocks += G.field_blocks(path, self._value(path), self.app.project)
        self.doc.set_blocks(blocks, keep_scroll=keep_scroll)

    def finish(self):
        self.done.add(self.lesson_id)
        self.lesson_id, self.index = None, 0
        self._save()
        self.app.settings["guide"]["done"] = sorted(self.done)
        self.show_home()

    def show_field(self, path):
        if not G.param(path):
            return
        self.mode = "field"
        self.field_path = path
        self._render_field()
        spec = []
        if self.lesson_id:
            spec.append(("חזרה לשיעור", lambda: self.show_step(self.index), True))
        spec.append(("שיעורים", self.show_home, not self.lesson_id))
        self._buttons(spec)
        self._draw_head()

    def _render_field(self, keep_scroll=False):
        e = G.param(self.field_path)
        self.doc.set_blocks([("title", e["title"])] + G.field_blocks(self.field_path, self._value(self.field_path),
                                                                     self.app.project), keep_scroll=keep_scroll)

    # ------------------------------------------------------------------ app hooks
    def on_project_change(self):
        """Called by App.refresh: re-check the value of the shown parameter."""
        if self.mode == "step":
            steps = self._steps()
            if self.index < len(steps) and steps[self.index].get("path"):
                self._render_step(steps[self.index], getattr(self, "step_hidden", False), keep_scroll=True)
        elif self.mode == "field":
            self._render_field(keep_scroll=True)

    def on_field_focus(self, path):
        if G.param(path) and not (self.mode == "step" and self._step_path() == path) and path != self.field_path:
            self.show_field(path)

    def _step_path(self):
        steps = self._steps()
        return steps[self.index].get("path") if self.mode == "step" and self.index < len(steps) else None

    def _value(self, path):
        try:
            return _get(self.app.project, path)
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
        self._unhilite()
        self._save()


def configure_styles(style, font_semi):
    style.configure("Guide.TLabel", background=HILITE, foreground="#1d2433", font=font_semi)
    style.configure("GuideFlash.TLabel", background="#ffd666", foreground="#1d2433", font=font_semi)
