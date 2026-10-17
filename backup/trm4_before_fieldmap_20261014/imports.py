"""Import contracts for external data (Section 06 of the application change roadmap).

Every parser returns the data together with what was assumed about it (units, column meaning) so
that the model and the report can state it, and raises ValueError with a clear message when the
file does not fulfil the contract.  Zemax OpticStudio MTF / transmission exports are handled in
zemax.py; this module covers

* spectral atmospheric transmission (wavelength x range, e.g. from MODTRAN),
* spectral path radiance,
* measured line-of-sight jitter time series,
* measured performance curves (MTDP / MRTD / MCP) and measured MTF / SFR curves.
"""
import hashlib
import re

import numpy as np

from .zemax import _tables


def file_hash(text):
    """Short SHA-256 of an imported file's text (recorded in the report for traceability)."""
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:16]


def _header_numbers(ctx, ncol):
    """Numbers in the header cells after the first one (e.g. path lengths), or None."""
    line = next((l for l in reversed(ctx) if l.strip()), "")
    header = [c.strip('"') for c in re.split(r"[,;\t ]+", line.strip()) if c.strip('"')]
    if len(header) != ncol:
        return None
    out = []
    for cell in header[1:]:
        m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", cell)
        if not m:
            return None
        out.append(float(m.group(0)))
    return out


def _largest_table(text):
    best = None
    for ctx, header, data in _tables(text):
        if data.shape[1] >= 2 and (best is None or len(data) > len(best[2])):
            best = (ctx, header, data)
    return best


def _wavelengths(col, notes):
    lam = np.asarray(col, float)
    if lam.max() > 100.0:
        notes.append("wavelength in nm converted to um")
        return lam / 1000.0
    if lam.max() > 30.0 and lam.min() > 300:          # pragma: no cover - wavenumber files
        raise ValueError("Wavelength column looks like wavenumbers (cm-1); export wavelength in um or nm.")
    return lam


# ---------------------------------------------------------------------------------------------
# Spectral atmospheric transmission / path radiance
# ---------------------------------------------------------------------------------------------
def parse_spectral_atmosphere(text, L_ref_km):
    """Wavelength- (and optionally range-) dependent atmospheric transmission.

    Two layouts are accepted:
      * two columns  'wavelength  transmission'  for one path length L_ref_km
        (the range dependence then follows Beer-Lambert per wavelength), or
      * 'wavelength  tau(R1)  tau(R2) ...' with the path lengths R1, R2 ... [km] in the header row.
    Returns dict(lam [um], R [km] array, tau [len(lam) x len(R)], notes).
    """
    best = _largest_table(text)
    if best is None:
        raise ValueError("No 'wavelength transmission' table found in the file.")
    ctx, _header, data = best
    data = data[np.argsort(data[:, 0])]
    notes = []
    lam = _wavelengths(data[:, 0], notes)
    vals = data[:, 1:]
    ranges = _header_numbers(ctx, data.shape[1])
    if data.shape[1] > 2 and ranges:
        R = np.asarray(ranges, float)
        notes.append("%d path lengths from header (%.3g - %.3g km)" % (len(R), R.min(), R.max()))
    else:
        if L_ref_km <= 0:
            raise ValueError("Path length of the transmission data must be > 0 km.")
        R = np.array([float(L_ref_km)])
        vals = vals[:, :1]
        notes.append("single path length %.3g km, Beer-Lambert scaling per wavelength" % L_ref_km)
    if vals.max() > 1.5:
        vals = vals / 100.0
        notes.append("transmission in % converted to fraction")
    if vals.max() > 1.0 + 1e-6 or vals.min() < -1e-6:
        raise ValueError("Atmospheric transmission outside [0, 1] (max %.3g)." % vals.max())
    if np.any(np.diff(lam) <= 0):
        keep = np.concatenate([[True], np.diff(lam) > 0])
        lam, vals = lam[keep], vals[keep]
    order = np.argsort(R)
    return {"lam": lam, "R": R[order], "tau": np.clip(vals[:, order], 0.0, 1.0), "notes": notes}


def parse_path_radiance(text, L_ref_km):
    """Spectral path radiance [W/(m^2 sr um)] (same layouts as parse_spectral_atmosphere)."""
    best = _largest_table(text)
    if best is None:
        raise ValueError("No 'wavelength path-radiance' table found in the file.")
    ctx, _header, data = best
    data = data[np.argsort(data[:, 0])]
    notes = []
    lam = _wavelengths(data[:, 0], notes)
    vals = data[:, 1:]
    ranges = _header_numbers(ctx, data.shape[1])
    if data.shape[1] > 2 and ranges:
        R = np.asarray(ranges, float)
    else:
        if L_ref_km <= 0:
            raise ValueError("Path length of the path radiance data must be > 0 km.")
        R = np.array([float(L_ref_km)])
        vals = vals[:, :1]
    if vals.min() < 0:
        raise ValueError("Negative path radiance in the file.")
    order = np.argsort(R)
    notes.append("unit assumed W/(m^2 sr um)")
    return {"lam": lam, "R": R[order], "L": vals[:, order], "notes": notes}


def atmosphere_summary(text, L_ref_km=1.0):
    a = parse_spectral_atmosphere(text, L_ref_km)
    return "%d wavelengths %.3g - %.3g um, %d range(s); mean tau %.3f (%s)" % (
        len(a["lam"]), a["lam"][0], a["lam"][-1], len(a["R"]), float(a["tau"].mean()), "; ".join(a["notes"]))


