"""Detector lookup from the Detector Atlas in detector_lookup_HTML/.

Sources: the Detectors_Atlas website (a local copy of the GitHub repository, e.g.
detector_lookup_HTML/Detectors_Atlas/, read from data/live.json -> data/catalog.json -> index.html, or its
published data/live.json on GitHub Pages), single atlas HTML pages that embed their catalog as JSON in
<script id="detectorData" type="application/json">, and plain JSON exports (a list of the same records).
`suggestions(record)` maps one atlas record onto the TRM4 project fields, in the same shape that
detector_lookup.lookup() returns, so the detector dialog can review / apply them.
"""
import html
import json
import os
import re
import urllib.request

ATLAS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "detector_lookup_HTML")

_DATA_RE = re.compile(r'<script[^>]*\bid=["\']detectorData["\'][^>]*>(.*?)</script>', re.S | re.I)
_REMOTE_RE = re.compile(r'url\s*=\s*https://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?\s*$', re.M)
_SITE_DATA = (os.path.join("data", "live.json"), os.path.join("data", "catalog.json"), "index.html")
_NUM = r"(\d+(?:\.\d+)?)"


class AtlasError(Exception):
    pass


def is_url(path):
    return path.lower().startswith(("http://", "https://"))


def site_root(path):
    """Website folder that `path` belongs to (the folder with index.html), or None."""
    if is_url(path):
        return None
    d = os.path.dirname(os.path.abspath(path))
    for cand in (d, os.path.dirname(d)):
        if os.path.isfile(os.path.join(cand, "index.html")) and os.path.isdir(os.path.join(cand, "data")):
            return cand
    return None


def site_feed_url(site):
    """Published data/live.json (GitHub Pages) of a website folder cloned from GitHub, else None."""
    try:
        with open(os.path.join(site, ".git", "config"), encoding="utf-8") as fh:
            m = _REMOTE_RE.search(fh.read())
    except OSError:
        return None
    return "https://%s.github.io/%s/data/live.json" % (m.group(1).lower(), m.group(2)) if m else None


def _sites(folder):
    """Website folders: `folder` itself and its direct sub-folders that hold an atlas website."""
    subs = [os.path.join(folder, f) for f in sorted(os.listdir(folder))]
    return [d for d in [folder] + subs
            if os.path.isdir(d) and any(os.path.isfile(os.path.join(d, f)) for f in _SITE_DATA[:2])]


def atlas_files(folder=ATLAS_DIR):
    """Atlas sources: for each website folder its best data file (live.json, else catalog.json, else
    index.html) followed by its online feed, then loose atlas files in `folder` (HTML first, newest first)."""
    if not os.path.isdir(folder):
        return []
    out = []
    for site in _sites(folder):
        best = next(os.path.join(site, f) for f in _SITE_DATA if os.path.isfile(os.path.join(site, f)))
        out.append(best)
        url = site_feed_url(site)
        if url:
            out.append(url)
    loose = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith((".html", ".htm", ".json"))
             and os.path.join(folder, f) not in out and f.lower() not in ("source_state.json",)]
    return out + sorted(loose, key=lambda f: (not f.lower().endswith((".html", ".htm")), -os.path.getmtime(f)))


def file_label(path, folder=ATLAS_DIR):
    """Short name of an atlas source for the file list."""
    if is_url(path):
        return "%s website - online (%s)" % (path.split("/")[3] if path.count("/") > 3 else "Atlas", path)
    site = site_root(path)
    if site:
        return "%s website - local copy (%s)" % (os.path.basename(site), os.path.relpath(path, site).replace("\\", "/"))
    try:
        return os.path.relpath(path, folder)
    except ValueError:
        return path


