"""Tkinter graphical user interface for the TRM4 model.

The parameter dialogs follow the structure of the "Modify Individual Parameters" dialog of the
TRM4 software (Chapter 2 of the documentation).  Results are shown in tabs: system performance
data, MTFs, AMOP, MTDP/MDSP (MCP), range performance, NIIRS and spectral data.
"""
import copy
import glob
import json
import math
import os
import re
import sys
import threading
import time
import traceback
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox, simpledialog

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib import cycler
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from . import presets as P
from .model import run_project, quick_estimate, ModelError, MODEL_VERSION, MODEL_REFERENCE, VALIDATION_VERSION
from . import report
from . import report_he
from . import scenario as SC
from . import zemax as Z
from . import imports as IM
from . import derived as DV
from . import profiles as PR
from . import analysis as AN
from . import advisor as ADV
from . import extensions as X
from . import labtools as LT
from . import atlas_news as NEWS
from .help_text import help_for
from . import __version__

APP_NAME = "TRM_HADMAAv1"
APP_TITLE = "TRM_HADMAAv1 Thermal Range Model"
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
PROJECT_DIR = os.path.dirname(HERE)
SETTINGS_FILE = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "TRM4", "settings.json")

# ---------------------------------------------------------------------------------------------
# Visual theme
# ---------------------------------------------------------------------------------------------
BG = "#eef1f5"            # window background / gaps
SURFACE = "#ffffff"       # cards, forms
SURFACE_ALT = "#f7f9fc"   # KPI cards, hover
BORDER = "#d7dde5"
TEXT = "#1d2433"
MUTED = "#6a7383"
ACCENT = "#1f6feb"
ACCENT_HOVER = "#1859c4"
ACCENT_SOFT = "#e8f0fe"
SIDEBAR = "#16202f"
SIDEBAR_HOVER = "#1f2c3f"
SIDEBAR_SEL = "#25344b"
SIDEBAR_TEXT = "#b9c4d4"
WARN = "#b54708"
OK = "#067647"
TASK_COLORS = ["#2563eb", "#ea580c", "#16a34a", "#dc2626", "#7c3aed"]
FONT = ("Segoe UI", 10)
FONT_SEMI = ("Segoe UI Semibold", 10)
ICON_FONT = None          # resolved at start-up (Segoe Fluent Icons / Segoe MDL2 Assets)

GLYPH = {"new": "", "open": "", "save": "", "export": "", "search": "",
         "run": "", "help": "", "info": "", "warn": "",
         "General": "", "Basic imager": "", "Optics": "", "Detector geometry": "",
         "Detector sensitivity": "", "Signal processing": "", "Display & observer": "",
         "Stabilization & MTFs": "", "Target & scenario": "", "Irradiance": "",
         "Atmosphere & turbulence": "", "Quick setup": "", "Camera profile": "", "Validation data": "", "Metadata": ""}

PAGE_INFO = {
    "Quick setup": "Camera profile, target, atmosphere and task - all other values come from the profile and "
                   "labelled presets",
    "Camera profile": "Select a camera and optical configuration; FOV, IFOV, Nyquist and F-number follow automatically",
    "Validation data": "Measured MTDP / MRTD / MCP, MTF / SFR and NETD with calibration metadata, compared with the "
                       "prediction",
    "General": "Project, imager category and modelling options",
    "Basic imager": "Frame rate, field of view, interlace, micro-scan and binning",
    "Optics": "Aperture, focal length, diffraction / aberrations or Zemax MTF, and transmission",
    "Detector geometry": "Detector shape, focal plane array layout, CTE and crosstalk",
    "Detector sensitivity": "Spectral response, noise, integration time and cold shield",
    "Signal processing": "Digital filters, electronic zoom and frame integration",
    "Display & observer": "Display panel, viewing geometry and eye model",
    "Stabilization & MTFs": "Line-of-sight stabilization errors and additional MTFs",
    "Target & scenario": "Target size and signature, background, geometry and tasks",
    "Irradiance": "Illumination source for reflective (Visible / General) bands",
    "Atmosphere & turbulence": "Atmospheric transmission and turbulence MTF",
    "Metadata": "Traceability of imported data, operating modes and processing (not used in the calculation)",
}

matplotlib.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "font.size": 9,
    "axes.titlesize": 10.5,
    "axes.titleweight": "semibold",
    "axes.titlelocation": "left",
    "axes.titlepad": 8,
    "axes.labelcolor": "#3b4556",
    "axes.edgecolor": "#a9b2bf",
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.prop_cycle": cycler(color=["#2563eb", "#ea580c", "#16a34a", "#dc2626", "#7c3aed", "#0891b2",
                                     "#db2777", "#65a30d", "#475569", "#ca8a04"]),
    "xtick.color": "#4b5565",
    "ytick.color": "#4b5565",
    "grid.color": "#c9d0da",
    "legend.frameon": True,
    "legend.framealpha": 0.9,
    "legend.edgecolor": "#e1e5eb",
    "legend.fontsize": 8,
    "lines.linewidth": 1.6,
    "figure.facecolor": SURFACE,
    "savefig.dpi": 200,
})


def apply_theme(root):
    """Flat, light ttk theme built on 'clam'."""
    global ICON_FONT
    fams = set(tkfont.families(root))
    ICON_FONT = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in fams), None)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            tkfont.nametofont(name).configure(family="Segoe UI", size=10)
        except tk.TclError:
            pass
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=SURFACE, foreground=TEXT, font=FONT, bordercolor=BORDER, lightcolor=SURFACE,
                darkcolor=SURFACE, troughcolor=BG, focuscolor=ACCENT, selectbackground=ACCENT,
                selectforeground="white", insertcolor=TEXT)
    s.configure("TFrame", background=SURFACE)
    s.configure("Bg.TFrame", background=BG)
    s.configure("TLabel", background=SURFACE, foreground=TEXT)
    s.configure("Muted.TLabel", foreground=MUTED)
    s.configure("Unit.TLabel", foreground=MUTED, font=("Segoe UI", 9))
    s.configure("Head.TLabel", foreground=ACCENT, font=("Segoe UI Semibold", 10))
    s.configure("PageTitle.TLabel", font=("Segoe UI Semibold", 15))
    s.configure("PageSub.TLabel", foreground=MUTED, font=("Segoe UI", 9))
    s.configure("Status.TFrame", background=BG)
    s.configure("Status.TLabel", background=BG, foreground="#4a5262", font=("Segoe UI", 9))
    s.configure("TEntry", fieldbackground=SURFACE, bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE,
                padding=(6, 3))
    s.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)])
    s.configure("TCombobox", fieldbackground=SURFACE, background=SURFACE, bordercolor=BORDER, arrowcolor=MUTED,
                lightcolor=SURFACE, darkcolor=SURFACE, padding=(6, 3))
    s.map("TCombobox", fieldbackground=[("readonly", SURFACE)], selectbackground=[("readonly", SURFACE)],
          selectforeground=[("readonly", TEXT)], bordercolor=[("focus", ACCENT), ("hover", "#aab4c2")],
          background=[("active", SURFACE_ALT)])
    root.option_add("*TCombobox*Listbox.font", FONT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "white")
    s.configure("TButton", background=SURFACE, bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE,
                padding=(12, 5), focusthickness=0)
    s.map("TButton", background=[("pressed", "#e3e8ef"), ("active", SURFACE_ALT)],
          bordercolor=[("active", "#aab4c2")])
    s.configure("Accent.TButton", background=ACCENT, foreground="white", bordercolor=ACCENT, lightcolor=ACCENT,
                darkcolor=ACCENT, font=FONT_SEMI)
    s.map("Accent.TButton", background=[("disabled", "#9db8e8"), ("pressed", ACCENT_HOVER), ("active", ACCENT_HOVER)],
          bordercolor=[("active", ACCENT_HOVER)], foreground=[("disabled", "white")])
    s.configure("TCheckbutton", background=SURFACE, indicatorbackground=SURFACE, indicatorforeground="white",
                indicatormargin=(0, 0, 6, 0), focusthickness=0, indicatorsize=int(14 * dpi_scale(root)))
    s.map("TCheckbutton", indicatorbackground=[("selected", ACCENT), ("active", ACCENT_SOFT)],
          background=[("active", SURFACE)])
    s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(8, 6, 8, 0))
    s.configure("TNotebook.Tab", background=BG, foreground=MUTED, padding=(8, 6), bordercolor=BG,
                lightcolor=BG, font=("Segoe UI", 9))
    s.map("TNotebook.Tab", background=[("selected", SURFACE), ("active", "#e4e8ee")],
          foreground=[("selected", ACCENT)], lightcolor=[("selected", ACCENT)])
    s.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, rowheight=int(26 * dpi_scale(root)),
                bordercolor=BORDER, font=FONT)
    s.map("Treeview", background=[("selected", ACCENT_SOFT)], foreground=[("selected", TEXT)])
    s.configure("Treeview.Heading", background=BG, foreground="#3b4556", font=FONT_SEMI, relief="flat",
                padding=(6, 5), bordercolor=BORDER)
    s.map("Treeview.Heading", background=[("active", "#e4e8ee")])
    s.configure("TProgressbar", background=ACCENT, troughcolor="#dde3ea", bordercolor=BG, lightcolor=ACCENT,
                darkcolor=ACCENT, thickness=6)
    s.configure("TScrollbar", background="#cfd6df", troughcolor=SURFACE, bordercolor=SURFACE, arrowcolor=MUTED,
                lightcolor="#cfd6df", darkcolor="#cfd6df", gripcount=0, arrowsize=12)
    s.map("TScrollbar", background=[("active", "#b3bcc8")])
    s.configure("TPanedwindow", background=BG)
    s.configure("Sash", sashthickness=6, gripcount=0, background=BG, lightcolor=BG, bordercolor=BG)
    s.configure("TSeparator", background=BORDER)
    root.configure(background=BG)


def autowrap(label, margin=8):
    """Let a packed/gridded label wrap at its current width."""
    label.bind("<Configure>", lambda e: label.configure(wraplength=max(e.width - margin, 50)), add="+")
    return label


def dpi_scale(widget):
    try:
        return max(1.0, widget.winfo_fpixels("1i") / 96.0)
    except tk.TclError:
        return 1.0


def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except OSError:
        pass


def find_documentation():
    hits = sorted(glob.glob(os.path.join(PROJECT_DIR, "TRM4*Documentation*.pdf")))
    return hits[0] if hits else None

THERMAL = lambda p: p["category"] == "Thermal"
VISIBLE = lambda p: p["category"] == "Visible"
GENERAL = lambda p: p["category"] == "General"
NOT_THERMAL = lambda p: p["category"] != "Thermal"
COOLED = lambda p: p["category"] != "Thermal" or p["imager_type"] == "cooled"
UNCOOLED = lambda p: p["category"] == "Thermal" and p["imager_type"] == "uncooled"
RADIOMETRIC = lambda p: COOLED(p) and not (THERMAL(p) and p["detector"]["noise_mode"] == "measured")
ALWAYS = lambda p: True
NEVER = lambda p: False
OPT_FILE = lambda p: p["optics"].get("mtf_source") in ("zemax", "measured", "device")
OPT_LENS = lambda p: p["optics"].get("mtf_source") in ("zemax", "measured")
OPT_MODEL = lambda p: not OPT_FILE(p)
FIELD = lambda p: p["mode"]["environment"] == "field"
JIT_MEAS = lambda p: p["stab"].get("jitter_mode") == "measured" and not p["stab"]["neglect"]
JIT_PSD = lambda p: p["stab"].get("jitter_mode") == "psd" and not p["stab"]["neglect"]
JIT_MODEL = lambda p: p["stab"].get("jitter_mode", "model") == "model" and not p["stab"]["neglect"]
SPEC_ATM = lambda p: p["atmosphere"]["mode"] == "spectral"
CAM_NETD = lambda p: THERMAL(p) and (p["detector"]["noise_mode"] == "measured" and p["imager_type"] == "cooled" or
                                     UNCOOLED(p) and p["detector"]["noise_mode"] == "device")
ALGO = lambda p: p["display"].get("observer", "legacy") == "algorithm"
POT = lambda p: ALGO(p) and p["display"].get("algo_criterion", "lp") == "pot"
TTP = lambda p: bool(p["target"].get("ttp")) and not POT(p)
TONE = lambda p: p["dsp"].get("tone_mode", "none") != "none"
WEATHER = lambda p: p["atmosphere"]["mode"] == "weather"
# turbulence acts outside the Thermal category (TRM4) and, as an extension, in it
TURB_CAT = lambda p: NOT_THERMAL(p) or p["turbulence"].get("thermal", False)
TURB_ON = lambda p: TURB_CAT(p) and p["turbulence"]["on"]
R0_MODE = lambda p: p["turbulence"]["cn2_mode"] == "r0"
ATM_DOC = lambda p: SPEC_ATM(p) or NOT_THERMAL(p) and p["atmosphere"].get("path_mode") == "import"
# the target depth is seen only from the side / diagonal or on an oblique line of sight (Eqs. 3.81-3.84)
TARGET_DEPTH = lambda p: p["target"]["aspect"] != "front" or (
    p["target"]["flight"] == "angle" and p["target"]["angle_deg"] != 0 or
    p["target"]["flight"] == "altitude" and p["target"]["altitude_m"] != 0)

# Parameter levels (roadmap Section 01 disposition rules):
#   base     KEEP / SIMPLIFY  - always shown in the Engineering workflow
#   adv      ADVANCED         - shown with "Show advanced parameters", or when the feature is in use
#   legacy   REMOVE           - outside the normal product scope; only shown while a project still uses it


_SQUARE = (("pitch_h_um", "pitch_v_um"), ("a_h_um", "a_v_um"))


def square_pixels(det):
    """Square-pixel state of a project: vertical pitch and active size equal the horizontal ones."""
    return all(float(det[h]) == float(det[v]) for h, v in _SQUARE)


def apply_square(p):
    """Square pixels: the vertical pitch and active size follow the horizontal entries (one input per pair)."""
    d = p["detector"]
    if d.get("square"):
        for h, v in _SQUARE:
            d[v] = d[h]
    return p


def F(path, label, kind="float", opts=None, cond=ALWAYS, unit="", level=None):
    return {"path": path, "label": label, "kind": kind, "opts": opts, "cond": cond, "unit": unit, "level": level}


def H(text, cond=ALWAYS, level="base", active=NEVER):
    """Group header.  Fields below inherit its level; `active(p)` = the group's feature is in use."""
    return {"kind": "header", "label": text, "cond": cond, "level": level, "active": active}


def D():
    """Read-only panel with the automatically calculated (dependent) values."""
    return {"kind": "derived", "cond": ALWAYS, "level": "base"}


CATEGORY = [("Thermal", "Thermal (blackbody emissivity only)"), ("Visible", "Visible/NIR/SWIR (reflectivity only)"),
            ("General", "General (reflectivity + emissivity)")]
FREQ_UNITS = [("mrad", "cycles/mrad (object space)"), ("mm", "cycles/mm (focal plane)"), ("pixel", "cycles/pixel")]


def _atm_rows():
    out = []
    for i in range(3):
        on = (lambda i=i: lambda p: p["atmosphere"]["atm"][i]["on"] and not SPEC_ATM(p))()
        out += [F("atmosphere.atm.%d.on" % i, "Atmosphere %d" % (i + 1), "bool", cond=lambda p: not SPEC_ATM(p)),
                F("atmosphere.atm.%d.sigma" % i, "  extinction coefficient", unit="1/km",
                  cond=(lambda on=on: lambda p: on(p) and not WEATHER(p) and
                        not (VISIBLE(p) and p["atmosphere"]["mode"] == "visibility"))()),
                F("atmosphere.atm.%d.V_km" % i, "  visual range", unit="km",
                  cond=(lambda on=on: lambda p: on(p) and (WEATHER(p) or VISIBLE(p) and
                                                           p["atmosphere"]["mode"] == "visibility"))()),
                F("atmosphere.atm.%d.rh_pct" % i, "  relative humidity", unit="%",
                  cond=(lambda on=on: lambda p: on(p) and WEATHER(p))()),
                F("atmosphere.atm.%d.tau0" % i, "  initial transmission", cond=on),
                F("atmosphere.atm.%d.T_air_K" % i, "  air temperature", unit="K",
                  cond=(lambda on=on: lambda p: on(p) and (GENERAL(p) or WEATHER(p)))()),
                F("atmosphere.atm.%d.F_PR" % i, "  path radiance factor",
                  cond=(lambda on=on: lambda p: on(p) and NOT_THERMAL(p) and p["atmosphere"].get("path_mode") != "import")())]
    return out


