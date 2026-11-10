"""Recording of a sentence by the Gemini voice (guide_voice.GEMINI): every Hebrew sentence of the guide.

Needs the package google-genai, ffmpeg, and a Gemini API key (Google AI Studio): the environment variable
GEMINI_API_KEY, or the file %USERPROFILE%\\.gemini_key.  Making recordings only; the application plays the mp3.
"""
import asyncio
import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trm4 import guide_voice as GV  # noqa: E402

SR = 24000                                   # Gemini returns 16-bit mono PCM at 24 kHz
KEY_FILE = os.path.join(os.path.expanduser("~"), ".gemini_key")
_client = None


def api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key and os.path.exists(KEY_FILE):
        with open(KEY_FILE, encoding="utf-8-sig") as f:
            key = f.read().strip()
    if not key:
        raise RuntimeError("no Gemini API key: set GEMINI_API_KEY or write it to %s" % KEY_FILE)
    return key


def client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=api_key())
    return _client


def say(said):
    """The text Gemini reads: the name of the program in Hebrew letters, so it is said the same way everywhere."""
    return said.replace("TRM", "טי אר אם")


class DailyQuota(RuntimeError):
    """The daily request limit of the model is used up: no point retrying today."""


def _pcm(said, model=None):
    """Gemini audio (16-bit PCM bytes) of one sentence, or of a list of sentences read one after the other (one per
    line).  The model gets the text only: an instruction in the text is read aloud."""
    from google.genai import types
    text = "\n".join(say(t) for t in said) if isinstance(said, (list, tuple)) else say(said)
    try:
        r = client().models.generate_content(
            model=model or GV.GEMINI["model"], contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=GV.GEMINI["voice"])))))
    except Exception as e:
        if "per_day" in str(e) or "PerDay" in str(e):
            raise DailyQuota(str(e)[:300]) from e
        raise
    data = r.candidates[0].content.parts[0].inline_data.data
    if not data:
        raise RuntimeError("Gemini returned no audio")
    return data


def _write_mp3(x, out):
    """int16 samples -> out (mp3): silence trimmed, a short tail, as the other recordings."""
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "s.raw")
        np.asarray(x, dtype=np.int16).tofile(raw)
        trim = ("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                "silenceremove=start_periods=1:start_threshold=-45dB,areverse,apad=pad_dur=0.25")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", raw,
                        "-af", trim, "-c:a", "libmp3lame", "-b:a", "48k", "-f", "mp3", out + ".part"], check=True)
    os.replace(out + ".part", out)


def _keep(out, said):
    """Check a new recording (check); one that does not say its sentence is deleted.  Returns kept."""
    ok, heard = check(out, said)
    if not ok:
        os.remove(out)
        print("  rejected (%s): heard %r" % (os.path.basename(out), heard[:70]), flush=True)
    return ok


async def make(said, out):
    """Record the spoken sentence `said` into `out` (mp3), if it passes check."""
    data = await asyncio.to_thread(_pcm, said)
    _write_mp3(np.frombuffer(data, dtype=np.int16), out)
    if not await asyncio.to_thread(_keep, out, said):
        raise RuntimeError("the recording did not say the sentence")


# ------------------------------------------------------------------------------------------------- checking
CHECK_MODEL = "gemini-3.8-flash"            # a text model (its own quota) that listens to every new recording
LEAK = ("קרא בעברית", "בקול חם", "בקצב רגוע", "שמסביר לתלמידים", "לפי הסדר", "הפסקה של שנייה")


def check(mp3, said):
    """(ok, what was heard): does the recording say the sentence, and only it?  The voice model sometimes reads
    its instruction aloud, or says something else; such a recording is not kept."""
    from google.genai import types
    ask = ("Listen to this Hebrew audio. The intended sentence is:\n%s\n\nFirst line: YES if the audio says this "
           "sentence (small differences of pronunciation or of how numbers and English words are read are fine) and "
           "nothing else before or after it, otherwise NO. Second line: a transcript of what the audio says."
           % say(said))
    for attempt in range(3):
        try:
            r = client().models.generate_content(model=CHECK_MODEL, contents=[
                types.Part.from_bytes(data=open(mp3, "rb").read(), mime_type="audio/mp3"), ask])
            text = (r.text or "").strip()
            break
        except Exception as e:                          # a hiccup of the checking model: one more try
            text = ""
            if attempt == 2:
                return True, "not checked: %s" % str(e)[:80]
    first, _, heard = text.partition("\n")
    if not first:
        return True, "not checked: empty answer"
    leak = any(w in heard for w in LEAK)
    return first.strip().upper().startswith("YES") and not leak, heard.strip()


