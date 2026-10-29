"""TRM_HADMAA extensions of the TRM4 range model (roadmap phase 3 of the parameter-sensitivity report, reports/).

TRM4 is line-pair deterministic: one range per task criterion, no probability, no clutter, no meteorological
extinction model, no turbulence in the Thermal category and no machine observer.  The functions here add those
capabilities as clearly labelled extensions.  Each one is off by default or an extra output next to the TRM4
result, so the TRM4 ranges of a project are unchanged unless the user switches an extension on.

Sources (report reference numbers in brackets):
* Johnson / Lawson target transfer probability function (TTPF) - Sjaardema, Smith, Birch, "History and Evolution
  of the Johnson Criteria", Sandia SAND2015-6368 (2015) [10].
* ACQUIRE-LC / Detect05 clutter-dependent detection criterion, same report.
* Aerosol extinction versus visual range: Kruse wavelength exponent, Kim, McArthur & Korevaar, Proc. SPIE 4214
  (2001) for visual ranges below 6 km [34], [35].
* Water-vapour continuum in the 8-14 um window: Roberts, Selby & Biberman, Appl. Opt. 15, 2085 (1976).
* Saturation vapour pressure: Magnus form of Alduchov & Eskridge, J. Appl. Meteor. 35, 601 (1996).
* Pixels-on-target thresholds of an algorithm observer: Holst & Mahalanobis, Proc. SPIE 12533 (2023) [51].
* Image compression as an equivalent per-pixel blur: O'Shea, Jacobs & Espinola, Opt. Eng. 47(1) 013202 (2008) [47].
* Turbulence mitigation processing, reported recognition-range gains of +10 to +25 % [42], [43].
* Targeting task performance (TTP) metric and its TTPF: Vollmerhausen, Jacobs & Driggers, "New metric for predicting
  target acquisition performance", Opt. Eng. 43(11), 2806 (2004).
* Aerosol MTF: Kopeika, "A System Engineering Approach to Imaging", SPIE Press (1998), Ch. 17.
"""
import math

import numpy as np

EXTENSION = "TRM_HADMAA extension (not TRM4)"

# ---------------------------------------------------------------------------------------------
# Probability of task performance: Johnson / Lawson TTPF
# ---------------------------------------------------------------------------------------------
PROB_LEVELS = (0.5, 0.8, 0.9)


def ttpf_johnson(x):
    """P(N / N50) = x^E / (1 + x^E) with E = 2.7 + 0.7 x (SAND2015-6368)."""
    x = max(float(x), 0.0)
    if x == 0:
        return 0.0
    e = 2.7 + 0.7 * x
    xe = x ** e
    return xe / (1.0 + xe)


def ttpf_ratio(prob):
    """N / N50 needed for probability `prob` (inverse of ttpf_johnson; 1 for P = 0.5)."""
    prob = float(prob)
    if not 0.0 < prob < 1.0:
        raise ValueError("Probability must be in (0, 1)")
    lo, hi = 1e-6, 50.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if ttpf_johnson(mid) < prob:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------------------------
# Background clutter: ACQUIRE-LC multiplier of the detection criterion
# ---------------------------------------------------------------------------------------------
CLUTTER_C = {"low": 1.0, "medium_low": 1.5, "medium": 2.0, "high": 2.7}


def clutter_factor(level, dT_K=None):
    """Multiplier of the Detection criterion relative to low clutter.

    ACQUIRE-LC: N50 = 0.75 C [(C / dT_RSS)^2 + 1] with C = 1 / 1.5 / 2 / 2.7.  The ratio to low clutter (C = 1) at the
    same contrast keeps the user's criterion as the low-clutter calibration.  dT_K: apparent thermal contrast
    (Thermal); None = high-contrast limit (factor C), used for reflective / General scenes."""
    c = CLUTTER_C.get(level)
    if c is None:
        return 1.0
    if dT_K is None or not dT_K > 0:
        return c
    return c * ((c / dT_K) ** 2 + 1.0) / ((1.0 / dT_K) ** 2 + 1.0)


# ---------------------------------------------------------------------------------------------
# Extinction from meteorological data: aerosol (Kruse / Kim) + water-vapour continuum (Roberts 1976)
# ---------------------------------------------------------------------------------------------
P0_HPA = 1013.25
R_V = 461.5                       # specific gas constant of water vapour [J / (kg K)]


