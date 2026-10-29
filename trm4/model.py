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
from . import extensions as X
from .amop import amop as amop_sim

MODEL_VERSION = "TRM4.v3 model / TRM_HADMAAv1 engine 2.7"
MODEL_REFERENCE = "Fraunhofer IOSB TR 2021/04 (TRM4.v3 parameter description and model documentation)"
# version of the acceptance/regression suite (kept separate from the model version, field map App. D)
VALIDATION_VERSION = "acceptance suite FM-1.1 (field map v1.1, 14.10.2026)"

# Components of the imaging chain (field map Sec. 15.4).  Every active data source states which
# components it covers; one component must not be covered by two sources (no double counting).
# Radiometric attenuation is not an optical MTF component; measured NETD and the modelled electrical
# noise are alternatives; an end-to-end measurement may already contain detector and processing.
COMPONENTS = ("optics", "diffraction", "detector_aperture", "electronics", "processing", "motion", "turbulence",
              "atmosphere_radiometry", "path_radiance")


class ModelError(Exception):
    pass


class ModelCoverageError(ModelError):
    def __init__(self, overlap, source):
        self.overlap, self.source = set(overlap), source
        super().__init__("Model component(s) %s would be counted twice (already covered when adding '%s')." %
                         (", ".join(sorted(overlap)), source))


def check_coverage(sources):
    """Raise ModelCoverageError when a chain component is contributed by more than one source."""
    included = set()
    for src in sources:
        overlap = included.intersection(src["components"])
        if overlap:
            raise ModelCoverageError(overlap, src["source"])
        included.update(src["components"])
    return included


def _deg(x):
    return math.radians(float(x))


