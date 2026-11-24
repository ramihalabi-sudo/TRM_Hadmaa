"""Live effect of a parameter value on the DRI ranges and on the image-quality figures, for the interactive guide.

For the parameter shown in the guide, the model is run for the current project and for one or a few alternative
values: the suggested value of a failed plausibility check, a +20 % (or -20 %) step of a number, the other state
of a switch, or the other options of a short choice.  The result says, for this system, how much the value moves the
Detection / Recognition / Identification ranges and which derived image-quality values (IFOV, FOV, Q = F lambda / d,
diffraction cut-off ...) change.  One fast model run takes about 0.5 - 2 s, so the runs are done in a worker thread
(ImpactWorker) and cached by the project state.
"""
import copy
import json
import queue
import threading

from . import analysis as A
from . import derived as DV
from . import extensions as X
from . import presets as P

MAX_OPTIONS = 5                    # choices with more options get only the suggested value
NO_SWEEP = {"category", "imager_type", "mode.environment", "detector.noise_mode", "atmosphere.mode",
            "turbulence.cn2_mode", "display.observer", "optics.mtf_source", "stab.jitter_mode", "irradiance.mode",
            "irradiance.type", "irradiance.spectrum", "optics.aperture", "target.t_refl_mode", "target.b_refl_mode",
            "target.t_emis_mode", "target.b_emis_mode", "detector.tint_mode", "detector.dark_mode",
            "detector.adc_mode", "detector.cs_mode", "detector.fpn_mode", "optics.tau_mode", "atmosphere.path_mode",
            "basic.fov_mode", "target.flight", "turbulence.mit_model", "display.algo_criterion"}
# parameters whose +-20 % step is meaningless: an absolute step instead
ABS_STEP = {"K": 10.0, "%": 10.0, "deg": 10.0}


def _state(p):
    return json.dumps(p, sort_keys=True, default=str)


def apply_value(case, path, value):
    """Set `path` = value in a project copy together with what the form does on such a change (pitch / focal length
    keep their physical group, presets fill their values, square pixels follow the horizontal entries)."""
    if path in ("detector.pitch_h_um", "optics.f_mm") and isinstance(value, (int, float)):
        A.apply_policy(case, path, value)
    else:
        A.set_path(case, path, value)
    if path == "target.preset" and value in P.THERMAL_TARGETS:
        t = P.THERMAL_TARGETS[value]
        for k in ("W_m", "H_m", "D_m", "T_bg_K", "dT_K"):
            case["target"][k] = t[k]
        for i, (lp, on) in enumerate(zip(t["tasks"], t["task_on"])):
            case["target"]["tasks"][i].update(lp=lp, on=on)
        case["target"]["task_preset"] = "target"
    elif path == "target.task_preset":
        vals = P.task_preset_values(case)
        if vals is not None:
            for i, lp in enumerate(vals):
                case["target"]["tasks"][i]["lp"] = lp
    elif path == "irradiance.preset" and value in P.NATURAL_SOURCES:
        case["irradiance"]["E_peak"] = P.NATURAL_SOURCES[value]["peak"]
    elif path == "atmosphere.preset" and value != "custom":
        case["atmosphere"]["mode"] = "extinction"
        for i, at in enumerate(P.atmosphere_preset(case, value)):
            case["atmosphere"]["atm"][i].update(at)
    elif path == "stab.jitter_preset" and value == "nvipm70":
        case["stab"].update(random_on=True, rand_h_mrad=X.TYPICAL_JITTER_MRAD, rand_v_mrad=X.TYPICAL_JITTER_MRAD)
    d = case.get("detector", {})
    if d.get("square"):
        d["pitch_v_um"], d["a_v_um"] = d["pitch_h_um"], d["a_h_um"]
    return case


