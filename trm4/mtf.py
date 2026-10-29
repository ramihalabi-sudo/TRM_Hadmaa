"""Component MTF equations (Chapter 4 and Appendix B of the TRM4.v3 documentation).

All MTFs are functions of the object-space spatial frequency r [cycles/mrad].  They return
signed values where the physical transfer function can change sign (sinc-type functions);
this matters for the AMOP simulation.
"""
import numpy as np
from .physics import sinc, sinc_ratio, j0, j1, jinc_mtf


# ---------------------------------------------------------------------------------------------
# Appendix B: diffraction limited MTF from the overlap area of two displaced pupils
# ---------------------------------------------------------------------------------------------
def pupil_overlap(D, D_obsc, W_along, W_perp, n_rows=3000, n_shift=700):
    """Normalized overlap area of the pupil with itself displaced along one direction.

    D        aperture diameter [mm] (0 -> rectangular aperture W_along x W_perp)
    D_obsc   diameter of the circular central obscuration [mm]
    W_along  width of the (symmetrically) truncated pupil in the shift direction [mm] (0: none)
    W_perp   width of the truncated pupil perpendicular to the shift direction [mm] (0: none)

    Returns (d [mm], overlap(d)/overlap(0), clear pupil area [mm^2]).
    The pupil is sliced into rows parallel to the shift direction; in each row the pupil is a set
    of at most two intervals, so the overlap of shifted rows is computed exactly (Eq. B.1).
    """
    R = 0.5 * D
    Ro = 0.5 * D_obsc
    rect = D <= 0
    if rect:
        if W_along <= 0 or W_perp <= 0:
            raise ValueError("Rectangular aperture needs both truncation widths > 0")
        T_along, T_perp = 0.5 * W_along, 0.5 * W_perp
        y_max = T_perp
    else:
        T_along = 0.5 * W_along if W_along > 0 else R
        T_perp = 0.5 * W_perp if W_perp > 0 else R
        y_max = min(R, T_perp)
    y = (np.arange(n_rows) + 0.5) / n_rows * 2 * y_max - y_max
    dy = 2 * y_max / n_rows
    if rect:
        xo = np.full_like(y, T_along)
    else:
        xo = np.minimum(np.sqrt(np.maximum(R * R - y * y, 0.0)), T_along)
    xi = np.where(np.abs(y) < Ro, np.sqrt(np.maximum(Ro * Ro - y * y, 0.0)), 0.0)
    xi = np.minimum(xi, xo)
    # two intervals per row: [-xo, -xi] and [xi, xo]
    starts = np.stack([-xo, xi])        # (2, rows)
    ends = np.stack([-xi, xo])
    d = np.linspace(0.0, 2 * T_along, n_shift)
    total = np.zeros_like(d)
    for a in range(2):
        for b in range(2):
            lo = np.maximum(starts[a][None, :], starts[b][None, :] + d[:, None])
            hi = np.minimum(ends[a][None, :], ends[b][None, :] + d[:, None])
            total += np.clip(hi - lo, 0.0, None).sum(axis=1)
    area = total[0] * dy
    return d, total / total[0], area


class DiffractionMTF:
    """Tabulated diffraction MTF for one direction: MTF(r, lambda) = O(lambda * r)."""

    def __init__(self, D, D_obsc, W_along, W_perp):
        self.d, self.o, self.area = pupil_overlap(D, D_obsc, W_along, W_perp)
        self.d_max = self.d[-1]

    def __call__(self, r, lam_um):
        # pupil displacement [mm] = lambda [um] * r [1/mrad]
        disp = np.abs(np.asarray(r, float)) * lam_um
        return np.interp(disp, self.d, self.o, right=0.0)


# ---------------------------------------------------------------------------------------------
# 4.2.1 Optics aberrations
# ---------------------------------------------------------------------------------------------
def mtf_blur(r, sigma_blur_um, f_mm):
    """Gaussian blur aberration, Eq. (4.14)."""
    return np.exp(-2.0 * (np.pi * sigma_blur_um / f_mm * np.asarray(r, float)) ** 2)


