"""Recordings of the guide narration (natural / neural voices), and the bookkeeping of the English translation.

    py tools/make_guide_voice.py                 make the missing recordings of both languages
    py tools/make_guide_voice.py --lang he       one language
    py tools/make_guide_voice.py --check         only report: missing recordings, unused recordings, stale translations
    py tools/make_guide_voice.py --prune         delete recordings no text uses any more
    py tools/make_guide_voice.py --stamp         record the Hebrew source of every English translation (after
                                                 translating or re-checking guide_voice_en.py)

Every fixed sentence of the guide (guide_voice.static_texts: the field cards, the lessons, the tour and the home
page, as said) gets trm4/assets/voice/<lang>/<hash>.mp3; the hash is of the spoken text, so a changed sentence gets a
new recording and the old one becomes unused.  Sentences that depend on the project (the check of the value, the
ranges) are said by the Windows voice while the guide runs.

Making recordings needs the internet and the package edge-tts (py -m pip install edge-tts): it uses the Microsoft
neural voices he-IL-AvriNeural and en-US-AndrewNeural.  The Hebrew sentences are read by a Gemini voice
(guide_voice.GEMINI, tools/voice_gemini.py): that needs google-genai and a Gemini API key (GEMINI_API_KEY, or the file
.gemini_key in the user folder).  The application itself never needs any of them.
"""
import argparse
import asyncio
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from trm4 import guide_voice as GV  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voice_mix  # noqa: E402
import voice_gemini  # noqa: E402

SOURCES = os.path.join(GV.VOICE_DIR, "en_sources.json")


def plan(lang):
    """(needed {hash: text}, existing {hash}, kept {hash}: the Microsoft recordings still played in place of a missing
    Gemini one, which --prune keeps)."""
    texts = GV.static_texts(lang)
    need = {GV.rec_key(lang, t): t for t in texts}
    d = os.path.join(GV.VOICE_DIR, lang)
    have = {f[:-4] for f in os.listdir(d) if f.endswith(".mp3")} if os.path.isdir(d) else set()
    kept = {GV.legacy_key(lang, t) for t in texts if GV.rec_key(lang, t) not in have} - {None}
    return need, have, kept & have


def stale_translations():
    """Keys whose Hebrew source changed since --stamp (or that were never stamped)."""
    try:
        with open(SOURCES, encoding="utf-8") as f:
            stamped = json.load(f)
    except (OSError, ValueError):
        stamped = {}
    now = GV.en_sources()
    return sorted(k for k, h in now.items() if stamped.get(k) != h)


def sections(lang):
    """The parts of the guide in the order they are recorded: [(name, [said])], every sentence in the first part
    that says it.  home, lesson1..lesson6 (lesson4 with the engineering entry and its pages), tour, then the field
    cards page by page (fields-<page>, the pages with the most sentences first)."""
    G = GV.G
    seen, out = set(), []

    def part(name, scripts, extra=()):
        ts = []
        for s in scripts:
            for seg in s:
                if not callable(seg) and not isinstance(seg, dict):
                    ts.append(GV.speech(seg[1], lang))
        ts += [GV.speech(t, lang) for t in extra]
        uniq = [t for t in dict.fromkeys(ts) if t not in seen]
        seen.update(uniq)
        out.append((name, uniq))

    part("home", [GV.home_script(lang, G.LESSONS, set())] +
         [GV.home_script(lang, [les], {les["id"]}, intro=False) for les in G.LESSONS])
    for i, les in enumerate(G.LESSONS, 1):
        welcome = []
        GV._add(welcome, GV.lesson_welcome(lang, les["id"]), lang)
        scripts = [welcome] + [GV.step_script(lang, les["id"], st) for st in les["steps"]]
        extra = ()
        if les["id"] == "engineering":
            scripts += [GV.step_script(lang, "engineering", st) for st in G.entry_steps([], {}, lambda *a: True)]
            for page in G.PAGE_HE:
                for kw in ({"page_intro": True, "critical": True}, {"group": True},
                           {"group": True, "page_intro": True}):
                    scripts.append(GV.step_script(lang, "engineering",
                                                  dict({"title": "", "entry": True, "page": page}, **kw)))
            extra = ["אעבור איתכם על כל אחד מהם, ואסמן אותו בטופס כדי שתראו בדיוק על מה מדובר." if lang == "he"
                     else "I will go through each of them with you, and highlight it in the form so you can see "
                          "exactly what we are talking about."]
        part("lesson%d" % i, scripts, extra)
    tour = []
    if lang == "he":
        tour = [GV.step_script(lang, "tour", {"title": "", "blocks": [("box", "info", ["עמוד %s (%s)" % (he, page),
                                                                                         desc], True)]})
                for page, (he, desc) in G.PAGE_HE.items()]
    else:
        for page in GV.EN.PAGES:
            tour.append(GV.step_script(lang, "tour", {"title": "", "group": True, "page": page,
                                                      "blocks": [("box", "info", [""], True)]}))
            tour.append(GV.step_script(lang, "tour", {"title": "", "group": True, "page": page}))
    part("tour", tour + [GV.step_script(lang, "tour", st) for st in G.tour_steps([], {}, lambda *a: True)])
    pages = {}
    for path in G.PARAMS:
        if lang == "en" and path not in GV.EN.PARAMS:
            continue
        p = path.replace(".N.", ".0.")
        pages.setdefault(path.split(".")[0], []).extend(
            [GV.field_script(lang, p, None, None), GV.field_script(lang, p, None, None, brief=True)])
    fields = []
    for page, scripts in pages.items():
        part("fields-" + page, scripts)
        fields.append(out.pop())
    out += sorted(fields, key=lambda nt: -len(nt[1]))
    rest = [t for t in GV.static_texts(lang) if t not in seen]
    if rest:
        out.append(("other", rest))
    return out