def kim_q(V_km):
    """Wavelength exponent of the aerosol extinction: Kruse above 6 km, Kim et al. (2001) below."""
    V = float(V_km)
    if V > 50:
        return 1.6
    if V > 6:
        return 1.3
    if V > 1:
        return 0.16 * V + 0.34
    if V > 0.5:
        return V - 0.5
    return 0.0


def aerosol_extinction(lam_um, V_km):
    """Aerosol extinction [1/km] = (3.912 / V) (lambda / 0.55 um)^-q."""
    V = float(V_km)
    if V <= 0:
        raise ValueError("Visual range must be > 0")
    lam = np.asarray(lam_um, float)
    return 3.912 / V * (lam / 0.55) ** (-kim_q(V))


def saturation_pressure_hpa(T_K):
    """Saturation vapour pressure over water [hPa], Magnus form (Alduchov & Eskridge 1996)."""
    t = float(T_K) - 273.15
    return 6.1094 * math.exp(17.625 * t / (t + 243.04))


def water_vapour_density(T_K, rh_pct):
    """Absolute humidity [g/m^3] from air temperature and relative humidity."""
    e = max(float(rh_pct), 0.0) / 100.0 * saturation_pressure_hpa(T_K) * 100.0      # Pa
    return 1000.0 * e / (R_V * float(T_K))


CONTINUUM_BAND_UM = (8.0, 14.0)


def continuum_extinction(lam_um, T_K, rh_pct, P_hpa=P0_HPA):
    """Water-vapour continuum absorption [1/km] in the 8-14 um window (Roberts, Selby & Biberman 1976).

    k(nu) = C_s(nu, T) w (e + 0.002 (P - e)),  C_s(nu, 296 K) = 4.18 + 5578 exp(-7.87e-3 nu)  [(g/cm^2)^-1 atm^-1],
    C_s(T) = C_s(296 K) exp[1800 (1/T - 1/296)],  w = precipitable water per km [g/cm^2].  Zero outside the window
    (line absorption of H2O / CO2 is not included)."""
    lam = np.asarray(lam_um, float)
    T = float(T_K)
    e_hpa = max(float(rh_pct), 0.0) / 100.0 * saturation_pressure_hpa(T)
    e_atm, P_atm = e_hpa / P0_HPA, float(P_hpa) / P0_HPA
    w = water_vapour_density(T, rh_pct) * 0.1                   # g/m^3 x 1 km -> g/cm^2
    nu = 1e4 / np.maximum(lam, 1e-6)
    cs = (4.18 + 5578.0 * np.exp(-7.87e-3 * nu)) * math.exp(1800.0 * (1.0 / T - 1.0 / 296.0))
    k = cs * w * (e_atm + 0.002 * (P_atm - e_atm))
    inside = (lam >= CONTINUUM_BAND_UM[0]) & (lam <= CONTINUUM_BAND_UM[1])
    return np.where(inside, k, 0.0)


def weather_extinction(lam_um, V_km, T_K, rh_pct):
    """(total, aerosol, water-vapour continuum) spectral extinction [1/km] from the weather."""
    a = aerosol_extinction(lam_um, V_km)
    w = continuum_extinction(lam_um, T_K, rh_pct)
    return a + w, a, w


# ---------------------------------------------------------------------------------------------
# Algorithm observer: pixels on target
# ---------------------------------------------------------------------------------------------
# pixels on the target area for Detection / Recognition / Identification (Holst & Mahalanobis 2023: 50-70 detection,
# 150 classification, 250 recognition, 350 identification)
POT_DEFAULTS = (60.0, 250.0, 350.0)
ALGO_CNR_DEFAULT = 3.0


def pot_default(index):
    return POT_DEFAULTS[index] if index < len(POT_DEFAULTS) else POT_DEFAULTS[-1]


def last_range_at_or_above(R, y, need):
    """Largest range on a falling curve y(R) at which y >= need (log-log interpolation).

    None if y < need already at the first range, inf if y >= need over the whole grid."""
    R, y = np.asarray(R, float), np.asarray(y, float)
    ok = y >= need
    if not ok[0]:
        return None
    bad = np.nonzero(~ok)[0]
    if not bad.size:
        return float("inf")
    i = bad[0]
    y0, y1 = math.log(max(y[i - 1], 1e-300)), math.log(max(y[i], 1e-300))
    t = (math.log(need) - y0) / (y1 - y0) if y1 != y0 else 0.0
    return float(math.exp(math.log(R[i - 1]) + t * (math.log(R[i]) - math.log(R[i - 1]))))


