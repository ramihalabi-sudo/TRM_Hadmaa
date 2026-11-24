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

from trm4.voice_live import SR  # noqa: E402  (Gemini returns 16-bit mono PCM at 24 kHz)
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


from trm4.voice_live import say  # noqa: E402  (the name of the program in Hebrew letters)


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
# the cutting of a batch into sentences is shared with the live voice of the application
from trm4.voice_live import split  # noqa: E402


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
