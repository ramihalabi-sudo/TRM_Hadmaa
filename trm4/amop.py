"""Average Modulation at Optimum Phase (AMOP), Sections 3.11.3 and 4.1.7.

AMOP cannot be calculated analytically.  As in TRM, the imaging of the standard 4-bar pattern
(7 bars of width w = 1/(2 r_p)) is simulated in one dimension:

    bar pattern --(prefilter MTF)--> sampling at phase phi --(postfilter MTF incl. eye)--> image

For each phase the average modulation between adjacent (apparent) maxima and minima of the
reproduced pattern is determined; AMOP is the maximum over all phases (optimum phase).
"""
import heapq
import math

import numpy as np


def _remove_wiggles_direct(seq, rel_threshold, abs_threshold):
    """Reference: repeatedly merge the smallest adjacent difference while it is below rel_threshold x the largest
    one (O(n^2) - very slow for spiky signals, e.g. an ideal observer MTF)."""
    seq = [list(e) for e in seq]
    while len(seq) >= 2:
        diffs = np.abs(np.diff([v for v, _ in seq]))
        thr = max(rel_threshold * diffs.max(), abs_threshold)
        i = int(np.argmin(diffs))
        if diffs[i] >= thr:
            break
        if i == 0:
            seq.pop(0)
        elif i + 1 == len(seq) - 1:
            seq.pop()
        else:
            a_prev, a_next = seq[i - 1], seq[i + 2]
            if a_prev[1] > 0:
                a_prev[0] = max(a_prev[0], seq[i + 1][0])
                a_next[0] = min(a_next[0], seq[i][0])
            else:
                a_prev[0] = min(a_prev[0], seq[i + 1][0])
                a_next[0] = max(a_next[0], seq[i][0])
            del seq[i:i + 2]
    return seq


def _remove_wiggles(seq, rel_threshold, abs_threshold):
    """Same merges in the same order as _remove_wiggles_direct, in O(n log n) (finite values).

    The sequence is a linked list; the adjacent differences live in a min-heap keyed (difference, left element) -
    elements keep their relative order, so ties resolve like np.argmin - and the largest one in a max-heap.  A merge
    only changes the differences next to it; outdated heap entries are skipped by a version number."""
    n = len(seq)
    val = [float(v) for v, _ in seq]
    typ = [t for _, t in seq]
    prv = list(range(-1, n - 1))
    nxt = list(range(1, n + 1))
    nxt[-1] = -1
    alive, ver = [True] * n, [0] * n
    push, pop = heapq.heappush, heapq.heappop
    lo = [(abs(val[i + 1] - val[i]), i, 0) for i in range(n - 1)]
    hi = [(-d, i, v) for d, i, v in lo]
    heapq.heapify(lo)
    heapq.heapify(hi)

    def update(i):                          # (re)publish the difference between i and its successor
        ver[i] += 1
        j = nxt[i]
        if j >= 0:
            d = abs(val[j] - val[i])
            push(lo, (d, i, ver[i]))
            push(hi, (-d, i, ver[i]))

    head, tail, count = 0, n - 1, n
    while count >= 2:
        while True:                         # smallest valid difference
            dmin, i, v = lo[0]
            if alive[i] and v == ver[i] and nxt[i] >= 0:
                break
            pop(lo)
        while True:                         # largest valid difference
            dmax, k, v = hi[0]
            if alive[k] and v == ver[k] and nxt[k] >= 0:
                break
            pop(hi)
        if dmin >= max(rel_threshold * -dmax, abs_threshold):
            break
        if i == head:                       # seq.pop(0)
            alive[i] = False
            head = nxt[i]
            prv[head] = -1
            count -= 1
        elif nxt[i] == tail:                # seq.pop()
            alive[tail] = False
            tail = i
            nxt[i] = -1
            ver[i] += 1
            count -= 1
        else:                               # merge the pair (i, j) into its neighbours a and b
            j = nxt[i]
            a, b = prv[i], nxt[j]
            if typ[a] > 0:
                val[a] = max(val[a], val[j])
                val[b] = min(val[b], val[i])
            else:
                val[a] = min(val[a], val[j])
                val[b] = max(val[b], val[i])
            alive[i] = alive[j] = False
            nxt[a], prv[b] = b, a
            count -= 2
            if prv[a] >= 0:
                update(prv[a])
            update(a)
            update(b)
    out, k = [], head
    while k >= 0:
        out.append([val[k], typ[k]])
        k = nxt[k]
    return out


