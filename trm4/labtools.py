"""Laboratory frame tools: slanted-edge SFR and photon-transfer characterization of a camera.

* Slanted-edge SFR after ISO 12233 (e-SFR): edge location per row by the centroid of the line derivative, straight
  edge fit, 4x oversampled edge spread function along the edge normal, Hamming-windowed line spread function,
  discrete-derivative correction.  Output in cycles/pixel - the unit the measured-MTF import of TRM takes.
* Photon transfer after EMVA 1288 (Release 4.0 Linear): mean and temporal variance from pairs of frames at several
  exposures and a dark pair; conversion gain K from the linear part of the photon-transfer curve, read noise,
  saturation capacity, DSNU, PRNU and dark current, with the TRM detector inputs they correspond to.

Both are verified on synthetic frames with known MTF / gain / noise (synthetic_edge, synthetic_ptc and
tests/test_labtools.py).  Real images still need the measurement conditions recorded (Validation data /
Metadata) - the tools do not know the camera's operating mode, processing state or temperature.
"""
import math

import numpy as np

E_CHARGE = 1.602176634e-19


# ---------------------------------------------------------------------------------------------
# frame input
# ---------------------------------------------------------------------------------------------
def load_frame(path):
    """2-D float frame from .npy, .csv / .txt (numbers) or an image file (PNG / TIFF via matplotlib; colour frames
    are averaged over the channels)."""
    p = str(path).lower()
    if p.endswith(".npy"):
        a = np.load(path, allow_pickle=False)
    elif p.endswith((".csv", ".txt", ".dat")):
        a = np.loadtxt(path, delimiter="," if p.endswith(".csv") else None)
    else:
        import matplotlib.image as mpimg
        a = mpimg.imread(path)
    a = np.asarray(a, float)
    if a.ndim == 3:
        a = a[..., :3].mean(axis=2)
    if a.ndim != 2:
        raise ValueError("%s: not a 2-D frame (shape %s)" % (path, a.shape))
    return a