TABS = [
    ("General", [
        H("Project"),
        F("name", "Project name", "text"),
        F("category", "Imager category / sensing band", "choice", CATEGORY),
        F("imager_type", "Imager type (Thermal)", "choice",
          [("cooled", "Cooled staring FPA (photon detector)"), ("uncooled", "Uncooled FPA (microbolometer)")], THERMAL),
        H("Modelling (Sec. 2.4)"),
        F("mode.environment", "Field / Lab", "choice", [("field", "Field performance"),
                                                        ("lab", "Laboratory performance")]),
        F("mode.ref_range_km", "Reference range (MTF/MDSP)", "float", cond=lambda p: NOT_THERMAL(p) and FIELD(p),
          unit="km"),
        F("mode.stream", "Video / Still", "choice", [("video", "Video (eye integration)"), ("still", "Still (single frame)")]),
        H("Aerial image interpretability", cond=FIELD, level="adv", active=lambda p: p["mode"]["niirs"]),
        F("mode.niirs", "Calculate NIIRS (GIQE 5)", "bool", cond=FIELD),
    ]),
    ("Basic imager", [
        H("Frame rate (Sec. 2.5)"),
        F("basic.frame_rate", "Frame rate", unit="Hz"),
        H("FOV cross-check (measured FOV, not used)", level="adv",
          active=lambda p: p["basic"]["fov_mode"] == "measured"),
        F("basic.fov_mode", "FOV", "choice", [("calculate", "Calculate FOV"), ("measured", "Measured FOV (cross-check)")]),
        F("basic.fov_h_deg", "Measured horizontal FOV", cond=lambda p: p["basic"]["fov_mode"] == "measured", unit="deg"),
        F("basic.fov_v_deg", "Measured vertical FOV", cond=lambda p: p["basic"]["fov_mode"] == "measured", unit="deg"),
        H("Micro-scan / dither", level="adv", active=lambda p: p["basic"]["microscan"] != "none"),
        F("basic.microscan", "Micro-scan / dither", "choice",
          [("none", "None"), ("rectangular", "Rectangular"), ("circular", "Circular (2x2)"), ("diagonal", "Diagonal")]),
        F("basic.ms_steps_h", "Horizontal steps", "int", cond=lambda p: p["basic"]["microscan"] == "rectangular"),
        F("basic.ms_steps_v", "Vertical steps", "int", cond=lambda p: p["basic"]["microscan"] == "rectangular"),
        F("basic.integ_during_move", "Integration during movement", "bool",
          cond=lambda p: p["basic"]["microscan"] != "none"),
        H("Pixel binning / sensors", level="adv",
          active=lambda p: p["basic"]["bin_h"] > 1 or p["basic"]["bin_v"] > 1 or p["basic"]["n_sensors"] != 1),
        F("basic.bin_h", "Binned pixels horizontal", "int"),
        F("basic.bin_v", "Binned pixels vertical", "int"),
        F("basic.n_sensors", "Number of identical sensors", "choice", [(1, "One"), (2, "Two")]),
        F("basic.bin_kind", "Binning type", "choice", [("charge", "Charge / hardware binning (one read-out)"),
                                                       ("digital", "Digital binning (sum of read-outs)")],
          cond=lambda p: p["basic"]["bin_h"] > 1 or p["basic"]["bin_v"] > 1),
        H("Readout / exposure timing (exposure = integration time on 'Detector sensitivity', shared with the motion "
          "model)", level="adv",
          active=lambda p: p["basic"].get("readout", "global") != "global" or not p["basic"].get("exp_overlap", True)
          or p["basic"].get("guard_ms", 0) > 0 or p["basic"].get("exp_min_ms", 0) > 0 or
          p["basic"].get("exp_max_ms", 0) > 0),
        F("basic.readout", "Readout mode", "choice", [("global", "Global shutter"), ("rolling", "Rolling shutter")]),
        F("basic.exp_overlap", "Exposure may overlap the readout of the previous frame", "bool"),
        F("basic.readout_ms", "Frame readout time (row 1 to last row)", unit="ms",
          cond=lambda p: p["basic"].get("readout") == "rolling" or not p["basic"].get("exp_overlap", True)),
        F("basic.guard_ms", "Guard / trigger dead time per frame", unit="ms"),
        F("basic.exp_min_ms", "Hardware minimum exposure (0 = not specified)", unit="ms"),
        F("basic.exp_max_ms", "Hardware maximum exposure (0 = not specified)", unit="ms"),
        H("Interlace (legacy video - not used by staring digital cameras)", level="legacy",
          active=lambda p: p["basic"]["interlace"] != "progressive"),
        F("basic.interlace", "Electronic interlace", "choice",
          [("progressive", "No interlace - progressive scan"), ("electronic", "Electronic interlace"),
           ("pseudo", "Pseudo interlace")]),
    ]),
    ("Optics", [
        H("Aperture and focal length (Sec. 2.6)"),
        F("optics.aperture", "Aperture specified by", "choice", [("circular", "Clear aperture diameter D"),
                                                                ("general", "F-number")]),
        F("optics.D_mm", "Aperture diameter D (0 = rectangular)", cond=lambda p: p["optics"]["aperture"] != "general", unit="mm"),
        F("optics.F_general", "Effective F-number", cond=lambda p: p["optics"]["aperture"] == "general"),
        F("optics.f_mm", "Focal length", unit="mm"),
        H("Pupil geometry", cond=lambda p: p["optics"]["aperture"] != "general", level="adv",
          active=lambda p: p["optics"]["D_obsc_mm"] > 0 or p["optics"]["W_trunc_h_mm"] > 0 or p["optics"]["W_trunc_v_mm"] > 0),
        F("optics.D_obsc_mm", "Central obscuration diameter", cond=lambda p: p["optics"]["aperture"] != "general", unit="mm"),
        F("optics.W_trunc_h_mm", "Width of truncated aperture (0 = none)", cond=lambda p: p["optics"]["aperture"] != "general", unit="mm"),
        F("optics.W_trunc_v_mm", "Height of truncated aperture (0 = none)", cond=lambda p: p["optics"]["aperture"] != "general", unit="mm"),
        H("Anamorphic optics / cross-check", level="adv",
          active=lambda p: p["optics"]["diff_focal"] or p["optics"].get("F_spec", 0) > 0),
        F("optics.diff_focal", "Different focal length vertical", "bool"),
        F("optics.f_v_mm", "Vertical focal length", cond=lambda p: p["optics"]["diff_focal"], unit="mm"),
        F("optics.F_spec", "Manufacturer F-number (0 = none)"),
        H("Optical MTF - data precedence"),
        F("optics.mtf_source", "Optical MTF source", "choice",
          [("model", "A: Theoretical (diffraction + aberration)"),
           ("zemax", "B: Zemax CSV (design lens MTF)"),
           ("measured", "B: Measured lens MTF (CSV)"),
           ("device", "C: Measured device prefilter MTF (optics + detector, end-to-end)")]),
        F("optics.zemax_mtf", "MTF data file (.csv/.txt)", "file",
          {"check": Z.mtf_summary, "title": "Import optics / device MTF data"}, cond=OPT_FILE),
        F("optics.zemax_mtf_unit", "Spatial frequency in file", "choice",
          [("auto", "As stated in the file (error if not stated)"), ("mm", "cycles/mm (image space)"),
           ("mrad", "cycles/mrad (object space, afocal)")], cond=OPT_FILE),
        F("optics.zemax_mtf_field", "Field number to use (1 = first)", "int", cond=OPT_FILE),
        F("optics.zemax_mtf_h", "Horizontal MTF uses", "choice",
          [("sagittal", "Sagittal (vertical = tangential)"), ("tangential", "Tangential (vertical = sagittal)")],
          cond=OPT_FILE),
        H("Description of the data: page 'Metadata'", cond=OPT_FILE),
        H("Component coverage of the imported MTF (no double counting)", cond=OPT_FILE),
        F("optics.mtf_incl_diffraction", "Data include diffraction (else computed and applied once)", "bool",
          cond=OPT_FILE),
        F("optics.mtf_incl_detector", "Data include the detector aperture (camera end-to-end)", "bool", cond=OPT_LENS),
        F("optics.mtf_incl_motion", "Data include image motion (stabilization inputs then ignored)", "bool",
          cond=OPT_FILE),
        H("Diffraction and aberration model", cond=OPT_MODEL, level="adv",
          active=lambda p: p["optics"]["aberration"] != "none" or p["optics"]["diffraction"] != "spectral"),
        F("optics.diffraction", "Diffraction MTF", "choice", [("spectral", "Automatic spectral weighting"),
                                                             ("single", "Single wavelength")], cond=OPT_MODEL),
        F("optics.lambda_diff_um", "Wavelength for diffraction (0 = band mean)",
          cond=lambda p: OPT_MODEL(p) and p["optics"]["diffraction"] == "single", unit="um"),
        F("optics.aberration", "Aberration (approximation)", "choice", [("none", "No aberration"),
                                                                        ("q", "Aberration parameter q"),
                                                                        ("blur", "Gaussian blur")], cond=OPT_MODEL),
        F("optics.q", "Aberration parameter q (>1)", cond=lambda p: OPT_MODEL(p) and p["optics"]["aberration"] == "q"),
        F("optics.blur_um", "Gaussian blur sigma", cond=lambda p: OPT_MODEL(p) and p["optics"]["aberration"] == "blur", unit="um"),
        H("Transmission"),
        F("optics.tau_mode", "Optics transmission", "choice", [("value", "Peak transmission value"),
                                                              ("zemax", "Spectral curve from file (.csv/.txt)")]),
        F("optics.tau_opt", "Peak transmission optics (w/o obscuration)"),
        F("optics.zemax_tau", "Transmission vs. wavelength", "file",
          {"check": Z.transmission_summary, "title": "Import optics transmission data"},
          cond=lambda p: p["optics"].get("tau_mode") == "zemax"),
        F("optics.tau_kind", "Values in file are", "choice", [("absolute", "Absolute transmission"),
                                                              ("normalized", "Normalized (x peak value above)")],
          cond=lambda p: p["optics"].get("tau_mode") == "zemax"),
        F("optics.tau_scope", "File covers", "choice", [("optics", "Optics only (filter applied separately)"),
                                                        ("system", "Full optical train incl. filter / window")],
          cond=lambda p: p["optics"].get("tau_mode") == "zemax"),
        F("optics.tau_filter", "Transmission additional filter",
          cond=lambda p: not (p["optics"].get("tau_mode") == "zemax" and p["optics"].get("tau_scope") == "system")),
        H("Field-edge throughput (ranges use the on-axis paraxial irradiance)", level="adv",
          active=lambda p: p["optics"].get("rel_illum", 1.0) < 1.0),
        F("optics.rel_illum", "Relative illumination at the field edge (vignetting x cos^4, 1 = none)"),
    ]),
    ("Detector geometry", [
        H("Focal plane array (Sec. 2.9)"),
        F("detector.n_h", "Number of horizontal detectors (sets the FOV, not the resolution)", "int"),
        F("detector.n_v", "Number of vertical detectors (sets the FOV, not the resolution)", "int"),
        F("detector.square", "Square pixels (vertical pitch and active size = horizontal)", "bool"),
        F("detector.pitch_h_um", "Detector pitch (horizontal)", unit="um"),
        F("detector.pitch_v_um", "Vertical detector pitch", cond=lambda p: not p["detector"].get("square"), unit="um"),
        F("detector.a_h_um", "Active size (horizontal)", cond=lambda p: p["detector"]["shape"] in ("rectangular", "rhombic"), unit="um"),
        F("detector.a_v_um", "Vertical active size", cond=lambda p: p["detector"]["shape"] in ("rectangular", "rhombic") and
          not p["detector"].get("square"), unit="um"),
        H("Detector shape", level="adv", active=lambda p: p["detector"]["shape"] != "rectangular"),
        F("detector.shape", "Detector shape", "choice", [("rectangular", "Rectangular"), ("rhombic", "Rhombic"),
                                                        ("circular", "Circular"), ("loophole", "Circular with loop-hole")]),
        F("detector.d_um", "Detector diameter (active)", cond=lambda p: p["detector"]["shape"] in ("circular", "loophole"), unit="um"),
        F("detector.d_hole_um", "Diameter of hole", cond=lambda p: p["detector"]["shape"] == "loophole", unit="um"),
        H("Charge transfer efficiency (CCD, legacy)", level="legacy", active=lambda p: p["detector"]["cte_on"]),
        F("detector.cte_on", "Charge transfer efficiency", "bool"),
        F("detector.cte_h", "Horizontal CTE", cond=lambda p: p["detector"]["cte_on"]),
        F("detector.ntr_h", "Number of horizontal transfers", "int", cond=lambda p: p["detector"]["cte_on"]),
        F("detector.cte_v", "Vertical CTE", cond=lambda p: p["detector"]["cte_on"]),
        F("detector.ntr_v", "Number of vertical transfers", "int", cond=lambda p: p["detector"]["cte_on"]),
        H("Crosstalk", level="adv", active=lambda p: p["detector"]["xtalk_h"] > 0 or p["detector"]["xtalk_v"] > 0),
        F("detector.xtalk_h", "Horizontal MTF at Nyquist (0 = off)"),
        F("detector.xtalk_v", "Vertical MTF at Nyquist (0 = off)"),
    ]),
    ("Detector sensitivity", [
        H("Spectral response"),
        F("detector.uncooled_response", "Spectral response", "choice", [("flat", "Flat response"),
                                                                        ("preset", "Preset / custom QE data")], UNCOOLED),
        F("detector.cuton_um", "Cut-on wavelength", cond=lambda p: UNCOOLED(p) and p["detector"]["uncooled_response"] == "flat", unit="um"),
        F("detector.cutoff_um", "Cut-off wavelength", cond=lambda p: UNCOOLED(p) and p["detector"]["uncooled_response"] == "flat", unit="um"),
        F("detector.qe_preset", "Spectral quantum efficiency", "choice", [(n, n) for n in P.QE_NAMES],
          cond=lambda p: not UNCOOLED(p) or p["detector"]["uncooled_response"] == "preset"),
        F("detector.qe_scale", "QE scale factor", cond=lambda p: not UNCOOLED(p) or p["detector"]["uncooled_response"] == "preset"),
        F("detector.qe_custom", "Custom QE: 'lambda QE' per line", "multiline",
          cond=lambda p: p["detector"]["qe_preset"] == "Custom" and (not UNCOOLED(p) or p["detector"]["uncooled_response"] == "preset")),
        F("detector.qe_unit", "Custom QE values are", "choice", [("auto", "Auto (<= 1 means fraction)"),
                                                                 ("percent", "Percent"), ("fraction", "Fraction")],
          cond=lambda p: p["detector"]["qe_preset"] == "Custom" and (not UNCOOLED(p) or p["detector"]["uncooled_response"] == "preset")),
        F("detector.qe_basis", "QE refers to", "choice",
          [("unspecified", "Not stated (TRM: active area)"), ("active_area", "Active area (intrinsic QE)"),
           ("pixel_area", "Full pixel area (total / EMVA 1288 QE, incl. fill factor)")], COOLED),
        H("Temporal noise / NETD"),
        F("detector.noise_mode", "Noise / sensitivity source", "choice",
          [("calculated", "Physics model (detector noise sources)"), ("measured", "Measured camera NETD")],
          cond=lambda p: THERMAL(p) and p["imager_type"] == "cooled"),
        F("detector.noise_mode", "Noise / sensitivity source", "choice",
          [("device", "Measured camera NETD"), ("detector", "Detector-level NETD (scaled to this optics)")], UNCOOLED),
        F("detector.netd_mK", "NETD", cond=lambda p: THERMAL(p) and (UNCOOLED(p) or p["detector"]["noise_mode"] == "measured"), unit="mK"),
        F("detector.netd_TB_K", "NETD test temperature (0 = not documented)", unit="K",
          cond=lambda p: THERMAL(p) and (p["detector"]["noise_mode"] in ("measured", "device"))),
        F("detector.t_th_ms", "Detector thermal time constant", cond=UNCOOLED, unit="ms"),
        F("detector.noise_floor_e", "Read noise (additive floor)", cond=RADIOMETRIC, unit="e-"),
        H("Camera NETD test conditions (replaces the detector noise model - nothing is added on top)", cond=CAM_NETD),
        F("detector.netd_F", "Test F-number (0 = not documented)", cond=CAM_NETD),
        F("detector.netd_tint_ms", "Test integration time (0 = not documented)", unit="ms",
          cond=lambda p: CAM_NETD(p) and COOLED(p)),
        F("detector.netd_frames", "Frames averaged in the test", "int", cond=CAM_NETD),
        F("detector.noise_port", "Measurement port", "choice", [("raw", "RAW (before NUC)"), ("post_nuc", "After NUC"),
                                                                 ("processed", "Processed video output")], CAM_NETD),
        H("NETD measurement conditions (detector-level NETD)", cond=lambda p: UNCOOLED(p) and p["detector"]["noise_mode"] == "detector"),
        F("detector.meas_F", "Measurement F-number (0 = project)", cond=lambda p: UNCOOLED(p) and p["detector"]["noise_mode"] == "detector"),
        F("detector.meas_tau", "Measurement transmission (0 = project)", cond=lambda p: UNCOOLED(p) and p["detector"]["noise_mode"] == "detector"),
        F("detector.meas_TB_K", "Measurement BB temperature (0 = project)", cond=lambda p: UNCOOLED(p) and p["detector"]["noise_mode"] == "detector", unit="K"),
        F("detector.readout_mK", "Read-out (floor) noise", cond=lambda p: UNCOOLED(p) and p["detector"]["noise_mode"] == "detector", unit="mK"),
        H("Integration time / exposure", cond=COOLED),
        F("detector.tint_mode", "Integration time via", "choice", [("direct", "Direct specification"),
                                                                  ("duty", "Integration duty cycle"), ("wellfill", "Well fill")], COOLED),
        F("detector.tint_ms", "Integration time", cond=lambda p: COOLED(p) and p["detector"]["tint_mode"] == "direct", unit="ms"),
        F("detector.duty", "Integration duty cycle", cond=lambda p: COOLED(p) and p["detector"]["tint_mode"] == "duty"),
        F("detector.wellfill_pct", "Well fill (of the usable capacity)", cond=lambda p: COOLED(p) and p["detector"]["tint_mode"] == "wellfill", unit="%"),
        H("Operating point and saturation capacity (one gain / readout / temperature mode)", cond=COOLED),
        F("detector.storage_e", "Full well (storage) capacity", cond=COOLED, unit="carriers"),
        F("detector.cap_node", "Capacity above refers to", "choice",
          [("unknown", "Not stated (generic)"), ("pixel", "Physical pixel full well"),
           ("roic", "ROIC integration capacitor / storage node"),
           ("camera", "Camera saturation capacity (input-referred, measured)")], COOLED),
        F("detector.sat_e", "Camera saturation capacity, input-referred (0 = unknown)", cond=COOLED, unit="e-"),
        H("Exposure budget: saturation, timing, motion and SNR checked together", cond=COOLED, level="adv",
          active=lambda p: p["detector"].get("snr_req", 0) > 0),
        F("detector.fill_limit_pct", "Permitted fill of the usable capacity (design margin)", cond=COOLED, unit="%"),
        F("detector.bright_refl", "Brightest credible scene reflectivity", cond=lambda p: COOLED(p) and NOT_THERMAL(p)),
        F("detector.bright_dT_K", "Brightest credible scene temperature above background", unit="K",
          cond=lambda p: COOLED(p) and not VISIBLE(p)),
        F("detector.snr_req", "Required pixel SNR (0 = not checked)", cond=COOLED),
        H("Charge-based noise sources and dark current", cond=RADIOMETRIC, level="adv",
          active=lambda p: p["detector"]["electron_gain"] != 1 or p["detector"]["noise_figure"] != 1 or
          p["detector"].get("dark_mode", "value") != "value"),
        F("detector.electron_gain", "Electron gain", cond=RADIOMETRIC),
        F("detector.dark_mode", "Dark current via", "choice", [("value", "Single value"),
                                                              ("table", "Calibrated table vs sensor temperature")],
          RADIOMETRIC),
        F("detector.dark_A", "Dark current", cond=lambda p: RADIOMETRIC(p) and p["detector"].get("dark_mode", "value") == "value",
          unit="A"),
        F("detector.dark_table", "Dark current table: 'T_sensor[K] I_dark[A]' per line", "multiline",
          cond=lambda p: RADIOMETRIC(p) and p["detector"].get("dark_mode") == "table"),
        F("detector.T_sensor_K", "Sensor operating temperature", unit="K",
          cond=lambda p: RADIOMETRIC(p) and p["detector"].get("dark_mode") == "table"),
        F("detector.noise_figure", "Noise figure (multiplicative)", cond=RADIOMETRIC),
        H("ADC resolution", level="adv", active=lambda p: p["detector"].get("adc_mode", "none") != "none"),
        F("detector.adc_mode", "ADC quantization noise", "choice", [("none", "Not specified"), ("carriers", "LSB in carriers"),
                                                                   ("mK", "LSB in temperature (Thermal)")]),
        F("detector.lsb_e", "LSB", cond=lambda p: p["detector"]["adc_mode"] == "carriers", unit="carriers"),
        F("detector.lsb_mK", "LSB", cond=lambda p: p["detector"]["adc_mode"] == "mK", unit="mK"),
        F("detector.adc_bits", "ADC bits (0 = no clipping check)", "int", cond=lambda p: p["detector"]["adc_mode"] == "carriers"),
        H("Cold shield / internal radiation", cond=lambda p: (GENERAL(p) or THERMAL(p)) and RADIOMETRIC(p), level="adv",
          active=lambda p: p["detector"]["cs_mode"] == "fnumber" or p["detector"]["cs_eff"] < 1 or
          p["detector"]["T_off_dev_K"] != 0 or p["detector"]["T_off_opt_K"] != 0),
        F("detector.T_off_dev_K", "Temperature offset device-background", cond=lambda p: (GENERAL(p) or THERMAL(p)) and RADIOMETRIC(p), unit="K"),
        F("detector.T_off_opt_K", "Temperature offset optics-background", cond=lambda p: (GENERAL(p) or THERMAL(p)) and RADIOMETRIC(p), unit="K"),
        F("detector.T_cs_K", "Cold shield temperature", cond=lambda p: (GENERAL(p) or THERMAL(p)) and RADIOMETRIC(p), unit="K"),
        F("detector.cs_mode", "Cold shield definition via", "choice", [("efficiency", "Cold shield efficiency"),
                                                                       ("fnumber", "Effective F-number")],
          cond=lambda p: (GENERAL(p) or THERMAL(p)) and RADIOMETRIC(p)),
        F("detector.cs_eff", "Cold shield efficiency", cond=lambda p: (GENERAL(p) or THERMAL(p)) and RADIOMETRIC(p) and p["detector"]["cs_mode"] == "efficiency"),
        F("detector.cs_F", "Cold shield effective F-number", cond=lambda p: (GENERAL(p) or THERMAL(p)) and RADIOMETRIC(p) and p["detector"]["cs_mode"] == "fnumber"),
        H("Measured noise power spectrum (quality check, not used for the ranges)", level="adv",
          active=lambda p: bool((p["detector"].get("nps_file") or {}).get("text"))),
        F("detector.nps_file", "NPS file ('f NPS' or 'f h v')", "file",
          {"check": IM.curve_summary, "title": "Import measured noise power spectrum"}),
        F("detector.nps_unit", "Frequency unit", "choice", FREQ_UNITS),
        F("detector.nps_stage", "Measured", "choice", [("raw", "Before processing (raw / after NUC)"),
                                                        ("processed", "After processing (delivered image)")]),
        H("Fixed pattern (spatial) noise - not the same as temporal noise", level="adv",
          active=lambda p: p["detector"]["fpn_mode"] != "none"),
        F("detector.fpn_mode", "Fixed pattern noise", "choice", [("none", "No noise"), ("measured", "Measured"),
                                                                ("estimate", "Estimate (fraction of NETD/NES)")]),
        F("detector.ietd_mK", "IETD", cond=lambda p: THERMAL(p) and p["detector"]["fpn_mode"] == "measured", unit="mK"),
        F("detector.prnu_pct", "PRNU", cond=lambda p: NOT_THERMAL(p) and p["detector"]["fpn_mode"] == "measured", unit="%"),
        F("detector.dsnu_A", "DSNU", cond=lambda p: NOT_THERMAL(p) and p["detector"]["fpn_mode"] == "measured", unit="A"),
        F("detector.fpn_fraction", "Fraction of NETD / NES", cond=lambda p: p["detector"]["fpn_mode"] == "estimate"),
    ]),
    ("Signal processing", [
        H("Frame integration (Sec. 2.15)"),
        F("dsp.frames_on", "Simple frame averaging", "bool"),
        F("dsp.n_frames", "Number of averaged frames", "int", cond=lambda p: p["dsp"]["frames_on"]),
        F("dsp.iir_on", "IIR frame integration filter", "bool"),
        F("dsp.iir_alpha", "Alpha", cond=lambda p: p["dsp"]["iir_on"]),
        H("Digital filter (sharpening / smoothing)", level="adv", active=lambda p: p["dsp"]["filter_on"]),
        F("dsp.filter_on", "Digital filter", "bool"),
        F("dsp.filter_dir", "Direction", "choice", [("both", "Both directions"), ("h", "Horizontal only"), ("v", "Vertical only")],
          cond=lambda p: p["dsp"]["filter_on"]),
        F("dsp.h_type", "Horizontal filter type", "choice", [("odd", "Odd"), ("even", "Even")], cond=lambda p: p["dsp"]["filter_on"]),
        F("dsp.h_coef", "Horizontal coefficients c0..c4", "list", cond=lambda p: p["dsp"]["filter_on"]),
        F("dsp.v_type", "Vertical filter type", "choice", [("odd", "Odd"), ("even", "Even")], cond=lambda p: p["dsp"]["filter_on"]),
        F("dsp.v_coef", "Vertical coefficients c0..c4", "list", cond=lambda p: p["dsp"]["filter_on"]),
        F("dsp.credit_boost", "Credit sharpening (boost > 1) in the ranges", "bool", cond=lambda p: p["dsp"]["filter_on"]),
        H("Electronic zoom / replication", level="adv",
          active=lambda p: p["dsp"]["zoom"] > 1 or p["dsp"]["lrep"] > 1 or p["dsp"]["crep"] > 1),
        F("dsp.zoom", "Electronic zoom factor (enlarges, adds no information)", "int"),
        F("dsp.zoom_type", "Type of zoom", "choice", [("pixel", "Pixel replication"), ("bilinear", "Bilinear interpolation")]),
        F("dsp.lrep", "Line replication factor (adds no information)", "int"),
        F("dsp.lrep_type", "Line replication type", "choice", [("pixel", "Pixel replication"), ("linear", "Linear interpolation")]),
        F("dsp.crep", "Column replication factor (adds no information)", "int"),
        F("dsp.crep_type", "Column replication type", "choice", [("pixel", "Pixel replication"), ("linear", "Linear interpolation")]),
        H("Compression", level="adv", active=lambda p: p["dsp"].get("pl_compression", "none") != "none"),
        F("dsp.pl_compression", "Compression", "choice", [("none", "None"), ("lossless", "Lossless"),
                                                          ("lossy", "Lossy")]),
        F("dsp.comp_blur_px", "Equivalent blur of the lossy codec (0 = not modelled, extension)", unit="pixels rms",
          cond=lambda p: p["dsp"].get("pl_compression") == "lossy"),
        H("Tone mapping / AGC of the output (extension)", level="adv", active=TONE),
        F("dsp.tone_mode", "Output tone curve", "choice", [("none", "None - linear RAW (TRM4)"),
                                                           ("linear", "Linear AGC to the output levels"),
                                                           ("gamma", "Gamma curve"), ("log", "Logarithmic (HDR)")]),
        F("dsp.tone_bits", "  output bit depth", "int", cond=TONE, unit="bit"),
        F("dsp.tone_gamma", "  gamma exponent", cond=lambda p: TONE(p) and p["dsp"]["tone_mode"] == "gamma"),
        F("dsp.tone_k", "  log compression factor k", cond=lambda p: TONE(p) and p["dsp"]["tone_mode"] == "log"),
        F("dsp.tone_span_K", "  AGC span mapped to the output", unit="K", cond=lambda p: TONE(p) and THERMAL(p)),
    ]),
    ("Display & observer", [
        H("Observer model", level="adv", active=lambda p: p["display"].get("observer", "legacy") != "legacy"),
        F("display.observer", "Observer", "choice", [("legacy", "Legacy-neutral (TRM4 standard observer)"),
                                                     ("human", "Human - user-defined viewing conditions"),
                                                     ("algorithm", "Algorithm (reads the digital frames)")]),
        F("display.algo_calib", "Calibration data set ID (empty = uncalibrated)", "text", cond=ALGO),
        F("display.algo_criterion", "Algorithm task criterion", "choice",
          [("lp", "TRM4 line pairs, display and eye removed (uncalibrated)"),
           ("pot", "Pixels on target + pixel CNR (extension)")], cond=ALGO),
        F("display.algo_cnr_min", "  minimum pixel CNR (processed frame)", cond=POT),
        H("Observation (standard observer profile)", cond=lambda p: not ALGO(p)),
        F("display.observation", "Observation", "choice", [("direct", "Direct observation"), ("eyepiece", "Through eyepiece")],
          cond=lambda p: not ALGO(p)),
        F("display.distance_cm", "Distance display - observer", cond=lambda p: p["display"]["observation"] == "direct", unit="cm"),
        F("display.f_eyepiece_mm", "Focal length of eyepiece", cond=lambda p: p["display"]["observation"] == "eyepiece", unit="mm"),
        H("Flat panel display (Sec. 2.18)", level="adv"),
        F("display.n_h", "Number of horizontal elements", "int"),
        F("display.n_v", "Number of vertical elements", "int"),
        F("display.pitch_h_mm", "Horizontal element pitch", unit="mm"),
        F("display.pitch_v_mm", "Vertical element pitch", unit="mm"),
        F("display.luminance", "Operational display luminance", unit="cd/m2"),
        H("Observer calibration constants (TRM4 defaults)"),
        F("display.snr_th", "Threshold SNR"),
        F("display.t_eye_s", "Eye integration time", unit="s",
          cond=lambda p: not ALGO(p) and p["mode"]["stream"] == "video"),
        H("Laboratory override: no eye MTF", level="adv",
          cond=lambda p: not FIELD(p) or p["display"]["neglect_eye"], active=lambda p: p["display"]["neglect_eye"]),
        F("display.neglect_eye", "Neglect eye MTF", "bool", cond=lambda p: not FIELD(p) or p["display"]["neglect_eye"]),
    ]),
    ("Stabilization & MTFs", [
        H("Residual stabilization / image motion (Sec. 2.19) - exposure window linked to the integration time"),
        F("stab.jitter_mode", "Motion source", "choice", [("none", "None (no image motion)"),
                                                          ("model", "RMS-jitter assumption / vibration models"),
                                                          ("measured", "Measured time series"),
                                                          ("psd", "Measured angular PSD")],
          cond=lambda p: not p["stab"]["neglect"]),
        F("stab.psd_file", "PSD file ('f[Hz] PSD' or 'f h v')", "file",
          {"check": IM.psd_summary, "title": "Import angular PSD of the residual line of sight"}, cond=JIT_PSD),
        F("stab.psd_unit", "PSD unit", "choice", [("urad2", "urad^2/Hz"), ("mrad2", "mrad^2/Hz"),
                                                  ("pixel2", "pixel^2/Hz")], cond=JIT_PSD),
        F("stab.residual_los", "Data are residual LOS after stabilization", "bool",
          cond=lambda p: JIT_PSD(p) or JIT_MEAS(p)),
        F("stab.jitter_file", "Jitter file ('t h v' or 'h v')", "file",
          {"check": IM.jitter_summary, "title": "Import measured line-of-sight jitter"}, cond=JIT_MEAS),
        F("stab.jitter_unit", "Motion unit in file", "choice", [("urad", "microradian"), ("mrad", "milliradian"),
                                                                ("pixels", "detector pixels")], cond=JIT_MEAS),
        F("stab.jitter_rate_hz", "Sample rate (0 = time column in file)", unit="Hz", cond=JIT_MEAS),
        F("stab.jitter_preset", "Random jitter preset", "choice",
          [("custom", "User values"), ("nvipm70", "Typical residual LOS jitter, 70 urad rms (NV-IPM practice)")],
          cond=JIT_MODEL),
        F("stab.random_on", "Random vibrations", "bool", cond=JIT_MODEL),
        F("stab.rand_h_mrad", "Horizontal random vibration rms", cond=lambda p: JIT_MODEL(p) and p["stab"]["random_on"], unit="mrad"),
        F("stab.rand_v_mrad", "Vertical random vibration rms", cond=lambda p: JIT_MODEL(p) and p["stab"]["random_on"], unit="mrad"),
        F("stab.lin_on", "Linear motion", "bool", cond=JIT_MODEL),
        F("stab.lin_h", "Horizontal linear image velocity", cond=lambda p: JIT_MODEL(p) and p["stab"]["lin_on"], unit="mrad/s"),
        F("stab.lin_v", "Vertical linear image velocity", cond=lambda p: JIT_MODEL(p) and p["stab"]["lin_on"], unit="mrad/s"),
        F("stab.smear_allow_px", "Allowed smear per exposure (exposure budget)", unit="pixels",
          cond=lambda p: JIT_MODEL(p) and p["stab"]["lin_on"]),
        F("stab.sin_on", "Sinusoidal vibrations", "bool", cond=JIT_MODEL),
        F("stab.sin_h", "Horizontal sinusoidal amplitude", cond=lambda p: JIT_MODEL(p) and p["stab"]["sin_on"], unit="mrad"),
        F("stab.sin_v", "Vertical sinusoidal amplitude", cond=lambda p: JIT_MODEL(p) and p["stab"]["sin_on"], unit="mrad"),
        H("TRM4 switch: neglect stabilization MTF", level="legacy", active=lambda p: p["stab"]["neglect"]),
        F("stab.neglect", "Neglect stabilization MTF", "bool"),
        H("Additional imager MTFs (Sec. 2.20)", level="adv",
          active=lambda p: any(p["additional"][k] != "none" for k in p["additional"] if k.endswith("_type"))),
    ] + [f for w, wl in (("pre", "prefilter"), ("post", "postfilter")) for z, zl in (("h", "horizontal"), ("v", "vertical"))
         for f in (F("additional.%s_%s_type" % (w, z), "Additional %s %s" % (wl, zl), "choice",
                     [("none", "None"), ("sinc", "sinc"), ("sinc2", "sinc^2"), ("gaussian", "Gaussian"), ("rectangular", "Rectangular")]),
                   F("additional.%s_%s_par" % (w, z), "  first zero / std. deviation",
                     cond=(lambda w=w, z=z: (lambda p: p["additional"]["%s_%s_type" % (w, z)] != "none"))(), unit="1/mrad"))]),
    ("Target & scenario", [
        H("Target (Sec. 2.24 / 2.25)"),
        F("target.preset", "Standard target model", "choice", [("custom", "User defined")] +
          [(k, k) for k in P.THERMAL_TARGETS], THERMAL),
        F("target.W_m", "Width", unit="m"),
        F("target.H_m", "Height", unit="m"),
        F("target.D_m", "Depth (seen from the side, diagonal or from above)", unit="m", cond=TARGET_DEPTH),
        F("target.aspect", "Target viewing aspect", "choice", [("front", "Front"), ("side", "Side"), ("diagonal", "Diagonal")]),
        H("Target-background signature"),
        F("target.dT_K", "Temperature difference target-background", cond=lambda p: not VISIBLE(p), unit="K"),
        F("target.t_emis_mode", "Target emissivity", "choice", [("blackbody", "Blackbody"), ("grey", "Greybody"),
                                                               ("spectral", "Spectral (preset)")], GENERAL),
        F("target.t_emis", "Target emissivity", cond=lambda p: GENERAL(p) and p["target"]["t_emis_mode"] == "grey"),
        F("target.t_emis_preset", "Target material", "choice", [(n, n) for n in P.EMISSIVITY],
          cond=lambda p: GENERAL(p) and p["target"]["t_emis_mode"] == "spectral"),
        F("target.t_refl_mode", "Target reflectivity", "choice", [("effective", "Effective"), ("spectral", "Spectral (preset)")], VISIBLE),
        F("target.t_refl", "Target reflectivity", cond=lambda p: VISIBLE(p) and p["target"]["t_refl_mode"] == "effective"),
        F("target.t_refl_preset", "Target material", "choice", [(n, n) for n in P.REFLECTIVITY],
          cond=lambda p: VISIBLE(p) and p["target"]["t_refl_mode"] == "spectral"),
        H("Background"),
        F("target.T_bg_K", "Background temperature", unit="K"),
        F("target.b_emis_mode", "Background emissivity", "choice", [("blackbody", "Blackbody"), ("grey", "Greybody"),
                                                                   ("spectral", "Spectral (preset)")], GENERAL),
        F("target.b_emis", "Background emissivity", cond=lambda p: GENERAL(p) and p["target"]["b_emis_mode"] == "grey"),
        F("target.b_emis_preset", "Background material", "choice", [(n, n) for n in P.EMISSIVITY],
          cond=lambda p: GENERAL(p) and p["target"]["b_emis_mode"] == "spectral"),
        F("target.b_refl_mode", "Background reflectivity", "choice", [("effective", "Effective"), ("spectral", "Spectral (preset)")], VISIBLE),
        F("target.b_refl", "Background reflectivity", cond=lambda p: VISIBLE(p) and p["target"]["b_refl_mode"] == "effective"),
        F("target.b_refl_preset", "Background material", "choice", [(n, n) for n in P.REFLECTIVITY],
          cond=lambda p: VISIBLE(p) and p["target"]["b_refl_mode"] == "spectral"),
        H("3D geometry: oblique / aerial line of sight", level="adv",
          active=lambda p: p["target"]["flight"] == "angle" and p["target"]["angle_deg"] != 0 or
          p["target"]["flight"] == "altitude" and p["target"]["altitude_m"] != 0),
        F("target.alt_m", "Target altitude above ground", unit="m"),
        F("target.flight", "Imager flight path", "choice", [("altitude", "Constant altitude"), ("angle", "Constant angle")]),
        F("target.altitude_m", "Altitude relative to target", cond=lambda p: p["target"]["flight"] == "altitude", unit="m"),
        F("target.angle_deg", "Observation angle (down = positive)", cond=lambda p: p["target"]["flight"] == "angle", unit="deg"),
        H("Task and number of line pairs (standard criteria)"),
        F("target.task_preset", "Criteria preset (version)", "choice", [(k, v[0]) for k, v in P.TASK_PRESETS.items()]),
    ] + [f for i in range(3) for f in (F("target.tasks.%d.on" % i, "Task %d active" % (i + 1), "bool"),
                                        F("target.tasks.%d.name" % i, "  name", "text"),
                                        F("target.tasks.%d.lp" % i, "  number of line pairs"),
                                        F("target.tasks.%d.pot" % i, "  pixels on target (algorithm)", cond=POT),
                                        F("target.tasks.%d.v50" % i, "  V50 of the TTP metric", unit="cycles",
                                          cond=TTP))] + [
        H("Probability and clutter (extensions - TRM4 gives the 50 % range of an uncluttered scene)"),
        F("target.prob_levels", "Also report P80 / P90 ranges (Johnson TTPF)", "bool", cond=lambda p: not POT(p)),
        F("target.ttp", "Also report TTP / V50 ranges (Vollmerhausen 2004)", "bool", cond=lambda p: not POT(p)),
        F("target.geo_limit", "Also report the geometric reference range (Nyquist / diffraction)", "bool"),
        F("target.clutter", "Background clutter", "choice", [("not_specified", "Not specified"), ("low", "Low"),
                                                             ("medium_low", "Medium-low"), ("medium", "Medium"),
                                                             ("high", "High")]),
        F("target.clutter_model", "Clutter raises the Detection criterion (ACQUIRE-LC)", "bool",
          cond=lambda p: p["target"].get("clutter", "not_specified") != "not_specified"),
    ]),
    ("Irradiance", [
        H("Illumination source (Sec. 2.26)", cond=NOT_THERMAL),
        F("irradiance.mode", "Irradiance", "choice", [("none", "No irradiance (General only)"),
                                                     ("single", "Single illumination source")], NOT_THERMAL),
        F("irradiance.type", "Source type", "choice", [("blackbody", "Blackbody (hemispherical)"), ("broadband", "Other - broadband"),
                                                      ("monochromatic", "Other - monochromatic")],
          cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single"),
        F("irradiance.T_bb_K", "Blackbody temperature", cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single"
          and p["irradiance"]["type"] == "blackbody", unit="K"),
        F("irradiance.spectrum", "Characterisation", "choice", [("effective", "Effective data (flat)"), ("colour", "Colour temperature"),
                                                               ("preset", "Natural source preset")],
          cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single" and p["irradiance"]["type"] == "broadband"),
        F("irradiance.E_eff", "Effective scene irradiance (band-integrated)", cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single"
          and p["irradiance"]["type"] == "broadband" and p["irradiance"]["spectrum"] == "effective", unit="W/m2"),
        F("irradiance.T_colour_K", "Colour temperature", cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single"
          and p["irradiance"]["type"] == "broadband" and p["irradiance"]["spectrum"] == "colour", unit="K"),
        F("irradiance.preset", "Natural source", "choice", [(n, "%s (peak %g)" % (n, P.NATURAL_SOURCES[n]["peak"])) for n in P.SOURCE_NAMES],
          cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single" and p["irradiance"]["type"] == "broadband"
          and p["irradiance"]["spectrum"] == "preset"),
        F("irradiance.E_peak", "Spectral irradiance at peak (at the target)", cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single"
          and p["irradiance"]["type"] == "broadband" and p["irradiance"]["spectrum"] != "effective", unit="W/(m2 um)"),
        F("irradiance.lambda_um", "Wavelength", cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single"
          and p["irradiance"]["type"] == "monochromatic", unit="um"),
        F("irradiance.E_mono", "Scene irradiance", cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single"
          and p["irradiance"]["type"] == "monochromatic", unit="W/m2"),
        F("irradiance.geometry", "Source geometry", "choice", [("extended", "Extended source"), ("fixed_space", "Point source fixed in space")],
          cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single" and p["irradiance"]["type"] != "blackbody"),
        F("irradiance.beta_h_deg", "Angle to target front - horizontal", cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single"
          and p["irradiance"]["geometry"] == "fixed_space" and p["irradiance"]["type"] != "blackbody", unit="deg"),
        F("irradiance.beta_v_deg", "Angle to target front - vertical", cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single"
          and p["irradiance"]["geometry"] == "fixed_space" and p["irradiance"]["type"] != "blackbody", unit="deg"),
        H("Not used in the Thermal category (targets and backgrounds are blackbodies).", cond=THERMAL),
    ]),
    ("Atmosphere & turbulence", [
        H("Atmospheric transmission (Sec. 2.27)"),
        F("atmosphere.preset", "Fast-mode preset", "choice", P.ATM_PRESET_NAMES, cond=lambda p: not SPEC_ATM(p)),
        F("atmosphere.mode", "Transmission via", "choice", [("extinction", "Extinction coefficient (fast, Beer-Lambert)"),
                                                           ("visibility", "Visual range (Visible category only)"),
                                                           ("weather", "Visual range + humidity + air temperature "
                                                                       "(extension)"),
                                                           ("spectral", "Spectral data import (e.g. MODTRAN)")]),
        F("atmosphere.spec_file", "Transmission vs wavelength (x range)", "file",
          {"check": IM.atmosphere_summary, "title": "Import spectral atmospheric transmission"}, cond=SPEC_ATM),
        F("atmosphere.spec_L_km", "Path length of the data (single column)", unit="km", cond=SPEC_ATM),
        F("atmosphere.atm.0.T_air_K", "Air temperature", unit="K", cond=lambda p: SPEC_ATM(p) and GENERAL(p)),
        F("atmosphere.atm.0.F_PR", "Path radiance factor", cond=lambda p: SPEC_ATM(p) and NOT_THERMAL(p)
          and p["atmosphere"].get("path_mode") != "import"),
    ] + _atm_rows() + [
        H("Path radiance (independent of the direct-path transmittance)", cond=NOT_THERMAL),
        F("atmosphere.path_mode", "Path radiance", "choice", [("model", "Modelled (air temperature / path radiance factor)"),
                                                              ("import", "Imported spectral path radiance")], NOT_THERMAL),
        F("atmosphere.path_file", "Path radiance vs wavelength (x range)", "file",
          {"check": IM.path_summary, "title": "Import spectral path radiance [W/(m2 sr um)]"},
          cond=lambda p: NOT_THERMAL(p) and p["atmosphere"].get("path_mode") == "import"),
        F("atmosphere.path_L_km", "Path length of the data (single column)", unit="km",
          cond=lambda p: NOT_THERMAL(p) and p["atmosphere"].get("path_mode") == "import"),
        H("Description of the imported data: page 'Metadata'", cond=ATM_DOC),
        H("Turbulence (Sec. 2.28)", cond=FIELD),
        F("turbulence.thermal", "Apply turbulence in the Thermal category (extension - TRM4 neglects it)", "bool",
          cond=lambda p: THERMAL(p) and FIELD(p)),
        F("turbulence.on", "Consider turbulence", "bool", cond=TURB_CAT),
        F("turbulence.cn2_preset", "Scenario default (Table C.2)", "choice",
          [("custom", "Custom")] + [(k, k) for k in P.CN2_PRESETS], cond=TURB_ON),
        F("turbulence.exposure", "Type of MTF", "choice", [("short", "Short exposure (image motion removed)"),
                                                           ("long", "Long exposure (incl. image wander)")], cond=TURB_ON),
        F("turbulence.cn2_mode", "Turbulence specified via", "choice",
          [("fixed", "Cn2 - fixed value"), ("height", "Cn2 - simplified height dependence"),
           ("hv", "Cn2 - Hufnagel-Valley altitude profile (extension)"),
           ("r0", "Fried parameter r0 with reference conditions")], cond=TURB_ON),
        F("turbulence.cn2", "Cn2 (Hufnagel-Valley: ground-level coefficient A)", cond=lambda p: TURB_ON(p) and
          not R0_MODE(p), unit="m^-2/3"),
        F("turbulence.hv_wind_ms", "  rms upper-altitude wind (HV 5/7: 21)", unit="m/s",
          cond=lambda p: TURB_ON(p) and p["turbulence"]["cn2_mode"] == "hv"),
        F("turbulence.r0_cm", "Fried parameter r0", cond=lambda p: TURB_ON(p) and R0_MODE(p), unit="cm"),
        F("turbulence.r0_lambda_um", "  r0 reference wavelength", unit="um", cond=lambda p: TURB_ON(p) and R0_MODE(p)),
        F("turbulence.r0_L_km", "  r0 reference path length", unit="km", cond=lambda p: TURB_ON(p) and R0_MODE(p)),
        F("turbulence.h_ref_m", "Cn2 specified at height", cond=lambda p: TURB_ON(p)
          and p["turbulence"]["cn2_mode"] == "height", unit="m"),
        F("turbulence.time", "Day / night", "choice", [("day", "Day"), ("night", "Night")],
          cond=lambda p: TURB_ON(p) and p["turbulence"]["cn2_mode"] == "height"),
        F("turbulence.L0_m", "Outer scale L0, von Karman (0 = Kolmogorov)", unit="m", cond=TURB_ON),
        F("turbulence.mitigation", "Mitigation processing: effective r0 gain (1 = none, extension)", cond=TURB_ON),
    ]),
    ("Metadata", [
        H("Imported optics MTF", cond=OPT_FILE),
        F("optics.mtf_meta", "Spectrum / field / zoom-focus of the data", "text", cond=OPT_FILE),
        F("optics.mtf_band", "Wavelength / band of the data", "text", cond=OPT_FILE),
        F("optics.mtf_focus", "Focus state", "text", cond=OPT_FILE),
        F("optics.mtf_temp", "Operating temperature", "text", cond=OPT_FILE),
        F("optics.mtf_uncert", "Measurement / model uncertainty", "text", cond=OPT_FILE),
        H("Imported atmospheric data", cond=ATM_DOC),
        F("atmosphere.meta.geometry", "Path geometry (horizontal / slant, altitudes)", "text", cond=ATM_DOC),
        F("atmosphere.meta.source", "Generating model / source (e.g. MODTRAN version)", "text", cond=ATM_DOC),
        F("atmosphere.meta.conditions", "Conditions (humidity, temperature, pressure, date)", "text", cond=ATM_DOC),
        F("atmosphere.meta.database", "Spectroscopy database edition (e.g. HITRAN2024)", "text", cond=ATM_DOC),
        F("atmosphere.meta.rt_code", "Radiative-transfer code / version", "text", cond=ATM_DOC),
        F("atmosphere.meta.profile", "T-p-h profile / gas concentrations", "text", cond=ATM_DOC),
        F("atmosphere.meta.aerosol", "Aerosol model / visibility", "text", cond=ATM_DOC),
        F("atmosphere.meta.resolution", "Spectral resolution / output bandpass", "text", cond=ATM_DOC),
        H("Sensor operating point and readout"),
        F("detector.op_mode", "Operating mode (gain, conversion gain, readout, temperature)", "text", cond=COOLED),
        F("detector.netd_nuc", "Camera NETD test: gain / NUC / processing state", "text", cond=CAM_NETD),
        F("basic.roi", "ROI / window mode", "text"),
        H("Processing pipeline (not modelled; compression: page 'Signal processing')"),
        F("dsp.pl_denoise", "Denoising active (not modelled)", "bool"),
        F("dsp.pl_order", "Order of steps (e.g. NUC > denoise > sharpen > zoom)", "text"),
        F("dsp.pl_version", "Kernel / algorithm version", "text"),
        H("Algorithm observer", cond=ALGO),
        F("display.algo_id", "Algorithm / model version ID", "text", cond=ALGO),
        F("display.algo_roc", "ROC / false-alarm definition", "text", cond=ALGO),
        H("Scene (clutter level: page 'Target & scenario')"),
        F("target.scene_id", "Scene / clutter measurement ID", "text"),
    ]),
    ("Validation data", [
        H("Measured performance curve (MTDP / MRTD / MCP)"),
        F("measured.fom_file", "Curve file ('f value' or 'f h v')", "file",
          {"check": IM.curve_summary, "title": "Import measured MTDP / MRTD / MCP"}),
        F("measured.fom_kind", "Quantity", "choice", [("MTDP", "MTDP"), ("MRTD", "MRTD"), ("MCP", "MCP (contrast)")]),
        F("measured.fom_unit", "Frequency unit", "choice", FREQ_UNITS),
        F("measured.fom_vunit", "Temperature unit", "choice", [("K", "K"), ("mK", "mK")],
          cond=lambda p: p["measured"]["fom_kind"] != "MCP"),
        F("measured.fom_use", "Use of the curve", "choice", [("compare", "Compare with the prediction"),
                                                             ("replace", "Replace the modelled MTDP for ranges (Thermal)")]),
        H("Measured MTF / SFR (slanted edge, bar target)"),
        F("measured.sfr_file", "MTF file ('f value' or 'f h v')", "file",
          {"check": IM.curve_summary, "title": "Import measured MTF / SFR"}),
        F("measured.sfr_kind", "Data describe", "choice", [("device", "Device prefilter (optics + detector)"),
                                                           ("system", "Delivered image SFR (incl. processing, display)")]),
        F("measured.sfr_unit", "Frequency unit", "choice", FREQ_UNITS),
        H("Measured NETD", cond=THERMAL),
        F("measured.netd_mK", "Measured NETD (0 = none)", unit="mK", cond=THERMAL),
        F("measured.netd_TB_K", "Blackbody temperature of the test", unit="K", cond=THERMAL),
        H("Calibration metadata"),
        F("measured.meta.instrument", "Instrument / test bench", "text"),
        F("measured.meta.date", "Date", "text"),
        F("measured.meta.method", "Method / standard", "text"),
        F("measured.meta.focus", "Focus setting", "text"),
        F("measured.meta.temperature", "Ambient / sensor temperature", "text"),
        F("measured.meta.processing", "Frame processing (NUC, filters, AGC)", "text"),
        F("measured.meta.uncertainty", "Measurement uncertainty", "text"),
        F("measured.meta.config_id", "Configuration identifier", "text"),
        F("measured.meta.firmware", "Camera firmware", "text"),
        F("measured.meta.op_mode", "Gain / readout mode", "text"),
        F("measured.meta.frame_rate", "Frame rate", "text"),
        F("measured.meta.roi", "ROI / window", "text"),
        F("measured.meta.exposure", "Exposure / integration time", "text"),
        F("measured.meta.f_number", "F-number", "text"),
        F("measured.meta.raw_files", "RAW file references", "text"),
        F("measured.meta.calib_id", "Calibration identifiers (traceable sources)", "text"),
    ]),
]

_BY_PATH = {}
for _name, _fields in TABS:
    for _f in _fields:
        if _f.get("path") and _f["path"] not in _BY_PATH:
            _BY_PATH[_f["path"]] = _f


def pick(path, label=None, cond=None):
    """Re-use a parameter definition on another page (Quick setup)."""
    f = dict(_BY_PATH[path])
    f["level"] = "base"
    if label:
        f["label"] = label
    if cond:
        f["cond"] = cond
    return f


QUICK = ("Quick setup", [
    {"kind": "profile", "cond": ALWAYS, "level": "base"},
    H("Camera"),
    pick("category"), pick("imager_type"), pick("optics.f_mm"),
    H("Target"),
    pick("target.preset"), pick("target.W_m"), pick("target.H_m"), pick("target.D_m"), pick("target.aspect"),
    H("Target-background signature"),
    pick("target.dT_K"), pick("target.T_bg_K"), pick("target.t_refl_mode"), pick("target.t_refl"),
    pick("target.t_refl_preset"), pick("target.b_refl_mode"), pick("target.b_refl"), pick("target.b_refl_preset"),
    H("Illumination", cond=NOT_THERMAL),
    pick("irradiance.mode"), pick("irradiance.type"), pick("irradiance.spectrum"), pick("irradiance.preset"),
    pick("irradiance.E_peak"),
    H("Atmosphere", cond=FIELD),
    pick("atmosphere.preset", cond=lambda p: FIELD(p) and not SPEC_ATM(p)),
    pick("atmosphere.atm.0.sigma", "Extinction coefficient (atm 1)", cond=lambda p: FIELD(p) and not SPEC_ATM(p) and not (
        VISIBLE(p) and p["atmosphere"]["mode"] == "visibility") and not WEATHER(p)),
    pick("atmosphere.atm.0.V_km", "Visual range (atm 1)", cond=lambda p: FIELD(p) and (WEATHER(p) or VISIBLE(p) and
         p["atmosphere"]["mode"] == "visibility")),
    pick("atmosphere.atm.0.rh_pct", "Relative humidity (atm 1)", cond=lambda p: FIELD(p) and WEATHER(p)),
    pick("turbulence.on", cond=lambda p: FIELD(p) and TURB_CAT(p)),
    pick("turbulence.cn2_preset", cond=lambda p: FIELD(p) and TURB_ON(p)),
    H("Task and observation"),
    pick("mode.environment"), pick("mode.stream"),
] + [pick("target.tasks.%d.%s" % (i, k)) for i in range(3) for k in ("on", "name", "lp")] + [D()])

PROFILE_PAGE = ("Camera profile", [{"kind": "profile_manager", "cond": ALWAYS, "level": "base"}, D()])

ALL_PAGES = [QUICK, PROFILE_PAGE] + TABS
ENGINEERING_PAGES = ["Camera profile"] + [n for n, _ in TABS if n != "Validation data"]
WORKFLOWS = {
    "quick": ("Quick Prediction", ["Quick setup", "Camera profile"]),
    "engineering": ("Engineering Analysis", ENGINEERING_PAGES),
    "lab": ("Laboratory & Image Evaluation", ["Validation data"] + ENGINEERING_PAGES),
}
RESULT_TABS = {
    "quick": ("Summary", "Range", "Messages"),
    "engineering": ("Summary", "System data", "MTF", "AMOP", "MTDP / MDSP", "Range", "NIIRS", "Spectral",
                    "Sensitivity", "Messages"),
    "lab": ("Summary", "System data", "MTF", "AMOP", "MTDP / MDSP", "Range", "NIIRS", "Spectral", "Validation",
            "Sensitivity", "Messages"),
}


# ---------------------------------------------------------------------------------------------
def get_path(d, path):
    for k in path.split("."):
        d = d[int(k)] if isinstance(d, list) else d[k]
    return d


def set_path(d, path, value):
    keys = path.split(".")
    for k in keys[:-1]:
        d = d[int(k)] if isinstance(d, list) else d[k]
    k = keys[-1]
    if isinstance(d, list):
        d[int(k)] = value
    else:
        d[k] = value


def fmt(v):
    if isinstance(v, float):
        return "%.6g" % v
    return str(v)


class ScrollFrame(ttk.Frame):
    def __init__(self, master, padding=0):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0, background=SURFACE, borderwidth=0)
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, padding=padding)
        self.inner.bind("<Configure>", self._update_region)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: (self.canvas.itemconfigure(self._win, width=e.width),
                                                   self._update_region()))
        self.canvas.configure(yscrollcommand=self.sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.sb.pack(side="right", fill="y")
        self.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _update_region(self, _e=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # hide the scrollbar when everything fits
        if self.inner.winfo_reqheight() <= self.canvas.winfo_height():
            self.canvas.yview_moveto(0)
            self.sb.pack_forget()
        elif not self.sb.winfo_ismapped():
            self.sb.pack(side="right", fill="y")

    def _wheel(self, e):
        if self.sb.winfo_ismapped():
            self.canvas.yview_scroll(int(-e.delta / 120), "units")


class Tooltip:
    """Small hover tooltip."""

    def __init__(self, widget, text, delay=550, wrap=0, click=False):
        self.widget, self.text, self.tip, self._job = widget, text, None, None
        self.delay, self.wrap = delay, wrap
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._toggle if click else self._hide, add="+")

    def _schedule(self, _e=None):
        self._job = self.widget.after(self.delay, self._show)

    def _toggle(self, _e=None):
        if self.tip:
            self._hide()
        else:
            self._show()

    def _show(self):
        self._job = None
        if self.tip or not self.text:
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        tk.Label(self.tip, text=self.text, bg="#26303f", fg="white", font=("Segoe UI", 9), padx=8, pady=4,
                 justify="left", wraplength=self.wrap).pack()
        # keep the tip on screen (the "?" icons sit at the right edge of the form)
        self.tip.update_idletasks()
        x = self.widget.winfo_rootx() + 8
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        x = max(0, min(x, self.widget.winfo_screenwidth() - self.tip.winfo_reqwidth() - 4))
        if y + self.tip.winfo_reqheight() > self.widget.winfo_screenheight():
            y = self.widget.winfo_rooty() - self.tip.winfo_reqheight() - 6
        self.tip.wm_geometry("+%d+%d" % (x, y))

    def _hide(self, _e=None):
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None
        if self.tip:
            self.tip.destroy()
            self.tip = None


class ToolButton(tk.Frame):
    """Flat toolbar button: icon glyph + text, hover highlight."""

    def __init__(self, master, glyph, text, command, accent=False, tip=None):
        self.accent = accent
        self.bg = ACCENT if accent else SURFACE
        self.hover = ACCENT_HOVER if accent else "#edf1f6"
        fg = "white" if accent else TEXT
        super().__init__(master, bg=self.bg, cursor="hand2")
        self.command, self.enabled = command, True
        self.parts = []
        if ICON_FONT and glyph:
            ic = tk.Label(self, text=glyph, font=(ICON_FONT, 11), bg=self.bg, fg="white" if accent else ACCENT)
            ic.pack(side="left", padx=(10, 5), pady=6)
            self.parts.append(ic)
        self.label = tk.Label(self, text=text, font=FONT_SEMI if accent else FONT, bg=self.bg, fg=fg)
        self.label.pack(side="left", padx=(0 if self.parts else 12, 12), pady=6)
        self.parts.append(self.label)
        for w in [self] + self.parts:
            w.bind("<Enter>", lambda e: self._paint(self.hover))
            w.bind("<Leave>", lambda e: self._paint(self.bg))
            w.bind("<ButtonRelease-1>", self._click)
        if tip:
            Tooltip(self, tip)

    def _paint(self, color):
        if not self.enabled:
            color = self.bg
        for w in [self] + self.parts:
            w.configure(bg=color)

    def _click(self, e):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, on):
        self.enabled = on
        fg = ("white" if self.accent else TEXT) if on else ("#dbe6fb" if self.accent else "#a3abb8")
        self.label.configure(fg=fg)
        self.configure(cursor="hand2" if on else "arrow")
        self._paint(self.bg)

    def set_text(self, text):
        self.label.configure(text=text)


