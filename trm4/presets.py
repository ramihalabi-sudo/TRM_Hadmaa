"""Preset data (Appendix C of the TRM4.v3 documentation) and project templates.

IMPORTANT: The original TRM4 ships the preset spectra as data files.  The document only shows
them as graphs, so the spectral curves below were digitised approximately from Figures in
Appendix C.  Scalar data taken from tables (peak irradiances, Cn2 values, STANAG targets,
phosphor/eye parameters) is reproduced exactly.
"""

# ---------------------------------------------------------------------------------------------
# C.1 Detector spectral quantum efficiencies [um, %]
# ---------------------------------------------------------------------------------------------
DETECTOR_QE = {
    "CCD Silicon generic": [(0.25, 0), (0.3, 8), (0.35, 35), (0.4, 50), (0.45, 68), (0.5, 72), (0.55, 76),
                            (0.6, 78), (0.65, 75), (0.7, 67), (0.75, 55), (0.8, 43), (0.85, 32), (0.9, 23),
                            (0.95, 15), (1.0, 8), (1.05, 3), (1.12, 0)],
    "InGaAs generic": [(0.88, 0), (0.92, 5), (0.95, 30), (0.98, 68), (1.02, 71), (1.3, 71), (1.4, 67),
                       (1.5, 62), (1.55, 58), (1.6, 55), (1.63, 40), (1.66, 20), (1.7, 5), (1.75, 0)],
    "InGaAs extended generic": [(0.98, 0), (1.05, 8), (1.1, 20), (1.2, 42), (1.3, 55), (1.4, 64), (1.5, 68),
                                (1.8, 69), (2.0, 70), (2.05, 68), (2.1, 64), (2.15, 45), (2.2, 10),
                                (2.25, 3), (2.3, 0)],
    "CMT MWIR generic": [(2.6, 58), (3.0, 58), (3.4, 61), (3.8, 66), (4.1, 72), (4.35, 69), (4.6, 80),
                         (4.9, 77), (5.0, 70), (5.1, 35), (5.2, 8), (5.3, 0)],
    "QWIP MWIR generic": [(2.5, 0), (3.0, 0.1), (3.5, 0.4), (4.0, 1.2), (4.25, 2.2), (4.5, 3.8), (4.75, 5.7),
                          (5.0, 4.5), (5.25, 1.3), (5.5, 0.3), (6.0, 0)],
    "InSb MWIR generic": [(2.5, 82), (2.8, 86), (3.0, 81), (3.5, 82), (3.8, 82), (4.1, 85), (4.5, 82),
                          (5.0, 85), (5.3, 86), (5.4, 55), (5.48, 27), (5.6, 3), (5.7, 0)],
    # not from Appendix C: XBn (InAsSb barrier) MWIR, band 3.6-4.2 um (50 % points),
    # QE > 85 % over 3.65-4.15 um (~84 % of the band)
    "XBn MWIR 3.6-4.2 um": [(3.5, 0), (3.55, 10), (3.6, 55), (3.63, 80), (3.65, 86), (3.7, 88), (3.8, 89),
                            (3.9, 90), (4.0, 89), (4.1, 88), (4.15, 86), (4.17, 80), (4.2, 55), (4.25, 10),
                            (4.3, 0)],
    "CMT LWIR generic": [(7.0, 74), (7.5, 72), (8.0, 69), (8.5, 72), (9.0, 75), (9.5, 80), (10.0, 82),
                         (10.4, 85), (10.6, 85), (10.8, 82), (11.0, 78), (11.2, 65), (11.35, 40), (11.4, 0)],
    "QWIP LWIR generic": [(7.1, 2.0), (7.5, 2.7), (8.0, 3.8), (8.5, 5.3), (8.75, 7.3), (9.0, 7.7), (9.25, 6.6),
                          (9.5, 5.0), (10.0, 3.0), (10.5, 1.5), (11.0, 0)],
}