def run_id(project):
    """Deterministic identifier of a calculation: all model inputs (incl. imported file contents) + model version.

    The same inputs give the same run ID, so a reported result can be traced back to its configuration
    (field map Sec. 12.1, P0 transparency).  Name, saved scenarios and analysis settings are not inputs.
    """
    import hashlib
    import json
    p = P.deep_merge(P.DEFAULT_PROJECT, project or {})
    for k in ("name", "scenarios", "uncertainty"):
        p.pop(k, None)
    blob = json.dumps(p, sort_keys=True, default=str) + "|" + MODEL_VERSION
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


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
            # Beer-Lambert per wavelength from one path length (initial transmission: weather-derived extinction)
            with np.errstate(divide="ignore"):
                k = -np.log(np.maximum(tab[:, 0], 1e-300)) / R[0]
            return self.tau0 * np.exp(-k * R_km)
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
        self._psd_cache = {}
        self.r_motion_zero = {}       # first zero of the signed motion MTF per direction (set in run)
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
        self.still = p["mode"]["stream"] == "still"          # NIIRS forces Still only for itself (see _niirs)

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
        area_pix = pitch["h"] * pitch["v"] * nb["h"] * nb["v"]
        # hardware (charge) binning reads the summed charge once; digital binning sums n read-outs
        self.bin_kind = b.get("bin_kind", "charge")
        self.n_reads = nb["h"] * nb["v"] if self.bin_kind == "digital" else 1
        # --- electronic pseudo interlace, Eqs. (3.6)-(3.8)
        self.interlace = b["interlace"]
        if self.interlace == "pseudo":
            area *= 2
            area_pix *= 2
            a_eff["v"] = pitch_eff["v"] + a_eff["v"]
            n_stor *= 2
        # QE convention (research review Sec. 3.5 / 7.2): TRM's QE refers to the active (sensitive) area; a
        # total / EMVA 1288 QE refers to the full pixel area and already contains fill factor and microlenses.
        # A_det is the QE-consistent reference area used for every photon -> carrier conversion.
        self.qe_basis = d.get("qe_basis", "unspecified")
        if self.qe_basis not in ("unspecified", "active_area", "pixel_area"):
            raise ModelError("Unknown QE basis %r" % self.qe_basis)
        self.A_active = area * 1e-12                       # [m^2]
        self.A_pixel = area_pix * 1e-12
        self.fill_factor = min(self.A_active / self.A_pixel, 1.0) if self.A_pixel > 0 else 1.0
        self.A_det = self.A_pixel if self.qe_basis == "pixel_area" else self.A_active
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
        # --- readout: global shutter or rolling shutter (row-sequential exposure start)
        self.readout = b.get("readout", "global")
        self.t_readout = float(b.get("readout_ms", 0.0)) * 1e-3
        if self.readout == "rolling":
            if self.t_readout <= 0:
                raise ModelError("Rolling-shutter readout selected: the frame readout time must be > 0 ms")
            if self.t_readout > 1.0 / self.frame_rate * 1.0001:
                self.warn("Rolling-shutter readout time %.3g ms is longer than the frame interval %.3g ms." %
                          (self.t_readout * 1e3, 1e3 / self.frame_rate))
        # --- sensor timing architecture (research review Sec. 3.1 / 3.8): t_max = 1/FPS only holds when the
        # exposure may overlap the readout of the previous frame; otherwise readout and guard time are subtracted.
        self.exp_overlap = bool(b.get("exp_overlap", True))
        guard = max(float(b.get("guard_ms", 0.0) or 0.0), 0.0) * 1e-3
        t_timing = t_max - guard
        if not self.exp_overlap:
            t_timing -= max(float(b.get("readout_ms", 0.0) or 0.0), 0.0) * 1e-3
        if t_timing <= 0:
            raise ModelError("Frame timing leaves no exposure time: frame interval %.4g ms minus readout / guard time "
                             "is <= 0" % (t_max * 1e3))
        self.t_timing = t_timing
        self.t_hw_min = max(float(b.get("exp_min_ms", 0.0) or 0.0), 0.0) * 1e-3
        self.t_hw_max = max(float(b.get("exp_max_ms", 0.0) or 0.0), 0.0) * 1e-3 or float("inf")
        if self.t_hw_max < self.t_hw_min:
            raise ModelError("Hardware maximum exposure is shorter than the minimum exposure")

        # --- signal processing factors
        self.zoom = max(1, int(round(dsp["zoom"])))
        self.lrep = max(1, int(round(dsp["lrep"])))
        self.crep = max(1, int(round(dsp["crep"])))
        self.rep = {"h": self.crep, "v": self.lrep}
        self.n_frames = max(1, int(dsp["n_frames"])) if dsp["frames_on"] else 1
        self.iir = float(dsp["iir_alpha"]) if dsp["iir_on"] else 0.0
        if not 0 <= self.iir < 1:
            raise ModelError("IIR alpha must be in [0, 1)")

        # --- observer: TRM4 standard observer (legacy), user-defined human viewing, or an algorithm that reads
        # the digital frames (no display, no eye) - field map Sec. 15.2.8
        self.observer = disp.get("observer", "legacy")
        if self.observer not in ("legacy", "human", "algorithm"):
            raise ModelError("Unknown observer type %r" % self.observer)
        self.algo = self.observer == "algorithm"
        # --- display, number of displayed pixels (3.26), (3.28); magnification (3.16)
        self.n_fov = {"h": self.n_sam["h"] * self.zoom * self.crep, "v": self.n_sam["v"] * self.zoom * self.lrep}
        if not self.algo and (self.n_fov["h"] > disp["n_h"] or self.n_fov["v"] > disp["n_v"]):
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
        if dist > 0.02 and not self.algo:
            self.warn("Geometrical distortion of the displayed image is %.1f %%." % (100 * dist))

        self.snr_th = float(disp["snr_th"])
        self.t_eye = float(disp["t_eye_s"])
        self._setup_operating_point()

    def _setup_operating_point(self):
        """Detector operating point: QE basis, saturation capacity node, dark current (research review Sec. 3.5-3.11).

        The storage capacity of TRM refers to its accumulation node; operational saturation can occur earlier at
        an input-referred camera saturation or at the ADC.  The usable capacity is the smallest of the stated
        limits and is the one used for well fill and exposure selection (spec wording Sec. 7.1 / 7.3).
        """
        d = self.p["detector"]
        nb = self.nbin["h"] * self.nbin["v"] * (2 if self.interlace == "pseudo" else 1)
        self.op_mode = str(d.get("op_mode", "") or "").strip()
        self.cap_node = d.get("cap_node", "unknown")
        limits = [(self.n_stor, {"pixel": "physical pixel full well", "roic": "ROIC / storage node",
                                 "camera": "camera saturation capacity (input-referred)"}.get(
                                     self.cap_node, "storage capacity (node not stated)"))]
        sat = float(d.get("sat_e", 0.0) or 0.0)
        if sat > 0:
            limits.append((sat * nb, "camera saturation capacity (input-referred)"))
        bits = int(d.get("adc_bits", 0) or 0)
        if bits > 0 and d["adc_mode"] == "carriers" and float(d["lsb_e"]) > 0:
            limits.append(((2 ** bits) * float(d["lsb_e"]), "ADC full scale (%d bit)" % bits))
        limits = [x for x in limits if x[0] > 0]
        if limits:
            self.n_use, self.cap_limit = min(limits, key=lambda x: x[0])
        else:
            self.n_use, self.cap_limit = 0.0, "not specified"
        # only an input-referred camera saturation capacity verifies the well fill; a physical full well does not
        self.cap_verified = sat > 0 or self.cap_node == "camera"
        # dark current: single value or calibrated table I_dark(T_sensor) (log-linear interpolation, no generic
        # temperature-doubling rule)
        self.dark_A = float(d["dark_A"])
        self.dark_label = "%.3g A (single value)" % self.dark_A
        if d.get("dark_mode", "value") == "table":
            pts = ph.parse_table(d.get("dark_table", ""))
            if len(pts) < 2:
                raise ModelError("Dark current table needs at least two 'T_sensor[K] I_dark[A]' rows")
            pts = pts[np.argsort(pts[:, 0])]
            if np.any(pts[:, 1] <= 0):
                raise ModelError("Dark current table values must be > 0 A")
            T = float(d.get("T_sensor_K", 0.0) or 0.0)
            if T <= 0:
                raise ModelError("Dark current table selected: the sensor operating temperature must be > 0 K")
            if T < pts[0, 0] or T > pts[-1, 0]:
                self.warn("Sensor temperature %.1f K is outside the dark current table (%.1f-%.1f K): the edge value "
                          "is used, not extrapolated." % (T, pts[0, 0], pts[-1, 0]))
            self.dark_A = float(np.exp(np.interp(T, pts[:, 0], np.log(pts[:, 1]))))
            self.dark_label = "%.3g A at %.1f K (table, %d points)" % (self.dark_A, T, len(pts))

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
        disp = self.p["display"]
        if self.algo:
            self.assume("Algorithm observer '%s': display and eye MTF are not applied, no eye integration; the TRM4 "
                        "threshold SNR %.2g and line-pair criteria are human-observer calibrations." %
                        (disp.get("algo_id") or "not identified", float(disp["snr_th"])))
            if not str(disp.get("algo_calib", "")).strip():
                self.warn("Algorithm observer without a calibration data set: the ranges are an uncalibrated estimate, "
                          "not a detection probability of the algorithm.")
        elif not disp["neglect_eye"]:
            self.assume("%s: Kornfeld-Lawson eye MTF, threshold SNR %.2g, eye integration %.3g s." %
                        ("Human observer (user-defined viewing conditions)" if self.observer == "human" else
                         "Standard observer (legacy-neutral)", float(disp["snr_th"]), float(disp["t_eye_s"])))
        if self.cat != "Thermal" and self.p["irradiance"]["mode"] != "none":
            self.assume("Illumination is specified at the target (source-to-target attenuation already included); the "
                        "atmosphere attenuates only the target-to-sensor path.")
        clutter = t.get("clutter", "not_specified")
        self.assume("Background clutter %s is not modelled - ranges assume a uniform background%s." % (
            "(not specified)" if clutter == "not_specified" else "'%s'" % clutter,
            " (scene %s)" % t["scene_id"] if str(t.get("scene_id", "")).strip() else ""))
        expect = P.task_preset_values(self.p)
        if expect is not None:
            vals = tuple(float(x["lp"]) for x in t["tasks"][:3])
            if vals != tuple(float(v) for v in expect):
                self.warn("Task criteria (%s) differ from the selected preset '%s' - the entered values are used." %
                          (" / ".join("%g" % v for v in vals),
                           P.TASK_PRESETS.get(t.get("task_preset"), ("?",))[0]))

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
                if a["mode"] == "weather":
                    self.atms.append(self._weather_atmosphere(i, at, path))
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
        if (a["mode"] == "spectral" or path is not None) and not self.lab:
            meta = a.get("meta") or {}
            missing = [k for k in ("geometry", "source", "conditions") if not str(meta.get(k, "")).strip()]
            if missing:
                self.assume("Imported atmospheric data: %s not documented (path geometry slant/horizontal, generating "
                            "model e.g. MODTRAN version, weather conditions)." % ", ".join(missing))
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

    def _weather_atmosphere(self, i, at, path):
        """Atmosphere slot from visual range, relative humidity and air temperature (extension): spectral extinction
        = aerosol (Kruse / Kim) + water-vapour continuum (Roberts 1976, 8-14 um), Beer-Lambert per wavelength."""
        V, T, rh = float(at["V_km"]), float(at["T_air_K"]), float(at.get("rh_pct", 50.0))
        if V <= 0 or T <= 0 or not 0 <= rh <= 100:
            raise ModelError("Atmosphere %d from the weather: visual range and air temperature must be > 0, relative "
                             "humidity in [0, 100] %%" % (i + 1))
        if not 0 < float(at["tau0"]) <= 1:
            raise ModelError("Atmosphere %d: initial transmission must be in (0, 1]" % (i + 1))
        total, aer, wv = X.weather_extinction(self.lam, V, T, rh)
        if not hasattr(self, "weather"):
            self.weather = []
            lo, hi = self.lam[0], self.lam[-1]
            if hi > 2.6 and lo < X.CONTINUUM_BAND_UM[0]:
                self.warn("Extinction from the weather: below 8 um (MWIR, edge of the 6.3 um water band) gas and "
                          "water-vapour absorption is not modelled - the derived extinction is aerosol only there and "
                          "optimistic in clear air; import a spectral transmission (e.g. MODTRAN) or enter the "
                          "extinction coefficient.")
            self.assume("Extinction from the weather (%s): aerosol from the visual range, wavelength exponent Kruse "
                        "(V > 6 km) / Kim et al. 2001 (V < 6 km); water-vapour continuum 8-14 um after Roberts, Selby "
                        "& Biberman 1976 at sea-level pressure; line absorption of H2O, CO2 and O3 is not included "
                        "(a lower bound of the clear-air infrared extinction); horizontal homogeneous path." %
                        X.EXTENSION)
        if V < 1.0:
            self.warn("Atmosphere %d: visual range %.3g km < 1 km (fog) - the aerosol model is weak there; use measured "
                      "extinction." % (i + 1, V))
        spec = {"lam": self.lam, "R": np.array([1.0]), "tau": np.exp(-total)[:, None]}
        T_air = self.T_B if self.cat == "Thermal" else T
        F_PR = 0.0 if self.cat == "Thermal" else float(at["F_PR"])
        x = Atmosphere("Atm %d (V=%g km, RH %g %%)" % (i + 1, V, rh), 0.0, at["tau0"], T_air, F_PR, spec=spec, path=path)
        self.weather.append({"slot": i, "V_km": V, "T_K": T, "rh_pct": rh, "aerosol": aer, "water": wv,
                             "rho_w": X.water_vapour_density(T, rh), "atm": x})
        return x

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
    def flux(self, R_km, atm, qe=True):
        """Integrated carrier flux densities [carriers/(s m^2)] for target and background at range R.

        qe=False gives photon flux densities [photons/(s m^2)] instead (research review Sec. 4.1: photon
        arrival rate and photoelectron generation rate are reported separately).
        """
        lab = atm is None
        tau = 1.0 if lab else atm.tau(R_km)
        tau_l = 1.0 if lab else atm.tau_lam(R_km)            # spectral array for imported atmospheres
        av = self.los_angle(R_km)
        F_T, F_B = self.irr_factors(av)
        F2 = self.F_eff ** 2
        k = self.pp * (self.eta if qe else 1.0) * self.tau_o
        emis_T = math.pi / (4 * F2) * self.L_T * self.eps_T                    # (3.110)
        emis_B = math.pi / (4 * F2) * self.L_B * self.eps_B
        refl_T = self.I * F_T * self.rho_T / (4 * F2)                          # (3.111)
        refl_B = self.I * F_B * self.rho_B / (4 * F2)
        jT = k * (emis_T + refl_T) * tau_l
        jB = k * (emis_B + refl_B) * tau_l
        # spectral path radiance L_path(lambda, R) [W/(m^2 sr um)]: L_sensor = tau L_scene + L_path
        L_path = np.zeros_like(self.lam)
        if not lab and atm.path is not None:
            L_path += atm.path_radiance(R_km, self.lam, tau_l)                             # imported L_path
        elif not lab:
            if self.cat != "Visible":
                L_path += ph.planck(self.lam, atm.T_air) * (1 - tau_l)                      # (3.107)
            if self.cat != "Thermal":
                L_path += self.I * atm.F_PR * (1 - tau_l) / math.pi                         # (3.108)
        path = math.pi / (4 * F2) * L_path
        j_path = float(ph.trapz(k * path, self.lam))
        jT_s = float(ph.trapz(jT, self.lam))
        jB_s = float(ph.trapz(jB, self.lam))
        # band radiances at the entrance aperture (detector window, not QE weighted) [W/(m^2 sr)]
        L_sc_T = self.L_T * self.eps_T + self.I * F_T * self.rho_T / math.pi
        L_sc_B = self.L_B * self.eps_B + self.I * F_B * self.rho_B / math.pi
        rad = {"L_T": float(ph.trapz(L_sc_T * tau_l + L_path, self.lam)),
               "L_B": float(ph.trapz(L_sc_B * tau_l + L_path, self.lam)),
               "L_path": float(ph.trapz(L_path, self.lam))}
        return {"jT": jT_s + j_path + self.j_internal, "jB": jB_s + j_path + self.j_internal,
                "jT_scene": jT_s, "jB_scene": jB_s, "j_path": j_path, "dj": jT_s - jB_s, "tau": tau,
                "av": av, "radiance": rad}

    @property
    def j_dark(self):
        """Dark carrier flux density, Eq. (3.113)."""
        return self.dark_A / ph.E_CHARGE / self.A_det

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
        # well fill, Eq. (3.76) - of the usable (mode-specific) capacity, not necessarily the physical full well
        pct = float(d["wellfill_pct"])
        if self.n_use <= 0:
            raise ModelError("Well-fill option needs a storage capacity > 0")
        gain = float(d["electron_gain"])
        t = pct * self.n_use / ((jB + self.j_dark) * self.A_det * gain * 100.0)
        t_lim = min(self.t_max, self.t_timing, self.t_hw_max)
        if t > t_lim:
            self.warn("Integration time for the requested well fill exceeds the maximum possible integration "
                      "time; the maximum is used.")
            t = t_lim
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
        # digital binning: read and quantization noise of every summed read-out
        var = (NF ** 2 * 0.5 * (jT + jB) + self.j_dark) * self.A_det * g ** 2 * t_int + \
            self.n_reads * (self.n_quant(t_int) ** 2 + float(d["noise_floor_e"]) ** 2)
        return math.sqrt(var)

    def well_fill(self, jB, t_int):
        """Well fill [%] of the usable capacity, Eq. (3.138) (= storage capacity unless an earlier limit is given)."""
        g = float(self.p["detector"]["electron_gain"])
        if self.n_use <= 0:
            return float("nan")
        return 100.0 * t_int * (jB + self.j_dark) * self.A_det * g / self.n_use

    # -----------------------------------------------------------------------------------------
    def _setup_noise(self):
        """Temporal/spatial noise quantities that do not depend on range."""
        d = self.p["detector"]
        dsp = self.p["dsp"]
        if float(d["electron_gain"]) <= 0:
            raise ModelError("Electron gain must be > 0 (is %g)" % float(d["electron_gain"]))
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
        if self.algo:
            n_int = self.fr_int                     # an algorithm sees the processed frame, no eye integration
        n_int *= max(1, int(self.p["basic"]["n_sensors"]))
        self.n_int_frames = n_int
        self.g_type = 1.0          # staring / micro-scanned imagers
        self.noise_source = "Physics model (shot, dark, read and quantization noise)"
        self.noise_quality = "modelled"

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
                if not self.dndt > 0:
                    raise ModelError("The detector receives no thermal signal (dN/dT = 0): optics and filter "
                                     "transmission, quantum efficiency and integration time must all be > 0.")
                self.sigma_B = self.noise(lab_flux["jB"], lab_flux["jB"], self.t_ref)
                self.netd_calc = self.sigma_B / self.dndt
                self.netd = float(d["netd_mK"]) * 1e-3 if d["noise_mode"] == "measured" else self.netd_calc
                self.wellfill_ref = self.well_fill(lab_flux["jB"], self.t_ref)
                if self.wellfill_ref > 100:
                    self.warn("Storage gate overflow: well fill %.0f %% (calculation continues)." % self.wellfill_ref)
                # integration time for 50 % / 100 % well fill
                g = float(d["electron_gain"])
                if self.n_use > 0:
                    self.t50 = 50 * self.n_use / ((lab_flux["jB"] + self.j_dark) * self.A_det * g * 100)
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
        camera = not self.uncooled or d["noise_mode"] == "device"
        if camera:
            self._check_camera_netd()
        else:
            self.noise_source = "Detector-level NETD scaled to this optics (Eq. 3.142)"
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

    def _check_camera_netd(self):
        """Measured camera NETD: the source of truth for the temporal noise (field map Sec. 12.4, DS-01..03).

        It replaces the detector noise model (no read/dark/shot noise is added on top).  Its test
        conditions are compared with the scenario; missing conditions mark the noise data as partial.
        """
        d = self.p["detector"]
        self.noise_source = "Measured camera NETD (detector noise model not added)"
        missing = []
        TB = float(d.get("netd_TB_K", 0.0) or 0.0)
        if TB <= 0:
            missing.append("blackbody temperature")
        Fm = float(d.get("netd_F", 0.0) or 0.0)
        if Fm <= 0:
            missing.append("F-number")
        elif abs(Fm - self.F_eff) / self.F_eff > 0.05:
            self.warn("Camera NETD was measured at F/%.2f but the optics are F/%.2f: NETD scales roughly with F^2 "
                      "(factor %.2f) - the measured value is used unchanged." % (Fm, self.F_eff, (self.F_eff / Fm) ** 2))
        if not self.uncooled:
            tm = float(d.get("netd_tint_ms", 0.0) or 0.0)
            if tm <= 0:
                missing.append("integration time")
            elif self.t_ref and abs(tm * 1e-3 - self.t_ref) / self.t_ref > 0.10:
                self.warn("Camera NETD was measured with %.3g ms integration time, the scenario uses %.3g ms - the "
                          "measured value is used unchanged." % (tm, self.t_ref * 1e3))
        nf = int(d.get("netd_frames", 1) or 1)
        if nf > 1:
            self.warn("Camera NETD was measured with %d-frame averaging: TRM4 adds its own frame / eye integration, so "
                      "the temporal noise reduction may be counted twice - use the single-frame NETD." % nf)
        if not str(d.get("netd_nuc", "")).strip():
            missing.append("gain / NUC state")
        if missing:
            self.noise_quality = "partial - test conditions not documented: %s" % ", ".join(missing)
            self.assume("Measured camera NETD with partial test conditions (missing: %s)." % ", ".join(missing))
        else:
            self.noise_quality = "documented test conditions"

    def signal_state(self, R_km, atm, t=None):
        """Signal/noise state at range R for Visible/General (carriers) or Thermal (Kelvin).

        t: integration time [s] to evaluate instead of the one selected by the exposure mode (Visible/General).
        """
        fl = self.flux(R_km, atm)
        ns, fs = float(self.wi.get("noise_scale", 1.0)), float(self.wi.get("fpn_scale", 1.0))
        if self.cat == "Thermal":
            tau = fl["tau"]
            return {"flux": fl, "nes": self.netd * ns, "ies": self.ietd * fs,
                    "eds": abs(float(self.p["target"]["dT_K"])) * tau, "t_int": self.t_ref}
        d = self.p["detector"]
        if t is None:
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
        self.mtf_mode = {"zemax": "B", "measured": "B", "device": "C"}.get(o.get("mtf_source"), "A")
        # components covered by the imported curve (field map Sec. 12.3 / 15.4); the engine adds only the rest
        cov = set()
        if self.mtf_mode == "B":
            cov = {"optics"}
            if o.get("mtf_incl_detector"):
                cov.add("detector_aperture")
        elif self.mtf_mode == "C":
            cov = {"optics", "detector_aperture"}
        if cov:
            if o.get("mtf_incl_diffraction", True):
                cov.add("diffraction")
            if o.get("mtf_incl_motion"):
                cov.add("motion")
        self.mtf_cov = cov
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
                if lam0 <= 0:
                    lam0 = float(ph.trapz(lam * self.w, lam))     # signal-weighted mean wavelength of the band
                    self.assume("Single-wavelength diffraction MTF at the signal-weighted mean wavelength %.3g um."
                                % lam0)
                elif not self.band[0] <= lam0 <= self.band[1]:
                    self.warn("Wavelength for the diffraction MTF (%.2f um) is outside the imager spectral band "
                              "(can be intended to approximate aberrations)." % lam0)
                m = dm(r, lam0)
            self.diff_tab = getattr(self, "diff_tab", {})
            self.diff_tab[z] = (r, m.copy())
            if self.wi.get("no_aberr") and self.mtf_mode != "C":
                pass                                       # what-if: diffraction-limited optics
            elif zemax and "diffraction" not in cov:
                # the imported curve excludes diffraction: the computed diffraction MTF is applied once
                rf, mf = zemax[z]
                if r[-1] > rf[-1] and mf[-1] > 0.05:
                    self.warn("Imported MTF (%s, without diffraction) ends at %.3g 1/mrad with MTF %.2f; the last value "
                              "is held beyond the data." % (z, rf[-1], mf[-1]))
                m = m * np.clip(np.interp(r, rf, mf), 0.0, 1.0)
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

        # --- digital sharpening (boost > 1) enters the ranges only when credited explicitly (field map SP-01):
        # without a calibrated noise/task model a sharper-looking image must not raise the predicted range
        dsp = self.p["dsp"]
        self.boost, self.boost_off = 1.0, False
        if dsp["filter_on"]:
            for z in "hv":
                rr = np.linspace(0.0, self.r_s[z], 400)
                self.boost = max(self.boost, float(np.max(np.abs(self._fir(rr, z)))))
            if self.boost > 1.01:
                if dsp.get("credit_boost"):
                    self.assume("Digital sharpening (boost up to %.2f) is credited in the ranges with the TRM4 signal and "
                                "noise filtering - the gain is not calibrated against observer data." % self.boost)
                else:
                    self.boost_off = True
                    self.warn("Digital filter boosts the MTF up to %.2f (sharpening): it is NOT credited in the ranges "
                              "(no calibrated noise / task model). Tick 'Credit sharpening in the ranges' to include "
                              "it." % self.boost)
        comp = self.compression_blur_px()
        unmodelled = [s for s, on in (("denoising", dsp.get("pl_denoise")),
                                      ("lossy compression", dsp.get("pl_compression") == "lossy" and not comp)) if on]
        if comp:
            self.assume("Lossy compression (%s) as an equivalent Gaussian blur of %.3g pixels rms applied to the "
                        "digital frame (signal and noise), O'Shea, Jacobs & Espinola 2008 - the blur must be fitted to "
                        "the codec and bit rate in use." % (X.EXTENSION, comp))
        if unmodelled:
            self.assume("Processing not modelled: %s - the prediction does not include these steps; compare with a "
                        "measured end-to-end SFR of this processing state (Lab)." % ", ".join(unmodelled))

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
            unit = Z.stated_frequency_unit(zf["text"])
            if unit is None:
                raise ModelError("MTF file %s does not state its spatial-frequency unit - select cycles/mm or "
                                 "cycles/mrad explicitly (the unit is not guessed)." % zf.get("name", ""))
        h_key = "S" if o.get("zemax_mtf_h", "sagittal") == "sagittal" else "T"
        v_key = "T" if h_key == "S" else "S"
        kind = "Device prefilter MTF" if self.mtf_mode == "C" else \
            ("Measured lens MTF" if o.get("mtf_source") == "measured" else "Optics MTF")
        self.zemax_mtf_label = "%s imported: %s, field %d (%s), h = %s, %s%s; covers %s" % (
            kind, zf.get("name", ""), n, fd["label"], "sagittal" if h_key == "S" else "tangential",
            "cycles/mm image space" if unit == "mm" else "cycles/mrad object space", " (from file header)" if auto else "",
            ", ".join(c for c in COMPONENTS if c in self.mtf_cov))
        self._record_import(kind, zf, "field %d, %s, covers %s" % (n, "cycles/mm" if unit == "mm" else "cycles/mrad",
                                                                  "+".join(c for c in COMPONENTS if c in self.mtf_cov)))
        if auto:
            self.assume("Frequency unit of the imported MTF taken from the file header: %s." %
                        ("cycles/mm (image space)" if unit == "mm" else "cycles/mrad (object space)"))
        if len(fields) == 1:
            self.assume("The imported MTF contains one field (%s) only; it is applied to the whole field of view - "
                        "off-axis performance is not represented." % fd["label"])
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
        if "detector_aperture" in self.mtf_cov or self.wi.get("ideal_det"):
            return np.ones_like(np.asarray(r, float))      # contained in the imported MTF (no double counting)
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

    def motion_active(self):
        """Motion source in use (None when no motion MTF is applied)."""
        st = self.p["stab"]
        mode = st.get("jitter_mode", "model")
        if st["neglect"] or mode == "none" or self.wi.get("no_stab") or "motion" in self.mtf_cov:
            return None
        if mode == "model" and not (st["random_on"] or st["lin_on"] or st["sin_on"]):
            return None
        return mode

    def t_exposure(self):
        """Exposure window that links the motion model to the integration time (field map BI-01)."""
        if self.uncooled:
            return self.t_th
        return self.t_ref if self.t_ref else self.t_max

    def mtf_stab(self, r, z):
        st = self.p["stab"]
        m = np.ones_like(np.asarray(r, float))
        mode = self.motion_active()
        if mode is None:
            return m
        if mode == "measured":
            return self._jitter_mtf(r, z)                 # measured motion replaces the vibration models
        if mode == "psd":
            return self._psd_mtf(r, z)
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
        key = (z, round(t, 12), self.still)
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

    def _psd_data(self):
        if not hasattr(self, "_psd"):
            st = self.p["stab"]
            fobj = st.get("psd_file") or {}
            if not fobj.get("text"):
                raise ModelError("Angular PSD selected, but no PSD file was imported")
            try:
                d = IM.parse_psd(fobj["text"])
            except ValueError as e:
                raise ModelError("PSD file %s: %s" % (fobj.get("name", ""), e))
            unit = st.get("psd_unit", "urad2")
            conv = {}
            for z in "hv":                                  # -> mrad^2/Hz
                if unit == "urad2":
                    conv[z] = 1e-6
                elif unit == "mrad2":
                    conv[z] = 1.0
                elif unit == "pixel2":
                    conv[z] = (self.pitch_unbinned[z] / self.f[z]) ** 2
                else:
                    raise ModelError("Unknown PSD unit %r" % unit)
            self._psd = {"f": d["f"], "psd": {z: d[z] * conv[z] for z in "hv"}, "unit": unit}
            self._record_import("Line-of-sight angular PSD", fobj, "%s/Hz; %s" % (
                {"urad2": "urad^2", "mrad2": "mrad^2", "pixel2": "pixel^2"}[unit], "; ".join(d["notes"])))
            self.assume("Motion from the angular PSD: intra-frame blur and frame-to-frame jitter are approximated by "
                        "Gaussian MTFs (valid for many independent motion components within the exposure).")
            if not st.get("residual_los", True):
                self.warn("The PSD is flagged as platform (base) motion, not residual line of sight after "
                          "stabilization - the blur is overestimated if a stabilization loop is active.")
        return self._psd

    def psd_stats(self, z):
        """(sigma_intra, sigma_frame, sigma_total) [mrad] of the PSD motion for the exposure window."""
        d = self._psd_data()
        t = self.t_exposure()
        key = (z, round(t, 12))
        if key not in self._psd_cache:
            s_i, s_f, s_t = IM.psd_sigmas(d["f"], d["psd"][z], t)
            if d["f"][-1] < 1.0 / t:
                self.warn("PSD data end at %.4g Hz, below 1/exposure = %.4g Hz - the intra-frame blur may be "
                          "underestimated." % (d["f"][-1], 1.0 / t))
            self._psd_cache[key] = (math.sqrt(s_i), math.sqrt(s_f), math.sqrt(s_t))
        return self._psd_cache[key]

    def _psd_mtf(self, r, z):
        s_i, s_f, _ = self.psd_stats(z)
        m = M.mtf_random_vibration(r, s_i)                  # blur during the exposure
        if not self.still and not self.algo:
            m = m * M.mtf_random_vibration(r, s_f)          # frame-to-frame jitter seen by the eye in video
        return m

    def mtf_add(self, r, where, z):
        a = self.p["additional"]
        kind = a["%s_%s_type" % (where, z)]
        if kind == "none" or (where == "pre" and self.mtf_mode == "C"):
            return np.ones_like(np.asarray(r, float))
        return M.mtf_additional(r, kind, float(a["%s_%s_par" % (where, z)]))

    def turbulence_active(self):
        # TRM4 neglects turbulence in the Thermal category (Sec. 2.28); applying it there is an extension
        tb = self.p["turbulence"]
        return (self.cat != "Thermal" or bool(tb.get("thermal"))) and not self.lab and bool(tb["on"]) and \
            not self.wi.get("no_turb")

    def mitigation_gain(self):
        """Effective Fried-parameter gain of turbulence-mitigation processing (extension, 1 = none)."""
        return max(float(self.p["turbulence"].get("mitigation", 1.0) or 1.0), 1.0)

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
        if tb["cn2_mode"] == "r0":
            # measured / specified Fried parameter: only meaningful with its wavelength and path length;
            # scaled as r0 ~ lambda^(6/5) L^(-3/5) (uniform Cn2 along the path)
            r0_cm, lam_r, L_r = float(tb.get("r0_cm", 0)), float(tb.get("r0_lambda_um", 0)), float(tb.get("r0_L_km", 0))
            if r0_cm <= 0 or lam_r <= 0 or L_r <= 0:
                raise ModelError("Fried parameter r0 needs its reference wavelength and path length (all > 0); r0 is "
                                 "not used without its reference conditions")
            r0_ref = r0_cm / 100.0 * (1.0 / lam_r) ** 1.2 * (max(R_km, 1e-9) / L_r) ** (-0.6)
            self.assume("Turbulence from r0 = %.3g cm at %.3g um over %.3g km, scaled with lambda^(6/5) and path "
                        "length^(-3/5) (uniform Cn2 along the path)." % (r0_cm, lam_r, L_r))
        else:
            r0_ref = M.fried_parameter(1.0, R_km, cn2_of_z)        # r0 at 1 um; r0 ~ lambda^(6/5)
        lam_s = self.lam[::4]
        w = np.interp(lam_s, self.lam, self.w)
        w = w / ph.trapz(w, lam_s)
        r_max = max(self.opt_tab["h"][0][-1], self.opt_tab["v"][0][-1])
        r = np.linspace(0.0, r_max, 1200)
        L0 = max(float(tb.get("L0_m", 0.0) or 0.0), 0.0)
        if self.mitigation_gain() > 1.0 and not self._turb_cache:
            self.assume("Turbulence mitigation processing (%s): the turbulence MTF uses an effective Fried parameter "
                        "%.3g x r0 - an empirical factor; published systems report +10 to +25 %% recognition range."
                        % (X.EXTENSION, self.mitigation_gain()))
            if tb["exposure"] == "long":
                self.warn("Turbulence mitigation with the long-exposure MTF: mitigation registers the frames (image "
                          "wander removed) - the short-exposure MTF is the consistent choice.")
        if L0 > 0:
            self.assume("Turbulence with a von Karman outer scale L0 = %.3g m (first-order correction of the phase "
                        "structure function, valid for pupil separations << L0)." % L0)
        vals = []
        gain = self.mitigation_gain()        # mitigation: effective r0 of the processed image (physical r0 reported)
        for lam_i in lam_s:
            r0 = r0_ref * lam_i ** 1.2 * gain
            vals.append(M.mtf_turbulence(r, lam_i, r0, self.D_eff, tb["exposure"], L0))
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

    def _fir(self, r, z):
        """Transfer function of the FIR digital filter as entered (may exceed 1 for sharpening)."""
        dsp = self.p["dsp"]
        if not dsp["filter_on"] or (dsp["filter_dir"] == "h" and z == "v") or (dsp["filter_dir"] == "v" and z == "h"):
            return np.ones_like(np.asarray(r, float))
        coef = dsp["h_coef"] if z == "h" else dsp["v_coef"]
        kind = dsp["h_type"] if z == "h" else dsp["v_type"]
        return M.mtf_digital_filter(r, coef, kind, self.alpha_s[z])

    def compression_blur_px(self):
        """Equivalent Gaussian blur of lossy compression [pixels] (extension, 0 = none)."""
        dsp = self.p["dsp"]
        return max(float(dsp.get("comp_blur_px", 0.0) or 0.0), 0.0) if dsp.get("pl_compression") == "lossy" else 0.0

    def mtf_dig(self, r, z):
        m = np.ones_like(np.asarray(r, float)) if self.boost_off else self._fir(r, z)   # sharpening (field map SP-01)
        s = self.compression_blur_px()
        if s > 0:
            m = m * X.mtf_compression(r, s, self.alpha_s[z])      # lossy compression as per-pixel blur
        return m

    def mtf_display(self, r, z):
        if self.algo:
            return np.ones_like(np.asarray(r, float))      # an algorithm reads the digital frames
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
        if self.p["display"]["neglect_eye"] or self.wi.get("ideal_eye") or self.algo:
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
        zc = self.r_motion_zero.get(z)
        if zc is not None and rp >= zc:
            return 0.0                      # contrast-reversed bars beyond the motion MTF zero are not credited
        margin = 4.0 / max(self._pre_cutoff_cached(z, R_km), 1e-6)
        return amop_sim(lambda fr: self.pre_system(fr, z, R_km), lambda fr: self.post_system(fr, z),
                        self.alpha_s[z], rp, psf_margin=margin)

    def _motion_zero(self, z, r_max):
        """First frequency below r_max at which the signed motion MTF changes sign (None if it does not).

        Linear motion (sinc), sinusoidal vibration (J0) and frame integration have negative lobes; beyond the first
        zero the bar image is contrast-reversed (spurious resolution) and would otherwise be credited by AMOP."""
        if self.motion_active() is None:
            return None
        r = np.linspace(0.0, r_max, 4001)
        m = self.mtf_stab(r, z)
        idx = np.nonzero(m <= 0)[0]
        if not idx.size or idx[0] == 0:
            return None
        i = idx[0]
        return float(r[i - 1] + (r[i] - r[i - 1]) * m[i - 1] / (m[i - 1] - m[i]))

    def _pre_cutoff_cached(self, z, R_km):
        key = ("cut", z, round(R_km, 9) if self.turbulence_active() else 0.0)
        if key not in self._amop_cache:
            self._amop_cache[key] = self._pre_cutoff(z, R_km)
        return self._amop_cache[key]

    def amop_table(self, R_km, z, rp):
        """AMOP on the frequency grid rp -> (rp, AMOP), refined at the resolution limit.

        Where AMOP first falls to <= 0.1 % the bracket is narrowed by bisection and its ends are added to the table,
        so the limiting bar frequency (and with it the range when the signal is ample) varies continuously with the
        inputs instead of jumping by whole grid steps (~8 %)."""
        vals = []
        zeros = 0
        for x in rp:
            if zeros >= 3:
                vals.append(0.0)
                continue
            a = self.amop_direct(R_km, x, z)
            vals.append(a)
            zeros = zeros + 1 if a <= 0.001 else 0
        rp, vals = np.asarray(rp, float), np.array(vals)
        dead = np.nonzero(vals <= 0.001)[0]
        if dead.size and dead[0] > 0:
            k = dead[0]
            lo, a_lo, hi, a_hi = rp[k - 1], vals[k - 1], rp[k], vals[k]
            for _ in range(10):
                mid = math.sqrt(lo * hi)
                a = self.amop_direct(R_km, mid, z)
                if a > 0.001:
                    lo, a_lo = mid, a
                else:
                    hi, a_hi = mid, a
            new = [(x, a) for x, a in ((lo, a_lo), (hi, a_hi)) if rp[k - 1] < x < rp[k]]
            if new:
                rp = np.concatenate([rp[:k], [x for x, _ in new], rp[k:]])
                vals = np.concatenate([vals[:k], [a for _, a in new], vals[k:]])
        return rp, vals

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
        # below the tabulated band the 4-bar pattern no longer fits the simulation window and AMOP is flat there:
        # use the band's lowest frequency, as the tabulated path does
        return self.amop_direct(R_km, max(rp, 0.02 * self.r_N[z]), z)

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
    def _validate_inputs(self):
        """Physical bounds of inputs that are otherwise only parsed as numbers (sensitivity study, report Ch. 6.4)."""
        p = self.p
        o, d, disp, tg, tb = p["optics"], p["detector"], p["display"], p["target"], p["turbulence"]
        checks = [("Target width", tg["W_m"], "> 0", lambda v: v > 0),
                  ("Target height", tg["H_m"], "> 0", lambda v: v > 0),
                  ("Target depth", tg["D_m"], ">= 0", lambda v: v >= 0),
                  ("Background temperature [K]", tg["T_bg_K"], "> 0", lambda v: v > 0),
                  ("Threshold SNR", disp["snr_th"], "> 0", lambda v: v > 0),
                  ("Eye integration time", disp["t_eye_s"], "> 0", lambda v: v > 0)]
        if o["aberration"] == "q":
            checks.append(("Aberration parameter q (MTF_diff^q)", o["q"], ">= 1", lambda v: v >= 1))
        if d["cte_on"]:
            checks += [("Charge transfer efficiency (%s)" % z, d["cte_" + z], "in (0, 1]", lambda v: 0 < v <= 1)
                       for z in "hv"]
        if d["tint_mode"] == "duty":
            checks.append(("Integration duty cycle", d["duty"], "in (0, 1]", lambda v: 0 < v <= 1))
        if d["tint_mode"] == "wellfill":
            checks.append(("Well fill", d["wellfill_pct"], "in (0, 100] %", lambda v: 0 < v <= 100))
        if tb["on"] and tb["cn2_mode"] != "r0":
            checks.append(("Cn2", tb["cn2"], ">= 0", lambda v: v >= 0))
        for i, at in enumerate(p["atmosphere"]["atm"]):
            if at.get("on") and "F_PR" in at:
                checks.append(("Atm %d path radiance factor" % (i + 1), at["F_PR"], ">= 0", lambda v: v >= 0))
        for label, v, rule, ok in checks:
            v = float(v)
            if not (math.isfinite(v) and ok(v)):
                raise ModelError("%s must be %s (is %g)" % (label, rule, v))

    def run(self):
        self.progress("Setting up imager geometry", 0.02)
        self._validate_inputs()
        self._setup_geometry()
        self._setup_spectral()
        self._setup_atmospheres()
        self._setup_optics()
        self._setup_noise()
        self._setup_criteria()
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
        self._motion_checks()
        self._input_semantics_checks()
        self.exposure = self._exposure_budget()
        self.coverage = self._coverage()
        self.nps = self._nps_check()

        # MTF curves
        res["mtf"] = self._mtf_curves(R_ref)

        # AMOP tables
        self.progress("Simulating AMOP (4-bar pattern imaging)", 0.15)
        rp_max = {z: min(2.5 * self.r_s[z], self.opt_tab[z][0][-1]) for z in "hv"}
        self.r_motion_zero = {}
        for z in "hv":
            zc = self._motion_zero(z, rp_max[z])
            if zc is not None:
                self.r_motion_zero[z] = zc
                rp_max[z] = max(zc, 0.03 * self.r_N[z])
        if self.r_motion_zero:
            self.assume("Bar frequencies above the first zero of the motion MTF (%s) are not credited: beyond it the "
                        "bar image is contrast-reversed (spurious resolution)." %
                        ", ".join("%s %.3g 1/mrad" % (z, v) for z, v in sorted(self.r_motion_zero.items())))
        self.amop_tab = {}
        for z in "hv":
            rp = np.logspace(np.log10(0.02 * self.r_N[z]), np.log10(rp_max[z]), 70)
            self.amop_tab[z] = self.amop_table(R_ref, z, rp)
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
            res["dashboard"]["context"]["validation"] = "compared with measured data (%s)%s" % (
                ", ".join(it["what"] for it in val["items"]),
                "; metadata incomplete" if val.get("missing_meta") else "")
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
            d = self.p["detector"]
            rn, g = float(d["noise_floor_e"]), float(d["electron_gain"])
            if rn > 0 and 0 <= st["N_B"] * g < rn ** 2:
                self.warn("Low signal at the reference range: %.3g background carriers per frame - the read noise "
                          "(%.3g e-) dominates the photon shot noise (read-noise limited)." % (st["N_B"], rn))

    def scan_smear_px(self):
        """Image smear per exposure window of the linear motion (scan / pan) in pixels {h, v}: velocity x
        thermal time constant (microbolometer) or x integration time (photon detector); None without linear motion."""
        st = self.p["stab"]
        if self.motion_active() != "model" or not st["lin_on"]:
            return None
        t = self.t_exposure()
        return {z: abs(float(st["lin_" + z])) * t / self.alpha_s[z] for z in "hv"}

    def _motion_checks(self):
        """Scan smear (report phase 3) and rolling shutter: the row-to-row delay distorts geometry; it is not blur
        (field map Sec. 15.2.3)."""
        st = self.p["stab"]
        sm = self.scan_smear_px()
        if sm and self.uncooled and max(sm.values()) > 1.0:
            self.warn("Microbolometer scan smear: the linear image motion moves the image by %.2f (h) / %.2f (v) pixels "
                      "within one thermal time constant (%.3g ms) - the exponential smear MTF of the detector response "
                      "is applied; an image velocity below %.3g mrad/s keeps it below one pixel." % (
                          sm["h"], sm["v"], self.t_th * 1e3, min(self.alpha_s.values()) / self.t_th))
        jit = self.motion_active()
        if not self.lab and (jit is None or jit == "model" and not st["random_on"]):
            ifov = min(self.alpha_s.values())
            if X.TYPICAL_JITTER_MRAD > ifov / 3.0:
                self.assume("No line-of-sight jitter: a typical residual jitter of %.0f urad rms (US Army NV-IPM "
                            "practice) is %.2f IFOV here (> 1/3) and would shorten the ranges - without it the ranges "
                            "of this narrow field of view are optimistic (preset on page 'Stabilization & MTFs')." % (
                                X.TYPICAL_JITTER_MRAD * 1e3, X.TYPICAL_JITTER_MRAD / ifov))
        if self.readout != "rolling":
            return
        self.assume("Rolling-shutter readout %.3g ms: each row is exposed for the integration time (motion blur uses "
                    "the exposure); the row-to-row delay only distorts the frame geometry." % (self.t_readout * 1e3))
        if self.motion_active() == "model" and st["lin_on"]:
            for z, key, what in (("h", "lin_h", "shear"), ("v", "lin_v", "stretch / compression")):
                px = abs(float(st[key])) * self.t_readout / self.alpha_s[z]
                if px > 0.5:
                    self.warn("Rolling shutter: the %s image motion %s the frame by %.2f pixels during the readout - "
                              "a geometric distortion that is not included in the MTF." % (
                                  "horizontal" if z == "h" else "vertical",
                                  "shears" if z == "h" else "stretches / compresses", px))

    def _input_semantics_checks(self):
        """Mandatory input-semantics checks before DRI estimates (research review Sec. 3.5, 3.6, 3.10, 3.12, 3.18,
        3.21, 3.24 and Sec. 10): QE basis vs pixel area, saturation-capacity basis, MTF / atmosphere metadata,
        noise measurement port and preset lifecycle records."""
        d, o, am = self.p["detector"], self.p["optics"], self.p["atmosphere"]
        photon = not self.uncooled
        # (1) QE convention and pixel area - fill factor must not be counted twice
        if photon:
            ff = self.fill_factor
            if self.qe_basis == "unspecified" and ff < 0.98:
                msg = ("QE basis not stated: the TRM convention (QE per active area, fill factor %.2f applied to the "
                       "signal) is used. If the QE is a total / EMVA 1288 QE referred to the full pixel area (incl. "
                       "fill factor and microlenses), select 'pixel area' - otherwise the fill factor is counted "
                       "twice." % ff)
                if self.source("detector.qe_preset") in ("manufacturer", "measurement") or \
                        self.source("detector.qe_custom") in ("manufacturer", "measurement", "import"):
                    self.warn(msg)
                else:
                    self.assume(msg)
            elif self.qe_basis == "pixel_area" and ff < 0.999:
                self.assume("QE referred to the full pixel area: the fill factor %.2f is contained in the QE and is "
                            "not applied to the signal again; the active size is used for the detector MTF only." % ff)
        # (2) saturation capacity used for the well fill must be valid for the modelled node and gain state
        if photon and (self.cat != "Thermal" or d["noise_mode"] != "measured"):
            if not self.cap_verified:
                msg = ("Well fill uses the %s %.3g e- (not a verified input-referred camera saturation capacity); "
                       "the ROIC, analog chain or ADC may clip earlier." % (self.cap_limit, self.n_use))
                if d["tint_mode"] == "wellfill":
                    self.warn(msg + " The integration time is selected from this capacity.")
                else:
                    self.assume(msg)
            if not self.op_mode:
                self.assume("Detector operating mode (gain / conversion gain / readout / temperature) not stated: "
                            "capacity, read noise and dark current are assumed to belong to the same mode.")
        if self.uncooled:
            self.assume("Microbolometer (thermal detector): no photoelectron full-well / well-fill model is applied; "
                        "the thermal time constant %.3g ms is a response time, not an exposure time (it sets the "
                        "motion low-pass)." % (float(d["t_th_ms"])))
        if self.nbin["h"] * self.nbin["v"] > 1:
            self.assume("%s binning %dx%d: read noise %s." % (
                "Digital" if self.bin_kind == "digital" else "Charge (hardware)", self.nbin["h"], self.nbin["v"],
                "added for each of the %d summed read-outs" % self.n_reads if self.bin_kind == "digital" else
                "counted once per binned pixel"))
        # (3) noise measurement port
        cam_netd = self.cat == "Thermal" and (d["noise_mode"] == "measured" and not self.uncooled or
                                              self.uncooled and d["noise_mode"] == "device")
        if cam_netd and d.get("noise_port", "raw") == "processed":
            self.warn("Camera NETD was measured at the processed video output (after denoising / temporal filtering): "
                      "TRM adds its own frame integration and filters - the noise reduction may be counted twice. "
                      "Use a RAW or post-NUC NETD.")
        # (4) imported MTF: content, units and conditions documented (spec wording Sec. 7.4)
        if self.mtf_mode != "A":
            missing = [lab for key, lab in (("mtf_band", "wavelength band"), ("mtf_focus", "focus"),
                                            ("mtf_temp", "temperature"), ("mtf_uncert", "uncertainty"))
                       if not str(o.get(key, "") or "").strip()]
            self.mtf_doc = "complete" if not missing else "partial (missing: %s)" % ", ".join(missing)
            if missing:
                self.assume("Imported MTF metadata incomplete (missing: %s)." % ", ".join(missing))
        else:
            self.mtf_doc = "computed (TRM optics model)"
        # (5) spectral atmosphere / path radiance: versioned RT data (spec wording Sec. 7.6)
        if not self.lab and (am["mode"] == "spectral" or self.cat != "Thermal" and am.get("path_mode") == "import"):
            meta = am.get("meta") or {}
            missing = [lab for key, lab in (("database", "spectroscopy database edition"),
                                            ("rt_code", "RT code / version"), ("profile", "atmospheric profile"),
                                            ("aerosol", "aerosol model"), ("resolution", "spectral resolution"))
                       if not str(meta.get(key, "") or "").strip()]
            if missing:
                self.assume("Imported atmospheric data not fully versioned (missing: %s)." % ", ".join(missing))
        # (6) preset lifecycle records
        recs = []
        if self.qe_label in P.DETECTOR_QE:
            recs.append(P.preset_record("qe", self.qe_label))
        tg = self.p["target"]
        for m in ("t_refl", "b_refl", "t_emis", "b_emis"):
            if (self.cat == "Visible" and "refl" in m or self.cat == "General" and "emis" in m) and \
                    tg["%s_mode" % m] == "spectral":
                recs.append(P.preset_record("material", tg["%s_preset" % m]))
        irr = self.p["irradiance"]
        if self.cat != "Thermal" and irr["mode"] == "single" and irr["type"] == "broadband" and \
                irr["spectrum"] == "preset":
            recs.append(P.preset_record("source", irr["preset"]))
        tb = self.p["turbulence"]
        if self.turbulence_active() and tb.get("cn2_preset", "custom") != "custom":
            recs.append(P.preset_record("cn2", tb["cn2_preset"]))
        if not self.lab and am["mode"] != "spectral" and am.get("preset", "custom") != "custom":
            recs.append(P.preset_record("atmosphere", am["preset"]))
        seen, self.preset_records = set(), []
        for r in recs:
            if (r["kind"], r["name"]) not in seen:
                seen.add((r["kind"], r["name"]))
                self.preset_records.append(r)
        # (7) paraxial focal-plane irradiance
        ri = float(o.get("rel_illum", 1.0) or 1.0)
        if not 0 < ri <= 1:
            raise ModelError("Relative illumination at the field edge must be in (0, 1]")
        self.rel_illum = ri
        if self.F_eff < 1.0:
            self.assume("Fast optics (F/%.2f): the paraxial irradiance factor pi/(4F^2) is an approximation - use the "
                        "measured throughput / etendue." % self.F_eff)
        # (8) generic defaults that act on the ranges but sit in hidden (advanced) input groups
        if photon and (self.cat != "Thermal" or d["noise_mode"] != "measured"):
            gen = P.DEFAULT_PROJECT["detector"]
            for key, what, unit in (("noise_floor_e", "Read noise", "e- rms"), ("lsb_e", "ADC step (LSB)", "e-")):
                if key == "lsb_e" and d["adc_mode"] != "carriers":
                    continue
                v = float(d[key])
                if v == float(gen[key]) and self.source("detector." + key) not in ("manufacturer", "measurement",
                                                                                   "import"):
                    extra = " (quantization noise %.3g e- rms)" % (v / math.sqrt(12)) if key == "lsb_e" else ""
                    self.assume("%s %.4g %s%s is the generic default, not a value of this detector - it acts on "
                                "the ranges; enter the datasheet value." % (what, v, unit, extra))

    def _bright_flux(self, R_km, atm):
        """Carrier flux density of the brightest credible scene pixel [carriers/(s m^2)] (research review Sec. 3.7).

        Candidates: a hot blackbody (T_bg + bright dT, emissive categories) and a highly reflective Lambertian
        surface under the best-lit irradiance factor (reflective categories); the larger one is returned.
        """
        d = self.p["detector"]
        fl = self.flux(R_km, atm)
        tau_l = 1.0 if atm is None else atm.tau_lam(R_km)
        F_T, F_B = self.irr_factors(self.los_angle(R_km))
        F2 = self.F_eff ** 2
        k = self.pp * self.eta * self.tau_o
        rb = min(max(float(d.get("bright_refl", 0.9)), 0.0), 1.0)
        cands = [fl["jB_scene"], fl["jT_scene"]]
        if self.cat != "Visible":
            L_hot = ph.planck(self.lam, self.T_B + max(float(d.get("bright_dT_K", 30.0)), 0.0))
            cands.append(float(ph.trapz(k * math.pi / (4 * F2) * L_hot * tau_l, self.lam)))
        if self.cat != "Thermal":
            L_refl = self.I * max(F_T, F_B) * rb / (4 * F2)
            if self.cat == "General":
                L_refl = L_refl + math.pi / (4 * F2) * (1 - rb) * self.L_B
            cands.append(float(ph.trapz(k * L_refl * tau_l, self.lam)))
        return max(cands) + fl["j_path"] + self.j_internal

    def _exposure_budget(self):
        """Joint exposure constraints (research review Sec. 4.3 / spec wording Sec. 7.3):

        t_int <= min[t_sat,max, t_timing,max, t_motion,max, t_hardware,max] and SNR(t_int) >= SNR_required,
        t_sat,max = fill x C_usable / (Phi_bright + Phi_dark),  t_motion,max = smear_allow x IFOV / |omega|.
        Reported for photon-integrating detectors; infeasible combinations are flagged, the selected
        integration time is not changed.
        """
        if self.uncooled:
            return None
        d, st = self.p["detector"], self.p["stab"]
        g = float(d["electron_gain"])
        fill = min(max(float(d.get("fill_limit_pct", 70.0)), 0.0), 100.0)
        atm0 = None if (self.lab or not self.atms or self.R_ref <= 0) else self.atms[0]
        jb = self._bright_flux(0.0, None)
        if atm0 is not None:
            jb = max(jb, self._bright_flux(self.R_ref, atm0))
        rate_b = (jb + self.j_dark) * self.A_det * g                       # e-/s, brightest pixel
        t_sel = self.ref_state["t_int"]
        lim = [("saturation of the brightest pixel at %.0f %% fill" % fill,
                fill / 100.0 * self.n_use / rate_b if self.n_use > 0 and rate_b > 0 else float("inf")),
               ("frame timing", self.t_timing), ("hardware maximum exposure", self.t_hw_max)]
        smear = {}
        if self.motion_active() == "model" and st["lin_on"]:
            allow = max(float(st.get("smear_allow_px", 0.5)), 0.0)
            t_m = float("inf")
            for z, key in (("h", "lin_h"), ("v", "lin_v")):
                w = abs(float(st[key]))                                      # mrad/s
                ifov = self.pitch_eff[z] / self.f[z]                         # pixel angular pitch [mrad]
                smear[z] = w * t_sel / ifov
                if w > 0:
                    t_m = min(t_m, allow * ifov / w)
            lim.append(("image motion (%.2g px allowed)" % allow, t_m))
        t_rec, limiter = min(((t, n) for n, t in lim), key=lambda x: x[0])
        out = {"t_sel": t_sel, "limits": lim, "t_rec": t_rec, "limiter": limiter, "fill_pct": fill,
               "rate_bright": rate_b, "smear_px": smear, "t_hw_min": self.t_hw_min,
               "wellfill_bright": 100.0 * t_sel * rate_b / self.n_use if self.n_use > 0 else float("nan"),
               "capacity": self.n_use, "capacity_limit": self.cap_limit, "violations": []}
        # SNR requirement (task-specific pixel SNR)
        snr_req = float(d.get("snr_req", 0.0) or 0.0)

        def snr_at(t):
            if self.cat == "Thermal":
                if d["noise_mode"] == "measured":
                    return None
                return abs(float(self.p["target"]["dT_K"])) * self.dN_dT(t) / \
                    self.noise(self.lab_flux["jB"], self.lab_flux["jB"], t)
            s = self.signal_state(self.R_ref if atm0 else 0.0, atm0, t=t)
            n = math.hypot(s["nes"], s["ies"])
            return s["eds"] / n if n > 0 else float("inf")
        if snr_req > 0 and np.isfinite(t_rec):
            out["snr_req"], out["snr_sel"], out["snr_rec"] = snr_req, snr_at(t_sel), snr_at(t_rec)
        v = out["violations"]
        if out["wellfill_bright"] > 100:
            v.append("brightest pixel saturates (%.0f %% of the %s)" % (out["wellfill_bright"], self.cap_limit))
        # (t_sel > t_max itself is already reported by the integration-time checks)
        if t_sel > self.t_timing * 1.0001 and self.t_timing < self.t_max * 0.9999:
            v.append("integration time %.4g ms exceeds the sensor timing limit %.4g ms" % (t_sel * 1e3,
                                                                                          self.t_timing * 1e3))
        if t_sel > self.t_hw_max * 1.0001:
            v.append("integration time exceeds the hardware maximum %.4g ms" % (self.t_hw_max * 1e3))
        if t_sel < self.t_hw_min * 0.9999:
            v.append("integration time is below the hardware minimum %.4g ms" % (self.t_hw_min * 1e3))
        allow = float(st.get("smear_allow_px", 0.5))
        for z, px in smear.items():
            if px > allow:
                v.append("%s image smear %.2f px > %.2g px allowed" % (z, px, allow))
        infeasible = []
        if t_rec < self.t_hw_min:
            infeasible.append("the shortest constraint (%s, %.4g ms) is below the hardware minimum exposure" %
                              (limiter, t_rec * 1e3))
        if out.get("snr_rec") is not None and out["snr_rec"] < snr_req:
            infeasible.append("SNR %.3g at the longest admissible exposure %.4g ms is below the required %.3g" %
                              (out["snr_rec"], t_rec * 1e3, snr_req))
        out["feasible"] = not infeasible
        for x in v:
            self.warn("Exposure budget: %s." % x)
        if infeasible:
            self.warn("Exposure budget infeasible: %s - saturation, motion, timing and SNR constraints cannot be met "
                      "together." % "; ".join(infeasible))
        return out

    def _coverage(self):
        """Resolve which data source contributes each chain component (field map Sec. 15.4) and check overlaps."""
        o, st, am = self.p["optics"], self.p["stab"], self.p["atmosphere"]
        src = []

        def add(source, comps, fobj=None):
            src.append({"source": source, "file": (fobj or {}).get("name", ""), "components": set(comps)})
        if self.mtf_mode == "A":
            add("Theoretical optics model (diffraction + aberration)", ("optics", "diffraction"))
        else:
            kind = "Imported device prefilter MTF (end-to-end camera)" if self.mtf_mode == "C" else \
                ("Measured lens MTF" if o.get("mtf_source") == "measured" else "Zemax / design lens MTF")
            add(kind, self.mtf_cov, o.get("zemax_mtf"))
            if "diffraction" not in self.mtf_cov:
                add("Diffraction MTF (computed, not in the imported data)", ("diffraction",))
        if "detector_aperture" not in self.mtf_cov:
            add("Detector aperture model (pixel footprint, crosstalk, CTE)", ("detector_aperture",))
        add(self.noise_source, ("electronics",))
        dsp = self.p["dsp"]
        if dsp["filter_on"] or self.zoom > 1 or self.lrep > 1 or self.crep > 1 or self.n_frames > 1 or self.iir > 0:
            add("Digital processing model (FIR filter / zoom / frame integration)", ("processing",))
        mode = self.motion_active()
        if mode:
            fobj = st.get("jitter_file") if mode == "measured" else (st.get("psd_file") if mode == "psd" else None)
            add({"model": "Vibration models (RMS / linear / sinusoidal)", "measured": "Measured jitter time series",
                 "psd": "Measured angular PSD"}[mode], ("motion",), fobj)
        elif "motion" in self.mtf_cov and not st["neglect"] and (
                st.get("jitter_mode") in ("measured", "psd") or
                st.get("jitter_mode", "model") == "model" and (st["random_on"] or st["lin_on"] or st["sin_on"])):
            self.warn("Image motion is contained in the imported MTF - the motion inputs on the Stabilization page are "
                      "not applied (no double counting).")
        if self.turbulence_active():
            add("Turbulence MTF (%s)" % ("r0" if self.p["turbulence"]["cn2_mode"] == "r0" else "Cn2"), ("turbulence",))
        if not self.lab:
            if am["mode"] == "spectral":
                add("Spectral atmospheric transmission", ("atmosphere_radiometry",), am.get("spec_file"))
            else:
                add("Atmosphere fast mode (Beer-Lambert)", ("atmosphere_radiometry",))
            if any(a.path is not None for a in self.atms):
                add("Imported path radiance", ("path_radiance",), am.get("path_file"))
            else:
                add("Modelled path radiance", ("path_radiance",))
        check_coverage(src)
        return src

    def _nps_check(self):
        """Measured noise power spectrum: whiteness check of the TRM4 noise assumption (QA only)."""
        d = self.p["detector"]
        fobj = d.get("nps_file") or {}
        if not fobj.get("text"):
            return None
        try:
            c = IM.parse_curve_hv(fobj["text"], "NPS")
        except ValueError as e:
            raise ModelError("NPS file %s: %s" % (fobj.get("name", ""), e))
        stage = d.get("nps_stage", "raw")
        self._record_import("Measured NPS (%s)" % stage, fobj, "; ".join(c["notes"]))
        out = {"stage": stage, "name": fobj.get("name", ""), "ratio": {}}
        for z in "hv":
            r = IM.to_cycles_per_mrad(c["f"], d.get("nps_unit", "mrad"), self.f[z], self.alpha_s[z])
            try:
                q = IM.nps_whiteness(r, c[z], self.r_N[z])
            except ValueError as e:
                self.warn("Measured NPS (%s): %s" % (z, e))
                continue
            out["ratio"][z] = q
            if q < 0.5:
                self.warn("Measured NPS (%s, %s) falls to %.2f of its low-frequency level at Nyquist: the noise is "
                          "spatially correlated (low-pass) - the white-noise assumption may overestimate the perceived "
                          "noise." % (z, stage, q))
            elif q > 2.0:
                self.warn("Measured NPS (%s, %s) rises to %.2f x its low-frequency level at Nyquist (boosted, e.g. "
                          "sharpening) - the white-noise assumption underestimates the perceived noise unless the "
                          "filter is modelled." % (z, stage, q))
        return out

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
                                     "abs_points": True, "mtf50_measured": self._mtf50(r, meas),
                                     "mtf50_predicted": self._mtf50(r, pr)})
                if float(np.max(meas)) > 1.02:
                    self.assume("Measured SFR (%s) exceeds 1 (max %.2f): sharpening overshoot - SFR > 1 is not new "
                                "target information (ISO 12233)." % (z, float(np.max(meas))))
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
                               "config_id", "firmware", "op_mode", "frame_rate", "roi", "exposure", "f_number",
                               "raw_files", "calib_id") if not str(meta.get(k, "")).strip()]
        out["meta"] = meta
        out["missing_meta"] = missing
        if missing:
            self.assume("Calibration metadata incomplete (missing: %s)." % ", ".join(missing))
        cfg_meas = str(meta.get("config_id", "")).strip()
        cfg_now = str((self.p.get("profile") or {}).get("config", "")).strip()
        if cfg_meas and cfg_now and cfg_meas != cfg_now:
            self.warn("Measured data belong to configuration '%s' but the project uses '%s' - calibration data are not "
                      "transferred between zoom / focus / gain states." % (cfg_meas, cfg_now))
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

    @staticmethod
    def aliasing_level(mtf_nyq, spurious):
        """Indicative aliasing risk from the presampled MTF (design heuristic, field map Sec. 5.4 / 15.2.5)."""
        if mtf_nyq >= 0.3 or spurious >= 0.4:
            return "high"
        if mtf_nyq >= 0.1 or spurious >= 0.15:
            return "moderate"
        return "low"

    @staticmethod
    def fld_regime(q):
        """Design regime from F lambda / d (Holst, Opt. Eng. 46(10) 103204, 2007; Driggers et al., Opt. Eng. 51(6)
        063202, 2012): which hardware change can lengthen the range."""
        if q < 1.0:
            return {"regime": "detector-limited (undersampled)",
                    "lever": "longer focal length or smaller pixels at the same F-number; a larger aperture alone "
                             "gains little"}
        if q < 2.0:
            return {"regime": "balanced (detector / optics)",
                    "lever": "focal length and aperture diameter together"}
        return {"regime": "optics-limited (diffraction)",
                "lever": "larger aperture diameter; smaller pixels gain nothing"}

    def _cnr_at(self, R_km, atm):
        """Contrast-to-noise ratio of the target at range R (difference signal / total noise per pixel)."""
        if self.cat == "Thermal":
            n = math.hypot(self.netd, self.ietd)
            return abs(float(self.p["target"]["dT_K"])) * atm.tau(R_km) / n if n > 0 else float("inf")
        s = self.signal_state(R_km, atm)
        n = math.hypot(s["nes"], s["ies"])
        return s["eds"] / n if n > 0 else float("inf")

    def _dashboard(self, res):
        """Compact always-visible figures (roadmap Section 09, field map Sec. 12.7 / 15.3)."""
        d = {"mtf": {}, "tasks": []}
        for z in "hv":
            r = res["mtf"]["r"][z]
            m = res["mtf"]["curves"][z]["System prefilter"]
            rN, rs = self.r_N[z], self.r_s[z]
            x = np.linspace(0.0, rN, 200)
            base = ph.trapz(np.interp(x, r, m), x)
            spur = ph.trapz(np.interp(rs - x, r, m), x) / base if base > 0 else 0.0   # in-band, presampled
            mn = float(np.interp(rN, r, m))
            d["mtf"][z] = {"mtf50": self._mtf50(r, m), "mtf_nyq": mn, "r_N": rN, "spurious": float(spur),
                           "aliasing": self.aliasing_level(mn, spur)}
        worst = max((d["mtf"][z]["aliasing"] for z in "hv"), key=["low", "moderate", "high"].index)
        d["aliasing"] = worst
        # F lambda / d with the signal-weighted mean wavelength of the band (not the QE peak) and the effective pitch
        lam_w = float(ph.trapz(self.lam * self.w, self.lam))
        pitch = math.sqrt(self.pitch_eff["h"] * self.pitch_eff["v"])
        q = self.F_eff * lam_w / pitch
        d["fld"] = dict(value=q, lambda_um=lam_w, pitch_um=pitch, F=self.F_eff, **self.fld_regime(q))
        st = self.ref_state
        if self.cat == "Thermal":
            n = math.hypot(st["nes"], st["ies"])
            d["cnr"] = abs(float(self.p["target"]["dT_K"])) / n if n > 0 else float("inf")
            d["cnr_label"] = "dT / sqrt(NETD^2 + IETD^2) at zero range"
        else:
            n = math.hypot(st["nes"], st["ies"])
            d["cnr"] = abs(st["ds"]) / n if n > 0 else float("inf")
            d["cnr_label"] = "difference signal / total noise at %.3g km" % self.R_ref
        # signal level and radiometry at the reference range (field map Sec. 15.2.11)
        sig = {"radiance": st["flux"]["radiance"]}
        if self.cat != "Thermal":
            sig.update(N_T=st["N_T"], N_B=st["N_B"])
            dt = self.p["detector"]
            if dt["adc_mode"] == "carriers" and float(dt["lsb_e"]) > 0:
                sig.update(DN_T=st["N_T"] / float(dt["lsb_e"]), DN_B=st["N_B"] / float(dt["lsb_e"]))
        elif not self.uncooled:
            sig["N_B"] = self.lab_flux["jB"] * self.A_det * self.t_ref
        d["signal"] = sig
        d["noise_source"], d["noise_quality"] = self.noise_source, self.noise_quality
        if getattr(self, "nps", None):
            d["nps"] = self.nps
        rg = res.get("range")
        if rg and rg["atm"]:
            a0 = rg["atm"][0]
            atm0 = self.atms[0]
            sysm = {z: (res["mtf"]["r"][z], res["mtf"]["curves"][z]["System prefilter"]) for z in "hv"}
            for t in a0["tasks"]:
                R0 = t["R0"]
                row = {"name": t["name"], "lp": t["lp"], "R0": R0}
                if R0 is not None and np.isfinite(R0) and R0 > 0:
                    ah, av, _ = self.target_dims(self.los_angle(R0))
                    ph_, pv_ = ah / (R0 * self.alpha_s["h"]), av / (R0 * self.alpha_s["v"])
                    row.update(pix_h=ph_, pix_v=pv_, cyc_nyq=0.5 * math.sqrt(ph_ * pv_))
                    row["sampling_limited"] = t["lp"] >= 0.9 * row["cyc_nyq"]
                    # task frequency: lp across the critical dimension sqrt(a_h a_v) [m] at R0 [km] -> cycles/mrad
                    crit = math.sqrt(ah * av)
                    row["crit_m"] = crit
                    f_task = t["lp"] * R0 / crit if crit > 0 else float("inf")
                    row["f_task"] = f_task
                    row["mtf_task"] = math.sqrt(max(float(np.interp(f_task, *sysm["h"], right=0.0)), 0.0) *
                                                max(float(np.interp(f_task, *sysm["v"], right=0.0)), 0.0))
                    row["cnr_task"] = self._cnr_at(R0, atm0)
                    # target occupancy (research review Sec. 3.9): angular target size vs the larger of the pixel
                    # angular pitch and the diffraction blur (Airy FWHM ~ 1.03 lambda / D) at the peak wavelength
                    blur = max(max(self.pitch_eff[z] / self.f[z] for z in "hv"), 1.03 * self.lam_peak / self.D_eff)
                    row["occupancy"] = min(ah, av) / R0 / blur
                    if row["occupancy"] < 1.0:
                        self.warn("%s range %.3g km: the target (%.3g mrad) is smaller than one pixel / blur spot "
                                  "(%.3g mrad) - the extended-source radiometry over-estimates its signal (sub-pixel "
                                  "target, ensquared energy not modelled)." % (t["name"], R0, min(ah, av) / R0, blur))
                    if t["lp"] > row["cyc_nyq"]:
                        row["limiter"] = "sampling (beyond Nyquist)"
                    elif row["sampling_limited"]:
                        row["limiter"] = "sampling (near Nyquist)"
                    elif row["mtf_task"] < 0.1:
                        row["limiter"] = "resolution (MTF)"
                    else:
                        row["limiter"] = "contrast / noise"
                    if "pot" in t:
                        row["limiter"] = "%s (algorithm criterion)" % t["limit"]
                for key in ("pot", "levels", "lp_input", "clutter", "ttp", "geo"):
                    if key in t:
                        row[key] = t[key]
                d["tasks"].append(row)
        d["nominal"] = True
        d["model"] = "TRM4 line-pair criterion (Johnson-type legacy), preset '%s'" % P.TASK_PRESETS.get(
            self.p["target"].get("task_preset", "legacy"), ("custom",))[0]
        if self.pot_mode:
            d["model"] = "Algorithm criterion: pixels on target and pixel CNR >= %g (%s)" % (self.algo_cnr, X.EXTENSION)
        d["extensions"] = self.extensions()
        fm = res.get("fom_measured")
        if self.algo:
            d["calibration"] = "Uncalibrated estimate - algorithm observer%s" % (
                " (calibration set '%s' recorded, not applied by TRM4)" % self.p["display"]["algo_calib"]
                if str(self.p["display"].get("algo_calib", "")).strip() else "")
        elif fm and fm["use"] == "replace":
            d["calibration"] = "Sensor figure of merit measured (%s); task criteria not calibrated" % fm["kind"]
        else:
            d["calibration"] = "Uncalibrated engineering estimate (not a validated detection probability)"
        d["exposure"] = self.exposure
        d["context"] = self._dri_context(res)
        return d

    def extensions(self):
        """Active TRM_HADMAA extensions (each labelled where its result is shown; empty = TRM4 model only)."""
        out = []
        if self.prob_levels and not self.lab:
            out.append("P80 / P90 ranges (Johnson TTPF; the TRM4 range is P50)")
        if self.clutter_mult != 1.0:
            out.append("clutter '%s': Detection criterion x%.3g (ACQUIRE-LC)" % (self.p["target"]["clutter"],
                                                                                self.clutter_mult))
        if getattr(self, "weather", None):
            out.append("extinction from visual range / humidity (Kruse-Kim + water-vapour continuum)")
        if self.cat == "Thermal" and self.turbulence_active():
            out.append("turbulence in the Thermal category")
        if self.turbulence_active() and self.mitigation_gain() > 1.0:
            out.append("turbulence mitigation: effective r0 x%.3g" % self.mitigation_gain())
        if self.compression_blur_px() > 0:
            out.append("lossy compression as %.3g px Gaussian blur" % self.compression_blur_px())
        if self.pot_mode:
            out.append("algorithm observer: pixels-on-target criterion")
        if self.ttp_on:
            out.append("TTP / V50 ranges (Vollmerhausen 2004, V50 to be calibrated)")
        if self.geo_on:
            out.append("geometric reference range (Nyquist / diffraction, no noise / contrast / atmosphere)")
        return out

    def _dri_context(self, res):
        """Context every DRI range is reported with (research review Sec. 3.22 / spec wording Sec. 7.7)."""
        p, tg, d = self.p, self.p["target"], self.p["detector"]
        tasks = [t for t in tg["tasks"] if t.get("on")]
        if self.uncooled:
            op = "F/%.2f, microbolometer, NETD %.3g mK, time constant %.3g ms" % (
                self.F_eff, self.netd * 1e3, float(d["t_th_ms"]))
        else:
            op = "F/%.2f, integration %.4g ms, gain %g, mode '%s', capacity %.3g e- (%s%s), QE basis %s" % (
                self.F_eff, self.ref_state["t_int"] * 1e3, float(d["electron_gain"]), self.op_mode or "not stated",
                self.n_use, self.cap_limit, "" if self.cap_verified else ", not verified",
                {"unspecified": "not stated (active area assumed)", "active_area": "active area",
                 "pixel_area": "full pixel area"}[self.qe_basis])
        if self.cat == "Thermal":
            scene = "thermal contrast dT %g K at %g K" % (float(tg["dT_K"]), self.T_B)
        else:
            irr = p["irradiance"]
            scene = "illumination: %s" % ("none" if irr["mode"] == "none" else irr.get("preset") if
                                          irr["spectrum"] == "preset" else irr["type"])
        rg = res.get("range")
        atm = rg["atm"][0]["label"] if rg and rg["atm"] else ("laboratory" if self.lab else "-")
        return {
            "task": "; ".join("%s %g lp" % (t["name"], float(t["lp"])) for t in tasks) +
                    " (preset '%s')" % tg.get("task_preset", "legacy"),
            "target": "%g x %g x %g m (W x H x D), %s aspect" % (float(tg["W_m"]), float(tg["H_m"]), float(tg["D_m"]),
                                                               tg["aspect"]),
            "operating_point": op,
            "scene": "%s; atmosphere %s" % (scene, atm),
            "mtf_source": "mode %s - %s" % (self.mtf_mode, getattr(self, "mtf_doc", "")),
            "observer": self.observer + (" (algorithm '%s')" % p["display"].get("algo_id", "") if self.algo else ""),
            "extensions": "; ".join(self.extensions()) or "none (TRM4 model only)",
            "uncertainty": "nominal prediction - no uncertainty statement unless the Sensitivity analysis is run",
            "validation": "not validated (no measured data)",
            "statement": "A nominal range is not, by itself, an assured operational outcome."}

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
        cov = [{"source": s["source"], "file": s["file"], "components": [c for c in COMPONENTS if c in s["components"]]}
               for s in getattr(self, "coverage", [])]
        return {"model_version": MODEL_VERSION, "model_reference": MODEL_REFERENCE,
                "validation_version": VALIDATION_VERSION, "run_id": run_id(p),
                "time": datetime.datetime.now().isoformat(timespec="seconds"),
                "profile": dict(p.get("profile") or {}), "imports": list(self.imports), "key_inputs": rows,
                "source_counts": counts, "category": self.cat, "imager_type": p["imager_type"],
                "environment": "laboratory" if self.lab else "field", "stream": "still" if self.still else "video",
                "coverage": cov, "task_preset": tg.get("task_preset", "legacy"), "observer": self.observer,
                "noise_source": self.noise_source,
                # operating-point semantics reported with every calculation (research review Sec. 6, P0)
                "op_mode": self.op_mode, "qe_basis": self.qe_basis, "capacity_limit": self.cap_limit,
                "capacity_verified": self.cap_verified, "mtf_doc": getattr(self, "mtf_doc", ""),
                "presets": list(getattr(self, "preset_records", []))}

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
        """First range at which the necessary signal exceeds the available one.

        None if it never does (caller decides), "below" if the task fails already at the first range - reported as
        None like in the Thermal category ("< first range")."""
        diff = np.log(np.maximum(need, 1e-300)) - np.log(np.maximum(have, 1e-300))
        idx = np.nonzero(diff >= 0)[0]
        if idx.size == 0:
            return None
        i = idx[0]
        if i == 0:
            return "below"
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
        if self.prob_levels:
            out["prob_levels"] = list(X.PROB_LEVELS)
        if self.geo_on:
            geo = {}
            for a in out["atm"]:
                for t in a["tasks"]:
                    if t["lp"] not in geo:
                        geo[t["lp"]] = self._geo_range(t["lp"])
                    t["geo"] = {"R0": geo[t["lp"]][0], "limit": geo[t["lp"]][1]}
        return out

    # --- task criteria (TRM4 line pairs; clutter, probability and pixels-on-target are extensions) -------------
    def _setup_criteria(self):
        tg, disp = self.p["target"], self.p["display"]
        self.clutter_mult = 1.0
        if tg.get("clutter_model") and tg.get("clutter") in X.CLUTTER_C:
            dT = abs(float(tg["dT_K"])) if self.cat == "Thermal" else None
            self.clutter_mult = X.clutter_factor(tg["clutter"], dT)
            self.assume("Background clutter '%s' (%s): the Detection criterion (first task) is multiplied by %.3g - "
                        "ACQUIRE-LC N50 = 0.75 C [(C / dT)^2 + 1], C = %g, relative to low clutter%s; the entered "
                        "criterion is taken as the low-clutter value." % (
                            tg["clutter"], X.EXTENSION, self.clutter_mult, X.CLUTTER_C[tg["clutter"]],
                            " at dT = %.3g K (dT_RSS approximated by the entered dT)" % dT if dT else
                            " in the high-contrast limit (factor C)"))
        self.pot_mode = self.algo and disp.get("algo_criterion", "lp") == "pot"
        self.algo_cnr = float(disp.get("algo_cnr_min", X.ALGO_CNR_DEFAULT))
        if self.pot_mode:
            if not self.algo_cnr > 0:
                raise ModelError("Minimum pixel CNR of the algorithm observer must be > 0")
            for i, t in enumerate(self._tasks()):
                if not float(t.get("pot", 1.0)) > 0:
                    raise ModelError("Pixels on target of task '%s' must be > 0" % t["name"])
            self.assume("Algorithm observer criterion (%s): pixels on the projected target area (Holst & Mahalanobis "
                        "2023: 50-70 detection, 150 classification, 250 recognition, 350 identification) and a pixel "
                        "CNR >= %.3g (difference signal / noise of the processed frame); the range is the shorter of "
                        "the two. Thresholds are generic until calibrated for the algorithm." % (X.EXTENSION,
                                                                                                  self.algo_cnr))
        # probability levels: Johnson / Lawson TTPF on the (N50) criterion; not for pixels-on-target criteria
        self.prob_levels = bool(tg.get("prob_levels", True)) and not self.pot_mode and not self.wi.get("no_prob")
        extra = not self.lab and not self.wi.get("no_extra")
        self.ttp_on = bool(tg.get("ttp", False)) and not self.pot_mode and extra
        self.geo_on = bool(tg.get("geo_limit", True)) and extra
        if self.ttp_on:
            for i, t in enumerate(self._tasks()):
                if not float(t.get("v50", X.v50_default(i))) > 0:
                    raise ModelError("V50 of task '%s' must be > 0" % t["name"])
            self.assume("TTP / V50 ranges (%s): targeting task performance TTP = integral of sqrt(signal / threshold) "
                        "over the bar frequencies the TRM4 threshold (MTDP / MDSP) resolves, cycles on target V = "
                        "TTP sqrt(a_h a_v) / R; the range is where V = V50 (P50), with P = x^E / (1 + x^E), E = 1.51 + "
                        "0.24 x, x = V / V50 (Vollmerhausen, Jacobs & Driggers 2004). The TRM4 threshold replaces "
                        "CTF_sys / C_target, so the V50 values are not interchangeable with NV-IPM values and have to "
                        "be calibrated." % X.EXTENSION)
        if self.prob_levels and not self.lab:
            self.assume("P80 / P90 ranges (%s): the task criterion is the 50 %% value N50; the criterion for "
                        "probability P is N50 x %.3g (P80) and x %.3g (P90) from the Johnson / Lawson TTPF "
                        "P = x^E / (1 + x^E), E = 2.7 + 0.7 x (SAND2015-6368)." % (
                            X.EXTENSION, X.ttpf_ratio(0.8), X.ttpf_ratio(0.9)))

    def _criterion(self, t):
        """Criterion entry of a task: line pairs actually used (entered x clutter factor), entered value, factor.

        The clutter factor acts on the Detection task (first task of the project); in heavy clutter the target is
        found only by recognising it, so the factor is capped at the Recognition criterion."""
        all_t = self.p["target"]["tasks"]
        i = next(k for k, x in enumerate(all_t) if x is t)
        n = float(t["lp"])
        c = {"lp": n, "lp_input": n, "clutter": 1.0}
        if i == 0 and self.clutter_mult != 1.0:
            n_c = n * self.clutter_mult
            if len(all_t) > 1 and all_t[1].get("on") and n_c > float(all_t[1]["lp"]) >= n:
                n_c = float(all_t[1]["lp"])
                self.warn("Clutter '%s' would raise the Detection criterion above the Recognition criterion (%g lp); "
                          "it is capped there - in this clutter the target is found only by recognising it." % (
                              self.p["target"]["clutter"], n_c))
            c.update(lp=n_c, clutter=n_c / n)
        if self.pot_mode:
            c["pot"] = float(t.get("pot", X.pot_default(i)))
        if self.ttp_on:
            c["v50"] = float(t.get("v50", X.v50_default(i)))
        return c

    def _ttp_task(self, R, V, v50):
        """TTP / V50 range of one task from the cycles-on-target curve V(R) (P50 and the P80 / P90 levels)."""
        V = np.maximum(V, 1e-300)
        out = {"v50": v50, "R0": X.last_range_at_or_above(R, V, v50)}
        if self.prob_levels:
            out["levels"] = [{"p": pr, "v": v50 * X.ttpf_ttp_ratio(pr),
                              "R0": X.last_range_at_or_above(R, V, v50 * X.ttpf_ttp_ratio(pr))}
                             for pr in X.PROB_LEVELS[1:]]
        return out

    def _ttp_cycles(self, R, ttp):
        """Cycles on target V = sqrt(TTP_h a_h TTP_v a_v) / R [TTP in cycles/mrad, a in m, R in km]."""
        dims = [self.target_dims(self.los_angle(x)) for x in R]
        return np.array([math.sqrt(max(th * dm[0] * tv * dm[1], 0.0)) / x
                         for x, th, tv, dm in zip(R, ttp["h"], ttp["v"], dims)])

    def _geo_range(self, n_lp):
        """Geometric resolution limit of a criterion (extension): (range km or None, limiting element).

        Fixed-point iteration because the projected target size depends on the line-of-sight angle."""
        lam = float(ph.trapz(self.lam * self.w, self.lam))
        ifov = math.sqrt(self.alpha_s["h"] * self.alpha_s["v"])
        R_min = self.min_range() * 1.0001
        R, limit = max(1.0, R_min), ""
        for _ in range(60):
            ah, av, _A = self.target_dims(self.los_angle(R))
            R_new, limit = X.geometric_range(math.sqrt(max(ah * av, 0.0)), n_lp, ifov, lam, self.D_opt)
            if not np.isfinite(R_new):
                return R_new, limit
            R_new = max(R_new, R_min)
            if abs(R_new - R) < 1e-9 * R:
                break
            R = R_new
        if self.min_range() > 0 and R <= R_min * 1.0001:
            return None, limit
        return float(R), limit

    def _pot_range(self, R, dims, cnr, n_pot):
        """Range of a pixels-on-target criterion with the pixel-CNR condition -> (R0, limiting condition)."""
        npot = np.array([dm[2] / (x * x * self.alpha_s["h"] * self.alpha_s["v"]) for x, dm in zip(R, dims)])
        r_geo = X.last_range_at_or_above(R, npot, n_pot)
        r_cnr = X.last_range_at_or_above(R, np.maximum(cnr, 1e-300), self.algo_cnr)
        if r_geo is None or r_cnr is None:
            return None, "pixels on target" if r_geo is None else "pixel CNR"
        return (r_geo, "pixels on target") if r_geo <= r_cnr else (r_cnr, "pixel CNR")

    @staticmethod
    def _nbar_range(R, nbar, n_perc):
        """Range at which the resolved line pairs on target fall below the criterion (Thermal, Eq. 3.212)."""
        below = np.nonzero(nbar < n_perc)[0]
        if below.size and below[0] > 0:
            i = below[0]
            y0, y1 = math.log(nbar[i - 1]), math.log(max(nbar[i], 1e-300))
            tt = (math.log(n_perc) - y0) / (y1 - y0)
            return math.exp(math.log(R[i - 1]) + tt * (math.log(R[i]) - math.log(R[i - 1])))
        if below.size == 0:
            return float("inf")
        return None

    def _thermal_turbulence(self, R):
        """MTDP versus range with the turbulence MTF (extension; TRM4 neglects turbulence in the Thermal category).

        Turbulence only changes the pre-sampling MTF, so MTDP_R(rp) = MTDP_0(rp) AMOP_0(rp) / AMOP_R(rp).  AMOP_R is
        simulated at nine ranges on the AMOP frequency grid and interpolated linearly in log range."""
        fom = self._fom_res
        Rk = np.logspace(math.log10(R[0]), math.log10(R[-1]), 9)
        out = {}
        for z in "hv":
            rt, a0t = self.amop_tab[z]
            ak = []
            for x in Rk:
                vals, zeros = [], 0
                for f in rt:
                    a = 0.0 if zeros >= 3 else self.amop_direct(x, f, z)
                    vals.append(a)
                    zeros = zeros + 1 if a <= 0.001 else 0
                ak.append(np.array(vals))
            ak = np.array(ak)
            rp, val = fom[z]["rp"], fom[z]["val"]
            a0 = np.interp(rp, rt, a0t, right=0.0)
            lr, lk = np.log(R), np.log(Rk)
            rows = []
            for x in lr:
                j = int(np.clip(np.searchsorted(lk, x) - 1, 0, len(Rk) - 2))
                t = (x - lk[j]) / (lk[j + 1] - lk[j])
                aR = np.interp(rp, rt, (1 - t) * ak[j] + t * ak[j + 1], right=0.0)
                with np.errstate(divide="ignore", invalid="ignore"):
                    v = np.where((aR > 0.001) & (a0 > 0.001), val * a0 / np.maximum(aR, 1e-300), np.inf)
                rows.append(v)
            out[z] = np.array(rows)
        self.assume("Turbulence in the Thermal category (%s): the MTDP is degraded by the turbulence MTF along the "
                    "range (MTDP_R = MTDP_0 AMOP_0 / AMOP_R, AMOP simulated at 9 ranges)." % X.EXTENSION)
        return out

    def _ranges_thermal(self, atm, tasks):
        """Range performance for the Thermal category, Section 3.12.3."""
        R = self._range_grid(300)
        dT = abs(float(self.p["target"]["dT_K"]))
        etd = dT * np.array([atm.tau(x) for x in R])                               # Eq. (3.208)
        fom = self._fom_res
        dims = [self.target_dims(self.los_angle(x)) for x in R]
        res = {"label": atm.label, "R": R, "signal": etd, "tasks": []}
        turb = self._thermal_turbulence(R) if self.turbulence_active() else None
        # resolved line pairs vs range, Eqs. (3.210), (3.211)
        nlp = {}
        for z, zi in (("h", 0), ("v", 1)):
            rp = fom[z]["rp"]
            n = []
            for k, (x, e, dm) in enumerate(zip(R, etd, dims)):
                val = fom[z]["val"] if turb is None else turb[z][k]
                finite = np.isfinite(val)
                r_last = rp[finite][-1] if finite.any() else 0.0
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
        st = self.ref_state
        cnr = etd / math.sqrt(st["nes"] ** 2 / self.n_int_frames + st["ies"] ** 2) if self.pot_mode else None
        V = None
        if self.ttp_on:
            ttp = {z: np.array([X.ttp_integral(fom[z]["rp"], fom[z]["val"] if turb is None else turb[z][k], e)
                                for k, e in enumerate(etd)]) for z in "hv"}
            V = self._ttp_cycles(R, ttp)
            res["ttp_R"], res["ttp_cycles"] = R, V
        for t in tasks:
            c = self._criterion(t)
            n_perc = c["lp"]
            if self.pot_mode:
                R0, c["limit"] = self._pot_range(R, dims, cnr, c["pot"])
            else:
                R0 = self._nbar_range(R, nbar, n_perc)
                if self.prob_levels:
                    c["levels"] = [{"p": pr, "lp": n_perc * X.ttpf_ratio(pr),
                                    "R0": self._nbar_range(R, nbar, n_perc * X.ttpf_ratio(pr))} for pr in X.PROB_LEVELS[1:]]
            # MNTD curves, Eq. (3.215) and average (3.216)-(3.218)
            mn = {}
            for z, zi in (("h", 0), ("v", 1)):
                rp = fom[z]["rp"]
                req = np.array([n_perc * x / dm[zi] for x, dm in zip(R, dims)])
                if turb is None:
                    big = np.where(np.isfinite(fom[z]["val"]), fom[z]["val"], 1e30)
                    v = np.interp(req, rp, big, left=big[0], right=1e30)
                else:
                    v = []
                    for q, row in zip(req, turb[z]):
                        big = np.where(np.isfinite(row), row, 1e30)
                        v.append(np.interp(q, rp, big, left=big[0], right=1e30))
                    v = np.array(v)
                mn[z] = np.where(v >= 1e30, np.inf, v)
            Ra, Sa = self._avg_curve(R, mn["h"], mn["v"])
            if V is not None:
                c["ttp"] = self._ttp_task(R, V, c["v50"])
            res["tasks"].append(dict(c, name=t["name"], R0=R0, R_avg=Ra, mn_avg=Sa, mn_h=mn["h"], mn_v=mn["v"]))
        return res

    def _ttp_signal(self, atm, R):
        """Cycles on target of the TTP metric versus range (Visible / General), on 16 ranges of the grid.

        The MDSP is evaluated on every second frequency of the AMOP grid up to the resolution limit.  With turbulence
        the tabulated AMOP (reference range) is scaled by the ratio of the turbulence MTF at the bar frequency,
        MTF_turb(rp, R) / MTF_turb(rp, R_ref) - an approximation used for this metric only (no AMOP simulation per
        range)."""
        Rk = np.logspace(math.log10(R[0]), math.log10(R[-1]), 16)
        rp = {z: self.amop_tab[z][0][::2] for z in "hv"}
        amop = None
        if self.turbulence_active():
            amop = {}
            for z in "hv":
                a0 = np.interp(rp[z], *self.amop_tab[z])
                t0 = np.maximum(self.mtf_turb(rp[z], self.R_ref), 1e-12)
                amop[z] = [a0 * self.mtf_turb(rp[z], x) / t0 for x in Rk]
        ttp = {"h": [], "v": []}
        for k, x in enumerate(Rk):
            s = self.signal_state(x, atm)
            for z in "hv":
                thr = np.full(rp[z].shape, np.inf)
                for j, f in enumerate(rp[z]):
                    thr[j] = self.mdsp(x, f, z, s["nes"], s["ies"], None if amop is None else amop[z][k][j])
                    if not np.isfinite(thr[j]):
                        break
                ttp[z].append(X.ttp_integral(rp[z], thr, s["eds"]))
        return Rk, self._ttp_cycles(Rk, ttp)

    def _ranges_signal(self, atm, tasks):
        """Range performance for the Visible and General categories, Section 3.12.4."""
        R = self._range_grid(56)
        states = [self.signal_state(x, atm) for x in R]
        eds = np.array([s["eds"] for s in states])
        res = {"label": atm.label, "R": R, "signal": eds, "tasks": []}

        def solve(n_perc):
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
                elif R0 == "below":
                    R0 = None
            return R0, Ra, Sa, mn

        if self.pot_mode:
            dims = [self.target_dims(self.los_angle(x)) for x in R]
            cnr = np.array([s["eds"] / math.sqrt(s["nes"] ** 2 / self.n_int_frames + s["ies"] ** 2) for s in states])
        for t in tasks:
            c = self._criterion(t)
            R0, Ra, Sa, mn = solve(c["lp"])
            if self.pot_mode:
                R0, c["limit"] = self._pot_range(R, dims, cnr, c["pot"])
            elif self.prob_levels:
                c["levels"] = [{"p": pr, "lp": c["lp"] * X.ttpf_ratio(pr), "R0": solve(c["lp"] * X.ttpf_ratio(pr))[0]}
                               for pr in X.PROB_LEVELS[1:]]
            res["tasks"].append(dict(c, name=t["name"], R0=R0, R_avg=Ra, mn_avg=Sa, mn_h=mn["h"], mn_v=mn["v"]))
        if self.ttp_on:
            # after the TRM4 ranges, so that the extension cannot change them through the model caches
            Rk, V = self._ttp_signal(atm, R)
            res["ttp_R"], res["ttp_cycles"] = Rk, V
            for c in res["tasks"]:
                c["ttp"] = self._ttp_task(Rk, V, c["v50"])
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
        # NIIRS is evaluated for single images (TRM4 Sec. 2: Still is used with NIIRS); the DRI ranges keep the
        # selected Video/Still option
        video, self.still = self.still, True
        try:
            self._niirs_curves(out, R)
        finally:
            self.still = video
        return out

    def _niirs_curves(self, out, R):
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


    def _turb_info(self, add, s, res):
        """r0, D/r0 and lambda/r0 in IFOV units; without a reference range the turbulence is evaluated at the range of
        the most demanding task."""
        rg = res.get("range") or {}
        R_t, at = self.R_ref, "reference range"
        if R_t <= 0 and rg.get("atm"):
            done = [t for t in rg["atm"][0]["tasks"] if t["R0"] is not None and np.isfinite(t["R0"])]
            if done:
                R_t, at = float(done[-1]["R0"]), "the %s range (%.3g km)" % (done[-1]["name"], done[-1]["R0"])
        if self.turbulence_active() and R_t > 0:
            r0 = self._turb_table(R_t)[2]
            add(s, "Fried parameter r0 at %s" % at, "%.4g" % (r0 * 100), "cm")
            if r0 > 0:
                # D/r0 > 1: the aperture is turbulence-limited; lambda/r0 against the IFOV says whether a longer
                # focal length still resolves more (blur angle >> IFOV: optics gains are eaten by turbulence)
                blur = self.lam_peak * 1e-3 / r0                                  # mrad
                ifov = math.sqrt(self.alpha_s["h"] * self.alpha_s["v"])
                add(s, "Aperture / r0 (D/r0, > 1 = turbulence-limited aperture)", "%.3g" % (self.D_eff / 1000.0 / r0))
                add(s, "Turbulence blur lambda/r0 vs IFOV", "%.4g urad = %.2f IFOV" % (blur * 1e3, blur / ifov))
                if self.mitigation_gain() > 1.0:
                    add(s, "Effective r0 after mitigation processing (extension)", "%.4g" % (
                        r0 * 100 * self.mitigation_gain()), "cm")

    def _extension_info(self, add, res):
        """System-data rows of the TRM_HADMAA extensions (report phase 3)."""
        e = "Extensions (not TRM4)"
        lw = float(ph.trapz(self.lam * self.w, self.lam))
        for wx in getattr(self, "weather", None) or []:
            a = wx["atm"]
            t1 = a.tau(1.0) / a.tau0
            add(e, "Atm %d from the weather: band extinction over 1 km" % (wx["slot"] + 1), "%.4g" % (
                -math.log(max(t1, 1e-300))), "1/km")
            add(e, "Atm %d: aerosol / water-vapour continuum at %.2f um" % (wx["slot"] + 1, lw), "%.4g / %.4g" % (
                float(np.interp(lw, self.lam, wx["aerosol"])), float(np.interp(lw, self.lam, wx["water"]))), "1/km")
            add(e, "Atm %d: absolute humidity" % (wx["slot"] + 1), "%.3g" % wx["rho_w"], "g/m^3")
        if self.clutter_mult != 1.0:
            add(e, "Clutter factor on the Detection criterion (ACQUIRE-LC)", "%.3g" % self.clutter_mult)
        sm = self.scan_smear_px()
        if sm:
            add(e, "Smear of the linear motion per %s h / v" % (
                "thermal time constant" if self.uncooled else "integration time"), "%.3g / %.3g" % (sm["h"], sm["v"]),
                "pixels")
        if self.compression_blur_px() > 0:
            add(e, "Compression equivalent blur", "%.3g" % self.compression_blur_px(), "pixels rms")
        rg = res.get("range")

        def fmt(x):
            return "-" if x is None else ("> grid" if not np.isfinite(x) else "%.3f" % x)
        if rg and rg["atm"]:
            for t in rg["atm"][0]["tasks"]:
                if "ttp" in t:
                    tt = t["ttp"]
                    add(e, "%s TTP range, V50 = %g cycles%s" % (t["name"], tt["v50"], " (P50 / P80 / P90)" if
                                                                tt.get("levels") else ""),
                        " / ".join(fmt(x) for x in [tt["R0"]] + [lv["R0"] for lv in tt.get("levels", [])]), "km")
                if "geo" in t:
                    add(e, "%s geometric reference range (%s)" % (t["name"], t["geo"]["limit"]), fmt(t["geo"]["R0"]),
                        "km")
        self._aerosol_info(add, e, rg)
        if rg and rg["atm"] and self.prob_levels:
            for t in rg["atm"][0]["tasks"]:
                lv = t.get("levels") or []
                add(e, "%s P50 / P80 / P90 (Johnson TTPF)" % t["name"], " / ".join(
                    "-" if x is None else ("> grid" if not np.isfinite(x) else "%.3f" % x)
                    for x in [t["R0"]] + [l["R0"] for l in lv]), "km")

    def _aerosol_info(self, add, e, rg):
        """Aerosol MTF diagnostics (Kopeika) of the weather-derived atmospheres.

        Above the cutoff xi_c = a / lambda the aerosol MTF is flat at the scattering transmission, which the Beer-Lambert
        extinction already applies to the signal; it only adds blur below xi_c.  The rows show where xi_c lies relative
        to the bar frequencies of the tasks; the ranges are not changed."""
        wx_all = getattr(self, "weather", None) or []
        if not wx_all or not (rg and rg["atm"]):
            return
        lw = float(ph.trapz(self.lam * self.w, self.lam))
        xc = {k: X.aerosol_cutoff(lw, a) for k, a in X.AEROSOL_RADIUS_UM.items()}
        add(e, "Aerosol MTF cutoff a / lambda at %.2f um: haze (1 um) / fog (10 um)" % lw,
            "%.3g / %.3g" % (xc["haze"], xc["fog"]), "cycles/mrad")
        f_low = []
        for t in rg["atm"][0]["tasks"]:
            R0 = t["R0"]
            if R0 is not None and np.isfinite(R0) and R0 > 0:
                ah, av, _A = self.target_dims(self.los_angle(R0))
                f_low.append(t["lp"] * R0 / math.sqrt(ah * av))
        if f_low:
            f = min(f_low)
            add(e, "Lowest task bar frequency / fog aerosol cutoff", "%.3g" % (f / xc["fog"]))
            if f < 3.0 * xc["fog"] and any(wx["V_km"] < 1.0 for wx in wx_all):
                self.warn("Fog (visual range < 1 km): the lowest task bar frequency (%.3g cycles/mrad) is within a "
                          "factor 3 of the aerosol MTF cutoff of fog droplets (%.3g cycles/mrad); forward-scatter blur "
                          "below the cutoff is not modelled (Kopeika aerosol MTF)." % (f, xc["fog"]))

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
        add(g, "Sensor timing limit (%s)" % ("exposure overlaps readout" if self.exp_overlap else
                                             "readout after exposure"), "%.4g" % (self.t_timing * 1e3), "ms")
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
        for (z, _t, still), (_rg, _m, js) in sorted(self._jit_cache.items()):
            if still != self.still:
                continue                    # the NIIRS (single-frame) entry; the DRI mode is reported
            add(ds_, "Jitter %s: rms / intra-frame / frame-to-frame" % z, "%.3g / %.3g / %.3g" % (
                js["rms"] * 1e3, js["intra_rms"] * 1e3, js.get("sigma_frame", 0.0) * 1e3), "urad")
            add(ds_, "Jitter %s: offset / drift" % z, "%.3g / %.3g" % (js["offset"] * 1e3, js["drift"] * 1e3),
                "urad / urad/s")
        for (z, _t), (s_i, s_f, s_t) in sorted(self._psd_cache.items()):
            add(ds_, "PSD motion %s: total / intra-frame / frame-to-frame rms" % z,
                "%.3g / %.3g / %.3g" % (s_t * 1e3, s_i * 1e3, s_f * 1e3), "urad")
        mode = self.motion_active()
        add(ds_, "Motion model", "linked to exposure: %.4g ms%s" % (
            self.t_exposure() * 1e3, " (thermal time constant)" if self.uncooled else "") if mode else
            ("contained in the imported MTF" if "motion" in self.mtf_cov else "none"))
        add(ds_, "Readout", "rolling shutter, %.4g ms" % (self.t_readout * 1e3) if self.readout == "rolling"
            else "global shutter")
        add(ds_, "Noise source", self.noise_source)
        add(ds_, "Noise data quality", self.noise_quality)
        add(ds_, "Observer", {"legacy": "TRM4 standard observer (legacy-neutral)", "human": "Human, user-defined viewing",
                              "algorithm": "Algorithm '%s'" % (self.p["display"].get("algo_id") or "-")}[self.observer])
        if self.p["dsp"]["filter_on"]:
            add(ds_, "Digital filter max. boost", "%.2f (%s)" % (self.boost, "not credited" if self.boost_off else
                                                                 ("credited" if self.boost > 1.01 else "no boost")))
        for s in getattr(self, "coverage", []):
            add("Component coverage (no double counting)", ", ".join(c for c in COMPONENTS if c in s["components"]),
                s["source"] + (" [%s]" % s["file"] if s["file"] else ""))
        o = "Optics"
        add(o, "Effective focal length", "%.2f" % self.f_eff, "mm")
        add(o, "Clear pupil area / effective diameter", "%.1f / %.2f" % (self.A_pup, self.D_eff), "mm^2 / mm")
        add(o, "Effective F-number", "%.3f" % self.F_eff)
        fl = (res.get("dashboard") or {}).get("fld")
        if fl:
            add(o, "F lambda / d (mean wavelength %.2f um, pitch %.3g um)" % (fl["lambda_um"], fl["pitch_um"]),
                "%.2f - %s" % (fl["value"], fl["regime"]))
            add(o, "Hardware lever in this regime", fl["lever"])
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
        self._turb_info(add, s, res)
        self._extension_info(add, res)
        if not self.uncooled:
            op = "Detector operating point"
            add(op, "Operating mode (gain / readout / temperature)", self.op_mode or "not stated")
            add(op, "QE basis", {"unspecified": "not stated - TRM active-area convention",
                                 "active_area": "intrinsic, per active area",
                                 "pixel_area": "total, per full pixel area"}[self.qe_basis])
            add(op, "Active / pixel area, fill factor", "%.4g / %.4g, %.3f" % (
                self.A_active * 1e12, self.A_pixel * 1e12, self.fill_factor), "um^2")
            add(op, "QE reference area for photon -> carrier conversion", "%.4g" % (self.A_det * 1e12), "um^2")
            add(op, "Storage capacity (stated node)", "%.4g (%s)" % (self.n_stor, {
                "pixel": "physical pixel full well", "roic": "ROIC / storage node",
                "camera": "camera saturation capacity"}.get(self.cap_node, "node not stated")), "e-")
            add(op, "Usable capacity for well fill (limiting node)", "%.4g (%s)" % (self.n_use, self.cap_limit), "e-")
            add(op, "Capacity verified (input-referred camera saturation)", "yes" if self.cap_verified else
                "no - well fill is indicative")
            add(op, "Dark current", self.dark_label)
            if self.nbin["h"] * self.nbin["v"] > 1:
                add(op, "Binning", "%s, %d read-out(s) per binned pixel" % (self.bin_kind, self.n_reads))
            ex = getattr(self, "exposure", None)
            if ex:
                e = "Exposure budget (t_int <= min of the limits)"
                for name, t in ex["limits"]:
                    add(e, "Limit: %s" % name, "%.4g ms" % (t * 1e3) if np.isfinite(t) else "none")
                add(e, "Longest admissible integration time", "%.4g ms (%s)" % (ex["t_rec"] * 1e3, ex["limiter"])
                    if np.isfinite(ex["t_rec"]) else "unbounded")
                add(e, "Selected integration time", "%.4g" % (ex["t_sel"] * 1e3), "ms")
                if ex["t_hw_min"] > 0:
                    add(e, "Hardware minimum exposure", "%.4g" % (ex["t_hw_min"] * 1e3), "ms")
                add(e, "Brightest credible pixel: photoelectron rate", "%.4g" % ex["rate_bright"], "e-/s")
                add(e, "Brightest credible pixel: well fill at selected time", "%.1f" % ex["wellfill_bright"], "%")
                for z, px in sorted(ex["smear_px"].items()):
                    add(e, "Image smear during the exposure (%s)" % z, "%.3g" % px, "pixels")
                if "snr_req" in ex:
                    add(e, "Pixel SNR required / at selected / at longest admissible time",
                        " / ".join("%.3g" % x if x is not None else "-" for x in
                                   (ex["snr_req"], ex["snr_sel"], ex["snr_rec"])))
                add(e, "Status", ("feasible" if ex["feasible"] else "INFEASIBLE") +
                    ("; %d violation(s) at the selected time" % len(ex["violations"]) if ex["violations"] else ""))
            # photon arrival vs photoelectron generation rate per pixel (research review Sec. 4.1)
            atm0 = None if (self.lab or not self.atms or not self.R_ref or self.cat == "Thermal") else self.atms[0]
            Rr = self.R_ref if atm0 is not None else 0.0
            fp, fe = self.flux(Rr, atm0, qe=False), self.flux(Rr, atm0)
            r_ph = (fp["jB_scene"] + fp["j_path"]) * self.A_det
            r_e = (fe["jB_scene"] + fe["j_path"]) * self.A_det
            add("Radiometry", "Background photon arrival rate per pixel (%s)" % (
                "%.3g km" % Rr if atm0 is not None else "zero range"), "%.4g" % r_ph, "photons/s")
            add("Radiometry", "Background photoelectron generation rate per pixel", "%.4g" % r_e, "e-/s")
            if self.rel_illum < 1:
                add("Radiometry", "Photoelectron rate at the field edge (relative illumination %.2f)" % self.rel_illum,
                    "%.4g" % (r_e * self.rel_illum), "e-/s")
        for rec in getattr(self, "preset_records", []):
            add("Preset data in use (lifecycle)", "%s '%s'" % (rec["kind"], rec["name"]),
                "%s; %s; %s; uncertainty: %s; %s [%s]" % (rec["source"], rec["date"], rec["applicability"],
                                                          rec["uncertainty"], rec["warning"], rec["version"]))
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
            for z in "hv":
                mz = db["mtf"][z]
                add("Figure of merit", "Aliasing risk (%s): presampled spurious response in-band" % z,
                    "%s (%.2f)" % (mz["aliasing"], mz["spurious"]))
            rad = db["signal"]["radiance"]
            add("Radiometry", "Band radiance at aperture: target / background",
                "%.4g / %.4g" % (rad["L_T"], rad["L_B"]), "W/(m^2 sr)")
            add("Radiometry", "Band path radiance L_path", "%.4g" % rad["L_path"], "W/(m^2 sr)")
            sg = db["signal"]
            if "N_T" in sg:
                add("Radiometry", "Target / background mean signal", "%.4g / %.4g" % (sg["N_T"], sg["N_B"]), "e-")
            if "DN_T" in sg:
                add("Radiometry", "Target / background mean signal", "%.4g / %.4g" % (sg["DN_T"], sg["DN_B"]), "DN")
            if db.get("nps"):
                for z, q in db["nps"]["ratio"].items():
                    add("Noise / observer", "Measured NPS (%s) at Nyquist / low frequency (%s)" % (z, db["nps"]["stage"]),
                        "%.2f" % q, "1 = white")
            for t in db["tasks"]:
                if "mtf_task" in t:
                    add("Task diagnostics", "%s: pixels | cycles | MTF@task | CNR | limiter" % t["name"],
                        "%.1fx%.1f | %.1f | %.2f @ %.3g 1/mrad | %.3g | %s" % (
                            t["pix_h"], t["pix_v"], t["cyc_nyq"], t["mtf_task"], t["f_task"], t["cnr_task"],
                            t["limiter"]))
            add("Task diagnostics", "Model", db["model"])
            add("Task diagnostics", "Calibration status", db["calibration"])
        rg = res.get("range")
        if rg:
            for a in rg["atm"]:
                for t in a["tasks"]:
                    R0 = t["R0"]
                    txt = "< %.3f" % a["R"][0] if R0 is None else ("> %.0f" % a["R"][-1] if not np.isfinite(R0) else "%.3f" % R0)
                    add("Range performance", "%s (%g lp) - %s" % (t["name"], t["lp"], a["label"]), txt, "km")
        return I


