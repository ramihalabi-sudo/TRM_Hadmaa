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
# Line-of-sight jitter
# ---------------------------------------------------------------------------------------------
# residual LOS jitter commonly assumed in US Army NV-IPM calculations [49]; narrow fields of view are optimistic
# without it (the Gaussian jitter MTF is reasonable below about 1/3 IFOV, NVTherm [16])
TYPICAL_JITTER_MRAD = 0.070