# ---------------------------------------------------------------------------------------------
# C.5 Spectral reflectivity (0.4 - 2.5 um) and emissivity (2.5 - 14 um) [%]
# ---------------------------------------------------------------------------------------------
REFLECTIVITY = {
    # backgrounds - vegetation
    "Dry grassland": [(0.4, 14), (0.5, 23), (0.6, 32), (0.7, 44), (0.8, 55), (1.0, 63), (1.2, 66), (1.3, 67),
                      (1.45, 56), (1.6, 58), (1.7, 60), (1.85, 57), (1.95, 45), (2.0, 50), (2.1, 45),
                      (2.2, 46), (2.35, 40), (2.5, 33)],
    "Green grassland": [(0.4, 4), (0.5, 6), (0.55, 10), (0.6, 7), (0.68, 4), (0.72, 20), (0.75, 45), (0.8, 50),
                        (1.0, 50), (1.1, 52), (1.2, 47), (1.3, 48), (1.4, 22), (1.45, 15), (1.6, 28), (1.7, 31),
                        (1.8, 28), (1.9, 6), (2.0, 8), (2.2, 16), (2.4, 8), (2.5, 6)],
    "Needle leaf forest": [(0.4, 4), (0.55, 11), (0.68, 4), (0.75, 45), (0.9, 51), (1.1, 48), (1.2, 42),
                           (1.4, 11), (1.65, 26), (1.9, 4), (2.2, 12), (2.5, 4)],
    "Broad leaf forest": [(0.4, 5), (0.55, 11), (0.68, 4), (0.75, 45), (0.9, 55), (1.1, 56), (1.2, 50),
                          (1.4, 16), (1.65, 32), (1.9, 5), (2.2, 17), (2.5, 5)],
    # backgrounds - man made
    "Asphalt": [(0.4, 6), (1.0, 8), (2.0, 8), (2.5, 7)],
    "Concrete": [(0.4, 10), (0.5, 20), (0.6, 28), (0.8, 31), (1.0, 33), (1.5, 37), (1.85, 40), (1.9, 35),
                 (2.0, 38), (2.2, 38), (2.5, 30)],
    "Brick": [(0.4, 3), (0.55, 5), (0.6, 17), (0.7, 26), (0.8, 25), (1.0, 33), (1.2, 50), (1.5, 52),
              (1.85, 53), (1.9, 48), (2.0, 53), (2.5, 48)],
    # soils
    "Dark Sand": [(0.4, 2), (0.6, 18), (0.8, 26), (1.0, 32), (1.4, 38), (1.8, 41), (1.9, 37), (2.1, 41),
                  (2.5, 36)],
    "Snow": [(0.4, 97), (0.6, 97), (0.8, 91), (1.0, 70), (1.1, 72), (1.2, 50), (1.35, 44), (1.45, 5),
             (1.5, 2), (1.8, 18), (1.9, 2), (2.0, 1), (2.25, 9), (2.5, 2)],
    "Pale Loam": [(0.4, 2), (0.5, 20), (0.6, 36), (0.7, 45), (0.9, 48), (1.2, 55), (1.4, 50), (1.7, 57),
                  (1.85, 55), (1.92, 37), (2.1, 55), (2.3, 48), (2.5, 35)],
    "Dark Loam": [(0.4, 1), (0.6, 10), (0.8, 16), (1.0, 18), (1.4, 21), (1.8, 23), (1.9, 17), (2.2, 23),
                  (2.5, 18)],
    # rocks
    "Gneiss": [(0.4, 7), (0.5, 12), (0.7, 12), (0.9, 16), (1.2, 25), (1.5, 40), (1.8, 53), (2.1, 62),
               (2.25, 61), (2.3, 57), (2.5, 60)],
    "Granite": [(0.4, 33), (0.5, 40), (0.6, 44), (0.8, 47), (1.2, 48), (1.6, 49), (2.0, 50), (2.5, 50)],
    "Basalt": [(0.4, 16), (0.6, 22), (0.8, 23), (1.0, 18), (1.2, 23), (1.6, 27), (2.0, 26), (2.5, 27)],
    # targets
    "Aluminum": [(0.4, 40), (0.6, 52), (0.8, 53), (1.0, 68), (1.5, 80), (2.0, 85), (2.5, 88)],
    "Oxidized Steel": [(0.4, 20), (0.5, 30), (0.6, 29), (0.8, 24), (1.0, 18), (1.4, 40), (1.8, 54), (2.2, 57),
                       (2.5, 57)],
    "Olive green paint": [(0.4, 6), (0.5, 12), (0.55, 22), (0.6, 12), (0.7, 11), (0.72, 67), (0.8, 63),
                          (1.0, 78), (1.3, 85), (1.4, 58), (1.6, 63), (1.8, 60), (1.9, 40), (2.0, 46),
                          (2.2, 40), (2.3, 28), (2.5, 21)],
    "Black paint": [(0.4, 3), (1.0, 3.5), (2.5, 4)],
}