# ---------------------------------------------------------------------------------------------
# slanted-edge SFR (ISO 12233 e-SFR)
# ---------------------------------------------------------------------------------------------
def slanted_edge_sfr(img, oversample=4):
    """SFR of a slanted edge in a region of interest -> {"f" [cycles/pixel], "sfr", "angle_deg", "mtf50",
    "orientation", "notes"}.

    The edge may be near-vertical or near-horizontal (the frame is transposed for a horizontal edge).  ISO 12233
    recommends an edge angle of a few degrees (about 2 - 10 deg) off the pixel axes."""
    a = np.asarray(img, float)
    if a.ndim != 2 or min(a.shape) < 8:
        raise ValueError("The edge region must be a 2-D frame of at least 8 x 8 pixels")
    notes = []
    gx = np.abs(np.diff(a, axis=1)).sum()
    gy = np.abs(np.diff(a, axis=0)).sum()
    orientation = "vertical"
    if gy > gx:
        a = a.T
        orientation = "horizontal"
    rows, cols = a.shape
    # edge position per row: centroid of the derivative along the row (flat-field the 2-tap derivative)
    d = np.diff(a, axis=1)
    if np.mean(d) < 0:
        d = -d
    x = np.arange(cols - 1) + 0.5
    w = np.clip(d, 0.0, None)
    sw = w.sum(axis=1)
    ok = sw > 0
    if ok.sum() < 4:
        raise ValueError("No edge found in the region")
    cen = (w[ok] * x).sum(axis=1) / sw[ok]
    y = np.arange(rows)[ok]
    slope, icpt = np.polyfit(y, cen, 1)
    # second and third pass (ISO 12233 windows the derivative around the edge): centroids within +/- 6 pixels of
    # the fitted edge, so that noise far from the edge does not pull them to the frame centre
    for _ in range(2):
        xe = icpt + slope * np.arange(rows)
        wn = w * (np.abs(x[None, :] - xe[:, None]) <= 6.0)
        sw = wn.sum(axis=1)
        ok = sw > 0
        if ok.sum() < 4:
            break
        cen = (wn[ok] * x).sum(axis=1) / sw[ok]
        y = np.arange(rows)[ok]
        slope, icpt = np.polyfit(y, cen, 1)
    angle = math.degrees(math.atan(slope))
    if abs(angle) < 1.0:
        notes.append("Edge angle %.2f deg: below about 1 deg the oversampled ESF has gaps - tilt the edge by "
                     "2 - 10 deg." % angle)
    if abs(angle) > 20.0:
        notes.append("Edge angle %.1f deg: well above the 2 - 10 deg of ISO 12233." % angle)
    # distance of every pixel centre to the fitted edge, measured along the row and projected on the normal
    yy, xx = np.mgrid[0:rows, 0:cols]
    dist = (xx - (icpt + slope * yy)) * math.cos(math.atan(slope))
    q = 1.0 / oversample
    idx = np.floor(dist.ravel() / q).astype(int)
    idx -= idx.min()
    nb = idx.max() + 1
    cnt = np.bincount(idx, minlength=nb)
    esf = np.bincount(idx, weights=a.ravel(), minlength=nb)
    filled = cnt > 0
    if (~filled).any():
        # empty bins (small angle): interpolate from the neighbours
        esf[filled] /= cnt[filled]
        esf[~filled] = np.interp(np.nonzero(~filled)[0], np.nonzero(filled)[0], esf[filled])
        notes.append("%d empty ESF bins interpolated." % int((~filled).sum()))
    else:
        esf = esf / cnt
    # drop the sparsely populated tails (corners of the region)
    keep = cnt >= max(1, 0.5 * np.median(cnt[filled]))
    i0, i1 = np.argmax(keep), len(keep) - np.argmax(keep[::-1])
    esf = esf[i0:i1]
    lsf = np.gradient(esf)
    if lsf.sum() < 0:
        lsf = -lsf
    n = len(lsf)
    c = int(np.argmax(np.convolve(np.abs(lsf), np.ones(5) / 5, mode="same")))
    # Hamming window centred on the LSF peak, wide enough for the whole record
    half = max(c, n - 1 - c)
    k = np.arange(n) - c
    win = 0.54 + 0.46 * np.cos(np.pi * k / max(half, 1))
    lsf = lsf * win
    spec = np.abs(np.fft.rfft(lsf))
    if spec[0] <= 0:
        raise ValueError("Edge has no contrast")
    sfr = spec / spec[0]
    f = np.fft.rfftfreq(n, d=q)                                     # cycles/pixel
    # np.gradient is a central difference over 2 bins: transfer sin(2 pi f q) / (2 pi f q)
    corr = np.sinc(2.0 * f * q)
    sfr = sfr / np.clip(corr, 0.1, None)
    sel = f <= 1.0
    f, sfr = f[sel], sfr[sel]
    below = np.nonzero(sfr < 0.5)[0]
    mtf50 = None
    if below.size and below[0] > 0:
        i = below[0]
        mtf50 = float(f[i - 1] + (0.5 - sfr[i - 1]) * (f[i] - f[i - 1]) / (sfr[i] - sfr[i - 1]))
    return {"f": f, "sfr": sfr, "angle_deg": angle, "mtf50": mtf50, "orientation": orientation, "notes": notes,
            "method": "ISO 12233 e-SFR, %dx oversampled ESF, Hamming window, derivative corrected" % oversample}


def sfr_to_text(res, name="SFR"):
    """Two-column text 'f [cycles/pixel]  SFR' for the measured-MTF import (unit: cycles/pixel)."""
    lines = ["# %s - %s" % (name, res["method"]),
             "# edge %s, angle %.2f deg, MTF50 %s cycles/pixel" % (
                 res["orientation"], res["angle_deg"], "%.4f" % res["mtf50"] if res["mtf50"] else "-"),
             "# frequency [cycles/pixel]   SFR"]
    lines += ["%.6f %.6f" % (f, s) for f, s in zip(res["f"], res["sfr"])]
    return "\n".join(lines) + "\n"