# ---------------------------------------------------------------------------------------------
# 4.2.3 Detector MTFs
# ---------------------------------------------------------------------------------------------
def mtf_det_geometry(r, shape, a_um, f_mm, d_um=0.0, d_hole_um=0.0):
    """Static detector geometry MTF, Eqs. (4.21)-(4.24)."""
    r = np.asarray(r, float)
    if shape == "rectangular":
        return sinc(a_um / f_mm * r)
    if shape == "rhombic":
        return sinc(a_um / (2.0 * f_mm) * r) ** 2
    if shape == "circular":
        return jinc_mtf(d_um / f_mm * r)
    if shape == "loophole":
        d, dh = d_um, d_hole_um
        u = np.pi * r / f_mm
        out = np.ones_like(r)
        nz = np.abs(r) > 1e-12
        out[nz] = 2.0 / (np.pi * d * (1 - dh ** 2 / d ** 2) * r[nz] / f_mm) * (
            j1(u[nz] * d) - dh / d * j1(u[nz] * dh))
        return out
    raise ValueError("unknown detector shape %s" % shape)


def mtf_binning(r, n_bin, pitch_um, f_mm):
    """Pixel binning, Eq. (4.26)."""
    return sinc_ratio(n_bin, pitch_um / f_mm * np.asarray(r, float))


def mtf_pseudo_interlace(r, pitch_v_um, f_mm):
    """Electronic pseudo-interlace (vertical), Eq. (4.27)."""
    return np.cos(np.pi * pitch_v_um / f_mm * np.asarray(r, float))


def mtf_cte(r, n_transfer, cte, pitch_um, f_mm):
    """Charge transfer efficiency, Eq. (4.28)."""
    r_stage = f_mm / pitch_um
    return np.exp(-n_transfer * (1.0 - cte) * (1.0 - np.cos(2 * np.pi * np.asarray(r, float) / r_stage)))


def crosstalk_diffusion_constant(mtf_geo_at_nyq, mtf_spec_at_nyq, r_nyq):
    """Diffusion constant from the MTF specified at Nyquist, Eq. (4.30)."""
    if mtf_spec_at_nyq <= 0 or mtf_spec_at_nyq >= mtf_geo_at_nyq:
        return 0.0
    return 1.0 / (2 * np.pi * r_nyq) * np.sqrt(mtf_geo_at_nyq / mtf_spec_at_nyq - 1.0)


def mtf_crosstalk(r, D_diff):
    """Detector crosstalk, Eq. (4.29)."""
    return 1.0 / (1.0 + (2 * np.pi * D_diff * np.asarray(r, float)) ** 2)


def mtf_microscan_integration(r, kind, duty, pitch_um, f_mm, n_step, t_int, frame_rate):
    """MTF due to integration during micro-scan movement, Eqs. (4.36)-(4.39)."""
    r = np.asarray(r, float)
    if kind == "rectangular":
        return sinc(duty * pitch_um / (f_mm * n_step) * r)
    if kind == "diagonal":
        return sinc(duty * pitch_um / (2 * f_mm) * r)
    if kind == "circular":
        x = t_int * frame_rate
        corr = 1.0 - 0.084 * (4 * x) ** 2 * np.exp(-12.5 * (0.64 - np.sqrt(2) * x * pitch_um / f_mm * r) ** 2)
        return sinc(pitch_um / (2 * f_mm) * np.sin(np.pi * x) * r) * corr
    return np.ones_like(r)


def mtf_first_order_lowpass(nu, nu0):
    """First-order exponential response |1/(1 + i nu/nu0)|, Eqs. (4.17) and (4.40)."""
    return 1.0 / np.sqrt(1.0 + (np.asarray(nu, float) / nu0) ** 2)


# ---------------------------------------------------------------------------------------------
# 4.2.6 / 4.2.7 Digital filter and signal reconstruction
# ---------------------------------------------------------------------------------------------
def mtf_digital_filter(r, coef, kind, alpha_s):
    """Symmetric FIR filter, Eqs. (4.46) (odd) and (4.47) (even)."""
    r = np.asarray(r, float)
    c = np.asarray(coef, float)
    if kind == "odd":
        n = np.arange(5)
        s = c.sum()
        return (c[None, :] * np.cos(2 * np.pi * n[None, :] * alpha_s * r[..., None])).sum(-1) / s
    n = np.arange(1, 5)
    cc = c[1:5]
    s = cc.sum()
    return (cc[None, :] * np.cos(2 * np.pi * (n[None, :] - 0.5) * alpha_s * r[..., None])).sum(-1) / s


def mtf_replication(r, alpha_s, factor, kind):
    """Electronic zoom / line / column replication, Eqs. (4.52)-(4.56)."""
    factor = int(round(factor))
    if factor <= 1:
        return np.ones_like(np.asarray(r, float))
    m = sinc_ratio(factor, alpha_s * np.asarray(r, float) / factor)
    return m if kind == "pixel" else m ** 2