def requests_for(n, batch):
    """About how many Gemini requests n sentences take: one per batch, and a fifth more for the retries."""
    return 0 if not n else -(-n // batch) + -(-n // (batch * 5))


class Pace:
    """The Gemini requests of one run: at most `rpm` started per minute, and at most `budget` in all (the daily
    limit counts every request, also one that failed)."""

    def __init__(self, rpm, budget):
        self.gap, self.budget, self.used, self.next = 60.0 / rpm, budget, 0, 0.0
        self.lock = asyncio.Lock()

    async def take(self):
        """Wait for the turn of the next request; False when the budget is used up."""
        async with self.lock:
            if self.used >= self.budget:
                return False
            loop = asyncio.get_running_loop()
            wait = self.next - loop.time()
            if wait > 0:
                await asyncio.sleep(wait)
            self.next = loop.time() + self.gap
            self.used += 1
            return True


def retry_delay(err, attempt):
    """Seconds to wait after a failed request: what a per-minute limit asks (retryDelay), else a growing wait."""
    m = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s", err)
    return float(m.group(1)) + 2 if m else 20.0 * (attempt + 1)


async def _make(lang, items, jobs, gemini_jobs=2, batch=20, rpm=8, budget=75):
    """Record items [(key, text, voice)], voice "gemini" or "ms" (the Microsoft voices).  The Gemini sentences go in
    batches of `batch` consecutive sentences, one request each, cut into one recording per sentence
    (voice_gemini.make_batch); a batch whose pauses do not fit is tried again in batches of 4, then one by one.
    The Gemini requests are paced (Pace: rpm, budget); a sentence left when the budget is used up waits for the
    next run."""
    import edge_tts
    d = os.path.join(GV.VOICE_DIR, lang)
    os.makedirs(d, exist_ok=True)
    sem = asyncio.Semaphore(jobs)
    gem = asyncio.Semaphore(gemini_jobs)
    pace = Pace(rpm, budget)
    done, failed, quota = [0], [], []
    total = len(items)

    def tick(n=1):
        before = done[0]
        done[0] += n
        if done[0] // 25 > before // 25 or done[0] == total:
            print("  %s: %d / %d" % (lang, done[0], total), flush=True)

    async def one(key, text):                           # a Microsoft recording
        async with sem:
            out = os.path.join(d, key + ".mp3")
            for attempt in range(3):
                try:
                    if GV.is_mixed(lang, text):                 # English words: said by the English voice
                        await voice_mix.make(text, out)
                    else:
                        await edge_tts.Communicate(text, GV.NEURAL[lang]).save(out + ".part")
                        os.replace(out + ".part", out)
                    break
                except Exception as e:                      # network hiccup: retry
                    if attempt == 2:
                        failed.append((key, str(e)[:200]))
                    await asyncio.sleep(1.5 * (attempt + 1))
            tick()

    async def group(part, size):                        # Gemini sentences, `size` per request
        for i in range(0, len(part), size):
            chunk = part[i:i + size]
            err, bad = None, None
            async with gem:
                for attempt in range(3):
                    if quota or not await pace.take():
                        err = "daily quota" if quota else "left for the next run (--max-requests)"
                        break
                    try:
                        outs = [os.path.join(d, k + ".mp3") for k, _t in chunk]
                        bad = await voice_gemini.make_batch([t for _k, t in chunk], outs)
                        break
                    except voice_gemini.DailyQuota as e:
                        quota.append(str(e))
                        err = "daily quota"
                        break
                    except Exception as e:                  # network hiccup or a per-minute limit: wait, retry
                        err = str(e)[:200]
                        await asyncio.sleep(retry_delay(str(e), attempt))
                if bad is None:                             # no answer: quota, budget, or three failures
                    failed.extend((k, err) for k, _t in chunk)
                    tick(len(chunk))
                    continue
            again = [chunk[j] for j in bad]
            tick(len(chunk) - len(again))
            if again and size > 1:
                await group(again, 4 if size > 4 else 1)
            elif again:
                failed.extend((k, "the pauses did not fit the sentences") for k, _t in again)
                tick(len(again))

    ms = [(k, t) for k, t, v in items if v == "ms"]
    gm = [(k, t) for k, t, v in items if v == "gemini"]
    parts = [gm[i:i + batch * 5] for i in range(0, len(gm), batch * 5)]        # consecutive runs, in parallel
    await asyncio.gather(*(one(k, t) for k, t in ms), *(group(p, batch) for p in parts))
    if quota:
        print("  the daily Gemini quota is used up: run again tomorrow (%s)" % quota[0][:160], flush=True)
    print("  Gemini requests used: %d of %d" % (pace.used, pace.budget), flush=True)
    return failed


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lang", choices=GV.LANGS)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--prune", action="store_true")
    ap.add_argument("--stamp", action="store_true")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--gemini-jobs", type=int, default=2, help="Gemini requests at a time")
    ap.add_argument("--batch", type=int, default=20, help="Gemini sentences per request (the daily limit counts "
                                                          "requests)")
    ap.add_argument("--rpm", type=float, default=8, help="Gemini requests started per minute (the limit is 10)")
    ap.add_argument("--max-requests", type=int, default=75, help="Gemini requests of this run, retries included "
                                                                 "(the daily limit is 100)")
    ap.add_argument("--only", help="record only these parts, by comma: home, lesson1..lesson6, tour, "
                                   "fields-<page> or fields (every field card); --plan lists them")
    ap.add_argument("--plan", action="store_true", help="list the parts: missing sentences and about how many "
                                                        "Gemini requests each takes (no internet)")
    a = ap.parse_args()

    if a.stamp:
        os.makedirs(GV.VOICE_DIR, exist_ok=True)
        with open(SOURCES, "w", encoding="utf-8") as f:
            json.dump(GV.en_sources(), f, ensure_ascii=False, indent=1, sort_keys=True)
        print("stamped %d translations" % len(GV.en_sources()))
        return 0

    rc = 0
    for lang in ([a.lang] if a.lang else GV.LANGS):
        need, have, kept = plan(lang)
        parts = sections(lang)
        if a.plan:
            total = 0
            print("%s:  part                    sentences  missing  Gemini requests" % lang)
            for name, ts in parts:
                n = sum(GV.rec_key(lang, t) not in have for t in ts)
                r = requests_for(n, a.batch) if GV.is_gemini(lang, "x") else 0
                total += r
                print("    %-24s %9d %8d %16d" % (name, len(ts), n, r))
            print("    %-24s %35d" % ("in all", total))
            continue
        order = {}
        for name, ts in parts:
            for t in ts:
                order.setdefault(t, (len(order), name))
        pick = None
        if a.only:
            want = [w.strip() for w in a.only.split(",") if w.strip()]
            names = {name for name, _ts in parts}
            bad = [w for w in want if w not in names and w != "fields"]
            if bad:
                print("unknown parts: %s (py tools/make_guide_voice.py --plan lists them)" % ", ".join(bad))
                return 2
            pick = {n for n in names if n in want or ("fields" in want and n.startswith("fields-"))}
        missing = [(k, t) for k, t in need.items() if k not in have]
        unused = sorted(have - set(need) - kept)
        size = sum(os.path.getsize(os.path.join(GV.VOICE_DIR, lang, k + ".mp3")) for k in have & set(need))
        print("%s: %d sentences, %d recorded (%.1f MB), %d missing (%d of them still play the Microsoft recording), "
              "%d unused" % (lang, len(need), len(have & set(need)), size / 1e6, len(missing), len(kept),
                             len(unused)))
        if a.prune:
            for k in unused:
                os.remove(os.path.join(GV.VOICE_DIR, lang, k + ".mp3"))
            print("  removed %d unused recordings" % len(unused))
        if a.check:
            rc |= bool(missing)
            continue
        if pick is not None:                            # --only: these parts now, the rest in a later run
            missing = [(k, t) for k, t in missing if order.get(t, (0, "other"))[1] in pick]
        # a Hebrew sentence that has no Microsoft recording either gets one, played until its Gemini one is made
        fallback = [(GV.legacy_key(lang, t), t, "ms") for k, t in missing
                    if GV.legacy_key(lang, t) and GV.legacy_key(lang, t) not in have]
        missing.sort(key=lambda kt: order.get(kt[1], (len(order), ""))[0])     # part by part, in guide order
        work = [(k, t, "gemini" if GV.is_gemini(lang, t) else "ms") for k, t in missing] + fallback
        if work:
            failed = asyncio.run(_make(lang, work, a.jobs, a.gemini_jobs, a.batch, a.rpm, a.max_requests))
            for k, e in failed[:10]:
                print("  failed %s: %s" % (k, e))
            if len(failed) > 10:
                print("  ... %d failed in all" % len(failed))
            rc |= bool(failed)
    stale = stale_translations()
    if stale:
        print("English translations whose Hebrew source changed (update guide_voice_en.py, then --stamp):")
        for k in stale:
            print("  " + k)
    return rc


if __name__ == "__main__":
    sys.exit(main())
