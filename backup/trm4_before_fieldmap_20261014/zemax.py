"""Import of Zemax OpticStudio analysis exports (.csv / .txt).

Two kinds of data are supported:

* MTF data (FFT / Huygens / Geometric MTF "Text" window saved as .txt or .csv).  The file holds
  one or more tables of spatial frequency vs. tangential / sagittal MTF, either one table per
  field ("Field: ..." header above each table) or several T/S column pairs side by side.
* Spectral transmission (e.g. coating / transmission vs. wavelength exports): wavelength in
  um or nm and transmission as fraction or percent.

OpticStudio writes its text exports as UTF-16 with BOM by default; UTF-8 and ANSI files are
accepted as well.
"""
import re

import numpy as np

_SPLIT_CELLS = re.compile(r"\s*[,;\t]\s*|\s{2,}")


def read_text_file(path):
    """Read a text export, detecting the UTF-16 / UTF-8 encodings used by OpticStudio."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace")
    if raw[1:200:2].count(0) > 20:            # UTF-16 LE without BOM
        return raw.decode("utf-16-le", errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _numbers(line):
    """Return the numbers of a pure data line, or None for text lines."""
    s = line.strip()
    if not s:
        return None
    toks = [t for t in re.split(r"[,;\t ]+", s) if t]
    if len(toks) < 2:
        return None
    try:
        return [float(t) for t in toks]
    except ValueError:
        return None


def _tables(text):
    """Split the file into numeric tables: list of (context lines, header cells, data array)."""
    out, ctx, rows = [], [], []

    def flush():
        if len(rows) >= 2:
            n = min(len(r) for r in rows)
            header = []
            for line in reversed(ctx):
                if line.strip():
                    header = [c for c in _SPLIT_CELLS.split(line.strip().strip('"')) if c]
                    header = [c.strip('"').strip() for c in header]
                    break
            out.append((list(ctx), header, np.array([r[:n] for r in rows], float)))

    for line in str(text).splitlines():
        nums = _numbers(line)
        if nums is not None:
            rows.append(nums)
            continue
        if rows:
            flush()
            ctx, rows = [], []
        ctx.append(line)
    if rows:
        flush()
    return out


# ---------------------------------------------------------------------------------------------
# MTF
# ---------------------------------------------------------------------------------------------
def detect_frequency_unit(text):
    """'mrad' when the export states cycles per milliradian (afocal mode), else 'mm'."""
    t = text.lower()
    if re.search(r"(cycles|lp)\s*(per|/)\s*(mr\b|mrad|milliradian)", t):
        return "mrad"
    return "mm"


def _kind(name):
    n = name.lower()
    if "diff" in n:                      # diffraction limit columns are not used
        return None
    if "tan" in n or re.match(r"^t\b", n):
        return "T"
    if "sag" in n or re.match(r"^s\b", n):
        return "S"
    return None


def _strip_kind(name):
    n = re.sub(r"(?i)tangential|sagittal|tan\.?|sag\.?", "", name)
    n = re.sub(r"^[TtSs]\b", "", n.strip())
    return n.strip(" :-_()")


def parse_mtf(text):
    """Parse an OpticStudio MTF export.

    Returns a list of fields, each {"label", "freq", "T", "S"} with frequency in the file's units
    (normally cycles/mm image space) and MTF as a fraction.
    """
    fields = []
    for ctx, header, data in _tables(text):
        ncol = data.shape[1]
        freq = data[:, 0]
        if ncol < 2 or np.any(np.diff(freq) <= 0) or freq[0] < 0:
            continue                                    # not a frequency table
        label = ""
        for line in reversed(ctx):
            if re.search(r"(?i)\bfield\b", line):
                label = re.sub(r"(?i)^\s*field\s*[:#]?\s*", "", line.strip()).strip()
                break
        cols = []
        if len(header) == ncol:
            kinds = [_kind(h) for h in header]
            t_idx = [i for i in range(1, ncol) if kinds[i] == "T"]
            s_idx = [i for i in range(1, ncol) if kinds[i] == "S"]
            if t_idx or s_idx:
                for k in range(max(len(t_idx), len(s_idx))):
                    ti = t_idx[k] if k < len(t_idx) else s_idx[k]
                    si = s_idx[k] if k < len(s_idx) else t_idx[k]
                    sub = _strip_kind(header[ti])
                    cols.append((ti, si, sub))
        if not cols:
            if ncol == 2:
                cols = [(1, 1, "")]
            else:
                cols = [(i, i + 1, "") for i in range(1, ncol - 1, 2)]
        for ti, si, sub in cols:
            T, S = data[:, ti].copy(), data[:, si].copy()
            if max(T.max(), S.max()) > 1.5:            # percent
                T, S = T / 100.0, S / 100.0
            lab = sub if len(cols) > 1 and sub else label
            fields.append({"label": lab or "Field %d" % (len(fields) + 1), "freq": freq.copy(),
                           "T": np.clip(T, 0.0, None), "S": np.clip(S, 0.0, None)})
    if not fields:
        raise ValueError("No MTF table (spatial frequency vs. tangential/sagittal MTF) found in the file.")
    return fields


def mtf_summary(text):
    fields = parse_mtf(text)
    unit = "cycles/mrad" if detect_frequency_unit(text) == "mrad" else "cycles/mm"
    labels = ", ".join("%d: %s" % (i + 1, f["label"]) for i, f in enumerate(fields[:4]))
    if len(fields) > 4:
        labels += ", ..."
    return "%d field(s), %d pts, up to %g %s  [%s]" % (len(fields), len(fields[0]["freq"]),
                                                      fields[0]["freq"][-1], unit, labels)


# ---------------------------------------------------------------------------------------------
# Spectral transmission
# ---------------------------------------------------------------------------------------------
def parse_transmission(text):
    """Parse a wavelength vs. transmission export.

    Returns (wavelength [um], transmission [fraction], description of the column used).
    With several data columns (e.g. S / P polarization or several fields) the column named
    average / mean / total is used if present, otherwise the mean of all data columns.
    """
    best = None
    for _ctx, header, data in _tables(text):
        if data.shape[1] >= 2 and (best is None or len(data) > len(best[1])):
            best = (header, data)
    if best is None:
        raise ValueError("No wavelength / transmission table found in the file.")
    header, data = best
    order = np.argsort(data[:, 0])
    data = data[order]
    lam = data[:, 0]
    if lam.max() > 100.0:                               # nm -> um
        lam = lam / 1000.0
    ncol = data.shape[1]
    note = "column 2"
    if ncol == 2:
        tau = data[:, 1]
    else:
        pick = None
        if len(header) == ncol:
            for i in range(1, ncol):
                if re.search(r"(?i)aver|avg|mean|total|unpol", header[i]):
                    pick = i
                    break
        if pick is not None:
            tau = data[:, pick]
            note = header[pick]
        else:
            tau = data[:, 1:].mean(axis=1)
            note = "mean of %d columns" % (ncol - 1)
    if tau.max() > 1.5:                                 # percent
        tau = tau / 100.0
    keep = np.concatenate([[True], np.diff(lam) > 0])
    lam, tau = lam[keep], tau[keep]
    if len(lam) < 2:
        raise ValueError("Transmission table needs at least two wavelengths.")
    return lam, np.clip(tau, 0.0, 1.0), note


def transmission_summary(text):
    lam, tau, note = parse_transmission(text)
    return "%d pts, %.3g - %.3g um, mean %.3f (%s)" % (len(lam), lam[0], lam[-1], tau.mean(), note)