# ---------------------------------------------------------------------------------------------
# Compression and turbulence mitigation
# ---------------------------------------------------------------------------------------------
def mtf_compression(r, sigma_px, alpha_mrad):
    """Equivalent Gaussian blur of lossy compression, sigma in pixels (O'Shea et al. 2008)."""
    s = float(sigma_px) * float(alpha_mrad)
    return np.exp(-2.0 * math.pi ** 2 * s ** 2 * np.asarray(r, float) ** 2)


# ---------------------------------------------------------------------------------------------
# Nonlinear output processing: tone mapping / AGC to a quantized display stream
# ---------------------------------------------------------------------------------------------
TONE_MODES = ("none", "linear", "gamma", "log")


def tone_slope(x, x_max, mode, bits, gamma=0.45, k_log=100.0):
    """Local slope dOut / dIn [output levels per input unit] of the tone curve at the input x (0 <= x <= x_max).

    linear: out = L x / x_max;  gamma: out = L (x / x_max)^gamma;  log: out = L ln(1 + k x / x_max) / ln(1 + k),
    L = 2^bits - 1.  Above x_max the output clips (slope 0)."""
    L = 2.0 ** int(bits) - 1.0
    x_max = float(x_max)
    if not x_max > 0:
        raise ValueError("Tone-mapping input range must be > 0")
    u = float(x) / x_max
    if u > 1.0:
        return 0.0
    u = max(u, 1e-9)
    if mode == "linear":
        return L / x_max
    if mode == "gamma":
        return L * float(gamma) * u ** (float(gamma) - 1.0) / x_max
    if mode == "log":
        k = float(k_log)
        return L * k / ((1.0 + k * u) * math.log(1.0 + k) * x_max)
    raise ValueError("Unknown tone-mapping mode %r" % mode)


def tone_noise(x, x_max, mode, bits, gamma=0.45, k_log=100.0):
    """Input-referred quantization noise of the tone-mapped output, 1 / (sqrt(12) slope) [input units].

    A signal and noise gain of the same slope leaves the SNR unchanged; what the curve adds is the rounding to
    2^bits output levels, large where the curve compresses (small slope).  inf where the output clips."""
    s = tone_slope(x, x_max, mode, bits, gamma, k_log)
    return float("inf") if s <= 0 else 1.0 / (math.sqrt(12.0) * s)


# ---------------------------------------------------------------------------------------------
# Line-of-sight jitter
# ---------------------------------------------------------------------------------------------
# residual LOS jitter commonly assumed in US Army NV-IPM calculations [49]; narrow fields of view are optimistic
# without it (the Gaussian jitter MTF is reasonable below about 1/3 IFOV, NVTherm [16])
TYPICAL_JITTER_MRAD = 0.070


# ---------------------------------------------------------------------------------------------
# Turbulence: Hufnagel-Valley Cn2 altitude profile
# ---------------------------------------------------------------------------------------------
HV_WIND_MS = 21.0                 # rms upper-altitude wind of the HV 5/7 profile [m/s]
HV_GROUND_CN2 = 1.7e-14           # ground-level coefficient A of HV 5/7 [m^-2/3]


def cn2_hufnagel_valley(h_m, A=HV_GROUND_CN2, v_ms=HV_WIND_MS):
    """Cn2(h) = 0.00594 (v / 27)^2 (1e-5 h)^10 exp(-h / 1000) + 2.7e-16 exp(-h / 1500) + A exp(-h / 100).

    h: height above ground [m].  HV 5/7 (A = 1.7e-14, v = 21 m/s): r0 = 5 cm and isoplanatic angle 7 urad at 0.5 um
    for a vertical path (Valley 1980; Andrews & Phillips, "Laser Beam Propagation through Random Media", 2nd ed., SPIE
    2005, Sec. 12.2).  A boundary-layer model of the free atmosphere above ~100 m, not of the surface layer."""
    h = np.maximum(np.asarray(h_m, float), 0.0)
    return 0.00594 * (float(v_ms) / 27.0) ** 2 * (1e-5 * h) ** 10 * np.exp(-h / 1000.0) + \
        2.7e-16 * np.exp(-h / 1500.0) + float(A) * np.exp(-h / 100.0)


# ---------------------------------------------------------------------------------------------
# Targeting task performance (TTP) metric with V50 criteria
# ---------------------------------------------------------------------------------------------
# V50 [cycles] per task for Detection / Recognition / Identification.  Identification ~ 20 is the order of the
# NVESD tracked-vehicle set (Vollmerhausen, Jacobs & Driggers 2004); the Detection / Recognition values are typical
# orders of magnitude only.  Every V50 has to be calibrated for the target set and the TRM4 threshold convention.
TTP_V50_DEFAULTS = (2.7, 14.5, 20.8)