EMISSIVITY = {
    "Dry grassland": [(2.5, 62), (3.0, 95), (3.5, 85), (4.0, 76), (5.0, 75), (5.8, 92), (6.0, 93), (8.0, 97),
                      (10.0, 93), (11.0, 90), (12.0, 92), (14.0, 95)],
    "Green grassland": [(2.5, 95), (3.0, 98), (14.0, 98)],
    "Needle leaf forest": [(2.5, 96), (3.0, 99), (14.0, 99)],
    "Broad leaf forest": [(2.5, 95), (3.0, 98), (14.0, 97.5)],
    "Asphalt": [(2.5, 93), (6.0, 96), (8.5, 94), (9.5, 93), (14.0, 96)],
    "Concrete": [(2.5, 72), (2.8, 95), (3.5, 88), (4.0, 86), (5.0, 91), (6.0, 97), (8.0, 95), (8.3, 86),
                 (9.2, 85), (10.5, 94), (14.0, 97)],
    "Brick": [(2.5, 55), (2.9, 88), (3.5, 70), (4.0, 61), (4.5, 75), (5.5, 90), (7.0, 97), (8.0, 97),
              (9.0, 91), (10.0, 95), (12.0, 98), (14.0, 98)],
    "Dark Sand": [(2.5, 65), (3.0, 97), (4.0, 82), (5.0, 90), (6.0, 98), (8.0, 97), (8.2, 82), (9.0, 85),
                  (9.5, 90), (11.0, 97), (14.0, 98)],
    "Snow": [(2.5, 98), (3.0, 99), (14.0, 99)],
    "Pale Loam": [(2.5, 70), (3.0, 95), (4.0, 73), (4.5, 80), (6.0, 97), (7.5, 93), (9.0, 94), (12.0, 97),
                  (14.0, 97)],
    "Dark Loam": [(2.5, 82), (3.0, 97), (4.0, 84), (6.0, 98), (8.0, 96), (9.0, 95), (14.0, 98)],
    "Gneiss": [(2.5, 40), (2.7, 82), (3.5, 43), (4.0, 43), (5.0, 65), (6.0, 85), (8.0, 97), (12.0, 95),
               (14.0, 98)],
    "Granite": [(2.5, 50), (2.8, 80), (3.5, 50), (4.0, 52), (5.0, 75), (6.0, 90), (8.0, 98), (9.0, 94),
                (11.0, 92), (12.0, 93), (13.0, 98), (14.0, 98)],
    "Basalt": [(2.5, 75), (3.0, 72), (4.0, 66), (5.0, 75), (8.0, 97), (14.0, 98)],
    "Aluminum": [(2.5, 11), (4.0, 8), (6.0, 7), (10.0, 5), (14.0, 5)],
    "Oxidized Steel": [(2.5, 45), (2.8, 80), (3.5, 50), (4.0, 45), (5.0, 45), (6.0, 58), (6.5, 48), (7.0, 52),
                       (8.0, 45), (9.0, 76), (10.0, 68), (11.0, 62), (12.0, 56), (14.0, 56)],
    "Olive green paint": [(2.5, 78), (3.0, 95), (4.0, 86), (5.0, 86), (5.5, 95), (8.0, 96), (9.0, 93),
                          (12.0, 95), (14.0, 97)],
    "Black paint": [(2.5, 95), (14.0, 95)],
}

# ---------------------------------------------------------------------------------------------
# C.6 Natural irradiation sources: approximate normalized spectral shape + exact peak values
# ---------------------------------------------------------------------------------------------
# shape: ("bb", T) -> blackbody of colour temperature T, or list of points (normalized)
NATURAL_SOURCES = {
    "Direct sunlight": {"peak": 1239.0, "shape": ("bb", 5800.0)},
    "Overcast daylight": {"peak": 14.19, "shape": ("bb", 6500.0)},
    "Full moon": {"peak": 1.74e-3, "shape": ("bb", 4300.0)},
    "Quarter moon": {"peak": 7.84e-4, "shape": ("bb", 4300.0)},
    "Star light": {"peak": 7.04e-4, "shape": [(0.4, 0.02), (0.6, 0.03), (0.8, 0.06), (1.0, 0.12), (1.2, 0.25),
                                              (1.3, 0.3), (1.37, 0.05), (1.45, 0.3), (1.5, 0.9), (1.6, 1.0),
                                              (1.8, 0.9), (1.85, 0.1), (1.95, 0.3), (2.0, 0.25)]},
}

# ---------------------------------------------------------------------------------------------
# Table C.2: recommended Cn2 values at 2 m height [m^-2/3]
# (climate, time) -> (90% winter, 90% summer, 50% winter, 50% summer)
# ---------------------------------------------------------------------------------------------
CN2_TABLE = {
    ("Arid", "Night"): (7.4e-14, 6.0e-14, 1.9e-14, 9.2e-15),
    ("Arid", "Noon"): (3.4e-13, 1.1e-12, 1.6e-13, 9.2e-13),
    ("Moderate", "Night"): (1.2e-13, 7.3e-14, 4.8e-14, 1.3e-14),
    ("Moderate", "Noon"): (2.2e-13, 5.1e-13, 3.7e-14, 2.0e-13),
    ("Subarctic", "Night"): (2.2e-13, 3.8e-14, 6.4e-14, 6.0e-15),
    ("Subarctic", "Noon"): (1.5e-13, 3.8e-13, 4.6e-14, 7.6e-14),
}

# Table 4.2: width of the eye point spread function vs display luminance (log10 fL)
EYE_GAMMA = [(-2, 2.2773), (-1, 1.8300), (0, 1.4650), (1, 1.0980), (2, 0.9598), (3, 0.81333)]

# Table 2.1: TRM4 target models for the Thermal category
THERMAL_TARGETS = {
    "STANAG 4347": {"W_m": 2.3, "H_m": 2.3, "D_m": 0.0, "T_bg_K": 288.0, "dT_K": 2.0,
                    "tasks": [1.0, 3.0, 6.0], "task_on": [True, True, True]},
    "Handheld objects": {"W_m": 0.08, "H_m": 0.70, "D_m": 0.08, "T_bg_K": 288.0, "dT_K": 1.0,
                         "tasks": [2.5, 3.5, 5.4], "task_on": [True, True, True]},
    "Persons": {"W_m": 0.6, "H_m": 1.7, "D_m": 0.4, "T_bg_K": 288.0, "dT_K": 2.0,
                "tasks": [1.0, 2.5, 6.0], "task_on": [True, True, False]},
}