def path_summary(text, L_ref_km=1.0):
    a = parse_path_radiance(text, L_ref_km)
    return "%d wavelengths %.3g - %.3g um, %d range(s), max %.3g W/(m2 sr um)" % (
        len(a["lam"]), a["lam"][0], a["lam"][-1], len(a["R"]), float(a["L"].max()))


# ---------------------------------------------------------------------------------------------
# Line-of-sight jitter
# ---------------------------------------------------------------------------------------------
def parse_jitter(text, rate_hz=0.0):
    """Measured image motion: 't[s] h v' (3 columns) or 'h v' with a given sample rate.

    h = horizontal (azimuth) axis, v = vertical (elevation) axis, in the unit chosen in the
    project (urad, mrad or pixels).  Returns dict(t [s], h, v, rate [Hz], notes).
    """
    best = _largest_table(text)
    if best is None:
        raise ValueError("No jitter time series found (columns 't h v' or 'h v').")
    _ctx, _header, data = best
    notes = []
    if data.shape[1] >= 3:
        t, h, v = data[:, 0], data[:, 1], data[:, 2]
        if np.any(np.diff(t) <= 0):
            raise ValueError("Time column of the jitter file must increase monotonically.")
        dt = np.diff(t)
        rate = 1.0 / float(np.median(dt))
        if dt.max() > 1.5 * dt.min():
            notes.append("non-uniform sampling (median rate used)")
        notes.append("time column present")
    else:
        if rate_hz <= 0:
            raise ValueError("The jitter file has no time column - enter the sample rate.")
        h, v = data[:, 0], data[:, 1]
        rate = float(rate_hz)
        t = np.arange(len(h)) / rate
    if len(t) < 16:
        raise ValueError("Jitter time series too short (%d samples)." % len(t))
    return {"t": np.asarray(t, float), "h": np.asarray(h, float), "v": np.asarray(v, float), "rate": rate,
            "notes": notes}


def jitter_summary(text, rate_hz=0.0):
    j = parse_jitter(text, rate_hz)
    return "%d samples, %.4g Hz, %.3g s; rms h/v %.3g / %.3g (file units)" % (
        len(j["t"]), j["rate"], j["t"][-1] - j["t"][0], np.std(j["h"]), np.std(j["v"]))


def jitter_mtf(x_mrad, rate, t_int, r):
    """MTF of measured motion x(t) [mrad] for integration time t_int [s] at frequencies r [1/mrad].

    The record is cut into integration windows.  Motion inside a window blurs the frame
    (intra-frame MTF = |mean of the window OTFs|); the window means are what moves from frame to
    frame (returned as rms after removing offset and linear drift).
    Returns (mtf_intra(r), sigma_frame [mrad], stats dict).
    """
    x = np.asarray(x_mrad, float)
    n = len(x)
    tt = np.arange(n) / rate
    offset = float(x.mean())
    slope, icpt = np.polyfit(tt, x, 1)
    resid = x - (slope * tt + icpt)
    m = max(1, int(round(t_int * rate)))
    stats = {"offset": offset, "drift": float(slope), "rms": float(np.std(resid)), "samples_per_frame": m}
    if m < 2:
        stats["intra_rms"] = 0.0
        return np.ones_like(np.asarray(r, float)), float(np.std(resid)), stats
    nw = n // m
    win = resid[:nw * m].reshape(nw, m)
    dev = win - win.mean(axis=1, keepdims=True)
    stats["intra_rms"] = float(np.sqrt(np.mean(dev ** 2)))
    r = np.asarray(r, float)
    otf = np.zeros(r.shape, complex)
    step = max(1, 400000 // max(dev.size, 1))
    for i in range(0, len(r), step):
        ph = np.exp(2j * np.pi * r[i:i + step, None, None] * dev[None, :, :])
        otf[i:i + step] = ph.mean(axis=(1, 2))
    sigma_frame = float(np.std(win.mean(axis=1)))
    return np.abs(otf), sigma_frame, stats


# ---------------------------------------------------------------------------------------------
# Measured curves (MTDP / MRTD / MCP, MTF / SFR)
# ---------------------------------------------------------------------------------------------
def parse_curve_hv(text, what="curve"):
    """'frequency value' (h = v) or 'frequency h v' columns; frequency must increase."""
    best = _largest_table(text)
    if best is None:
        raise ValueError("No numeric '%s' table found (frequency + value columns)." % what)
    _ctx, _header, data = best
    data = data[np.argsort(data[:, 0])]
    f = data[:, 0]
    if f[0] < 0 or np.any(np.diff(f) <= 0):
        raise ValueError("Frequency column of the %s must be positive and increasing." % what)
    h = data[:, 1]
    v = data[:, 2] if data.shape[1] >= 3 else data[:, 1]
    notes = ["h and v columns" if data.shape[1] >= 3 else "one column used for h and v"]
    return {"f": f, "h": h, "v": v, "notes": notes}


def curve_summary(text):
    c = parse_curve_hv(text)
    return "%d points, frequency %.3g - %.3g (%s)" % (len(c["f"]), c["f"][0], c["f"][-1], c["notes"][0])


def to_cycles_per_mrad(f, unit, f_mm, alpha_s_mrad):
    """Convert a frequency axis to object-space cycles/mrad."""
    if unit == "mrad":
        return np.asarray(f, float)
    if unit == "mm":                       # image space cycles/mm
        return np.asarray(f, float) * f_mm / 1000.0
    if unit == "pixel":                    # cycles/pixel (ISO 12233 SFR)
        return np.asarray(f, float) / alpha_s_mrad
    raise ValueError("Unknown frequency unit %r" % unit)