class SidebarItem(tk.Frame):
    def __init__(self, master, name, on_select):
        super().__init__(master, bg=SIDEBAR, cursor="hand2")
        self.name, self.selected = name, False
        self.bar = tk.Frame(self, bg=SIDEBAR, width=3)
        self.bar.pack(side="left", fill="y")
        self.parts = [self]
        if ICON_FONT:
            ic = tk.Label(self, text=GLYPH.get(name, ""), font=(ICON_FONT, 11), bg=SIDEBAR, fg=SIDEBAR_TEXT, width=2)
            ic.pack(side="left", padx=(12, 6), pady=7)
            self.parts.append(ic)
        lb = tk.Label(self, text=name, font=FONT, bg=SIDEBAR, fg=SIDEBAR_TEXT, anchor="w")
        lb.pack(side="left", fill="x", expand=True, padx=(0 if ICON_FONT else 16, 10), pady=7)
        self.parts.append(lb)
        for w in self.parts:
            w.bind("<Enter>", lambda e: self._paint())
            w.bind("<Leave>", lambda e: self._paint())
            w.bind("<ButtonRelease-1>", lambda e: on_select(self.name))

    def _paint(self):
        try:
            x, y = self.winfo_pointerxy()
            hovering = self.winfo_containing(x, y) in self.parts
        except (tk.TclError, KeyError):
            hovering = False
        bg = SIDEBAR_SEL if self.selected else (SIDEBAR_HOVER if hovering else SIDEBAR)
        fg = "white" if self.selected else SIDEBAR_TEXT
        for w in self.parts:
            w.configure(bg=bg)
            if isinstance(w, tk.Label):
                w.configure(fg="#5aa2ff" if (self.selected and w is self.parts[1] and ICON_FONT) else fg)
        self.bar.configure(bg="#5aa2ff" if self.selected else bg)

    def select(self, on):
        self.selected = on
        self._paint()


class PlotTab(ttk.Frame):
    def __init__(self, master, nrows=1, ncols=1):
        super().__init__(master)
        self.fig = Figure(figsize=(7, 5), dpi=100, constrained_layout=True)
        self.nrows, self.ncols = nrows, ncols
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        tb = NavigationToolbar2Tk(self.canvas, self, pack_toolbar=False)
        tb.configure(background=SURFACE)
        for w in tb.winfo_children():
            try:
                w.configure(background=SURFACE)
            except tk.TclError:
                pass
        tb.update()
        tb.pack(side="bottom", fill="x", padx=6)
        w = self.canvas.get_tk_widget()
        w.pack(fill="both", expand=True, padx=6, pady=(6, 0))
        # matplotlib applies the screen scaling on first <Map>; on a hidden notebook tab the widget size does not
        # change afterwards, so no <Configure> follows and the figure stays too large -> re-fit it explicitly.
        w.bind("<Map>", lambda e: self.after_idle(self._refit), add="+")
        self.placeholder("Results appear here after the calculation (F5).")

    def _refit(self):
        w = self.canvas.get_tk_widget()
        if w.winfo_width() > 1 and w.winfo_height() > 1:
            ev = type("Ev", (), {"width": w.winfo_width(), "height": w.winfo_height()})()
            self.canvas.resize(ev)

    def placeholder(self, text):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.axis("off")
        ax.text(0.5, 0.5, text, ha="center", va="center", color=MUTED, fontsize=11, transform=ax.transAxes)
        self.draw()

    def axes(self, nrows=None, ncols=None):
        self.fig.clear()
        n, m = nrows or self.nrows, ncols or self.ncols
        return [self.fig.add_subplot(n, m, i + 1) for i in range(n * m)]

    def draw(self):
        self.canvas.draw_idle()


class Splash(tk.Toplevel):
    def __init__(self, master, logo):
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(bg=SIDEBAR)
        k = dpi_scale(master)
        w, h = int(480 * k), int(290 * k)
        x, y = (self.winfo_screenwidth() - w) // 2, (self.winfo_screenheight() - h) // 2
        self.geometry("%dx%d+%d+%d" % (w, h, x, y))
        box = tk.Frame(self, bg=SIDEBAR)
        box.place(relx=0.5, rely=0.45, anchor="center")
        if logo:
            tk.Label(box, image=logo, bg=SIDEBAR).pack(pady=(0, 10))
        tk.Label(box, text=APP_NAME, font=("Segoe UI Semibold", 24), fg="white", bg=SIDEBAR).pack()
        tk.Label(box, text="Thermal Range Model  ·  TRM4.v3", font=("Segoe UI", 11), fg=SIDEBAR_TEXT,
                 bg=SIDEBAR).pack()
        self.msg = tk.Label(self, text="Starting...", font=("Segoe UI", 9), fg="#7f8ba0", bg=SIDEBAR)
        self.msg.place(relx=0.04, rely=0.93, anchor="w")
        tk.Label(self, text="Version %s" % __version__, font=("Segoe UI", 9), fg="#7f8ba0",
                 bg=SIDEBAR).place(relx=0.96, rely=0.93, anchor="e")
        self.lift()
        self.update()

    def say(self, text):
        self.msg.configure(text=text)
        self.update_idletasks()