# Table 4.1: phosphor screen double-exponential parameters (for reference / future ICCD use)
PHOSPHOR = {"P43": (0.237, 3.455e-5, 6.205e-4), "P46": (0.139, 5.917e-7, 6.875e-8),
            "P47": (5.470e-2, 3.662e-7, 4.200e-8), "P20": (0.914, 1.639e-3, 4.552e-2)}

QE_NAMES = list(DETECTOR_QE.keys()) + ["Custom"]
MATERIAL_NAMES = list(REFLECTIVITY.keys())
SOURCE_NAMES = list(NATURAL_SOURCES.keys())


# ---------------------------------------------------------------------------------------------
# Default project and templates
# ---------------------------------------------------------------------------------------------
def _atm(on, sigma, tau0=1.0, T_air=288.0, F_PR=0.15, V=20.0):
    return {"on": on, "sigma": sigma, "tau0": tau0, "T_air_K": T_air, "F_PR": F_PR, "V_km": V}


_NOFILE = {"name": "", "text": ""}

# ---------------------------------------------------------------------------------------------
# Atmosphere presets for the fast (Beer-Lambert) mode: effective extinction coefficients [1/km]
# per spectral band.  These are typical engineering values for horizontal paths near the ground
# (visible values from Koschmieder with V = 23 / 10 / 3 km).  They are assumptions, not
# measurements - use measured or MODTRAN data (spectral import) where accuracy matters.
# ---------------------------------------------------------------------------------------------
ATM_PRESETS = {
    "VIS/NIR": {"clear": 0.17, "average": 0.39, "adverse": 1.30},
    "SWIR":    {"clear": 0.10, "average": 0.25, "adverse": 0.90},
    "MWIR":    {"clear": 0.15, "average": 0.30, "adverse": 0.80},
    "LWIR":    {"clear": 0.20, "average": 0.40, "adverse": 1.00},
}
ATM_PRESET_NAMES = [("custom", "Custom (enter extinction below)"), ("clear", "Clear"), ("average", "Average"),
                    ("adverse", "Adverse"), ("all", "Compare clear / average / adverse")]


def band_of(lo_um, hi_um):
    """Spectral band name for a detector window (used for presets and plausibility checks)."""
    mid = 0.5 * (lo_um + hi_um)
    if mid < 1.1:
        return "VIS/NIR"
    if mid < 3.0:
        return "SWIR"
    if mid < 6.0:
        return "MWIR"
    return "LWIR"


def qe_window(project):
    """Approximate detector spectral window (lo, hi) [um] without running the model."""
    d = project["detector"]
    if project["category"] == "Thermal" and project["imager_type"] == "uncooled" and \
            d.get("uncooled_response") == "flat":
        return float(d["cuton_um"]), float(d["cutoff_um"])
    pts = DETECTOR_QE.get(d.get("qe_preset"))
    if pts is None:
        rows = []
        for line in str(d.get("qe_custom", "")).splitlines():
            parts = line.split("#")[0].replace(",", " ").replace(";", " ").split()
            try:
                rows.append(float(parts[0]))
            except (ValueError, IndexError):
                pass
        if len(rows) < 2:
            return None
        lo, hi = min(rows), max(rows)
        return (lo / 1000.0, hi / 1000.0) if hi > 100 else (lo, hi)
    pos = [x for x, q in pts if q > 0]
    return (min(pos), max(pos)) if pos else None


def atmosphere_preset(project, which):
    """Atmosphere list for a preset name ('clear', 'average', 'adverse' or 'all')."""
    win = qe_window(project) or (8.0, 12.0)
    tab = ATM_PRESETS[band_of(*win)]
    old = project["atmosphere"]["atm"]
    names = ["clear", "average", "adverse"] if which == "all" else [which]
    out = []
    for i in range(3):
        at = dict(old[i]) if i < len(old) else _atm(False, 0.5)
        if i < len(names):
            at.update(on=True, sigma=tab[names[i]], tau0=1.0, V_km=round(3.912 / tab[names[i]], 2))
        else:
            at["on"] = False
        out.append(at)
    return out


# Turbulence: Cn2 presets from Table C.2 (value at 2 m height, simplified height dependence)
CN2_PRESETS = {}
for (_clim, _time), _vals in CN2_TABLE.items():
    for _k, _lab in enumerate(("90 % winter", "90 % summer", "50 % winter", "50 % summer")):
        CN2_PRESETS["%s, %s, %s" % (_clim, _time.lower(), _lab)] = {"cn2": _vals[_k], "time": "day" if _time == "Noon"
                                                                     else "night"}

# Task criteria presets (field map Sec. 4.2 / 15.2.10).  The legacy preset is the default and is never changed
# automatically; the others are documented alternatives from the Johnson-criteria literature (Sandia SAND2015-6368).
# Values are line pairs (= cycles) across the critical target dimension for Detection / Recognition / Identification.
TASK_PRESETS = {
    "legacy": ("TRM4 / STANAG legacy: 1 / 3 / 6 lp", (1.0, 3.0, 6.0)),
    "sandia148": ("1 / 4 / 8 cycles (alternative tradition, Sandia report)", (1.0, 4.0, 8.0)),
    "johnson1958": ("Johnson 1958, 50 %: 1 / 4 / 6.4 cycles", (1.0, 4.0, 6.4)),
    "target": ("From the TRM4 standard target model (Table 2.1)", None),
    "custom": ("Custom (user values)", None),
}


