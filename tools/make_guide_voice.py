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
neural voices he-IL-AvriNeural and en-US-AndrewNeural.  The application itself never needs it.
"""
import argparse
import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from trm4 import guide_voice as GV  # noqa: E402

SOURCES = os.path.join(GV.VOICE_DIR, "en_sources.json")


def plan(lang):
    """(needed {hash: text}, existing {hash})."""
    need = {GV.rec_key(lang, t): t for t in GV.static_texts(lang)}
    d = os.path.join(GV.VOICE_DIR, lang)
    have = {f[:-4] for f in os.listdir(d) if f.endswith(".mp3")} if os.path.isdir(d) else set()
    return need, have


def stale_translations():
    """Keys whose Hebrew source changed since --stamp (or that were never stamped)."""
    try:
        with open(SOURCES, encoding="utf-8") as f:
            stamped = json.load(f)
    except (OSError, ValueError):
        stamped = {}
    now = GV.en_sources()
    return sorted(k for k, h in now.items() if stamped.get(k) != h)


async def _make(lang, items, jobs):
    import edge_tts
    d = os.path.join(GV.VOICE_DIR, lang)
    os.makedirs(d, exist_ok=True)
    sem = asyncio.Semaphore(jobs)
    done, failed = [0], []

    async def one(key, text):
        async with sem:
            out = os.path.join(d, key + ".mp3")
            for attempt in range(3):
                try:
                    await edge_tts.Communicate(text, GV.NEURAL[lang]).save(out + ".part")
                    os.replace(out + ".part", out)
                    break
                except Exception as e:                      # network hiccup: retry
                    if attempt == 2:
                        failed.append((key, str(e)))
                    await asyncio.sleep(1.5 * (attempt + 1))
            done[0] += 1
            if done[0] % 50 == 0 or done[0] == len(items):
                print("  %s: %d / %d" % (lang, done[0], len(items)), flush=True)

    await asyncio.gather(*(one(k, t) for k, t in items))
    return failed


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lang", choices=GV.LANGS)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--prune", action="store_true")
    ap.add_argument("--stamp", action="store_true")
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()

    if a.stamp:
        os.makedirs(GV.VOICE_DIR, exist_ok=True)
        with open(SOURCES, "w", encoding="utf-8") as f:
            json.dump(GV.en_sources(), f, ensure_ascii=False, indent=1, sort_keys=True)
        print("stamped %d translations" % len(GV.en_sources()))
        return 0

    rc = 0
    for lang in ([a.lang] if a.lang else GV.LANGS):
        need, have = plan(lang)
        missing = [(k, t) for k, t in need.items() if k not in have]
        unused = sorted(have - set(need))
        size = sum(os.path.getsize(os.path.join(GV.VOICE_DIR, lang, k + ".mp3")) for k in have & set(need))
        print("%s: %d sentences, %d recorded (%.1f MB), %d missing, %d unused" % (
            lang, len(need), len(have & set(need)), size / 1e6, len(missing), len(unused)))
        if a.prune:
            for k in unused:
                os.remove(os.path.join(GV.VOICE_DIR, lang, k + ".mp3"))
            print("  removed %d unused recordings" % len(unused))
        if a.check:
            rc |= bool(missing)
            continue
        if missing:
            failed = asyncio.run(_make(lang, missing, a.jobs))
            for k, e in failed[:10]:
                print("  failed %s: %s" % (k, e))
            rc |= bool(failed)
    stale = stale_translations()
    if stale:
        print("English translations whose Hebrew source changed (update guide_voice_en.py, then --stamp):")
        for k in stale:
            print("  " + k)
    return rc


if __name__ == "__main__":
    sys.exit(main())