def synthetic_edge(shape=(100, 100), angle_deg=5.0, sigma_px=0.6, low=50.0, high=200.0, noise=0.0, seed=0,
                   sub=16):
    """Slanted-edge frame through a Gaussian PSF (sigma in pixels) and a 100 % fill-factor pixel aperture.

    The true SFR is exp(-2 pi^2 sigma^2 f^2) |sinc(f)| (f in cycles/pixel)."""
    rows, cols = shape
    t = math.tan(math.radians(angle_deg))
    s = (np.arange(sub) + 0.5) / sub - 0.5
    out = np.zeros(shape)
    x0 = cols / 2.0
    for r in range(rows):
        yy = r + s[:, None]
        xs = np.arange(cols)[None, None, :] + s[None, :, None]
        dist = (xs - (x0 + t * yy[:, :, None])) * math.cos(math.atan(t))
        u = dist / sigma_px if sigma_px > 0 else np.sign(dist) * 1e9
        cdf = 0.5 * (1.0 + _erf(u / math.sqrt(2.0)))
        out[r] = cdf.mean(axis=(0, 1))
    img = low + (high - low) * out
    if noise > 0:
        img = img + np.random.default_rng(seed).normal(0.0, noise, img.shape)
    return img


def _erf(x):
    """Vectorized erf, Abramowitz & Stegun 7.1.26 (absolute error < 1.5e-7)."""
    x = np.asarray(x, float)
    s = np.sign(x)
    a = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * a)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * \
        np.exp(-a * a)
    return s * y