def task_preset_values(project):
    """Criteria (D, R, I) the selected task preset stands for, None for custom values."""
    t = project["target"]
    key = t.get("task_preset", "legacy")
    if key == "target":
        tm = THERMAL_TARGETS.get(t.get("preset"))
        return tuple(tm["tasks"]) if tm and project["category"] == "Thermal" else None
    return (TASK_PRESETS.get(key) or (None, None))[1]

# Data source (provenance) categories shown next to each parameter
SOURCES = [("preset", "Preset / template"), ("assumption", "Assumption"), ("user", "Entered by user"),
           ("manufacturer", "Manufacturer datasheet"), ("measurement", "Measurement"), ("import", "Imported file"),
           ("profile", "Camera profile")]

DEFAULT_PROJECT = {
    "schema": 2,
    "name": "",
    "category": "Thermal",           # Thermal | Visible | General
    "imager_type": "cooled",         # Thermal: cooled | uncooled ; Visible/General: staring
    "mode": {"environment": "field", "ref_range_km": 0.0, "stream": "video", "niirs": False},
    "basic": {"frame_rate": 50.0, "fov_mode": "calculate", "fov_h_deg": 0.0, "fov_v_deg": 0.0,
              "interlace": "progressive", "microscan": "none", "ms_steps_h": 2, "ms_steps_v": 2,
              "integ_during_move": False, "bin_h": 1, "bin_v": 1, "n_sensors": 1,
              "readout": "global", "readout_ms": 0.0},
    "optics": {"aperture": "circular", "D_mm": 50.0, "D_obsc_mm": 0.0, "W_trunc_h_mm": 0.0,
               "W_trunc_v_mm": 0.0, "f_mm": 100.0, "diff_focal": False, "f_v_mm": 100.0, "F_general": 2.0,
               "diffraction": "spectral", "lambda_diff_um": 10.0, "aberration": "none", "q": 1.3,
               "blur_um": 5.0, "tau_opt": 0.8, "tau_filter": 1.0,
               "mtf_source": "model", "zemax_mtf": {"name": "", "text": ""}, "zemax_mtf_unit": "auto",
               "zemax_mtf_field": 1, "zemax_mtf_h": "sagittal", "mtf_meta": "",
               # component coverage of an imported MTF (field map Sec. 12.3 / 15.4)
               "mtf_incl_diffraction": True, "mtf_incl_detector": False, "mtf_incl_motion": False,
               "tau_mode": "value", "zemax_tau": {"name": "", "text": ""}, "tau_kind": "absolute",
               "tau_scope": "optics", "F_spec": 0.0},
    "detector": {"shape": "rectangular", "a_h_um": 14.0, "a_v_um": 14.0, "d_um": 14.0, "d_hole_um": 2.0,
                 "n_h": 640, "n_v": 512, "pitch_h_um": 15.0, "pitch_v_um": 15.0,
                 "cte_on": False, "cte_h": 0.9999, "ntr_h": 320, "cte_v": 0.9999, "ntr_v": 256,
                 "xtalk_h": 0.0, "xtalk_v": 0.0,
                 "qe_preset": "CMT LWIR generic", "qe_custom": "", "qe_scale": 1.0, "qe_unit": "auto",
                 "netd_TB_K": 0.0, "adc_bits": 0,
                 "uncooled_response": "flat", "cuton_um": 8.0, "cutoff_um": 14.0,
                 "tint_mode": "wellfill", "tint_ms": 0.2, "duty": 0.5, "wellfill_pct": 50.0,
                 "storage_e": 1.5e7, "electron_gain": 1.0, "dark_A": 1e-12, "noise_floor_e": 500.0,
                 "noise_figure": 1.0, "adc_mode": "carriers", "lsb_e": 1000.0, "lsb_mK": 0.0,
                 "T_off_dev_K": 0.0, "T_off_opt_K": 0.0, "T_cs_K": 77.0, "cs_mode": "efficiency",
                 "cs_eff": 1.0, "cs_F": 2.0,
                 "noise_mode": "calculated", "netd_mK": 30.0, "meas_F": 0.0, "meas_tau": 0.0,
                 "meas_TB_K": 0.0, "t_th_ms": 10.0, "readout_mK": 0.0,
                 # test conditions of a measured camera NETD (field map Sec. 12.4 / 15.2.6)
                 "netd_F": 0.0, "netd_tint_ms": 0.0, "netd_frames": 1, "netd_nuc": "",
                 # measured noise power spectrum (quality check only, not used for the ranges)
                 "nps_file": dict(_NOFILE), "nps_unit": "mrad", "nps_stage": "raw",
                 "fpn_mode": "estimate", "ietd_mK": 20.0, "fpn_fraction": 0.5, "prnu_pct": 0.5,
                 "dsnu_A": 1e-15},
    "dsp": {"filter_on": False, "filter_dir": "both", "h_type": "odd", "h_coef": [1.0, 0.5, 0.0, 0.0, 0.0],
            "v_type": "odd", "v_coef": [1.0, 0.5, 0.0, 0.0, 0.0], "zoom": 1, "zoom_type": "pixel",
            "lrep": 1, "lrep_type": "pixel", "crep": 1, "crep_type": "pixel",
            "frames_on": False, "n_frames": 1, "iir_on": False, "iir_alpha": 0.0,
            # sharpening (boost) is credited in the ranges only on request (field map SP-01)
            "credit_boost": False,
            # processing pipeline documentation (field map Sec. 15.2.7)
            "pl_denoise": False, "pl_compression": "none", "pl_order": "", "pl_version": ""},
    "display": {"n_h": 1280, "n_v": 1024, "pitch_h_mm": 0.27, "pitch_v_mm": 0.27, "luminance": 50.0,
                "observation": "direct", "f_eyepiece_mm": 25.0, "distance_cm": 50.0, "snr_th": 2.5,
                "t_eye_s": 0.1, "neglect_eye": False,
                # observer (field map Sec. 15.2.8): legacy = TRM4 standard observer
                "observer": "legacy", "algo_id": "", "algo_calib": "", "algo_roc": ""},
    "stab": {"neglect": False, "random_on": False, "rand_h_mrad": 0.0, "rand_v_mrad": 0.0,
             "lin_on": False, "lin_h": 0.0, "lin_v": 0.0, "sin_on": False, "sin_h": 0.0, "sin_v": 0.0,
             "jitter_mode": "model", "jitter_file": dict(_NOFILE), "jitter_unit": "urad", "jitter_rate_hz": 0.0,
             # angular PSD of the residual line-of-sight motion (field map Sec. 15.2.9)
             "psd_file": dict(_NOFILE), "psd_unit": "urad2", "residual_los": True},
    "additional": {"pre_h_type": "none", "pre_h_par": 10.0, "pre_v_type": "none", "pre_v_par": 10.0,
                   "post_h_type": "none", "post_h_par": 10.0, "post_v_type": "none", "post_v_par": 10.0},
    "target": {"preset": "STANAG 4347", "alt_m": 1.0, "dT_K": 2.0, "W_m": 2.3, "H_m": 2.3, "D_m": 0.0,
               "t_emis_mode": "blackbody", "t_emis": 0.9, "t_emis_preset": "Olive green paint",
               "t_refl_mode": "effective", "t_refl": 0.3, "t_refl_preset": "Olive green paint",
               "b_emis_mode": "blackbody", "b_emis": 0.9, "b_emis_preset": "Green grassland",
               "b_refl_mode": "effective", "b_refl": 0.15, "b_refl_preset": "Green grassland",
               "T_bg_K": 288.0, "aspect": "front", "flight": "altitude", "altitude_m": 0.0, "angle_deg": 0.0,
               "tasks": [{"name": "Detection", "on": True, "lp": 1.0},
                         {"name": "Recognition", "on": True, "lp": 3.0},
                         {"name": "Identification", "on": True, "lp": 6.0}],
               "task_preset": "legacy", "clutter": "not_specified", "scene_id": ""},
    "irradiance": {"mode": "none", "type": "broadband", "spectrum": "colour", "T_colour_K": 5800.0,
                   "E_peak": 1239.0, "E_eff": 100.0, "preset": "Direct sunlight", "lambda_um": 0.85,
                   "E_mono": 1.0, "T_bb_K": 6000.0, "geometry": "extended", "beta_h_deg": 0.0,
                   "beta_v_deg": 45.0},
    "atmosphere": {"mode": "extinction", "preset": "custom",
                   "atm": [_atm(True, 0.2), _atm(True, 1.0), _atm(False, 0.5)],
                   "spec_file": dict(_NOFILE), "spec_L_km": 1.0,
                   "path_mode": "model", "path_file": dict(_NOFILE), "path_L_km": 1.0,
                   # documentation of imported atmospheric data (field map Sec. 15.2.12)
                   "meta": {"geometry": "", "source": "", "conditions": ""}},
    "turbulence": {"on": False, "exposure": "short", "cn2_mode": "fixed", "cn2": 1e-14, "h_ref_m": 2.0,
                   "time": "day", "cn2_preset": "custom",
                   # Fried parameter input with its reference conditions (cn2_mode = "r0")
                   "r0_cm": 5.0, "r0_lambda_um": 0.55, "r0_L_km": 1.0},
    # measured system data (Laboratory & Image Evaluation workflow)
    "measured": {"fom_file": dict(_NOFILE), "fom_kind": "MTDP", "fom_unit": "mrad", "fom_vunit": "K", "fom_use": "compare",
                 "sfr_file": dict(_NOFILE), "sfr_kind": "device", "sfr_unit": "mrad",
                 "netd_mK": 0.0, "netd_TB_K": 0.0,
                 "meta": {"instrument": "", "date": "", "method": "", "focus": "", "temperature": "",
                          "processing": "", "uncertainty": "", "config_id": ""}},
    "profile": {"name": "", "config": ""},
    "provenance": {},                # parameter path -> data source (see SOURCES)
    "uncertainty": {},               # uncertainty-study settings (see analysis.uncertainty_settings)
    "scenarios": [],                 # saved configurations for scenario comparison: {"name", "project"}
}