def alternatives(path, value, field, entry, project, check):
    """[(label, value)] to compare with the current value; `check` is the guide check result of the value."""
    if not entry or entry.get("impact", 1) == 0:
        return []
    out = []
    if check and len(check) > 2 and check[2] is not None and check[2] != value:
        out.append(("הערך המוצע", check[2]))
    kind = (field or {}).get("kind", "float")
    if out or path in NO_SWEEP:
        return out
    if kind == "bool" and isinstance(value, bool):
        out.append(("מופעל" if not value else "כבוי", not value))
    elif kind == "choice":
        opts = [o[0] if isinstance(o, (list, tuple)) else o for o in ((field or {}).get("opts") or [])]
        names = {o[0]: o[1] for o in ((field or {}).get("opts") or []) if isinstance(o, (list, tuple))}
        others = [o for o in opts if o != value and o != "custom"]
        if 0 < len(others) <= MAX_OPTIONS:
            out += [(names.get(o, str(o)), o) for o in others]
    elif kind in ("float", "int") and isinstance(value, (int, float)) and not isinstance(value, bool) and value != 0:
        step = ABS_STEP.get((field or {}).get("unit", ""))
        if step and abs(value) > 50:
            cands = [value + step, value - step]
        else:
            cands = [value * 1.2, value * 0.8]
        fn = entry.get("check")
        for c in cands:
            c = int(round(c)) if kind == "int" else round(c, 6)
            if c == value:
                c = value + 1 if kind == "int" else c
            ok = True
            if fn:
                try:
                    r = fn(c, project)
                    ok = not (r and r[0] == "warn")
                except Exception:
                    ok = True
            if ok:
                out.append(("%+.0f%%" % (100.0 * (c - value) / value) if not step or abs(value) <= 50 else
                            "%+g %s" % (c - value, field.get("unit", "")), c))
                break
    return out


class ImpactCache:
    def __init__(self, size=300):
        self.size, self.data, self.lock = size, {}, threading.Lock()

    def ranges(self, project):
        """({task: km}, None) or (None, error text)."""
        key = _state(project)
        with self.lock:
            if key in self.data:
                return self.data[key]
        try:
            r, _w = A.model_ranges(project)
            out = (r, None)
        except Exception as e:                     # ModelError, invalid intermediate inputs while typing
            out = (None, str(e).split("\n")[0][:200])
        with self.lock:
            if len(self.data) >= self.size:
                self.data.pop(next(iter(self.data)))
            self.data[key] = out
        return out


# derived values that describe the image quality, with a short name (label prefix of derived.compute -> name)
QUALITY = (("IFOV = p / f", "IFOV"), ("Field of view", "FOV"), ("Q = lambda F / pitch", "Q = Fλ/d"),
           ("Effective F-number", "F-number"), ("Optics cut-off / Nyquist", "קטעון אופטי / נייקוויסט"),
           ("System magnification", "הגדלת המערכת"), ("Eye MTF at the detector Nyquist", "MTF העין בנייקוויסט"),
           ("Signal throughput", "העברת אות"), ("Maximum integration time", "זמן אינטגרציה מקסימלי"))


def _derived(p):
    """{short name: (value text, unit)} of the image-quality values of derived.compute."""
    try:
        rows, _w = DV.compute(p)
    except Exception:
        return {}
    out = {}
    for _g, label, val, unit in rows:
        for prefix, name in QUALITY:
            if label.startswith(prefix) and name not in out:
                out[name] = (val, unit)
    return out


def evaluate(cache, project, path, alts):
    """Model runs for the current project and each alternative ->
    {"base": ranges | None, "error": text | None, "alts": [(label, value, ranges | None, error, derived changes)]}."""
    base, err = cache.ranges(project)
    d0 = _derived(project)
    res = {"base": base, "error": err, "alts": []}
    for label, v in alts:
        case = apply_value(copy.deepcopy(project), path, v)
        r, e = cache.ranges(case)
        d1 = _derived(case)
        changes = [(k, d0[k][0], d1[k][0], d1[k][1]) for k in d1 if k in d0 and d0[k][0] != d1[k][0]]
        res["alts"].append((label, v, r, e, changes))
    return res


