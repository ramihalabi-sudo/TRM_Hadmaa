"""The Gemini voice while the guide runs: the sentences built from the user's own project (the value they entered,
the suggestion, weight / cost and sensitivity, the ranges) that no recording made in advance can have.

When the narration reaches sentences without a recording, they are sent to Gemini in one request (one sentence per
line, guide_voice.GEMINI: the model and voice of the recordings), the audio is cut into one WAV per sentence at the
pauses (split) and kept in a cache (%APPDATA%\\TRM4\\voice_cache\\<lang>), so a sentence is asked for once.  Until it
arrives the narrator says it with the Windows voice.  Needs the package google-genai and a Gemini API key (the
environment variable GEMINI_API_KEY, or the file %USERPROFILE%\\.gemini_key); without them, or when the daily quota is
used up, the guide keeps the Windows voice.  tools/voice_gemini.py (the recordings made in advance) uses the same
cutting.
"""
import datetime
import os
import threading
import time
import wave

SR = 24000                                   # Gemini returns 16-bit mono PCM at 24 kHz
KEY_FILE = os.path.join(os.path.expanduser("~"), ".gemini_key")
CACHE = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "TRM4", "voice_cache")
GAP_S = 6.5                                  # s between requests: the limit is 10 a minute
BATCH = 12                                   # sentences per request
RESET_HOUR = 10                              # the daily quota starts again at 10:00 (local time)


def say(said):
    """The text Gemini reads: the name of the program in Hebrew letters, so it is said the same way everywhere."""
    return said.replace("TRM", "טי אר אם")


def api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key and os.path.exists(KEY_FILE):
        try:
            with open(KEY_FILE, encoding="utf-8-sig") as f:
                key = f.read().strip()
        except OSError:
            key = ""
    return key


# ------------------------------------------------------------------------------------------------- cutting
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
    import numpy as np
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
    import numpy as np
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


def write_wav(x, out):
    """int16 samples -> out (WAV, 24 kHz mono) with a short tail of silence, written whole or not at all."""
    import numpy as np
    x = np.concatenate([np.asarray(x, dtype=np.int16), np.zeros(int(0.25 * SR), np.int16)])
    with wave.open(out + ".part", "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(x.tobytes())
    os.replace(out + ".part", out)


# ------------------------------------------------------------------------------------------------- the service
class DailyQuota(RuntimeError):
    """The daily request limit of the model is used up: no point asking again before it starts again."""


def cached(lang, key):
    """Path of the live recording of a sentence (its guide_voice.rec_key), or None."""
    p = os.path.join(CACHE, lang, key + ".wav")
    return p if os.path.exists(p) else None


class Live:
    """Asks Gemini for the sentences that have no recording, one request at a time, in a worker thread."""

    def __init__(self, voice, model, lang="he", pcm=None):
        self.voice, self.model, self.lang = voice, model, lang
        self._pcm_fn = pcm                      # tests: a stand-in for the request
        self._lock = threading.Lock()
        self._queue = []                        # [(key, text)] waiting
        self._pending = set()                   # keys asked for and not done
        self._thread = None
        self._last = 0.0
        self._client = None
        self.off = None                         # why the live voice is off (None: on)

    # ---- state
    def _quota_file(self):
        return os.path.join(CACHE, "quota_used_up.txt")

    def _quota_over(self):
        """The daily quota was used up and has not started again yet."""
        try:
            with open(self._quota_file(), encoding="utf-8") as f:
                when = datetime.datetime.fromisoformat(f.read().strip())
        except (OSError, ValueError):
            return False
        reset = when.replace(hour=RESET_HOUR, minute=0, second=0, microsecond=0)
        if when >= reset:
            reset += datetime.timedelta(days=1)
        return datetime.datetime.now() < reset

    def available(self, lang):
        """Can sentences of `lang` be asked for now."""
        if lang != self.lang or self.off:
            return False
        if self._pcm_fn is not None:
            return True
        if not api_key():
            return False
        try:
            import google.genai  # noqa: F401
            import numpy  # noqa: F401
        except ImportError:
            return False
        return not self._quota_over()

    def pending(self, key):
        with self._lock:
            return key in self._pending

    # ---- requests
    def request(self, items):
        """Ask for [(key, text)] (sentences as said) that are neither cached nor already asked for."""
        with self._lock:
            new = [(k, t) for k, t in items if k not in self._pending and not cached(self.lang, k)]
            for k, _t in new:
                self._pending.add(k)
            self._queue += new
            if new and (self._thread is None or not self._thread.is_alive()):
                self._thread = threading.Thread(target=self._work, daemon=True)
                self._thread.start()

    def _work(self):
        while True:
            with self._lock:
                if not self._queue:
                    return
                batch, self._queue = self._queue[:BATCH], self._queue[BATCH:]
            try:
                self._record(batch)
            except DailyQuota:
                self.off = "daily quota"
                try:
                    os.makedirs(CACHE, exist_ok=True)
                    with open(self._quota_file(), "w", encoding="utf-8") as f:
                        f.write(datetime.datetime.now().isoformat(timespec="seconds"))
                except OSError:
                    pass
                with self._lock:
                    self._queue = []
                    self._pending.clear()
                return
            except Exception:                   # no network, a refused request: these stay with the Windows voice
                pass
            with self._lock:
                for k, _t in batch:
                    self._pending.discard(k)

    def _record(self, batch):
        """One request for the batch, cut into a WAV per sentence; a batch whose pauses do not fit is asked again in
        groups of 4, then one by one."""
        import numpy as np
        texts = [t for _k, t in batch]
        x = np.frombuffer(self._pcm(texts), dtype=np.int16)
        pieces = split(x, texts)
        if pieces is None:
            if len(batch) > 1:
                size = 4 if len(batch) > 4 else 1
                for i in range(0, len(batch), size):
                    self._record(batch[i:i + size])
            return
        folder = os.path.join(CACHE, self.lang)
        os.makedirs(folder, exist_ok=True)
        pad = int(0.05 * SR)
        for (s, t), (k, _text) in zip(pieces, batch):
            write_wav(x[max(0, int(s * SR) - pad): int(t * SR) + pad], os.path.join(folder, k + ".wav"))

    def _pcm(self, texts):
        """Gemini audio (16-bit PCM bytes) of the sentences read one after the other; at most one request every
        GAP_S seconds."""
        wait = self._last + GAP_S - time.time()
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()
        if self._pcm_fn is not None:
            return self._pcm_fn(texts)
        from google import genai
        from google.genai import types
        if self._client is None:
            self._client = genai.Client(api_key=api_key())
        try:
            r = self._client.models.generate_content(
                model=self.model, contents="\n".join(say(t) for t in texts),
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice)))))
        except Exception as e:
            if "per_day" in str(e) or "PerDay" in str(e):
                raise DailyQuota(str(e)[:300]) from e
            raise
        data = r.candidates[0].content.parts[0].inline_data.data
        if not data:
            raise RuntimeError("Gemini returned no audio")
        return data