def quick_estimate(project):
    """Geometric quick mode (extension): Nyquist / diffraction range of every active task without the AMOP
    simulation, noise, contrast or atmosphere -> {"tasks": [{name, lp, R0, limit}], "lambda_um", "ifov_mrad", "D_mm",
    "warnings"}.

    A first sizing of focal length / pitch / aperture, not a bound of the TRM4 range: the 4-bar AMOP also credits
    bars beyond Nyquist (longer ranges), while noise and contrast shorten them."""
    m = TRM4Model(project)
    m._validate_inputs()
    m._setup_geometry()
    m._setup_spectral()
    m._setup_atmospheres()
    m._setup_optics()
    m._setup_criteria()
    m._setup_weights(0.0)
    out = {"lambda_um": float(ph.trapz(m.lam * m.w, m.lam)),
           "ifov_mrad": math.sqrt(m.alpha_s["h"] * m.alpha_s["v"]), "D_mm": m.D_opt, "tasks": [],
           "warnings": m.warnings}
    for t in m._tasks():
        c = m._criterion(t)
        R0, limit = m._geo_range(c["lp"])
        out["tasks"].append({"name": t["name"], "lp": c["lp"], "R0": R0, "limit": limit})
    return out


def run_project(project, progress=None):
    """Run the model for a project dictionary; returns (model, results)."""
    m = TRM4Model(project, progress)
    res = m.run()
    return m, res
