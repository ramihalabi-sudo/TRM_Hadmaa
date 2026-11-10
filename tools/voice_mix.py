"""Mixed-language recordings: a Hebrew sentence whose English words are said by an English voice.

edge-tts takes one voice per request (custom SSML is blocked by the service), so a sentence is cut into Hebrew and
English runs (guide_voice.voice_parts), each run is recorded by its own voice, the silence at both ends of every run
is cut, and the runs are joined with a short pause where the text has a comma or a stop.  The English voice
(guide_voice.MIX_EN) is tuned to sound like the Hebrew narrator, he-IL-AvriNeural: lowered to his pitch (about
101 Hz), its treble softened to his darker tone, and its loudness matched to the Hebrew runs.  It was chosen by
measuring the median pitch, pitch range, spectral centroid and spectral tilt of every English male voice against
Avri (closest: Eric, Christopher), then by ear.

Needs ffmpeg and numpy (making recordings only; the application plays the finished mp3).
"""
import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trm4 import guide_voice as GV  # noqa: E402

SR = 24000


def _decode(mp3, raw, extra=None):
    f = ("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
         "silenceremove=start_periods=1:start_threshold=-45dB,areverse")
    if extra:
        f += "," + extra
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", mp3, "-af", f, "-ar", str(SR), "-ac", "1",
                    "-f", "s16le", raw], check=True)
    return np.frombuffer(open(raw, "rb").read(), dtype=np.int16).astype(np.float32)


def _gap(text):
    t = text.rstrip()
    if t.endswith((".", "!", "?")):
        return 0.40
    if t.endswith((",", ";", ":")):
        return 0.26
    return 0.06


async def make(said, out, he_voice=None, mix=None):
    """Record the spoken Hebrew sentence `said` (guide_voice.speech) into `out` (mp3)."""
    import edge_tts
    he_voice = he_voice or GV.NEURAL["he"]
    mix = dict(GV.MIX_EN, **(mix or {}))
    segs = GV.voice_parts(said)
    with tempfile.TemporaryDirectory() as tmp:
        pcm, he_rms = [], []
        for i, (lang, t) in enumerate(segs):
            mp3 = os.path.join(tmp, "p%d.mp3" % i)
            say = t.strip(" ,;:-")
            if lang == "he":
                await edge_tts.Communicate(say, he_voice).save(mp3)
            else:
                await edge_tts.Communicate(say, mix["voice"], pitch=mix["pitch"]).save(mp3)
            x = _decode(mp3, os.path.join(tmp, "p%d.raw" % i), mix["tone"] if lang == "en" else None)
            rms = float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0
            if lang == "he" and rms:
                he_rms.append(rms)
            pcm.append((lang, x, rms, _gap(t)))
        ref = float(np.median(he_rms)) if he_rms else None
        chunks = []
        for k, (lang, x, rms, gap) in enumerate(pcm):
            if lang == "en" and ref and rms:
                x = x * min(ref / rms, 2.0)                       # the English runs as loud as the Hebrew
            chunks.append(x)
            if k < len(pcm) - 1:
                chunks.append(np.zeros(int(SR * gap), np.float32))
        y = np.clip(np.concatenate(chunks), -32768, 32767).astype(np.int16)
        raw = os.path.join(tmp, "all.raw")
        y.tofile(raw)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", raw,
                        "-af", "apad=pad_dur=0.25", "-c:a", "libmp3lame", "-b:a", "48k", "-f", "mp3", out + ".part"],
                       check=True)
        os.replace(out + ".part", out)
