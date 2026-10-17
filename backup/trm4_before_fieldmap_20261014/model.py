"""TRM4 performance model (Chapter 3 of the TRM4.v3 documentation).

Scope of this implementation
----------------------------
Imager categories : Thermal (2nd generation cooled staring / micro-scanned FPA, uncooled FPA),
                    Visible/NIR/SWIR (CCD/CMOS staring) and General (staring).
Display           : flat panel (directly linked to the digital output).
Not implemented   : opto-mechanically scanned imagers (1st/2nd generation scanning), ICCD/ICMOS,
                    NVG and direct-view devices, CRT/LED displays and the analog video chain,
                    sky background, asymmetric aperture truncations.
External data     : optics MTF and spectral optics transmission can be imported from Zemax
                    OpticStudio exports (see zemax.py).
"""
import math
import numpy as np

from . import physics as ph
from . import mtf as M
from . import presets as P
from . import zemax as Z
from . import imports as IM
from .amop import amop as amop_sim

MODEL_VERSION = "TRM4.v3 model / TRM_HADMAAv1 engine 2.0"


class ModelError(Exception):
    pass


def _deg(x):
    return math.radians(float(x))


class Atmosphere:
    """One atmospheric condition.

    Fast mode: effective extinction coefficient sigma (Beer-Lambert, Eq. 2.29).
    Spectral mode: imported transmission tau(lambda, R) (e.g. MODTRAN), evaluated on the detector
    wavelength grid.  Path radiance is either modelled (Eqs. 3.107/3.108) or imported separately -
    it is never derived from the direct-path transmittance of an imported file.
    """

    def __init__(self, label, sigma, tau0, T_air, F_PR, spec=None, path=None):
        self.label = label
        self.sigma = float(sigma)
        self.tau0 = float(tau0)
        self.T_air = float(T_air)
        self.F_PR = float(F_PR)
        self.spec = spec              # {"lam", "R", "tau"} resampled to the model grid
        self.path = path              # {"lam", "R", "L"} resampled to the model grid
        self.band_w = None            # spectral weight for the band-effective scalar transmission

    def tau_lam(self, R_km):
        """Transmission on the model wavelength grid (array) or a scalar in fast mode."""
        if self.spec is None:
            return self.tau(R_km)
        R, tab = self.spec["R"], self.spec["tau"]
        if len(R) == 1:
            # Beer-Lambert per wavelength from one path length
            with np.errstate(divide="ignore"):
                k = -np.log(np.maximum(tab[:, 0], 1e-300)) / R[0]
            return np.exp(-k * R_km)
        if R_km <= R[0]:
            # between 0 and the first tabulated range: log-linear towards tau = 1
            return np.maximum(tab[:, 0], 1e-300) ** (R_km / R[0]) if R[0] > 0 else tab[:, 0]
        if R_km >= R[-1]:
            with np.errstate(divide="ignore"):
                k = -(np.log(np.maximum(tab[:, -1], 1e-300)) - np.log(np.maximum(tab[:, -2], 1e-300))) / \
                    (R[-1] - R[-2])
            return tab[:, -1] * np.exp(-k * (R_km - R[-1]))
        i = int(np.searchsorted(R, R_km))
        t = (R_km - R[i - 1]) / (R[i] - R[i - 1])
        lt = (1 - t) * np.log(np.maximum(tab[:, i - 1], 1e-300)) + t * np.log(np.maximum(tab[:, i], 1e-300))
        return np.exp(lt)

    def tau(self, R_km):
        """Band-effective (scalar) transmission; Beer-Lambert with initial transmission, Eq. (2.29)."""
        if self.spec is None:
            return self.tau0 * math.exp(-self.sigma * R_km)
        tl = self.tau_lam(R_km)
        w = self.band_w if self.band_w is not None else np.ones_like(tl)
        return float(ph.trapz(w * tl, self.spec["lam"]) / ph.trapz(w, self.spec["lam"]))

    def path_radiance(self, R_km, lam, tau_l):
        """Imported spectral path radiance at range R [W/(m^2 sr um)] on the model grid."""
        Rt, Lt = self.path["R"], self.path["L"]
        if len(Rt) == 1:
            # homogeneous path: L_path(R) = L_path(L_ref) (1 - tau(R)) / (1 - tau(L_ref))
            ref = self.tau_lam(Rt[0])
            ref = np.broadcast_to(ref, lam.shape)
            scale = (1 - np.broadcast_to(tau_l, lam.shape)) / np.maximum(1 - ref, 1e-9)
            return Lt[:, 0] * scale
        if R_km <= Rt[0]:
            return Lt[:, 0] * (R_km / Rt[0])
        if R_km >= Rt[-1]:
            return Lt[:, -1]
        i = int(np.searchsorted(Rt, R_km))
        t = (R_km - Rt[i - 1]) / (Rt[i] - Rt[i - 1])
        return (1 - t) * Lt[:, i - 1] + t * Lt[:, i]


