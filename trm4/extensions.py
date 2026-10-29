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
* Exposure-time turbulence MTF (effective aperture D + v tau): Azoulay, FGAN-FfO report 1990/3, as used in
  Weiss-Wrana, "Influence of atmospheric turbulence on imaging quality of electro-optical sensors in different
  climates", FGAN-FOM 2003/11 (also the source of the sunrise and overcast Cn2 statements).
* Residual-tilt (registration) OTF: Hardie, Rucci, Bose-Pillai & Van Hook, "Application of tilt correlation
  statistics to anisoplanatic optical turbulence modeling and mitigation", arXiv:2108.00528 (2021).
* Near / far-field short-exposure MTF: Fried, JOSA 56, 1372 (1966); Tofsted, Opt. Eng. 50, 016001 (2011) and 53,
  044112 (2014).
* Lucky imaging: Fried, "Probability of getting a lucky short-exposure image through turbulence", JOSA 68, 1651
  (1978); tilt-removed phase variance 0.134 (D/r0)^(5/3): Noll, JOSA 66, 207 (1976).
* Isoplanatic angle: Fried, "Anisoplanatism in adaptive optics", JOSA 72, 52 (1982); spherical-wave tilt statistics
  and the tilt correlation of horizontal paths: Hardie et al. 2021 (above), Sec. 3 and Table 2.
* Cn2 altitude profiles SLC (day / night), Greenwood and Brookner: Quatresooz & Oestges, "Cn2 modeling for free-space
  optical communications: a review", IEEE Access 13, 21279 (2025); TRM4 App. C.7.2 on such preset profiles.
* Cn2 from macro-meteorology: Sadot & Kopeika, Opt. Eng. 31(2), 200 (1992); fit height 15 m and transfer to Mauna
  Loa: Jellen, Nelson, Brownell & Burkhardt, "Effective benchmarks for optical turbulence modeling", AIES (2024).
* Scintillation of a spherical wave in weak turbulence, sigma_A^2 = 0.124 k^(7/6) L^(11/6) Cn2: Weiss-Wrana,
  "Turbulence statistics applied to calculate expected turbulence-induced scintillation effects on electro-optical
  systems in different climate regions", FGAN-FOM 2005/09.  Spherical-wave aperture averaging A = [1 + 0.214
  (k D^2 / 4L)^(7/6)]^-1: Churnside, "Aperture averaging of optical scintillations in the turbulent atmosphere",
  Appl. Opt. 30(15), 1982 (1991), as reproduced in Kaushal & Kaddoum, arXiv:1506.04836 (2015), Eq. (21).  Weak
  fluctuations = Rytov variance < 1: Andrews & Phillips, "Laser Beam Propagation through Random Media", 2nd ed., SPIE
  Press (2005).
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
# Turbulence: further Cn2 altitude profiles (Quatresooz & Oestges, IEEE Access 13, 21279 (2025))
# ---------------------------------------------------------------------------------------------
# cn2_mode -> (label, formula, uses the Cn2 field).  Astronomical-site / free-atmosphere models: TRM4 (App. C.7.2)
# notes that such preset profiles tend to underestimate the turbulence close to the ground.
CN2_PROFILES = {
    "slc_night": ("SLC night", "8.40e-15 (h <= 18.5 m); 2.87e-12 h^-2 (18.5 - 110 m); 2.5e-16 (110 - 1500 m); "
                  "8.87e-7 h^-3 (1500 - 7200 m); 2.0e-16 h^-0.5 (7200 - 20000 m)", False),
    "slc_day": ("SLC day", "1.70e-14 (h <= 18.5 m); 3.13e-13 h^-1 (18.5 - 240 m); 1.30e-15 (240 - 880 m); "
                "8.87e-7 h^-3 (880 - 7200 m); 2.0e-16 h^-0.5 (7200 - 20000 m)", False),
    "greenwood_good": ("Greenwood, good seeing", "(2.2e-13 (h + 10)^-1.3 + 4.3e-17) exp(-h / 4000 m)", False),
    "greenwood_poor": ("Greenwood, poor seeing", "(2.2e-12 (h + 10)^-1.3 + 7e-16) exp(-h / 2000 m)", False),
    "brookner": ("Brookner", "Cn0^2 h^-5/6 exp(-h / 320 m), Cn0^2 = the Cn2 field (Cn2 at 1 m)", True),
}
BROOKNER_H0_M = 320.0
H_MIN_M = 0.1                     # lowest height of the power-law profiles (as the TRM4 height mode)


