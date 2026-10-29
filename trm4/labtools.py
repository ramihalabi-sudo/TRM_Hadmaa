"""Laboratory frame tools: slanted-edge SFR and photon-transfer characterization of a camera, and the turbulence
Fried parameter r0 measured from a frame sequence of the camera itself.

* Slanted-edge SFR after ISO 12233 (e-SFR): edge location per row by the centroid of the line derivative, straight
  edge fit, 4x oversampled edge spread function along the edge normal, Hamming-windowed line spread function,
  discrete-derivative correction.  Output in cycles/pixel - the unit the measured-MTF import of TRM takes.
* Photon transfer after EMVA 1288 (Release 4.0 Linear): mean and temporal variance from pairs of frames at several
  exposures and a dark pair; conversion gain K from the linear part of the photon-transfer curve, read noise,
  saturation capacity, DSNU, PRNU and dark current, with the TRM detector inputs they correspond to.
* r0 from a frame sequence, spectral-ratio method of Hardie, Rucci, Bose-Pillai & Van Hook, "Application of tilt
  correlation statistics to anisoplanatic optical turbulence modeling and mitigation", Appl. Opt. 60 (2021),
  arXiv:2108.00528, Sec. 5: the magnitude spectrum of the long exposure (average of the frames, optionally registered)
  over the average magnitude spectrum of the short exposures is the Gaussian G(rho) = exp(-rho^2 / (2 sigma_G^2)) of the
  residual tilt (Eqs. 34 - 36, 43), r0 = [6.88 (lambda l sigma_G)^2 (1 - alpha) / D^(1/3)]^(3/5) (Eq. 44).

All are verified on synthetic frames with known MTF / gain / noise / r0 (synthetic_edge, synthetic_ptc,
synthetic_turbulence_frames and tests/test_labtools.py).  Real images still need the measurement conditions recorded
(Validation data / Metadata) - the tools do not know the camera's operating mode, processing state or temperature.
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


# ---------------------------------------------------------------------------------------------
# Fried parameter r0 from a frame sequence (spectral ratio, Hardie et al. 2021, Sec. 5)
# ---------------------------------------------------------------------------------------------
R0_RATIO_BAND = (0.15, 0.95)        # spectral-ratio values used for the Gaussian fit
R0_MIN_FRAMES = 10


def load_frames(paths):
    """Frame sequence (N, rows, cols) from one .npy stack (N x rows x cols) or from several frame files (load_frame),
    all of the same size."""
    paths = [paths] if isinstance(paths, str) else list(paths)
    if len(paths) == 1 and str(paths[0]).lower().endswith(".npy"):
        a = np.asarray(np.load(paths[0], allow_pickle=False), float)
        if a.ndim == 3:
            return a
    frames = [load_frame(p) for p in paths]
    if len({f.shape for f in frames}) > 1:
        raise ValueError("All frames of the sequence must have the same size")
    return np.array(frames)


def _tukey(n, frac):
    """Tukey (tapered cosine) window of n points with the fraction `frac` of them in the two cosine tapers."""
    x = (np.arange(n) + 0.5) / n
    w = np.ones(n)
    a = float(frac)
    if a > 0:
        lo, hi = x < a / 2.0, x > 1.0 - a / 2.0
        w[lo] = 0.5 * (1.0 - np.cos(2.0 * np.pi * x[lo] / a))
        w[hi] = 0.5 * (1.0 - np.cos(2.0 * np.pi * (1.0 - x[hi]) / a))
    return w


def _freq_grid(rows, cols):
    return np.fft.fftfreq(rows)[:, None], np.fft.fftfreq(cols)[None, :]


def _shift_estimate(ref_f, img_f, fy, fx):
    """Shift (dy, dx) [pixels] of a frame relative to the reference from their spectra: integer peak of the phase
    correlation, refined twice by a weighted least-squares fit of the cross-spectrum phase below 0.2 cycles/pixel."""
    cross = img_f * np.conj(ref_f)                       # |F|^2 exp(-i 2 pi f.d) for a frame shifted by d
    pc = np.real(np.fft.ifft2(cross / np.maximum(np.abs(cross), 1e-300)))
    rows, cols = pc.shape
    iy, ix = np.unravel_index(int(np.argmax(pc)), pc.shape)
    d = np.array([iy if iy <= rows // 2 else iy - rows, ix if ix <= cols // 2 else ix - cols], float)
    rho = np.hypot(fy, fx)
    low = (rho < 0.2) & (rho > 0)
    fyl, fxl = np.broadcast_to(fy, low.shape)[low], np.broadcast_to(fx, low.shape)[low]
    a = 2.0 * np.pi * np.stack([fyl, fxl])
    for _ in range(2):
        res = cross[low] * np.exp(2j * np.pi * (fyl * d[0] + fxl * d[1]))
        phi, w = np.angle(res), np.abs(res)
        try:
            d = d + np.linalg.solve((w * a) @ a.T, -(w * a) @ phi)
        except np.linalg.LinAlgError:
            break
    return d


def _shifted(img, dy, dx, fy, fx):
    """Frame shifted by (dy, dx) pixels (Fourier shift: periodic, exact for band-limited content)."""
    return np.real(np.fft.ifft2(np.fft.fft2(img) * np.exp(-2j * np.pi * (fy * dy + fx * dx))))


def register_frames(frames, iterations=2):
    """Global registration of a frame sequence (camera motion): every frame is shifted onto the mean frame (phase
    correlation with a sub-pixel phase-slope fit, Fourier shift), the second time onto the mean of the registered
    frames.  -> (registered frames, shifts (N, 2) [pixels] that were removed, zero mean)."""
    F = np.asarray(frames, float)
    n, rows, cols = F.shape
    fy, fx = _freq_grid(rows, cols)
    win = np.outer(_tukey(rows, 0.25), _tukey(cols, 0.25))
    total = np.zeros((n, 2))
    out = F
    for _ in range(int(iterations)):
        ref = out.mean(axis=0)
        ref_f = np.fft.fft2(win * (ref - ref.mean()))
        step = np.array([_shift_estimate(ref_f, np.fft.fft2(win * (out[k] - out[k].mean())), fy, fx)
                         for k in range(n)])
        total += step - step.mean(axis=0)                # the common shift is arbitrary: keep the mean position
        out = np.array([_shifted(F[k], -total[k, 0], -total[k, 1], fy, fx) for k in range(n)])
    return out, total


def r0_from_frames(frames, lam_um, focal_mm, pitch_um, D_mm, alpha=0.0, register=False, path_km=None, tukey=0.25,
                   f_max=0.5, band=R0_RATIO_BAND):
    """Fried parameter r0 from a short-exposure frame sequence (spectral ratio, Hardie et al. 2021, Sec. 5).

    frames: (N, rows, cols) of a static scene, N >= 10 (Hardie et al. used 300); lam_um: mean wavelength [um];
    focal_mm: focal length l [mm]; pitch_um: pixel pitch of the frames (binning included) [um]; D_mm: aperture [mm];
    alpha: fraction of the turbulence tilt removed by a registration of the frames (0 = raw frames of a fixed camera;
    Hardie et al.: about 0.52 for a global registration of their 501 x 501 frames); register: register the frames
    globally first (camera motion - it also removes part of the turbulence tilt, so enter its alpha); path_km: path
    length to the scene (TRM r0 inputs and the path-averaged Cn2).

    Every frame minus its mean is Tukey-windowed; ratio = |FFT(mean frame)| / mean |FFT(frame)|, median over the angle
    per radial frequency, corrected for the noise floor of the N-frame average (E|S|^2 = G^2 + (1 - G^2) / N) and fitted
    with ln G = -rho^2 / (2 sigma_G^2) (weights G^2) where band[0] <= G <= band[1] and rho <= f_max [cycles/pixel].
    Units: rho and sigma_G in cycles per metre of the focal plane (= cycles/pixel / pitch), lambda, l and D in metres:
    r0 = [6.88 (lambda l sigma_G)^2 (1 - alpha) / D^(1/3)]^(3/5) [m] (Eq. 44)."""
    F = np.asarray(frames, float)
    if F.ndim != 3:
        raise ValueError("The frame sequence must be N x rows x cols")
    n, rows, cols = F.shape
    if n < R0_MIN_FRAMES:
        raise ValueError("At least %d frames are needed (%d given); Hardie et al. used 300" % (R0_MIN_FRAMES, n))
    if min(rows, cols) < 32:
        raise ValueError("The frames must be at least 32 x 32 pixels")
    lam, l, pitch, D = float(lam_um) * 1e-6, float(focal_mm) * 1e-3, float(pitch_um) * 1e-6, float(D_mm) * 1e-3
    if not (lam > 0 and l > 0 and pitch > 0 and D > 0):
        raise ValueError("Wavelength, focal length, pixel pitch and aperture must be > 0")
    alpha = float(alpha)
    if not 0.0 <= alpha < 1.0:
        raise ValueError("The tilt correction factor alpha must be in [0, 1)")
    notes = []
    shifts = None
    if register:
        F, shifts = register_frames(F)
        if alpha == 0.0:
            notes.append("The frames were registered but alpha = 0: the registration also removes part of the "
                         "turbulence tilt, so r0 is over-estimated - enter the tilt correction factor of the "
                         "registration (Hardie et al.: about 0.52 for a global registration of 501 x 501 frames).")
    win = np.outer(_tukey(rows, tukey), _tukey(cols, tukey))
    mag = np.zeros((rows, cols))
    acc = np.zeros((rows, cols))
    for fr in F:
        g = win * (fr - fr.mean())
        mag += np.abs(np.fft.fft2(g))
        acc += g
    mag /= n
    long_ = np.abs(np.fft.fft2(acc / n))
    ratio = np.where(mag > 0, long_ / np.where(mag > 0, mag, 1.0), 0.0)
    fy, fx = _freq_grid(rows, cols)
    rho = np.hypot(fy, fx)
    step = 1.0 / min(rows, cols)
    edges = np.arange(0.5 * step, f_max + step, step)
    f_b, g_b = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (rho >= lo) & (rho < hi)
        if sel.sum() >= 4:
            m = float(np.median(ratio[sel]))
            f_b.append(0.5 * (lo + hi))
            g_b.append(math.sqrt(max(m * m - 1.0 / n, 0.0) / (1.0 - 1.0 / n)))
    f_b, g_b = np.array(f_b), np.array(g_b)
    used = (f_b <= f_max) & (g_b >= band[0]) & (g_b <= band[1])
    if used.sum() < 3:
        if g_b.size and g_b[-1] > band[1]:
            # ratio still above band[1] at f_max: G(f_max) >= band[1] -> sigma_G >= f_max / sqrt(-2 ln band[1])
            sg_min = f_b[-1] / math.sqrt(-2.0 * math.log(band[1]))
            r0_min = (6.88 * (lam * l * sg_min / pitch) ** 2 * (1.0 - alpha) / D ** (1.0 / 3.0)) ** 0.6
            raise ValueError("The spectral ratio stays above %.2f up to %.2f cycles/pixel: the turbulence tilt is not "
                             "resolved by the pixels (r0 > %.3g cm, or the frames are registered / stabilised)." % (
                                 band[1], f_b[-1], 100.0 * r0_min))
        raise ValueError("Too few spectral-ratio points between %.2f and %.2f for the Gaussian fit: the tilt is too "
                         "large for the frame size, or the frames are not of one static scene." % tuple(band))
    x, y, w = f_b[used] ** 2, -np.log(g_b[used]), g_b[used] ** 2
    b = float(np.sum(w * x * y) / np.sum(w * x * x))
    if not b > 0:
        raise ValueError("The spectral ratio does not fall with frequency - no turbulence tilt found")
    sg_px = math.sqrt(1.0 / (2.0 * b))                       # sigma_G [cycles/pixel]
    resid = y - b * x
    r2 = 1.0 - float(np.sum(w * resid ** 2) / max(np.sum(w * (y - np.average(y, weights=w)) ** 2), 1e-300))
    sg = sg_px / pitch                                       # cycles/m in the focal plane
    r0 = (6.88 * (lam * l * sg) ** 2 * (1.0 - alpha) / D ** (1.0 / 3.0)) ** 0.6
    tilt_px = 1.0 / (2.0 * math.pi * sg_px)                  # residual tilt in the averaged frames, per axis
    if n < 50:
        notes.append("Only %d frames: the noise floor 1 / sqrt(N) = %.2f of the averaged spectrum limits the fit "
                     "(Hardie et al. used 300 frames)." % (n, 1.0 / math.sqrt(n)))
    if tilt_px < 0.2:
        notes.append("The residual tilt is %.2f pixels rms: hardly resolved by the pixels, r0 is uncertain." % tilt_px)
    if r2 < 0.9:
        notes.append("The spectral ratio is not Gaussian (R^2 = %.2f): scene motion, camera vibration, noise or "
                     "registration errors?" % r2)
    out = {"r0_m": r0, "r0_cm": 100.0 * r0, "lam_um": float(lam_um), "D_over_r0": D / r0, "sigma_G_px": sg_px,
           "sigma_G_per_mm": sg * 1e-3, "tilt_px": tilt_px, "tilt_urad": tilt_px * pitch / l * 1e6, "r2": r2,
           "n_frames": n, "shape": (rows, cols), "alpha": alpha, "registered": bool(register), "shifts": shifts,
           "f": f_b, "ratio": g_b, "fit": np.exp(-b * f_b ** 2), "used": used, "path_km": None, "cn2": None,
           "notes": notes, "trm": {},
           "method": "Spectral ratio (Hardie et al. 2021, Eq. 44): |FFT(mean frame)| / mean |FFT(frame)|, Tukey "
                     "window, median over the angle, Gaussian fit; r0 = [6.88 (lambda l sigma_G)^2 (1 - alpha) / "
                     "D^(1/3)]^(3/5)%s" % (", frames registered globally" if register else "")}
    if path_km and float(path_km) > 0:
        from .extensions import cn2_uniform_from_r0
        out["path_km"] = float(path_km)
        out["cn2"] = cn2_uniform_from_r0(r0, lam_um, path_km)
        out["trm"] = {"turbulence.on": True, "turbulence.cn2_mode": "r0", "turbulence.cn2_preset": "custom",
                      "turbulence.r0_cm": round(100.0 * r0, 4), "turbulence.r0_lambda_um": float(lam_um),
                      "turbulence.r0_L_km": float(path_km)}
    return out


def r0_summary(res):
    """Text lines of an r0 measurement (r0_from_frames)."""
    rows, cols = res["shape"]
    f_used = res["f"][res["used"]]
    lines = [res["method"], "",
             "Frames: %d of %d x %d pixels%s" % (res["n_frames"], rows, cols, ", registered" if res["registered"]
                                                 else ""),
             "Fried parameter r0 = %.4g cm at %.3g um (D / r0 = %.3g, tilt correction alpha = %.3g)" % (
                 res["r0_cm"], res["lam_um"], res["D_over_r0"], res["alpha"]),
             "Gaussian width sigma_G = %.4g cycles/pixel = %.4g cycles/mm; fit R^2 = %.3f over %d radial bins "
             "(%.3g - %.3g cycles/pixel)" % (res["sigma_G_px"], res["sigma_G_per_mm"], res["r2"], len(f_used),
                                             f_used.min(), f_used.max()),
             "Residual tilt in the averaged frames: %.3g pixels = %.3g urad rms per axis" % (res["tilt_px"],
                                                                                      res["tilt_urad"])]
    if res["path_km"]:
        lines.append("Path %.4g km: path-averaged Cn2 = %.3g m^-2/3 (uniform path, spherical wave, TRM4 Eq. 4.82)" % (
            res["path_km"], res["cn2"]))
    return lines + ["Note: " + n for n in res["notes"]]


def r0_to_text(res, name="frames"):
    """Text report of an r0 measurement with the spectral-ratio curve."""
    lines = ["# r0 from the frame sequence %s" % name] + ["# " + s for s in r0_summary(res) if s] + \
        ["# frequency [cycles/pixel]   ratio G   Gaussian fit   used in the fit"]
    lines += ["%.6f %.6f %.6f %d" % (f, g, m, u) for f, g, m, u in zip(res["f"], res["ratio"], res["fit"], res["used"])]
    return "\n".join(lines) + "\n"


def synthetic_turbulence_frames(r0_m, lam_um, focal_mm, pitch_um, D_mm, n=300, shape=(128, 128), alpha=0.0, noise=0.0,
                                seed=0):
    """Frames of a static random scene seen through turbulence of Fried parameter r0 -> (frames, tilt rms [pixels]).

    Every frame is blurred by the same short-exposure OTF (diffraction x Fried near-field short exposure, Hardie et al.
    2021 Eqs. 29, 30) and shifted by a random Gaussian tilt, independent per axis and frame, whose variance gives the
    Gaussian of Eqs. (35), (36): tilt rms = 1 / (2 pi sigma_G) [pixels]; with alpha > 0 the residual tilt after a
    registration that removed the fraction alpha.  The scene has a 1/f amplitude spectrum (periodic, so the Fourier
    shift is exact); additive white noise of `noise` times the scene standard deviation."""
    rng = np.random.default_rng(seed)
    rows, cols = shape
    fy, fx = _freq_grid(rows, cols)
    rho_px = np.hypot(fy, fx)
    scene_f = np.fft.fft2(rng.standard_normal(shape)) / np.maximum(rho_px, 1.0 / max(rows, cols))
    scene_f[0, 0] = 0.0
    s_std = float(np.real(np.fft.ifft2(scene_f)).std())
    lam, l, D, pitch = float(lam_um) * 1e-6, float(focal_mm) * 1e-3, float(D_mm) * 1e-3, float(pitch_um) * 1e-6
    rho = rho_px / pitch                                     # cycles/m in the focal plane
    x = np.clip(rho * lam * l / D, 0.0, 1.0)                 # rho / rho_c, rho_c = 1 / (lambda f#)
    h_dif = 2.0 / np.pi * (np.arccos(x) - x * np.sqrt(1.0 - x * x))
    s = lam * l * rho
    h_se = np.exp(-3.44 * (s / float(r0_m)) ** (5.0 / 3.0) * np.clip(1.0 - (s / D) ** (1.0 / 3.0), 0.0, None))
    base = scene_f * h_dif * h_se * (20.0 / s_std)
    sg2 = float(r0_m) ** (5.0 / 3.0) * D ** (1.0 / 3.0) / (6.88 * (1.0 - float(alpha)) * (lam * l) ** 2)
    tilt = 1.0 / (2.0 * math.pi * math.sqrt(sg2) * pitch)    # pixels
    frames = np.empty((int(n), rows, cols))
    for k in range(int(n)):
        dy, dx = rng.normal(0.0, tilt, 2)
        frames[k] = 100.0 + np.real(np.fft.ifft2(base * np.exp(-2j * np.pi * (fy * dy + fx * dx))))
    if noise > 0:
        frames += rng.normal(0.0, 20.0 * float(noise), frames.shape)
    return frames, tilt
