"""Physical constants and numerical helper functions used throughout the TRM4 model.

Units convention (see TRM4.v3 documentation, Appendix A):
    wavelength            [um]
    detector dimensions   [um]
    focal length          [mm]      -> angles  um/mm = mrad
    spatial frequency     [1/mrad]  (object space, cycles per mrad)
    range                 [km]      -> target size m/km = mrad
    radiance              [W / (m^2 sr um)]
    irradiance            [W / (m^2 um)]
"""
import numpy as np

H = 6.62607015e-34        # Planck constant [J s]
C = 2.99792458e8          # speed of light [m/s]
KB = 1.380649e-23         # Boltzmann constant [J/K]
E_CHARGE = 1.602176634e-19  # electron charge [C]
KM = 683.0                # maximum luminous efficacy [lm/W]

trapz = np.trapezoid


def planck(lam_um, T):
    """Blackbody spectral radiance L(lambda, T) [W/(m^2 sr um)], Eq. (3.57)."""
    lam = np.asarray(lam_um, dtype=float) * 1e-6
    if T <= 0:
        return np.zeros_like(lam)
    x = H * C / (lam * KB * T)
    with np.errstate(over="ignore", divide="ignore"):
        L = 2.0 * H * C ** 2 / lam ** 5 / np.expm1(x)
    return np.nan_to_num(L) * 1e-6


def dplanck_dT(lam_um, T):
    """Temperature derivative of the Planck radiance [W/(m^2 sr um K)]."""
    lam = np.asarray(lam_um, dtype=float) * 1e-6
    if T <= 0:
        return np.zeros_like(lam)
    x = H * C / (lam * KB * T)
    L = planck(lam_um, T)
    with np.errstate(over="ignore"):
        factor = x / T / (-np.expm1(-x))
    return np.nan_to_num(L * factor)


def photons_per_joule(lam_um):
    """lambda / (h c) [photons/J]."""
    return np.asarray(lam_um, dtype=float) * 1e-6 / (H * C)


def sinc(x):
    """sinc(x) = sin(pi x)/(pi x), Eq. (4.10)."""
    return np.sinc(x)


def sinc_ratio(n, b):
    """sinc(n*b)/sinc(b) for integer n, with the correct limits at integer b.

    Appears in binning, zoom, replication, micro-scan and spatial noise terms.
    """
    b = np.asarray(b, dtype=float)
    n = int(round(n))
    if n <= 1:
        return np.ones_like(b)
    num = np.sin(np.pi * n * b)
    den = n * np.sin(np.pi * b)
    out = np.empty_like(b)
    small = np.abs(den) < 1e-10
    out[~small] = num[~small] / den[~small]
    k = np.round(b[small]).astype(np.int64)
    out[small] = np.where(((n - 1) * k) % 2 == 0, 1.0, -1.0)
    return out


def j0(x):
    """Bessel function of the first kind, order 0 (rational approximation)."""
    x = np.asarray(x, dtype=float)
    ax = np.abs(x)
    out = np.empty_like(ax)
    m = ax < 8.0
    y = x[m] ** 2
    a1 = 57568490574.0 + y * (-13362590354.0 + y * (651619640.7 + y * (-11214424.18 + y * (77392.33017 + y * (-184.9052456)))))
    a2 = 57568490411.0 + y * (1029532985.0 + y * (9494680.718 + y * (59272.64853 + y * (267.8532712 + y))))
    out[m] = a1 / a2
    axm = ax[~m]
    z = 8.0 / axm
    y = z * z
    xx = axm - 0.785398164
    a1 = 1.0 + y * (-0.1098628627e-2 + y * (0.2734510407e-4 + y * (-0.2073370639e-5 + y * 0.2093887211e-6)))
    a2 = -0.1562499995e-1 + y * (0.1430488765e-3 + y * (-0.6911147651e-5 + y * (0.7621095161e-6 - y * 0.934935152e-7)))
    out[~m] = np.sqrt(0.636619772 / axm) * (np.cos(xx) * a1 - z * np.sin(xx) * a2)
    return out