def cn2_slc(h_m, day=False):
    """SLC (Submarine Laser Communication) Cn2 model, night or day [m^-2/3]; h above ground [m], defined to 20 km
    (the last term is continued above).  The pieces join within 6 % at the breakpoints."""
    h = np.maximum(np.asarray(h_m, float), 0.0)
    hs = np.maximum(h, 1.0)                                  # np.select evaluates every branch
    if day:
        return np.select([h <= 18.5, h <= 240.0, h <= 880.0, h <= 7200.0],
                         [np.full_like(h, 1.70e-14), 3.13e-13 / hs, np.full_like(h, 1.30e-15), 8.87e-7 * hs ** -3],
                         2.0e-16 * hs ** -0.5)
    return np.select([h <= 18.5, h <= 110.0, h <= 1500.0, h <= 7200.0],
                     [np.full_like(h, 8.40e-15), 2.87e-12 * hs ** -2, np.full_like(h, 2.5e-16), 8.87e-7 * hs ** -3],
                     2.0e-16 * hs ** -0.5)


def cn2_greenwood(h_m, poor=False):
    """Greenwood Cn2 model [m^-2/3], good seeing (2.2e-13 (h + 10)^-1.3 + 4.3e-17) exp(-h / 4000) or poor seeing
    (2.2e-12 (h + 10)^-1.3 + 7e-16) exp(-h / 2000); h above ground [m]."""
    h = np.maximum(np.asarray(h_m, float), 0.0)
    if poor:
        return (2.2e-12 * (h + 10.0) ** -1.3 + 7e-16) * np.exp(-h / 2000.0)
    return (2.2e-13 * (h + 10.0) ** -1.3 + 4.3e-17) * np.exp(-h / 4000.0)


def cn2_brookner(h_m, cn0):
    """Brookner Cn2 model Cn0^2 h^(-5/6) exp(-h / 320 m) [m^-2/3]; h above ground [m] (>= 0.1 m), Cn0^2 = Cn2 at 1 m."""
    h = np.maximum(np.asarray(h_m, float), H_MIN_M)
    return float(cn0) * h ** (-5.0 / 6.0) * np.exp(-h / BROOKNER_H0_M)


def cn2_profile(mode, h_m, cn2=None):
    """Cn2 [m^-2/3] of a profile of CN2_PROFILES at the heights h [m]; cn2 = Cn0^2 of the Brookner model."""
    if mode == "slc_night":
        return cn2_slc(h_m, day=False)
    if mode == "slc_day":
        return cn2_slc(h_m, day=True)
    if mode == "greenwood_good":
        return cn2_greenwood(h_m, poor=False)
    if mode == "greenwood_poor":
        return cn2_greenwood(h_m, poor=True)
    if mode == "brookner":
        return cn2_brookner(h_m, cn2)
    raise ValueError("Unknown Cn2 profile %r" % mode)


# ---------------------------------------------------------------------------------------------
# Turbulence: Cn2 from macro-meteorology (Sadot & Kopeika 1992)
# ---------------------------------------------------------------------------------------------
SK_HEIGHT_M = 15.0                # height the regression was fitted at (Jellen et al. 2024)
SK_VALID = {"T_C": (9.0, 35.0), "rh_pct": (14.0, 92.0), "wind_ms": (0.0, 10.0)}
# Temporal-hour weight W (Sadot & Kopeika 1992, reproduced as Table 3 of Quatresooz & Oestges 2025).  PROVISIONAL:
# only these entries are verified (secondary source); the full table of the paper still has to be entered.
# key -> (label, temporal hours [lo, hi) relative to sunrise, W, time of day of the height exponent)
SK_W_PRESETS = {
    "night": ("more than 3 h before sunrise", (-float("inf"), -3.0), 0.11, "night"),
    "pre_sunrise": ("3 - 2 h before sunrise", (-3.0, -2.0), 0.07, "night"),
    "h3_4": ("3 - 4 temporal hours after sunrise", (3.0, 4.0), 0.75, "day"),
    "h4_5": ("4 - 5 temporal hours after sunrise", (4.0, 5.0), 0.95, "day"),
    "h5_6": ("5 - 6 temporal hours after sunrise", (5.0, 6.0), 1.00, "day"),
}
SK_W_PROVISIONAL = True
SK_TRANSFER_NOTE = ("fitted in the Negev (Beer Sheva, Sde Boker) - it transfers poorly to other sites (R^2 = 0.02 at "
                    "Mauna Loa, Jellen et al. 2024) and needs a local calibration (scintillometer)")