class ProfileBar(ttk.Frame):
    """Camera profile selector (Quick setup) or manager (Camera profile page)."""

    def __init__(self, master, app, manager=False):
        super().__init__(master)
        self.app, self.manager = app, manager
        k = app.k
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Camera profile", style="Head.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.cb_prof = ttk.Combobox(top, state="readonly", width=24)
        self.cb_prof.grid(row=1, column=0, sticky="we", padx=(0, 6))
        self.cb_prof.bind("<<ComboboxSelected>>", lambda e: self._prof_selected())
        self.cb_cfg = ttk.Combobox(top, state="readonly", width=12)
        self.cb_cfg.grid(row=1, column=1, sticky="we", padx=(0, 6))
        ttk.Button(top, text="Apply", style="Accent.TButton", command=self._apply).grid(row=1, column=2)
        top.columnconfigure(0, weight=3)
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="sensor", style="Unit.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(top, text="optics (zoom / FOV)", style="Unit.TLabel").grid(row=2, column=1, sticky="w")
        self.info = autowrap(ttk.Label(self, style="Muted.TLabel", justify="left"))
        self.info.pack(fill="x", pady=(6, 0))
        self.current = autowrap(ttk.Label(self, justify="left"))
        self.current.pack(fill="x", pady=(4, 0))
        if manager:
            bar = ttk.Frame(self)
            bar.pack(fill="x", pady=(10, 0))
            ttk.Button(bar, text="Save camera as new profile...", command=self._save_new).grid(row=0, column=0,
                                                                                            sticky="we", padx=(0, 4))
            ttk.Button(bar, text="Add optics as configuration...", command=self._add_config).grid(row=0, column=1,
                                                                                                sticky="we")
            ttk.Button(bar, text="Delete profile", command=self._delete).grid(row=1, column=0, sticky="we",
                                                                              padx=(0, 4), pady=(4, 0))
            ttk.Button(bar, text="Open profiles folder", command=self._open_folder).grid(row=1, column=1, sticky="we",
                                                                                        pady=(4, 0))
            autowrap(ttk.Label(self, style="Muted.TLabel", justify="left", text=(
                "A profile holds the sensor (category, detector, frame rate, processing) and one or more optical "
                "configurations (zoom / focus positions). Applying it copies the values into the project and marks "
                "their data source; FOV, IFOV, Nyquist frequency and F-number are then calculated automatically. "
                "Profiles are stored as JSON files in the 'profiles' folder. Tip: use Detector lookup to fill the "
                "detector from a datasheet, check the values, then save the camera as a profile."))).pack(
                fill="x", pady=(10, 0))
        self.reload()

    def _names(self):
        return [p["name"] + ("" if p.get("builtin") else "   (user)") for p in self.app.profiles]

    def reload(self):
        self.cb_prof.configure(values=self._names())
        self.sync(select=True)

    def _sel(self):
        i = self.cb_prof.current()
        return self.app.profiles[i] if 0 <= i < len(self.app.profiles) else None

    def _prof_selected(self):
        prof = self._sel()
        if not prof:
            return
        names = [c["name"] for c in prof["configs"]]
        self.cb_cfg.configure(values=names)
        self.cb_cfg.set(names[0])
        src = dict(P.SOURCES).get(prof.get("source", ""), prof.get("source", ""))
        self.info.configure(text="%s%s  ·  data source: %s  ·  %d configuration(s)\n%s" % (
            prof.get("vendor", "") or "", " " if prof.get("vendor") else "", src, len(names), prof.get("notes", "")))

    def sync(self, select=False):
        cur = (self.app.project.get("profile") or {})
        if cur.get("name"):
            mod = any(s == "user" for p, s in (self.app.project.get("provenance") or {}).items()
                      if p.split(".")[0] in PR.SENSOR_KEYS + ("optics",))
            self.current.configure(text="Applied to the project: %s  [%s]%s" % (
                cur["name"], cur.get("config", ""), "  - modified by the user" if mod else ""), foreground=OK)
        else:
            self.current.configure(text="No profile applied - the camera is defined by the template / manual input.",
                                   foreground=MUTED)
        if select or self.cb_prof.current() < 0:
            names = [p["name"] for p in self.app.profiles]
            if cur.get("name") in names:
                self.cb_prof.current(names.index(cur["name"]))
                self._prof_selected()
                cfgs = [c["name"] for c in self.app.profiles[names.index(cur["name"])]["configs"]]
                if cur.get("config") in cfgs:
                    self.cb_cfg.set(cur["config"])
            elif self.app.profiles and self.cb_prof.current() < 0:
                self.cb_prof.current(0)
                self._prof_selected()

    def _apply(self):
        prof = self._sel()
        if prof:
            self.app.apply_profile(prof, self.cb_cfg.get())

    def _ask(self, title, fields):
        """Small form dialog: fields = [(key, label, default, options-or-None)] -> dict or None."""
        dlg = self.app._dialog(title)
        fr = ttk.Frame(dlg, padding=18)
        fr.pack(fill="both", expand=True)
        vals = {}
        for i, (key, label, default, opts) in enumerate(fields):
            ttk.Label(fr, text=label).grid(row=i, column=0, sticky="w", pady=3, padx=(0, 10))
            if opts:
                w = ttk.Combobox(fr, values=[l for _, l in opts], state="readonly", width=36)
                w.set(dict(opts).get(default, opts[0][1]))
                vals[key] = (w, opts)
            else:
                v = tk.StringVar(value=default)
                w = ttk.Entry(fr, textvariable=v, width=38)
                vals[key] = (v, None)
            w.grid(row=i, column=1, sticky="we", pady=3)
        out = {}

        def ok():
            for key, (w, opts) in vals.items():
                if opts:
                    out[key] = next(v for v, l in opts if l == w.get())
                else:
                    out[key] = w.get().strip()
            dlg.destroy()
        bar = ttk.Frame(fr)
        bar.grid(row=len(fields), column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(bar, text="OK", style="Accent.TButton", command=ok).pack(side="left", padx=4)
        ttk.Button(bar, text="Cancel", command=dlg.destroy).pack(side="left")
        dlg.wait_window()
        return out or None

    def _save_new(self):
        p = self.app.collect()
        src_opts = [s for s in P.SOURCES if s[0] in ("manufacturer", "measurement", "assumption", "user")]
        r = self._ask("Save camera as profile", [("name", "Profile name", p.get("name", ""), None),
                                                 ("vendor", "Manufacturer / model", "", None),
                                                 ("config", "Optical configuration name", "Nominal", None),
                                                 ("source", "Values come from", "manufacturer", src_opts),
                                                 ("calibration_date", "Calibration date (if measured)", "", None),
                                                 ("notes", "Notes", "", None)])
        if not r or not r["name"]:
            return
        try:
            prof = PR.from_project(p, r["name"], r["config"] or "Nominal", r["vendor"], r["source"], r["notes"],
                                   r.get("calibration_date", ""))
            fn = PR.save(prof)
        except (ValueError, OSError) as e:
            messagebox.showerror("Camera profile", str(e), parent=self.app)
            return
        self.app.project["profile"] = {"name": prof["name"], "config": prof["configs"][0]["name"],
                                       "profile_id": prof["profile_id"], "content_hash": prof["content_hash"]}
        self.app.reload_profiles()
        self.app.status.set("Profile saved: %s" % fn)

    def _add_config(self):
        prof = self._sel()
        if not prof or prof.get("builtin"):
            messagebox.showinfo("Camera profile", "Select a user profile (built-in profiles cannot be changed). Save "
                                "the camera as a new profile first.", parent=self.app)
            return
        r = self._ask("Add optical configuration", [("config", "Configuration name (e.g. NFOV)", "", None)])
        if not r or not r["config"]:
            return
        PR.add_config(prof, self.app.collect(), r["config"])
        PR.save(prof)
        self.app.reload_profiles()
        self.app.status.set("Configuration '%s' added to %s" % (r["config"], prof["name"]))

    def _delete(self):
        prof = self._sel()
        if not prof:
            return
        if prof.get("builtin"):
            messagebox.showinfo("Camera profile", "Built-in profiles cannot be deleted.", parent=self.app)
            return
        if messagebox.askyesno("Camera profile", "Delete the profile '%s'?\n%s" % (prof["name"], prof["file"]),
                               parent=self.app):
            PR.delete(prof)
            self.app.reload_profiles()

    def _open_folder(self):
        os.makedirs(PR.PROFILE_DIR, exist_ok=True)
        os.startfile(PR.PROFILE_DIR)


INC_COLOR, DEC_COLOR = "#4c78a8", "#b07aa1"      # neutral hues: neither implies better or worse


class SensitivityTab(ttk.Frame):
    """Sensitivity analysis: one layout for all modes - inputs, summary cards, chart / table / details.

    Each mode keeps its own last result; a result whose inputs have changed is marked as not updated.
    """

    MODES = (("advisor", "Improve performance"), ("limiting", "Limiting factors"), ("sweep", "Parameter sweep"),
             ("uncertainty", "Uncertainty"), ("bands", "Range bands"), ("scenarios", "Scenarios"))
    MODE_NAME = dict(MODES)

    def __init__(self, master, app):
        super().__init__(master, padding=(8, 8, 8, 0))
        self.app = app
        self.mode = tk.StringVar(value="limiting")
        self.busy = False
        self._stop = False
        self.results, self.sigs, self.history = {}, {}, []
        self.shown = {}                       # mode -> result currently displayed (latest or from history)
        k = app.k

        bar = ttk.Frame(self)
        bar.pack(fill="x")
        for key, label in self.MODES:
            ttk.Radiobutton(bar, text=label, value=key, variable=self.mode,
                            command=lambda: self.show_mode(self.mode.get())).pack(side="left", padx=(0, 10))
        bar2 = ttk.Frame(self)
        bar2.pack(fill="x", pady=(6, 0))
        self.run_btn = ttk.Button(bar2, text="Run analysis", style="Accent.TButton", command=lambda: self.run())
        self.run_btn.pack(side="left")
        self.stop_btn = ttk.Button(bar2, text="Stop", command=self._request_stop, state="disabled")
        self.stop_btn.pack(side="left", padx=4)
        ttk.Button(bar2, text="Reset", command=self.reset).pack(side="left")
        ttk.Button(bar2, text="Export CSV...", command=self.export_csv).pack(side="left", padx=4)
        ttk.Button(bar2, text="Hebrew PDF report...", command=lambda: self.app.export_report_he()).pack(side="left")
        ttk.Label(bar2, text="Atmosphere", style="Unit.TLabel").pack(side="left", padx=(10, 4))
        self._atm_slots = []
        self.atm_cb = ttk.Combobox(bar2, state="readonly", width=22, postcommand=self._atm_choices)
        self.atm_cb.pack(side="left")
        self.atm_cb.bind("<<ComboboxSelected>>", lambda e: self._set_atm())
        ttk.Label(bar2, text="History", style="Unit.TLabel").pack(side="left", padx=(10, 4))
        self.hist_cb = ttk.Combobox(bar2, state="readonly", width=24)
        self.hist_cb.pack(side="left", fill="x", expand=True)
        self.hist_cb.bind("<<ComboboxSelected>>", lambda e: self._load_history())
        self.state_lbl = autowrap(ttk.Label(self, style="Muted.TLabel", justify="left"))
        self.state_lbl.pack(fill="x", pady=(4, 0))
        self.stale = tk.Label(self, text="Results not updated - the inputs changed since this run. Press 'Run "
                                         "analysis'.", bg="#fff4e0", fg=WARN, font=("Segoe UI Semibold", 9), anchor="w",
                              padx=8, pady=4)

        # inputs (upper, resizable / collapsible) and results (lower)
        self.body = ttk.PanedWindow(self, orient="vertical")
        self.body.pack(fill="both", expand=True, pady=(4, 0))
        self.in_pane = ScrollFrame(self.body, padding=(0, 2, 6, 6))
        self.opts = self.in_pane.inner
        self.body.add(self.in_pane, weight=2)
        res = ttk.Frame(self.body)
        self.body.add(res, weight=5)
        self.inputs_shown = True
        self.in_btn = ttk.Button(bar2, text="Hide inputs", command=self.toggle_inputs)
        self.in_btn.pack(side="left", padx=(0, 4), before=self.run_btn)
        self.cards = ttk.Frame(res)
        self.cards.pack(fill="x", pady=(4, 2))
        self.method_lbl = autowrap(ttk.Label(res, style="Muted.TLabel", justify="left"))
        self.method_lbl.pack(fill="x")

        self.nb = ttk.Notebook(res)
        self.nb.pack(fill="both", expand=True, pady=(4, 0))
        chart = ttk.Frame(self.nb)
        self.chart_opts = ttk.Frame(chart)
        self.chart_opts.pack(fill="x", pady=(4, 0))
        self.plot = PlotTab(chart)
        self.plot.pack(fill="both", expand=True)
        self.plot.canvas.mpl_connect("pick_event", self._on_pick)
        self.nb.add(chart, text="Chart")
        tfr = ttk.Frame(self.nb)
        self.table = ttk.Treeview(tfr, show="headings")
        xs = ttk.Scrollbar(tfr, orient="horizontal", command=self.table.xview)
        ys = ttk.Scrollbar(tfr, orient="vertical", command=self.table.yview)
        self.table.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.table.pack(fill="both", expand=True)
        self.nb.add(tfr, text="Table")
        self.details = tk.Text(self.nb, wrap="word", relief="flat", font=("Consolas", 9), padx=10, pady=8,
                               background=SURFACE_ALT, highlightthickness=0)
        self.details.tag_configure("h", font=("Segoe UI Semibold", 10))
        self.details.tag_configure("sel", background="#e8f0fe")
        self.nb.add(self.details, text="Calculation details")

        # mode option variables (kept across mode switches)
        # fields that only feed checks or reports (AN.NO_RANGE_EFFECT) are not offered for sweeps
        self.sweep_fields = [(f["path"], "%s: %s" % (page, f["label"].strip()) if not re.search(r"tasks\.\d+\.lp",
                              f["path"]) else "%s: task %d criterion (line pairs)" % (page, int(f["path"].split(".")[2]) + 1),
                              f["unit"])
                             for page, fields in TABS for f in fields
                             if f.get("kind") in ("float", "int") and not f["path"].startswith("measured.") and
                             f["path"] not in AN.NO_RANGE_EFFECT]
        self.sw = {ax: {"param": tk.StringVar(), "from": tk.StringVar(), "to": tk.StringVar(),
                        "n": tk.StringVar(value="7" if ax == "x" else "5"), "sampling": tk.StringVar(value="linear"),
                        "policy": tk.StringVar()} for ax in ("x", "y")}
        self.sw_dim = tk.StringVar(value="1D")
        self.task_var = tk.StringVar()
        self.view_var = tk.StringVar(value="delta")
        self.sort_var = tk.StringVar(value="effect")
        self.chart_kind = tk.StringVar(value="tornado")
        self.adv_open = tk.BooleanVar(value=False)
        self.unc_rows, self.corr = [], []
        self.u_method = tk.StringVar(value="rss")
        self.u_adv = {k: tk.StringVar() for k in ("mc_n", "seed", "coverage", "k", "deriv_step_pct", "morris_r",
                                                  "sobol_n")}
        self.adv_task = tk.StringVar()
        self.adv_minfov = tk.StringVar(value="0")
        self.adv_step = tk.StringVar(value="25")
        self.adv_robust = tk.BooleanVar(value=True)
        self.band_factor = tk.StringVar(value="10")
        self.show_mode("limiting")

    # ------------------------------------------------------------------ state
    def _signature(self, mode, p=None):
        p = copy.deepcopy(p if p is not None else self.app.collect())
        for key in ("provenance", "uncertainty", "scenarios", "name"):
            p.pop(key, None)
        extra = {}
        if mode == "sweep":
            extra = {ax: {k: v.get() for k, v in d.items()} for ax, d in self.sw.items()}
            extra["dim"] = self.sw_dim.get()
        elif mode == "uncertainty":
            extra = self._unc_settings_from_ui(store=False)
        elif mode == "scenarios":
            extra = [s["name"] for s in self.app.project.get("scenarios", [])]
        elif mode == "advisor":
            extra = [self.adv_task.get(), self.adv_minfov.get(), self.adv_step.get(), self.adv_robust.get()]
        elif mode == "bands":
            extra = [self.band_factor.get()]
        return json.dumps([p, extra], sort_keys=True, default=str)

    def check_stale(self, p=None):
        mode = self.mode.get()
        r = self.shown.get(mode)
        stale = r is not None and self.sigs.get(id(r)) is not None and self.sigs[id(r)] != self._signature(mode, p)
        if stale and not self.stale.winfo_ismapped():
            self.stale.pack(fill="x", pady=(4, 0), after=self.state_lbl)
        elif not stale and self.stale.winfo_ismapped():
            self.stale.pack_forget()

    def toggle_inputs(self, show=None):
        show = (not self.inputs_shown) if show is None else show
        if show == self.inputs_shown:
            return
        if show:
            self.body.insert(0, self.in_pane, weight=2)
        else:
            self.body.forget(self.in_pane)
        self.inputs_shown = show
        self.in_btn.configure(text="Hide inputs" if show else "Show inputs")

    def _atm_choices(self):
        """Active atmospheres offered for the analyses (refreshed whenever the list opens or the view changes)."""
        try:
            p = self.app.collect()
        except Exception:
            return
        a = P.deep_merge(P.DEFAULT_PROJECT, p)["atmosphere"]
        if a["mode"] == "spectral":
            self._atm_slots, labels = [0], ["Imported spectral atmosphere"]
        else:
            vis = a["mode"] == "visibility" and p.get("category") == "Visible" or a["mode"] == "weather"
            self._atm_slots = [i for i, at in enumerate(a["atm"]) if at.get("on")]
            labels = [("Atm %d (V %g km)" if vis else "Atm %d (sigma %g/km)") %
                      (i + 1, float(a["atm"][i]["V_km" if vis else "sigma"])) for i in self._atm_slots]
            if a["mode"] == "weather":
                labels = [l[:-1] + ", RH %g %%)" % float(a["atm"][i].get("rh_pct", 50.0))
                          for l, i in zip(labels, self._atm_slots)]
        self.atm_cb.configure(values=labels)
        slot = AN.analysis_slot(p)
        self.atm_cb.set(labels[self._atm_slots.index(slot)] if slot in self._atm_slots else "")

    def _set_atm(self):
        i = self.atm_cb.current()
        if 0 <= i < len(self._atm_slots):
            self.app.project["analysis_atm"] = self._atm_slots[i]
            self.show_mode(self.mode.get())

    def _request_stop(self):
        self._stop = True
        self.state_lbl.configure(text="Stopping after the current model run ...")

    def reset(self):
        mode = self.mode.get()
        self.results.pop(mode, None)
        self.shown.pop(mode, None)
        self.show_mode(mode)

    def clear_all(self):
        """New project / template / profile: results of the old configuration are dropped (history is kept)."""
        self.results, self.shown = {}, {}
        self.unc_rows, self.corr = [], []
        self.show_mode(self.mode.get())

    def _load_history(self):
        i = self.hist_cb.current()
        if 0 <= i < len(self.history):
            h = self.history[::-1][i]
            self.shown[h["mode"]] = h["result"]
            self.show_mode(h["mode"])

    # ------------------------------------------------------------------ inputs per mode
    def show_mode(self, mode):
        if mode not in self.MODE_NAME:
            return
        if self.mode.get() == "uncertainty" and self.unc_rows:
            self._unc_settings_from_ui(store=True)      # keep table edits when the view is rebuilt
        self.unc_rows = []                              # the widgets are destroyed below
        if mode != self.mode.get():
            self.toggle_inputs(True)
        self.mode.set(mode)
        for w in self.opts.winfo_children():
            w.destroy()
        getattr(self, "_opts_" + mode)()
        self._atm_choices()
        self.in_pane.canvas.yview_moveto(0)
        self.display()

    def _section_label(self, parent, text):
        autowrap(ttk.Label(parent, style="Muted.TLabel", justify="left", text=text)).pack(fill="x", anchor="w")

    def _opts_advisor(self):
        self._section_label(self.opts, "Range Improvement Advisor: diagnoses the bottleneck of each task, applies "
                                       "physically consistent what-if changes (lens, aperture, detector, noise, fixed "
                                       "pattern noise, exposure, transmission, stabilization, display) through the "
                                       "same range engine, in the atmosphere chosen above, and "
                                       "ranks the three best materially different actions. Environment changes are "
                                       "shown as scenarios, never as improvements. Advisory only - the project is not "
                                       "changed.")
        fr = ttk.Frame(self.opts)
        fr.pack(fill="x", pady=(6, 0))
        try:
            tasks = [t["name"] for t in self.app.collect()["target"]["tasks"] if t.get("on")]
        except Exception:
            tasks = []
        if self.adv_task.get() not in tasks:
            self.adv_task.set(tasks[-1] if tasks else "")
        ttk.Label(fr, text="Rank by task").grid(row=0, column=0, sticky="w")
        ttk.Combobox(fr, values=tasks, state="readonly", textvariable=self.adv_task, width=16).grid(
            row=0, column=1, sticky="w", padx=(6, 16))
        ttk.Label(fr, text="Minimum FOV (h)").grid(row=0, column=2, sticky="w")
        ttk.Entry(fr, textvariable=self.adv_minfov, width=7).grid(row=0, column=3, sticky="w", padx=(6, 2))
        ttk.Label(fr, text="deg (0 = no limit)", style="Unit.TLabel").grid(row=0, column=4, sticky="w", padx=(0, 16))
        ttk.Label(fr, text="What-if step [%]").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(fr, textvariable=self.adv_step, width=7).grid(row=1, column=1, sticky="w", padx=(6, 2), pady=(4, 0))
        ttk.Checkbutton(fr, text="Paired robustness under assumption ranges (top 3)", variable=self.adv_robust).grid(
            row=1, column=2, columnspan=3, sticky="w", pady=(4, 0))

    def _opts_bands(self):
        self._section_label(self.opts, "Range bands: the DRI ranges of every active atmosphere (weather) and, when "
                                       "turbulence acts, of the turbulence strength divided and multiplied by the "
                                       "factor below - one decade of Cn2 moves visible ranges by about +/-35 %. The "
                                       "band is a scenario envelope, not a probability interval; use 'Uncertainty' "
                                       "for that.")
        fr = ttk.Frame(self.opts)
        fr.pack(fill="x", pady=(6, 0))
        ttk.Label(fr, text="Turbulence factor (Cn2 / f, x f)").pack(side="left")
        ttk.Entry(fr, textvariable=self.band_factor, width=7).pack(side="left", padx=(6, 0))

    def _opts_limiting(self):
        self._section_label(self.opts, "What limits the nominal range? Each degradation of the imaging chain is "
                                       "removed in turn (ideal optics, clear atmosphere, half the temporal noise, ...) "
                                       "and the DRI ranges are recalculated. Standard task criteria are not changed. "
                                       "For input uncertainty use 'Uncertainty'; for design trades use 'Parameter "
                                       "sweep'.")

    def _opts_sweep(self):
        top = ttk.Frame(self.opts)
        top.pack(fill="x")
        ttk.Label(top, text="Sweep").pack(side="left")
        for d in ("1D", "2D"):
            ttk.Radiobutton(top, text=d if d == "1D" else "2D grid (heatmap)", value=d, variable=self.sw_dim,
                            command=lambda: self.show_mode("sweep")).pack(side="left", padx=(8, 0))
        axes = ("x",) if self.sw_dim.get() == "1D" else ("x", "y")
        labels = [l for _, l, _u in self.sweep_fields]
        for ax in axes:
            v = self.sw[ax]
            fr = ttk.Frame(self.opts)
            fr.pack(fill="x", pady=(6, 0))
            fr.columnconfigure(1, weight=1)
            ttk.Label(fr, text="Parameter" if ax == "x" else "Parameter 2").grid(row=0, column=0, sticky="w")
            cb = ttk.Combobox(fr, values=labels, state="readonly", textvariable=v["param"], width=30)
            cb.grid(row=0, column=1, columnspan=7, sticky="we", padx=(6, 0))
            cb.bind("<<ComboboxSelected>>", lambda e, ax=ax: (self._sweep_defaults(ax), self.show_mode("sweep")))
            if not v["param"].get():
                default = "optics.f_mm" if ax == "x" else "atmosphere.atm.0.sigma"
                v["param"].set(next((l for p, l, _u in self.sweep_fields if p == default), labels[0]))
                self._sweep_defaults(ax)
            unit = next((u for p, l, u in self.sweep_fields if l == v["param"].get()), "")
            for i, (lab, key, w) in enumerate((("from", "from", 9), ("to", "to", 9), ("points", "n", 5))):
                ttk.Label(fr, text=lab).grid(row=1, column=2 * i, sticky="w", pady=(4, 0))
                ttk.Entry(fr, textvariable=v[key], width=w).grid(row=1, column=2 * i + 1, sticky="w", padx=(4, 8),
                                                                  pady=(4, 0))
            ttk.Label(fr, text=unit, style="Unit.TLabel").grid(row=1, column=6, sticky="w", pady=(4, 0))
            ttk.Combobox(fr, values=["linear", "log"], state="readonly", textvariable=v["sampling"], width=7).grid(
                row=1, column=7, sticky="e", pady=(4, 0))
            path = self._path_of(v["param"].get())
            pols = AN.policies_for(path)
            if v["policy"].get() not in [l for _, l in pols]:
                v["policy"].set(pols[0][1])
            ttk.Label(fr, text="Hold constant").grid(row=2, column=0, sticky="w", pady=(4, 0))
            ttk.Combobox(fr, values=[l for _, l in pols], state="readonly", textvariable=v["policy"]).grid(
                row=2, column=1, columnspan=7, sticky="we", padx=(6, 0), pady=(4, 0))
        try:
            eng = AN.describe_engine(self.app.collect())
        except Exception:
            eng = ""
        self._section_label(self.opts, "Engine: %s. Every point is a full model recalculation after the hold-constant "
                                       "policy is applied and the configuration is validated; rejected points are "
                                       "listed in the table." % eng)

    def _opts_uncertainty(self):
        s = AN.uncertainty_settings(self.app.collect())
        top = ttk.Frame(self.opts)
        top.pack(fill="x")
        ttk.Label(top, text="Method").pack(side="left")
        self.u_method.set(s["method"])
        ttk.Radiobutton(top, text="RSS approximation (GUM)", value="rss", variable=self.u_method).pack(side="left",
                                                                                                   padx=(8, 0))
        ttk.Radiobutton(top, text="Monte Carlo", value="mc", variable=self.u_method).pack(side="left", padx=(8, 0))
        ttk.Radiobutton(top, text="Global: Morris screening", value="morris", variable=self.u_method).pack(
            side="left", padx=(8, 0))
        ttk.Radiobutton(top, text="Global: Sobol indices", value="sobol", variable=self.u_method).pack(
            side="left", padx=(8, 0))
        ttk.Checkbutton(top, text="Advanced", variable=self.adv_open,
                        command=lambda: self.show_mode("uncertainty")).pack(side="right")
        self._section_label(self.opts, "State what each +/- value means and its distribution. One-at-a-time runs give "
                                       "the range change for each input (tornado); RSS combines standard "
                                       "uncertainties and local sensitivities; Monte Carlo samples all inputs together. "
                                       "The global methods vary all inputs over their +/- intervals at once and "
                                       "capture interactions and regime changes: Morris ranks the inputs with "
                                       "r (k + 1) runs, Sobol splits the range variance with N (k + 2) runs.")
        sf = ScrollFrame(self.opts)
        sf.pack(fill="x")
        sf.canvas.configure(height=int(min(26 * (len(s["inputs"]) + 1), 190) * self.app.k))
        g = sf.inner
        for c, h in enumerate(("", "Input", "+/- %", "Value means", "Distribution")):
            ttk.Label(g, text=h, style="Unit.TLabel").grid(row=0, column=c, sticky="w", padx=2)
        g.columnconfigure(1, weight=1)
        self.unc_rows = []
        mlab, dlab = dict(AN.MEANINGS), dict(AN.DISTRIBUTIONS)
        for i, (path, e) in enumerate(s["inputs"].items(), start=1):
            on = tk.BooleanVar(value=bool(e["on"]))
            pct = tk.StringVar(value=fmt(float(e["pct"])))
            mean = ttk.Combobox(g, values=list(mlab.values()), state="readonly", width=16)
            mean.set(mlab.get(e["meaning"], mlab["bound"]))
            dist = ttk.Combobox(g, values=list(dlab.values()), state="readonly", width=10)
            dist.set(dlab.get(e["dist"], "Normal"))
            ttk.Checkbutton(g, variable=on).grid(row=i, column=0)
            ttk.Label(g, text=e["label"]).grid(row=i, column=1, sticky="w")
            ttk.Entry(g, textvariable=pct, width=6).grid(row=i, column=2, sticky="w", padx=2)
            mean.grid(row=i, column=3, sticky="w", padx=2)
            dist.grid(row=i, column=4, sticky="w", padx=2)
            self.unc_rows.append((path, e["label"], on, pct, mean, dist))
        self.corr = [list(c) for c in s["correlations"]]
        if self.adv_open.get():
            adv = ttk.Frame(self.opts)
            adv.pack(fill="x", pady=(6, 0))
            for key, val in (("mc_n", s["mc_n"]), ("seed", s["seed"]), ("coverage", 100 * float(s["coverage"])),
                             ("k", s["k"]), ("deriv_step_pct", s["deriv_step_pct"]), ("morris_r", s["morris_r"]),
                             ("sobol_n", s["sobol_n"])):
                self.u_adv[key].set(fmt(val))
            for i, (key, lab) in enumerate((("mc_n", "MC samples"), ("seed", "Random seed"), ("coverage", "Coverage %"),
                                            ("k", "Coverage factor k"), ("deriv_step_pct", "Derivative step %"),
                                            ("morris_r", "Morris trajectories r"), ("sobol_n", "Sobol base samples N"))):
                ttk.Label(adv, text=lab).grid(row=i // 3, column=2 * (i % 3), sticky="w", pady=2)
                ttk.Entry(adv, textvariable=self.u_adv[key], width=7).grid(row=i // 3, column=2 * (i % 3) + 1,
                                                                          sticky="w", padx=(4, 12))
            cf = ttk.Frame(self.opts)
            cf.pack(fill="x", pady=(6, 0))
            ttk.Label(cf, text="Correlations (linked inputs)", style="Head.TLabel").grid(row=0, column=0, columnspan=5,
                                                                                      sticky="w")
            names = [l for _p, l, *_r in self.unc_rows]
            ca = ttk.Combobox(cf, values=names, state="readonly", width=18)
            cb = ttk.Combobox(cf, values=names, state="readonly", width=18)
            rho = tk.StringVar(value="1")
            ca.grid(row=1, column=0, sticky="w")
            cb.grid(row=1, column=1, sticky="w", padx=4)
            ttk.Label(cf, text="rho").grid(row=1, column=2)
            ttk.Entry(cf, textvariable=rho, width=5).grid(row=1, column=3, padx=4)
            lb = tk.Listbox(cf, height=3, font=("Segoe UI", 9), relief="flat", highlightthickness=1,
                            highlightbackground=BORDER)
            lb.grid(row=2, column=0, columnspan=5, sticky="we", pady=(4, 0))
            cf.columnconfigure(4, weight=1)
            lab_of = {p: l for p, l, *_r in self.unc_rows}
            path_of = {l: p for p, l, *_r in self.unc_rows}

            def fill():
                lb.delete(0, "end")
                for a, b, r in self.corr:
                    lb.insert("end", "%s  <->  %s   rho = %g" % (lab_of.get(a, a), lab_of.get(b, b), r))

            def add():
                try:
                    r = max(-1.0, min(1.0, float(rho.get())))
                except ValueError:
                    return
                if ca.get() and cb.get() and ca.get() != cb.get():
                    self.corr.append([path_of[ca.get()], path_of[cb.get()], r])
                    fill()

            def remove():
                for i in reversed(lb.curselection()):
                    del self.corr[i]
                fill()
            ttk.Button(cf, text="Add", command=add).grid(row=1, column=4, sticky="w")
            ttk.Button(cf, text="Remove selected", command=remove).grid(row=3, column=0, sticky="w", pady=(4, 0))
            fill()

    def _opts_scenarios(self):
        fr = ttk.Frame(self.opts)
        fr.pack(fill="x")
        self._section_label(fr, "Save baseline configurations and compare their DRI ranges. The first scenario is the "
                                "reference for the deltas. Scenarios are stored in the project file.")
        self.scen_lb = tk.Listbox(fr, height=4, font=("Segoe UI", 9), relief="flat", highlightthickness=1,
                                  highlightbackground=BORDER, selectmode="extended")
        self.scen_lb.pack(fill="x", pady=(4, 4))
        for s in self.app.project.get("scenarios", []):
            self.scen_lb.insert("end", s["name"])
        b = ttk.Frame(fr)
        b.pack(fill="x")
        ttk.Button(b, text="Add current configuration...", command=self._scen_add).pack(side="left")
        ttk.Button(b, text="Remove selected", command=self._scen_remove).pack(side="left", padx=4)
        ttk.Button(b, text="Load selected into the editor", command=self._scen_load).pack(side="left")

    def _scen_add(self):
        name = simpledialog.askstring("Scenario", "Name of the scenario:", parent=self.app,
                                      initialvalue=self.app.project.get("name", ""))
        if not name:
            return
        snap = copy.deepcopy(self.app.collect())
        snap.pop("scenarios", None)
        self.app.project.setdefault("scenarios", []).append({"name": name, "project": snap})
        self.app._schedule_dirty_check()
        self.show_mode("scenarios")

    def _scen_remove(self):
        sc = self.app.project.get("scenarios", [])
        for i in reversed(self.scen_lb.curselection()):
            del sc[i]
        self.app._schedule_dirty_check()
        self.show_mode("scenarios")

    def _scen_load(self):
        sel = self.scen_lb.curselection()
        if not sel:
            return
        sc = self.app.project.get("scenarios", [])
        new = copy.deepcopy(sc[sel[0]]["project"])
        new["scenarios"] = sc
        self.app._load_into_form(new, saved=False)
        self.app.status.set("Scenario '%s' loaded into the editor" % sc[sel[0]]["name"])

    # ------------------------------------------------------------------ helpers
    def _path_of(self, label):
        return next((p for p, l, _u in self.sweep_fields if l == label), None)

    def _unit_of(self, path):
        return next((u for p, l, u in self.sweep_fields if p == path), "")

    def _label_of(self, path):
        return next((l for p, l, u in self.sweep_fields if p == path), path)

    def _sweep_defaults(self, ax):
        v = self.sw[ax]
        path = self._path_of(v["param"].get())
        try:
            x = float(get_path(self.app.collect(), path))
        except (KeyError, ValueError, TypeError, IndexError):
            x = 1.0
        lo, hi = (x * 0.5, x * 1.5) if x else (0.0, 1.0)
        v["from"].set(fmt(lo))
        v["to"].set(fmt(hi))
        v["policy"].set(AN.policies_for(path)[0][1])

    def _unc_settings_from_ui(self, store=True):
        if not self.unc_rows:
            return AN.uncertainty_settings(self.app.project)
        minv, dinv = {l: k for k, l in AN.MEANINGS}, {l: k for k, l in AN.DISTRIBUTIONS}
        inputs = {}
        for path, label, on, pct, mean, dist in self.unc_rows:
            try:
                pv = abs(float(pct.get()))
            except ValueError:
                pv = 0.0
            inputs[path] = {"on": bool(on.get()), "pct": pv, "meaning": minv.get(mean.get(), "bound"),
                            "dist": dinv.get(dist.get(), "normal")}
        s = dict(AN.uncertainty_settings(self.app.project))
        s.pop("inputs", None)
        s["method"] = self.u_method.get()
        for key, conv in (("mc_n", int), ("seed", int), ("coverage", float), ("k", float), ("deriv_step_pct", float),
                          ("morris_r", int), ("sobol_n", int)):
            try:
                val = conv(float(self.u_adv[key].get())) if self.u_adv[key].get() else None
            except ValueError:
                val = None
            if val is not None:
                s[key] = val / 100.0 if key == "coverage" else val
        s["correlations"] = [list(c) for c in self.corr]
        s["inputs"] = inputs
        if store:
            self.app.project["uncertainty"] = copy.deepcopy(s)
        return s

    # ------------------------------------------------------------------ run
    def run(self, mode=None):
        if mode:
            try:
                self.app.right.select(self)
            except tk.TclError:
                pass
            self.show_mode(mode)
        if self.busy:
            return
        mode = self.mode.get()
        if mode == "uncertainty":
            self._unc_settings_from_ui(store=True)
        try:
            p = self.app.collect(strict=True)
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e), parent=self.app)
            return
        if p["mode"]["environment"] != "field":
            messagebox.showinfo("Sensitivity", "Range analyses need 'Field performance' (General page).",
                                parent=self.app)
            return
        sig = self._signature(mode, p)
        try:
            job = self._job(mode, p)
        except ValueError as e:
            messagebox.showerror(self.MODE_NAME[mode], str(e), parent=self.app)
            return
        self.busy, self._stop = True, False
        self.run_btn.state(["disabled"])
        self.stop_btn.state(["!disabled"])
        self.app.configure(cursor="watch")
        t0 = time.time()

        def progress(msg, frac=None):
            msg = "%s  -  %s elapsed" % (msg, time.strftime("%M:%S", time.gmtime(time.time() - t0)))
            self.after(0, lambda: (self.state_lbl.configure(text=msg),
                                   frac is not None and self.app.prog.configure(value=frac)))

        def work():
            try:
                r = job(progress, lambda: self._stop)
                r["elapsed_s"] = time.time() - t0
                self.after(0, lambda: self._done(mode, r, None, sig))
            except AN.AnalysisCancelled:
                self.after(0, lambda: self._done(mode, None, "cancelled", sig))
            except Exception as e:          # ModelError and anything unexpected
                err = str(e) if isinstance(e, (ModelError, ValueError)) else traceback.format_exc()
                self.after(0, lambda: self._done(mode, None, err, sig))

        threading.Thread(target=work, daemon=True).start()

    def _job(self, mode, p):
        if mode == "advisor":
            try:
                fov, step = float(self.adv_minfov.get() or 0), float(self.adv_step.get() or 25) / 100.0
            except ValueError:
                raise ValueError("Enter a numeric minimum FOV and what-if step.")
            if not 0.02 <= step <= 1.0:
                raise ValueError("The what-if step must be between 2 and 100 %.")
            task, rob = self.adv_task.get() or None, bool(self.adv_robust.get())
            return lambda prog, stop: ADV.advise(p, prog, stop=stop, rank_task=task, min_fov_deg=fov, step=step,
                                                 robustness=rob)
        if mode == "limiting":
            return lambda prog, stop: AN.limiting_factors(p, prog, stop=stop)
        if mode == "bands":
            try:
                fac = float(self.band_factor.get())
            except ValueError:
                raise ValueError("Enter a numeric turbulence factor.")
            return lambda prog, stop: AN.range_bands(p, prog, stop=stop, factor=fac)
        if mode == "uncertainty":
            if not AN.items_from_settings(AN.uncertainty_settings(p)):
                raise ValueError("Tick at least one input with a non-zero uncertainty.")
            return lambda prog, stop: AN.run_uncertainty(p, prog, stop=stop)
        if mode == "scenarios":
            sc = [(s["name"], P.deep_merge(P.DEFAULT_PROJECT, s["project"])) for s in p.get("scenarios", [])]
            if not sc:
                raise ValueError("Add at least one scenario (the current configuration can be added).")
            cur = copy.deepcopy(p)
            cur.pop("scenarios", None)
            sc = sc + [("(current editor state)", cur)]
            return lambda prog, stop: AN.compare_scenarios(sc, prog, stop=stop)
        spec = []
        for ax in (("x",) if self.sw_dim.get() == "1D" else ("x", "y")):
            v = self.sw[ax]
            path = self._path_of(v["param"].get())
            if not path:
                raise ValueError("Choose the parameter to sweep.")
            try:
                lo, hi, n = float(v["from"].get()), float(v["to"].get()), int(float(v["n"].get()))
            except ValueError:
                raise ValueError("Enter numeric 'from', 'to' and 'points'.")
            if n > (40 if ax == "x" and self.sw_dim.get() == "1D" else 12):
                raise ValueError("Too many points (max. 40 for 1D, 12 x 12 for 2D).")
            vals = AN.grid(lo, hi, n, v["sampling"].get())
            pol = next(k for k, l in AN.policies_for(path) if l == v["policy"].get())
            spec.append((path, vals, pol, v["sampling"].get()))
        if len(spec) == 1:
            path, vals, pol, smp = spec[0]
            return lambda prog, stop: AN.sweep(p, path, vals, prog, policy=pol, stop=stop, sampling=smp)
        (px, vx, polx, _s), (py, vy, poly, _s2) = spec
        return lambda prog, stop: AN.sweep2d(p, px, vx, py, vy, prog, polx, poly, stop=stop)

    def _done(self, mode, r, err, sig):
        self.busy = False
        self.run_btn.state(["!disabled"])
        self.stop_btn.state(["disabled"])
        self.app.configure(cursor="")
        self.app.prog.configure(value=0)
        if mode == "advisor":                          # a Hebrew report may be waiting for this run
            self.after_idle(lambda: self.app._advisor_finished(r, err))
        if err == "cancelled":
            self.state_lbl.configure(text="Analysis stopped - previous results kept.")
            return
        if err:
            self.state_lbl.configure(text="Analysis failed")
            messagebox.showerror("Sensitivity analysis", err, parent=self.app)
            return
        self.results[mode] = r
        self.shown[mode] = r
        self.sigs[id(r)] = sig
        self.app.analyses[r["kind"] if r["kind"] in ("sweep2d", "global") else mode] = r
        label = "%s  %s" % (time.strftime("%H:%M:%S"), self.MODE_NAME[mode])
        if r["kind"] == "sweep":
            label += ": " + r["path"].split(".")[-1]
        elif r["kind"] == "sweep2d":
            label += ": %s x %s" % (r["px"].split(".")[-1], r["py"].split(".")[-1])
        elif r["kind"] == "uncertainty":
            label += " (%s)" % ("MC" if r["method"] == "mc" else "RSS")
        elif r["kind"] == "global":
            label += " (%s)" % r["method"].capitalize()
        elif r["kind"] == "advisor":
            label += ": " + r["rank_task"]
        self.history.append({"mode": mode, "result": r, "label": label})
        self.history = self.history[-30:]
        self.hist_cb.configure(values=[h["label"] for h in self.history[::-1]])
        self.hist_cb.current(0)
        self.state_lbl.configure(text="Done in %.1f s." % r.get("elapsed_s", 0))
        if self.mode.get() != mode:
            self.show_mode(mode)
        else:
            self.display()
        self.toggle_inputs(False)               # give the results the full height; 'Show inputs' brings them back
        if self.app.result:
            self.app._show_summary(self.app.result)

    _KIND_MODE = {"advisor": "advisor", "limiting": "limiting", "sweep": "sweep", "sweep2d": "sweep", "uncertainty": "uncertainty",
                  "global": "uncertainty", "bands": "bands", "scenarios": "scenarios"}

    def is_stale(self, r, p=None):
        sig = self.sigs.get(id(r))
        return sig is None or sig != self._signature(self._KIND_MODE.get(r.get("kind"), "limiting"), p)

    # ------------------------------------------------------------------ display
    def _tasks(self, r):
        return list(r.get("base") or {}) or r.get("tasks", [])

    def display(self):
        mode = self.mode.get()
        r = self.shown.get(mode)
        for w in self.cards.winfo_children():
            w.destroy()
        for w in self.chart_opts.winfo_children():
            w.destroy()
        self.table.delete(*self.table.get_children())
        self.table.configure(columns=())
        self.details.delete("1.0", "end")
        self.check_stale()
        if r is None:
            self.method_lbl.configure(text="")
            self.plot.placeholder("No %s result yet - set the inputs above and press 'Run analysis'." %
                                  self.MODE_NAME[mode].lower())
            return
        tasks = self._tasks(r)
        if self.task_var.get() not in tasks and tasks:
            self.task_var.set(tasks[-1])
        getattr(self, "_show_" + r["kind"])(r, tasks)

    def _outcome_selector(self, tasks):
        ttk.Label(self.chart_opts, text="Outcome").pack(side="left")
        cb = ttk.Combobox(self.chart_opts, values=tasks, state="readonly", textvariable=self.task_var, width=14)
        cb.pack(side="left", padx=(4, 10))
        cb.bind("<<ComboboxSelected>>", lambda e: self.display())

    def _card_row(self, items):
        g = self.cards
        for c in range(len(items)):
            g.columnconfigure(c, weight=1, uniform="sc")
        for i, (title, value, sub, color) in enumerate(items):
            c = tk.Frame(g, bg=SURFACE_ALT, highlightthickness=1, highlightbackground=BORDER)
            c.grid(row=0, column=i, sticky="nsew", padx=(0, 6))
            tk.Frame(c, bg=color, height=3).pack(fill="x")
            tk.Label(c, text=title, font=("Segoe UI", 9), fg=MUTED, bg=SURFACE_ALT, anchor="w").pack(fill="x", padx=8,
                                                                                                   pady=(4, 0))
            tk.Label(c, text=value, font=("Segoe UI Semibold", 13), fg=color, bg=SURFACE_ALT, anchor="w").pack(
                fill="x", padx=8)
            autowrap(tk.Label(c, text=sub, font=("Segoe UI", 8), fg=MUTED, bg=SURFACE_ALT, anchor="w",
                              justify="left")).pack(fill="x", padx=8, pady=(0, 6))

    def _fill_table(self, cols, rows, widths=None):
        ids = ["c%d" % i for i in range(len(cols))]
        self.table.configure(columns=ids)
        for i, c in enumerate(cols):
            self.table.heading(ids[i], text=c, anchor="w")
            self.table.column(ids[i], width=int((widths[i] if widths else 90) * self.app.k), stretch=False, anchor="w")
        for r in rows:
            self.table.insert("", "end", values=r)

    def _details(self, sections):
        for title, lines in sections:
            self.details.insert("end", title + "\n", "h")
            for l in lines:
                self.details.insert("end", "  " + l + "\n")
            self.details.insert("end", "\n")

    @staticmethod
    def _f(v, spec="%.3f"):
        return "-" if v is None or (isinstance(v, float) and not np.isfinite(v)) else spec % v

    # --- range improvement advisor
    def _show_advisor(self, r, tasks):
        t = r["rank_task"]
        b = r["baseline"]
        top = [ADV.action_by_id(r, a) for a in r["top"]]
        cards = [("Baseline %s" % t, "%.3f km" % r["base"][t], "%s | %s" % (b["baseline_id"],
                                                                          r["diagnosis"][t]["label"]), MUTED)]
        for i, a in enumerate(top):
            x = a["results"][t]
            cards.append(("#%d %s" % (i + 1, a["label"].split(":")[0]), "%.3f km (%+.1f %%)" % (x["after"], x["gain_pct"]),
                          "%s | %s" % (ADV.SUPPORT[a["support"]], a["tradeoffs"][0] if a["tradeoffs"] else ""),
                          TASK_COLORS[i % len(TASK_COLORS)]))
        if not top:
            cards.append(("No ranked action", "measure first", "see Calculation details", WARN))
        self._card_row(cards)
        w = r.get("weather") or {}
        self.method_lbl.configure(text="Primary bottleneck candidate (%s): %s - %s. Ranked in %s.%s Advisory only: "
                                       "uncalibrated model predictions." % (
                                           t, r["diagnosis"][t]["label"], "; ".join(r["diagnosis"][t]["reasons"]),
                                           w.get("atmosphere", "atm 1"),
                                           " The best action changes with the weather - see the gains per atmosphere "
                                           "in Calculation details." if w.get("depends") else ""))
        ax = self.plot.axes(1, 1)[0]
        ok = [a for a in r["actions"] if a["ok"]]
        ok.sort(key=lambda a: a["results"][t]["gain_pct"] or 0.0)
        for i, a in enumerate(ok):
            g = a["results"][t]["gain_pct"] or 0.0
            col = ACCENT if a["rank"] else ("#c3c9d4" if a["kind"] != "environment" else "#e8d5b5")
            ax.barh(i, g, color=col, hatch="//" if a["kind"] == "environment" or a.get("constraint") else None,
                    edgecolor="white")
            ax.annotate("%+.1f %%  (%.2f km)%s" % (g, a["results"][t]["after"],
                                                   "  #%d" % a["rank"] if a["rank"] else ""),
                        xy=(max(g, 0), i), xytext=(4, 0), textcoords="offset points", va="center", fontsize=7)
        ax.set_yticks(np.arange(len(ok)))
        ax.set_yticklabels([("[scenario] " if a["kind"] == "environment" else "") + a["label"][:60] for a in ok],
                           fontsize=7)
        ax.axvline(0, color="#555", lw=0.8)
        ax.set_xlabel("%s range change vs baseline %.3f km [%%]" % (t, r["base"][t]))
        ax.set_title("What-if actions through the range engine (blue: top 3; hatched: scenario / constraint)")
        ax.grid(alpha=0.3, axis="x")
        self.plot.draw()
        cols = ["#", "Action", "Kind", "Evidence"] + ["%s km" % x for x in tasks] + ["d%s %%" % x[0] for x in tasks] + \
            ["FOV deg", "Pareto", "Trade-offs / notes"]
        rows = []
        order = lambda a: (a["rank"] or 99, -(a["results"][t]["gain_pct"] or 0) if a["ok"] else 1e9)   # noqa: E731
        for a in sorted(r["actions"], key=order):
            if a["ok"]:
                rows.append([a["rank"] or "", a["label"], ADV.KIND[a["kind"]], ADV.SUPPORT[a["support"]]] +
                            ["%.3f" % a["results"][x]["after"] for x in tasks] +
                            [self._f(a["results"][x]["gain_pct"], "%+.1f") for x in tasks] +
                            ["%.3f" % a["geometry"].get("fov_h_deg", float("nan")), "yes" if a.get("pareto") else "",
                             "; ".join(([a["constraint"]] if a.get("constraint") else []) + a["tradeoffs"] + a["notes"])])
            else:
                rows.append(["", a["label"], ADV.KIND[a["kind"]], "rejected"] + ["-"] * (2 * len(tasks)) +
                            ["", "", a["reason"]])
        self._fill_table(cols, rows, [30, 330, 120, 130] + [75] * len(tasks) + [55] * len(tasks) + [65, 55, 600])
        self._details([("Range Improvement Advisor", ADV.format_text(r))])

    # --- limiting factors
    def _show_limiting(self, r, tasks):
        self._card_row([(t, "%.3f km" % r["base"][t], "limited by: %s" % r["limit_type"].get(t, "-"),
                         TASK_COLORS[i % len(TASK_COLORS)]) for i, t in enumerate(tasks)])
        self.method_lbl.configure(text="Method: %s Dominant limiting factor (ranked by %s): %s." % (
            r["method"], r["rank_task"], r["dominant"] or "none (all gains < 1 %)"))
        ax = self.plot.axes(1, 1)[0]
        rows = r["rows"][::-1]
        y = np.arange(len(rows))
        hgt = 0.8 / max(len(tasks), 1)
        for i, t in enumerate(tasks):
            ax.barh(y + i * hgt - 0.4 + hgt / 2, [x["gain_pct"][t] for x in rows], height=hgt,
                    color=TASK_COLORS[i % len(TASK_COLORS)], label="%s (%.2f km)" % (t, r["base"][t]))
        ax.set_yticks(y)
        ax.set_yticklabels([x["factor"] for x in rows], fontsize=8)
        ax.axvline(0, color="#555", lw=0.8)
        ax.set_xlabel("range gain when the degradation is removed [%]")
        ax.set_title("What limits the nominal range (ranked by %s)" % r["rank_task"])
        ax.grid(alpha=0.3, axis="x")
        ax.legend(fontsize=8)
        self.plot.draw()
        self._fill_table(["Factor removed"] + ["%s gain %%" % t for t in tasks] + ["%s km" % t for t in tasks],
                         [[x["factor"]] + ["%+.1f" % x["gain_pct"][t] for t in tasks] +
                          ["%.3f" % x["ranges"][t] for t in tasks] for x in r["rows"]],
                         [260] + [95] * (2 * len(tasks)))
        self._details([("Method", [r["method"], "Engine: " + r["engine"], "Calculated: " + r["time"]]),
                       ("Limit type per task (nominal configuration)",
                        ["%s: %s" % kv for kv in r["limit_type"].items()]),
                       ("Interpretation", ["A large gain means the degradation strongly limits the range. This is a "
                                           "performance bottleneck review - not an uncertainty statement."])])

    # --- 1D sweep
    def _show_sweep(self, r, tasks):
        unit = self._unit_of(r["path"])
        ok = [x for x in r["runs"] if x["ok"]]
        cards = []
        for i, t in enumerate(tasks):
            vals = [x["ranges"][t] for x in ok]
            sub = "over the sweep: %.3f - %.3f km" % (min(vals), max(vals)) if vals else "no valid point"
            cards.append((t, "%.3f km" % r["base"][t], "baseline (%s = %g %s); %s" % (
                r["path"].split(".")[-1], r["base_value"], unit, sub), TASK_COLORS[i % len(TASK_COLORS)]))
        self._card_row(cards)
        nbad = sum(1 for x in r["runs"] if not x["ok"])
        self.method_lbl.configure(text="DRI range vs %s - %s; %s sampling, %d point(s)%s." % (
            self._label_of(r["path"]), r["policy_label"], r["sampling"], len(r["runs"]),
            ", %d rejected" % nbad if nbad else ""))
        ax = self.plot.axes(1, 1)[0]
        for i, t in enumerate(tasks):
            xs = [x["value"] for x in ok]
            ax.plot(xs, [x["ranges"][t] for x in ok], "o-", color=TASK_COLORS[i % len(TASK_COLORS)], label=t)
            ax.plot([r["base_value"]], [r["base"][t]], "D", color=TASK_COLORS[i % len(TASK_COLORS)], ms=8,
                    mfc="white", mew=2)
        for x in r["runs"]:
            if not x["ok"]:
                ax.axvline(x["value"], color="#b54708", ls=":", lw=1)
        if r["base_value"] is not None:
            ax.axvline(r["base_value"], color="grey", ls="--", lw=1, label="baseline")
        if r["sampling"] == "log":
            ax.set_xscale("log")
        ax.set_xlabel("%s%s" % (self._label_of(r["path"]), " [%s]" % unit if unit else ""))
        ax.set_ylabel("range [km]")
        ax.set_title("DRI range vs parameter (diamonds: baseline; dotted: rejected points)")
        ax.grid(alpha=0.3, which="both")
        ax.legend(fontsize=8)
        self.plot.draw()
        cols = ["%s [%s]" % (r["path"].split(".")[-1], unit) if unit else r["path"].split(".")[-1]] + \
            ["%s km" % t for t in tasks] + ["d%s %%" % t[0] for t in tasks] + ["valid", "diagnostics"]
        rows = [["%g (baseline)" % r["base_value"]] + ["%.3f" % r["base"][t] for t in tasks] + ["0"] * len(tasks) +
                ["yes", ""]]
        for x in r["runs"]:
            rows.append(["%.5g" % x["value"]] + [self._f(x["ranges"].get(t)) for t in tasks] +
                        [self._f(x["delta_pct"][t], "%+.1f") for t in tasks] + ["yes" if x["ok"] else "NO",
                                                                                "; ".join(x["diag"])])
        self._fill_table(cols, rows, [110] + [80] * len(tasks) + [60] * len(tasks) + [50, 400])
        self._details([("Method", [r["method"], "Engine: " + r["engine"], "Calculated: %s, %.1f s" % (
            r["time"], r.get("elapsed_s", 0))]),
            ("Hold-constant assumptions", [r["policy_label"]] + r["policy_notes"]),
            ("Rejected / flagged points", ["%.5g: %s" % (x["value"], "; ".join(x["diag"])) for x in r["runs"]
                                           if x["diag"]] or ["none"])])

    # --- 2D sweep
    def _show_sweep2d(self, r, tasks):
        self._outcome_selector(tasks)
        t = self.task_var.get()
        g = r["ranges"][t]
        self._card_row([(tt, "%.3f km" % r["base"][tt], "grid: %s - %s km" % (
            self._f(np.nanmin(r["ranges"][tt]) if np.isfinite(r["ranges"][tt]).any() else None),
            self._f(np.nanmax(r["ranges"][tt]) if np.isfinite(r["ranges"][tt]).any() else None)),
            TASK_COLORS[i % len(TASK_COLORS)]) for i, tt in enumerate(tasks)])
        self.method_lbl.configure(text="2-D grid: %s x %s, full recalculation per cell; %d invalid combination(s)." % (
            self._label_of(r["px"]), self._label_of(r["py"]), len(r["invalid"])))
        ax = self.plot.axes(1, 1)[0]
        vx, vy = np.array(r["vx"]), np.array(r["vy"])
        m = np.ma.masked_invalid(g)
        im = ax.pcolormesh(np.arange(len(vx) + 1), np.arange(len(vy) + 1), m, cmap="viridis", shading="flat")
        for j in range(len(vy)):
            for i in range(len(vx)):
                v = g[j, i]
                ax.text(i + 0.5, j + 0.5, "%.2f" % v if np.isfinite(v) else "invalid", ha="center", va="center",
                        fontsize=7, color="white" if np.isfinite(v) else "#b54708")
        ax.set_xticks(np.arange(len(vx)) + 0.5)
        ax.set_xticklabels(["%.3g" % v for v in vx], fontsize=8)
        ax.set_yticks(np.arange(len(vy)) + 0.5)
        ax.set_yticklabels(["%.3g" % v for v in vy], fontsize=8)
        ax.set_xlabel(self._label_of(r["px"]))
        ax.set_ylabel(self._label_of(r["py"]))
        ax.set_title("%s range [km]  (baseline %.3g / %.3g: %.3f km)" % (t, r["base_x"], r["base_y"], r["base"][t]))
        self.plot.fig.colorbar(im, ax=ax, label="range [km]")
        self.plot.draw()
        self._fill_table(["%s \\ %s" % (r["py"].split(".")[-1], r["px"].split(".")[-1])] + ["%.4g" % v for v in vx],
                         [["%.4g" % y] + [self._f(g[j, i]) for i in range(len(vx))] for j, y in enumerate(vy)],
                         [120] + [70] * len(vx))
        self._details([("Method", ["Full model recalculation per grid cell", "Engine: " + r["engine"],
                                   "Policies: %s / %s" % (r["policy_x"], r["policy_y"]), "Calculated: " + r["time"]]),
                       ("Invalid combinations", r["invalid"] or ["none"])])

    # --- uncertainty
    def _show_uncertainty(self, r, tasks):
        self._outcome_selector(tasks)
        ttk.Label(self.chart_opts, text="Chart").pack(side="left")
        kinds = [("tornado", "Tornado (-/+ runs)")] + ([("hist", "MC distribution")] if "mc" in r else [])
        kcb = ttk.Combobox(self.chart_opts, values=[l for _, l in kinds], state="readonly", width=17)
        kcb.set(dict(kinds).get(self.chart_kind.get(), kinds[0][1]))
        kcb.pack(side="left", padx=(4, 10))
        kcb.bind("<<ComboboxSelected>>", lambda e: (self.chart_kind.set(next(k for k, l in kinds if l == kcb.get())),
                                                    self.display()))
        if self.chart_kind.get() not in dict(kinds):
            self.chart_kind.set("tornado")
        ttk.Label(self.chart_opts, text="View").pack(side="left")
        vcb = ttk.Combobox(self.chart_opts, values=["delta km", "absolute km"], state="readonly", width=11)
        vcb.set("delta km" if self.view_var.get() == "delta" else "absolute km")
        vcb.pack(side="left", padx=(4, 10))
        vcb.bind("<<ComboboxSelected>>", lambda e: (self.view_var.set("delta" if vcb.get() == "delta km" else "abs"),
                                                    self.display()))
        ttk.Label(self.chart_opts, text="Sort").pack(side="left")
        sorts = [("effect", "max |range change|"), ("elasticity", "normalized sensitivity"),
                 ("contrib", "uncertainty contribution")]
        scb = ttk.Combobox(self.chart_opts, values=[l for _, l in sorts], state="readonly", width=21)
        scb.set(dict(sorts)[self.sort_var.get()])
        scb.pack(side="left", padx=(4, 0))
        scb.bind("<<ComboboxSelected>>", lambda e: (self.sort_var.set(next(k for k, l in sorts if l == scb.get())),
                                                    self.display()))
        t = self.task_var.get()
        cards = []
        for i, tt in enumerate(tasks):
            lo, hi, txt = AN.interval(r, tt)
            olo, ohi = AN.oat_envelope(r, tt)
            cards.append((tt, "%.3f km" % r["base"][tt], "%s\nOAT runs span %.3f - %.3f km (not a probability "
                                                          "interval)" % (txt, olo, ohi), TASK_COLORS[i % len(TASK_COLORS)]))
        self._card_row(cards)
        self.method_lbl.configure(text="Interval: %s.  Click a tornado bar for its runs." % r["label"])
        R0 = r["base"][t]
        key = {"effect": lambda x: max(abs(x["low"][t] - R0), abs(x["high"][t] - R0)),
               "elasticity": lambda x: abs(x["elasticity"][t]), "contrib": lambda x: abs(x["contrib"][t])}
        rows = sorted(r["rows"], key=key[self.sort_var.get()])
        self._tornado_rows = rows
        ax = self.plot.axes(1, 1)[0]
        if self.chart_kind.get() == "hist" and "mc" in r and t in r["mc"]:
            m = r["mc"][t]
            ax.hist(m["samples"], bins=30, color=INC_COLOR, alpha=0.75)
            for v, ls, lab in ((m["p_lo"], ":", "P%.1f" % (50 * (1 - r["mc"]["coverage"]))), (m["p50"], "-", "median"),
                               (m["p_hi"], ":", "P%.1f" % (100 - 50 * (1 - r["mc"]["coverage"]))),
                               (R0, "--", "nominal")):
                ax.axvline(v, color="#333" if lab != "nominal" else "#b07aa1", ls=ls, label="%s %.3f km" % (lab, v))
            ax.set_xlabel("%s range [km]" % t)
            ax.set_ylabel("samples")
            ax.set_title("Monte Carlo distribution - %s (%d samples, seed %d)" % (t, r["mc"]["n_ok"], r["mc"]["seed"]))
            ax.legend(fontsize=8)
        else:
            absv = self.view_var.get() == "abs"
            ref = 0.0 if not absv else R0
            span = max([max(abs(x["low"][t] - R0), abs(x["high"][t] - R0)) for x in rows] + [1e-12])
            for i, x in enumerate(rows):
                dl, dh = x["low"][t] - R0, x["high"][t] - R0
                b1 = ax.barh(i, dl, left=ref, color=DEC_COLOR, picker=True)
                b2 = ax.barh(i, dh, left=ref, color=INC_COLOR, picker=True)
                b1.patches[0].row_index = b2.patches[0].row_index = i
                if max(abs(dl), abs(dh)) < 0.01 * span:
                    ax.annotate("below display resolution (%+.2g / %+.2g km)" % (dl, dh), xy=(0.02, i),
                                xycoords=("axes fraction", "data"), va="center", fontsize=7, color=MUTED)
            ax.set_yticks(range(len(rows)))
            ax.set_yticklabels(["%s (+/-%g %%, %s)" % (x["label"], x["pct"], dict(AN.MEANINGS)[x["meaning"]].split(" (")[0])
                                for x in rows], fontsize=8)
            ax.axvline(ref, color="#555", lw=0.8)
            ax.set_xlabel(("%s range [km]" if absv else "range change for %s [km]") % t)
            ax.set_title("Tornado - %s (nominal %.3f km)" % (t, R0))
            from matplotlib.patches import Patch
            ax.legend(handles=[Patch(color=DEC_COLOR, label="input decreased"),
                               Patch(color=INC_COLOR, label="input increased")], fontsize=8, loc="best")
            ax.grid(alpha=0.3, axis="x")
        self.plot.draw()
        cols = ["Input", "nominal", "+/- %", "means", "distribution", "u (1 sigma) %", "%s at -" % t, "%s at +" % t,
                "d- km", "d+ km", "%/% sensitivity", "u contribution %"]
        trows = []
        for x in sorted(r["rows"], key=key[self.sort_var.get()], reverse=True):
            trows.append([x["label"], "%.4g" % x["x0"], "%g" % x["pct"], dict(AN.MEANINGS)[x["meaning"]],
                          x["dist"], "%.2f" % (100 * x["u_rel"]), "%.3f" % x["low"][t], "%.3f" % x["high"][t],
                          "%+.4f" % (x["low"][t] - R0), "%+.4f" % (x["high"][t] - R0),
                          "%+.3f" % x["elasticity"][t], "%.1f" % (100 * x["contrib"][t])])
        self._fill_table(cols, trows, [170, 70, 50, 120, 80, 85, 75, 75, 70, 70, 95, 105])
        rk = lambda f: [x["label"] for x in sorted(r["rows"], key=f, reverse=True)][:3]
        sec = [("Results answer three questions (%s)" % t,
                ["Changes DRI most over the stated perturbation: " + ", ".join(rk(key["effect"])),
                 "Contributes most to the result uncertainty: " + ", ".join(rk(key["contrib"])),
                 "System most sensitive per 1 %% input change: " + ", ".join(rk(key["elasticity"]))]),
               ("Method", ["Interval: " + r["label"],
                           "One-at-a-time: each input at nominal -/+ its stated value, all others nominal; full model "
                           "recalculation. Gives range changes, not a probability interval.",
                           "RSS: u(R)^2 = sum_ij c_i c_j u_i u_j rho_ij with local sensitivities c_i = dR/dx_i "
                           "(central differences, step %g %%) and standard uncertainties u_i from the stated value, its "
                           "meaning and distribution (bound: normal 3 sigma, uniform a/sqrt3, triangular a/sqrt6; 95 %%: "
                           "normal a/1.96)." % r["settings"]["deriv_step_pct"],
                           ("Monte Carlo: %d samples (%d failed), seed %d, Gaussian copula for correlations, coverage "
                            "%.0f %%." % (r["mc"]["n_ok"], r["mc"]["n_fail"], r["mc"]["seed"], 100 * r["mc"]["coverage"]))
                           if "mc" in r else "Monte Carlo: not run.",
                           "Engine: " + r["engine"], "Calculated: %s, %.1f s" % (r["time"], r.get("elapsed_s", 0))]),
               ("Correlations", ["%s <-> %s: rho = %g" % tuple(c) for c in r["correlations"]] or ["none (independent "
                                                                                                 "inputs)"]),
               ("Notes and model safeguards", r["notes"] or ["none"])]
        self._details(sec)

    def _on_pick(self, event):
        i = getattr(event.artist, "row_index", None)
        r = self.shown.get("uncertainty")
        if i is None or r is None or self.mode.get() != "uncertainty":
            return
        x = self._tornado_rows[i]
        tasks = self._tasks(r)
        lines = ["Input %s: nominal %.5g, low %.5g, high %.5g (+/-%g %%, %s, %s)" % (
            x["label"], x["x0"], x["x_low"], x["x_high"], x["pct"], dict(AN.MEANINGS)[x["meaning"]], x["dist"])]
        for t in tasks:
            R0 = r["base"][t]
            lines.append("%-15s nominal %.4f km | low %.4f (%+.4f km, %+.2f %%) | high %.4f (%+.4f km, %+.2f %%)" % (
                t, R0, x["low"][t], x["low"][t] - R0, 100 * (x["low"][t] / R0 - 1), x["high"][t], x["high"][t] - R0,
                100 * (x["high"][t] / R0 - 1)))
        self.details.delete("1.0", "1.0")
        self.details.insert("1.0", "Selected bar\n", "h")
        self.details.insert("2.0", "\n".join("  " + l for l in lines) + "\n\n", "sel")
        self.nb.select(self.details)

    # --- scenarios
    def _show_bands(self, r, tasks):
        self._card_row([(t, "%s - %s km" % (self._f(r["band"][t]["min"], "%.2f"), self._f(r["band"][t]["max"], "%.2f")),
                         "nominal %s km (%s)" % (self._f(r["base"][t], "%.2f"), r["analysis_atm"]),
                         TASK_COLORS[i % len(TASK_COLORS)]) for i, t in enumerate(tasks)])
        self.method_lbl.configure(text="Method: %s Scenario envelope - not a probability interval.%s" % (
            r["method"], " Invalid cases: %s." % ", ".join(r["invalid"]) if r["invalid"] else ""))
        ax = self.plot.axes(1, 1)[0]
        marks = ["o", "s", "^", "D", "v"]
        n_c = len(r["atms"]) * len(r["turb"])
        for i, t in enumerate(tasks):
            col = TASK_COLORS[i % len(TASK_COLORS)]
            b = r["band"][t]
            ax.plot([i, i], [b["min"], b["max"]], color=col, lw=6, alpha=0.25, solid_capstyle="butt")
            k = 0
            for jt, lab in enumerate(r["turb"]):
                for ja, atm in enumerate(r["atms"]):
                    v = r["grid"][t][jt][ja]
                    x = i - 0.25 + 0.5 * (k + 0.5) / n_c
                    ax.plot(x, v, marks[ja % len(marks)], color=col, ms=6, alpha=0.5 + 0.5 * (jt + 1) / len(r["turb"]),
                            label="%s, %s" % (atm, lab) if i == 0 else None)
                    k += 1
            ax.plot([i - 0.3, i + 0.3], [b["nominal"]] * 2, color=col, lw=2)
        ax.set_xticks(range(len(tasks)))
        ax.set_xticklabels(tasks)
        ax.set_yscale("log")
        ax.set_ylabel("range [km]")
        ax.set_title("DRI range bands: weather x turbulence (bar = nominal, %s)" % r["analysis_atm"])
        ax.grid(alpha=0.3, axis="y", which="both")
        ax.legend(fontsize=7, ncol=max(1, len(r["turb"])))
        self.plot.draw()
        rows = [[t, lab] + [self._f(v) for v in row] for t in tasks for lab, row in zip(r["turb"], r["grid"][t])]
        rows += [[t, "band (min - max)", "%s - %s" % (self._f(r["band"][t]["min"]), self._f(r["band"][t]["max"]))]
                 for t in tasks]
        self._fill_table(["Task", "Turbulence"] + ["%s km" % a for a in r["atms"]], rows,
                         [110, 170] + [150] * len(r["atms"]))
        self._details([("Method", [r["method"], "Engine: " + r["engine"], "Calculated: " + r["time"]]),
                       ("Interpretation", ["Weather (extinction / visual range) dominates long-range Detection; "
                                           "turbulence dominates visible Identification. The width of the band says "
                                           "how much a nominal range depends on the scene conditions."])])

    def _show_global(self, r, tasks):
        task = self.task_var.get() if self.task_var.get() in tasks else tasks[-1]
        morris = r["method"] == "morris"
        key = "mu_star" if morris else "ST"
        top = sorted(r["rows"], key=lambda x: -np.nan_to_num(x[key][task], nan=-1.0))
        self._card_row([(t, "%.3f km" % r["base"][t], "top input: %s" % max(
            r["rows"], key=lambda x: np.nan_to_num(x[key][t], nan=-1.0))["label"], TASK_COLORS[i % len(TASK_COLORS)])
            for i, t in enumerate(tasks)])
        self.method_lbl.configure(text="Method: %s; %d model runs%s. %s" % (
            r["label"], r["n_runs"], " (%d invalid)" % r["n_fail"] if r["n_fail"] else "", " ".join(r["notes"])))
        self._outcome_selector(tasks)
        ax = self.plot.axes(1, 1)[0]
        if morris:
            xs = [x["mu_star"][task] for x in r["rows"]]
            ys = [x["sigma"][task] for x in r["rows"]]
            ax.scatter(xs, ys, color=TASK_COLORS[tasks.index(task) % len(TASK_COLORS)])
            for x, y, row in zip(xs, ys, r["rows"]):
                if np.isfinite(x) and np.isfinite(y):
                    ax.annotate(row["label"], (x, y), fontsize=7, xytext=(3, 3), textcoords="offset points")
            lim = max([v for v in xs + ys if np.isfinite(v)] + [1e-6])
            ax.plot([0, lim], [0, lim], color="#999", lw=0.8, ls="--")
            ax.set_xlabel("mu* - mean |elementary effect| over the input interval [km]")
            ax.set_ylabel("sigma - spread of the effects [km]")
            ax.set_title("Morris screening, %s (above the dashed line: interactions / non-linearity)" % task)
        else:
            rows = top[::-1]
            y = np.arange(len(rows))
            ax.barh(y - 0.2, [np.nan_to_num(x["S1"][task]) for x in rows], height=0.4, label="first order S_i")
            ax.barh(y + 0.2, [np.nan_to_num(x["ST"][task]) for x in rows], height=0.4, label="total S_Ti")
            ax.set_yticks(y)
            ax.set_yticklabels([x["label"] for x in rows], fontsize=8)
            ax.axvline(0, color="#555", lw=0.8)
            ax.set_xlabel("share of the range variance")
            ax.set_title("Sobol indices, %s (S_Ti - S_i = interactions)" % task)
            ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        self.plot.draw()
        if morris:
            cols = ["Input", "Interval"] + ["%s mu* km" % t for t in tasks] + ["%s sigma km" % t for t in tasks]
            vals = [[x["label"], "%.4g - %.4g" % (x["lo"], x["hi"])] + [self._f(x["mu_star"][t]) for t in tasks] +
                    [self._f(x["sigma"][t]) for t in tasks] for x in top]
        else:
            cols = ["Input", "Interval"] + ["%s S1" % t for t in tasks] + ["%s ST" % t for t in tasks]
            vals = [[x["label"], "%.4g - %.4g" % (x["lo"], x["hi"])] +
                    ["%s [%s, %s]" % (self._f(x["S1"][t], "%.2f"), self._f(x["S1_ci"][t][0], "%.2f"),
                                      self._f(x["S1_ci"][t][1], "%.2f")) for t in tasks] +
                    ["%s [%s, %s]" % (self._f(x["ST"][t], "%.2f"), self._f(x["ST_ci"][t][0], "%.2f"),
                                      self._f(x["ST_ci"][t][1], "%.2f")) for t in tasks] for x in top]
        self._fill_table(cols, vals, [240, 130] + [120] * (2 * len(tasks)))
        self._details([("Method", [r["label"], "Engine: " + r["engine"], "Calculated: " + r["time"],
                                   "Model runs: %d unique (%d planned)" % (r["n_runs"], r["n_planned"])] + r["notes"]),
                       ("Interpretation", [
                           "Morris: mu* ranks the inputs by their effect over the whole interval; a sigma comparable "
                           "to mu* means the effect depends on the other inputs (regime change, interaction)."
                           if morris else
                           "Sobol: S_i is the share of the range variance explained by the input alone, S_Ti "
                           "includes its interactions; with small N the bootstrap intervals are wide."])])

    def _show_scenarios(self, r, tasks):
        rows = r["rows"]
        self._card_row([(x["name"], " / ".join("%.2f" % x["ranges"][t] for t in tasks) + " km" if x["ok"] else "invalid",
                         " / ".join(tasks), TASK_COLORS[i % len(TASK_COLORS)]) for i, x in enumerate(rows[:4])])
        self.method_lbl.configure(text="Scenario comparison, full recalculation per scenario; deltas relative to '%s'."
                                       % rows[0]["name"])
        ax = self.plot.axes(1, 1)[0]
        ok = [x for x in rows if x["ok"]]
        w = 0.8 / max(len(ok), 1)
        for i, x in enumerate(ok):
            ax.bar(np.arange(len(tasks)) + i * w - 0.4 + w / 2, [x["ranges"][t] for t in tasks], width=w, label=x["name"])
        ax.set_xticks(range(len(tasks)))
        ax.set_xticklabels(tasks)
        ax.set_ylabel("range [km]")
        ax.set_title("DRI ranges per scenario")
        ax.grid(alpha=0.3, axis="y")
        ax.legend(fontsize=8)
        self.plot.draw()
        self._fill_table(["Scenario"] + ["%s km" % t for t in tasks] + ["d%s %%" % t[0] for t in tasks] + ["engine"],
                         [[x["name"]] + [self._f(x["ranges"].get(t)) for t in tasks] +
                          [self._f(x["delta_pct"][t], "%+.1f") for t in tasks] + [x["engine"]] for x in rows],
                         [180] + [80] * len(tasks) + [60] * len(tasks) + [400])
        self._details([("Scenarios", ["%s: %s" % (x["name"], x["engine"] if x["ok"] else "; ".join(x["warnings"]))
                                      for x in rows]),
                       ("Warnings", ["%s: %s" % (x["name"], w) for x in rows for w in x["warnings"]] or ["none"])])

    # ------------------------------------------------------------------ export
    def export_csv(self):
        r = self.shown.get(self.mode.get())
        if r is None:
            messagebox.showinfo("Export CSV", "Run the analysis first.", parent=self.app)
            return
        fn = filedialog.asksaveasfilename(parent=self.app, title="Export analysis as CSV",
                                          initialdir=self.app._start_dir(), defaultextension=".csv",
                                          initialfile="%s - %s.csv" % (self.app.project.get("name") or "TRM",
                                                                       r["kind"]),
                                          filetypes=[("CSV table", "*.csv")])
        if not fn:
            return
        import csv
        with open(fn, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(ADV.to_csv_rows(r) if r["kind"] == "advisor" else AN.to_csv_rows(r))
        self.app.status.set("Analysis exported to %s" % fn)


SRC_STYLE = {"preset": ("preset", "#7b8494", "#eef1f5"), "assumption": ("assumed", "#9a5b00", "#fff1db"),
             "user": ("user", ACCENT, ACCENT_SOFT), "manufacturer": ("datasheet", "#067647", "#e3f5ec"),
             "measurement": ("measured", "#0e7490", "#ddf3f8"), "import": ("import", "#6d28d9", "#efe8fd"),
             "profile": ("profile", "#475569", "#e9edf2")}
NO_BADGE = re.compile(r"^(name|target\.tasks\.\d+\.name|measured\..*|mode\..*|optics\.mtf_(meta|band|focus|temp|uncert)|"
                      r"basic\.roi|detector\.op_mode)$")


class DerivedPanel(tk.Frame):
    """Read-only box with the automatically calculated values and live consistency warnings."""

    def __init__(self, master, k):
        super().__init__(master, bg=SURFACE_ALT, highlightthickness=1, highlightbackground=BORDER)
        top = tk.Frame(self, bg=SURFACE_ALT)
        top.pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(top, text="Calculated automatically (read-only)", font=("Segoe UI Semibold", 9), fg=MUTED,
                 bg=SURFACE_ALT).pack(side="left")
        self.body = tk.Frame(self, bg=SURFACE_ALT)
        self.body.pack(fill="x", padx=12, pady=(0, 8))
        self.body.columnconfigure(1, weight=1)
        self.k = k
        self._sig = None

    def update_values(self, rows, warns):
        sig = (tuple(rows), tuple(warns))
        if sig == self._sig:
            return
        self._sig = sig
        for w in self.body.winfo_children():
            w.destroy()
        r = 0
        for _grp, label, val, unit in rows:
            tk.Label(self.body, text=label, font=("Segoe UI", 9), fg=MUTED, bg=SURFACE_ALT, anchor="w").grid(
                row=r, column=0, sticky="w", padx=(0, 12))
            tk.Label(self.body, text="%s %s" % (val, unit), font=("Segoe UI Semibold", 9), fg=TEXT, bg=SURFACE_ALT,
                     anchor="w").grid(row=r, column=1, sticky="w")
            r += 1
        for w in warns:
            autowrap(tk.Label(self.body, text="!  " + w, font=("Segoe UI", 9), fg=WARN, bg=SURFACE_ALT, anchor="w",
                              justify="left")).grid(row=r, column=0, columnspan=2, sticky="we", pady=(3, 0))
            r += 1


class App(tk.Tk):
    def __init__(self):
        super().__init__(className=APP_NAME)
        self.withdraw()
        self.settings = load_settings()
        apply_theme(self)
        self.k = dpi_scale(self)
        self._load_icons()
        splash = Splash(self, self.logo_big)
        t0 = time.time()
        self.title(APP_TITLE)
        self.minsize(int(1100 * self.k), int(650 * self.k))
        self.project = P.make_template(list(P.TEMPLATES)[0])
        self.vars = {}
        self.rows = []
        self.badges = {}
        self.derived_panels = []
        self.profile_bars = []
        self._edit_order = {}
        self.result = None
        self.model = None
        self.analyses = {}
        self.busy = False
        self.file_path = None
        self.saved_state = None
        self.dirty = False
        self.calc_time = None
        self.workflow = self.settings.get("workflow", "engineering")
        if self.workflow not in WORKFLOWS:
            self.workflow = "engineering"
        self.show_adv = tk.BooleanVar(value=bool(self.settings.get("show_adv", False)))
        self.profiles = PR.all_profiles()
        splash.say("Building parameter pages...")
        self._build()
        splash.say("Loading default template...")
        self._load_into_form(self.project)
        self.set_workflow(self.workflow, initial=True)
        self._restore_window()
        self.protocol("WM_DELETE_WINDOW", self.exit_app)
        self.after(max(0, int(1100 - (time.time() - t0) * 1000)), lambda: (splash.destroy(), self.deiconify(),
                                                                           self.lift(), self.focus_force(),
                                                                           self.after(80, self._place_sash),
                                                                           self.after(2500, self.check_news)))

    def _place_sash(self):
        self.update_idletasks()
        try:
            self.paned.sashpos(0, int(self.paned.winfo_width() * 0.47))
        except tk.TclError:
            pass

    def report_callback_exception(self, exc, val, tb):
        messagebox.showerror("Unexpected error", "".join(traceback.format_exception(exc, val, tb)), parent=self)

    def _load_icons(self):
        self.logo_big = self.logo_small = self.logo_mid = None
        try:
            ico = os.path.join(ASSETS, "trm4.ico")
            if sys.platform == "win32" and os.path.exists(ico):
                self.iconbitmap(default=ico)
            self.iconphoto(True, tk.PhotoImage(file=os.path.join(ASSETS, "trm4_64.png")),
                           tk.PhotoImage(file=os.path.join(ASSETS, "trm4_32.png")))
            self.logo_big = tk.PhotoImage(file=os.path.join(ASSETS, "trm4_128.png"))
            self.logo_mid = tk.PhotoImage(file=os.path.join(ASSETS, "trm4_64.png"))
            self.logo_small = tk.PhotoImage(file=os.path.join(ASSETS, "trm4_32.png"))
        except tk.TclError:
            pass

    def _restore_window(self):
        geo = self.settings.get("geometry")
        if geo:
            try:
                self.geometry(geo)
            except tk.TclError:
                pass
        else:
            w, h = int(1500 * self.k), int(900 * self.k)
            self.geometry("%dx%d+%d+%d" % (w, h, max(0, (self.winfo_screenwidth() - w) // 2),
                                           max(0, (self.winfo_screenheight() - h) // 3)))
        if self.settings.get("zoomed", True):
            try:
                self.state("zoomed")
            except tk.TclError:
                pass

    # ------------------------------------------------------------------ layout
    def _build(self):
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()

        body = ttk.Frame(self, style="Bg.TFrame")
        body.pack(fill="both", expand=True)
        self._build_sidebar(body)

        pw = ttk.PanedWindow(body, orient="horizontal")
        pw.pack(side="left", fill="both", expand=True, padx=(8, 8), pady=8)
        self.paned = pw

        # parameter pages (one visible at a time, chosen in the sidebar)
        left = tk.Frame(pw, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        pw.add(left, weight=2)
        head = ttk.Frame(left, padding=(18, 14, 18, 6))
        head.pack(fill="x")
        self.page_title = ttk.Label(head, style="PageTitle.TLabel")
        self.page_title.pack(anchor="w")
        self.page_sub = ttk.Label(head, style="PageSub.TLabel")
        self.page_sub.pack(anchor="w")
        ttk.Separator(left).pack(fill="x", padx=18, pady=(6, 0))
        self.page_host = ttk.Frame(left)
        self.page_host.pack(fill="both", expand=True)
        self.pages = {}
        for tab_name, fields in ALL_PAGES:
            sf = ScrollFrame(self.page_host, padding=(10, 4, 16, 16))
            fr = sf.inner
            fr.columnconfigure(1, weight=1)
            group = None
            for f in fields:
                if f["kind"] == "header":
                    group = f
                self._make_field(fr, f, group)
            self.pages[tab_name] = sf
        self.current_page = None

        # results
        right = ttk.Notebook(pw)
        pw.add(right, weight=3)
        self.result_tabs = {}

        def add(widget, name):
            right.add(widget, text=name)
            self.result_tabs[name] = widget

        self.summary = ScrollFrame(right, padding=(22, 18, 22, 22))
        add(self.summary, "Summary")
        tree_fr = ttk.Frame(right, padding=8)
        self.info_tree = ttk.Treeview(tree_fr, columns=("value", "unit"), show="tree headings")
        self.info_tree.heading("#0", text="Parameter", anchor="w")
        self.info_tree.heading("value", text="Value", anchor="w")
        self.info_tree.heading("unit", text="Unit", anchor="w")
        self.info_tree.column("#0", width=int(360 * self.k))
        self.info_tree.column("value", width=int(220 * self.k))
        self.info_tree.column("unit", width=int(90 * self.k))
        self.info_tree.tag_configure("section", font=FONT_SEMI, background=SURFACE_ALT)
        tsb = ttk.Scrollbar(tree_fr, orient="vertical", command=self.info_tree.yview)
        self.info_tree.configure(yscrollcommand=tsb.set)
        tsb.pack(side="right", fill="y")
        self.info_tree.pack(fill="both", expand=True)
        add(tree_fr, "System data")
        self.tab_mtf = PlotTab(right)
        add(self.tab_mtf, "MTF")
        self.tab_amop = PlotTab(right)
        add(self.tab_amop, "AMOP")
        self.tab_fom = PlotTab(right)
        add(self.tab_fom, "MTDP / MDSP")
        self.tab_range = PlotTab(right)
        add(self.tab_range, "Range")
        self.tab_niirs = PlotTab(right)
        add(self.tab_niirs, "NIIRS")
        self.tab_spec = PlotTab(right)
        add(self.tab_spec, "Spectral")
        self.tab_val = PlotTab(right)
        self.tab_val.placeholder("Import measured data on the 'Validation data' page, then calculate (F5).")
        add(self.tab_val, "Validation")
        self.sens = SensitivityTab(right, self)
        add(self.sens, "Sensitivity")
        msg_fr = ttk.Frame(right, padding=8)
        self.msg = tk.Text(msg_fr, wrap="word", height=10, relief="flat", font=FONT, padx=12, pady=10,
                           background=SURFACE, foreground=TEXT, highlightthickness=0, spacing1=2, spacing3=4)
        self.msg.tag_configure("title", font=("Segoe UI Semibold", 12), spacing3=8)
        self.msg.tag_configure("warn", foreground=WARN, lmargin1=8, lmargin2=24)
        self.msg.tag_configure("note", foreground="#4a5262", lmargin1=8, lmargin2=24)
        self.msg.tag_configure("ok", foreground=OK)
        self.msg.pack(fill="both", expand=True)
        add(msg_fr, "Messages")
        self.right = right
        self.msg_tab = msg_fr
        self._show_summary_placeholder()

    def _build_menu(self):
        m = tk.Menu(self)
        mf = tk.Menu(m, tearoff=False)
        self.menu_templates = tk.Menu(mf, tearoff=False)
        for name in P.TEMPLATES:
            self.menu_templates.add_command(label=name, command=lambda n=name: self.load_template(n))
        mf.add_command(label="New project", accelerator="Ctrl+N", command=self.new_project)
        mf.add_cascade(label="New from template", menu=self.menu_templates)
        mf.add_separator()
        mf.add_command(label="Open project...", accelerator="Ctrl+O", command=self.open_project)
        self.menu_recent = tk.Menu(mf, tearoff=False)
        mf.add_cascade(label="Open recent", menu=self.menu_recent)
        mf.add_separator()
        mf.add_command(label="Save", accelerator="Ctrl+S", command=self.save_project)
        mf.add_command(label="Save as...", accelerator="Ctrl+Shift+S", command=self.save_project_as)
        mf.add_separator()
        mf.add_command(label="Export report...", accelerator="Ctrl+E", command=self.export_report)
        mf.add_command(label="Export Hebrew DRI report (PDF)...", command=self.export_report_he)
        mf.add_command(label="Export scenario record (JSON)...", command=self.export_scenario)
        mf.add_command(label="Export current plot...", accelerator="Ctrl+P", command=self.export_plot)
        mf.add_separator()
        mf.add_command(label="Exit", accelerator="Alt+F4", command=self.exit_app)
        m.add_cascade(label="File", menu=mf)

        mw = tk.Menu(m, tearoff=False)
        self.wf_var = tk.StringVar(value=self.workflow)
        for i, (key, (label, _pages)) in enumerate(WORKFLOWS.items()):
            mw.add_radiobutton(label=label, variable=self.wf_var, value=key, accelerator="Ctrl+Shift+%d" % (i + 1),
                               command=lambda k=key: self.set_workflow(k))
        mw.add_separator()
        mw.add_checkbutton(label="Show advanced parameters", variable=self.show_adv, command=self._toggle_adv)
        m.add_cascade(label="Workflow", menu=mw)

        mv = tk.Menu(m, tearoff=False)
        for name, _ in ALL_PAGES:
            mv.add_command(label=name, command=lambda n=name: self.goto_page(n))
        m.add_cascade(label="Parameters", menu=mv)

        mr = tk.Menu(m, tearoff=False)
        mr.add_command(label="Calculate", accelerator="F5", command=self.calculate)
        mr.add_command(label="Quick geometric estimate", command=self.quick_estimate)
        mr.add_separator()
        mr.add_command(label="Improve performance (advisor)", command=lambda: self.sens.run("advisor"))
        mr.add_command(label="Limiting factors", command=lambda: self.sens.run("limiting"))
        for key, label in (("sweep", "Parameter sweep"), ("uncertainty", "Uncertainty study"),
                           ("scenarios", "Scenario comparison")):
            mr.add_command(label=label + "...", command=lambda k=key: self.open_analysis(k))
        mr.add_separator()
        mr.add_command(label="Lab: slanted-edge SFR from an image...", command=self.lab_sfr)
        mr.add_command(label="Lab: photon transfer (EMVA 1288) from flat / dark frames...", command=self.lab_ptc)
        mr.add_separator()
        mr.add_command(label="Detector lookup...", accelerator="Ctrl+D", command=self.detector_lookup)
        m.add_cascade(label="Run", menu=mr)

        mn = tk.Menu(m, tearoff=False)
        mn.add_command(label="Detector Atlas news...", command=lambda: self.open_news())
        mn.add_command(label="Check for new detectors now", command=lambda: self.check_news(manual=True))
        m.add_cascade(label="News", menu=mn)
        self.menubar, self.news_menu_index = m, m.index("end")

        mh = tk.Menu(m, tearoff=False)
        mh.add_command(label="Model documentation (PDF)", accelerator="F1", command=self.open_docs)
        mh.add_command(label="Keyboard shortcuts", command=self.show_shortcuts)
        mh.add_separator()
        mh.add_command(label="About " + APP_NAME, command=self.show_about)
        m.add_cascade(label="Help", menu=mh)
        self.config(menu=m)
        self._update_recent_menu()

        keys = {"<Control-n>": self.new_project, "<Control-o>": self.open_project, "<Control-s>": self.save_project,
                "<Control-S>": self.save_project_as, "<Control-e>": self.export_report, "<Control-p>": self.export_plot,
                "<Control-d>": self.detector_lookup, "<F5>": self.calculate, "<F1>": self.open_docs}
        for k, fn in keys.items():
            self.bind_all(k, lambda e, fn=fn: (fn(), "break")[1])
        for i in range(9):
            self.bind_all("<Control-Key-%d>" % (i + 1), lambda e, i=i: self._page_by_index(i))
        for i, key in enumerate(WORKFLOWS):
            self.bind_all("<Control-Shift-Key-%d>" % (i + 1), lambda e, k=key: self.set_workflow(k))
            # Shift changes the key symbol of digits on most layouts
            self.bind_all("<Control-%s>" % ("exclam", "at", "numbersign")[i], lambda e, k=key: self.set_workflow(k))

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=SURFACE)
        bar.pack(fill="x")
        inner = tk.Frame(bar, bg=SURFACE)
        inner.pack(fill="x", padx=8, pady=6)
        if self.logo_small:
            tk.Label(inner, image=self.logo_small, bg=SURFACE).pack(side="left", padx=(4, 8))
        tk.Label(inner, text=APP_NAME, font=("Segoe UI Semibold", 13), bg=SURFACE, fg=TEXT).pack(side="left")
        tk.Frame(inner, bg=BORDER, width=1).pack(side="left", fill="y", padx=14, pady=4)
        new_btn = ToolButton(inner, GLYPH["new"], "New", None, tip="New project from a template  (Ctrl+N)")
        new_btn.command = lambda: self.menu_templates.tk_popup(new_btn.winfo_rootx(),
                                                               new_btn.winfo_rooty() + new_btn.winfo_height())
        new_btn.pack(side="left")
        ToolButton(inner, GLYPH["open"], "Open", self.open_project, tip="Open project  (Ctrl+O)").pack(side="left")
        ToolButton(inner, GLYPH["save"], "Save", self.save_project, tip="Save project  (Ctrl+S)").pack(side="left")
        ToolButton(inner, GLYPH["export"], "Report", self.export_report,
                   tip="Export text report  (Ctrl+E)").pack(side="left")
        tk.Frame(inner, bg=BORDER, width=1).pack(side="left", fill="y", padx=10, pady=4)
        ToolButton(inner, GLYPH["search"], "Detector lookup", self.detector_lookup,
                   tip="Pick a detector from the Detector Atlas and fill its parameters  (Ctrl+D)").pack(side="left")
        ToolButton(inner, GLYPH["help"], "Docs", self.open_docs, tip="Open model documentation  (F1)").pack(side="left")
        self.calc_btn = ToolButton(inner, GLYPH["run"], "Calculate", self.calculate, accent=True,
                                   tip="Run the model  (F5)")
        self.calc_btn.pack(side="right", padx=(0, 4))
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

    def _build_statusbar(self):
        sb = ttk.Frame(self, style="Status.TFrame", padding=(10, 3))
        sb.pack(side="bottom", fill="x")
        tk.Frame(self, bg=BORDER, height=1).pack(side="bottom", fill="x")
        self.status = tk.StringVar(value="Ready")
        ttk.Label(sb, textvariable=self.status, style="Status.TLabel").pack(side="left")
        self.prog = ttk.Progressbar(sb, length=int(160 * self.k), maximum=1.0)
        self.prog.pack(side="right", padx=(10, 0))
        self.file_label = tk.StringVar()
        ttk.Label(sb, textvariable=self.file_label, style="Status.TLabel").pack(side="right", padx=10)
        self.cat_label = tk.StringVar()
        ttk.Label(sb, textvariable=self.cat_label, style="Status.TLabel").pack(side="right", padx=10)

    def _build_sidebar(self, body):
        side = tk.Frame(body, bg=SIDEBAR, width=int(240 * self.k))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="WORKFLOW", font=("Segoe UI Semibold", 8), fg="#7f8ba0", bg=SIDEBAR,
                 anchor="w").pack(fill="x", padx=18, pady=(16, 6))
        seg = tk.Frame(side, bg=SIDEBAR)
        seg.pack(fill="x", padx=14)
        self.wf_buttons = {}
        for key, short in (("quick", "Quick"), ("engineering", "Engineering"), ("lab", "Lab")):
            b = tk.Label(seg, text=short, font=("Segoe UI", 9), bg=SIDEBAR_HOVER, fg=SIDEBAR_TEXT, padx=6, pady=4,
                         cursor="hand2")
            b.pack(side="left", fill="x", expand=True, padx=1)
            b.bind("<ButtonRelease-1>", lambda e, k=key: self.set_workflow(k))
            Tooltip(b, WORKFLOWS[key][0])
            self.wf_buttons[key] = b
        self.wf_title = tk.Label(side, text="", font=("Segoe UI", 8), fg="#7f8ba0", bg=SIDEBAR, anchor="w")
        self.wf_title.pack(fill="x", padx=18, pady=(4, 0))
        tk.Label(side, text="PARAMETERS", font=("Segoe UI Semibold", 8), fg="#7f8ba0", bg=SIDEBAR,
                 anchor="w").pack(fill="x", padx=18, pady=(14, 6))
        self.side_list = tk.Frame(side, bg=SIDEBAR)
        self.side_list.pack(fill="x")
        self.side_items = {}
        foot = tk.Frame(side, bg=SIDEBAR)
        foot.pack(side="bottom", fill="x", padx=18, pady=14)
        self.adv_check = tk.Checkbutton(foot, text="Show advanced parameters", variable=self.show_adv,
                                        command=self._toggle_adv, bg=SIDEBAR, fg=SIDEBAR_TEXT, selectcolor=SIDEBAR_SEL,
                                        activebackground=SIDEBAR, activeforeground="white", font=("Segoe UI", 9),
                                        anchor="w", highlightthickness=0, bd=0)
        self.adv_check.pack(fill="x", pady=(0, 10))
        Tooltip(self.adv_check, "Advanced parameters change the result only for special hardware or detailed "
                                "studies. Groups that are in use stay visible anyway; hiding a field never changes, "
                                "resets or bypasses its value or checks.", wrap=int(300 * self.k))
        tk.Label(foot, text="TRM4.v3 model  ·  v%s" % __version__, font=("Segoe UI", 8), fg="#6f7b90",
                 bg=SIDEBAR, anchor="w").pack(fill="x")
        tk.Label(foot, text="Fraunhofer IOSB TR 2021/04", font=("Segoe UI", 8), fg="#6f7b90", bg=SIDEBAR,
                 anchor="w").pack(fill="x")

    def set_workflow(self, key, initial=False):
        if key not in WORKFLOWS:
            return
        self.workflow = key
        self.wf_var.set(key)
        label, pages = WORKFLOWS[key]
        for k, b in self.wf_buttons.items():
            b.configure(bg="#2f6fd6" if k == key else SIDEBAR_HOVER, fg="white" if k == key else SIDEBAR_TEXT)
        self.wf_title.configure(text=label)
        for w in self.side_list.winfo_children():
            w.destroy()
        self.side_items = {}
        for name in pages:
            it = SidebarItem(self.side_list, name, self.show_page)
            it.pack(fill="x")
            self.side_items[name] = it
        if key == "quick":
            self.adv_check.pack_forget()
        elif not self.adv_check.winfo_ismapped():
            self.adv_check.pack(fill="x", pady=(0, 10), before=self.adv_check.master.winfo_children()[1])
        # result tabs: compact set for Quick Prediction, engineering views otherwise
        visible = RESULT_TABS[key]
        for name, w in self.result_tabs.items():
            if name in visible:
                self.right.add(w)
            else:
                self.right.hide(w)
        try:
            cur = self.right.tab(self.right.select(), "text").split(" (")[0]
        except tk.TclError:
            cur = ""
        if cur not in visible:
            self.right.select(self.result_tabs["Summary"])
        old = self.current_page
        self.current_page = None
        if old in self.pages:
            self.pages[old].pack_forget()
        want = self.settings.get("page_" + key)
        self.show_page(want if want in pages else pages[0])
        self.refresh()
        if not initial:
            self.settings["workflow"] = key
            self.status.set("Workflow: %s" % label)

    def open_analysis(self, mode):
        if self.workflow == "quick":
            self.set_workflow("engineering")
        self.right.select(self.sens)
        self.sens.show_mode(mode)

    def _toggle_adv(self):
        self.settings["show_adv"] = bool(self.show_adv.get())
        self.refresh()

    def _page_by_index(self, i):
        pages = WORKFLOWS[self.workflow][1]
        if i < len(pages):
            self.show_page(pages[i])

    def goto_page(self, name):
        if name not in WORKFLOWS[self.workflow][1]:
            self.set_workflow("lab" if name == "Validation data" else ("quick" if name == "Quick setup" else
                                                                       "engineering"))
        self.show_page(name)

    def show_page(self, name):
        if self.current_page == name or name not in self.pages:
            return
        if self.current_page:
            self.pages[self.current_page].pack_forget()
            if self.current_page in self.side_items:
                self.side_items[self.current_page].select(False)
        self.pages[name].pack(fill="both", expand=True)
        if name in self.side_items:
            self.side_items[name].select(True)
        self.page_title.configure(text=name)
        self.page_sub.configure(text=PAGE_INFO.get(name, ""))
        self.current_page = name
        self.settings["page_" + self.workflow] = name

    # ------------------------------------------------------------------ parameter rows
    def _make_field(self, fr, f, group):
        row = fr.grid_size()[1]
        kind = f["kind"]
        if kind == "header":
            w = ttk.Label(fr, text=f["label"], style="Head.TLabel")
            w.grid(row=row, column=0, columnspan=5, sticky="w", padx=8, pady=(16 if row else 8, 4))
            widgets = [w]
            if f.get("level") in ("adv", "legacy"):
                tag = tk.Label(fr, text="advanced" if f["level"] == "adv" else "legacy", font=("Segoe UI", 8),
                               fg="#9a5b00" if f["level"] == "legacy" else MUTED, bg=SURFACE)
                tag.grid(row=row, column=2, columnspan=3, sticky="e", padx=8, pady=(16 if row else 8, 4))
                widgets.append(tag)
            self.rows.append((f, widgets, None, f))
            return
        if kind == "derived":
            dp = DerivedPanel(fr, self.k)
            dp.grid(row=row, column=0, columnspan=5, sticky="we", padx=8, pady=(10, 4))
            self.derived_panels.append(dp)
            self.rows.append((f, [dp], None, None))
            return
        if kind in ("profile", "profile_manager"):
            pb = ProfileBar(fr, self, manager=kind == "profile_manager")
            pb.grid(row=row, column=0, columnspan=5, sticky="we", padx=8, pady=(10, 4))
            self.profile_bars.append(pb)
            self.rows.append((f, [pb], None, None))
            return
        lab = ttk.Label(fr, text=f["label"], wraplength=int(200 * self.k), justify="left")
        lab.grid(row=row, column=0, sticky="w", padx=(18, 10), pady=3)
        path = f["path"]
        idx = len(self.vars.get(path, []))
        widgets = [lab]
        if kind == "bool":
            var = tk.BooleanVar()
            w = ttk.Checkbutton(fr, variable=var, command=lambda: (self._user_edit(path, idx), self.refresh()))
        elif kind == "choice":
            var = tk.StringVar()
            labels = [l for _, l in f["opts"]]
            w = ttk.Combobox(fr, values=labels, state="readonly", width=12)
            w.bind("<<ComboboxSelected>>", lambda e, w=w, f=f, var=var: self._choice_selected(w, f, var, idx))
            var._combo = w
        elif kind == "multiline":
            var = None
            w = tk.Text(fr, height=6, width=30, relief="flat", font=("Consolas", 10), highlightthickness=1,
                        highlightbackground=BORDER, highlightcolor=ACCENT, padx=6, pady=4)
            w.bind("<KeyRelease>", lambda e: (self._user_edit(path, idx), self._schedule_dirty_check()))
            w.bind("<FocusOut>", lambda e: self.refresh())
        elif kind == "file":
            # imported text file stored in the project as {"name", "text"} (JSON in the variable)
            var = tk.StringVar(value=json.dumps({"name": "", "text": ""}))
            w = ttk.Frame(fr)
            ttk.Button(w, text="Import...", width=8, command=lambda f=f, var=var: self._import_file(f, var, idx)).grid(
                row=0, column=0, sticky="w")
            ttk.Button(w, text="Clear", width=6, command=lambda var=var: (var.set(json.dumps({"name": "", "text": ""})),
                                                                         self._user_edit(path, idx, "preset"),
                                                                         self.refresh())).grid(row=0, column=1,
                                                                                               sticky="w", padx=(4, 0))
            w.columnconfigure(2, weight=1)
            info = autowrap(ttk.Label(w, style="Muted.TLabel", justify="left", width=1))
            info.grid(row=1, column=0, columnspan=3, sticky="we", pady=(2, 0))
            var.trace_add("write", lambda *_a, f=f, var=var, info=info: self._show_file_info(f, var, info))
            self._show_file_info(f, var, info)
        else:
            var = tk.StringVar()
            w = ttk.Entry(fr, textvariable=var, width=10)
            w.bind("<FocusOut>", lambda e: self.refresh())
            w.bind("<Return>", lambda e: self.refresh())
            w.bind("<KeyRelease>", lambda e, var=var: (self._user_edit(path, idx, check=var), self._schedule_dirty_check()))
        w.grid(row=row, column=1, sticky="we", padx=4, pady=3)
        widgets.append(w)
        if f["unit"]:
            u = ttk.Label(fr, text=f["unit"], style="Unit.TLabel")
            u.grid(row=row, column=2, sticky="w", padx=(2, 6))
            widgets.append(u)
        if not NO_BADGE.match(path):
            b = tk.Label(fr, text="", font=("Segoe UI", 7), padx=4, pady=0, cursor="hand2")
            b.grid(row=row, column=3, sticky="w", padx=(0, 4))
            b.bind("<ButtonRelease-1>", lambda e, path=path, b=b: self._source_menu(path, b))
            Tooltip(b, "Data source of this value - click to change")
            self.badges.setdefault(path, []).append(b)
            widgets.append(b)
        text = help_for(path)
        if text:
            q = tk.Label(fr, text="?", font=("Segoe UI Semibold", 8), bg=ACCENT_SOFT, fg=ACCENT, width=2,
                         cursor="question_arrow")
            q.grid(row=row, column=4, sticky="w", padx=(0, 4))
            q.bind("<Enter>", lambda e: q.configure(bg=ACCENT, fg="white"), add="+")
            q.bind("<Leave>", lambda e: q.configure(bg=ACCENT_SOFT, fg=ACCENT), add="+")
            Tooltip(q, text, delay=150, wrap=int(340 * self.k), click=True)
            widgets.append(q)
        self.rows.append((f, widgets, (var, w), group))
        self.vars.setdefault(path, []).append((f, var, w))

    # ------------------------------------------------------------------ provenance
    def _source(self, path):
        return (self.project.get("provenance") or {}).get(path, "preset")

    def _paint_badges(self, path=None):
        for pth, labels in ([(path, self.badges.get(path, []))] if path else self.badges.items()):
            text, fg, bg = SRC_STYLE.get(self._source(pth), SRC_STYLE["preset"])
            for b in labels:
                b.configure(text=text, fg=fg, bg=bg)

    def _set_source(self, path, src):
        prov = self.project.setdefault("provenance", {})
        if src == "preset":
            prov.pop(path, None)
        else:
            prov[path] = src
        self._paint_badges(path)
        self._schedule_dirty_check()

    def _source_menu(self, path, badge):
        m = tk.Menu(self, tearoff=False)
        cur = self._source(path)
        for key, label in P.SOURCES:
            m.add_command(label=("•  " if key == cur else "    ") + label, command=lambda k=key: self._set_source(path, k))
        m.tk_popup(badge.winfo_rootx(), badge.winfo_rooty() + badge.winfo_height())

    def _user_edit(self, path, idx, source="user", check=None):
        """A widget was changed by the user: it wins over duplicates and its source becomes 'user'."""
        if check is not None:
            try:
                cur = get_path(self.project, path)
            except (KeyError, IndexError):
                cur = None
            if check.get() == fmt(cur) if not isinstance(cur, list) else check.get() == ", ".join(fmt(x) for x in cur):
                return
        self._edit_order[path] = idx
        if self._source(path) != source:
            self._set_source(path, source)
        # a manual change of a preset-controlled value turns the preset into 'custom'
        if path.startswith("atmosphere.atm.") and get_path(self.project, "atmosphere.preset") != "custom":
            self._set_value("atmosphere.preset", "custom")
        if path in ("turbulence.cn2", "turbulence.cn2_mode", "turbulence.h_ref_m", "turbulence.time") and \
                get_path(self.project, "turbulence.cn2_preset") != "custom":
            self._set_value("turbulence.cn2_preset", "custom")
        if path in ("stab.random_on", "stab.rand_h_mrad", "stab.rand_v_mrad") and \
                get_path(self.project, "stab.jitter_preset") != "custom":
            self._set_value("stab.jitter_preset", "custom")
        if path in ("target.W_m", "target.H_m", "target.D_m", "target.dT_K", "target.T_bg_K") and \
                get_path(self.project, "target.preset") != "custom" and self.project["category"] == "Thermal":
            self._set_value("target.preset", "custom")
        if re.match(r"^target\.tasks\.\d\.lp$", path) and get_path(self.project, "target.task_preset") != "custom":
            self._set_value("target.task_preset", "custom")

    @staticmethod
    def _file_value(var):
        try:
            v = json.loads(var.get())
            return v if isinstance(v, dict) else {"name": "", "text": ""}
        except ValueError:
            return {"name": "", "text": ""}

    def _show_file_info(self, f, var, info):
        v = self._file_value(var)
        if not v.get("text"):
            info.configure(text="No file imported", foreground=MUTED)
            return
        try:
            info.configure(text="%s  [sha256 %s]\n%s" % (v.get("name", ""), IM.file_hash(v["text"]),
                                                       f["opts"]["check"](v["text"])), foreground=MUTED)
        except Exception as e:
            info.configure(text="%s\n%s" % (v.get("name", ""), e), foreground=WARN)

    def _import_file(self, f, var, idx):
        fn = filedialog.askopenfilename(parent=self, title=f["opts"]["title"], initialdir=self._start_dir(),
                                        filetypes=[("Data export", "*.csv *.txt *.dat"), ("All files", "*.*")])
        if not fn:
            return
        try:
            text = Z.read_text_file(fn)
            summary = f["opts"]["check"](text)
        except Exception as e:
            messagebox.showerror(f["opts"]["title"], "Could not import %s\n\n%s" % (fn, e), parent=self)
            return
        var.set(json.dumps({"name": os.path.basename(fn), "text": text}))
        self.settings["last_dir"] = os.path.dirname(fn)
        self._user_edit(f["path"], idx, "measurement" if f["path"].startswith("measured.") else "import")
        self.refresh()
        self.status.set("Imported %s  -  %s" % (os.path.basename(fn), summary))

    def _choice_selected(self, w, f, var, idx):
        lab = w.get()
        old = var.get()
        for val, l in f["opts"]:
            if l == lab:
                var.set(json.dumps(val))
        if var.get() == old:
            return
        path = f["path"]
        self._user_edit(path, idx)
        if path == "category":
            cat = json.loads(var.get())
            self._set_value("imager_type", "cooled" if cat == "Thermal" else "staring")
        if path == "target.preset":
            name = json.loads(var.get())
            if name in P.THERMAL_TARGETS:
                t = P.THERMAL_TARGETS[name]
                for k in ("W_m", "H_m", "D_m", "T_bg_K", "dT_K"):
                    self._set_value("target." + k, t[k])
                    self._set_source("target." + k, "preset")
                for i, (lp, on) in enumerate(zip(t["tasks"], t["task_on"])):
                    self._set_value("target.tasks.%d.lp" % i, lp)
                    self._set_value("target.tasks.%d.on" % i, on)
                self._set_value("target.task_preset", "target")
        if path == "target.task_preset":
            cur = self.collect()
            vals = P.task_preset_values(cur)
            if vals is not None:
                for i, lp in enumerate(vals):
                    self._set_value("target.tasks.%d.lp" % i, lp)
                    self._set_source("target.tasks.%d.lp" % i, "preset")
                self.status.set("Task criteria preset applied: %s" % P.TASK_PRESETS[json.loads(var.get())][0])
        if path == "irradiance.preset":
            self._set_value("irradiance.E_peak", P.NATURAL_SOURCES[json.loads(var.get())]["peak"])
            self._set_source("irradiance.E_peak", "preset")
        if path == "atmosphere.preset":
            which = json.loads(var.get())
            if which != "custom":
                cur = self.collect()
                atms = P.atmosphere_preset(cur, which)
                self._set_value("atmosphere.mode", "extinction")
                for i, at in enumerate(atms):
                    for key, val in at.items():
                        self._set_value("atmosphere.atm.%d.%s" % (i, key), val)
                        self._set_source("atmosphere.atm.%d.%s" % (i, key), "preset")
                win = P.qe_window(cur)
                self.status.set("Atmosphere preset '%s' for the %s band applied (typical engineering values)" % (
                    which, P.band_of(*win) if win else "LWIR"))
        if path == "stab.jitter_preset" and json.loads(var.get()) == "nvipm70":
            for key, val in (("random_on", True), ("rand_h_mrad", X.TYPICAL_JITTER_MRAD),
                             ("rand_v_mrad", X.TYPICAL_JITTER_MRAD)):
                self._set_value("stab." + key, val)
                self._set_source("stab." + key, "preset")
            self.status.set("Random jitter preset applied: %.0f urad rms in both axes (US Army NV-IPM practice)" %
                            (X.TYPICAL_JITTER_MRAD * 1e3))
        if path == "turbulence.cn2_preset":
            name = json.loads(var.get())
            if name in P.CN2_PRESETS:
                c = P.CN2_PRESETS[name]
                for key, val in (("cn2", c["cn2"]), ("cn2_mode", "height"), ("h_ref_m", 2.0), ("time", c["time"])):
                    self._set_value("turbulence." + key, val)
                    self._set_source("turbulence." + key, "preset")
        self.refresh()

    # ------------------------------------------------------------------ values
    def _set_entry(self, f, var, w, value):
        k = f["kind"]
        if k == "bool":
            var.set(bool(value))
        elif k == "choice":
            var.set(json.dumps(value))
            lab = next((l for v, l in f["opts"] if v == value), None)
            w.set(lab if lab is not None else "")
        elif k == "multiline":
            if w.get("1.0", "end").strip() != str(value).strip():
                w.delete("1.0", "end")
                w.insert("1.0", str(value))
        elif k == "list":
            var.set(", ".join(fmt(x) for x in value))
        elif k == "file":
            new = json.dumps(value if isinstance(value, dict) else {"name": "", "text": ""})
            if var.get() != new:
                var.set(new)
        else:
            var.set(fmt(value))

    def _set_value(self, path, value, skip=None):
        for i, (f, var, w) in enumerate(self.vars.get(path, [])):
            if i != skip:
                self._set_entry(f, var, w, value)

    def _load_into_form(self, project, saved=True):
        self.project = P.deep_merge(P.DEFAULT_PROJECT, project)
        # one entry per pixel pair whenever the loaded values allow it (old projects have no square flag)
        self.project["detector"]["square"] = square_pixels(self.project["detector"])
        self._edit_order = {}
        for path in self.vars:
            try:
                self._set_value(path, get_path(self.project, path))
            except (KeyError, IndexError):
                pass
        self._paint_badges()
        self.refresh()
        if saved:
            self._mark_saved()

    # ------------------------------------------------------------------ document state
    @staticmethod
    def _state_of(p):
        return json.dumps(p, sort_keys=True, default=str)

    def _mark_saved(self):
        self.saved_state = self._state_of(self.project)
        self._set_dirty(False)

    def _schedule_dirty_check(self):
        if getattr(self, "_dirty_job", None):
            self.after_cancel(self._dirty_job)
        self._dirty_job = self.after(300, lambda: self._set_dirty(self._state_of(self.collect()) != self.saved_state))

    def _set_dirty(self, dirty):
        self.dirty = dirty
        name = os.path.basename(self.file_path) if self.file_path else (self.project.get("name") or "Untitled")
        self.title("%s%s  -  %s" % (name, " *" if dirty else "", APP_TITLE))
        self.file_label.set((self.file_path or "Not saved yet") + ("  (modified)" if dirty else ""))
        p = self.project
        kind = {"cooled": "cooled", "uncooled": "uncooled"}.get(p.get("imager_type"), p.get("imager_type", ""))
        prof = (p.get("profile") or {}).get("name")
        self.cat_label.set("%s%s  ·  %s%s" % (p.get("category", ""), " / " + kind if p.get("category") == "Thermal" else "",
                                              "Field" if p["mode"]["environment"] == "field" else "Laboratory",
                                              "  ·  " + prof if prof else ""))

    def confirm_discard(self):
        """Ask to save unsaved changes. Returns False if the user cancels."""
        self.dirty = self._state_of(self.collect()) != self.saved_state
        if not self.dirty:
            return True
        ans = messagebox.askyesnocancel(APP_NAME, "Save changes to \"%s\"?" % (
            os.path.basename(self.file_path) if self.file_path else self.project.get("name") or "Untitled"), parent=self)
        if ans is None:
            return False
        if ans:
            return self.save_project()
        return True

    def collect(self, strict=False):
        p = copy.deepcopy(self.project)
        errors = []
        for path, entries in self.vars.items():
            order = list(range(len(entries)))
            last = self._edit_order.get(path)
            if last is not None and len(entries) > 1:
                order.remove(last)
                order.append(last)          # the widget the user changed last wins over its duplicates
            for i in order:
                f, var, w = entries[i]
                if f["kind"] == "choice" and len(entries) > 1:
                    try:
                        if not f["cond"](p):
                            continue
                    except Exception:
                        pass
                k = f["kind"]
                try:
                    if k == "bool":
                        val = bool(var.get())
                    elif k == "choice":
                        s = var.get()
                        if not s:
                            continue
                        val = json.loads(s)
                    elif k == "multiline":
                        val = w.get("1.0", "end").strip()
                    elif k == "file":
                        val = self._file_value(var)
                    elif k == "list":
                        vals = [float(x) for x in var.get().replace(";", ",").split(",") if x.strip()]
                        val = (vals + [0.0] * 5)[:5]
                    elif k == "int":
                        val = int(float(var.get()))
                    elif k == "float":
                        val = float(var.get())
                    else:
                        val = var.get()
                    set_path(p, path, val)
                except ValueError:
                    errors.append("%s: invalid value %r" % (f["label"].strip(), var.get() if var else ""))
        apply_square(p)
        if strict and errors:
            raise ValueError("\n".join(errors))
        return p

    def _row_visible(self, f, group, p):
        try:
            if not f["cond"](p):
                return False
        except Exception:
            pass
        level = f.get("level") or (group.get("level") if group else "base") or "base"
        if level == "base":
            return True
        try:
            active = bool(group["active"](p)) if group else False
        except Exception:
            active = False
        if level == "adv":
            return bool(self.show_adv.get()) or active
        return active                                   # legacy: only while still in use

    def refresh(self):
        p = self.collect()
        self.project = p
        if p["detector"].get("square"):                 # hidden vertical entries show the values in use
            for _h, v in _SQUARE:
                self._set_value("detector." + v, p["detector"][v])
        # keep duplicated widgets (Quick setup and the detailed pages) in step
        for path, entries in self.vars.items():
            if len(entries) > 1:
                try:
                    self._set_value(path, get_path(p, path), skip=self._edit_order.get(path))
                except (KeyError, IndexError):
                    pass
        for f, widgets, _, group in self.rows:
            show = self._row_visible(f, group, p)
            for w in widgets:
                if show:
                    w.grid()
                else:
                    w.grid_remove()
        rows, warns = DV.compute(p)
        for dp in self.derived_panels:
            dp.update_values(rows, warns)
        for pb in self.profile_bars:
            pb.sync()
        if getattr(self, "sens", None) is not None:
            self.sens.check_stale(p)
        if self.saved_state is not None:
            self._set_dirty(self._state_of(p) != self.saved_state)

    # ------------------------------------------------------------------ camera profiles
    def apply_profile(self, prof, config):
        try:
            new = PR.apply(self.collect(strict=True), prof, config)
        except ValueError as e:
            messagebox.showerror("Camera profile", str(e), parent=self)
            return
        self._load_into_form(new, saved=False)
        self._clear_results()
        self.status.set("Camera profile applied: %s  [%s] - FOV, IFOV, Nyquist and F-number are recalculated" % (
            prof["name"], config))

    def reload_profiles(self):
        self.profiles = PR.all_profiles()
        for pb in self.profile_bars:
            pb.reload()

    # ------------------------------------------------------------------ actions
    def _start_dir(self):
        d = self.settings.get("last_dir")
        return d if d and os.path.isdir(d) else PROJECT_DIR

    def _clear_results(self):
        self.result = self.model = None
        self.analyses = {}
        self.info_tree.delete(*self.info_tree.get_children())
        for tab in (self.tab_mtf, self.tab_amop, self.tab_fom, self.tab_range, self.tab_niirs, self.tab_spec):
            tab.placeholder("Results appear here after the calculation (F5).")
        self.tab_val.placeholder("Import measured data on the 'Validation data' page, then calculate (F5).")
        self.sens.clear_all()
        self.msg.delete("1.0", "end")
        self.right.tab(self.msg_tab, text="Messages")
        self.prog["value"] = 0
        self._show_summary_placeholder()

    def new_project(self):
        self.load_template(list(P.TEMPLATES)[0])

    def load_template(self, name):
        if not self.confirm_discard():
            return
        self.file_path = None
        self._load_into_form(P.make_template(name))
        self._clear_results()
        self.status.set("New project from template: %s" % name)

    def open_project(self, fn=None):
        if not self.confirm_discard():
            return
        if not fn:
            fn = filedialog.askopenfilename(parent=self, title="Open project", initialdir=self._start_dir(),
                                            filetypes=[("TRM4 project", "*.json"), ("All files", "*.*")])
        if not fn:
            return
        try:
            with open(fn, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.file_path = fn
            self._load_into_form(data)
            self._clear_results()
            self._add_recent(fn)
            self.status.set("Opened %s" % fn)
        except Exception as e:
            self.file_path = None
            messagebox.showerror("Open project", "Could not open %s\n\n%s" % (fn, e), parent=self)
            self._forget_recent(fn)

    def save_project(self):
        """Save to the current file (or ask for one). Returns True when saved."""
        if not self.file_path:
            return self.save_project_as()
        return self._write_project(self.file_path)

    def save_project_as(self):
        try:
            p = self.collect(strict=True)
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e), parent=self)
            return False
        fn = filedialog.asksaveasfilename(parent=self, title="Save project as", initialdir=self._start_dir(),
                                          defaultextension=".json", initialfile=(p.get("name") or "project") + ".json",
                                          filetypes=[("TRM4 project", "*.json")])
        return self._write_project(fn) if fn else False

    def _write_project(self, fn):
        try:
            p = self.collect(strict=True)
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e), parent=self)
            return False
        try:
            with open(fn, "w", encoding="utf-8") as fh:
                json.dump(p, fh, indent=2)
        except OSError as e:
            messagebox.showerror("Save project", str(e), parent=self)
            return False
        self.project = p
        self.file_path = fn
        self._mark_saved()
        self._add_recent(fn)
        self.status.set("Saved %s" % fn)
        return True

    def export_report(self):
        if not self.result:
            messagebox.showinfo("Export report", "Run a calculation first (F5).", parent=self)
            return
        fn = filedialog.asksaveasfilename(parent=self, title="Export report", initialdir=self._start_dir(),
                                          defaultextension=".txt",
                                          initialfile=(self.project.get("name") or "report") + " - report.txt",
                                          filetypes=[("Text report", "*.txt")])
        if fn:
            report.write_report(fn, getattr(self, "calc_project", self.project), self.result, self.analyses)
            self.settings["last_dir"] = os.path.dirname(fn)
            self.status.set("Report written to %s" % fn)

    def export_report_he(self):
        """Hebrew scholarly PDF: DRI results + Range Improvement Advisor recommendations.

        Reuses the advisor result of the Sensitivity tab when it matches the current inputs; otherwise the advisor runs
        there first (progress, elapsed time and Stop on that tab) and the PDF is written when it finishes."""
        if getattr(self, "_report_he_pending", None) or getattr(self, "_report_he_busy", False):
            messagebox.showinfo("Hebrew DRI report", "The Hebrew report is already being prepared - the progress is "
                                                     "shown on the Sensitivity tab ('Stop' cancels it).", parent=self)
            try:
                self.right.select(self.sens)
            except tk.TclError:
                pass
            return
        if self.busy or self.sens.busy:
            messagebox.showinfo("Hebrew DRI report", "A calculation or analysis is still running. Wait until it has "
                                                     "finished (or press 'Stop' on the Sensitivity tab), then export "
                                                     "the report again.", parent=self)
            return
        try:
            p = self.collect(strict=True)
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e), parent=self)
            return
        if p["mode"]["environment"] != "field":
            messagebox.showinfo("Hebrew DRI report", "The DRI report needs 'Field performance' (General page).",
                                parent=self)
            return
        adv = self.sens.results.get("advisor")
        reuse = adv is not None and not self.sens.is_stale(adv, p)
        if not reuse and not messagebox.askokcancel(
                "Hebrew DRI report", "The report needs the Range Improvement Advisor for the current inputs. It will "
                                     "run now on the Sensitivity tab (progress and 'Stop' there) and the PDF is written "
                                     "when it has finished.\n\nThe advisor makes about 60 model runs in parallel - "
                                     "from well under a minute up to several minutes for slow (e.g. turbulence) "
                                     "configurations.", parent=self):
            return
        fn = filedialog.asksaveasfilename(parent=self, title="Export Hebrew DRI report", initialdir=self._start_dir(),
                                          defaultextension=".pdf",
                                          initialfile=(self.project.get("name") or "TRM") + " - DRI report (HE).pdf",
                                          filetypes=[("PDF document", "*.pdf")])
        if not fn:
            return
        self.settings["last_dir"] = os.path.dirname(fn)
        if reuse:
            self._write_report_he(fn, p, adv)
            return
        self._report_he_pending = (fn, p)
        self.sens.run("advisor")
        if not self.sens.busy:                         # the run was refused (message already shown)
            self._report_he_pending = None

    def _advisor_finished(self, r, err):
        pending, self._report_he_pending = getattr(self, "_report_he_pending", None), None
        if not pending:
            return
        if err or r is None:
            self.status.set("Hebrew report not written - the advisor %s" % ("was stopped" if err == "cancelled"
                                                                            else "failed"))
            return
        self._write_report_he(pending[0], pending[1], r)

    def _write_report_he(self, fn, p, adv):
        same = self.result is not None and json.dumps(getattr(self, "calc_project", None), sort_keys=True,
                                                      default=str) == json.dumps(p, sort_keys=True, default=str)
        res = self.result if same else None
        self._report_he_busy = True
        self.configure(cursor="watch")
        self.status.set("Writing the Hebrew PDF report...")

        def work():
            try:
                n = report_he.write_pdf(fn, p, res if res is not None else run_project(p)[1], adv)
                self.after(0, lambda: self._report_he_done(fn, n, None))
            except Exception as e:          # ModelError, file in use, and anything unexpected
                err = str(e) if isinstance(e, (ModelError, ValueError, OSError)) else traceback.format_exc()
                self.after(0, lambda: self._report_he_done(fn, 0, err))

        threading.Thread(target=work, daemon=True).start()

    def _report_he_done(self, fn, n, err):
        self._report_he_busy = False
        self.configure(cursor="")
        if err:
            self.status.set("Hebrew report failed")
            messagebox.showerror("Hebrew DRI report", "The PDF could not be written:\n%s\n\nIf the file is open in a "
                                                      "PDF viewer, close it and export again." % err, parent=self)
            return
        self.status.set("Hebrew report written to %s (%d pages)" % (fn, n))
        if messagebox.askyesno("Hebrew DRI report", "Report written (%d pages):\n%s\n\nOpen it now?" % (n, fn),
                               parent=self):
            try:
                os.startfile(fn)
            except OSError:
                pass

    def export_scenario(self):
        """Unit-labelled scenario record with coverage and trace (field map Sec. 12.8)."""
        if not self.result:
            messagebox.showinfo("Export scenario record", "Run a calculation first (F5).", parent=self)
            return
        fn = filedialog.asksaveasfilename(parent=self, title="Export scenario record", initialdir=self._start_dir(),
                                          defaultextension=".json",
                                          initialfile=(self.project.get("name") or "scenario") + " - scenario.json",
                                          filetypes=[("Scenario record", "*.json")])
        if fn:
            SC.write(fn, getattr(self, "calc_project", self.project), self.result)
            self.settings["last_dir"] = os.path.dirname(fn)
            self.status.set("Scenario record written to %s" % fn)

    def export_plot(self):
        tab = self.nametowidget(self.right.select())
        if tab is self.sens:
            tab = self.sens.plot
        if not isinstance(tab, PlotTab) or not self.result:
            messagebox.showinfo("Export plot", "Select a plot tab (MTF, AMOP, Range, ...) after a calculation.",
                                parent=self)
            return
        label = self.right.tab(tab, "text").replace("/", "-").replace(" ", "")
        fn = filedialog.asksaveasfilename(parent=self, title="Export plot", initialdir=self._start_dir(),
                                          defaultextension=".png",
                                          initialfile="%s - %s.png" % (self.project.get("name") or "TRM4", label),
                                          filetypes=[("PNG image", "*.png"), ("PDF document", "*.pdf"),
                                                     ("SVG vector image", "*.svg")])
        if fn:
            tab.fig.savefig(fn, bbox_inches="tight")
            self.settings["last_dir"] = os.path.dirname(fn)
            self.status.set("Plot saved to %s" % fn)

    def detector_lookup(self):
        DetectorDialog(self)

    # ------------------------------------------------------------------ detector atlas news
    def check_news(self, manual=False):
        """Read the atlas feed in the background; new unread detectors open the news window.  Re-runs every
        NEWS.CHECK_INTERVAL_MS while TRM is open."""
        if not manual:
            self._news_job = self.after(NEWS.CHECK_INTERVAL_MS, self.check_news)
        if getattr(self, "_news_busy", False):
            return
        self._news_busy = True

        def work():
            res = NEWS.fetch()
            self.after(0, lambda: self._news_done(*res, manual=manual))
        threading.Thread(target=work, daemon=True).start()

    def _news_done(self, news, info, manual=False):
        self._news_busy = False
        self.news, self.news_info = news, info
        unread = NEWS.unread(news, self.settings)
        self._update_news_menu(len(unread))
        dlg = getattr(self, "news_dlg", None)
        if dlg is not None and dlg.winfo_exists():
            dlg.refresh()
        shown = self.__dict__.setdefault("_news_shown", set())
        fresh = [it for it in unread if it["id"] not in shown]
        if fresh or manual:
            self.open_news()
        if fresh:
            self.status.set("Detector Atlas: %d new detector(s) - %s" % (
                len(unread), ", ".join(NEWS.title(it) for it in unread[:3])))

    def _update_news_menu(self, n):
        try:
            self.menubar.entryconfigure(self.news_menu_index, label="News (%d new)" % n if n else "News")
        except (AttributeError, tk.TclError):
            pass

    def open_news(self):
        dlg = getattr(self, "news_dlg", None)
        if dlg is not None and dlg.winfo_exists():
            dlg.refresh()
            dlg.deiconify()
            dlg.lift()
            return
        if not hasattr(self, "news"):
            self.check_news(manual=True)
            return
        self.news_dlg = NewsDialog(self)

    def set_news_read(self, ids, read=True):
        NEWS.mark_read(self.settings, ids, read)
        save_settings(self.settings)
        self._update_news_menu(len(NEWS.unread(getattr(self, "news", []), self.settings)))

    # ------------------------------------------------------------------ recent files / settings
    def _add_recent(self, fn):
        fn = os.path.abspath(fn)
        rec = [f for f in self.settings.get("recent", []) if os.path.normcase(f) != os.path.normcase(fn)]
        self.settings["recent"] = [fn] + rec[:7]
        self.settings["last_dir"] = os.path.dirname(fn)
        self._update_recent_menu()
        save_settings(self.settings)

    def _forget_recent(self, fn):
        self.settings["recent"] = [f for f in self.settings.get("recent", []) if f != fn]
        self._update_recent_menu()

    def _update_recent_menu(self):
        m = self.menu_recent
        m.delete(0, "end")
        rec = self.settings.get("recent", [])
        for i, fn in enumerate(rec):
            m.add_command(label="%d  %s" % (i + 1, fn), command=lambda f=fn: self.open_project(f))
        if not rec:
            m.add_command(label="(no recent projects)", state="disabled")
        else:
            m.add_separator()
            m.add_command(label="Clear list", command=lambda: (self.settings.update(recent=[]),
                                                               self._update_recent_menu()))

    def exit_app(self):
        if self.busy and not messagebox.askyesno(APP_NAME, "A calculation is running. Exit anyway?", parent=self):
            return
        if not self.confirm_discard():
            return
        zoomed = self.state() == "zoomed"
        self.settings["zoomed"] = zoomed
        if not zoomed:
            self.settings["geometry"] = self.geometry()
        self.settings["workflow"] = self.workflow
        self.settings["show_adv"] = bool(self.show_adv.get())
        save_settings(self.settings)
        self.destroy()

    # ------------------------------------------------------------------ help
    def open_docs(self):
        pdf = find_documentation()
        if pdf:
            os.startfile(pdf)
        else:
            messagebox.showinfo("Documentation", "The TRM4 documentation PDF was not found in\n%s" % PROJECT_DIR,
                                parent=self)

    def show_shortcuts(self):
        rows = [("F5", "Calculate"), ("Ctrl+N", "New project"), ("Ctrl+O", "Open project"), ("Ctrl+S", "Save"),
                ("Ctrl+Shift+S", "Save as"), ("Ctrl+E", "Export text report"), ("Ctrl+P", "Export current plot"),
                ("Ctrl+D", "Detector lookup"), ("Ctrl+1 ... 9", "Go to parameter page"),
                ("Ctrl+Shift+1 / 2 / 3", "Quick / Engineering / Lab workflow"), ("F1", "Documentation")]
        dlg = self._dialog("Keyboard shortcuts")
        fr = ttk.Frame(dlg, padding=20)
        fr.pack(fill="both", expand=True)
        for i, (k, d) in enumerate(rows):
            tk.Label(fr, text=k, font=("Consolas", 10), bg=SURFACE_ALT, fg=TEXT, padx=8, pady=2,
                     highlightthickness=1, highlightbackground=BORDER).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Label(fr, text=d).grid(row=i, column=1, sticky="w", padx=14)
        ttk.Button(fr, text="Close", command=dlg.destroy).grid(row=len(rows), column=1, sticky="e", pady=(16, 0))

    def show_about(self):
        import platform
        dlg = self._dialog("About " + APP_NAME)
        fr = ttk.Frame(dlg, padding=24)
        fr.pack(fill="both", expand=True)
        if self.logo_mid:
            ttk.Label(fr, image=self.logo_mid).grid(row=0, column=0, rowspan=3, sticky="n", padx=(0, 18))
        ttk.Label(fr, text=APP_TITLE, font=("Segoe UI Semibold", 15)).grid(row=0, column=1, sticky="w")
        ttk.Label(fr, text="Version %s  ·  TRM4.v3 model / v%s / Fraunhofer IOSB TR 2021/04\nValidation: %s" % (
            __version__, __version__, VALIDATION_VERSION),
            style="Muted.TLabel", justify="left").grid(row=1, column=1, sticky="w")
        ttk.Label(fr, wraplength=int(380 * self.k), justify="left", text=(
            "Python implementation of the TRM4.v3 range performance model for thermal, visible / NIR / SWIR "
            "and general imagers, following \"TRM4.v3 - Parameter Description and Model Documentation\" "
            "(Fraunhofer IOSB Technical Report 2021/04).\n\n"
            "Python %s  ·  NumPy %s  ·  Matplotlib %s  ·  Tk %s" % (
                platform.python_version(), np.__version__, matplotlib.__version__, tk.TkVersion))).grid(
            row=2, column=1, sticky="w", pady=(10, 0))
        ttk.Button(fr, text="OK", style="Accent.TButton", command=dlg.destroy).grid(row=3, column=1, sticky="e",
                                                                                  pady=(18, 0))

    def _dialog(self, title):
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.configure(bg=SURFACE)
        dlg.transient(self)
        dlg.resizable(False, False)
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        dlg.after(10, lambda: (dlg.update_idletasks(), dlg.geometry("+%d+%d" % (
            self.winfo_rootx() + (self.winfo_width() - dlg.winfo_width()) // 2,
            self.winfo_rooty() + (self.winfo_height() - dlg.winfo_height()) // 3)), dlg.grab_set()))
        return dlg

    # ------------------------------------------------------------------ calculation
    def calculate(self):
        if self.busy:
            return
        try:
            p = self.collect(strict=True)
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e), parent=self)
            return
        self.project = p
        self.calc_project = copy.deepcopy(p)
        # keep only analyses that were calculated with the current inputs
        self.analyses = {k: v for k, v in self.analyses.items() if not self.sens.is_stale(v, p)}
        self.busy = True
        self.calc_btn.set_enabled(False)
        self.calc_btn.set_text("Calculating...")
        self.configure(cursor="watch")
        self.prog["value"] = 0
        self._t_start = time.time()

        def progress(msg, frac=None):
            self.after(0, lambda: (self.status.set(msg), frac is not None and self.prog.configure(value=frac)))

        def work():
            try:
                model, res = run_project(p, progress)
                self.after(0, lambda: self._done(model, res, None))
            except ModelError as e:
                self.after(0, lambda e=e: self._done(None, None, str(e)))
            except Exception:
                tb = traceback.format_exc()
                self.after(0, lambda: self._done(None, None, tb))

        threading.Thread(target=work, daemon=True).start()

    def quick_estimate(self):
        """Geometric quick mode: Nyquist / diffraction ranges in a dialog, without running the model."""
        try:
            p = self.collect(strict=True)
            q = quick_estimate(p)
        except (ValueError, ModelError) as e:
            messagebox.showerror("Quick geometric estimate", str(e), parent=self)
            return
        lines = ["%-16s %5g lp   %s   (%s)" % (t["name"], t["lp"], "-" if t["R0"] is None else (
            "> 1000 km" if not np.isfinite(t["R0"]) else "%.3f km" % t["R0"]), t["limit"]) for t in q["tasks"]]
        messagebox.showinfo("Quick geometric estimate", "\n".join(lines) + (
            "\n\nIFOV %.4g mrad, aperture %.4g mm, mean wavelength %.3g um.\nOne line pair = the larger of 2 pixels "
            "and lambda / D; noise, contrast, MTF roll-off and the atmosphere are ignored, and TRM4 also credits bars "
            "beyond Nyquist - a first sizing, not a TRM4 range (extension)." % (q["ifov_mrad"], q["D_mm"],
                                                                                q["lambda_um"])), parent=self)

    _FRAME_TYPES = [("Frames", "*.npy *.csv *.txt *.png *.tif *.tiff"), ("All files", "*.*")]

    def _apply_to_project(self, changes, source="measured"):
        """Write {path: value} into the form (unsaved) and mark the values' data source."""
        p = self.collect()
        for path, v in changes.items():
            set_path(p, path, v)
        self._load_into_form(p, saved=False)
        for path in changes:
            self._set_source(path, source)

    def lab_sfr(self):
        """Slanted-edge SFR (ISO 12233 e-SFR) of an edge region -> measured MTF / SFR input (cycles/pixel)."""
        fn = filedialog.askopenfilename(parent=self, title="Edge region (frame with one slanted edge)",
                                        initialdir=self._start_dir(), filetypes=self._FRAME_TYPES)
        if not fn:
            return
        try:
            res = LT.slanted_edge_sfr(LT.load_frame(fn))
        except (ValueError, OSError) as e:
            messagebox.showerror("Slanted-edge SFR", str(e), parent=self)
            return
        name = os.path.basename(fn)
        msg = "%s\n\nEdge %s, angle %.2f deg\nMTF50 %s cycles/pixel\nSFR at Nyquist (0.5) %.3f%s" % (
            res["method"], res["orientation"], res["angle_deg"], "%.4f" % res["mtf50"] if res["mtf50"] else "-",
            float(np.interp(0.5, res["f"], res["sfr"])), "\n\n" + "\n".join(res["notes"]) if res["notes"] else "")
        if messagebox.askyesno("Slanted-edge SFR", msg + "\n\nUse it as the measured MTF / SFR (Validation data, "
                               "cycles/pixel)? State on that page whether it is the device prefilter or the delivered "
                               "image SFR.", parent=self):
            self._apply_to_project({"measured.sfr_file": {"name": "SFR of " + name, "text": LT.sfr_to_text(res, name)},
                                    "measured.sfr_unit": "pixel"})
            self.goto_page("Validation data")

    def lab_ptc(self):
        """EMVA 1288 photon transfer from frame pairs -> detector inputs (read noise, ADC step, saturation, FPN)."""
        flats = filedialog.askopenfilenames(parent=self, title="Flat frames: two per illumination level, sorted "
                                            "(A1, B1, A2, B2, ...)", initialdir=self._start_dir(),
                                            filetypes=self._FRAME_TYPES)
        if not flats:
            return
        darks = filedialog.askopenfilenames(parent=self, title="Dark frames: one pair at the flat exposure",
                                            initialdir=self._start_dir(), filetypes=self._FRAME_TYPES)
        if not darks:
            return
        try:
            if len(flats) % 2 or len(darks) != 2:
                raise ValueError("Select an even number of flat frames (pairs) and exactly two dark frames.")
            fr = [LT.load_frame(f) for f in flats]
            t_ms = simpledialog.askfloat("Photon transfer", "Exposure of the dark pair [ms] (for DSNU as a current; "
                                         "Cancel = skip)", parent=self, minvalue=0.0)
            res = LT.photon_transfer(list(zip(fr[0::2], fr[1::2])), (LT.load_frame(darks[0]), LT.load_frame(darks[1])),
                                     t_int_s=(t_ms or 0.0) * 1e-3)
        except (ValueError, OSError) as e:
            messagebox.showerror("Photon transfer", str(e), parent=self)
            return
        rows = "\n".join("  %s = %.4g" % (k, v) if isinstance(v, float) else "  %s = %s" % (k, v)
                         for k, v in res["trm"].items())
        msg = "%s\n\nConversion gain K %.4g DN/e-  (ADC step %.4g e-)\nRead noise %.3g e-\nSaturation capacity %.4g e-" \
              "\nDSNU %.3g e-   PRNU %.3g %%%s\n\nTRM inputs:\n%s" % (
                  res["method"], res["K_DN_per_e"], res["lsb_e"], res["read_noise_e"], res["sat_e"], res["dsnu_e"],
                  res["prnu_pct"], "\n\n" + "\n".join(res["notes"]) if res["notes"] else "", rows)
        if messagebox.askyesno("Photon transfer (EMVA 1288)", msg + "\n\nWrite these values into the detector "
                               "inputs (source: measured)?", parent=self):
            self._apply_to_project(res["trm"])

    def _done(self, model, res, err):
        self.busy = False
        self.calc_btn.set_enabled(True)
        self.calc_btn.set_text("Calculate")
        self.configure(cursor="")
        if err:
            self.status.set("Calculation failed")
            self.prog["value"] = 0
            messagebox.showerror("Calculation error", err, parent=self)
            return
        self.model, self.result = model, res
        self.calc_time = time.strftime("%H:%M:%S")
        n = len(res["warnings"])
        self.status.set("Calculation finished in %.1f s%s" % (time.time() - self._t_start,
                                                              "  ·  %d warning(s)" % n if n else ""))
        self.prog["value"] = 1.0
        try:
            self._show(res)
        except Exception:
            messagebox.showerror("Display error", traceback.format_exc(), parent=self)

    # ------------------------------------------------------------------ summary dashboard
    def _clear_summary(self):
        fr = self.summary.inner
        for w in fr.winfo_children():
            w.destroy()
        fr.columnconfigure(0, weight=1)
        return fr

    def _show_summary_placeholder(self):
        fr = self._clear_summary()
        box = ttk.Frame(fr)
        box.pack(expand=True, pady=(int(110 * self.k), 0))
        if self.logo_big:
            ttk.Label(box, image=self.logo_big).pack(pady=(0, 14))
        ttk.Label(box, text="No results yet", font=("Segoe UI Semibold", 15)).pack()
        ttk.Label(box, text="Set the imager parameters on the left (or load a template),\nthen run the model.",
                  style="Muted.TLabel", justify="center").pack(pady=(4, 16))
        ttk.Button(box, text="Calculate   F5", style="Accent.TButton", command=self.calculate).pack()

    @staticmethod
    def _info_get(res, needle, first=True):
        for _, name, val, unit in res["info"]:
            if name == needle or (not first and needle in name):
                return val, unit
        return None

    def _card(self, parent, caption, value, unit="", color=None, width=None):
        c = tk.Frame(parent, bg=SURFACE_ALT, highlightthickness=1, highlightbackground=BORDER)
        if color:
            tk.Frame(c, bg=color, height=3).pack(fill="x")
        inner = tk.Frame(c, bg=SURFACE_ALT)
        inner.pack(fill="both", expand=True, padx=14, pady=(10, 12))
        tk.Label(inner, text=caption, font=("Segoe UI", 9), fg=MUTED, bg=SURFACE_ALT, anchor="w").pack(fill="x")
        row = tk.Frame(inner, bg=SURFACE_ALT)
        row.pack(fill="x", pady=(2, 0))
        size = 16 if len(value) <= 9 else (13 if len(value) <= 15 else 11)
        tk.Label(row, text=value, font=("Segoe UI Semibold", size), fg=color or TEXT, bg=SURFACE_ALT).pack(side="left")
        if unit:
            tk.Label(row, text=unit, font=("Segoe UI", 9), fg=MUTED, bg=SURFACE_ALT).pack(side="left", padx=(5, 0),
                                                                                         pady=(6, 0))
        return c

    def _section(self, fr, text):
        ttk.Label(fr, text=text, font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(20, 8))

    def _grid_cards(self, fr, cards, cols=3):
        g = ttk.Frame(fr)
        g.pack(fill="x")
        for c in range(cols):
            g.columnconfigure(c, weight=1, uniform="card")
        for i, (args, kw) in enumerate(cards):
            self._card(g, *args, **kw).grid(row=i // cols, column=i % cols, sticky="nsew", padx=(0, 10), pady=(0, 10))

    @staticmethod
    def _range_txt(R0, a):
        if R0 is None:
            return "< %.2f" % a["R"][0]
        if not np.isfinite(R0):
            return "> %.0f" % a["R"][-1]
        return "%.2f" % R0

    def _table(self, fr, headings, rows, widths=None):
        cols = ["c%d" % i for i in range(len(headings))]
        tv = ttk.Treeview(fr, columns=cols, show="headings", height=max(1, len(rows)))
        for i, h in enumerate(headings):
            tv.heading(cols[i], text=h, anchor="w")
            if widths:
                tv.column(cols[i], width=int(widths[i] * self.k), stretch=i == 0)
        for r in rows:
            tv.insert("", "end", values=r)
        tv.pack(fill="x", pady=(4, 0))
        return tv

    def _show_summary(self, res):
        fr = self._clear_summary()
        p = getattr(self, "calc_project", self.project)
        ttk.Label(fr, text=p.get("name") or "Untitled project", font=("Segoe UI Semibold", 17)).pack(anchor="w")
        prof = (p.get("profile") or {}).get("name")
        sub = "%s  ·  %s  ·  %s  ·  calculated %s%s  ·  run ID %s" % (
            res["category"] + (" (%s)" % p["imager_type"] if res["category"] == "Thermal" else ""),
            "Field performance" if p["mode"]["environment"] == "field" else "Laboratory performance",
            "video" if p["mode"]["stream"] == "video" else "still image", self.calc_time,
            "  ·  profile: %s [%s]" % (prof, p["profile"].get("config", "")) if prof else "",
            (res.get("provenance") or {}).get("run_id", "-"))
        autowrap(ttk.Label(fr, text=sub, style="Muted.TLabel", justify="left")).pack(anchor="w", fill="x", pady=(2, 0))
        db = res.get("dashboard") or {}

        # standard D / R / I ranges
        rg = res.get("range")
        if rg and rg["atm"]:
            self._section(fr, "Range performance  ·  %s%s" % (rg["atm"][0]["label"],
                                                             "  ·  from %s" % rg["source"] if rg.get("source") else ""))
            cards = []
            a0 = rg["atm"][0]
            unc = self.analyses.get("uncertainty")
            for i, t in enumerate(a0["tasks"]):
                txt = self._range_txt(t["R0"], a0)
                cap = "%s  (%s)" % (t["name"], "%g px on target" % t["pot"] if "pot" in t else
                                    "%g lp" % t["lp"] + (" incl. clutter x%.2g" % t["clutter"]
                                                         if t.get("clutter", 1.0) != 1.0 else ""))
                if unc and t["name"] in unc["base"]:
                    lo, hi, _txt = AN.interval(unc, t["name"])
                    cap += "  ·  %s %.2f - %.2f km" % ("MC" if unc.get("method") == "mc" else "+/-U", lo, hi)
                cards.append(((cap, txt, "km"), {"color": TASK_COLORS[i % len(TASK_COLORS)]}))
            self._grid_cards(fr, cards, cols=max(1, min(3, len(cards))))
            lv = [(t["name"], "%s km" % self._range_txt(t["R0"], a0)) + tuple(
                "%s km" % self._range_txt(l["R0"], a0) for l in t["levels"]) +
                (" / ".join("%.3g" % x for x in [t["lp"]] + [l["lp"] for l in t["levels"]]),)
                for t in a0["tasks"] if t.get("levels")]
            if lv:
                ttk.Label(fr, text="Probability levels  ·  Johnson TTPF on the task criterion (extension - the TRM4 "
                                   "range is P50)", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
                tv = self._table(fr, ("Task", "P50 (TRM4)", "P80", "P90", "Criterion N50 / N80 / N90 [lp]"), lv,
                                 (110, 95, 95, 95, 200))
                tv.column("c0", stretch=False)
                tv.column("c4", stretch=True)
            ex = [(t["name"], "%s km" % self._range_txt(t["R0"], a0),
                   " / ".join("%s" % self._range_txt(x, a0) for x in [t["ttp"]["R0"]] +
                              [l["R0"] for l in t["ttp"].get("levels", [])]) + " km  (V50 %g)" % t["ttp"]["v50"]
                   if "ttp" in t else "-",
                   ("%s km  (%s)" % (self._range_txt(t["geo"]["R0"], a0), t["geo"]["limit"])) if "geo" in t else "-")
                  for t in a0["tasks"] if "ttp" in t or "geo" in t]
            if ex:
                ttk.Label(fr, text="Other range metrics (extensions, not TRM4)  ·  TTP / V50 (P50 / P80 / P90, V50 "
                                   "uncalibrated)  ·  geometric reference: Nyquist / diffraction only",
                          style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
                tv = self._table(fr, ("Task", "TRM4", "TTP / V50", "Geometric reference"), ex, (110, 95, 260, 260))
                tv.column("c0", stretch=False)
                tv.column("c3", stretch=True)
            rows = []
            for t in db.get("tasks", []):
                if "mtf_task" in t:
                    rows.append((t["name"], "%s km" % self._range_txt(t["R0"], a0), "%.1f × %.1f" % (t["pix_h"], t["pix_v"]),
                                 "%.1f / %g" % (t["cyc_nyq"], t["lp"]), "%.2f" % t["mtf_task"], "%.3g" % t["cnr_task"],
                                 t["limiter"]))
                else:
                    rows.append((t["name"], "%s km" % self._range_txt(t["R0"], a0), "-", "- / %g" % t["lp"], "-", "-",
                                 "range at the grid limit"))
            if rows:
                ttk.Label(fr, text="Diagnostics at the task range (atmosphere 1)  ·  Pixels | Cycles | MTF @ task "
                                   "frequency | CNR | Limiting factor  ·  double-click a row for the explanation",
                          style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
                tv = self._table(fr, ("Task", "Range", "Target px h × v", "Cycles @Nyq / req.", "MTF @task",
                                      "CNR", "Indicative limiter"), rows, (95, 70, 95, 105, 70, 60, 170))
                tv.bind("<Double-1>", lambda e, tv=tv, db=db: self._explain_task(tv, db))
            st_lines = [("Model", db.get("model", "")),
                        ("Extensions (not TRM4)", "; ".join(db.get("extensions") or []) or "none - TRM4 model only"),
                        ("Calibration status", db.get("calibration", "")),
                        ("Confidence / uncertainty method", (unc["label"] if unc else
                                                             "nominal - input uncertainties not specified")),
                        ("Input provenance", ", ".join("%s %d" % (SRC_STYLE.get(k, (k,))[0], n) for k, n in sorted(
                            ((res.get("provenance") or {}).get("source_counts") or {}).items(), key=lambda x: -x[1])))]
            for k_, v_ in st_lines:
                autowrap(ttk.Label(fr, text="%s:  %s" % (k_, v_), style="Muted.TLabel", justify="left")).pack(
                    anchor="w", fill="x", pady=(2, 0))
            if len(rg["atm"]) > 1:
                rows = []
                for it, t in enumerate(a0["tasks"]):
                    rows.append([t["name"]] + ["%s km" % self._range_txt(a["tasks"][it]["R0"], a) for a in rg["atm"]])
                ttk.Label(fr, text="All atmospheres", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
                self._table(fr, ["Task"] + [a["label"] for a in rg["atm"]], rows)
        elif p["mode"]["environment"] != "field":
            self._section(fr, "Range performance")
            ttk.Label(fr, text="Ranges are calculated in 'Field performance' mode (General page).",
                      style="Muted.TLabel").pack(anchor="w")

        # image quality / sampling diagnostics
        self._section(fr, "Image quality and sampling")
        kpis = []

        def add(caption, needle, first=True):
            v = self._info_get(res, needle, first)
            if v:
                kpis.append(((caption, v[0].replace(" x ", " × "), v[1]), {}))

        add("Field of view (h × v)", "Field of view h x v")
        add("Detector angular subtense", "Detector angular subtense h x v")
        add("Nyquist frequency", "Nyquist frequency h x v")
        m = db.get("mtf")
        if m:
            m50 = ["%.3g" % m[z]["mtf50"] if m[z]["mtf50"] else "-" for z in "hv"]
            kpis.append((("MTF50 system prefilter (h × v)", "%s × %s" % tuple(m50), "1/mrad"), {}))
            kpis.append((("MTF at Nyquist (h × v)", "%.2f × %.2f" % (m["h"]["mtf_nyq"], m["v"]["mtf_nyq"]), ""), {}))
        if "cnr" in db:
            kpis.append((("CNR (%s)" % ("zero range" if res["category"] == "Thermal" else "ref. range"),
                          "%.3g" % db["cnr"], ""), {}))
        if "aliasing" in db:
            kpis.append((("Aliasing risk (presampled MTF)", db["aliasing"], ""),
                         {"color": WARN if db["aliasing"] == "high" else None}))
        if "fld" in db:
            kpis.append((("F·λ/d - %s" % db["fld"]["regime"], "%.2f" % db["fld"]["value"], ""), {}))
        add("Effective F-number", "Effective F-number")
        if res["category"] == "Thermal":
            add("NETD used", "NETD used")
        else:
            add("Well fill (background)", "Well fill (background)")
        add("%s at Nyquist (h)" % res["fom"]["name"], "at Nyquist (h)", first=False)
        self._grid_cards(fr, kpis, cols=3)

        # dominant limiting factor
        self._section(fr, "Dominant limiting factor")
        lf = self.analyses.get("limiting")
        if lf:
            ttk.Label(fr, text=lf["dominant"] or "No single dominant factor (all range gains < 1 %)",
                      font=("Segoe UI Semibold", 11), foreground=ACCENT).pack(anchor="w")
            for r in lf["rows"][:4]:
                autowrap(ttk.Label(fr, text="•  %s:  %s" % (r["factor"], ",  ".join(
                    "%s %+.0f %%" % (t, g) for t, g in r["gain_pct"].items())), style="Muted.TLabel",
                    justify="left")).pack(anchor="w", fill="x", padx=(14, 0), pady=(2, 0))
        elif rg and rg["atm"]:
            line = ttk.Frame(fr)
            line.pack(fill="x")
            ttk.Button(line, text="Analyse", command=lambda: self.sens.run("limiting")).pack(side="left", padx=(0, 10))
            autowrap(ttk.Label(line, text="Not analysed yet - removes each degradation in turn and compares the "
                                          "ranges (about 10 model runs).", style="Muted.TLabel", justify="left")).pack(
                side="left", fill="x", expand=True)
        else:
            ttk.Label(fr, text="Available in Field performance mode.", style="Muted.TLabel").pack(anchor="w")

        # assumptions & confidence
        self._section(fr, "Assumptions and confidence")
        pv = res.get("provenance") or {}
        counts = pv.get("source_counts", {})
        if counts:
            line = tk.Frame(fr, bg=SURFACE)
            line.pack(fill="x", anchor="w")
            tk.Label(line, text="Key inputs by data source:", font=("Segoe UI", 9), fg=MUTED, bg=SURFACE).pack(
                side="left", padx=(0, 6))
            for src, n in sorted(counts.items(), key=lambda x: -x[1]):
                text, fg, bg = SRC_STYLE.get(src, SRC_STYLE["preset"])
                tk.Label(line, text="%s %d" % (text, n), font=("Segoe UI", 8), fg=fg, bg=bg, padx=5).pack(
                    side="left", padx=2)
        if db.get("noise_source"):
            autowrap(ttk.Label(fr, text="Noise source: %s  ·  data quality: %s" % (db["noise_source"],
                                                                                 db.get("noise_quality", "")),
                               justify="left")).pack(anchor="w", fill="x", pady=(6, 0))
        if unc_text := self._confidence_text(res):
            autowrap(ttk.Label(fr, text=unc_text, justify="left")).pack(anchor="w", fill="x", pady=(6, 0))
        for a in res.get("assumptions", [])[:6]:
            autowrap(ttk.Label(fr, text="•  " + a, justify="left", style="Muted.TLabel")).pack(anchor="w", fill="x", padx=(14, 0), pady=(2, 0))
        if len(res.get("assumptions", [])) > 6:
            ttk.Label(fr, text="   ... %d more in the Messages tab" % (len(res["assumptions"]) - 6),
                      style="Muted.TLabel").pack(anchor="w", padx=(14, 0))

        # exposure budget and the context every DRI range is reported with (research review Sec. 4.3 / 7.7)
        ex, ctx = db.get("exposure"), db.get("context")
        if ex or ctx:
            self._section(fr, "Exposure budget and DRI context")
        if ex:
            lim = ", ".join("%s %s" % (n, "%.4g ms" % (t * 1e3) if t != float("inf") else "none")
                            for n, t in ex["limits"])
            lines = [("Status", ("feasible" if ex["feasible"] else "INFEASIBLE") +
                      ("  -  %s" % "; ".join(ex["violations"]) if ex["violations"] else "")),
                     ("Selected / longest admissible integration time", "%.4g ms / %s (limited by %s)" % (
                         ex["t_sel"] * 1e3, "%.4g ms" % (ex["t_rec"] * 1e3) if ex["t_rec"] != float("inf") else
                         "unbounded", ex["limiter"])),
                     ("Limits", lim),
                     ("Brightest credible pixel well fill", "%.1f %% of %.3g e- (%s)" % (
                         ex["wellfill_bright"], ex["capacity"], ex["capacity_limit"]))]
            for k_, v_ in lines:
                autowrap(ttk.Label(fr, text="%s:  %s" % (k_, v_), justify="left",
                                   foreground=WARN if k_ == "Status" and (ex["violations"] or not ex["feasible"])
                                   else None)).pack(anchor="w", fill="x", pady=(2, 0))
        if ctx:
            for k_, lab in (("task", "Task"), ("target", "Target"), ("operating_point", "Operating point"),
                            ("scene", "Scene"), ("mtf_source", "MTF source"), ("observer", "Observer"),
                            ("uncertainty", "Uncertainty"), ("validation", "Validation status")):
                autowrap(ttk.Label(fr, text="%s:  %s" % (lab, ctx.get(k_, "")), style="Muted.TLabel",
                                   justify="left")).pack(anchor="w", fill="x", pady=(2, 0))
            autowrap(ttk.Label(fr, text=ctx.get("statement", ""), justify="left")).pack(anchor="w", fill="x",
                                                                                         pady=(4, 0))

        # diagnostics
        w = res["warnings"]
        self._section(fr, "Diagnostics")
        line = ttk.Frame(fr)
        line.pack(fill="x")
        if ICON_FONT:
            tk.Label(line, text="" if w else "", font=(ICON_FONT, 12), bg=SURFACE,
                     fg=WARN if w else OK).pack(side="left", padx=(0, 8))
        ttk.Label(line, text=("%d warning(s) - see the Messages tab" % len(w)) if w else
                  "No warnings", foreground=WARN if w else OK).pack(side="left")
        for msg in w[:5]:
            autowrap(ttk.Label(fr, text="•  " + msg, justify="left", style="Muted.TLabel")).pack(anchor="w", fill="x", padx=(26, 0), pady=(4, 0))
        if len(w) > 5:
            ttk.Label(fr, text="   ... and %d more" % (len(w) - 5), style="Muted.TLabel").pack(anchor="w", padx=(26, 0))
        if self.workflow == "quick":
            ttk.Button(fr, text="Open engineering views (MTF, AMOP, MTDP, sensitivity) ...",
                       command=lambda: self.set_workflow("engineering")).pack(anchor="w", pady=(18, 0))
        self.summary.canvas.yview_moveto(0)

    def _explain_task(self, tv, db):
        sel = tv.selection()
        if not sel:
            return
        i = tv.index(sel[0])
        t = (db.get("tasks") or [])[i] if i < len(db.get("tasks") or []) else None
        if not t or "mtf_task" not in t:
            return
        txt = ("%s at %.3g km (criterion %g lp)\n\n"
               "Pixels: the projected target (%.2f m critical dimension) covers %.1f x %.1f detector samples.\n"
               "Cycles: with ideal sampling at most %.1f cycles fit across it (Nyquist); the task needs %g. %s\n"
               "MTF @ task frequency: the presampled system MTF is %.2f at %.3g cycles/mrad (the frequency of %g lp "
               "across the target at this range).\n"
               "CNR: target difference signal / total noise per pixel at this range = %.3g.\n"
               "Indicative limiter: %s. For a quantitative ranking run Sensitivity > Limiting factors.\n\n"
               "Model: %s\nCalibration status: %s\n\n"
               "Pixels and cycles are a geometric sampling bound, not a probability of task success." % (
                   t["name"], t["R0"], t["lp"], t["crit_m"], t["pix_h"], t["pix_v"], t["cyc_nyq"], t["lp"],
                   "The TRM4 AMOP allows bar patterns beyond Nyquist (aliased), so the range is sampling limited." if
                   t["lp"] > t["cyc_nyq"] else "", t["mtf_task"], t["f_task"], t["lp"], t["cnr_task"], t["limiter"],
                   db.get("model", ""), db.get("calibration", "")))
        messagebox.showinfo("Task diagnostics - %s" % t["name"], txt, parent=self)

    def _confidence_text(self, res):
        unc = self.analyses.get("uncertainty")
        if unc:
            return "%s:  %s" % (unc["label"], ";  ".join("%s %s" % (t, AN.interval(unc, t)[2]) for t in unc["base"]))
        return ("Nominal prediction - input uncertainties are not specified, so no uncertainty interval is given. "
                "Use Run > Uncertainty study with the known tolerances of your inputs.")

    # ------------------------------------------------------------------ result display
    def _show(self, res):
        t = self.info_tree
        t.delete(*t.get_children())
        secs = {}
        for sec, name, val, unit in res["info"]:
            if sec not in secs:
                secs[sec] = t.insert("", "end", text=sec, open=True, tags=("section",))
            t.insert(secs[sec], "end", text=name, values=(val, unit))
        self.msg.delete("1.0", "end")
        self.msg.insert("end", "Warnings and diagnostics\n", "title")
        if res["warnings"]:
            for w in res["warnings"]:
                self.msg.insert("end", "•  " + w + "\n", "warn")
        else:
            self.msg.insert("end", "No warnings - all checks passed.\n", "ok")
        self.msg.insert("end", "\nAssumptions\n", "title")
        for a in res.get("assumptions", []) or ["none recorded"]:
            self.msg.insert("end", "•  " + a + "\n", "note")
        pv = res.get("provenance") or {}
        self.msg.insert("end", "\nTraceability\n", "title")
        self.msg.insert("end", "•  %s, calculated %s, run ID %s\n" % (pv.get("model_version", ""), pv.get("time", ""),
                                                                    pv.get("run_id", "-")), "note")
        self.msg.insert("end", "•  Model reference: %s\n•  Validation version: %s\n" % (
            pv.get("model_reference", ""), pv.get("validation_version", "")), "note")
        for c in pv.get("coverage", []):
            self.msg.insert("end", "•  Coverage %s: %s%s\n" % ("+".join(c["components"]), c["source"],
                                                              " [%s]" % c["file"] if c["file"] else ""), "note")
        if pv.get("profile", {}).get("name"):
            self.msg.insert("end", "•  Camera profile: %s [%s]\n" % (pv["profile"]["name"], pv["profile"].get("config", "")),
                            "note")
        for im in pv.get("imports", []):
            self.msg.insert("end", "•  Import %s: %s  sha256 %s  (%s)\n" % (im["what"], im["name"], im["sha256"],
                                                                          im["notes"]), "note")
        for label, path, val, unit, src in pv.get("key_inputs", []):
            self.msg.insert("end", "•  %s = %s %s  [%s]\n" % (label, val, unit, dict(P.SOURCES).get(src, src)), "note")
        n = len(res["warnings"])
        self.right.tab(self.msg_tab, text="Messages (%d)" % n if n else "Messages")
        self._show_summary(res)
        self._plot_mtf(res)
        self._plot_amop(res)
        self._plot_fom(res)
        self._plot_range(res)
        self._plot_niirs(res)
        self._plot_spec(res)
        self._plot_validation(res)

    def _plot_validation(self, res):
        val = res.get("validation")
        if not val:
            self.tab_val.placeholder("No measured data - import curves on the 'Validation data' page (Lab workflow).")
            return
        curves = [it for it in val["items"] if np.ndim(it["measured"]) > 0]
        scal = [it for it in val["items"] if np.ndim(it["measured"]) == 0]
        n = max(1, len(curves))
        axs = self.tab_val.axes(n, 1) if curves else self.tab_val.axes(1, 1)
        for ax, it in zip(axs, curves):
            logy = it["unit"] in ("K", "contrast")
            plot = ax.semilogy if logy else ax.plot
            plot(it["rp"], it["measured"], "o", color="#ea580c", ms=4, label="measured")
            ok = np.isfinite(it["predicted"])
            plot(np.asarray(it["rp"])[ok], np.asarray(it["predicted"])[ok], "-", color="#2563eb", label="predicted")
            ax.set_title("%s  ·  mean |dev| %.1f %s" % (it["what"], it["mean_dev_pct"],
                                                        "%-pts" if it.get("abs_points") else "%"))
            ax.set_xlabel("spatial frequency [1/mrad]")
            ax.set_ylabel(it["unit"])
            ax.grid(alpha=0.3, which="both")
            ax.legend(fontsize=8)
        if not curves:
            axs[0].axis("off")
        txt = "  ".join("%s: measured %.3g, predicted %.3g %s (%+.1f %%)" % (it["what"], it["measured"], it["predicted"],
                                                                            it["unit"], it["mean_dev_pct"]) for it in scal)
        if val.get("missing_meta"):
            txt += ("   |   " if txt else "") + "missing calibration metadata: " + ", ".join(val["missing_meta"])
        if txt:
            self.tab_val.fig.suptitle(txt, fontsize=8, color="#4a5262")
        self.tab_val.draw()

    def _plot_mtf(self, res):
        axs = self.tab_mtf.axes(2, 1)
        m = res["mtf"]
        for ax, z, zl in zip(axs, "hv", ("Horizontal", "Vertical")):
            r = m["r"][z]
            for name, c in m["curves"][z].items():
                ls = "-" if name.startswith("System") else "--"
                ax.plot(r, c, ls, label=name, lw=2 if name.startswith("System (") else 1.2)
            a = res["amop"][z]
            ax.plot(a["rp"], a["amop"], "k-", lw=2, label="AMOP")
            ax.axvline(m["r_N"][z], color="grey", ls=":", label="Nyquist")
            dz = (res.get("dashboard") or {}).get("mtf", {}).get(z)
            if dz:
                ax.text(0.99, 0.97, "system prefilter: MTF50 %s 1/mrad, MTF @ Nyquist %.2f, aliasing risk %s" % (
                    "%.3g" % dz["mtf50"] if dz["mtf50"] else "-", dz["mtf_nyq"], dz["aliasing"]),
                    transform=ax.transAxes, ha="right", va="top", fontsize=7, color=MUTED)
            ax.set_xlim(0, r[-1])
            ax.set_ylim(0, 1.05)
            ax.set_title("%s MTFs" % zl)
            ax.set_xlabel("spatial frequency [1/mrad]")
            ax.grid(alpha=0.3)
        axs[0].legend(fontsize=7, ncol=3)
        self.tab_mtf.draw()

    def _plot_amop(self, res):
        ax = self.tab_amop.axes(1, 1)[0]
        for z, c in (("h", "C0"), ("v", "C1")):
            a = res["amop"][z]
            ax.plot(a["rp"], a["amop"], color=c, label="AMOP %s" % z)
            sysm = res["mtf"]["curves"][z]["System (pre x post)"]
            ax.plot(res["mtf"]["r"][z], sysm, "--", color=c, alpha=0.6, label="MTF_sys %s" % z)
            ax.axvline(res["mtf"]["r_N"][z], color=c, ls=":")
        ax.set_xlabel("pattern frequency r_p [1/mrad]")
        ax.set_ylabel("AMOP / MTF")
        ax.set_ylim(0, 1.1)
        ax.grid(alpha=0.3)
        ax.legend()
        ax.set_title("Average Modulation at Optimum Phase (dotted: Nyquist)")
        self.tab_amop.draw()

    def _plot_fom(self, res):
        f = res["fom"]
        mcp = res.get("mcp")
        axs = self.tab_fom.axes(1, 2 if mcp else 1)
        ax = axs[0]
        for z, c in (("h", "C0"), ("v", "C1")):
            v = np.where(np.isfinite(f[z]["val"]), f[z]["val"], np.nan)
            ax.semilogy(f[z]["rp"], v, color=c, label="%s %s" % (f["name"], z))
            ax.axvline(res["mtf"]["r_N"][z], color=c, ls=":")
        if len(f["avg"]["rp"]):
            ax.semilogy(f["avg"]["rp"], f["avg"]["val"], "k--", label="%s average" % f["name"])
        fm = res.get("fom_measured")
        if fm and fm["kind"] != "MCP":
            for z, c in (("h", "C0"), ("v", "C1")):
                ax.semilogy(fm[z]["rp"], fm[z]["val"], "o", color=c, ms=4, mfc="none",
                            label="measured %s %s%s" % (fm["kind"], z, " (used for ranges)" if fm["use"] == "replace" else ""))
        ax.set_xlabel("spatial frequency [1/mrad]")
        ax.set_ylabel("%s [%s]" % (f["name"], f["unit"]))
        ttl = f["name"] + ("" if res["category"] == "Thermal" else " at reference range %.3g km" % f["R_ref"])
        ax.set_title(ttl)
        ax.grid(alpha=0.3, which="both")
        ax.legend()
        if mcp:
            ax2 = axs[1]
            for z, c in (("h", "C0"), ("v", "C1")):
                ax2.semilogy(mcp[z]["rp"], mcp[z]["val"], color=c, label="MCP %s" % z)
            ax2.set_xlabel("spatial frequency [1/mrad]")
            ax2.set_ylabel("MCP (contrast)")
            ax2.set_title("Minimum Contrast Perceived (laboratory)")
            ax2.grid(alpha=0.3, which="both")
            ax2.legend()
        self.tab_fom.draw()

    def _plot_range(self, res):
        rg = res.get("range")
        if not rg:
            ax = self.tab_range.axes(1, 1)[0]
            ax.text(0.5, 0.5, "Range data is calculated in 'Field performance' mode only", ha="center", transform=ax.transAxes)
            self.tab_range.draw()
            return
        thermal = res["category"] == "Thermal"
        axs = self.tab_range.axes(2 if thermal else 1, 1)
        ax = axs[0]
        mn = "MNTD" if thermal else "MNDS"
        colors = ["C0", "C1", "C2", "C3", "C4"]
        styles = ["-", "--", ":"]
        for ia, a in enumerate(rg["atm"]):
            ax.loglog(a["R"], a["signal"], color="k", ls=styles[ia % 3], lw=2, label="%s %s" % (rg["quantity"], a["label"]))
            for it, t in enumerate(a["tasks"]):
                if ia == 0 and len(t["R_avg"]):
                    ax.loglog(t["R_avg"], t["mn_avg"], color=colors[it], label="%s %s (%g lp)" % (mn, t["name"], t["lp"]))
                if t["R0"] and np.isfinite(t["R0"]):
                    ax.axvline(t["R0"], color=colors[it], ls=styles[ia % 3], alpha=0.5)
        ax.set_xlabel("range [km]")
        ax.set_ylabel("%s / %s [%s]" % (rg["quantity"], mn, rg["unit"]))
        ax.grid(alpha=0.3, which="both")
        lo = min(np.nanmin(a["signal"][a["signal"] > 0]) for a in rg["atm"]) if rg["atm"] else 1e-3
        hi = max(np.nanmax(a["signal"]) for a in rg["atm"]) if rg["atm"] else 1
        ax.set_ylim(max(lo, hi * 1e-4), hi * 10)
        ax.set_title("Range performance (vertical lines: task ranges)")
        ax.legend(fontsize=7)
        if thermal:
            ax2 = axs[1]
            for ia, a in enumerate(rg["atm"]):
                ax2.loglog(a["R"], a["nlp"], color="k", ls=styles[ia % 3], label="resolved line pairs %s" % a["label"])
            for it, t in enumerate(rg["atm"][0]["tasks"] if rg["atm"] else []):
                ax2.axhline(t["lp"], color=colors[it], ls="-.", label="%s (%g lp)" % (t["name"], t["lp"]))
            ax2.set_xlabel("range [km]")
            ax2.set_ylabel("average resolved line pairs")
            ax2.set_ylim(0.1, 100)
            ax2.grid(alpha=0.3, which="both")
            ax2.legend(fontsize=7)
        self.tab_range.draw()

    def _plot_niirs(self, res):
        ni = res.get("niirs")
        axs = self.tab_niirs.axes(1, 1)
        ax = axs[0]
        if not ni or not ni["atm"]:
            ax.text(0.5, 0.5, "Enable 'Calculate NIIRS' (field mode, slant line of sight)", ha="center", transform=ax.transAxes)
        else:
            for a in ni["atm"]:
                ax.semilogx(a["R"], a["niirs"], label="NIIRS %s" % a["label"])
            ax.set_xlabel("slant range [km]")
            ax.set_ylabel("NIIRS (GIQE 5)")
            ax.set_ylim(0, 10)
            ax.grid(alpha=0.3, which="both")
            ax.legend()
            ax.set_title("National Imagery Interpretability Rating Scale")
        self.tab_niirs.draw()

    def _plot_spec(self, res):
        s = res["spectral"]
        atm = res.get("atmosphere")
        axs = self.tab_spec.axes(3 if atm else 2, 1)
        ax1, ax2 = axs[0], axs[1]
        if atm:
            ax3 = axs[2]
            for a in atm:
                ax3.semilogx(a["R"], a["tau"], label=a["label"])
            ax3.set_xlabel("range [km]")
            ax3.set_ylabel("band-effective transmission")
            ax3.set_ylim(0, 1.05)
            ax3.grid(alpha=0.3, which="both")
            ax3.legend(fontsize=8)
            ax3.set_title("Effective atmospheric transmission (direct path)")
        lam = s["lam"]
        ax1.plot(lam, s["qe"], label="detector QE [%]")
        ax1.plot(lam, s["w"] / max(s["w"].max(), 1e-30) * 100, label="MTF spectral weight (norm.) [%]")
        if "tau_o" in s:
            ax1.plot(lam, s["tau_o"] * 100, label="optics x filter transmission [%]")
        ax1.set_ylabel("%")
        ax1.grid(alpha=0.3)
        ax1.legend(fontsize=8)
        ax1.set_title("Detector response and spectral weighting")
        if res["category"] == "Visible":
            ax2.plot(lam, s["rho_T"], label="target reflectivity")
            ax2.plot(lam, s["rho_B"], label="background reflectivity")
        elif res["category"] == "General":
            ax2.plot(lam, s["eps_T"], label="target emissivity")
            ax2.plot(lam, s["eps_B"], label="background emissivity")
        if s["I"].max() > 0:
            ax2.plot(lam, s["I"] / s["I"].max(), "k--", label="irradiance (normalized)")
        if not atm:
            ax2.set_xlabel("wavelength [um]")
        ax2.grid(alpha=0.3)
        if ax2.lines:
            ax2.legend(fontsize=8)
        else:
            ax2.text(0.5, 0.5, "Thermal category: blackbody target/background", ha="center", transform=ax2.transAxes)
        self.tab_spec.draw()


class NewsDialog(tk.Toplevel):
    """New detectors found by the Detector Atlas watcher.  Close keeps the news unread (shown again at the next
    start); 'Mark as read' hides an item for good (kept in the settings)."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Detector Atlas news")
        self.configure(bg=SURFACE)
        self.transient(app)
        k = dpi_scale(app)
        self.geometry("%dx%d" % (int(760 * k), int(520 * k)))
        self.bind("<Escape>", lambda e: self.destroy())
        self.show_read = tk.BooleanVar(value=False)

        top = ttk.Frame(self, padding=(18, 16, 18, 6))
        top.pack(fill="x")
        ttk.Label(top, text="New detectors in the Detector Atlas", style="PageTitle.TLabel").pack(anchor="w")
        self.sub = ttk.Label(top, style="PageSub.TLabel")
        self.sub.pack(anchor="w", pady=(2, 0))

        bot = ttk.Frame(self, padding=(18, 8, 18, 14))
        bot.pack(side="bottom", fill="x")
        ttk.Checkbutton(bot, text="Show news already marked as read", variable=self.show_read,
                        command=self.refresh).pack(side="left")
        ttk.Button(bot, text="Close", command=self.destroy).pack(side="right")
        self.all_btn = ttk.Button(bot, text="Mark all as read", style="Accent.TButton", command=self.mark_all)
        self.all_btn.pack(side="right", padx=8)

        self.body = ScrollFrame(self, padding=(18, 4, 18, 4))
        self.body.pack(fill="both", expand=True)
        self.refresh()
        self.after(10, lambda: (self.update_idletasks(), self.geometry("+%d+%d" % (
            app.winfo_rootx() + (app.winfo_width() - self.winfo_width()) // 2,
            app.winfo_rooty() + (app.winfo_height() - self.winfo_height()) // 4))))

    def refresh(self):
        app = self.app
        news = getattr(app, "news", [])
        info = getattr(app, "news_info", {})
        done = NEWS.read_ids(app.settings)
        unread = [it for it in news if it["id"] not in done]
        app.__dict__.setdefault("_news_shown", set()).update(it["id"] for it in unread)
        shown = news if self.show_read.get() else unread
        src = "GitHub" if info.get("online") else \
            "local copy (GitHub not reachable)" if info.get("source") else "no feed reachable"
        checked = (info.get("last_checked") or "").replace("T", " ").rstrip("Z")
        self.sub.configure(text="%d unread of %d  ·  atlas scanned %s UTC  ·  source: %s\n"
                                "A newly detected listing is not necessarily a newly launched product - "
                                "verify the datasheet." % (len(unread), len(news), checked or "?", src))
        self.all_btn.state(["!disabled"] if unread else ["disabled"])
        for w in self.body.inner.winfo_children():
            w.destroy()
        if not shown:
            msg = "No new detectors - you're up to date." if news or info.get("source") else \
                "The atlas feed could not be read:\n%s" % (info.get("error") or "")
            ttk.Label(self.body.inner, text=msg, style="Muted.TLabel", justify="left").pack(anchor="w", pady=20)
        for it in shown:
            self._card(it, it["id"] in done)

    def _card(self, it, read):
        import webbrowser
        card = tk.Frame(self.body.inner, bg=SURFACE if read else ACCENT_SOFT, highlightthickness=1,
                        highlightbackground=BORDER, padx=12, pady=10)
        card.pack(fill="x", pady=5)
        bg = card["bg"]
        head = tk.Frame(card, bg=bg)
        head.pack(fill="x")
        if not read:
            tk.Label(head, text="NEW", bg=ACCENT, fg="white", font=("Segoe UI Semibold", 8), padx=6).pack(
                side="left", padx=(0, 8))
        tk.Label(head, text=NEWS.title(it), bg=bg, fg=TEXT, font=("Segoe UI Semibold", 11)).pack(side="left")
        ttk.Button(head, text="Mark as unread" if read else "Mark as read",
                   command=lambda: (self.app.set_news_read([it["id"]], not read), self.refresh())).pack(side="right")
        url = it.get("source_url") or it.get("listing_url")
        if url:
            ttk.Button(head, text="Open listing", command=lambda: webbrowser.open(url)).pack(side="right", padx=6)
        tk.Label(card, text=NEWS.details(it), bg=bg, fg=MUTED, font=("Segoe UI", 9), anchor="w",
                 justify="left").pack(fill="x", pady=(4, 0))
        if it.get("review"):
            autowrap(tk.Label(card, text=it["review"], bg=bg, fg=TEXT, font=("Segoe UI", 9), anchor="w",
                              justify="left")).pack(fill="x", pady=(2, 0))

    def mark_all(self):
        done = NEWS.read_ids(self.app.settings)
        self.app.set_news_read([it["id"] for it in getattr(self.app, "news", []) if it["id"] not in done])
        self.refresh()


class DetectorDialog(tk.Toplevel):
    """Pick a detector from the Detector Atlas website (local copy in detector_lookup_HTML/ or its online feed)
    or an atlas file, review/edit its values, apply them."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Detector lookup (Detector Atlas)")
        k = dpi_scale(app)
        self.geometry("%dx%d" % (int(1180 * k), int(760 * k)))
        self.result = None
        self.rows = []
        self.records = []
        self.rec = None

        from . import detector_atlas as DA
        self.DA = DA
        top = ttk.Frame(self, padding=(14, 14, 14, 6))
        top.pack(fill="x")
        ttk.Label(top, text="Atlas source:").grid(row=0, column=0, sticky="w")
        self.files = DA.atlas_files()
        self.file = tk.StringVar()
        self.file_cb = ttk.Combobox(top, textvariable=self.file, state="readonly", width=80,
                                    values=[DA.file_label(f) for f in self.files])
        self.file_cb.grid(row=0, column=1, sticky="we", padx=4)
        self.file_cb.bind("<<ComboboxSelected>>", lambda ev: self.load_file(self.files[self.file_cb.current()]))
        ttk.Button(top, text="Browse...", command=self.browse).grid(row=0, column=2, padx=(0, 4))
        ttk.Button(top, text="View in browser", command=self.open_html).grid(row=0, column=3)
        ttk.Label(top, text="Search:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.query = tk.StringVar()
        e = ttk.Entry(top, textvariable=self.query, width=40)
        e.grid(row=1, column=1, sticky="w", padx=4, pady=(6, 0))
        e.focus_set()
        self.query.trace_add("write", lambda *a: self.fill_list())
        bf = ttk.Frame(top)
        bf.grid(row=1, column=2, columnspan=2, sticky="e", pady=(6, 0))
        ttk.Label(bf, text="Band:").pack(side="left")
        self.band = tk.StringVar(value="All")
        self.band_cb = ttk.Combobox(bf, textvariable=self.band, state="readonly", width=8, values=["All"])
        self.band_cb.pack(side="left", padx=4)
        self.band_cb.bind("<<ComboboxSelected>>", lambda ev: self.fill_list())
        self.new_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(bf, text="New listings only", variable=self.new_only,
                        command=self.fill_list).pack(side="left", padx=(8, 0))
        top.columnconfigure(1, weight=1)
        self.status = tk.StringVar(value="Choose a detector from the list; its parameters are shown for review.")
        ttk.Label(self, textvariable=self.status, wraplength=int(1100 * k), style="Muted.TLabel",
                  padding=(14, 2)).pack(fill="x")

        bot = ttk.Frame(self, padding=14)
        bot.pack(side="bottom", fill="x")
        ttk.Button(bot, text="Apply selected to project", style="Accent.TButton", command=self.apply).pack(side="left")
        self.src_btn = ttk.Button(bot, text="Open source page", command=self.open_source, state="disabled")
        self.src_btn.pack(side="left", padx=6)
        ttk.Button(bot, text="Close", command=self.destroy).pack(side="right")

        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True, padx=14)
        lf = ttk.Frame(pw)
        cols = ("manufacturer", "model", "band", "format", "pitch", "cooling")
        self.tree = ttk.Treeview(lf, columns=cols, show="headings", selectmode="browse")
        for c, w in zip(cols, (90, 150, 50, 80, 50, 100)):
            self.tree.heading(c, text=c.capitalize(), command=lambda c=c: self.sort_by(c))
            self.tree.column(c, width=int(w * k), stretch=c == "model")
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda ev: self.select())
        self.tree.tag_configure("new", foreground=ACCENT)
        pw.add(lf, weight=2)
        rf = ttk.Frame(pw)
        self.summary = tk.Text(rf, height=7, wrap="word", relief="flat", font=FONT, bg=SURFACE_ALT, padx=10, pady=8,
                               highlightthickness=1, highlightbackground=BORDER)
        self.summary.pack(fill="x", padx=(8, 0), pady=(0, 6))
        self.table = ScrollFrame(rf)
        self.table.pack(fill="both", expand=True, padx=(8, 0))
        pw.add(rf, weight=3)
        self.sort_key = None

        if self.files:
            self.file_cb.current(0)
            self.load_file(self.files[0])
        else:
            self.status.set("No atlas files (.html / .json) found in %s - use Browse..." % DA.ATLAS_DIR)

    # ------------------------------------------------------------------
    def browse(self):
        fn = filedialog.askopenfilename(parent=self, title="Open Detector Atlas",
                                        initialdir=self.DA.ATLAS_DIR if os.path.isdir(self.DA.ATLAS_DIR) else None,
                                        filetypes=[("Detector Atlas", "*.html *.htm *.json"), ("All files", "*.*")])
        if not fn:
            return
        fn = os.path.abspath(fn)
        if fn not in self.files:
            self.files.append(fn)
            self.file_cb["values"] = [self.DA.file_label(f) for f in self.files]
        self.file_cb.current(self.files.index(fn))
        self.load_file(fn)

    def load_file(self, fn):
        if not self.DA.is_url(fn):
            try:
                self._loaded(fn, self.DA.load_info(fn))
            except self.DA.AtlasError as e:
                messagebox.showerror("Detector lookup", str(e), parent=self)
            return
        # online feed: download in the background so the dialog stays responsive
        self.status.set("Downloading the detector list from %s ..." % fn)
        self.file_cb.state(["disabled"])
        box = {}

        def work():
            try:
                box["res"] = self.DA.load_info(fn)
            except self.DA.AtlasError as e:
                box["err"] = e

        def poll():
            if not self.winfo_exists():
                return
            if th.is_alive():
                self.after(150, poll)
                return
            self.file_cb.state(["!disabled"])
            if "err" in box:
                self.status.set("Download failed - choose the local copy of the website.")
                messagebox.showerror("Detector lookup", str(box["err"]), parent=self)
                if getattr(self, "atlas_path", None) in self.files:
                    self.file_cb.current(self.files.index(self.atlas_path))
            else:
                self._loaded(fn, box["res"])

        th = threading.Thread(target=work, daemon=True)
        th.start()
        self.after(150, poll)

    def _loaded(self, fn, res):
        self.records, info = res
        self.atlas_path = fn
        self.band_cb["values"] = ["All"] + sorted({r.get("band") or "" for r in self.records} - {""})
        self.band.set("All")
        self.fill_list()
        n_new = sum(1 for r in self.records if r.get("_new_listing"))
        self.status.set("%d detectors in %s%s%s.  Choose one to see its parameters." % (
            len(self.records), self.DA.file_label(fn),
            ", atlas checked %s" % info["last_checked"].replace("T", " ").rstrip("Z") if info["last_checked"] else "",
            ", %d new listing(s) (blue)" % n_new if n_new else ""))

    def _row(self, r):
        fmt_ = "%sx%s" % (r.get("width") or "?", r.get("height") or "?")
        pitch = "%g" % r["pitch_um"] if isinstance(r.get("pitch_um"), (int, float)) else ""
        return (r.get("manufacturer") or "", r.get("model") or "", r.get("band") or "", fmt_, pitch,
                r.get("cooling_class") or "")

    def sort_by(self, col):
        i = ("manufacturer", "model", "band", "format", "pitch", "cooling").index(col)
        rev = self.sort_key == (col, False)
        key = (lambda r: float(self._row(r)[i] or 0)) if col == "pitch" else (lambda r: self._row(r)[i].lower())
        self.records.sort(key=key, reverse=rev)
        self.sort_key = (col, rev)
        self.fill_list()

    def fill_list(self):
        q = self.query.get().lower().split()
        band = self.band.get()
        self.tree.delete(*self.tree.get_children())
        self.shown = {}
        for i, r in enumerate(self.records):
            text = " ".join(str(v) for v in self._row(r) + (r.get("technology") or "", r.get("product_type") or "")).lower()
            if (band == "All" or r.get("band") == band) and all(w in text for w in q) and \
                    (not self.new_only.get() or r.get("_new_listing")):
                iid = self.tree.insert("", "end", values=self._row(r), tags=("new",) if r.get("_new_listing") else ())
                self.shown[iid] = r

    def select(self):
        sel = self.tree.selection()
        if not sel:
            return
        rec = self.rec = self.shown[sel[0]]
        DA = self.DA
        info = {"category": DA.category(rec), "detector_name": rec.get("model") or "",
                "manufacturer": rec.get("manufacturer") or ""}
        qe_custom, qe_note, qe_on = DA.qe_table(rec)
        self._show({"info": info, "suggestions": DA.suggestions(rec), "qe_custom": qe_custom, "qe_note": qe_note,
                    "qe_on": qe_on})
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", DA.summary(rec))
        self.src_btn.state(["!disabled"] if DA.source_urls(rec) else ["disabled"])
        has_qe = qe_on or DA.qe_shape(rec) is not None
        self.status.set("%s: %d parameter(s) from the atlas%s.  Review / edit the values, untick what you don't "
                        "want, then Apply." % (DA.label(rec), len(self.result["suggestions"]) + bool(qe_custom),
                                               " incl. spectral QE" if has_qe else
                                               " (QE material unknown - current QE setting kept)"))

    def _show(self, res):
        self.result = res
        info = res["info"]
        fr = self.table.inner
        for w in fr.winfo_children():
            w.destroy()
        self.rows = []
        for c, h in enumerate(("Apply", "Parameter", "Current", "Found (editable)", "Unit", "Source / note")):
            ttk.Label(fr, text=h, style="Head.TLabel").grid(row=0, column=c, sticky="w", padx=4)
        fr.columnconfigure(5, weight=1)
        cur = self.app.collect()
        items = [(path, label, unit, value, note) for _, path, label, unit, value, note in res["suggestions"]]
        items.insert(0, ("category", "Imager category", "", info["category"], ""))
        if res["qe_custom"]:
            items.append(("detector.qe_custom", "Spectral QE (custom table)", "um %", res["qe_custom"], res["qe_note"]))
        for i, (path, label, unit, value, note) in enumerate(items, start=1):
            on = tk.BooleanVar(value=(path != "detector.qe_custom" or res.get("qe_on", True)) and
                               path not in self.DA.NOT_TICKED)
            ttk.Checkbutton(fr, variable=on).grid(row=i, column=0, padx=4)
            ttk.Label(fr, text=label).grid(row=i, column=1, sticky="w", padx=4)
            try:
                current = get_path(cur, path)
            except (KeyError, IndexError):
                current = ""
            if path == "detector.qe_custom":
                current = cur["detector"]["qe_preset"]
                w = tk.Text(fr, height=5, width=22)
                w.insert("1.0", value)
                get = lambda w=w: w.get("1.0", "end").strip()
            elif path == "detector.qe_preset":
                var = tk.StringVar(value=value)
                w = ttk.Combobox(fr, textvariable=var, values=P.QE_NAMES[:-1], state="readonly", width=24)
                get = var.get
            else:
                var = tk.StringVar(value=fmt(value))
                w = ttk.Entry(fr, textvariable=var, width=22)
                get = var.get
            ttk.Label(fr, text=fmt(current), style="Muted.TLabel").grid(row=i, column=2, sticky="w", padx=4)
            w.grid(row=i, column=3, sticky="w", padx=4, pady=1)
            ttk.Label(fr, text=unit, style="Unit.TLabel").grid(row=i, column=4, sticky="w")
            ttk.Label(fr, text=note, wraplength=380, style="Muted.TLabel").grid(row=i, column=5, sticky="w", padx=4)
            self.rows.append((path, label, on, get))

    def apply(self):
        if not self.result:
            return
        a = self.app
        errors, n = [], 0
        applied = {}
        for path, label, on, get in self.rows:
            if not on.get():
                continue
            raw = get().strip()
            try:
                if path in ("category", "imager_type", "detector.qe_preset"):
                    val = raw
                elif path == "detector.qe_custom":
                    val = raw
                elif isinstance(get_path(a.project, path), int) and not isinstance(get_path(a.project, path), bool):
                    val = int(round(float(raw)))
                else:
                    val = float(raw)
            except ValueError:
                errors.append("%s: invalid value %r" % (label, raw))
                continue
            a._set_value(path, val)
            a._set_source(path, "manufacturer")
            applied[path] = val
            n += 1
            # switch the related mode so the applied value is actually used
            if path == "detector.qe_custom":
                a._set_value("detector.qe_preset", "Custom")
                a._set_value("detector.qe_unit", "percent")
                a._set_value("detector.qe_scale", 1.0)
                a._set_value("detector.uncooled_response", "preset")
            elif path == "detector.cs_F":
                a._set_value("detector.cs_mode", "fnumber")
            elif path in ("detector.cuton_um", "detector.cutoff_um") and not any(
                    r[0] == "detector.qe_custom" and r[2].get() for r in self.rows):
                a._set_value("detector.uncooled_response", "flat")
            elif path == "detector.lsb_e":
                a._set_value("detector.adc_mode", "carriers")
            elif path == "category":
                a._set_value("imager_type", "cooled" if val == "Thermal" else "staring")
        if any("detector." + v in applied for _h, v in _SQUARE):
            # a datasheet with its own vertical values decides whether the pixel is square
            cur = {k: applied.get("detector." + k, a.project["detector"][k]) for pair in _SQUARE for k in pair}
            a._set_value("detector.square", square_pixels(cur))
        a.refresh()
        a.status.set("Applied %d detector parameter(s) - you can still edit them in the parameter tabs" % n)
        if errors:
            messagebox.showwarning("Detector lookup", "Not applied:\n" + "\n".join(errors), parent=self)

    def open_source(self):
        import webbrowser
        urls = self.DA.source_urls(self.rec) if self.rec else []
        if len(urls) == 1:
            webbrowser.open(urls[0][1])
        elif urls:
            m = tk.Menu(self, tearoff=False)
            for title, u in urls:
                m.add_command(label="%s - %s" % (title, u), command=lambda u=u: webbrowser.open(u))
            m.tk_popup(self.src_btn.winfo_rootx(), self.src_btn.winfo_rooty() + self.src_btn.winfo_height())

    def open_html(self):
        path = getattr(self, "atlas_path", None)
        site = self.DA.site_root(path) if path else None
        if path and self.DA.is_url(path):
            import webbrowser
            webbrowser.open(path.rsplit("/data/", 1)[0] + "/")
        elif site:
            os.startfile(os.path.join(site, "index.html"))
        elif path and path.lower().endswith((".html", ".htm")):
            os.startfile(path)
        elif os.path.isdir(self.DA.ATLAS_DIR):
            os.startfile(self.DA.ATLAS_DIR)


def _windows_setup():
    """Crisp text on high-DPI screens and our own taskbar icon/group instead of Python's."""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TRM_HADMAAv1.ThermalRangeModel.1")
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def main():
    _windows_setup()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