def _read(path):
    if is_url(path):
        try:
            req = urllib.request.Request(path, headers={"User-Agent": "TRM4 detector lookup",
                                                        "Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read(50 * 1024 * 1024).decode("utf-8")
        except Exception as e:
            raise AtlasError("Could not download %s:\n%s\n\nUse the local copy of the website instead." % (path, e))
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as e:
        raise AtlasError("Could not read %s:\n%s" % (path, e))


def load_info(path):
    """(detector records sorted by manufacturer / model, info dict) from an atlas website feed (live.json),
    JSON catalog or HTML page.  info: last_checked, message, events (new listings found by the website's
    watcher).  Records named by an event get '_new_listing' = detection time."""
    text = _read(path)
    name = path if is_url(path) else os.path.basename(path)
    if path.lower().split("?")[0].endswith(".json"):
        raw = text
    else:
        m = _DATA_RE.search(text)
        if not m:
            raise AtlasError("%s does not contain detector data\n(no <script id=\"detectorData\"> block)." % name)
        raw = m.group(1)
    try:
        data = json.loads(raw)
    except ValueError:
        try:
            data = json.loads(html.unescape(raw))
        except ValueError as e:
            raise AtlasError("Invalid detector data in %s:\n%s" % (name, e))
    info = {"last_checked": "", "message": "", "events": []}
    if isinstance(data, dict):  # live.json {"catalog": [...], "events": [...]} or {"detectors": [...]} exports
        info.update({k: data[k] for k in ("last_checked", "message", "events") if data.get(k)})
        data = data["catalog"] if isinstance(data.get("catalog"), list) else \
            next((v for v in data.values() if isinstance(v, list)), [])
    recs = [d for d in data if isinstance(d, dict) and d.get("model")]
    if not recs:
        raise AtlasError("No detectors found in %s." % name)
    new = {e.get("record_id"): e.get("detected_at") or "" for e in info["events"] if isinstance(e, dict)}
    for d in recs:
        if d.get("id") in new or d.get("discovered_at"):
            d["_new_listing"] = new.get(d.get("id")) or d.get("discovered_at")
    return sorted(recs, key=lambda d: ((d.get("manufacturer") or "").lower(), (d.get("model") or "").lower())), info


def load(path):
    """Detector records (list of dicts) from an atlas website feed, HTML page or JSON catalog."""
    return load_info(path)[0]


def _num(v):
    try:
        return float(v) if v not in (None, "") and not isinstance(v, bool) else None
    except (TypeError, ValueError):
        return None


def category(rec):
    return "Thermal" if (rec.get("band") or "").upper() in ("MWIR", "LWIR") else "Visible"


def imager_type(rec):
    """'cooled' / 'uncooled' for thermal detectors, None when the atlas does not say."""
    if category(rec) != "Thermal":
        return None
    cls = (rec.get("cooling_class") or "").lower()
    tech = (rec.get("technology") or "").lower()
    if cls.startswith("uncooled") or "microbolometer" in tech or "bolometer" in tech or \
            tech in ("vox", "a-si", "amorphous silicon"):
        return "uncooled"
    if cls.startswith("cryogenic") or tech in ("mct", "insb", "xbn", "insb / xbn", "t2sl", "qwip", "hfm"):
        return "cooled"
    if (rec.get("band") or "").upper() == "MWIR":  # MWIR FPAs are photon detectors (no MWIR bolometers here)
        return "cooled"
    return None


def spectral_limits(rec):
    """(cut-on, cut-off) in um from a text like '8–14 µm' or '(3.7 ± 0.2)–(4.8 ± 0.2) µm', else (None, None).
    Ranges the atlas marks as not verified are ignored."""
    if (rec.get("spectral_verification") or "").lower().startswith("not verified"):
        return None, None
    s = re.sub(r"[±+]\s*/?-?\s*\d+(?:\.\d+)?", "", rec.get("spectral_range") or "")  # drop tolerances
    s = s.replace("(", "").replace(")", "")
    m = re.search(_NUM + r"\s*(?:[-–—~]|to)\s*" + _NUM + r"\s*(?:µm|um|μm)", s)
    if not m:
        return None, None
    lo, hi = float(m.group(1)), float(m.group(2))
    return (lo, hi) if hi > lo else (None, None)


def spectral_note(rec):
    parts = [rec.get("spectral_range") or "", rec.get("spectral_verification") or "", rec.get("spectral_notes") or ""]
    return "; ".join(p for p in parts if p)


def operating_temp(rec):
    """(FPA temperature K, note) from fpa_operating_k or the first 'NNN K' in fpa_operating_note."""
    note = rec.get("fpa_operating_note") or ""
    t = _num(rec.get("fpa_operating_k"))
    if t is None:
        m = re.search(_NUM + r"\s*K\b", note)
        t = float(m.group(1)) if m else None
    return t, note


def stated_qe(rec):
    """(QE %, wavelength um or None, text) from qe_percent or a 'QE >80% at 1550nm' style note."""
    text = " ".join(str(rec.get(k) or "") for k in ("metric_notes", "notes"))
    m = re.search(r"\bQE\b[^0-9%;]{0,15}" + _NUM + r"\s*%(?:\s*(?:at|@)\s*" + _NUM + r"\s*(nm|µm|um|μm))?", text, re.I)
    qe = _num(rec.get("qe_percent"))
    if qe is None and m:
        qe = float(m.group(1))
    lam = None
    if m and m.group(2) and (qe is None or abs(float(m.group(1)) - qe) < 1e-6):
        lam = float(m.group(2)) / (1000.0 if m.group(3) == "nm" else 1.0)
    return qe, lam, (m.group(0) if m else "")


def qe_shape(rec):
    """Name of the TRM4 QE preset that matches the detector material (technology) and band, or None when
    the material is unknown, ambiguous (e.g. 'InSb / XBn') or has no preset (T2SL, CQD, HFM, microbolometer)."""
    from . import presets as P
    tech = (rec.get("technology") or "").lower()
    band = (rec.get("band") or "").upper()
    cut_off = spectral_limits(rec)[1]
    if "/" in tech or "not individually" in tech:
        return None
    if "ingaas" in tech:
        name = "InGaAs extended generic" if cut_off and cut_off > 1.8 else "InGaAs generic"
    elif "xbn" in tech:
        name = "XBn MWIR 3.6-4.2 um"
    elif "insb" in tech:
        name = "InSb MWIR generic"
    elif "qwip" in tech:
        name = "QWIP %s generic" % band
    elif "mct" in tech or "cmt" in tech:
        name = "CMT %s generic" % band
    elif "cmos" in tech or "ccd" in tech or (band == "DAY" and tech in ("", "not verified")):
        name = "CCD Silicon generic"
    else:
        return None
    return name if name in P.DETECTOR_QE else None


def _interp(pts, lam):
    if lam <= pts[0][0] or lam >= pts[-1][0]:
        return 0.0 if lam < pts[0][0] or lam > pts[-1][0] else (pts[0][1] if lam == pts[0][0] else pts[-1][1])
    for (l0, q0), (l1, q1) in zip(pts, pts[1:]):
        if l0 <= lam <= l1:
            return q0 + (q1 - q0) * (lam - l0) / (l1 - l0)


def _window(pts, lo, hi):
    """The curve limited to the band lo..hi (steep edges), or None if it has no response there."""
    d = min(0.02, (hi - lo) / 20)
    inside = [(l, q) for l, q in pts if lo < l < hi]
    rows = [(lo - d, 0.0), (lo, _interp(pts, lo))] + inside + [(hi, _interp(pts, hi)), (hi + d, 0.0)]
    return rows if max(q for _, q in rows) > 0 else None


def _band50(pts):
    """(lo, hi) where the curve crosses 50 % of its peak."""
    half = max(q for _, q in pts) / 2.0
    above = [l for l, q in pts if q >= half]
    return above[0], above[-1]


def preset_matches_range(shape, lo, hi, tol=0.15):
    """True when the preset's own band (50 % points) already equals the verified range within tol um."""
    from . import presets as P
    p_lo, p_hi = _band50(P.DETECTOR_QE[shape])
    return abs(p_lo - lo) <= tol and abs(p_hi - hi) <= tol


TYPICAL_QE = 70.0  # % - assumed level of the flat QE table when only the band is known


def qe_table(rec):
    """(custom QE text 'lambda[um] QE[%]' per line, note, apply by default) or ('', '', False).

    - Matching material curve + stated QE: the curve scaled to the stated QE at the stated wavelength (or peak).
    - Matching material curve + verified spectral range: the curve limited to that range (unless the preset's
      own band already is that range - then the preset itself is proposed by suggestions()).
    - No material curve but a verified range (cooled / SWIR / visible photon detectors): a flat table over the
      range at the stated QE, or at the assumed TYPICAL_QE.
    Without a stated QE or verified range, ('', '', False): the material preset (or the current QE) is used.
    The third value is True whenever a table is returned (kept for the dialog's 'apply by default' flag)."""
    from . import presets as P
    qe, lam, text = stated_qe(rec)
    shape = qe_shape(rec)
    lo, hi = spectral_limits(rec)
    if shape and qe is None and lo and preset_matches_range(shape, lo, hi):
        return "", "", False
    src = text or ("qe_percent = %g %%" % qe if qe is not None else "")
    rng = "range %s" % rec.get("spectral_range") if lo else ""
    if shape and (qe is not None or lo):
        pts = list(P.DETECTOR_QE[shape])
        notes = ["Shape from '%s'" % shape]
        if qe is not None:
            if lam is not None and pts[0][0] <= lam <= pts[-1][0]:
                ref, at = _interp(pts, lam), "at %g um" % lam
            else:
                ref, at = max(q for _, q in pts), "at the peak"
            if ref > 0:
                k = qe / ref
                pts = [(l, min(100.0, q * k)) for l, q in pts]
                notes.append("scaled x%.3g to %g %% %s (atlas: %s)" % (k, qe, at, src))
        if lo:
            win = _window(pts, lo, hi)
            if win:
                pts = win
                notes.append("limited to the atlas %s" % rng)
        if len(notes) == 1:
            return "", "", False
        return "\n".join("%g %.4g" % r for r in pts), ", ".join(notes) + ".", True
    if lo and imager_type(rec) != "uncooled":
        level = qe if qe is not None else TYPICAL_QE
        d = min(0.02, (hi - lo) / 20)
        rows = [(lo - d, 0.0), (lo, level), (hi, level), (hi + d, 0.0)]
        if qe is not None:
            note = "Flat %g %% over the atlas %s (atlas: %s; no QE curve for '%s')." % (
                qe, rng, src, rec.get("technology") or "")
        else:
            note = ("Material '%s' has no QE preset: flat %g %% (assumed level - edit if known) over the atlas %s." % (
                rec.get("technology") or "?", level, rng))
        return "\n".join("%g %.4g" % r for r in rows), note, True
    return "", "", False


def label(rec):
    return "%s %s" % (rec.get("manufacturer") or "", rec.get("model") or "")


def summary(rec):
    fmt_ = "%sx%s" % (rec.get("width") or "?", rec.get("height") or "?")
    pitch = "%g um" % rec["pitch_um"] if _num(rec.get("pitch_um")) else "pitch n/a"
    lines = ["%s - %s %s, %s, %s, %s, %s" % (label(rec), rec.get("band") or "", rec.get("technology") or "",
                                              fmt_, pitch, rec.get("product_type") or "",
                                              rec.get("cooling_class") or "")]
    if rec.get("_new_listing"):
        lines.append("NEW LISTING found by the atlas watcher on %s (not the release date) - %s" % (
            rec["_new_listing"][:10], rec.get("watch_status") or rec.get("status") or "review the specifications"))
    for k, title in (("notes", "Notes"), ("metric_notes", "Metrics"), ("cooling", "Cooling")):
        if rec.get(k):
            lines.append("%s: %s" % (title, rec[k]))
    if spectral_note(rec):
        lines.append("Spectral range: %s" % spectral_note(rec))
    table, note, on = qe_table(rec)
    if table:
        lines.append("Spectral QE: %s%s" % (note, "" if on else " (row not ticked)"))
    elif qe_shape(rec):
        qe = stated_qe(rec)[0]
        lines.append("Spectral QE: '%s' preset for the detector material%s." % (
            qe_shape(rec), "" if qe is None else " (stated QE %g %% not applied)" % qe))
    else:
        lines.append("Spectral QE: material unknown or no matching preset - the project's current QE setting is kept.")
    for c in rec.get("cooler_options") or []:
        extra = ", ".join("%s %s" % (k.replace("_", " "), c[k]) for k in ("power_steady", "cooldown", "mttf", "weight")
                          if c.get(k))
        lines.append("Cooler: %s (%s)%s" % (c.get("model", ""), c.get("type", ""), " - " + extra if extra else ""))
    lines.append("Source: %s (%s, checked %s)" % (rec.get("source_url") or "-", rec.get("source_level") or "-",
                                                 rec.get("checked") or "-"))
    for k, title in (("spectral_source_url", "Spectral source"), ("technology_source_url", "Technology source"),
                     ("cooling_source_url", "Cooling source")):
        if rec.get(k) and rec[k] != rec.get("source_url"):
            lines.append("%s: %s" % (title, rec[k]))
    return "\n".join(lines)


def source_urls(rec):
    """[(title, url)] of the distinct source links of a record."""
    out = []
    for k, title in (("source_url", "Product page"), ("spectral_source_url", "Spectral source"),
                     ("technology_source_url", "Technology source"), ("cooling_source_url", "Cooling source")):
        u = rec.get(k)
        if u and u not in [x[1] for x in out]:
            out.append((title, u))
    return out


ACTIVE_NOTE = "= pitch (100 % fill assumed - the atlas gives no active area; reduce it if the datasheet states a " \
              "fill factor)"
# offered but not ticked by default: the atlas value is a limit, not an operating point
NOT_TICKED = {"basic.frame_rate"}


def suggestions(rec):
    """[(key, project path, label, unit, value, note)] for the values the atlas record gives."""
    src = "Detector Atlas: %s" % (rec.get("source_level") or "catalog")
    metric = rec.get("metric_notes") or ""
    t_op, t_note = operating_temp(rec)
    itype = imager_type(rec)
    # Cut-on / cut-off only drive the flat response of uncooled detectors; for photon detectors the
    # band is applied through the spectral QE table (qe_table()).
    cut_on, cut_off = spectral_limits(rec) if category(rec) == "Thermal" and itype != "cooled" else (None, None)
    pitch = _num(rec.get("pitch_um"))
    rows = [
        ("imager_type", "imager_type", "Imager type (Thermal)", "", itype,
         "%s; %s" % (rec.get("cooling_class") or "", rec.get("technology") or "")),
        ("n_h", "detector.n_h", "Number of horizontal detectors", "", _num(rec.get("width")), src),
        ("n_v", "detector.n_v", "Number of vertical detectors", "", _num(rec.get("height")), src),
        ("pitch_h_um", "detector.pitch_h_um", "Horizontal detector pitch", "um", pitch, src),
        ("pitch_v_um", "detector.pitch_v_um", "Vertical detector pitch", "um", pitch, src),
        # the active size must follow the pitch, otherwise the old active area (and fill factor) is kept
        ("active_h_um", "detector.a_h_um", "Horizontal dimension (active)", "um", pitch, ACTIVE_NOTE),
        ("active_v_um", "detector.a_v_um", "Vertical dimension (active)", "um", pitch, ACTIVE_NOTE),
        ("frame_rate_hz", "basic.frame_rate", "Frame rate", "Hz", _num(rec.get("max_fps")),
         "maximum full-frame rate (%s) - not ticked: enter the operating frame rate" % (metric or src)),
        ("readout_noise_e", "detector.noise_floor_e", "Noise floor (additive)", "e-", _num(rec.get("read_noise_e")),
         metric or src),
        ("netd_mK", "detector.netd_mK", "NETD", "mK", _num(rec.get("netd_mk")), metric or src),
        # the FPA temperature is not the cold shield temperature (which sets the shield's own emission)
        ("operating_temp_K", "detector.T_sensor_K", "Sensor operating temperature", "K",
         t_op if itype == "cooled" else None, "FPA operating temperature: %s" % (t_note or "%g K" % (t_op or 0))),
        ("cut_on_um", "detector.cuton_um", "Cut-on wavelength", "um", cut_on, spectral_note(rec)),
        ("cut_off_um", "detector.cutoff_um", "Cut-off wavelength", "um", cut_off, spectral_note(rec)),
    ]
    # Material QE preset, unless a stated QE / verified band gives a custom table (offered by qe_table()).
    if not qe_table(rec)[0]:
        rows.append(("qe_preset", "detector.qe_preset", "Spectral quantum efficiency", "", qe_shape(rec),
                     "Preset for the detector material: %s, %s" % (rec.get("technology") or "", rec.get("band") or "")))
    return [r for r in rows if r[4] is not None]