class ImpactWorker:
    """Runs evaluate() in one daemon thread; only the newest request is evaluated (stepping quickly through a lesson
    does not queue model runs).  The thread only fills a queue - Tk is touched from the Tk thread alone (a poll with
    after()), where the callback runs."""

    POLL_MS = 80

    def __init__(self, tk_widget):
        self.w, self.cache = tk_widget, ImpactCache()
        self.token = 0
        self.results = queue.Queue()
        self._job = None
        self._pending = None                        # newest request not yet started
        self._lock = threading.Lock()
        self._thread = None

    def request(self, project, path, alts, callback):
        self.token += 1
        tok = self.token
        with self._lock:
            self._pending = (tok, copy.deepcopy(project), path, list(alts), callback)
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._work, name="guide-impact", daemon=True)
                self._thread.start()
        self._schedule()
        return tok

    def _work(self):
        while True:
            with self._lock:
                job, self._pending = self._pending, None
                if job is None:
                    self._thread = None
                    return
            tok, project, path, alts, callback = job
            if tok != self.token:                   # superseded before it started
                continue
            try:
                res = evaluate(self.cache, project, path, alts)
            except Exception as e:
                res = {"base": None, "error": str(e)[:200], "alts": []}
            self.results.put((tok, callback, res))

    def _schedule(self):
        if self._job is None:
            try:
                self._job = self.w.after(self.POLL_MS, self._poll)
            except Exception:                       # widget destroyed
                self._job = None

    def _poll(self):
        self._job = None
        while True:
            try:
                tok, cb, res = self.results.get_nowait()
            except queue.Empty:
                break
            if tok == self.token:
                cb(res)
                return
        if self.busy():
            self._schedule()

    def busy(self):
        with self._lock:
            running = self._thread is not None or self._pending is not None
        return running or not self.results.empty()

    def cancel(self):
        self.token += 1


# ---------------------------------------------------------------------------------------------
# presentation (RtlCanvas blocks)
# ---------------------------------------------------------------------------------------------
TASK_HE = {"Detection": "גילוי", "Recognition": "הכרה", "Identification": "זיהוי"}


def _km(v):
    return ("%.2f" % v) if v < 10 else ("%.1f" % v)


def _fmt_value(v):
    if isinstance(v, bool):
        return "מופעל" if v else "כבוי"
    if isinstance(v, float):
        return ("%.4g" % v)
    return str(v)


def ranges_line(r):
    return " · ".join("%s %s ק\"מ" % (TASK_HE.get(t, t), _km(v)) for t, v in r.items())


def verdict(pct):
    a = abs(pct)
    if a < 2:
        return "כמעט ללא השפעה במערכת שלכם"
    if a < 8:
        return "השפעה קטנה"
    if a < 20:
        return "השפעה בינונית"
    return "השפעה גדולה"


def blocks(res, unit=""):
    """Blocks of the 'effect on the ranges' card."""
    if res is None:
        return [("box", "plain", ["ההשפעה על טווחי התצפית", "מחשב את הטווחים עם הערך שלכם ועם חלופה..."], True)]
    if res.get("base") is None:
        msg = res.get("error") or ""
        if "Field performance" in msg or "Range analyses" in msg:
            msg = "אין טווחים במצב מעבדה (Laboratory) או בלי משימה פעילה."
        return [("box", "plain", ["ההשפעה על טווחי התצפית", "אי אפשר לחשב כרגע: " + msg], True)]
    base = res["base"]
    lines = ["ההשפעה על טווחי התצפית", "עכשיו: " + ranges_line(base)]
    worst = 0.0
    for label, v, r, e, changes in res["alts"]:
        if r is None:
            lines.append("עם %s (%s): החישוב נכשל - %s" % (_fmt_value(v), label, e or ""))
            continue
        parts = []
        for t, R in r.items():
            R0 = base.get(t)
            if R0:
                pct = 100.0 * (R - R0) / R0
                if abs(pct) > abs(worst):
                    worst = pct
                parts.append("%s %s (%+.0f%%)" % (TASK_HE.get(t, t), _km(R), pct))
        suggested = label == "הערך המוצע"
        if isinstance(v, str):
            head = "עם " + (v if suggested else label)
        else:
            head = ("עם %s %s" % (_fmt_value(v), unit)).strip()
        lines.append("%s%s: %s" % (head, " (הערך המוצע)" if suggested else "", " · ".join(parts)))
        if changes:
            lines.append("איכות התמונה: " + "; ".join("%s %s במקום %s %s" % (k, b, a, u) for k, a, b, u in changes[:4]))
    if res["alts"]:
        lines.append(verdict(worst) + " (עד %+.0f%% בטווח)." % worst if abs(worst) >= 2 else verdict(worst) + ".")
    return [("box", "info", lines, True)]