def _extrema_modulation(y, rel_threshold=0.1, abs_threshold=1e-6):
    """Average difference between adjacent maxima/minima of y (zig-zag with hysteresis)."""
    d = np.diff(y)
    s = np.sign(d)
    # forward-fill zero slopes so that plateaus do not create spurious turning points
    nz = np.nonzero(s)[0]
    if nz.size == 0:
        return 0.0
    idx = np.maximum.accumulate(np.where(s != 0, np.arange(s.size), 0))
    s = s[idx]
    s[: nz[0]] = s[nz[0]]
    turn = np.nonzero(s[:-1] != s[1:])[0] + 1
    if turn.size == 0:
        return 0.0
    vals = y[turn]
    types = np.where(s[turn - 1] > 0, 1, -1)                            # +1 max, -1 min
    # linear-time hysteresis pass: discard wiggles below 1e-4 of the signal range
    delta = max(1e-4 * float(np.ptp(y)), abs_threshold * 0.1)
    seq = []
    for v, t in zip(vals.tolist(), types.tolist()):
        if not seq:
            seq.append([v, t])
            continue
        last = seq[-1]
        if last[1] == t:
            if (t > 0 and v > last[0]) or (t < 0 and v < last[0]):
                last[0] = v
        elif abs(v - last[0]) >= delta:
            seq.append([v, t])
        elif len(seq) >= 2:
            # small counter-move: ignore it (the running extreme is kept)
            pass
    if all(math.isfinite(v) for v, _ in seq):
        seq = _remove_wiggles(seq, rel_threshold, abs_threshold)
    else:
        seq = _remove_wiggles_direct(seq, rel_threshold, abs_threshold)
    while seq and seq[0][1] < 0:
        seq.pop(0)
    while seq and seq[-1][1] < 0:
        seq.pop()
    n_max = sum(1 for _, t in seq if t > 0)
    if n_max < 2:
        return 0.0
    return float(np.mean(np.abs(np.diff([v for v, _ in seq]))))


def amop(pre, post, alpha_s, rp, sampled=True, n_phase=8, psf_margin=0.0, max_n=2 ** 17):
    """AMOP of the 4-bar pattern with spatial frequency rp [1/mrad] in one direction.

    pre, post  callables returning the (signed) pre-/postfilter MTF for frequencies r >= 0
    alpha_s    sampling distance [mrad]
    psf_margin additional margin [mrad] to accommodate wide prefilter point spread functions
    """
    w = 0.5 / rp
    M = int(max(8, np.ceil(10.0 * alpha_s / w)))
    L_pat = 7.0 * w
    margin = max(24.0 * alpha_s, 4.0 * w, psf_margin)
    while True:
        dx = alpha_s / M
        n = int(2 ** np.ceil(np.log2((L_pat + 2 * margin) / dx)))
        if n <= max_n or M <= 4:
            break
        M //= 2
    n = min(n, max_n * 2)
    dx = alpha_s / M
    x = (np.arange(n) + 0.5) * dx
    x0 = 0.5 * (n * dx - L_pat)
    f = np.zeros(n)
    lo = x - 0.5 * dx
    hi = x + 0.5 * dx
    for k in (0, 2, 4, 6):
        b0, b1 = x0 + k * w, x0 + (k + 1) * w
        f += np.clip(np.minimum(hi, b1) - np.maximum(lo, b0), 0.0, None) / dx
    fr = np.fft.rfftfreq(n, dx)
    h_pre = pre(fr)
    h_post = post(fr)
    g = np.fft.irfft(np.fft.rfft(f) * h_pre, n)
    i0 = int(np.floor((x0 - 0.5 * w) / dx))
    i1 = int(np.ceil((x0 + L_pat + 0.5 * w) / dx))
    if not sampled:
        out = np.fft.irfft(np.fft.rfft(g) * h_post, n)
        return _extrema_modulation(out[i0:i1])
    best = 0.0
    step = max(1, M // n_phase)
    for ph in range(0, M, step):
        s = np.zeros(n)
        s[ph::M] = g[ph::M] * M
        out = np.fft.irfft(np.fft.rfft(s) * h_post, n)
        best = max(best, _extrema_modulation(out[i0:i1]))
    return best