def temporal_hour(t_h, sunrise_h, sunset_h):
    """Temporal hour (t - sunrise) / (day length / 12) of the clock time t [h]; negative before sunrise."""
    day = float(sunset_h) - float(sunrise_h)
    if not day > 0:
        raise ValueError("Sunset must be later than sunrise")
    return (float(t_h) - float(sunrise_h)) / (day / 12.0)


def sk_weight(th):
    """(W, preset key) of a temporal hour from the verified part of the W table; (None, None) where the table is not
    entered yet (PROVISIONAL)."""
    for key, (_lab, (lo, hi), w, _tod) in SK_W_PRESETS.items():
        if lo <= float(th) < hi:
            return w, key
    return None, None


def cn2_sadot_kopeika(T_K, rh_pct, wind_ms, W):
    """Cn2 [m^-2/3] at 15 m from the weather (Sadot & Kopeika 1992):

    Cn2 = 3.8e-14 W + 2.0e-15 T - 2.5e-15 U + 1.2e-15 U^2 - 8.5e-17 U^3 - 2.8e-15 RH + 2.9e-17 RH^2 - 1.1e-19 RH^3
          - 5.3e-13
    T air temperature [K], RH relative humidity [%], U wind speed [m/s], W temporal-hour weight.  A regression: it can
    be <= 0 outside the fitted regime (valid for 9 - 35 C, RH 14 - 92 %, U 0 - 10 m/s)."""
    T, rh, U, W = float(T_K), float(rh_pct), float(wind_ms), float(W)
    return (3.8e-14 * W + 2.0e-15 * T - 2.5e-15 * U + 1.2e-15 * U ** 2 - 8.5e-17 * U ** 3 - 2.8e-15 * rh +
            2.9e-17 * rh ** 2 - 1.1e-19 * rh ** 3 - 5.3e-13)


def sk_out_of_range(T_K, rh_pct, wind_ms):
    """Inputs outside the validity range of the Sadot & Kopeika regression (list of text, empty = inside)."""
    out = []
    t_c = float(T_K) - 273.15
    for name, v, (lo, hi), unit in (("air temperature", t_c, SK_VALID["T_C"], "C"),
                                    ("relative humidity", float(rh_pct), SK_VALID["rh_pct"], "%"),
                                    ("wind speed", float(wind_ms), SK_VALID["wind_ms"], "m/s")):
        if not lo <= v <= hi:
            out.append("%s %.3g %s (valid %g - %g %s)" % (name, v, unit, lo, hi, unit))
    return out


# ---------------------------------------------------------------------------------------------
# Turbulence: anisoplanatism (isoplanatic angle, image tilt, tilt correlation)
# ---------------------------------------------------------------------------------------------
ANISO_TILT_IFOV = 0.5             # rms image tilt [IFOV] from which a distortion within the target is visible


def isoplanatic_angle(lam_um, R_km, cn2_of_z, n=801):
    """(theta0 [rad], h_bar [m], plane-wave r0 [m]) of a line of sight of length R (Fried 1982).

    theta0 = [2.914 k^2 Int Cn2(z) z^(5/3) dz]^(-3/5) = 0.314 r0 / h_bar, with the plane-wave (unweighted) r0 =
    [0.423 k^2 Int Cn2 dz]^(-3/5) and h_bar = [Int Cn2 z^(5/3) dz / Int Cn2 dz]^(3/5).  z is the distance from the
    imager: rays from two object points theta apart are theta z apart at the distance z from the aperture, so the
    weight z^(5/3) puts the turbulence at the target end first (the spherical-wave r0 of TRM4 Eq. 4.82 weights the
    imager end).  cn2_of_z(z) as for mtf.fried_parameter."""
    R = float(R_km) * 1000.0
    if R <= 0:
        return float("inf"), 0.0, float("inf")
    z = np.linspace(0.0, R, n)
    c = cn2_of_z(z)
    i0 = float(np.trapezoid(c, z))
    i53 = float(np.trapezoid(c * z ** (5.0 / 3.0), z))
    if not (i0 > 0 and i53 > 0):
        return float("inf"), 0.0, float("inf")
    k2 = (2.0 * math.pi / (float(lam_um) * 1e-6)) ** 2
    return (2.914 * k2 * i53) ** -0.6, (i53 / i0) ** 0.6, (0.423 * k2 * i0) ** -0.6