def mtf_diagonal_zoom(r, alpha_s):
    """Artificial zoom associated with diagonal micro-scan, Eq. (4.54)."""
    return np.cos(np.pi * alpha_s * np.asarray(r, float) / 2.0) ** 2


def mtf_flat_panel(r, r_s, zoom, rep):
    """Flat panel display with 100 % fill factor, Eqs. (4.63)/(4.64)."""
    return sinc(np.asarray(r, float) / (r_s * zoom * rep))


# ---------------------------------------------------------------------------------------------
# 4.2.10 Stabilization errors
# ---------------------------------------------------------------------------------------------
def mtf_random_vibration(r, sigma_mrad):
    return np.exp(-2 * np.pi ** 2 * sigma_mrad ** 2 * np.asarray(r, float) ** 2)


def mtf_sinusoidal_vibration(r, amp_mrad):
    return j0(2 * np.pi * amp_mrad * np.asarray(r, float))


def mtf_iir(r, alpha, n_frames, omega, frame_rate):
    """IIR frame integration smear, Eq. (4.72)."""
    r = np.asarray(r, float)
    ph = 2 * np.pi * n_frames * omega * r / frame_rate
    return (1 - alpha) / np.abs(1 - alpha * np.exp(-1j * ph))


# ---------------------------------------------------------------------------------------------
# 4.2.11 Additional MTFs
# ---------------------------------------------------------------------------------------------
def mtf_additional(r, kind, par):
    r = np.asarray(r, float)
    if kind == "sinc":
        return sinc(r / par)
    if kind == "sinc2":
        return sinc(r / par) ** 2
    if kind == "gaussian":
        return np.exp(-r ** 2 / (2 * par ** 2))
    if kind == "rectangular":
        return np.where(np.abs(r) <= par, 1.0, 0.0)
    return np.ones_like(r)


# ---------------------------------------------------------------------------------------------
# 4.2.12 Observer (eye-brain) MTF
# ---------------------------------------------------------------------------------------------
def eye_gamma(luminance_cd_m2, table):
    """Width of the eye point spread function (Table 4.2) interpolated in log10(fL)."""
    fl = max(luminance_cd_m2, 1e-6) / 3.426
    x = np.clip(np.log10(fl), table[0][0], table[-1][0])
    xs = [t[0] for t in table]
    ys = [t[1] for t in table]
    return float(np.interp(x, xs, ys))


def mtf_eye(r, gamma, m_sys):
    """Simplified Kornfeld-Lawson eye model, Eq. (4.79)."""
    return np.exp(-gamma * np.abs(np.asarray(r, float)) / m_sys)


# ---------------------------------------------------------------------------------------------
# 4.2.13 Turbulence
# ---------------------------------------------------------------------------------------------
def fried_parameter(lam_um, R_km, cn2_of_z, n=201):
    """Spherical-wave Fried parameter r0 [m], Eq. (4.82).

    cn2_of_z(z) returns Cn2 at distance z [m] from the imager along the line of sight; n integration points.
    """
    R = R_km * 1000.0
    if R <= 0:
        return np.inf
    z = np.linspace(0.0, R, n)
    integrand = ((R - z) / R) ** (5.0 / 3.0) * cn2_of_z(z)
    integral = np.trapezoid(integrand, z)
    lam = lam_um * 1e-6
    if integral <= 0:
        return np.inf
    return 0.185 * (integral / lam ** 2) ** (-3.0 / 5.0)


def mtf_turbulence(r, lam_um, r0_m, D_opt_mm, exposure, L0_m=0.0):
    """Turbulence MTF, Eqs. (4.80)-(4.83).

    L0_m > 0: von Karman outer scale, first-order correction of the phase structure function
    D(s) = 6.88 (s/r0)^(5/3) [1 - 1.485 (s/L0)^(1/3)], valid for s << L0 (Tokovinin 2002).
    """
    r = np.abs(np.asarray(r, float))
    if not np.isfinite(r0_m):
        return np.ones_like(r)
    sep = lam_um * r * 1e-3                      # pupil-plane separation [m]
    phi = 6.88 * (sep / r0_m) ** (5.0 / 3.0)
    if L0_m > 0:
        phi = phi * np.clip(1.0 - 1.485 * (sep / L0_m) ** (1.0 / 3.0), 0.0, None)
    if exposure == "short":
        D = D_opt_mm * 1e-3
        phi = phi * np.clip(1.0 - 0.5 * (sep / D) ** (1.0 / 3.0), 0.0, None)
    return np.exp(-0.5 * phi)