def deep_merge(base, override):
    """Recursively merge `override` into a copy of `base`."""
    import copy
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


TEMPLATES = {
    "Thermal - LWIR cooled staring 640x512 (CMT)": {
        "name": "LWIR cooled staring 640x512",
    },
    "Thermal - MWIR cooled staring 640x512 (InSb)": {
        "name": "MWIR cooled staring 640x512",
        "optics": {"D_mm": 50.0, "f_mm": 200.0, "lambda_diff_um": 4.0},
        "detector": {"qe_preset": "InSb MWIR generic", "storage_e": 7e6, "wellfill_pct": 60.0,
                     "cs_eff": 1.0, "noise_floor_e": 300.0, "lsb_e": 500.0},
        "atmosphere": {"atm": [_atm(True, 0.2, 0.8), _atm(True, 1.0, 0.8), _atm(False, 0.5, 0.8)]},
    },
    "Thermal - MWIR cooled staring 640x512 (XBn 3.6-4.2 um)": {
        "name": "MWIR XBn cooled staring 640x512",
        "optics": {"D_mm": 50.0, "f_mm": 200.0, "lambda_diff_um": 3.9},
        "detector": {"qe_preset": "XBn MWIR 3.6-4.2 um", "storage_e": 7e6, "wellfill_pct": 60.0,
                     "cs_eff": 1.0, "noise_floor_e": 300.0, "lsb_e": 500.0, "T_cs_K": 150.0},
        "atmosphere": {"atm": [_atm(True, 0.2, 0.8), _atm(True, 1.0, 0.8), _atm(False, 0.5, 0.8)]},
    },
    "Thermal - LWIR uncooled microbolometer 640x480": {
        "name": "LWIR uncooled 640x480, 17 um",
        "imager_type": "uncooled",
        "basic": {"frame_rate": 30.0},
        "optics": {"D_mm": 50.0, "f_mm": 50.0, "tau_opt": 0.9},
        "detector": {"a_h_um": 16.0, "a_v_um": 16.0, "pitch_h_um": 17.0, "pitch_v_um": 17.0, "n_h": 640,
                     "n_v": 480, "uncooled_response": "flat", "cuton_um": 8.0, "cutoff_um": 14.0,
                     "noise_mode": "device", "netd_mK": 50.0, "t_th_ms": 10.0, "fpn_mode": "estimate",
                     "fpn_fraction": 0.5},
        "display": {"n_h": 800, "n_v": 600, "pitch_h_mm": 0.3, "pitch_v_mm": 0.3},
    },
    "Visible - CMOS daylight camera 1920x1080": {
        "name": "Visible CMOS 1920x1080",
        "category": "Visible", "imager_type": "staring",
        "basic": {"frame_rate": 50.0},
        "optics": {"D_mm": 25.0, "f_mm": 100.0, "lambda_diff_um": 0.55, "tau_opt": 0.85},
        "detector": {"a_h_um": 5.0, "a_v_um": 5.0, "pitch_h_um": 5.0, "pitch_v_um": 5.0, "n_h": 1920,
                     "n_v": 1080, "qe_preset": "CCD Silicon generic", "tint_mode": "direct", "tint_ms": 0.25,
                     "storage_e": 2.0e4, "dark_A": 3e-16, "noise_floor_e": 5.0, "lsb_e": 5.0,
                     "fpn_mode": "measured", "prnu_pct": 0.5, "dsnu_A": 4e-17},
        "display": {"n_h": 1920, "n_v": 1080, "pitch_h_mm": 0.3, "pitch_v_mm": 0.3, "luminance": 100.0,
                    "distance_cm": 60.0},
        "target": {"preset": "custom", "W_m": 2.3, "H_m": 2.3, "D_m": 6.0, "t_refl_mode": "spectral",
                   "t_refl_preset": "Olive green paint", "b_refl_mode": "spectral",
                   "b_refl_preset": "Dry grassland", "altitude_m": 0.0},
        "irradiance": {"mode": "single", "type": "broadband", "spectrum": "preset", "preset": "Direct sunlight",
                       "E_peak": 1239.0, "geometry": "fixed_space", "beta_h_deg": 30.0, "beta_v_deg": 45.0},
        "atmosphere": {"mode": "visibility", "atm": [_atm(True, 0.17, V=23.0, F_PR=0.2),
                                                       _atm(True, 0.78, V=5.0, F_PR=0.2),
                                                       _atm(False, 0.39, V=10.0, F_PR=0.2)]},
        "turbulence": {"on": True, "exposure": "short", "cn2_mode": "fixed", "cn2": 1e-14},
    },
    "Visible/SWIR - InGaAs night camera 640x512": {
        "name": "SWIR InGaAs 640x512",
        "category": "Visible", "imager_type": "staring",
        "basic": {"frame_rate": 30.0},
        "optics": {"D_mm": 75.0, "f_mm": 150.0, "lambda_diff_um": 1.3, "tau_opt": 0.85},
        "detector": {"a_h_um": 15.0, "a_v_um": 15.0, "pitch_h_um": 15.0, "pitch_v_um": 15.0,
                     "qe_preset": "InGaAs generic", "tint_mode": "direct", "tint_ms": 30.0,
                     "storage_e": 1.0e6, "dark_A": 2e-15, "noise_floor_e": 30.0, "lsb_e": 60.0,
                     "fpn_mode": "estimate", "fpn_fraction": 0.3},
        "display": {"n_h": 1280, "n_v": 1024, "luminance": 10.0},
        "target": {"preset": "custom", "W_m": 2.3, "H_m": 2.3, "D_m": 6.0, "t_refl_mode": "spectral",
                   "t_refl_preset": "Olive green paint", "b_refl_mode": "spectral",
                   "b_refl_preset": "Green grassland"},
        "irradiance": {"mode": "single", "type": "broadband", "spectrum": "preset", "preset": "Full moon",
                       "E_peak": 1.74e-3, "geometry": "extended"},
        "atmosphere": {"mode": "visibility", "atm": [_atm(True, 0.17, V=23.0, F_PR=0.1),
                                                       _atm(True, 0.78, V=5.0, F_PR=0.1),
                                                       _atm(False, 0.39, V=10.0, F_PR=0.1)]},
    },
    "General - MWIR sun-lit scene (emission + reflection)": {
        "name": "MWIR InSb, General category",
        "category": "General", "imager_type": "staring",
        "optics": {"D_mm": 50.0, "f_mm": 200.0, "lambda_diff_um": 4.0},
        "detector": {"qe_preset": "InSb MWIR generic", "storage_e": 7e6, "wellfill_pct": 60.0,
                     "noise_floor_e": 300.0, "lsb_e": 500.0, "fpn_mode": "estimate"},
        "target": {"preset": "custom", "W_m": 2.3, "H_m": 2.3, "D_m": 6.0, "dT_K": 5.0,
                   "t_emis_mode": "spectral", "t_emis_preset": "Olive green paint",
                   "b_emis_mode": "spectral", "b_emis_preset": "Green grassland"},
        "irradiance": {"mode": "single", "type": "broadband", "spectrum": "preset", "preset": "Direct sunlight",
                       "E_peak": 1239.0, "geometry": "fixed_space", "beta_h_deg": 30.0, "beta_v_deg": 45.0},
        "atmosphere": {"atm": [_atm(True, 0.2, 0.8, F_PR=0.05), _atm(True, 1.0, 0.8, F_PR=0.05),
                               _atm(False, 0.5, 0.8)]},
    },
    "NIIRS - airborne visible camera (slant path)": {
        "name": "Airborne visible camera, 3 km altitude",
        "category": "Visible", "imager_type": "staring",
        "mode": {"niirs": True, "stream": "still"},
        "optics": {"D_mm": 100.0, "f_mm": 500.0, "lambda_diff_um": 0.6, "tau_opt": 0.85},
        "detector": {"a_h_um": 5.5, "a_v_um": 5.5, "pitch_h_um": 5.5, "pitch_v_um": 5.5, "n_h": 4096,
                     "n_v": 3072, "qe_preset": "CCD Silicon generic", "tint_mode": "direct", "tint_ms": 0.2,
                     "storage_e": 3.0e4, "dark_A": 3e-16, "noise_floor_e": 5.0, "lsb_e": 8.0,
                     "fpn_mode": "measured"},
        "display": {"n_h": 4096, "n_v": 3072, "pitch_h_mm": 0.2, "pitch_v_mm": 0.2, "luminance": 100.0},
        "target": {"preset": "custom", "W_m": 2.3, "H_m": 2.3, "D_m": 6.0, "t_refl_mode": "spectral",
                   "t_refl_preset": "Olive green paint", "b_refl_mode": "spectral",
                   "b_refl_preset": "Dry grassland", "flight": "altitude", "altitude_m": 3000.0,
                   "alt_m": 1.0},
        "irradiance": {"mode": "single", "type": "broadband", "spectrum": "preset", "preset": "Direct sunlight",
                       "E_peak": 1239.0, "geometry": "fixed_space", "beta_h_deg": 20.0, "beta_v_deg": 50.0},
        "stab": {"random_on": True, "rand_h_mrad": 0.003, "rand_v_mrad": 0.003},
        "atmosphere": {"mode": "visibility", "atm": [_atm(True, 0.17, V=23.0, F_PR=0.15),
                                                       _atm(False, 0.78, V=5.0, F_PR=0.15),
                                                       _atm(False, 0.39, V=10.0, F_PR=0.15)]},
        "turbulence": {"on": True, "exposure": "short", "cn2_mode": "height", "cn2": 1e-13, "h_ref_m": 2.0,
                       "time": "day"},
    },
}


def make_template(name):
    """New project from a template.  The project name starts empty - the user enters it."""
    p = deep_merge(DEFAULT_PROJECT, TEMPLATES[name])
    p["name"] = ""
    return p
