"""Dependent (automatically calculated) imager values and input consistency checks.

These are cheap closed-form quantities shown read-only in the parameter pages while the user
edits independent inputs (Section 05 of the change roadmap): FOV, IFOV, sampling, Nyquist
frequency, effective aperture / F-number, Q = lambda F / pitch, diffraction cut-off and frame
timing.  Inconsistent redundant inputs produce warnings instead of silently overriding the
physical calculation.  The full model (model.py) uses the same equations (TRM4 3.1-3.11, 3.41-3.49).
"""
import math

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
    rows.append((G, "IFOV (detector angular subtense) h x v", "%.1f x %.1f" % (das["h"] * 1e3, das["v"] * 1e3),
                 "urad"))
    rows.append((G, "Sampling distance h x v", "%.1f x %.1f" % (alpha["h"] * 1e3, alpha["v"] * 1e3), "urad"))
    rows.append((G, "Nyquist frequency h x v", "%.3f x %.3f" % (rN["h"], rN["v"]), "1/mrad"))
    rows.append((G, "Nyquist frequency (focal plane) h x v", "%.1f x %.1f" % (500.0 / p_eff["h"], 500.0 / p_eff["v"]),
                 "lp/mm"))
    rows.append((G, "Samples h x v", "%d x %d" % (n_sam["h"], n_sam["v"]), ""))
    fill = a["h"] * a["v"] / (pitch["h"] * pitch["v"])
    rows.append((G, "Fill factor (active / pitch area)", "%.0f" % (100 * fill), "%"))

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
    return rows, warn