class TRM4Model:
    def __init__(self, project, progress=None):
        self.p = P.deep_merge(P.DEFAULT_PROJECT, project or {})
        self.warnings = []
        self.progress = progress or (lambda msg, frac=None: None)
        self._amop_cache = {}
        self._turb_cache = {}
        self._jit_cache = {}
        # internal "what-if" switches used by the sensitivity / limiting-factor analysis (analysis.py)
        self.wi = dict(self.p.get("_what_if") or {})
        self.imports = []             # traceability of imported files: (what, name, sha256, notes)
        self.assumptions = []

    # -----------------------------------------------------------------------------------------
    def warn(self, msg):
        if msg not in self.warnings:
            self.warnings.append(msg)

    def assume(self, msg):
        if msg not in self.assumptions:
            self.assumptions.append(msg)

    def _record_import(self, what, fobj, notes=""):
        self.imports.append({"what": what, "name": fobj.get("name", ""), "sha256": IM.file_hash(fobj.get("text", "")),
                             "notes": notes})

    def source(self, path):
        """Data source of a parameter (provenance), 'preset' when not recorded."""
        return (self.p.get("provenance") or {}).get(path, "preset")

    # =========================================================================================
    # Geometry, sampling, display  (Sections 3.2 - 3.4)
    # =========================================================================================
    def _setup_geometry(self):
        p = self.p
        b, o, d, dsp, disp = p["basic"], p["optics"], p["detector"], p["dsp"], p["display"]
        self.cat = p["category"]
        if self.cat not in ("Thermal", "Visible", "General"):
            raise ModelError("Unknown imager category %r" % self.cat)
        self.uncooled = self.cat == "Thermal" and p["imager_type"] == "uncooled"
        self.lab = p["mode"]["environment"] == "lab"
        self.still = p["mode"]["stream"] == "still" or bool(p["mode"]["niirs"])

        fh = float(o["f_mm"])
        fv = float(o["f_v_mm"]) if o["diff_focal"] else fh
        if fh <= 0 or fv <= 0:
            raise ModelError("Focal length must be > 0")
        self.f = {"h": fh, "v": fv}
        self.f_eff = math.sqrt(fh * fv)                                   # Eq. (3.45)

        ms = b["microscan"]
        if ms == "rectangular":
            ns = {"h": max(1, int(b["ms_steps_h"])), "v": max(1, int(b["ms_steps_v"]))}
        elif ms in ("circular", "diagonal"):
            ns = {"h": 2, "v": 2}
        else:
            ms = "none"
            ns = {"h": 1, "v": 1}
        self.ms, self.nstep = ms, ns

        nb = {"h": max(1, int(b["bin_h"])), "v": max(1, int(b["bin_v"]))}
        self.nbin = nb
        self.shape = d["shape"]
        pitch = {"h": float(d["pitch_h_um"]), "v": float(d["pitch_v_um"])}
        if self.shape in ("circular", "loophole"):
            a = {"h": float(d["d_um"]), "v": float(d["d_um"])}
        else:
            a = {"h": float(d["a_h_um"]), "v": float(d["a_v_um"])}
        if min(pitch.values()) <= 0 or min(a.values()) <= 0:
            raise ModelError("Detector dimensions and pitch must be > 0")
        for z in "hv":
            if a[z] > pitch[z] * 1.0001:
                self.warn("Active detector dimension (%s) is larger than the pitch." % z)
        if self.shape == "rectangular":
            area = a["h"] * a["v"]
        elif self.shape == "rhombic":
            area = 0.5 * a["h"] * a["v"]
        elif self.shape == "circular":
            area = math.pi / 4 * d["d_um"] ** 2
        else:
            area = math.pi / 4 * (d["d_um"] ** 2 - d["d_hole_um"] ** 2)
        self.a_unbinned, self.pitch_unbinned = dict(a), dict(pitch)

        # --- pixel binning, Eqs. (3.1)-(3.5)
        n_el = {"h": int(d["n_h"]) // nb["h"], "v": int(d["n_v"]) // nb["v"]}
        a_eff = {z: a[z] + (nb[z] - 1) * pitch[z] for z in "hv"}
        pitch_eff = {z: pitch[z] * nb[z] for z in "hv"}
        area *= nb["h"] * nb["v"]
        n_stor = float(d["storage_e"]) * nb["h"] * nb["v"]
        # --- electronic pseudo interlace, Eqs. (3.6)-(3.8)
        self.interlace = b["interlace"]
        if self.interlace == "pseudo":
            area *= 2
            a_eff["v"] = pitch_eff["v"] + a_eff["v"]
            n_stor *= 2
        self.A_det = area * 1e-12                          # [m^2]
        self.n_stor = n_stor
        self.a_eff, self.pitch_eff = a_eff, pitch_eff
        self.n_el = n_el

        # --- samples, FOV, sampling distances, Eqs. (3.11), (3.41), (3.43), (3.44)
        self.n_sam = {z: n_el[z] * ns[z] for z in "hv"}
        self.fov = {z: ((self.n_sam[z] - 1) / ns[z] * pitch_eff[z] + a_eff[z]) / self.f[z] for z in "hv"}
        self.alpha_s = {z: pitch_eff[z] / (self.f[z] * ns[z]) for z in "hv"}
        self.r_s = {z: 1.0 / self.alpha_s[z] for z in "hv"}
        self.r_N = {z: 0.5 * self.r_s[z] for z in "hv"}
        self.das = {z: a_eff[z] / self.f[z] for z in "hv"}

        if b["fov_mode"] == "measured":
            for z, key in (("h", "fov_h_deg"), ("v", "fov_v_deg")):
                meas = float(b[key])
                calc = math.degrees(self.fov[z] * 1e-3)
                if meas > 0:
                    dev = abs(calc - meas) / meas
                    if dev > 0.10:
                        self.warn("Measured %s-FOV (%.3f deg) deviates by %.0f %% (>10 %%) from the calculated "
                                  "FOV (%.3f deg) - check the data." % (z, meas, 100 * dev, calc))
                    elif dev > 0.02:
                        self.warn("Measured %s-FOV deviates by %.1f %% from the calculated FOV; the calculated "
                                  "FOV is used." % (z, 100 * dev))

        # --- maximum integration time, Eqs. (3.74), (3.75)
        self.frame_rate = float(b["frame_rate"])
        if self.frame_rate <= 0:
            raise ModelError("Frame rate must be > 0")
        if ms == "diagonal":
            t_max = 1.0 / (self.frame_rate * 2)
        else:
            t_max = 1.0 / (self.frame_rate * ns["h"] * ns["v"])
        if self.interlace in ("electronic", "pseudo"):
            t_max /= 2
        self.t_max = t_max

        # --- signal processing factors
        self.zoom = max(1, int(round(dsp["zoom"])))
        self.lrep = max(1, int(round(dsp["lrep"])))
        self.crep = max(1, int(round(dsp["crep"])))
        self.rep = {"h": self.crep, "v": self.lrep}
        self.n_frames = max(1, int(dsp["n_frames"])) if dsp["frames_on"] else 1
        self.iir = float(dsp["iir_alpha"]) if dsp["iir_on"] else 0.0
        if not 0 <= self.iir < 1:
            raise ModelError("IIR alpha must be in [0, 1)")

        # --- display, number of displayed pixels (3.26), (3.28); magnification (3.16)
        self.n_fov = {"h": self.n_sam["h"] * self.zoom * self.crep, "v": self.n_sam["v"] * self.zoom * self.lrep}
        if self.n_fov["h"] > disp["n_h"] or self.n_fov["v"] > disp["n_v"]:
            self.warn("The flat panel display has fewer elements (%dx%d) than image pixels to be displayed "
                      "(%dx%d) - TRM4 treats this as a fatal inconsistency." %
                      (disp["n_h"], disp["n_v"], self.n_fov["h"], self.n_fov["v"]))
        if disp["observation"] == "eyepiece":
            dist_m = float(disp["f_eyepiece_mm"]) / 1000.0
        else:
            dist_m = float(disp["distance_cm"]) / 100.0
        self.m_sys = self.n_fov["v"] * float(disp["pitch_v_mm"]) / (self.fov["v"] * dist_m)
        self.gamma_eye = M.eye_gamma(float(disp["luminance"]), P.EYE_GAMMA)
        dist = abs(self.alpha_s["h"] * disp["pitch_v_mm"] * self.lrep /
                   (self.alpha_s["v"] * disp["pitch_h_mm"] * self.crep) - 1.0)    # Eq. (3.36)
        self.distortion = dist
        if dist > 0.02:
            self.warn("Geometrical distortion of the displayed image is %.1f %%." % (100 * dist))

        self.snr_th = float(disp["snr_th"])
        self.t_eye = float(disp["t_eye_s"])

    # =========================================================================================
    # Spectral data (Sections 3.5, 3.6)
    # =========================================================================================
    def _setup_spectral(self):
        p, d, t = self.p, self.p["detector"], self.p["target"]
        # detector spectral response
        if self.uncooled and d["uncooled_response"] == "flat":
            lo, hi = float(d["cuton_um"]), float(d["cutoff_um"])
            if hi <= lo:
                raise ModelError("Cut-off wavelength must be larger than cut-on wavelength")
            lam = np.linspace(lo, hi, 300)
            qe = np.full_like(lam, 100.0)
            self.qe_label = "flat %.1f-%.1f um" % (lo, hi)
        else:
            if d["qe_preset"] == "Custom":
                pts = ph.parse_table(d["qe_custom"])
                if len(pts) < 2:
                    raise ModelError("Custom spectral quantum efficiency needs at least two 'lambda[um] QE[%]' rows")
                if pts[:, 0].max() > 100.0:
                    pts[:, 0] /= 1000.0
                    self.warn("Custom QE wavelengths look like nm - converted to um.")
                unit = d.get("qe_unit", "auto")
                if unit == "fraction" or (unit == "auto" and pts[:, 1].max() <= 1.0):
                    pts[:, 1] *= 100.0
                    if unit == "auto":
                        self.warn("Custom QE values are all <= 1 and were interpreted as fractions (x100 %). "
                                  "Set the QE unit explicitly if this is wrong.")
                if pts[:, 1].min() < 0:
                    raise ModelError("Custom QE contains negative values")
                self.qe_label = "custom"
            else:
                pts = np.asarray(P.DETECTOR_QE[d["qe_preset"]], float)
                self.qe_label = d["qe_preset"]
            pos = np.nonzero(pts[:, 1] > 0)[0]
            if pos.size == 0:
                raise ModelError("Quantum efficiency is zero everywhere")
            lo = float(pts[max(pos[0] - 1, 0), 0])
            hi = float(pts[min(pos[-1] + 1, len(pts) - 1), 0])
            lam = np.linspace(lo, hi, 400)
            qe = ph.curve(pts, lam) * float(d["qe_scale"])
            if np.any(qe > 100.0001):
                self.warn("Spectral quantum efficiency exceeds 100 % - values are clipped.")
                qe = np.minimum(qe, 100.0)
        self.lam = lam
        self.eta = qe / 100.0
        self.tau_o = self._optics_transmission(lam)
        self.pp = ph.photons_per_joule(lam)
        self.band = (float(lam[0]), float(lam[-1]))
        # wavelength of peak responsivity, Eqs. (3.60)-(3.62)
        resp = lam * self.eta
        ip = int(np.argmax(resp))
        self.lam_peak, self.qe_peak = float(lam[ip]), float(qe[ip])

        # target / background temperatures, emissivity and reflectivity
        self.T_B = float(t["T_bg_K"])
        self.T_T = self.T_B + float(t["dT_K"])
        if self.cat == "Thermal":
            self.eps_T = np.ones_like(lam)
            self.eps_B = np.ones_like(lam)
            self.rho_T = np.zeros_like(lam)
            self.rho_B = np.zeros_like(lam)
        elif self.cat == "Visible":
            self.eps_T = np.zeros_like(lam)
            self.eps_B = np.zeros_like(lam)
            self.rho_T = self._refl(t["t_refl_mode"], t["t_refl"], t["t_refl_preset"])
            self.rho_B = self._refl(t["b_refl_mode"], t["b_refl"], t["b_refl_preset"])
        else:
            self.eps_T = self._emis(t["t_emis_mode"], t["t_emis"], t["t_emis_preset"])
            self.eps_B = self._emis(t["b_emis_mode"], t["b_emis"], t["b_emis_preset"])
            self.rho_T = 1.0 - self.eps_T                     # emissivity + reflectivity = 1
            self.rho_B = 1.0 - self.eps_B
        self.L_T = ph.planck(lam, self.T_T)
        self.L_B = ph.planck(lam, self.T_B)
        self.I = self._irradiance()
        if self.qe_label in P.DETECTOR_QE:
            self.assume("Detector QE is the generic preset curve '%s' (digitised approximately from TRM4 "
                        "Appendix C), not the curve of this detector." % self.qe_label)
        spectral_mat = [m for m in ("t_refl", "b_refl", "t_emis", "b_emis")
                        if (self.cat == "Visible" and "refl" in m or self.cat == "General" and "emis" in m)
                        and t["%s_mode" % m] == "spectral"]
        if spectral_mat:
            self.assume("Target/background spectral reflectivity or emissivity from approximate preset materials.")
        if not self.p["display"]["neglect_eye"]:
            self.assume("Standard observer: Kornfeld-Lawson eye MTF, threshold SNR %.2g, eye integration %.3g s." %
                        (float(self.p["display"]["snr_th"]), float(self.p["display"]["t_eye_s"])))

    def _optics_transmission(self, lam):
        """Optics x filter transmission: a constant, or spectral data imported from Zemax."""
        o = self.p["optics"]
        tau_f = float(o["tau_filter"])
        for key, val in (("Optics transmission", float(o["tau_opt"])), ("Filter transmission", tau_f)):
            if not 0.0 <= val <= 1.0:
                raise ModelError("%s must be within [0, 1] (is %g)" % (key, val))
        if o.get("tau_mode") != "zemax":
            self.tau_label = "%.3g (constant)" % float(o["tau_opt"])
            return float(o["tau_opt"]) * tau_f
        zt = o.get("zemax_tau") or {}
        if not zt.get("text"):
            raise ModelError("Optics transmission via Zemax file selected, but no transmission file was imported")
        try:
            wl, tau, note = Z.parse_transmission(zt["text"])
        except ValueError as e:
            raise ModelError("Zemax transmission file %s: %s" % (zt.get("name", ""), e))
        self._record_import("Optics transmission", zt, note)
        if wl[0] > lam[0] + 1e-6 or wl[-1] < lam[-1] - 1e-6:
            self.warn("Transmission data (%.3g-%.3g um) does not cover the detector spectral window "
                      "(%.3g-%.3g um); the edge values are held constant." % (wl[0], wl[-1], lam[0], lam[-1]))
        t = np.interp(lam, wl, tau)
        kind = o.get("tau_kind", "absolute")
        if kind == "normalized":
            if t.max() <= 0:
                raise ModelError("Normalized transmission curve is zero in the detector band")
            t = t / tau.max() * float(o["tau_opt"])
            note += ", normalized x peak %.3g" % float(o["tau_opt"])
        elif tau.max() >= 0.999:
            self.warn("Imported transmission reaches 1.0 - if the curve is normalized (not absolute), select "
                      "'normalized' so that the peak transmission is applied.")
        if o.get("tau_scope") == "system":
            if abs(tau_f - 1.0) > 1e-9:
                self.warn("Imported transmission covers the complete optical train (incl. filter/window); the "
                          "additional filter transmission %.3g is NOT applied to avoid counting it twice." % tau_f)
            tau_f = 1.0
            note += ", full system throughput"
        self.tau_label = "Imported: %s (%s, %s)" % (zt.get("name", ""), note, kind)
        return t * tau_f

    def _refl(self, mode, value, preset):
        if mode == "spectral":
            # outside the band of the external data the reflectivity is assumed to be 0 (Sec. 3.5.2)
            return ph.curve(P.REFLECTIVITY[preset], self.lam) / 100.0
        return np.full_like(self.lam, float(value))

    def _emis(self, mode, value, preset):
        if mode == "blackbody":
            return np.ones_like(self.lam)
        if mode == "grey":
            return np.full_like(self.lam, float(value))
        e = np.asarray(P.EMISSIVITY[preset], float)
        eps = np.interp(self.lam, e[:, 0], e[:, 1]) / 100.0
        if preset in P.REFLECTIVITY:
            short = self.lam < e[0, 0]
            eps[short] = 1.0 - ph.curve(P.REFLECTIVITY[preset], self.lam[short], fill=0.0) / 100.0
        return np.clip(eps, 0.0, 1.0)

    def _irradiance(self):
        """Spectral irradiance of the illumination source at the target plane [W/(m^2 um)] (Sec. 2.26)."""
        irr = self.p["irradiance"]
        lam = self.lam
        self.irr_extended = True
        if self.cat == "Thermal" or irr["mode"] == "none":
            if self.cat == "Visible":
                self.warn("Visible category requires an illumination source - no irradiance specified.")
            return np.zeros_like(lam)
        self.irr_extended = irr["geometry"] == "extended" or irr["type"] == "blackbody"
        typ = irr["type"]
        if typ == "blackbody":
            return math.pi * ph.planck(lam, float(irr["T_bb_K"]))
        if typ == "monochromatic":
            lam0 = float(irr["lambda_um"])
            out = np.zeros_like(lam)
            if lam0 < lam[0] or lam0 > lam[-1]:
                self.warn("Monochromatic source wavelength is outside the detector spectral window.")
                return out
            i = int(np.argmin(np.abs(lam - lam0)))
            dl = lam[1] - lam[0]
            out[i] = float(irr["E_mono"]) / (dl if 0 < i < len(lam) - 1 else 0.5 * dl)
            return out
        spec = irr["spectrum"]
        if spec == "effective":
            return np.full_like(lam, float(irr["E_eff"]) / (lam[-1] - lam[0]))
        if spec == "colour":
            T = float(irr["T_colour_K"])
            peak = ph.planck(np.array([2897.77 / T]), T)[0]
            return ph.planck(lam, T) / peak * float(irr["E_peak"])
        src = P.NATURAL_SOURCES[irr["preset"]]
        shape = src["shape"]
        if isinstance(shape, tuple):
            T = shape[1]
            peak = ph.planck(np.array([2897.77 / T]), T)[0]
            norm = ph.planck(lam, T) / peak
        else:
            norm = ph.curve(shape, lam)
        return norm * float(irr["E_peak"])

    # =========================================================================================
    # Atmosphere, scenario and target geometry (Sections 2.27, 3.6)
    # =========================================================================================
    def _setup_atmospheres(self):
        a = self.p["atmosphere"]
        self.atms = []
        path = self._load_path_radiance() if a.get("path_mode") == "import" and not self.lab else None
        if a["mode"] == "visibility" and self.cat != "Visible":
            self.warn("Visual range is only a valid atmosphere description for the Visible/NIR/SWIR category; it is "
                      "not converted to an infrared extinction coefficient - the extinction coefficients are used.")
        if a["mode"] == "spectral":
            spec = self._load_spectral_atmosphere()
            at = a["atm"][0]
            T_air = self.T_B if self.cat == "Thermal" else float(at["T_air_K"])
            F_PR = 0.0 if self.cat == "Thermal" else float(at["F_PR"])
            name = (a.get("spec_file") or {}).get("name", "") or "spectral data"
            self.atms.append(Atmosphere("Imported (%s)" % name, 0.0, 1.0, T_air, F_PR, spec=spec, path=path))
        else:
            for i, at in enumerate(a["atm"]):
                if not at.get("on"):
                    continue
                if a["mode"] == "visibility" and self.cat == "Visible":
                    V = float(at["V_km"])
                    if V <= 0:
                        raise ModelError("Visibility must be > 0")
                    sigma = 3.912 / V                                   # Koschmieder, Eq. (2.28)
                    label = "Atm %d (V=%g km)" % (i + 1, V)
                else:
                    sigma = float(at["sigma"])
                    label = "Atm %d (sigma=%g/km)" % (i + 1, sigma)
                if sigma < 0 or not 0 < float(at["tau0"]) <= 1:
                    raise ModelError("%s: extinction must be >= 0 and initial transmission in (0, 1]" % label)
                T_air = self.T_B if self.cat == "Thermal" else float(at["T_air_K"])
                F_PR = 0.0 if self.cat == "Thermal" else float(at["F_PR"])
                self.atms.append(Atmosphere(label, sigma, at["tau0"], T_air, F_PR, path=path))
            if self.atms and a.get("preset", "custom") != "custom":
                self.assume("Atmosphere: '%s' preset extinction for the %s band (typical engineering value, "
                            "horizontal path near ground)." % (a["preset"], P.band_of(*self.band)))
        if self.wi.get("no_atm"):
            self.atms = [Atmosphere(x.label, 0.0, 1.0, x.T_air, 0.0) for x in self.atms]
        if not self.atms and not self.lab:
            self.warn("No atmosphere activated - a transparent atmosphere is assumed.")
            self.atms.append(Atmosphere("No atmosphere", 0.0, 1.0, self.T_B, 0.0))
        # band weight for the effective scalar transmission of spectral atmospheres
        if self.cat == "Thermal":
            bw = self.lam * self.eta * self.tau_o * ph.dplanck_dT(self.lam, self.T_B)
        else:
            bw = self.lam * self.eta * self.tau_o * (np.abs(self.I * (self.rho_T - self.rho_B)) +
                                                     math.pi * np.abs(self.L_T * self.eps_T - self.L_B * self.eps_B))
        if not np.any(bw > 0):
            bw = self.lam * self.eta
        for x in self.atms:
            x.band_w = np.broadcast_to(bw, self.lam.shape)
        tg = self.p["target"]
        self.W, self.H, self.D = float(tg["W_m"]), float(tg["H_m"]), float(tg["D_m"])
        asp = tg["aspect"]
        if asp == "side":
            self.alpha_h = math.pi / 2
        elif asp == "diagonal":
            self.alpha_h = math.acos(self.W / math.hypot(self.W, self.D)) if (self.W or self.D) else 0.0
        else:
            self.alpha_h = 0.0
        if tg["flight"] == "altitude" and float(tg["altitude_m"]) < 0 or \
                tg["flight"] == "angle" and float(tg["angle_deg"]) < 0:
            self.warn("Upward looking geometry (sky background) is not implemented; the background is "
                      "treated as a Lambertian plane.")

    def _spectral_on_grid(self, lam_f, table, what):
        lo, hi = self.lam[0], self.lam[-1]
        if lam_f[0] > lo + 1e-6 or lam_f[-1] < hi - 1e-6:
            self.warn("%s (%.3g-%.3g um) does not cover the detector spectral window (%.3g-%.3g um); edge values "
                      "are held constant." % (what, lam_f[0], lam_f[-1], lo, hi))
        return np.stack([np.interp(self.lam, lam_f, table[:, j]) for j in range(table.shape[1])], axis=1)

    def _load_spectral_atmosphere(self):
        a = self.p["atmosphere"]
        fobj = a.get("spec_file") or {}
        if not fobj.get("text"):
            raise ModelError("Spectral atmosphere selected, but no transmission file was imported")
        try:
            d = IM.parse_spectral_atmosphere(fobj["text"], float(a.get("spec_L_km", 1.0)))
        except ValueError as e:
            raise ModelError("Spectral atmosphere file %s: %s" % (fobj.get("name", ""), e))
        self._record_import("Atmospheric transmission", fobj, "; ".join(d["notes"]))
        return {"lam": self.lam, "R": d["R"],
                "tau": self._spectral_on_grid(d["lam"], d["tau"], "Atmospheric transmission data")}

    def _load_path_radiance(self):
        a = self.p["atmosphere"]
        fobj = a.get("path_file") or {}
        if not fobj.get("text"):
            raise ModelError("Imported path radiance selected, but no path radiance file was imported")
        try:
            d = IM.parse_path_radiance(fobj["text"], float(a.get("path_L_km", 1.0)))
        except ValueError as e:
            raise ModelError("Path radiance file %s: %s" % (fobj.get("name", ""), e))
        self._record_import("Path radiance", fobj, "; ".join(d["notes"]))
        return {"lam": self.lam, "R": d["R"], "L": self._spectral_on_grid(d["lam"], d["L"], "Path radiance data")}

    def los_angle(self, R_km):
        """Vertical line-of-sight angle alpha_v [rad] at slant range R (constant altitude/angle)."""
        tg = self.p["target"]
        if self.lab:
            return 0.0
        if tg["flight"] == "angle":
            return _deg(tg["angle_deg"])
        h = float(tg["altitude_m"])
        if h == 0:
            return 0.0
        R_m = max(R_km * 1000.0, 1e-9)
        return math.asin(max(-1.0, min(1.0, h / R_m)))

    def min_range(self):
        tg = self.p["target"]
        if tg["flight"] == "altitude":
            return abs(float(tg["altitude_m"])) / 1000.0
        return 0.0

    def target_dims(self, av):
        """Effective target dimensions and projected area, Eqs. (3.81), (3.83), (3.84)."""
        W, H, D, ah = self.W, self.H, self.D, self.alpha_h
        a_h = W * math.cos(ah) + D * math.sin(ah)
        s = abs(math.sin(av))
        a_v = H * math.cos(av) + (W * D * s / a_h if a_h > 0 else 0.0)
        A = a_h * H * math.cos(av) + W * D * s
        return a_h, a_v, A

    def irr_factors(self, av):
        """Irradiative correction factors F_irr,T and F_irr,B, Eqs. (3.96)-(3.99)."""
        if self.cat == "Thermal" or self.irr_extended:
            return 1.0, 1.0
        irr = self.p["irradiance"]
        bh, bv = _deg(irr["beta_h_deg"]), _deg(irr["beta_v_deg"])
        if self.lab:
            f = max(0.0, math.cos(bh) * math.cos(bv))
            return f, f
        ah = self.alpha_h
        W, H, D = self.W, self.H, self.D
        A_front = W * H * math.cos(ah) * math.cos(av)
        A_side = D * H * math.sin(ah) * math.cos(av)
        A_top = W * D * math.sin(abs(av)) if av > 0 else 0.0
        _, _, A_tar = self.target_dims(av)
        num = A_front * math.cos(bh) * math.cos(bv) + A_side * math.sin(bh) * math.cos(bv) + \
            A_top * math.sin(abs(bv))
        F_T = max(0.0, num / A_tar) if A_tar > 0 else 0.0
        if abs(av) < 1e-9:
            F_B = max(0.0, math.cos(bh - ah) * math.cos(bv))
        else:
            F_B = max(0.0, math.sin(bv))
        return F_T, F_B

    # =========================================================================================
    # Optics (Sections 2.6, 3.4) and detector internal radiation (3.7.2)
    # =========================================================================================
    def _setup_optics(self):
        o = self.p["optics"]
        if o["aperture"] == "general":
            F = float(o["F_general"])
            if F <= 0:
                raise ModelError("Effective F-number must be > 0")
            D, Dobs, Wh, Wv = self.f_eff / F, 0.0, 0.0, 0.0
        else:
            D, Dobs = float(o["D_mm"]), float(o["D_obsc_mm"])
            Wh, Wv = float(o["W_trunc_h_mm"]), float(o["W_trunc_v_mm"])
            if D <= 0 and (Wh <= 0 or Wv <= 0):
                raise ModelError("Specify an aperture diameter or both truncation widths (rectangular aperture)")
            if D > 0 and Dobs >= D:
                raise ModelError("Central obscuration must be smaller than the aperture")
        self.diff = {"h": M.DiffractionMTF(D, Dobs, Wh, Wv), "v": M.DiffractionMTF(D, Dobs, Wv, Wh)}
        area = self.diff["h"].area
        self.A_pup = area
        self.D_eff = math.sqrt(4 * area / math.pi)                           # Eq. (3.48)
        self.F_eff = F if o["aperture"] == "general" else self.f_eff / self.D_eff  # Eq. (3.47)
        self.D_opt = D if D > 0 else math.hypot(Wh, Wv)                      # Eq. (3.49)
        if self.F_eff < 0.5:
            self.warn("Effective F-number %.2f is below 0.5 - impossible optical geometry (check focal length and "
                      "aperture)." % self.F_eff)
        F_spec = float(o.get("F_spec", 0.0))
        if F_spec > 0 and abs(F_spec - self.F_eff) / F_spec > 0.05:
            self.warn("Specified F-number F/%.2f is inconsistent with the calculated effective F-number F/%.2f "
                      "(%.0f %% difference) - the calculated value is used." %
                      (F_spec, self.F_eff, 100 * abs(F_spec - self.F_eff) / F_spec))

        d = self.p["detector"]
        F2 = self.F_eff ** 2
        if self.cat != "Visible" and not self.uncooled:
            if d["cs_mode"] == "fnumber":
                Fcs = float(d["cs_F"])
                eta_cs = (4 * Fcs ** 2 + 1) / (4 * F2 + 1)                    # Eq. (2.10)
            else:
                eta_cs = float(d["cs_eff"])
            if eta_cs > 1.0 + 1e-9:
                self.warn("Cold shield efficiency > 1 is not permitted (fatal in TRM4); limited to 1.")
                eta_cs = 1.0
            eta_min = 1.0 / (4 * F2 + 1)                                     # Eq. (3.52)
            if eta_cs < eta_min:
                self.warn("Cold shield efficiency below the hemispherical minimum; limited.")
                eta_cs = eta_min
            self.eta_cs = eta_cs
            self.F_cs = math.sqrt(max((eta_cs * (4 * F2 + 1) - 1) / 4, 0.0))
            T_opt = self.T_B + float(d["T_off_opt_K"])
            T_dev = self.T_B + float(d["T_off_dev_K"])
            T_cs = float(d["T_cs_K"])
            k = self.pp * self.eta
            j_opt = k * math.pi / (4 * F2 + 1) * ph.planck(self.lam, T_opt) * (1 - self.tau_o)      # (3.104)
            j_dev = k * math.pi / (4 * F2 + 1) * (1 - eta_cs) / eta_cs * ph.planck(self.lam, T_dev)  # (3.105)
            j_cs = k * math.pi * (1 - 1 / (4 * self.F_cs ** 2 + 1)) * ph.planck(self.lam, T_cs)     # (3.106)
            self.j_internal = float(ph.trapz(j_opt + j_dev + j_cs, self.lam))
            self.j_internal_parts = (float(ph.trapz(j_opt, self.lam)), float(ph.trapz(j_dev, self.lam)),
                                     float(ph.trapz(j_cs, self.lam)))
        else:
            self.eta_cs, self.F_cs = None, None
            self.j_internal = 0.0
            self.j_internal_parts = (0.0, 0.0, 0.0)

    # =========================================================================================
    # Carrier flux densities, signal and noise (Sections 3.7, 3.8)
    # =========================================================================================
    def flux(self, R_km, atm):
        """Integrated carrier flux densities [carriers/(s m^2)] for target and background at range R."""
        lab = atm is None
        tau = 1.0 if lab else atm.tau(R_km)
        tau_l = 1.0 if lab else atm.tau_lam(R_km)            # spectral array for imported atmospheres
        av = self.los_angle(R_km)
        F_T, F_B = self.irr_factors(av)
        F2 = self.F_eff ** 2
        k = self.pp * self.eta * self.tau_o
        emis_T = math.pi / (4 * F2) * self.L_T * self.eps_T                    # (3.110)
        emis_B = math.pi / (4 * F2) * self.L_B * self.eps_B
        refl_T = self.I * F_T * self.rho_T / (4 * F2)                          # (3.111)
        refl_B = self.I * F_B * self.rho_B / (4 * F2)
        jT = k * (emis_T + refl_T) * tau_l
        jB = k * (emis_B + refl_B) * tau_l
        path = np.zeros_like(self.lam)
        if not lab and atm.path is not None:
            path += math.pi / (4 * F2) * atm.path_radiance(R_km, self.lam, tau_l)       # imported L_path
        elif not lab:
            if self.cat != "Visible":
                T_air = atm.T_air
                path += math.pi / (4 * F2) * ph.planck(self.lam, T_air) * (1 - tau_l)    # (3.107)
            if self.cat != "Thermal":
                path += self.I * atm.F_PR * (1 - tau_l) / (4 * F2)                     # (3.108)
        j_path = float(ph.trapz(k * path, self.lam))
        jT_s = float(ph.trapz(jT, self.lam))
        jB_s = float(ph.trapz(jB, self.lam))
        return {"jT": jT_s + j_path + self.j_internal, "jB": jB_s + j_path + self.j_internal,
                "jT_scene": jT_s, "jB_scene": jB_s, "j_path": j_path, "dj": jT_s - jB_s, "tau": tau,
                "av": av}

    @property
    def j_dark(self):
        """Dark carrier flux density, Eq. (3.113)."""
        return float(self.p["detector"]["dark_A"]) / ph.E_CHARGE / self.A_det

    def t_int_for(self, jB):
        d = self.p["detector"]
        mode = d["tint_mode"]
        if mode == "direct":
            t = float(d["tint_ms"]) * 1e-3
            if t > self.t_max * 1.0001:
                self.warn("Integration time exceeds the maximum available time (duty cycle > 1).")
            return t
        if mode == "duty":
            return float(d["duty"]) * self.t_max
        # well fill, Eq. (3.76)
        pct = float(d["wellfill_pct"])
        if self.n_stor <= 0:
            raise ModelError("Well-fill option needs a storage capacity > 0")
        gain = float(d["electron_gain"])
        t = pct * self.n_stor / ((jB + self.j_dark) * self.A_det * gain * 100.0)
        if t > self.t_max:
            self.warn("Integration time for the requested well fill exceeds the maximum possible integration "
                      "time; the maximum is used.")
            t = self.t_max
        return t

    def dN_dT(self, t_int):
        """Carrier difference per Kelvin for the thermal NETD, derived from Eq. (3.110)."""
        F2 = self.F_eff ** 2
        dL = ph.dplanck_dT(self.lam, self.T_B)
        g = float(self.p["detector"]["electron_gain"])
        return float(ph.trapz(self.pp * math.pi / (4 * F2) * dL * self.tau_o * self.eta, self.lam)) * \
            self.A_det * t_int * g

    def n_quant(self, t_int):
        d = self.p["detector"]
        if d["adc_mode"] == "carriers":
            return float(d["lsb_e"]) / math.sqrt(12)                  # Eq. (2.12)
        if d["adc_mode"] == "mK" and self.cat == "Thermal":
            return float(d["lsb_mK"]) * 1e-3 * self.dN_dT(t_int) / math.sqrt(12)
        return 0.0

    def noise(self, jT, jB, t_int):
        """Temporal noise of an integrating detector [carriers], Eq. (3.130)."""
        d = self.p["detector"]
        NF, g = float(d["noise_figure"]), float(d["electron_gain"])
        var = (NF ** 2 * 0.5 * (jT + jB) + self.j_dark) * self.A_det * g ** 2 * t_int + \
            self.n_quant(t_int) ** 2 + float(d["noise_floor_e"]) ** 2
        return math.sqrt(var)

    def well_fill(self, jB, t_int):
        g = float(self.p["detector"]["electron_gain"])
        if self.n_stor <= 0:
            return float("nan")
        return 100.0 * t_int * (jB + self.j_dark) * self.A_det * g / self.n_stor     # Eq. (3.138)

    # -----------------------------------------------------------------------------------------
    def _setup_noise(self):
        """Temporal/spatial noise quantities that do not depend on range."""
        d = self.p["detector"]
        dsp = self.p["dsp"]
        a = self.iir
        # frame integration factor, Eq. (3.141)
        self.fr_int = self.n_frames * (1 + a) / (1 - a)
        if self.still:
            n_int = self.fr_int
        else:
            n_eye = max(1.0, self.frame_rate * self.t_eye / self.n_frames)
            corr = 1.0 - 2 * a / n_eye * (1 - a ** n_eye) / (1 - a ** 2) if a > 0 else 1.0
            n_int = self.frame_rate * self.t_eye / corr                             # Eq. (3.181)
            n_int = max(n_int, self.fr_int)
        n_int *= max(1, int(self.p["basic"]["n_sensors"]))
        self.n_int_frames = n_int
        self.g_type = 1.0          # staring / micro-scanned imagers

        lab_flux = self.flux(0.0, None)
        self.lab_flux = lab_flux
        if self.cat == "Thermal":
            if self.uncooled:
                self.t_ref = self.t_max * (float(d["duty"]) if d["tint_mode"] == "duty" else 1.0)
                if d["tint_mode"] == "direct":
                    self.t_ref = float(d["tint_ms"]) * 1e-3
                netd_m = float(d["netd_mK"]) * 1e-3
                if d["noise_mode"] == "detector":
                    Fs = self.F_eff
                    Fm = float(d["meas_F"]) or Fs
                    tau_m = float(d["meas_tau"]) or self.tau_o          # may be spectral (Zemax data)
                    TBm = float(d["meas_TB_K"]) or self.T_B
                    R = self.lam * self.eta
                    num = ph.trapz(tau_m * R * ph.dplanck_dT(self.lam, TBm), self.lam)
                    den = ph.trapz(self.tau_o * R * ph.dplanck_dT(self.lam, self.T_B), self.lam)
                    netd_s = netd_m * (Fs ** 2 / Fm ** 2) * num / den                     # Eq. (3.142)
                    extra = (float(d["readout_mK"]) * 1e-3) ** 2
                    if d["adc_mode"] == "mK":
                        extra += (float(d["lsb_mK"]) * 1e-3) ** 2 / 12
                    self.netd = math.sqrt(netd_s ** 2 + extra)
                    self.netd_scaled_only = netd_s
                else:
                    self.netd = netd_m
                t_th = float(d["t_th_ms"]) * 1e-3
                self.t_th = t_th
            else:
                self.t_ref = self.t_int_for(lab_flux["jB"])
                self.dndt = self.dN_dT(self.t_ref)
                self.sigma_B = self.noise(lab_flux["jB"], lab_flux["jB"], self.t_ref)
                self.netd_calc = self.sigma_B / self.dndt
                self.netd = float(d["netd_mK"]) * 1e-3 if d["noise_mode"] == "measured" else self.netd_calc
                self.wellfill_ref = self.well_fill(lab_flux["jB"], self.t_ref)
                if self.wellfill_ref > 100:
                    self.warn("Storage gate overflow: well fill %.0f %% (calculation continues)." % self.wellfill_ref)
                # integration time for 50 % / 100 % well fill
                g = float(d["electron_gain"])
                if self.n_stor > 0:
                    self.t50 = 50 * self.n_stor / ((lab_flux["jB"] + self.j_dark) * self.A_det * g * 100)
                    self.t100 = 2 * self.t50
            fpn = d["fpn_mode"]
            if fpn == "measured":
                self.ietd = float(d["ietd_mK"]) * 1e-3
            elif fpn == "estimate":
                self.ietd = float(d["fpn_fraction"]) * self.netd
                if self.ietd > 0:
                    self.assume("Fixed pattern noise estimated as %.2g x NETD (not measured)." %
                                float(d["fpn_fraction"]))
            else:
                self.ietd = 0.0
            self._check_netd_conditions()
        else:
            self.t_ref = None

    def _check_netd_conditions(self):
        """NETD is only valid at its test conditions: flag undocumented or extrapolated use."""
        d = self.p["detector"]
        measured = self.uncooled or d["noise_mode"] == "measured"
        if not measured:
            return
        if self.uncooled and d["noise_mode"] == "detector":
            TBm = float(d["meas_TB_K"])
        else:
            TBm = float(d.get("netd_TB_K", 0.0))
        if TBm <= 0:
            self.assume("NETD test (blackbody) temperature not documented - assumed equal to the background "
                        "temperature %.0f K." % self.T_B)
        elif abs(TBm - self.T_B) > 10.0:
            if self.uncooled and d["noise_mode"] == "detector":
                note = "the NETD is scaled to the scene temperature (Eq. 3.142), which is an extrapolation"
            else:
                note = "the measured NETD is used unchanged"
            self.warn("NETD was measured at %.0f K but the background is %.0f K (%+.0f K): %s." %
                      (TBm, self.T_B, self.T_B - TBm, note))
        src = self.source("detector.netd_mK")
        if src in ("preset", "assumption"):
            self.assume("NETD %.1f mK is a %s value, not a measurement of this camera." % (self.netd * 1e3, src))

    def signal_state(self, R_km, atm):
        """Signal/noise state at range R for Visible/General (carriers) or Thermal (Kelvin)."""
        fl = self.flux(R_km, atm)
        ns, fs = float(self.wi.get("noise_scale", 1.0)), float(self.wi.get("fpn_scale", 1.0))
        if self.cat == "Thermal":
            tau = fl["tau"]
            return {"flux": fl, "nes": self.netd * ns, "ies": self.ietd * fs,
                    "eds": abs(float(self.p["target"]["dT_K"])) * tau, "t_int": self.t_ref}
        d = self.p["detector"]
        t = self.t_int_for(fl["jB"])
        g = float(d["electron_gain"])
        sigma = self.noise(fl["jT"], fl["jB"], t) * ns
        fpn = d["fpn_mode"]
        if fpn == "measured":
            n_prnu = float(d["prnu_pct"]) / 100.0 * fl["jB"] * self.A_det * t * g      # (3.166)
            n_dsnu = float(d["dsnu_A"]) / ph.E_CHARGE * t                               # (3.167)
            ies = math.hypot(n_prnu, n_dsnu)                                             # (3.168)
        elif fpn == "estimate":
            ies = float(d["fpn_fraction"]) * sigma
        else:
            ies = 0.0
        ies *= fs
        ds = fl["dj"] * self.A_det * t * g                                              # (3.128)
        return {"flux": fl, "nes": sigma, "ies": ies, "eds": abs(ds), "ds": ds, "t_int": t,
                "N_B": fl["jB_scene"] * self.A_det * t * g, "N_T": fl["jT_scene"] * self.A_det * t * g,
                "wellfill": self.well_fill(fl["jB"], t), "wellfill_T": self.well_fill(fl["jT"], t)}

    def _check_saturation(self, st, where):
        """Full-well and ADC clipping: the linear signal/noise model is invalid when the signal clips."""
        if self.cat == "Thermal":
            return
        d = self.p["detector"]
        wf = max(st.get("wellfill", 0.0), st.get("wellfill_T", 0.0))
        if np.isfinite(wf) and wf > 100.0:
            self.warn("Saturation %s: the pixel well is filled to %.0f %% - the linear signal/noise model is not "
                      "valid (reduce integration time or aperture)." % (where, wf))
        bits = int(d.get("adc_bits", 0) or 0)
        if bits > 0 and d["adc_mode"] == "carriers" and float(d["lsb_e"]) > 0:
            g = float(d["electron_gain"])
            n_max = max(st["N_T"], st["N_B"]) + (self.j_dark * self.A_det * st["t_int"] * g)
            full = (2 ** bits) * float(d["lsb_e"])
            if n_max > full:
                self.warn("ADC clipping %s: signal %.3g e- exceeds the %d-bit range (%.3g e-)." %
                          (where, n_max, bits, full))

    # =========================================================================================
    # MTFs (Chapter 4)
    # =========================================================================================
    def _setup_weights(self, R_ref):
        """Spectral weighting function w(lambda), Eqs. (4.2), (4.3)."""
        atm = None if self.lab or not self.atms else self.atms[0]
        tau = 1.0 if atm is None else atm.tau_lam(R_ref)
        F_T, F_B = self.irr_factors(self.los_angle(R_ref))
        ds = (self.I * (self.rho_T - self.rho_B) + math.pi * (self.L_T * self.eps_T - self.L_B * self.eps_B)) * \
            self.tau_o * tau * self.lam * self.eta
        tot = ph.trapz(ds, self.lam)
        if abs(tot) < 1e-6 * ph.trapz(np.abs(ds), self.lam) or not np.isfinite(tot) or tot == 0:
            ds = np.abs(ds)
            tot = ph.trapz(ds, self.lam)
        if tot <= 0 or not np.isfinite(tot):
            ds = self.lam * self.eta
            tot = ph.trapz(ds, self.lam)
        self.w = ds / tot

    def _setup_mtf(self):
        o, d, st, add = self.p["optics"], self.p["detector"], self.p["stab"], self.p["additional"]
        lam = self.lam
        # --- optics, spectrally weighted diffraction MTF (4.1) + aberration (4.11)/(4.13)
        # (or the polychromatic MTF imported from Zemax, which already contains diffraction + aberrations)
        self.opt_tab = {}
        # data precedence (roadmap 06-A): Mode A computed optics, Mode B imported optics MTF (replaces
        # diffraction + aberration), Mode C imported device prefilter MTF (replaces optics, detector and
        # pre-sampling submodels - they are bypassed to avoid double counting)
        self.mtf_mode = {"zemax": "B", "device": "C"}.get(o.get("mtf_source"), "A")
        zemax = self._zemax_mtf_data() if self.mtf_mode in ("B", "C") else None
        if self.mtf_mode == "A" and o["aberration"] != "none":
            self.assume("Optics aberrations approximated by %s (full optical MTF not available)." %
                        ("the aberration parameter q = %g" % float(o["q"]) if o["aberration"] == "q" else
                         "a Gaussian blur of sigma = %g um" % float(o["blur_um"])))
        for z in "hv":
            dm = self.diff[z]
            r_cut = dm.d_max / lam[0]
            if zemax:
                r_cut = max(r_cut, zemax[z][0][-1])
            r = np.linspace(0.0, r_cut, 1200)
            if o["diffraction"] == "spectral" or zemax:
                lam_s = lam[::4]
                w = np.interp(lam_s, lam, self.w)
                w = w / ph.trapz(w, lam_s)
                m = np.abs(ph.trapz(w[None, :] * dm(r[:, None], lam_s[None, :]), lam_s, axis=1))
            else:
                lam0 = float(o["lambda_diff_um"])
                if not self.band[0] <= lam0 <= self.band[1]:
                    self.warn("Wavelength for the diffraction MTF (%.2f um) is outside the imager spectral band "
                              "(can be intended to approximate aberrations)." % lam0)
                m = dm(r, lam0)
            self.diff_tab = getattr(self, "diff_tab", {})
            self.diff_tab[z] = (r, m.copy())
            if self.wi.get("no_aberr") and self.mtf_mode != "C":
                pass                                       # what-if: diffraction-limited optics
            elif zemax:
                m = self._zemax_mtf_on_grid(r, m, z, *zemax[z])
            elif o["aberration"] == "q":
                m = m ** float(o["q"])
            elif o["aberration"] == "blur":
                m = m * M.mtf_blur(r, float(o["blur_um"]), self.f_eff)
            self.opt_tab[z] = (r, m)

        # --- detector crosstalk diffusion constants (4.30)
        self.d_diff = {}
        for z, key in (("h", "xtalk_h"), ("v", "xtalk_v")):
            spec = float(d[key])
            rN = self.f[z] / (2 * self.pitch_unbinned[z])
            geo = float(M.mtf_det_geometry(np.array([rN]), self.shape, self.a_unbinned[z], self.f[z],
                                           float(d["d_um"]), float(d["d_hole_um"]))[0])
            self.d_diff[z] = M.crosstalk_diffusion_constant(abs(geo), spec, rN) if spec > 0 else 0.0
            if spec > 0 and spec >= abs(geo):
                self.warn("Specified detector MTF at Nyquist (%s) is not below the geometrical MTF; "
                          "no crosstalk applied." % z)

    def _zemax_mtf_data(self):
        """Imported Zemax MTF converted to object space: {z: (r [1/mrad], mtf)}."""
        o = self.p["optics"]
        zf = o.get("zemax_mtf") or {}
        if not zf.get("text"):
            raise ModelError("Optics MTF via Zemax file selected, but no MTF file was imported")
        try:
            fields = Z.parse_mtf(zf["text"])
        except ValueError as e:
            raise ModelError("Zemax MTF file %s: %s" % (zf.get("name", ""), e))
        n = int(o.get("zemax_mtf_field", 1))
        if not 1 <= n <= len(fields):
            raise ModelError("Zemax MTF field %d requested, but the file contains %d field(s)" % (n, len(fields)))
        fd = fields[n - 1]
        unit = o.get("zemax_mtf_unit", "auto")
        auto = unit == "auto"
        if auto:
            unit = Z.detect_frequency_unit(zf["text"])
        h_key = "S" if o.get("zemax_mtf_h", "sagittal") == "sagittal" else "T"
        v_key = "T" if h_key == "S" else "S"
        kind = "Device prefilter MTF" if self.mtf_mode == "C" else "Optics MTF"
        self.zemax_mtf_label = "%s imported: %s, field %d (%s), h = %s, %s%s" % (
            kind, zf.get("name", ""), n, fd["label"], "sagittal" if h_key == "S" else "tangential",
            "cycles/mm image space" if unit == "mm" else "cycles/mrad object space", " (auto-detected)" if auto else "")
        self._record_import(kind, zf, "field %d, %s" % (n, "cycles/mm" if unit == "mm" else "cycles/mrad"))
        if auto:
            self.assume("Frequency unit of the imported MTF auto-detected as %s." %
                        ("cycles/mm (image space)" if unit == "mm" else "cycles/mrad (object space)"))
        if not str(o.get("mtf_meta", "")).strip():
            self.assume("Spectral weighting, field position and zoom/focus of the imported MTF are not documented.")
        out = {}
        for z, key in (("h", h_key), ("v", v_key)):
            # image space cycles/mm -> object space cycles/mrad: r = nu * f[mm] / 1000
            r = fd["freq"] * (self.f[z] / 1000.0 if unit == "mm" else 1.0)
            m = fd[key]
            if m.max() > 1.02:
                self.warn("Imported MTF (%s) has values above 1 (max %.3f) - MTF must be within [0, 1]; values are "
                          "clipped." % (z, m.max()))
            if r[0] == 0 and abs(m[0] - 1.0) > 0.05:
                self.warn("Imported MTF (%s) is %.3f at zero frequency - the curve is not normalized." % (z, m[0]))
            if r[-1] < self.r_N[z] * 0.999:
                self.warn("Imported MTF (%s) ends at %.3g 1/mrad, below the Nyquist frequency %.3g 1/mrad - the MTF "
                          "near Nyquist is extrapolated." % (z, r[-1], self.r_N[z]))
            if r[0] > 0:
                r, m = np.concatenate([[0.0], r]), np.concatenate([[1.0], m])
            out[z] = (r, np.clip(m, 0.0, 1.0))
        return out

    def _zemax_mtf_on_grid(self, r, m_diff, z, r_file, m_file):
        """Interpolate the Zemax MTF on r; beyond the file range continue with the diffraction shape."""
        m = np.interp(r, r_file, m_file)
        beyond = r > r_file[-1]
        if np.any(beyond):
            d_last = float(np.interp(r_file[-1], r, m_diff))
            scale = m_file[-1] / d_last if d_last > 1e-6 else 0.0
            m[beyond] = m_diff[beyond] * scale
            if m_file[-1] > 0.05:
                self.warn("Zemax MTF data (%s) ends at %.3g 1/mrad with MTF %.2f; it is extended with the shape of "
                          "the diffraction MTF." % (z, r_file[-1], m_file[-1]))
        inside = ~beyond & (r > 0)
        if np.any(m[inside] > m_diff[inside] + 0.05):
            self.warn("Imported Zemax MTF (%s) exceeds the diffraction limit of the specified aperture - check the "
                      "frequency unit, focal length, aperture and selected field." % z)
        return np.clip(m, 0.0, 1.0)

    def mtf_opt(self, r, z):
        rt, mt = self.opt_tab[z]
        return np.interp(np.abs(r), rt, mt, right=0.0)

    def mtf_det(self, r, z):
        """Static detector MTF (4.20) times integration-during-movement MTF."""
        if self.mtf_mode == "C" or self.wi.get("ideal_det"):
            return np.ones_like(np.asarray(r, float))      # contained in the imported device prefilter MTF
        d = self.p["detector"]
        m = M.mtf_det_geometry(r, self.shape, self.a_unbinned[z], self.f[z], float(d["d_um"]), float(d["d_hole_um"]))
        m = m * M.mtf_binning(r, self.nbin[z], self.pitch_unbinned[z], self.f[z])
        if z == "v" and self.interlace == "pseudo":
            m = m * M.mtf_pseudo_interlace(r, self.pitch_unbinned["v"], self.f["v"])
        if d["cte_on"]:
            n_tr = float(d["ntr_h"] if z == "h" else d["ntr_v"])
            cte = float(d["cte_h"] if z == "h" else d["cte_v"])
            m = m * M.mtf_cte(r, n_tr, cte, self.pitch_eff[z], self.f[z])
        if self.d_diff[z] > 0:
            m = m * M.mtf_crosstalk(r, self.d_diff[z])
        if self.ms != "none" and self.p["basic"]["integ_during_move"]:
            t = self.t_ref if self.t_ref else self.t_max
            duty = min(1.0, t / self.t_max)
            m = m * M.mtf_microscan_integration(r, self.ms, duty, self.pitch_eff[z], self.f[z], self.nstep[z],
                                                t, self.frame_rate)
        return m

    def mtf_stab(self, r, z):
        st = self.p["stab"]
        m = np.ones_like(np.asarray(r, float))
        if st["neglect"] or self.wi.get("no_stab"):
            return m
        if st.get("jitter_mode") == "measured":
            return self._jitter_mtf(r, z)                 # measured motion replaces the vibration models
        if st["random_on"]:
            m = m * M.mtf_random_vibration(r, float(st["rand_h_mrad"] if z == "h" else st["rand_v_mrad"]))
        if st["sin_on"]:
            m = m * M.mtf_sinusoidal_vibration(r, float(st["sin_h"] if z == "h" else st["sin_v"]))
        if st["lin_on"]:
            w = float(st["lin_h"] if z == "h" else st["lin_v"])
            if w > 0:
                r = np.asarray(r, float)
                if self.uncooled:
                    m = m * M.mtf_first_order_lowpass(w * r, 1.0 / (2 * math.pi * self.t_th))   # (4.69)
                else:
                    t = self.t_ref if self.t_ref else self.t_max
                    m = m * ph.sinc(t * w * r)                                                  # (4.67)
                K = self.n_frames * self.nstep["h"] * self.nstep["v"]
                m = m * ph.sinc_ratio(K, w * r / (self.frame_rate * self.nstep["h"] * self.nstep["v"]))  # (4.71)
                if self.iir > 0:
                    m = m * M.mtf_iir(r, self.iir, self.n_frames, w, self.frame_rate)            # (4.72)
        return m

    def _jitter_data(self):
        if not hasattr(self, "_jit"):
            st = self.p["stab"]
            fobj = st.get("jitter_file") or {}
            if not fobj.get("text"):
                raise ModelError("Measured jitter selected, but no jitter time series was imported")
            try:
                j = IM.parse_jitter(fobj["text"], float(st.get("jitter_rate_hz", 0.0)))
            except ValueError as e:
                raise ModelError("Jitter file %s: %s" % (fobj.get("name", ""), e))
            unit = st.get("jitter_unit", "urad")
            conv = {}
            for z in "hv":
                if unit == "urad":
                    conv[z] = 1e-3
                elif unit == "mrad":
                    conv[z] = 1.0
                else:                                       # pixels -> mrad (unbinned detector pitch)
                    conv[z] = self.pitch_unbinned[z] / self.f[z]
            self._jit = {"rate": j["rate"], "x": {z: j[z] * conv[z] for z in "hv"}, "unit": unit}
            self._record_import("Line-of-sight jitter", fobj, "%s, %.4g Hz, axes h = column 1, v = column 2; %s" %
                                (unit, j["rate"], "; ".join(j["notes"])))
        return self._jit

    def _jitter_mtf(self, r, z):
        jd = self._jitter_data()
        if self.uncooled:
            t = self.t_th
        else:
            t = self.t_ref if self.t_ref else self.t_max
        key = (z, round(t, 12))
        if key not in self._jit_cache:
            r_max = self.opt_tab[z][0][-1]
            rg = np.linspace(0.0, r_max, 300)
            intra, sig_f, stats = IM.jitter_mtf(jd["x"][z], jd["rate"], t, rg)
            m = intra
            if stats["samples_per_frame"] < 2:
                # motion within one integration time is not resolved: treat all as random vibration
                m = M.mtf_random_vibration(rg, stats["rms"])
                self.warn("Jitter sample rate %.4g Hz is too low to resolve motion within the %.3g ms integration "
                          "time - the measured rms is used as random vibration." % (jd["rate"], t * 1e3))
            elif not self.still:
                m = m * M.mtf_random_vibration(rg, sig_f)              # frame-to-frame jitter seen by the eye
            drift_eye = abs(stats["drift"]) * self.t_eye
            if drift_eye > 0.5 * self.alpha_s[z]:
                self.warn("Measured slow drift (%s) moves the image by %.2f pixels during the eye integration time - "
                          "drift is not modelled as blur." % (z, drift_eye / self.alpha_s[z]))
            stats["sigma_frame"] = sig_f
            self._jit_cache[key] = (rg, m, stats)
        rg, m, _ = self._jit_cache[key]
        return np.interp(np.abs(np.asarray(r, float)), rg, m, right=float(m[-1]))

    def mtf_add(self, r, where, z):
        a = self.p["additional"]
        kind = a["%s_%s_type" % (where, z)]
        if kind == "none" or (where == "pre" and self.mtf_mode == "C"):
            return np.ones_like(np.asarray(r, float))
        return M.mtf_additional(r, kind, float(a["%s_%s_par" % (where, z)]))

    def turbulence_active(self):
        return self.cat != "Thermal" and not self.lab and bool(self.p["turbulence"]["on"]) and \
            not self.wi.get("no_turb")

    def _turb_table(self, R_km):
        key = round(R_km, 9)
        if key in self._turb_cache:
            return self._turb_cache[key]
        tb = self.p["turbulence"]
        tg = self.p["target"]
        h_t = max(float(tg["alt_m"]), 0.1)
        av = self.los_angle(R_km)
        h_i = h_t + R_km * 1000.0 * math.sin(av)
        R_m = R_km * 1000.0
        cn2 = float(tb["cn2"])
        if tb["cn2_mode"] == "height":
            delta = 4.0 / 3.0 if tb["time"] == "day" else 2.0 / 3.0
            href = float(tb["h_ref_m"])

            def cn2_of_z(zz):
                h = np.maximum(h_i + (h_t - h_i) * zz / max(R_m, 1e-9), 0.1)
                return cn2 * (h / href) ** (-delta)                                  # Eq. (4.84)
        else:
            def cn2_of_z(zz):
                return np.full_like(zz, cn2)
        r0_ref = M.fried_parameter(1.0, R_km, cn2_of_z)            # r0 at 1 um; r0 ~ lambda^(6/5)
        lam_s = self.lam[::4]
        w = np.interp(lam_s, self.lam, self.w)
        w = w / ph.trapz(w, lam_s)
        r_max = max(self.opt_tab["h"][0][-1], self.opt_tab["v"][0][-1])
        r = np.linspace(0.0, r_max, 1200)
        m = np.zeros_like(r)
        vals = []
        for lam_i in lam_s:
            r0 = r0_ref * lam_i ** 1.2
            vals.append(M.mtf_turbulence(r, lam_i, r0, self.D_eff, tb["exposure"]))
        m = np.abs(ph.trapz(w[None, :] * np.array(vals).T, lam_s, axis=1))
        self._turb_cache[key] = (r, m, r0_ref * self.lam_peak ** 1.2)
        return self._turb_cache[key]

    def mtf_turb(self, r, R_km):
        if not self.turbulence_active() or R_km <= 0:
            return np.ones_like(np.asarray(r, float))
        rt, mt, _ = self._turb_table(R_km)
        return np.interp(np.abs(r), rt, mt, right=0.0)

    def pre_device(self, r, z):
        return self.mtf_opt(r, z) * self.mtf_det(r, z) * self.mtf_add(r, "pre", z)

    def pre_system(self, r, z, R_km):
        return self.pre_device(r, z) * self.mtf_stab(r, z) * self.mtf_turb(r, R_km)

    def mtf_dig(self, r, z):
        dsp = self.p["dsp"]
        if not dsp["filter_on"] or (dsp["filter_dir"] == "h" and z == "v") or (dsp["filter_dir"] == "v" and z == "h"):
            return np.ones_like(np.asarray(r, float))
        coef = dsp["h_coef"] if z == "h" else dsp["v_coef"]
        kind = dsp["h_type"] if z == "h" else dsp["v_type"]
        return M.mtf_digital_filter(r, coef, kind, self.alpha_s[z])

    def mtf_display(self, r, z):
        return M.mtf_flat_panel(r, self.r_s[z], self.zoom, self.rep[z])

    def mtf_psi(self, r, z):
        """Noise postfilter MTF without eye, Eqs. (3.193), (3.194)."""
        dsp = self.p["dsp"]
        rep_type = dsp["crep_type"] if z == "h" else dsp["lrep_type"]
        return self.mtf_dig(r, z) * M.mtf_replication(r, self.alpha_s[z], self.zoom, dsp["zoom_type"]) * \
            M.mtf_replication(r, self.alpha_s[z], self.rep[z], rep_type) * self.mtf_display(r, z) * \
            self.mtf_add(r, "post", z)

    def post_device(self, r, z):
        m = self.mtf_psi(r, z)
        if self.ms == "diagonal":
            m = m * M.mtf_diagonal_zoom(r, self.alpha_s[z])
        return m

    def mtf_eye(self, r):
        if self.p["display"]["neglect_eye"] or self.wi.get("ideal_eye"):
            return np.ones_like(np.asarray(r, float))
        return M.mtf_eye(r, self.gamma_eye, self.m_sys)

    def post_system(self, r, z):
        return self.post_device(r, z) * self.mtf_eye(r)

    # =========================================================================================
    # AMOP and eye/brain integrals (Sections 3.11.3 - 3.11.6)
    # =========================================================================================
    def _pre_cutoff(self, z, R_km):
        r = np.linspace(0, self.opt_tab[z][0][-1], 2000)
        m = np.abs(self.pre_system(r, z, R_km))
        idx = np.nonzero(m < 0.02)[0]
        return r[idx[0]] if idx.size else r[-1]

    def amop_direct(self, R_km, rp, z):
        margin = 4.0 / max(self._pre_cutoff_cached(z, R_km), 1e-6)
        return amop_sim(lambda fr: self.pre_system(fr, z, R_km), lambda fr: self.post_system(fr, z),
                        self.alpha_s[z], rp, psf_margin=margin)

    def _pre_cutoff_cached(self, z, R_km):
        key = ("cut", z, round(R_km, 9) if self.turbulence_active() else 0.0)
        if key not in self._amop_cache:
            self._amop_cache[key] = self._pre_cutoff(z, R_km)
        return self._amop_cache[key]

    def amop_table(self, R_km, z, rp):
        vals = []
        zeros = 0
        for x in rp:
            if zeros >= 3:
                vals.append(0.0)
                continue
            a = self.amop_direct(R_km, x, z)
            vals.append(a)
            zeros = zeros + 1 if a <= 0.001 else 0
        return np.array(vals)

    def amop_at(self, R_km, rp, z):
        if not self.turbulence_active():
            rt, at = self.amop_tab[z]
            if rp <= rt[0]:
                return float(at[0])
            if rp > rt[-1]:
                return 0.0
            pos = at > 0
            if rp > rt[pos][-1]:
                # between last positive and first zero entry: interpolate linearly to zero
                return float(max(0.0, np.interp(rp, rt, at)))
            return float(ph.loglog_interp(rp, rt[pos], at[pos]))
        return self.amop_direct(R_km, rp, z)

    def _eye_integrals(self):
        """Tabulate the eye/brain spatial integration factors versus bar pattern frequency."""
        rN = min(self.r_N.values())
        rs = max(self.r_s.values())
        self.e_rp = np.logspace(np.log10(1e-3 * rN), np.log10(6 * rs), 140)
        kD = math.sqrt(2) if self.ms == "diagonal" else 1.0
        self.EN, self.EI = {}, {}
        self.df_I = {}
        for z in "hv":
            a = self.alpha_s[z]
            N = self.nstep[z]
            rr = np.linspace(0.0, self.r_s[z], 4001)
            self.df_I[z] = N * a * ph.trapz(ph.sinc_ratio(N, a * rr) ** 2, rr)          # Eq. (3.171) w/o filter
            r_hi = 14.0 * self.r_s[z] * self.zoom * self.rep[z]
            for k in (1, 7):
                en, ei = [], []
                for rp in self.e_rp:
                    x_c = 20.0 * rp / k
                    r = np.unique(np.concatenate([np.linspace(0, min(x_c, r_hi), 3000),
                                                  np.linspace(min(x_c, r_hi), max(r_hi, x_c * 1.2), 3000)]))
                    base = self.mtf_psi(r, z) ** 2 * self.mtf_eye(r) ** 2 * ph.sinc(k * r / (2 * rp)) ** 2
                    en.append(2 * kD * a * ph.trapz(base, r))
                    ei.append(2 * a * N * ph.trapz(base * ph.sinc_ratio(N, a * r) ** 2, r))
                self.EN[(z, k)] = np.array(en)
                self.EI[(z, k)] = np.array(ei)

    def _e(self, table, key, rp):
        return float(ph.loglog_interp(rp, self.e_rp, table[key]))

    def psi(self, rp, z, nes, ies):
        """Total perceived noise variance, Eqs. (3.179), (3.180), (3.184)."""
        zp = "v" if z == "h" else "h"
        psi_n = nes ** 2 / self.n_int_frames * self._e(self.EN, (z, 1), rp) * self._e(self.EN, (zp, 7), rp)
        psi_i = 0.0
        if ies > 0:
            psi_i = ies ** 2 * self.g_type / (self.df_I["h"] * self.df_I["v"]) * \
                self._e(self.EI, (z, 1), rp) * self._e(self.EI, (zp, 7), rp)
        return psi_n + psi_i

    def mdsp(self, R_km, rp, z, nes, ies, amop_val=None):
        """MTDP / MDSP, Eqs. (3.175), (3.176)."""
        a = self.amop_at(R_km, rp, z) if amop_val is None else amop_val
        if a <= 0.001:
            return float("inf")
        return 0.5 * math.pi * self.snr_th * math.sqrt(self.psi(rp, z, nes, ies)) / a

    # =========================================================================================
    # Main entry
    # =========================================================================================
    def run(self):
        self.progress("Setting up imager geometry", 0.02)
        self._setup_geometry()
        self._setup_spectral()
        self._setup_atmospheres()
        self._setup_optics()
        self._setup_noise()
        R_ref = 0.0 if (self.lab or self.cat == "Thermal") else max(float(self.p["mode"]["ref_range_km"]), 0.0)
        if R_ref > 0 and R_ref < self.min_range():
            self.warn("Reference range is shorter than the imager altitude; the minimum slant range is used.")
            R_ref = self.min_range() * 1.0001
        self.R_ref = R_ref
        self._setup_weights(R_ref)
        self.progress("Calculating MTFs", 0.08)
        self._setup_mtf()

        res = {"warnings": self.warnings, "category": self.cat, "name": self.p.get("name", "")}
        ref_atm = None if (self.lab or R_ref == 0) else self.atms[0]
        if self.cat == "Thermal":
            ref_state = self.signal_state(0.0, None)
        else:
            ref_state = self.signal_state(R_ref, ref_atm)
            self.t_ref = ref_state["t_int"]
        self.ref_state = ref_state
        self._check_saturation(ref_state, "at the reference range")
        self._check_contrast(ref_state)

        # MTF curves
        res["mtf"] = self._mtf_curves(R_ref)

        # AMOP tables
        self.progress("Simulating AMOP (4-bar pattern imaging)", 0.15)
        rp_max = {z: min(2.5 * self.r_s[z], self.opt_tab[z][0][-1]) for z in "hv"}
        self.amop_tab = {}
        for z in "hv":
            rp = np.logspace(np.log10(0.02 * self.r_N[z]), np.log10(rp_max[z]), 70)
            self.amop_tab[z] = (rp, self.amop_table(R_ref, z, rp))
        res["amop"] = {z: {"rp": self.amop_tab[z][0], "amop": self.amop_tab[z][1]} for z in "hv"}
        self.progress("Eye/brain integrals", 0.35)
        self._eye_integrals()

        # MTDP / MDSP / MCP at reference range
        res["fom"] = self._fom(R_ref, ref_state)
        self._fom_res = res["fom"]
        if self.cat == "Visible" and self.lab:
            res["mcp"] = self._mcp(ref_state)
        meas = self._measured_fom()
        if meas:
            res["fom_measured"] = meas
            if meas["use"] == "replace":
                self._fom_res = {"name": res["fom"]["name"], "unit": res["fom"]["unit"], "R_ref": R_ref,
                                 "h": meas["h"], "v": meas["v"], "avg": res["fom"]["avg"]}

        # ranges
        if not self.lab:
            self.progress("Range calculation", 0.45)
            res["range"] = self._ranges()
            if meas and meas["use"] == "replace":
                res["range"]["source"] = "measured %s (%s)" % (meas["kind"], meas["name"])
            for a in res["range"]["atm"]:
                if "states" in a:
                    i = int(np.nanargmax(np.where(np.isfinite(a["states"]["wellfill"]), a["states"]["wellfill"], -1)))
                    if np.isfinite(a["states"]["wellfill"][i]) and a["states"]["wellfill"][i] > 100:
                        self.warn("Saturation along the range curve (%s): background well fill up to %.0f %%." %
                                  (a["label"], a["states"]["wellfill"][i]))
            if self.p["mode"]["niirs"]:
                self.progress("NIIRS calculation", 0.9)
                res["niirs"] = self._niirs()
        res["spectral"] = {"lam": self.lam, "qe": self.eta * 100, "w": self.w,
                           "rho_T": self.rho_T, "rho_B": self.rho_B, "eps_T": self.eps_T, "eps_B": self.eps_B,
                           "I": self.I, "tau_o": np.broadcast_to(self.tau_o, self.lam.shape).copy()}
        if not self.lab and self.atms:
            Rg = self._range_grid(60)
            res["atmosphere"] = [{"label": a.label, "R": Rg, "tau": np.array([a.tau(x) for x in Rg])}
                                 for a in self.atms]
        res["dashboard"] = self._dashboard(res)
        val = self._validation(res)
        if val:
            res["validation"] = val
        res["info"] = self._info(res)
        res["provenance"] = self._provenance()
        res["assumptions"] = self.assumptions
        self.progress("Done", 1.0)
        return res

    # -----------------------------------------------------------------------------------------
    def _check_contrast(self, st):
        tg = self.p["target"]
        if self.cat == "Thermal":
            dT = abs(float(tg["dT_K"]))
            if dT == 0:
                self.warn("No target contrast (temperature difference 0 K): the target cannot be detected at any "
                          "range.")
            elif dT < self.netd:
                self.warn("Target temperature difference %.3g K is below the NETD %.3g K - low SNR even at zero "
                          "range." % (dT, self.netd))
        else:
            if st["ds"] == 0:
                self.warn("No target contrast (target and background signals are equal): the target cannot be "
                          "detected at any range.")
            else:
                n = math.hypot(st["nes"], st["ies"])
                if n > 0 and abs(st["ds"]) / n < 1.0:
                    self.warn("Low SNR at the reference range: difference signal / noise = %.2f." % (abs(st["ds"]) / n))

    def _measured_fom(self):
        """Measured MTDP / MRTD / MCP curve (Laboratory workflow)."""
        ms = self.p.get("measured") or {}
        fobj = ms.get("fom_file") or {}
        if not fobj.get("text"):
            return None
        kind = ms.get("fom_kind", "MTDP")
        try:
            c = IM.parse_curve_hv(fobj["text"], kind)
        except ValueError as e:
            raise ModelError("Measured %s file %s: %s" % (kind, fobj.get("name", ""), e))
        self._record_import("Measured " + kind, fobj, "; ".join(c["notes"]))
        out = {"kind": kind, "name": fobj.get("name", ""), "use": ms.get("fom_use", "compare")}
        scale = 1e-3 if kind in ("MTDP", "MRTD") and ms.get("fom_vunit", "K") == "mK" else 1.0
        for z in "hv":
            rp = IM.to_cycles_per_mrad(c["f"], ms.get("fom_unit", "mrad"), self.f[z], self.alpha_s[z])
            out[z] = {"rp": rp, "val": c[z] * scale}
        if out["use"] == "replace":
            if self.cat != "Thermal" or kind == "MCP":
                self.warn("Measured %s can replace the modelled figure of merit only for Thermal imagers (MTDP / "
                          "MRTD); it is shown for comparison only." % kind)
                out["use"] = "compare"
            else:
                if kind == "MRTD":
                    self.warn("Measured MRTD is used as MTDP - they agree only for well-sampled imagers; beyond "
                              "Nyquist the MRTD is not defined.")
                self.assume("Range calculated from the measured %s instead of the modelled MTDP." % kind)
        return out

    def _validation(self, res):
        """Comparison of measured and predicted data (Laboratory & Image Evaluation workflow)."""
        ms = self.p.get("measured") or {}
        out = {"items": []}
        if "fom_measured" in res:
            m = res["fom_measured"]
            ref = res.get("mcp") if m["kind"] == "MCP" else res["fom"]
            if ref is None:
                self.warn("Measured MCP can only be compared with a Visible/NIR/SWIR prediction in laboratory mode.")
            else:
                for z in "hv":
                    pr = np.interp(m[z]["rp"], ref[z]["rp"], np.where(np.isfinite(ref[z]["val"]), ref[z]["val"], np.nan),
                                   left=np.nan, right=np.nan)
                    ok = np.isfinite(pr) & np.isfinite(m[z]["val"]) & (m[z]["val"] > 0)
                    dev = 100 * (pr[ok] / m[z]["val"][ok] - 1) if ok.any() else np.array([])
                    out["items"].append({"what": "%s %s" % (m["kind"], z), "rp": m[z]["rp"], "measured": m[z]["val"],
                                         "predicted": pr, "unit": "K" if m["kind"] != "MCP" else "contrast",
                                         "mean_dev_pct": float(np.mean(np.abs(dev))) if dev.size else np.nan,
                                         "max_dev_pct": float(np.max(np.abs(dev))) if dev.size else np.nan})
        sf = ms.get("sfr_file") or {}
        if sf.get("text"):
            try:
                c = IM.parse_curve_hv(sf["text"], "MTF / SFR")
            except ValueError as e:
                raise ModelError("Measured MTF/SFR file %s: %s" % (sf.get("name", ""), e))
            self._record_import("Measured MTF / SFR", sf, "; ".join(c["notes"]))
            kind = ms.get("sfr_kind", "device")
            for z in "hv":
                r = IM.to_cycles_per_mrad(c["f"], ms.get("sfr_unit", "mrad"), self.f[z], self.alpha_s[z])
                meas = c[z] / (100.0 if c[z].max() > 1.5 else 1.0)
                if kind == "device":
                    pr = np.abs(self.pre_device(r, z))
                    label = "device prefilter MTF"
                else:
                    pr = np.abs(self.pre_device(r, z) * self.mtf_stab(r, z) * self.post_device(r, z))
                    label = "delivered-image SFR (pre x post, no eye)"
                dev = 100 * np.abs(pr - meas)        # absolute MTF difference in % points
                out["items"].append({"what": "MTF %s (%s)" % (z, label), "rp": r, "measured": meas, "predicted": pr,
                                     "unit": "MTF", "mean_dev_pct": float(np.mean(dev)), "max_dev_pct": float(np.max(dev)),
                                     "abs_points": True})
        nm = float(ms.get("netd_mK", 0.0) or 0.0)
        if nm > 0 and self.cat == "Thermal":
            pred = self.netd * 1e3
            out["items"].append({"what": "NETD", "measured": nm, "predicted": pred, "unit": "mK",
                                 "mean_dev_pct": 100 * (pred / nm - 1), "max_dev_pct": 100 * abs(pred / nm - 1)})
            TBm = float(ms.get("netd_TB_K", 0.0) or 0.0)
            if TBm > 0 and abs(TBm - self.T_B) > 5:
                self.warn("Measured NETD was taken at %.0f K, the prediction is for a %.0f K background - not a "
                          "like-for-like comparison." % (TBm, self.T_B))
        if not out["items"]:
            return None
        meta = ms.get("meta") or {}
        missing = [k for k in ("instrument", "date", "method", "focus", "temperature", "processing", "uncertainty",
                               "config_id") if not str(meta.get(k, "")).strip()]
        out["meta"] = meta
        out["missing_meta"] = missing
        if missing:
            self.assume("Calibration metadata incomplete (missing: %s)." % ", ".join(missing))
        if not self.lab and self.cat != "Thermal" and self.R_ref > 0:
            self.warn("Measured (laboratory) data are compared with a field-mode prediction at %.3g km - switch to "
                      "Laboratory performance for a like-for-like comparison." % self.R_ref)
        return out

    @staticmethod
    def _mtf50(r, m):
        idx = np.nonzero(m < 0.5)[0]
        if idx.size == 0 or idx[0] == 0:
            return None
        i = idx[0]
        return float(r[i - 1] + (0.5 - m[i - 1]) * (r[i] - r[i - 1]) / (m[i] - m[i - 1]))

    def _dashboard(self, res):
        """Compact always-visible figures (roadmap Section 09)."""
        d = {"mtf": {}, "tasks": []}
        for z in "hv":
            r = res["mtf"]["r"][z]
            m = res["mtf"]["curves"][z]["System prefilter"]
            d["mtf"][z] = {"mtf50": self._mtf50(r, m), "mtf_nyq": float(np.interp(self.r_N[z], r, m)),
                           "r_N": self.r_N[z]}
        st = self.ref_state
        if self.cat == "Thermal":
            n = math.hypot(st["nes"], st["ies"])
            d["cnr"] = abs(float(self.p["target"]["dT_K"])) / n if n > 0 else float("inf")
            d["cnr_label"] = "dT / sqrt(NETD^2 + IETD^2) at zero range"
        else:
            n = math.hypot(st["nes"], st["ies"])
            d["cnr"] = abs(st["ds"]) / n if n > 0 else float("inf")
            d["cnr_label"] = "difference signal / total noise at %.3g km" % self.R_ref
        rg = res.get("range")
        if rg and rg["atm"]:
            a0 = rg["atm"][0]
            for t in a0["tasks"]:
                R0 = t["R0"]
                row = {"name": t["name"], "lp": t["lp"], "R0": R0}
                if R0 is not None and np.isfinite(R0) and R0 > 0:
                    ah, av, _ = self.target_dims(self.los_angle(R0))
                    ph_, pv_ = ah / (R0 * self.alpha_s["h"]), av / (R0 * self.alpha_s["v"])
                    row.update(pix_h=ph_, pix_v=pv_, cyc_nyq=0.5 * math.sqrt(ph_ * pv_))
                    row["sampling_limited"] = t["lp"] >= 0.9 * row["cyc_nyq"]
                d["tasks"].append(row)
        d["nominal"] = True
        return d

    def _provenance(self):
        import datetime
        p = self.p
        o, dt, tg = p["optics"], p["detector"], p["target"]
        key = [("Focal length", "optics.f_mm", "mm")]
        key.append(("F-number", "optics.F_general", "") if o["aperture"] == "general" else
                   ("Aperture diameter", "optics.D_mm", "mm"))
        key += [("Detector pitch (h)", "detector.pitch_h_um", "um"), ("Detector format (h)", "detector.n_h", ""),
                ("Frame rate", "basic.frame_rate", "Hz"), ("Optics transmission", "optics.tau_opt", "")]
        if self.cat == "Thermal" and (self.uncooled or dt["noise_mode"] == "measured"):
            key.append(("NETD", "detector.netd_mK", "mK"))
        else:
            key += [("Read noise", "detector.noise_floor_e", "e-"), ("Dark current", "detector.dark_A", "A"),
                    ("Well capacity", "detector.storage_e", "e-")]
        if self.uncooled and dt["uncooled_response"] == "flat":
            key += [("Cut-on wavelength", "detector.cuton_um", "um"), ("Cut-off wavelength", "detector.cutoff_um", "um")]
        else:
            key.append(("Spectral QE", "detector.qe_preset", ""))
        key += [("Target width", "target.W_m", "m"), ("Target height", "target.H_m", "m")]
        key.append(("Target dT", "target.dT_K", "K") if self.cat != "Visible" else
                   ("Target reflectivity", "target.t_refl", ""))
        if p["atmosphere"]["mode"] == "spectral":
            key.append(("Atmosphere", "atmosphere.spec_file", ""))
        else:
            key.append(("Extinction (atm 1)", "atmosphere.atm.0.sigma", "1/km"))
        rows = []
        for label, path, unit in key:
            v = p
            try:
                for k in path.split("."):
                    v = v[int(k)] if isinstance(v, list) else v[k]
            except (KeyError, IndexError, ValueError):
                continue
            if isinstance(v, dict):
                v = v.get("name", "")
            rows.append((label, path, v, unit, self.source(path)))
        counts = {}
        for r in rows:
            counts[r[4]] = counts.get(r[4], 0) + 1
        return {"model_version": MODEL_VERSION, "time": datetime.datetime.now().isoformat(timespec="seconds"),
                "profile": dict(p.get("profile") or {}), "imports": list(self.imports), "key_inputs": rows,
                "source_counts": counts, "category": self.cat, "imager_type": p["imager_type"],
                "environment": "laboratory" if self.lab else "field", "stream": "still" if self.still else "video"}

    # -----------------------------------------------------------------------------------------
    def _mtf_curves(self, R_ref):
        out = {"r": {}, "curves": {}, "r_N": dict(self.r_N)}
        for z in "hv":
            r = np.linspace(0.0, 2.2 * self.r_s[z], 400)
            if self.mtf_mode == "C":
                c = {"Imported device prefilter": self.mtf_opt(r, z)}
            else:
                c = {"Optics (imported)" if self.mtf_mode == "B" else "Optics": self.mtf_opt(r, z),
                     "Detector": self.mtf_det(r, z)}
            c["Stabilization"] = self.mtf_stab(r, z)
            if self.turbulence_active() and R_ref > 0:
                c["Turbulence"] = self.mtf_turb(r, R_ref)
            c["Device prefilter"] = self.pre_device(r, z)
            c["System prefilter"] = self.pre_system(r, z, R_ref)
            c["Device postfilter"] = self.post_device(r, z)
            c["Eye"] = self.mtf_eye(r)
            c["System (pre x post)"] = c["System prefilter"] * c["Device postfilter"] * c["Eye"]
            out["r"][z] = r
            out["curves"][z] = {k: np.abs(v) for k, v in c.items()}
        return out

    def _fom(self, R_ref, st):
        name = "MTDP" if self.cat == "Thermal" else "MDSP"
        unit = "K" if self.cat == "Thermal" else "carriers"
        out = {"name": name, "unit": unit, "R_ref": R_ref}
        for z in "hv":
            rp, am = self.amop_tab[z]
            vals = np.array([self.mdsp(R_ref, x, z, st["nes"], st["ies"], a) for x, a in zip(rp, am)])
            out[z] = {"rp": rp, "val": vals}
        # average MDSP, Eqs. (3.204), (3.205)
        rh, mh = out["h"]["rp"], out["h"]["val"]
        rv, mv = out["v"]["rp"], out["v"]["val"]
        ra, ma = [], []
        for x, m in zip(rh, mh):
            if not np.isfinite(m):
                continue
            xv = ph.inverse_first_crossing(rv, mv, m)
            if xv is None:
                continue
            ra.append(math.sqrt(x * xv))
            ma.append(m)
        out["avg"] = {"rp": np.array(ra), "val": np.array(ma)}
        return out

    def _mcp(self, st):
        """Minimum Contrast Perceived for Visible/NIR/SWIR imagers in the laboratory, Eqs. (3.177)/(3.178)."""
        fl = st["flux"]
        t = st["t_int"]
        g = float(self.p["detector"]["electron_gain"])
        NB = fl["jB_scene"] * self.A_det * t * g
        out = {}
        for z in "hv":
            rp, am = self.amop_tab[z]
            vals = []
            for x, a in zip(rp, am):
                if a <= 0.001 or NB <= 0:
                    vals.append(np.nan)
                    continue
                C = 0.01
                ok = False
                for _ in range(60):
                    jB = fl["jB"]
                    jT = jB + fl["jB_scene"] * 2 * C / (1 - C)
                    sigma = self.noise(jT, jB, t)
                    ies = st["ies"] if self.p["detector"]["fpn_mode"] != "estimate" else \
                        float(self.p["detector"]["fpn_fraction"]) * sigma
                    m = self.mdsp(0.0, x, z, sigma, ies, a)
                    C_new = m * (1 - C) / (2 * NB)
                    if C_new >= 0.999:
                        C = 1.0
                        break
                    if abs(C_new - C) < 1e-6 * max(C, 1e-9):
                        C = C_new
                        ok = True
                        break
                    C = 0.5 * (C + C_new)
                vals.append(C if (ok or C < 1) else np.nan)
            out[z] = {"rp": rp, "val": np.array(vals)}
        return out

    # -----------------------------------------------------------------------------------------
    def _tasks(self):
        return [t for t in self.p["target"]["tasks"] if t.get("on") and float(t.get("lp", 0)) > 0]

    def _range_grid(self, n):
        r0 = max(self.min_range() * 1.0005, 0.01)
        return np.logspace(np.log10(r0), np.log10(max(100.0, r0 * 10)), n)

    @staticmethod
    def _avg_curve(R, mh, mv):
        """Average MNTD/MNDS via geometric mean of the ranges with equal h/v values, (3.216)-(3.218)."""
        Ra, Sa = [], []
        for Ri, S in zip(R, mh):
            if not np.isfinite(S) or S <= 0:
                continue
            Rv = ph.inverse_first_crossing(R, mv, S)
            if Rv is None:
                continue
            Ra.append(math.sqrt(Ri * Rv))
            Sa.append(S)
        Ra, Sa = np.array(Ra), np.array(Sa)
        order = np.argsort(Ra)
        return Ra[order], Sa[order]

    @staticmethod
    def _crossing(R, need, have):
        """First range at which the necessary signal exceeds the available one."""
        diff = np.log(np.maximum(need, 1e-300)) - np.log(np.maximum(have, 1e-300))
        idx = np.nonzero(diff >= 0)[0]
        if idx.size == 0:
            return None
        i = idx[0]
        if i == 0:
            return float(R[0])
        t = -diff[i - 1] / (diff[i] - diff[i - 1])
        return float(math.exp(math.log(R[i - 1]) + t * (math.log(R[i]) - math.log(R[i - 1]))))

    def _ranges(self):
        tasks = self._tasks()
        out = {"quantity": "ETD" if self.cat == "Thermal" else "EDS",
               "unit": "K" if self.cat == "Thermal" else "carriers", "atm": []}
        n_atm = len(self.atms)
        for ia, atm in enumerate(self.atms):
            if self.cat == "Thermal":
                out["atm"].append(self._ranges_thermal(atm, tasks))
            else:
                self.progress("Range calculation - %s" % atm.label, 0.45 + 0.45 * ia / max(n_atm, 1))
                out["atm"].append(self._ranges_signal(atm, tasks))
        return out

    def _ranges_thermal(self, atm, tasks):
        """Range performance for the Thermal category, Section 3.12.3."""
        R = self._range_grid(300)
        dT = abs(float(self.p["target"]["dT_K"]))
        etd = dT * np.array([atm.tau(x) for x in R])                               # Eq. (3.208)
        fom = self._fom_res
        dims = [self.target_dims(self.los_angle(x)) for x in R]
        res = {"label": atm.label, "R": R, "signal": etd, "tasks": []}
        # resolved line pairs vs range, Eqs. (3.210), (3.211)
        nlp = {}
        for z, zi in (("h", 0), ("v", 1)):
            rp, val = fom[z]["rp"], fom[z]["val"]
            finite = np.isfinite(val)
            r_last = rp[finite][-1] if finite.any() else 0.0
            n = []
            for x, e, dm in zip(R, etd, dims):
                rs = ph.inverse_first_crossing(rp, val, e)
                if rs is None:
                    rs = r_last
                elif rs == rp[0] and e < val[0]:
                    rs = 0.0
                n.append(rs * dm[zi] / x)
            nlp[z] = np.array(n)
        nbar = np.sqrt(nlp["h"] * nlp["v"])
        res["nlp"] = nbar
        res["npix"] = nlp["h"] * nlp["v"]                                         # Eq. (3.214)
        for t in tasks:
            n_perc = float(t["lp"])
            R0 = None
            below = np.nonzero(nbar < n_perc)[0]
            if below.size and below[0] > 0:
                i = below[0]
                y0, y1 = math.log(nbar[i - 1]), math.log(max(nbar[i], 1e-300))
                tt = (math.log(n_perc) - y0) / (y1 - y0)
                R0 = math.exp(math.log(R[i - 1]) + tt * (math.log(R[i]) - math.log(R[i - 1])))
            elif below.size == 0:
                R0 = float("inf")
            # MNTD curves, Eq. (3.215) and average (3.216)-(3.218)
            mn = {}
            for z, zi in (("h", 0), ("v", 1)):
                rp, val = fom[z]["rp"], fom[z]["val"]
                req = np.array([n_perc * x / dm[zi] for x, dm in zip(R, dims)])
                big = np.where(np.isfinite(val), val, 1e30)
                v = np.interp(req, rp, big, left=big[0], right=1e30)
                mn[z] = np.where(v >= 1e30, np.inf, v)
            Ra, Sa = self._avg_curve(R, mn["h"], mn["v"])
            res["tasks"].append({"name": t["name"], "lp": n_perc, "R0": R0, "R_avg": Ra, "mn_avg": Sa,
                                 "mn_h": mn["h"], "mn_v": mn["v"]})
        return res

    def _ranges_signal(self, atm, tasks):
        """Range performance for the Visible and General categories, Section 3.12.4."""
        R = self._range_grid(56)
        states = [self.signal_state(x, atm) for x in R]
        eds = np.array([s["eds"] for s in states])
        res = {"label": atm.label, "R": R, "signal": eds, "tasks": []}
        for it, t in enumerate(tasks):
            n_perc = float(t["lp"])
            mn = {}
            for z, zi in (("h", 0), ("v", 1)):
                vals = []
                dead = False
                for x, s in zip(R, states):
                    if dead:
                        vals.append(np.inf)
                        continue
                    a_z = self.target_dims(self.los_angle(x))[zi]
                    rp = n_perc * x / a_z if a_z > 0 else np.inf
                    m = self.mdsp(x, rp, z, s["nes"], s["ies"]) if np.isfinite(rp) else np.inf
                    vals.append(m)
                    dead = not np.isfinite(m)
                mn[z] = np.array(vals)
            Ra, Sa = self._avg_curve(R, mn["h"], mn["v"])
            R0 = None
            if Ra.size >= 2:
                eds_a = ph.loglog_interp(Ra, R, np.maximum(eds, 1e-300))
                R0 = self._crossing(Ra, Sa, eds_a)
                if R0 is None:
                    # no crossing: either the signal suffices up to the end of the grid, or the bar pattern
                    # frequency exceeds the resolution limit (MNDS infinite) beyond the last averaged range
                    dead = not (np.all(np.isfinite(mn["h"])) and np.all(np.isfinite(mn["v"])))
                    R0 = float(Ra[-1]) if dead else float("inf")
            res["tasks"].append({"name": t["name"], "lp": n_perc, "R0": R0, "R_avg": Ra, "mn_avg": Sa,
                                 "mn_h": mn["h"], "mn_v": mn["v"]})
        res["states"] = {"t_int": np.array([s["t_int"] for s in states]),
                         "nes": np.array([s["nes"] for s in states]),
                         "wellfill": np.array([s.get("wellfill", np.nan) for s in states])}
        return res

    # -----------------------------------------------------------------------------------------
    def _rer(self, z, R_km):
        """Relative edge response, Eq. (3.231)."""
        a = self.alpha_s[z]
        r = np.linspace(0.0, min(self.opt_tab[z][0][-1], 30 * self.r_s[z]), 6000)
        m = self.pre_system(r, z, R_km)
        return 2 * a * ph.trapz(m * ph.sinc(r * a), r)

    def _niirs(self):
        """NIIRS according to GIQE 5, Section 3.13."""
        out = {"atm": []}
        tg = self.p["target"]
        if tg["flight"] == "altitude" and float(tg["altitude_m"]) <= 0 or \
                tg["flight"] == "angle" and float(tg["angle_deg"]) <= 0:
            self.warn("NIIRS requires a slant (downward looking) line of sight.")
            return out
        r_min = max(self.min_range() * 1.001, 0.05)
        R = np.logspace(np.log10(r_min), np.log10(max(r_min * 20, 30.0)), 40)
        for atm in self.atms:
            vals, gsds, rers, dsnrs = [], [], [], []
            for x in R:
                av = self.los_angle(x)
                if av <= 0:
                    vals.append(np.nan); gsds.append(np.nan); rers.append(np.nan); dsnrs.append(np.nan)
                    continue
                gsd_h = self.alpha_s["h"] * x
                gsd_v = self.alpha_s["v"] * x
                gsd_w = math.sqrt(gsd_h * gsd_v) / math.sin(av) ** 0.25              # Eq. (3.230)
                rh, rv = self._rer("h", x), self._rer("v", x)
                X, Y = max(rh, rv), min(rh, rv)
                rer = (X * Y * Y) ** (1.0 / 3.0) if Y > 0 else np.nan                  # Eq. (3.233)
                s = self.signal_state(x, atm)
                if self.cat == "Thermal":
                    dsnr = s["eds"] / math.hypot(self.netd, self.ietd)                   # (3.234)
                else:
                    dsnr = s["eds"] / math.hypot(s["nes"], s["ies"])                      # (3.235)
                if not np.isfinite(rer) or rer <= 0 or dsnr <= 0:
                    n = np.nan
                else:
                    lr = math.log10(rer)
                    n = 4.274 - 3.32 * math.log10(gsd_w) + 3.32 * (1 - math.exp(-1.9 / dsnr)) * lr - \
                        2 * lr ** 4 - 1.8 / dsnr                                          # Eq. (3.227)
                vals.append(n); gsds.append(gsd_w); rers.append(rer); dsnrs.append(dsnr)
            out["atm"].append({"label": atm.label, "R": R, "niirs": np.array(vals), "gsd": np.array(gsds),
                               "rer": np.array(rers), "dsnr": np.array(dsnrs)})
        return out


    def _info(self, res):
        I = []

        def add(sec, name, val, unit=""):
            I.append((sec, name, val, unit))

        g = "Imager geometry"
        add(g, "Category / type", "%s / %s" % (self.cat, self.p["imager_type"]))
        add(g, "Field of view h x v", "%.3f x %.3f" % (math.degrees(self.fov["h"] * 1e-3),
                                                       math.degrees(self.fov["v"] * 1e-3)), "deg")
        add(g, "Field of view h x v", "%.2f x %.2f" % (self.fov["h"], self.fov["v"]), "mrad")
        add(g, "Number of samples h x v", "%d x %d" % (self.n_sam["h"], self.n_sam["v"]))
        add(g, "Micro-scan / steps", "%s / %dx%d" % (self.ms, self.nstep["h"], self.nstep["v"]))
        add(g, "Detector angular subtense h x v", "%.4f x %.4f" % (self.das["h"], self.das["v"]), "mrad")
        add(g, "Sampling distance h x v", "%.4f x %.4f" % (self.alpha_s["h"], self.alpha_s["v"]), "mrad")
        add(g, "Nyquist frequency h x v", "%.3f x %.3f" % (self.r_N["h"], self.r_N["v"]), "1/mrad")
        add(g, "Sensitive detector area", "%.3g" % (self.A_det * 1e12), "um^2")
        add(g, "Frame interval / maximum integration time", "%.4g / %.4g" % (1e3 / self.frame_rate, self.t_max * 1e3),
            "ms")
        ds_ = "Data sources"
        add(ds_, "Optics MTF route", {"A": "Mode A - computed (diffraction + aberration model)",
                                      "B": "Mode B - imported optics MTF (no extra diffraction)",
                                      "C": "Mode C - imported device prefilter MTF (optics/detector submodels "
                                           "bypassed)"}[self.mtf_mode])
        am = self.p["atmosphere"]
        if not self.lab:
            add(ds_, "Atmospheric transmission", "spectral import" if am["mode"] == "spectral" else
                ("fast mode, preset '%s'" % am.get("preset") if am.get("preset", "custom") != "custom" else
                 "fast mode (Beer-Lambert, user extinction)"))
            add(ds_, "Path radiance", "imported" if any(a.path is not None for a in self.atms) else "modelled")
        st = self.p["stab"]
        add(ds_, "Stabilization", "neglected" if st["neglect"] else
            ("measured jitter time series" if st.get("jitter_mode") == "measured" else "vibration models"))
        if "fom_measured" in res:
            add(ds_, "Figure of merit for ranges", "measured %s" % res["fom_measured"]["kind"]
                if res["fom_measured"]["use"] == "replace" else "modelled (measured %s for comparison)" %
                res["fom_measured"]["kind"])
        for (z, _t), (_rg, _m, js) in sorted(self._jit_cache.items()):
            add(ds_, "Jitter %s: rms / intra-frame / frame-to-frame" % z, "%.3g / %.3g / %.3g" % (
                js["rms"] * 1e3, js["intra_rms"] * 1e3, js.get("sigma_frame", 0.0) * 1e3), "urad")
            add(ds_, "Jitter %s: offset / drift" % z, "%.3g / %.3g" % (js["offset"] * 1e3, js["drift"] * 1e3),
                "urad / urad/s")
        o = "Optics"
        add(o, "Effective focal length", "%.2f" % self.f_eff, "mm")
        add(o, "Clear pupil area / effective diameter", "%.1f / %.2f" % (self.A_pup, self.D_eff), "mm^2 / mm")
        add(o, "Effective F-number", "%.3f" % self.F_eff)
        add(o, "Diffraction cut-off at %.2f um (h)" % self.lam_peak, "%.3f" % (self.diff["h"].d_max / self.lam_peak),
            "1/mrad")
        add(o, "Optics MTF", getattr(self, "zemax_mtf_label", None) or "TRM4 model (diffraction %s, aberration %s)" % (
            self.p["optics"]["diffraction"], self.p["optics"]["aberration"]))
        add(o, "Optics transmission", self.tau_label)
        add(o, "Optics x filter transmission (band mean)", "%.3f" % float(np.mean(self.tau_o)))
        if self.eta_cs is not None:
            add(o, "Cold shield efficiency / eff. F-number", "%.3f / %.3f" % (self.eta_cs, self.F_cs))
        s = "Sensitivity"
        add(s, "Detector spectral window", "%.2f - %.2f (%s)" % (self.band[0], self.band[1], self.qe_label), "um")
        add(s, "Peak responsivity wavelength / QE", "%.3f / %.1f" % (self.lam_peak, self.qe_peak), "um / %")
        if self.cat == "Thermal":
            if not self.uncooled:
                add(s, "Integration time", "%.4g" % (self.t_ref * 1e3), "ms")
                add(s, "Integration duty cycle", "%.3f" % (self.t_ref / self.t_max))
                add(s, "Well fill (background)", "%.1f" % self.wellfill_ref, "%")
                if hasattr(self, "t50"):
                    add(s, "Integration time for 50 % / 100 % well fill", "%.4g / %.4g" % (self.t50 * 1e3, self.t100 * 1e3), "ms")
                fl = self.lab_flux
                add(s, "Background carriers per frame", "%.4g" % (fl["jB"] * self.A_det * self.t_ref), "e-")
                add(s, "Carrier flux: scene / optics / device / cold shield",
                    "%.3g / %.3g / %.3g / %.3g" % ((fl["jB_scene"],) + self.j_internal_parts), "1/(s m^2)")
                add(s, "Signal per Kelvin (dN/dT)", "%.4g" % self.dndt, "e-/K")
                add(s, "Temporal noise (detector output)", "%.4g" % self.sigma_B, "e-")
                add(s, "NETD calculated (detector output)", "%.2f" % (self.netd_calc * 1e3), "mK")
            add(s, "NETD used", "%.2f" % (self.netd * 1e3), "mK")
            add(s, "IETD used", "%.2f" % (self.ietd * 1e3), "mK")
        else:
            st = self.ref_state
            add(s, "Reference range", "%.3g" % self.R_ref, "km")
            add(s, "Integration time", "%.4g" % (st["t_int"] * 1e3), "ms")
            add(s, "Integration duty cycle", "%.3f" % (st["t_int"] / self.t_max))
            add(s, "Well fill (background)", "%.2f" % st["wellfill"], "%")
            add(s, "Target / background carriers", "%.4g / %.4g" % (st["N_T"], st["N_B"]), "e-")
            add(s, "Difference signal", "%.4g" % st["ds"], "e-")
            add(s, "NES (temporal noise)", "%.4g" % st["nes"], "e-")
            add(s, "IES (fixed pattern noise)", "%.4g" % st["ies"], "e-")
            if st["nes"] > 0:
                add(s, "SNR (difference signal / NES)", "%.3g" % (st["ds"] / st["nes"]))
            if st["N_T"] + st["N_B"] > 0:
                add(s, "Target contrast (N_T-N_B)/(N_T+N_B)", "%.4f" % ((st["N_T"] - st["N_B"]) / (st["N_T"] + st["N_B"])))
            if self.turbulence_active() and self.R_ref > 0:
                add(s, "Fried parameter r0 at reference range", "%.4g" % (self._turb_table(self.R_ref)[2] * 100), "cm")
        n = "Noise / observer"
        add(n, "Independent frames integrated by the eye", "%.3g" % self.n_int_frames)
        add(n, "Frame integration factor FR_int", "%.3g" % self.fr_int)
        add(n, "Spatial noise bandwidth h x v", "%.3f x %.3f" % (self.df_I["h"], self.df_I["v"]))
        add(n, "System magnification", "%.3f" % self.m_sys)
        add(n, "Eye PSF width Gamma", "%.4f" % self.gamma_eye)
        add(n, "Displayed pixels h x v", "%d x %d" % (self.n_fov["h"], self.n_fov["v"]))
        f = res["fom"]
        for z in "hv":
            rp, val = f[z]["rp"], f[z]["val"]
            v = np.interp(self.r_N[z], rp, val)
            add("Figure of merit", "%s at Nyquist (%s)" % (f["name"], z), "%.4g" % v, f["unit"])
        db = res.get("dashboard")
        if db:
            for z in "hv":
                m50 = db["mtf"][z]["mtf50"]
                add("Figure of merit", "System prefilter MTF50 (%s)" % z, "%.4g" % m50 if m50 else "-", "1/mrad")
                add("Figure of merit", "System prefilter MTF at Nyquist (%s)" % z, "%.3f" % db["mtf"][z]["mtf_nyq"])
            add("Figure of merit", "CNR (%s)" % db["cnr_label"], "%.3g" % db["cnr"])
        rg = res.get("range")
        if rg:
            for a in rg["atm"]:
                for t in a["tasks"]:
                    R0 = t["R0"]
                    txt = "< %.3f" % a["R"][0] if R0 is None else ("> %.0f" % a["R"][-1] if not np.isfinite(R0) else "%.3f" % R0)
                    add("Range performance", "%s (%g lp) - %s" % (t["name"], t["lp"], a["label"]), txt, "km")
        return I


def run_project(project, progress=None):
    """Run the model for a project dictionary; returns (model, results)."""
    m = TRM4Model(project, progress)
    res = m.run()
    return m, res