def cn2_uniform_from_r0(r0_m, lam_um, L_km):
    """Uniform Cn2 [m^-2/3] of a path of length L with the spherical-wave Fried parameter r0 at lambda (TRM4 Eq. 4.82:
    r0 = 0.185 (3 Cn2 L / (8 lambda^2))^(-3/5))."""
    lam, L = float(lam_um) * 1e-6, float(L_km) * 1000.0
    return 8.0 * lam ** 2 / (3.0 * L) * (float(r0_m) / 0.185) ** (-5.0 / 3.0)


def tilt_rms(lam_um, r0_m, D_m):
    """One-axis rms image tilt [rad], Z-tilt sigma^2 = 0.182 (lambda / D)^2 (D / r0)^(5/3).  With the spherical-wave
    r0 of a horizontal path it reproduces the tilt variance of Hardie et al. 2021, Table 2 (within 0.5 %)."""
    if not (np.isfinite(r0_m) and r0_m > 0):
        return 0.0
    lam = float(lam_um) * 1e-6
    return math.sqrt(0.182 * (lam / float(D_m)) ** 2 * (float(D_m) / float(r0_m)) ** (5.0 / 3.0))


def tilt_correlation_angle(D_m, R_km):
    """Angle [rad] over which the image tilt stays correlated, of order D / L.  For a spherical wave the ray bundles of
    two object points theta apart are D (1 - z/L) wide and theta z apart at the distance z from the aperture: at theta
    = D / L they separate over the target half of the path, and parts of an extended target further apart move
    independently.  Literature: about 120 urad for 1 km and a 6 cm aperture (~2 D/L) against theta0 ~ 1.3 urad."""
    return float(D_m) / max(float(R_km) * 1000.0, 1e-9)


# ---------------------------------------------------------------------------------------------
# Turbulence: scintillation (point / sub-pixel targets, active illumination)
# ---------------------------------------------------------------------------------------------
# weak fluctuations: Rytov variance < 1 (Andrews & Phillips 2005); for the spherical wave it is beta0^2 = 0.5 Cn2
# k^(7/6) L^(11/6) ~ 4 sigma_A^2, so the weak regime ends at sigma_A^2 = 0.25
SCINT_WEAK_SIGMA_A2 = 0.25
SCINT_WARN_SIGMA_I = 0.10         # rms intensity fluctuation from which a relevant case is warned about


def scint_log_amplitude_variance(lam_um, L_km, cn2):
    """Log-amplitude variance sigma_A^2 = 0.124 k^(7/6) L^(11/6) Cn2 of a spherical wave over a path of length L in
    weak turbulence (Weiss-Wrana, FGAN-FOM 2005/09); cn2 [m^-2/3] uniform, or the path average of scint_path_cn2."""
    k = 2.0 * math.pi / (float(lam_um) * 1e-6)
    return 0.124 * k ** (7.0 / 6.0) * (float(L_km) * 1000.0) ** (11.0 / 6.0) * float(cn2)


def scint_path_cn2(R_km, cn2_of_z, n=801):
    """Cn2 [m^-2/3] of a line of sight of length R averaged with the spherical-wave weight w(z) = [z (L - z) / L]^(5/6)
    of the Rytov theory, so that scint_log_amplitude_variance gives 0.124 / B(11/6, 11/6) k^(7/6) Int Cn2(z) w(z) dz =
    0.562 k^(7/6) Int Cn2 w dz.  The weight is symmetric (either end may be the source) and largest at mid-path;
    a uniform Cn2 is returned unchanged.  cn2_of_z(z) as for isoplanatic_angle."""
    R = float(R_km) * 1000.0
    if R <= 0:
        return 0.0
    z = np.linspace(0.0, R, n)
    w = (z * (R - z) / R) ** (5.0 / 6.0)
    return float(np.trapezoid(cn2_of_z(z) * w, z) / np.trapezoid(w, z))


def scint_intensity_variance(sigma_A2):
    """Normalized intensity variance (scintillation index) at a point, sigma_I^2 = exp(4 sigma_A^2) - 1 (log-normal
    intensity; ~ 4 sigma_A^2 = 0.5 k^(7/6) L^(11/6) Cn2 in weak turbulence).  inf where exp overflows."""
    x = 4.0 * float(sigma_A2)
    return math.expm1(x) if x < 700.0 else float("inf")


def aperture_averaging_spherical(lam_um, L_km, D_m):
    """(A, k D^2 / 4L): aperture-averaging factor A = sigma_I^2(D) / sigma_I^2(0) of a spherical wave in weak
    turbulence, A = [1 + 0.214 (k D^2 / 4L)^(7/6)]^-1 (Churnside, Appl. Opt. 30, 1982 (1991)).  1 for an aperture much
    smaller than the Fresnel zone sqrt(lambda L), ~ D^(-7/3) for a much larger one."""
    x = 2.0 * math.pi / (float(lam_um) * 1e-6) * float(D_m) ** 2 / (4.0 * max(float(L_km) * 1000.0, 1e-9))
    return 1.0 / (1.0 + 0.214 * x ** (7.0 / 6.0)), x


