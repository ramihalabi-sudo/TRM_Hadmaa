"""Detector Atlas news: new detectors found by the atlas watcher on GitHub.

The Detectors_Atlas repository runs a watcher (GitHub Actions, every 6 h) that scans manufacturer catalogs
and writes each newly detected listing as an event into data/live.json.  `fetch()` reads that feed (GitHub
Pages, then raw GitHub, then the local copy in detector_lookup_HTML/) and returns the events as news items;
`unread()` filters out the ones the user marked as read (ids kept in the TRM settings under "atlas_news").
"""
import json
import os
import urllib.request

from . import detector_atlas as DA

REPO = ("ramihalabi-sudo", "Detectors_Atlas")
CHECK_INTERVAL_MS = 60 * 60 * 1000  # re-check while TRM is open (the watcher itself runs every 6 h)


def feed_urls():
    """Online feeds: the published GitHub Pages feed of the local clone (or the default repo), then raw GitHub."""
    owner, repo = REPO
    urls = []
    for site in DA._sites(DA.ATLAS_DIR) if os.path.isdir(DA.ATLAS_DIR) else []:
        url = DA.site_feed_url(site)
        if url and url not in urls:
            urls.append(url)
    urls += ["https://%s.github.io/%s/data/live.json" % (owner.lower(), repo),
             "https://raw.githubusercontent.com/%s/%s/main/data/live.json" % (owner, repo)]
    return list(dict.fromkeys(urls))


def local_feeds():
    if not os.path.isdir(DA.ATLAS_DIR):
        return []
    return [p for p in (os.path.join(s, "data", "live.json") for s in DA._sites(DA.ATLAS_DIR)) if os.path.isfile(p)]


def _load(src):
    if DA.is_url(src):
        req = urllib.request.Request(src, headers={"User-Agent": "TRM4 atlas news", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read(50 * 1024 * 1024).decode("utf-8"))
    with open(src, encoding="utf-8") as fh:
        return json.load(fh)


def items(data):
    """News items (newest first) from a live.json dict: one per watcher event, with the catalog record merged
    in when the event names one."""
    recs = {r.get("id"): r for r in data.get("catalog") or [] if isinstance(r, dict)}
    out = []
    for e in data.get("events") or []:
        if not isinstance(e, dict) or not e.get("id"):
            continue
        it = dict(e)
        rec = recs.get(e.get("record_id"))
        if rec:
            it["record"] = rec
            it["band"] = it.get("band") or rec.get("band")
        out.append(it)
    return sorted(out, key=lambda it: it.get("detected_at") or "", reverse=True)


def fetch():
    """(items, info) from the first feed that answers.  info: source, online (bool), last_checked, error."""
    errors = []
    for src in feed_urls() + local_feeds():
        try:
            data = _load(src)
        except Exception as e:  # network down, 404, bad JSON - try the next source
            errors.append("%s: %s" % (src, e))
            continue
        if isinstance(data, dict):
            return items(data), {"source": src, "online": DA.is_url(src), "last_checked": data.get("last_checked", ""),
                                 "error": "\n".join(errors)}
    return [], {"source": "", "online": False, "last_checked": "", "error": "\n".join(errors) or "No atlas feed found."}


def read_ids(settings):
    return set((settings.get("atlas_news") or {}).get("read", []))


def mark_read(settings, ids, read=True):
    """Add (or with read=False remove) item ids to the read list in `settings` (caller saves the settings)."""
    cur = read_ids(settings)
    cur = cur | set(ids) if read else cur - set(ids)
    settings.setdefault("atlas_news", {})["read"] = sorted(cur)


def unread(news, settings):
    done = read_ids(settings)
    return [it for it in news if it["id"] not in done]


def title(it):
    return "%s %s" % (it.get("manufacturer") or "", it.get("model") or "?")


def details(it):
    """One-line facts of a news item: detection date, band, key specs, status."""
    rec = it.get("record") or {}
    specs = dict(it.get("specs") or {}, **{k: v for k, v in rec.items() if v not in (None, "")})
    parts = ["Found %s" % (it.get("detected_at") or "?")[:10]]
    if it.get("band"):
        parts.append(it["band"])
    if specs.get("technology"):
        parts.append(specs["technology"])
    if specs.get("width") and specs.get("height"):
        parts.append("%sx%s" % (specs["width"], specs["height"]))
    if specs.get("pitch_um"):
        parts.append("%g um pitch" % float(specs["pitch_um"]))
    if specs.get("netd_mk"):
        parts.append("NETD %s mK" % specs["netd_mk"])
    if it.get("status"):
        parts.append(it["status"])
    return "  ·  ".join(parts)