# ------------------------------------------------------------------------------------------------- batches
FRAME = 0.01                    # s, frame of the silence detection
MIN_GAP = 0.15                  # s, shortest pause that may end a sentence
RATIO = (0.6, 1.7)              # a sentence may last 0.6-1.7 times its share of the batch (by letters)


def _weight(text):
    """How long a sentence takes to say, in letters (spaces and punctuation are short)."""
    t = say(text)
    return sum(1 for c in t if c.isalnum()) + 2 * sum(1 for c in t if c in ",;:") + 3


def _gaps(x):
    """Pauses in the audio: [(start s, end s)] of every run of silence of at least MIN_GAP, and (begin, end) of the
    speech."""
    n = int(SR * FRAME)
    f = x[: len(x) // n * n].astype(np.float32).reshape(-1, n)
    db = 20 * np.log10(np.sqrt(np.mean(f ** 2, axis=1)) / 32768 + 1e-9)
    loud = db > max(-45.0, float(np.percentile(db, 98)) - 40)
    idx = np.flatnonzero(loud)
    if not len(idx):
        return [], (0.0, 0.0)
    b, e = idx[0], idx[-1] + 1
    gaps, run = [], None
    for i in range(b, e):
        if not loud[i]:
            run = i if run is None else run
        elif run is not None:
            if (i - run) * FRAME >= MIN_GAP:
                gaps.append((run * FRAME, i * FRAME))
            run = None
    return gaps, (b * FRAME, e * FRAME)


def split(x, texts):
    """Cut the audio of a batch into one piece per sentence: [(start s, end s)], or None when the pauses do not fit
    the sentences.  The cuts are chosen among the pauses (dynamic programming) so that every sentence lasts close to
    its share of the batch by letters, preferring long pauses; every piece is then checked against RATIO."""
    n = len(texts)
    gaps, (b, e) = _gaps(x)
    if n == 1:
        return [(b, e)]
    if len(gaps) < n - 1:
        return None
    w = np.array([_weight(t) for t in texts], float)
    pause = sum(g1 - g0 for g0, g1 in sorted(gaps, key=lambda g: g[0] - g[1])[: n - 1])
    rate = (e - b - pause) / w.sum()                                     # s per letter
    exp = w * rate
    starts = [b] + [g1 for _g0, g1 in gaps]
    ends = [g0 for g0, _g1 in gaps] + [e]
    glen = [g1 - g0 for g0, g1 in gaps]
    m = len(gaps)
    INF = float("inf")

    def cost(i, s, t):                                   # sentence i spoken from s to t
        d = t - s
        return INF if d <= 0 else float(np.log(d / exp[i]) ** 2)

    # best[k][j]: sentences 0..k, sentence k ends at gap j (j = m: at the end)
    best = np.full((n, m + 1), INF)
    back = np.zeros((n, m + 1), int)
    for j in range(m):
        best[0][j] = cost(0, b, ends[j]) - 0.5 * min(glen[j], 1.2)
    for k in range(1, n):
        for j in range(k, m + 1):
            if k == n - 1 and j != m or k < n - 1 and j == m:
                continue
            bonus = 0.5 * min(glen[j], 1.2) if j < m else 0.0
            for i in range(k - 1, j):
                if best[k - 1][i] == INF:
                    continue
                c = best[k - 1][i] + cost(k, starts[i + 1], ends[j]) - bonus
                if c < best[k][j]:
                    best[k][j], back[k][j] = c, i
    if best[n - 1][m] == INF:
        return None
    cut, j = [m], m
    for k in range(n - 1, 0, -1):
        j = back[k][j]
        cut.append(j)
    cut = cut[::-1]                                      # gap index that ends each sentence (m = end)
    pieces, s = [], b
    for k, j in enumerate(cut):
        t = ends[j]
        r = (t - s) / exp[k]
        if not RATIO[0] <= r <= RATIO[1]:
            return None
        pieces.append((s, t))
        s = starts[j + 1] if j < m else e
    return pieces


async def make_batch(texts, outs, model=None):
    """Record the sentences `texts` in one request and cut them into `outs` (mp3).  Returns the indices of the
    sentences that could not be cut reliably (all of them when the pauses do not fit) or whose piece does not say
    the sentence (check); those are not kept."""
    data = await asyncio.to_thread(_pcm, list(texts), model)
    x = np.frombuffer(data, dtype=np.int16)
    pieces = split(x, texts)
    if pieces is None:
        return list(range(len(texts)))
    pad = int(0.05 * SR)
    for (s, t), out in zip(pieces, outs):
        _write_mp3(x[max(0, int(s * SR) - pad): int(t * SR) + pad], out)
    kept = await asyncio.gather(*(asyncio.to_thread(_keep, o, t) for o, t in zip(outs, texts)))
    return [i for i, ok in enumerate(kept) if not ok]