def scintillation(lam_um, R_km, cn2_of_z, D_m, n=801):
    """Scintillation of a point source at the range R seen through the aperture D (spherical wave, weak turbulence):
    dict with the path-weighted Cn2 `cn2`, `sigma_A2`, the point value `sigma_I2_0` = exp(4 sigma_A^2) - 1, the
    aperture-averaging factor `A` and `x` = k D^2 / 4L, the value through the aperture `sigma_I2` = A sigma_I2_0 and
    `weak` (4 sigma_A^2 < 1; outside it the weak-turbulence values over-predict the saturating scintillation)."""
    c = scint_path_cn2(R_km, cn2_of_z, n)
    sa2 = scint_log_amplitude_variance(lam_um, R_km, c)
    si2 = scint_intensity_variance(sa2)
    A, x = aperture_averaging_spherical(lam_um, R_km, D_m)
    return {"cn2": c, "sigma_A2": sa2, "sigma_I2_0": si2, "A": A, "x": x, "sigma_I2": A * si2,
            "weak": sa2 < SCINT_WEAK_SIGMA_A2}


# ---------------------------------------------------------------------------------------------
# Turbulence: exposure time, short-exposure regime, mitigation
# ---------------------------------------------------------------------------------------------
def tilt_removed_exposure(D_m, wind_ms, tau_s):
    """Fraction of the image tilt that does not blur an exposure of tau seconds (frozen flow at crosswind v).

    During the exposure the aperture sweeps a strip of length D + v tau through the turbulence (effective-aperture
    model of Azoulay, FGAN-FOM, as used by Weiss-Wrana 2003); the tilt common to the strip moves the whole image, the
    rest blurs it.  With the Z-tilt variance ~ D^(-1/3): a = (D / (D + v tau))^(1/3) - 1 for a frozen snapshot (short
    exposure), -> 0 for long exposures.  Turbulence evolution during tau (boiling) is neglected (it adds blur)."""
    D, s = float(D_m), max(float(wind_ms), 0.0) * max(float(tau_s), 0.0)
    return (D / (D + s)) ** (1.0 / 3.0) if D > 0 else 0.0


def se_factor_auto(D_m, lam_um, R_km):
    """Factor of Fried's short-exposure term from the Fresnel ratio Q = D / sqrt(lambda L): 1/2 for Q << 1 (far
    field), 1 for Q >= 1 (near field; Tofsted: the near-field form holds down to Q ~ 1), linear in between (an
    interpolation between the two published limits)."""
    L = max(float(R_km), 1e-9) * 1000.0
    q = float(D_m) / math.sqrt(float(lam_um) * 1e-6 * L)
    return 0.5 + 0.5 * min(1.0, q), q


# Fried 1978: a short exposure is "lucky" when its tilt-removed phase variance over the aperture is <= 1 rad^2.  The
# mean tilt-removed variance is 0.134 (D/r0)^(5/3) rad^2 (Noll 1976), so a lucky frame behaves like D/r0 = 3.34.
LUCKY_DR0 = (1.0 / 0.134) ** 0.6


def lucky_probability(D_over_r0):
    """Probability of a lucky short exposure, Fried (1978) P = 5.6 exp[-0.1557 (D/r0)^2] (D/r0 >= 3.5; capped at 1)."""
    x = float(D_over_r0)
    if x <= LUCKY_DR0:
        return 1.0
    return min(1.0, 5.6 * math.exp(-0.1557 * x * x))


# ---------------------------------------------------------------------------------------------
# Turbulence statistics: Cn2 at sunrise and under an overcast sky (Weiss-Wrana, FGAN-FOM 2003 / 2005)
# ---------------------------------------------------------------------------------------------
# typical daily minimum around sunrise in the arid summer (Negev, Israel): about 1e-15 measured at 2.3 m (FGAN-FOM
# 2005/09), scaled to the 2 m of Table C.2 with the neutral-condition exponent -2/3: 1e-15 (2.3 / 2)^(2/3) = 1.1e-15
CN2_SUNRISE_ARID_SUMMER = 1.1e-15
OVERCAST_NOON_FACTOR = 0.1           # clouds reduce the midday Cn2 by 1 - 2 orders of magnitude; the smaller is used


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
