"""Dependent (automatically calculated) imager values and input consistency checks.

These are cheap closed-form quantities shown read-only in the parameter pages while the user
edits independent inputs (Section 05 of the change roadmap): FOV, IFOV, sampling, Nyquist
frequency, effective aperture / F-number, Q = lambda F / pitch, diffraction cut-off and frame
timing.  Inconsistent redundant inputs produce warnings instead of silently overriding the
physical calculation.  The full model (model.py) uses the same equations (TRM4 3.1-3.11, 3.41-3.49).
"""
import math

from . import extensions as X
from . import mtf as M
from . import presets as P


def _f(x):
    return float(x)


def compute(p):
    """Return (rows, warnings).  rows: list of (group, label, value text, unit)."""
    rows, warn = [], []
    b, o, d = p["basic"], p["optics"], p["detector"]
    try:
        fh = _f(o["f_mm"])
        fv = _f(o["f_v_mm"]) if o["diff_focal"] else fh
        nb = {"h": max(1, int(b["bin_h"])), "v": max(1, int(b["bin_v"]))}
        pitch = {"h": _f(d["pitch_h_um"]), "v": _f(d["pitch_v_um"])}
        if d["shape"] in ("circular", "loophole"):
            a = {"h": _f(d["d_um"]), "v": _f(d["d_um"])}
        else:
            a = {"h": _f(d["a_h_um"]), "v": _f(d["a_v_um"])}
        n = {"h": int(d["n_h"]), "v": int(d["n_v"])}
    except (KeyError, ValueError, TypeError):
        return rows, ["Incomplete input - derived values cannot be calculated."]
    if fh <= 0 or fv <= 0 or min(pitch.values()) <= 0 or min(a.values()) <= 0 or min(n.values()) <= 0:
        return rows, ["Focal length, detector count, size and pitch must be > 0."]
    f = {"h": fh, "v": fv}
    ms = b["microscan"]
    ns = {"h": max(1, int(b["ms_steps_h"])), "v": max(1, int(b["ms_steps_v"]))} if ms == "rectangular" else \
        ({"h": 2, "v": 2} if ms in ("circular", "diagonal") else {"h": 1, "v": 1})
    a_eff = {z: a[z] + (nb[z] - 1) * pitch[z] for z in "hv"}
    p_eff = {z: pitch[z] * nb[z] for z in "hv"}
    n_el = {z: n[z] // nb[z] for z in "hv"}
    n_sam = {z: n_el[z] * ns[z] for z in "hv"}
    fov = {z: ((n_sam[z] - 1) / ns[z] * p_eff[z] + a_eff[z]) / f[z] for z in "hv"}          # mrad
    alpha = {z: p_eff[z] / (f[z] * ns[z]) for z in "hv"}                                    # mrad
    das = {z: a_eff[z] / f[z] for z in "hv"}
    rN = {z: 0.5 / alpha[z] for z in "hv"}
    G = "Geometry & sampling"
    rows.append((G, "Field of view h x v", "%.3f x %.3f" % (math.degrees(fov["h"] * 1e-3),
                                                           math.degrees(fov["v"] * 1e-3)), "deg"))
    rows.append((G, "IFOV = p / f (sampling distance) h x v", "%.1f x %.1f" % (alpha["h"] * 1e3, alpha["v"] * 1e3),
                 "urad"))
    rows.append((G, "Detector angular subtense (active size / f) h x v",
                 "%.1f x %.1f" % (das["h"] * 1e3, das["v"] * 1e3), "urad"))
    rows.append((G, "Angular Nyquist f / (2000 p) h x v", "%.3f x %.3f" % (rN["h"], rN["v"]), "cy/mrad"))
    rows.append((G, "Nyquist 1 / (2 p) (focal plane) h x v",
                 "%.1f x %.1f" % (500.0 / (p_eff["h"] / ns["h"]), 500.0 / (p_eff["v"] / ns["v"])), "cy/mm"))
    rows.append((G, "Samples h x v", "%d x %d" % (n_sam["h"], n_sam["v"]), ""))
    fill = a["h"] * a["v"] / (pitch["h"] * pitch["v"])
    rows.append((G, "Fill factor (active / pitch area)", "%.0f" % (100 * fill), "%"))
    rows.append((G, "Note", "IFOV is geometric - not a PSF or sharpness measure", ""))

    # aperture: one principal entry, its counterpart is calculated
    O = "Optics"
    f_eff = math.sqrt(fh * fv)
    if o["aperture"] == "general":
        F = _f(o["F_general"])
        if F <= 0:
            warn.append("Effective F-number must be > 0.")
            return rows, warn
        D_eff = f_eff / F
        rows.append((O, "Aperture diameter (from F-number)", "%.2f" % D_eff, "mm"))
    else:
        D, Do = _f(o["D_mm"]), _f(o["D_obsc_mm"])
        Wh, Wv = _f(o["W_trunc_h_mm"]), _f(o["W_trunc_v_mm"])
        if D > 0:
            if Do >= D:
                warn.append("Central obscuration must be smaller than the aperture diameter.")
                return rows, warn
            area = math.pi / 4 * (D * D - Do * Do)
            if Wh > 0 or Wv > 0:
                area = None          # truncated pupil: exact area is computed by the model
        elif Wh > 0 and Wv > 0:
            area = Wh * Wv
        else:
            warn.append("Specify an aperture diameter (or both truncation widths).")
            return rows, warn
        if area is None:
            D_eff = D
            rows.append((O, "F-number (f / D, truncation not included)", "%.3f" % (f_eff / D), ""))
        else:
            D_eff = math.sqrt(4 * area / math.pi)
            rows.append((O, "Effective F-number (f / D_eff)", "%.3f" % (f_eff / D_eff), ""))
        F = f_eff / D_eff
    if F < 0.5:
        warn.append("Effective F-number %.2f is below 0.5 - physically impossible optical geometry." % F)
    Fs = _f(o.get("F_spec", 0.0))
    if Fs > 0 and abs(Fs - F) / Fs > 0.05:
        warn.append("Specified F-number F/%.2f differs by %.0f %% from f / D = F/%.2f - check focal length and "
                    "aperture." % (Fs, 100 * abs(Fs - F) / Fs, F))
    win = P.qe_window(p)
    if win:
        lam_c = 0.5 * (win[0] + win[1])
        Q = lam_c * F / pitch["h"]
        rows.append((O, "Q = lambda F / pitch (band centre %.2f um)" % lam_c, "%.2f" % Q, ""))
        rows.append((O, "Diffraction cut-off D / lambda", "%.2f" % (D_eff / lam_c), "1/mrad"))
        rows.append((O, "Optics cut-off / Nyquist (h)", "%.2f" % (D_eff / lam_c / rN["h"]), ""))
        band = P.band_of(*win)
        cat = p["category"]
        if cat == "Thermal" and band in ("VIS/NIR", "SWIR"):
            warn.append("Thermal category with a %s detector band (%.2f-%.2f um) - unsupported combination; use the "
                        "Visible/NIR/SWIR category." % (band, win[0], win[1]))
        if cat == "Visible" and band in ("MWIR", "LWIR"):
            warn.append("Visible/NIR/SWIR category with a %s detector band - emission is ignored; use the Thermal or "
                        "General category." % band)

    T = "Timing"
    fr = _f(b["frame_rate"])
    if fr > 0:
        t_max = 1.0 / (fr * ns["h"] * ns["v"]) if ms != "diagonal" else 1.0 / (2 * fr)
        if b["interlace"] in ("electronic", "pseudo"):
            t_max /= 2
        rows.append((T, "Frame interval", "%.3f" % (1000.0 / fr), "ms"))
        rows.append((T, "Maximum integration time", "%.3f" % (1000.0 * t_max), "ms"))
        if d["tint_mode"] == "direct" and (p["category"] != "Thermal" or p["imager_type"] == "cooled"):
            ti = _f(d["tint_ms"]) * 1e-3
            rows.append((T, "Integration duty cycle", "%.3f" % (ti / t_max), ""))
            if ti > t_max * 1.0001:
                warn.append("Integration time %.3g ms is longer than the frame allows (%.3g ms)." % (ti * 1e3,
                                                                                                     t_max * 1e3))
        rows.append((T, "Motion model", "linked to exposure (integration time)", ""))
        if b.get("readout") == "rolling":
            ro = _f(b.get("readout_ms", 0.0))
            rows.append((T, "Readout", "rolling shutter, %.3g" % ro, "ms"))
            if ro <= 0:
                warn.append("Rolling-shutter readout needs a frame readout time > 0 ms.")
            elif ro > 1000.0 / fr * 1.0001:
                warn.append("Rolling-shutter readout time %.3g ms is longer than the frame interval." % ro)

    # cross-checks of redundant inputs
    for z in "hv":
        if a[z] > pitch[z] * 1.0001:
            warn.append("Active detector size (%s) is larger than the pitch." % z)
    if b["fov_mode"] == "measured":
        for z, key in (("h", "fov_h_deg"), ("v", "fov_v_deg")):
            meas = _f(b[key])
            calc = math.degrees(fov[z] * 1e-3)
            if meas > 0 and abs(calc - meas) / meas > 0.02:
                warn.append("Measured %s-FOV %.3f deg differs by %.1f %% from the calculated %.3f deg (calculated value "
                            "is used)." % (z, meas, 100 * abs(calc - meas) / meas, calc))
    disp = p["display"]
    zoom = max(1, int(round(_f(p["dsp"]["zoom"]))))
    nh = n_sam["h"] * zoom * max(1, int(p["dsp"]["crep"]))
    nv = n_sam["v"] * zoom * max(1, int(p["dsp"]["lrep"]))
    if nh > int(disp["n_h"]) or nv > int(disp["n_v"]):
        warn.append("Display has fewer elements (%dx%d) than image pixels (%dx%d)." % (disp["n_h"], disp["n_v"], nh, nv))
    _merged_views(p, rows, warn, alpha, rN, fov, nv, t_max if fr > 0 else None)
    return rows, warn


def _merged_views(p, rows, warn, alpha, rN, fov, nv, t_max):
    """One principal entry per physical quantity, its counterparts shown here (roadmap phase 2): transmission
    budget, extinction <-> visual range, integration time <-> duty cycle, system magnification, jitter in IFOV
    units and dark current in datasheet units."""
    o, d, disp, st = p["optics"], p["detector"], p["display"], p["stab"]
    cat = p["category"]
    photon = cat != "Thermal" or p["imager_type"] == "cooled"
    O = "Optics"
    tau = _f(o["tau_opt"]) if o.get("tau_mode", "value") == "value" else None
    filt = 1.0 if (o.get("tau_mode") == "zemax" and o.get("tau_scope") == "system") else _f(o["tau_filter"])
    if tau is not None:
        qe = _f(d["qe_scale"]) if photon or d.get("uncooled_response") == "preset" else 1.0
        rows.append((O, "Signal throughput tau_opt x tau_filter x QE scale", "%.3f" % (tau * filt * qe), ""))
    if cat == "Visible" and p["mode"]["environment"] == "field" and p["atmosphere"]["mode"] in ("visibility",
                                                                                                "extinction"):
        A = "Atmosphere"
        for i, at in enumerate(p["atmosphere"]["atm"]):
            if not at.get("on"):
                continue
            if p["atmosphere"]["mode"] == "visibility" and _f(at["V_km"]) > 0:
                rows.append((A, "Atm %d: extinction from the visual range (3.912 / V)" % (i + 1),
                             "%.4g" % (3.912 / _f(at["V_km"])), "1/km"))
            elif p["atmosphere"]["mode"] == "extinction" and _f(at["sigma"]) > 0:
                rows.append((A, "Atm %d: equivalent visual range (3.912 / sigma)" % (i + 1),
                             "%.4g" % (3.912 / _f(at["sigma"])), "km"))
    win = P.qe_window(p)
    if p["mode"]["environment"] == "field" and p["atmosphere"]["mode"] == "weather" and win:
        lam_c = 0.5 * (win[0] + win[1])
        for i, at in enumerate(p["atmosphere"]["atm"]):
            if not at.get("on") or _f(at["V_km"]) <= 0 or _f(at["T_air_K"]) <= 0:
                continue
            tot, aer, wv = (float(v) for v in X.weather_extinction(lam_c, _f(at["V_km"]), _f(at["T_air_K"]),
                                                                    _f(at.get("rh_pct", 50.0))))
            rows.append(("Atmosphere", "Atm %d: extinction from the weather at %.2f um (aerosol + water vapour)" % (
                i + 1, lam_c), "%.4g = %.4g + %.4g" % (tot, aer, wv), "1/km"))
    T = "Timing"
    if t_max and photon and d["tint_mode"] == "duty":
        rows.append((T, "Integration time (duty x maximum)", "%.4g" % (1000.0 * _f(d["duty"]) * t_max), "ms"))
    elif photon and d["tint_mode"] == "wellfill":
        rows.append((T, "Integration time", "set by the well fill - see System data after the run", ""))
    if disp.get("observer", "legacy") != "algorithm":
        V = "Display & observer"
        dist_m = (_f(disp["f_eyepiece_mm"]) / 1000.0 if disp["observation"] == "eyepiece" else
                  _f(disp["distance_cm"]) / 100.0)
        if dist_m > 0 and fov["v"] > 0:
            m_sys = nv * _f(disp["pitch_v_mm"]) / (fov["v"] * dist_m)                    # Eq. (3.16)
            rows.append((V, "System magnification M (displayed image angle / object angle)", "%.3g" % m_sys, ""))
            if not disp["neglect_eye"] and m_sys > 0:
                eye = math.exp(-M.eye_gamma(_f(disp["luminance"]), P.EYE_GAMMA) * rN["v"] / m_sys)   # Eq. (4.79)
                rows.append((V, "Eye MTF at the detector Nyquist frequency", "%.2f" % eye, ""))
                if eye < 0.2:
                    warn.append("The eye MTF at the detector Nyquist frequency is %.2f (< 0.2): the display "
                                "magnification M = %.3g limits the resolution - a shorter viewing distance, a "
                                "larger displayed image or an eyepiece with a shorter focal length raise it."
                                % (eye, m_sys))
    if st.get("jitter_mode", "model") == "model" and not st["neglect"] and st["random_on"]:
        S = "Motion"
        for z, key in (("h", "rand_h_mrad"), ("v", "rand_v_mrad")):
            sig = _f(st[key])
            if sig > 0:
                ratio = sig / alpha[z]
                rows.append((S, "Random jitter %s in IFOV units" % z, "%.4g urad = %.2f IFOV" % (sig * 1e3, ratio), ""))
                if ratio > 1.0 / 3.0:
                    warn.append("Random jitter %s is %.2f IFOV (> 1/3): the motion MTF, not the pixel, limits the "
                                "resolution." % (z, ratio))
    if st.get("jitter_mode", "model") == "model" and not st["neglect"] and st["lin_on"]:
        # smear of the linear motion (scan / pan) per exposure window: microbolometer time constant or integration time
        if not photon:
            t_e, what = _f(d["t_th_ms"]) * 1e-3, "thermal time constant"
        elif d["tint_mode"] == "direct":
            t_e, what = _f(d["tint_ms"]) * 1e-3, "integration time"
        elif d["tint_mode"] == "duty" and t_max:
            t_e, what = _f(d["duty"]) * t_max, "integration time"
        else:
            t_e, what = t_max, "maximum integration time"
        if t_e:
            sm = {z: abs(_f(st["lin_" + z])) * t_e / alpha[z] for z in "hv"}
            rows.append(("Motion", "Linear motion smear per %s h / v" % what, "%.3g / %.3g" % (sm["h"], sm["v"]),
                         "pixels"))
            if not photon and max(sm.values()) > 1.0:
                warn.append("Microbolometer scan smear: %.2f pixels within one thermal time constant - the exponential "
                            "detector response blurs the scanned image." % max(sm.values()))
    if photon and not (cat == "Thermal" and d["noise_mode"] == "measured") and d.get("dark_mode", "value") == "value":
        I = _f(d["dark_A"])
        if I > 0:
            area_cm2 = _f(d["pitch_h_um"]) * _f(d["pitch_v_um"]) * 1e-8
            rows.append(("Detector", "Dark current in datasheet units", "%.4g e-/s = %.4g nA/cm2 (pixel area)" % (
                I / 1.602176634e-19, I * 1e9 / area_cm2), ""))