def j1(x):
    """Bessel function of the first kind, order 1 (rational approximation)."""
    x = np.asarray(x, dtype=float)
    ax = np.abs(x)
    out = np.empty_like(ax)
    m = ax < 8.0
    xm = x[m]
    y = xm ** 2
    a1 = xm * (72362614232.0 + y * (-7895059235.0 + y * (242396853.1 + y * (-2972611.439 + y * (15704.48260 + y * (-30.16036606))))))
    a2 = 144725228442.0 + y * (2300535178.0 + y * (18583304.74 + y * (99447.43394 + y * (376.9991397 + y))))
    out[m] = a1 / a2
    axm = ax[~m]
    z = 8.0 / axm
    y = z * z
    xx = axm - 2.356194491
    a1 = 1.0 + y * (0.183105e-2 + y * (-0.3516396496e-4 + y * (0.2457520174e-5 + y * (-0.240337019e-6))))
    a2 = 0.04687499995 + y * (-0.2002690873e-3 + y * (0.8449199096e-5 + y * (-0.88228987e-6 + y * 0.105787412e-6)))
    ans = np.sqrt(0.636619772 / axm) * (np.cos(xx) * a1 - z * np.sin(xx) * a2)
    out[~m] = np.where(x[~m] < 0, -ans, ans)
    return out


def jinc_mtf(u):
    """2 J1(pi u) / (pi u) with value 1 at u = 0 (circular aperture transform)."""
    u = np.asarray(u, dtype=float)
    out = np.ones_like(u)
    nz = np.abs(u) > 1e-12
    out[nz] = 2.0 * j1(np.pi * u[nz]) / (np.pi * u[nz])
    return out


def curve(points, lam, fill=0.0):
    """Piece-wise linear interpolation of tabulated (x, y) data; `fill` outside the table."""
    pts = np.asarray(points, dtype=float)
    return np.interp(lam, pts[:, 0], pts[:, 1], left=fill, right=fill)


def parse_table(text):
    """Parse two-column text ("x y" per line, '#' comments) into an (N, 2) array."""
    rows = []
    for line in str(text).splitlines():
        line = line.split("#")[0].replace(",", " ").replace(";", " ").strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        rows.append((float(parts[0]), float(parts[1])))
    rows.sort()
    return np.asarray(rows, dtype=float) if rows else np.zeros((0, 2))


def inverse_first_crossing(x, y, level):
    """Smallest x at which the non-decreasing envelope of y(x) reaches `level`.

    Returns None if the level is never reached and x[0] if already exceeded at the start.
    Used to invert MTDP/MDSP/MNDS curves (which may be non-monotonic for undersampled imagers).
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    env = np.maximum.accumulate(np.where(np.isfinite(y), y, np.inf))
    if level <= env[0]:
        return x[0]
    idx = np.nonzero(env >= level)[0]
    if idx.size == 0:
        return None
    i = idx[0]
    y0, y1 = env[i - 1], env[i]
    if not np.isfinite(y1) or y1 <= y0:
        return x[i]
    # interpolate in log-log space when possible
    if y0 > 0 and y1 > 0 and x[i - 1] > 0 and x[i] > 0:
        t = (np.log(level) - np.log(y0)) / (np.log(y1) - np.log(y0))
        return float(np.exp(np.log(x[i - 1]) + t * (np.log(x[i]) - np.log(x[i - 1]))))
    t = (level - y0) / (y1 - y0)
    return float(x[i - 1] + t * (x[i] - x[i - 1]))


def loglog_interp(x, xp, fp):
    """Interpolation in log-log space for positive data (clamped at the ends)."""
    xp = np.asarray(xp, float)
    fp = np.asarray(fp, float)
    good = (xp > 0) & (fp > 0) & np.isfinite(fp)
    if good.sum() < 2:
        return np.interp(x, xp, fp)
    return np.exp(np.interp(np.log(x), np.log(xp[good]), np.log(fp[good])))