def v50_default(index):
    return TTP_V50_DEFAULTS[index] if index < len(TTP_V50_DEFAULTS) else TTP_V50_DEFAULTS[-1]


def ttpf_ttp(x):
    """P(V / V50) = x^E / (1 + x^E) with E = 1.51 + 0.24 x (Vollmerhausen, Jacobs & Driggers 2004)."""
    x = max(float(x), 0.0)
    if x == 0:
        return 0.0
    e = 1.51 + 0.24 * x
    xe = x ** e
    return xe / (1.0 + xe)


def ttpf_ttp_ratio(prob):
    """V / V50 needed for probability `prob` (inverse of ttpf_ttp; 1 for P = 0.5)."""
    prob = float(prob)
    if not 0.0 < prob < 1.0:
        raise ValueError("Probability must be in (0, 1)")
    lo, hi = 1e-6, 100.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if ttpf_ttp(mid) < prob:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def ttp_integral(rp, threshold, signal):
    """TTP = integral of sqrt(signal / threshold(rp)) d rp over the frequencies where signal > threshold.

    rp: bar frequencies [cycles/mrad]; threshold: TRM4 MTDP / MDSP at rp (inf = not resolved); signal: available ETD
    or EDS at the same range.  The TRM4 threshold over the signal takes the place of CTF_sys / C_target."""
    rp, thr = np.asarray(rp, float), np.asarray(threshold, float)
    s = float(signal)
    if not s > 0:
        return 0.0
    ok = np.isfinite(thr) & (thr > 0) & (thr < s)
    if not ok.any():
        return 0.0
    g = np.where(ok, np.sqrt(s / np.where(ok, thr, 1.0)), 0.0)
    return float(np.sum(0.5 * (g[1:] + g[:-1]) * np.diff(rp)))


# ---------------------------------------------------------------------------------------------
# Geometric quick estimate: Nyquist / diffraction range without noise, contrast or atmosphere
# ---------------------------------------------------------------------------------------------
def geometric_range(crit_m, n_lp, ifov_mrad, lam_um, D_mm):
    """(range [km], limit) at which `n_lp` line pairs fit across the critical dimension.

    One line pair needs the larger of two pixels (Nyquist) and the diffraction period lambda / D (the optics cutoff).
    Noise, contrast, MTF roll-off below the cutoff and the atmosphere are ignored, and bars beyond Nyquist (which the
    TRM4 AMOP still credits) are not, so this is a reference value, not a bound of the TRM4 range."""
    p_samp = 2.0 * float(ifov_mrad)
    p_diff = float(lam_um) / float(D_mm) if D_mm > 0 else 0.0
    period, limit = (p_samp, "sampling (2 pixels per line pair)") if p_samp >= p_diff else \
        (p_diff, "diffraction (lambda / D)")
    if not (period > 0 and n_lp > 0):
        return float("inf"), limit
    return float(crit_m) / (float(n_lp) * period), limit


# ---------------------------------------------------------------------------------------------
# Aerosol MTF (Kopeika): low-frequency forward-scatter blur
# ---------------------------------------------------------------------------------------------
# typical particle radii: haze ~ 1 um, fog / mist ~ 10 um (Kopeika, "A System Engineering Approach to Imaging",
# SPIE Press 1998, Ch. 17)
AEROSOL_RADIUS_UM = {"haze": 1.0, "fog": 10.0}


def aerosol_cutoff(lam_um, radius_um):
    """Spatial frequency above which the aerosol MTF is flat, xi_c = a / lambda [cycles/rad] -> cycles/mrad."""
    return float(radius_um) / float(lam_um) / 1000.0


def aerosol_mtf(r, R_km, S_per_km, xi_c):
    """Kopeika aerosol MTF exp[-S R (r / xi_c)^2] below xi_c, exp(-S R) above (S: aerosol scattering [1/km]).

    Above xi_c the value equals the scattering part of the Beer-Lambert transmission: an image model that already
    counts the aerosol extinction in the signal must not apply this plateau again."""
    r = np.asarray(r, float)
    sr = float(S_per_km) * float(R_km)
    return np.where(r < xi_c, np.exp(-sr * (r / xi_c) ** 2), math.exp(-sr))