# ---------------------------------------------------------------------------------------------
# photon transfer (EMVA 1288 Release 4.0 Linear)
# ---------------------------------------------------------------------------------------------
def _pair_stats(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.shape != b.shape:
        raise ValueError("The two frames of a pair must have the same size")
    mean = 0.5 * (a.mean() + b.mean())
    var_t = np.var(a - b) / 2.0                     # temporal variance, spatial pattern cancels
    avg = 0.5 * (a + b)
    var_s = max(np.var(avg) - var_t / 2.0, 0.0)     # spatial variance of the 2-frame average, temporal part removed
    return mean, var_t, var_s


def photon_transfer(flat_pairs, dark_pair, t_int_s=None, dark_series=None, linear_max=0.7):
    """EMVA 1288 analysis of frame pairs [DN].

    flat_pairs: [(A, B)] at increasing illumination / exposure; dark_pair: (A, B) dark frames at the same exposure.
    t_int_s: exposure of the dark pair [s] (for DSNU as a current); dark_series: [(t_s, A, B)] dark pairs at several
    exposures (dark current from the slope).  linear_max: fraction of the saturation mean used for the gain fit.

    -> dict with K [DN/e-], read noise [e-], saturation capacity [e-], DSNU [e-], PRNU [%], dark current [e-/s],
    the curve and the TRM inputs they correspond to ("trm": {path: value})."""
    md, vd, vsd = _pair_stats(*dark_pair)
    mu, var, vsp = [], [], []
    for a, b in flat_pairs:
        m, v, s = _pair_stats(a, b)
        mu.append(m - md)
        var.append(v - vd)
        vsp.append(s - vsd)
    mu, var, vsp = np.array(mu), np.array(var), np.array(vsp)
    order = np.argsort(mu)
    mu, var, vsp = mu[order], var[order], vsp[order]
    if len(mu) < 3:
        raise ValueError("At least 3 illumination levels are needed for the photon-transfer curve")
    i_sat = int(np.argmax(var))                      # saturation: maximum of the temporal variance
    mu_sat = mu[i_sat]
    lin = (mu > 0) & (mu <= linear_max * mu_sat)
    if lin.sum() < 2:
        lin = (mu > 0) & (np.arange(len(mu)) <= i_sat)
    if lin.sum() < 2:
        raise ValueError("Not enough points below saturation for the gain fit")
    # var = K mu + const (EMVA: fit of the linear part, the dark variance already subtracted)
    K, c0 = np.polyfit(mu[lin], var[lin], 1)
    if not K > 0:
        raise ValueError("Photon-transfer slope <= 0: check the frame order / illumination")
    notes = []
    resid = var[lin] - (K * mu[lin] + c0)
    nonlin = float(np.max(np.abs(resid)) / max(np.max(var[lin]), 1e-30))
    if nonlin > 0.05:
        notes.append("Photon-transfer curve deviates %.0f %% from a straight line in the fit range (nonlinear "
                     "response or processing - EMVA 1288 Linear does not apply)." % (100 * nonlin))
    read_e = math.sqrt(max(vd, 0.0)) / K
    sat_e = mu_sat / K
    dsnu_e = math.sqrt(max(vsd, 0.0)) / K
    j = int(np.argmin(np.abs(mu - 0.5 * mu_sat)))
    prnu = 100.0 * math.sqrt(max(vsp[j], 0.0)) / mu[j] if mu[j] > 0 else 0.0     # at ~50 % of saturation
    out = {"K_DN_per_e": float(K), "lsb_e": 1.0 / float(K), "read_noise_e": read_e, "sat_e": sat_e,
           "dsnu_e": dsnu_e, "prnu_pct": prnu, "mu_dn": mu, "var_dn2": var, "fit_mask": lin,
           "dark_mean_dn": md, "dark_var_dn2": vd, "notes": notes, "dark_current_e_s": None,
           "method": "EMVA 1288 Release 4.0 Linear: pair differences, linear fit below %.0f %% of saturation" %
                     (100 * linear_max)}
    if dark_series:
        ts = np.array([float(t) for t, _a, _b in dark_series])
        ms = np.array([_pair_stats(a, b)[0] for _t, a, b in dark_series])
        if len(ts) >= 2 and np.ptp(ts) > 0:
            out["dark_current_e_s"] = float(np.polyfit(ts, ms, 1)[0] / K)
    trm = {"detector.noise_floor_e": round(read_e, 3), "detector.lsb_e": round(1.0 / K, 6),
           "detector.adc_mode": "carriers", "detector.sat_e": round(sat_e, 1), "detector.cap_node": "camera",
           "detector.prnu_pct": round(prnu, 4)}
    if t_int_s and t_int_s > 0:
        trm["detector.dsnu_A"] = dsnu_e / t_int_s * E_CHARGE
    if out["dark_current_e_s"] is not None:
        trm["detector.dark_A"] = max(out["dark_current_e_s"], 0.0) * E_CHARGE
    trm["detector.fpn_mode"] = "measured"
    out["trm"] = trm
    return out


def synthetic_ptc(K=0.25, read_e=5.0, full_well=20000.0, prnu=0.01, dsnu_e=3.0, offset_dn=100.0, levels=12,
                  shape=(64, 64), dark_e_s=0.0, t_dark=(0.01, 0.02, 0.04), seed=1, bits=16):
    """Synthetic frame pairs of a linear camera with Poisson shot noise -> (flat_pairs, dark_pair, dark_series).

    Signal clips at the full well; the output is rounded to integer DN and clipped to the ADC range."""
    rng = np.random.default_rng(seed)
    gain_map = 1.0 + prnu * rng.standard_normal(shape)
    dark_map = dsnu_e * rng.standard_normal(shape)

    def frame(mean_e, dark_e=0.0):
        e = rng.poisson(np.clip(mean_e * gain_map, 0, None)).astype(float) + dark_map + dark_e + \
            read_e * rng.standard_normal(shape)
        e = np.minimum(e, full_well)
        return np.clip(np.round(offset_dn + K * e), 0, 2 ** bits - 1)

    flats = [(frame(m), frame(m)) for m in np.linspace(0.02, 1.15, levels) * full_well]
    dark = (frame(0.0), frame(0.0))
    series = [(t, frame(0.0, dark_e_s * t), frame(0.0, dark_e_s * t)) for t in t_dark]
    return flats, dark, series
