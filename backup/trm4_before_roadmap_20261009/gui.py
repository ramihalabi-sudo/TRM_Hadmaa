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
import sys
import threading
import time
import traceback
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib import cycler
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from . import presets as P
from .model import run_project, ModelError
from . import report
from . import zemax as Z
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
         "Atmosphere & turbulence": ""}

PAGE_INFO = {
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
    s.configure("TNotebook.Tab", background=BG, foreground=MUTED, padding=(14, 6), bordercolor=BG,
                lightcolor=BG, font=FONT)
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
OPT_ZEMAX = lambda p: p["optics"].get("mtf_source") == "zemax"
OPT_MODEL = lambda p: not OPT_ZEMAX(p)


def F(path, label, kind="float", opts=None, cond=ALWAYS, unit=""):
    return {"path": path, "label": label, "kind": kind, "opts": opts, "cond": cond, "unit": unit}


def H(text, cond=ALWAYS):
    return {"kind": "header", "label": text, "cond": cond}


YESNO = None
CATEGORY = [("Thermal", "Thermal (blackbody emissivity only)"), ("Visible", "Visible/NIR/SWIR (reflectivity only)"),
            ("General", "General (reflectivity + emissivity)")]

TABS = [
    ("General", [
        H("Project"),
        F("name", "Project name", "text"),
        F("category", "Imager category", "choice", CATEGORY),
        F("imager_type", "Imager type (Thermal)", "choice",
          [("cooled", "2nd generation staring / micro-scan (cooled FPA)"), ("uncooled", "Uncooled FPA")], THERMAL),
        H("Modelling (Sec. 2.4)"),
        F("mode.environment", "Field / Lab", "choice", [("field", "Field performance"),
                                                        ("lab", "Laboratory performance")]),
        F("mode.ref_range_km", "Reference range (MTF/MDSP)", "float", cond=lambda p: NOT_THERMAL(p) and
          p["mode"]["environment"] == "field", unit="km"),
        F("mode.stream", "Video / Still", "choice", [("video", "Video (eye integration)"), ("still", "Still (single frame)")]),
        F("mode.niirs", "Calculate NIIRS (GIQE 5)", "bool", cond=lambda p: p["mode"]["environment"] == "field"),
    ]),
    ("Basic imager", [
        H("Frame rate and FOV (Sec. 2.5)"),
        F("basic.frame_rate", "Frame rate", unit="Hz"),
        F("basic.fov_mode", "FOV", "choice", [("calculate", "Calculate FOV"), ("measured", "Measured FOV (check)")]),
        F("basic.fov_h_deg", "Measured horizontal FOV", cond=lambda p: p["basic"]["fov_mode"] == "measured", unit="deg"),
        F("basic.fov_v_deg", "Measured vertical FOV", cond=lambda p: p["basic"]["fov_mode"] == "measured", unit="deg"),
        H("Electronic interlace / micro-scan"),
        F("basic.interlace", "Electronic interlace", "choice",
          [("progressive", "No interlace - progressive scan"), ("electronic", "Electronic interlace"),
           ("pseudo", "Pseudo interlace")]),
        F("basic.microscan", "Micro-scan / dither", "choice",
          [("none", "None"), ("rectangular", "Rectangular"), ("circular", "Circular (2x2)"), ("diagonal", "Diagonal")]),
        F("basic.ms_steps_h", "Horizontal steps", "int", cond=lambda p: p["basic"]["microscan"] == "rectangular"),
        F("basic.ms_steps_v", "Vertical steps", "int", cond=lambda p: p["basic"]["microscan"] == "rectangular"),
        F("basic.integ_during_move", "Integration during movement", "bool",
          cond=lambda p: p["basic"]["microscan"] != "none"),
        H("Pixel binning / sensors"),
        F("basic.bin_h", "Binned pixels horizontal", "int"),
        F("basic.bin_v", "Binned pixels vertical", "int"),
        F("basic.n_sensors", "Number of sensors", "choice", [(1, "One"), (2, "Two")]),
    ]),
    ("Optics", [
        H("Aperture (Sec. 2.6)"),
        F("optics.aperture", "Type of aperture", "choice", [("circular", "Specific aperture"),
                                                           ("general", "General (F-number only)")]),
        F("optics.D_mm", "Aperture diameter D (0 = rectangular)", cond=lambda p: p["optics"]["aperture"] != "general", unit="mm"),
        F("optics.D_obsc_mm", "Central obscuration diameter", cond=lambda p: p["optics"]["aperture"] != "general", unit="mm"),
        F("optics.W_trunc_h_mm", "Width of truncated aperture (0 = none)", cond=lambda p: p["optics"]["aperture"] != "general", unit="mm"),
        F("optics.W_trunc_v_mm", "Height of truncated aperture (0 = none)", cond=lambda p: p["optics"]["aperture"] != "general", unit="mm"),
        F("optics.F_general", "Effective F-number", cond=lambda p: p["optics"]["aperture"] == "general"),
        F("optics.f_mm", "Focal length (horizontal)", unit="mm"),
        F("optics.diff_focal", "Different focal length vertical", "bool"),
        F("optics.f_v_mm", "Vertical focal length", cond=lambda p: p["optics"]["diff_focal"], unit="mm"),
        H("Diffraction MTF / aberrations"),
        F("optics.mtf_source", "Optics MTF from", "choice", [("model", "TRM4 model (diffraction + aberration)"),
                                                            ("zemax", "Zemax OpticStudio MTF file (.csv/.txt)")]),
        F("optics.diffraction", "Diffraction MTF", "choice", [("spectral", "Automatic spectral weighting"),
                                                             ("single", "Single wavelength")], cond=OPT_MODEL),
        F("optics.lambda_diff_um", "Wavelength for diffraction",
          cond=lambda p: OPT_MODEL(p) and p["optics"]["diffraction"] == "single", unit="um"),
        F("optics.aberration", "Aberration", "choice", [("none", "No aberration"), ("q", "Aberration parameter q"),
                                                       ("blur", "Gaussian blur")], cond=OPT_MODEL),
        F("optics.q", "Aberration parameter q (>1)", cond=lambda p: OPT_MODEL(p) and p["optics"]["aberration"] == "q"),
        F("optics.blur_um", "Gaussian blur sigma", cond=lambda p: OPT_MODEL(p) and p["optics"]["aberration"] == "blur", unit="um"),
        F("optics.zemax_mtf", "Zemax MTF export (FFT/Huygens MTF)", "file",
          {"check": Z.mtf_summary, "title": "Import Zemax OpticStudio MTF data"}, cond=OPT_ZEMAX),
        F("optics.zemax_mtf_unit", "Spatial frequency in file", "choice",
          [("auto", "Auto-detect (cycles/mm unless stated)"), ("mm", "cycles/mm (image space)"),
           ("mrad", "cycles/mrad (object space, afocal)")], cond=OPT_ZEMAX),
        F("optics.zemax_mtf_field", "Field number to use (1 = first)", "int", cond=OPT_ZEMAX),
        F("optics.zemax_mtf_h", "Horizontal MTF uses", "choice",
          [("sagittal", "Sagittal (vertical = tangential)"), ("tangential", "Tangential (vertical = sagittal)")],
          cond=OPT_ZEMAX),
        H("Transmission"),
        F("optics.tau_mode", "Optics transmission", "choice", [("value", "Peak transmission value"),
                                                              ("zemax", "Spectral, Zemax file (.csv/.txt)")]),
        F("optics.tau_opt", "Peak transmission optics (w/o obscuration)",
          cond=lambda p: p["optics"].get("tau_mode") != "zemax"),
        F("optics.zemax_tau", "Zemax transmission vs. wavelength", "file",
          {"check": Z.transmission_summary, "title": "Import Zemax OpticStudio transmission data"},
          cond=lambda p: p["optics"].get("tau_mode") == "zemax"),
        F("optics.tau_filter", "Transmission additional filter"),
    ]),
    ("Detector geometry", [
        H("Detector shape (Sec. 2.9)"),
        F("detector.shape", "Detector shape", "choice", [("rectangular", "Rectangular"), ("rhombic", "Rhombic"),
                                                        ("circular", "Circular"), ("loophole", "Circular with loop-hole")]),
        F("detector.a_h_um", "Horizontal dimension (active)", cond=lambda p: p["detector"]["shape"] in ("rectangular", "rhombic"), unit="um"),
        F("detector.a_v_um", "Vertical dimension (active)", cond=lambda p: p["detector"]["shape"] in ("rectangular", "rhombic"), unit="um"),
        F("detector.d_um", "Detector diameter (active)", cond=lambda p: p["detector"]["shape"] in ("circular", "loophole"), unit="um"),
        F("detector.d_hole_um", "Diameter of hole", cond=lambda p: p["detector"]["shape"] == "loophole", unit="um"),
        H("Focal plane geometry"),
        F("detector.n_h", "Number of horizontal detectors", "int"),
        F("detector.n_v", "Number of vertical detectors", "int"),
        F("detector.pitch_h_um", "Horizontal detector pitch", unit="um"),
        F("detector.pitch_v_um", "Vertical detector pitch", unit="um"),
        H("Charge transfer efficiency / crosstalk"),
        F("detector.cte_on", "Charge transfer efficiency", "bool"),
        F("detector.cte_h", "Horizontal CTE", cond=lambda p: p["detector"]["cte_on"]),
        F("detector.ntr_h", "Number of horizontal transfers", "int", cond=lambda p: p["detector"]["cte_on"]),
        F("detector.cte_v", "Vertical CTE", cond=lambda p: p["detector"]["cte_on"]),
        F("detector.ntr_v", "Number of vertical transfers", "int", cond=lambda p: p["detector"]["cte_on"]),
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
        F("detector.qe_custom", "Custom QE: 'lambda[um] QE[%]' per line", "multiline",
          cond=lambda p: p["detector"]["qe_preset"] == "Custom" and (not UNCOOLED(p) or p["detector"]["uncooled_response"] == "preset")),
        H("Temporal noise / NETD"),
        F("detector.noise_mode", "Temporal noise", "choice", [("calculated", "Calculated"), ("measured", "Measured NETD")],
          cond=lambda p: THERMAL(p) and p["imager_type"] == "cooled"),
        F("detector.noise_mode", "NETD", "choice", [("device", "Device measured"), ("detector", "Detector measured")], UNCOOLED),
        F("detector.netd_mK", "NETD", cond=lambda p: THERMAL(p) and (UNCOOLED(p) or p["detector"]["noise_mode"] == "measured"), unit="mK"),
        F("detector.meas_F", "Measurement F-number (0 = project)", cond=lambda p: UNCOOLED(p) and p["detector"]["noise_mode"] == "detector"),
        F("detector.meas_tau", "Measurement transmission (0 = project)", cond=lambda p: UNCOOLED(p) and p["detector"]["noise_mode"] == "detector"),
        F("detector.meas_TB_K", "Measurement BB temperature (0 = project)", cond=lambda p: UNCOOLED(p) and p["detector"]["noise_mode"] == "detector", unit="K"),
        F("detector.readout_mK", "Read-out (floor) noise", cond=lambda p: UNCOOLED(p) and p["detector"]["noise_mode"] == "detector", unit="mK"),
        F("detector.t_th_ms", "Detector thermal time constant", cond=UNCOOLED, unit="ms"),
        H("Integration time / storage", cond=COOLED),
        F("detector.tint_mode", "Integration time via", "choice", [("direct", "Direct specification"),
                                                                  ("duty", "Integration duty cycle"), ("wellfill", "Well fill")], COOLED),
        F("detector.tint_ms", "Integration time", cond=lambda p: COOLED(p) and p["detector"]["tint_mode"] == "direct", unit="ms"),
        F("detector.duty", "Integration duty cycle", cond=lambda p: COOLED(p) and p["detector"]["tint_mode"] == "duty"),
        F("detector.wellfill_pct", "Well fill", cond=lambda p: COOLED(p) and p["detector"]["tint_mode"] == "wellfill", unit="%"),
        F("detector.storage_e", "Storage capacity", cond=COOLED, unit="carriers"),
        H("Detector noise sources", cond=RADIOMETRIC),
        F("detector.electron_gain", "Electron gain", cond=RADIOMETRIC),
        F("detector.dark_A", "Dark current", cond=RADIOMETRIC, unit="A"),
        F("detector.noise_floor_e", "Noise floor (additive)", cond=RADIOMETRIC, unit="e-"),
        F("detector.noise_figure", "Noise figure (multiplicative)", cond=RADIOMETRIC),
        F("detector.adc_mode", "ADC resolution", "choice", [("none", "Not specified"), ("carriers", "LSB in carriers"),
                                                           ("mK", "LSB in temperature (Thermal)")]),
        F("detector.lsb_e", "LSB", cond=lambda p: p["detector"]["adc_mode"] == "carriers", unit="carriers"),
        F("detector.lsb_mK", "LSB", cond=lambda p: p["detector"]["adc_mode"] == "mK", unit="mK"),
        H("Cold shield / internal radiation", cond=lambda p: NOT_THERMAL(p) and not VISIBLE(p) or (THERMAL(p) and RADIOMETRIC(p))),
        F("detector.T_off_dev_K", "Temperature offset device-background", cond=lambda p: (GENERAL(p) or THERMAL(p)) and RADIOMETRIC(p), unit="K"),
        F("detector.T_off_opt_K", "Temperature offset optics-background", cond=lambda p: (GENERAL(p) or THERMAL(p)) and RADIOMETRIC(p), unit="K"),
        F("detector.T_cs_K", "Cold shield temperature", cond=lambda p: (GENERAL(p) or THERMAL(p)) and RADIOMETRIC(p), unit="K"),
        F("detector.cs_mode", "Cold shield definition via", "choice", [("efficiency", "Cold shield efficiency"),
                                                                       ("fnumber", "Effective F-number")],
          cond=lambda p: (GENERAL(p) or THERMAL(p)) and RADIOMETRIC(p)),
        F("detector.cs_eff", "Cold shield efficiency", cond=lambda p: (GENERAL(p) or THERMAL(p)) and RADIOMETRIC(p) and p["detector"]["cs_mode"] == "efficiency"),
        F("detector.cs_F", "Cold shield effective F-number", cond=lambda p: (GENERAL(p) or THERMAL(p)) and RADIOMETRIC(p) and p["detector"]["cs_mode"] == "fnumber"),
        H("Fixed pattern noise"),
        F("detector.fpn_mode", "Fixed pattern noise", "choice", [("none", "No noise"), ("measured", "Measured"),
                                                                ("estimate", "Estimate (fraction of NETD/NES)")]),
        F("detector.ietd_mK", "IETD", cond=lambda p: THERMAL(p) and p["detector"]["fpn_mode"] == "measured", unit="mK"),
        F("detector.prnu_pct", "PRNU", cond=lambda p: NOT_THERMAL(p) and p["detector"]["fpn_mode"] == "measured", unit="%"),
        F("detector.dsnu_A", "DSNU", cond=lambda p: NOT_THERMAL(p) and p["detector"]["fpn_mode"] == "measured", unit="A"),
        F("detector.fpn_fraction", "Fraction of NETD / NES", cond=lambda p: p["detector"]["fpn_mode"] == "estimate"),
    ]),
    ("Signal processing", [
        H("Digital filter (Sec. 2.15)"),
        F("dsp.filter_on", "Digital filter", "bool"),
        F("dsp.filter_dir", "Direction", "choice", [("both", "Both directions"), ("h", "Horizontal only"), ("v", "Vertical only")],
          cond=lambda p: p["dsp"]["filter_on"]),
        F("dsp.h_type", "Horizontal filter type", "choice", [("odd", "Odd"), ("even", "Even")], cond=lambda p: p["dsp"]["filter_on"]),
        F("dsp.h_coef", "Horizontal coefficients c0..c4", "list", cond=lambda p: p["dsp"]["filter_on"]),
        F("dsp.v_type", "Vertical filter type", "choice", [("odd", "Odd"), ("even", "Even")], cond=lambda p: p["dsp"]["filter_on"]),
        F("dsp.v_coef", "Vertical coefficients c0..c4", "list", cond=lambda p: p["dsp"]["filter_on"]),
        H("Special features"),
        F("dsp.zoom", "Electronic zoom factor", "int"),
        F("dsp.zoom_type", "Type of zoom", "choice", [("pixel", "Pixel replication"), ("bilinear", "Bilinear interpolation")]),
        F("dsp.lrep", "Line replication factor", "int"),
        F("dsp.lrep_type", "Line replication type", "choice", [("pixel", "Pixel replication"), ("linear", "Linear interpolation")]),
        F("dsp.crep", "Column replication factor", "int"),
        F("dsp.crep_type", "Column replication type", "choice", [("pixel", "Pixel replication"), ("linear", "Linear interpolation")]),
        H("Frame integration"),
        F("dsp.frames_on", "Simple frame integration", "bool"),
        F("dsp.n_frames", "Number of integrated frames", "int", cond=lambda p: p["dsp"]["frames_on"]),
        F("dsp.iir_on", "IIR frame integration filter", "bool"),
        F("dsp.iir_alpha", "Alpha", cond=lambda p: p["dsp"]["iir_on"]),
    ]),
    ("Display & observer", [
        H("Flat panel display (Sec. 2.18)"),
        F("display.n_h", "Number of horizontal elements", "int"),
        F("display.n_v", "Number of vertical elements", "int"),
        F("display.pitch_h_mm", "Horizontal element pitch", unit="mm"),
        F("display.pitch_v_mm", "Vertical element pitch", unit="mm"),
        F("display.luminance", "Operational display luminance", unit="cd/m2"),
        H("Observation of the display"),
        F("display.neglect_eye", "Neglect eye MTF", "bool"),
        F("display.observation", "Observation", "choice", [("direct", "Direct observation"), ("eyepiece", "Through eyepiece")]),
        F("display.distance_cm", "Distance display - observer", cond=lambda p: p["display"]["observation"] == "direct", unit="cm"),
        F("display.f_eyepiece_mm", "Focal length of eyepiece", cond=lambda p: p["display"]["observation"] == "eyepiece", unit="mm"),
        H("Eye characterization"),
        F("display.snr_th", "Threshold SNR"),
        F("display.t_eye_s", "Eye integration time", unit="s"),
    ]),
    ("Stabilization & MTFs", [
        H("Stabilization errors (Sec. 2.19)"),
        F("stab.neglect", "Neglect stabilization MTF", "bool"),
        F("stab.random_on", "Random vibrations", "bool"),
        F("stab.rand_h_mrad", "Horizontal random vibration rms", cond=lambda p: p["stab"]["random_on"], unit="mrad"),
        F("stab.rand_v_mrad", "Vertical random vibration rms", cond=lambda p: p["stab"]["random_on"], unit="mrad"),
        F("stab.lin_on", "Linear motion", "bool"),
        F("stab.lin_h", "Horizontal linear image velocity", cond=lambda p: p["stab"]["lin_on"], unit="mrad/s"),
        F("stab.lin_v", "Vertical linear image velocity", cond=lambda p: p["stab"]["lin_on"], unit="mrad/s"),
        F("stab.sin_on", "Sinusoidal vibrations", "bool"),
        F("stab.sin_h", "Horizontal sinusoidal amplitude", cond=lambda p: p["stab"]["sin_on"], unit="mrad"),
        F("stab.sin_v", "Vertical sinusoidal amplitude", cond=lambda p: p["stab"]["sin_on"], unit="mrad"),
        H("Additional imager MTFs (Sec. 2.20)"),
    ] + [f for w, wl in (("pre", "prefilter"), ("post", "postfilter")) for z, zl in (("h", "horizontal"), ("v", "vertical"))
         for f in (F("additional.%s_%s_type" % (w, z), "Additional %s %s" % (wl, zl), "choice",
                     [("none", "None"), ("sinc", "sinc"), ("sinc2", "sinc^2"), ("gaussian", "Gaussian"), ("rectangular", "Rectangular")]),
                   F("additional.%s_%s_par" % (w, z), "  first zero / std. deviation",
                     cond=(lambda w=w, z=z: (lambda p: p["additional"]["%s_%s_type" % (w, z)] != "none"))(), unit="1/mrad"))]),
    ("Target & scenario", [
        H("Target (Sec. 2.24 / 2.25)"),
        F("target.preset", "Standard target model", "choice", [("custom", "User defined")] +
          [(k, k) for k in P.THERMAL_TARGETS], THERMAL),
        F("target.alt_m", "Target altitude above ground", unit="m"),
        F("target.dT_K", "Temperature difference target-background", cond=lambda p: not VISIBLE(p), unit="K"),
        F("target.W_m", "Width", unit="m"),
        F("target.H_m", "Height", unit="m"),
        F("target.D_m", "Depth", unit="m"),
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
        H("Scenario"),
        F("target.aspect", "Target viewing aspect", "choice", [("front", "Front"), ("side", "Side"), ("diagonal", "Diagonal")]),
        F("target.flight", "Imager flight path", "choice", [("altitude", "Constant altitude"), ("angle", "Constant angle")]),
        F("target.altitude_m", "Altitude relative to target", cond=lambda p: p["target"]["flight"] == "altitude", unit="m"),
        F("target.angle_deg", "Observation angle (down = positive)", cond=lambda p: p["target"]["flight"] == "angle", unit="deg"),
        H("Task and number of line pairs"),
    ] + [f for i in range(3) for f in (F("target.tasks.%d.on" % i, "Task %d active" % (i + 1), "bool"),
                                        F("target.tasks.%d.name" % i, "  name", "text"),
                                        F("target.tasks.%d.lp" % i, "  number of line pairs"))]),
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
        F("irradiance.E_eff", "Effective scene irradiance", cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single"
          and p["irradiance"]["type"] == "broadband" and p["irradiance"]["spectrum"] == "effective", unit="W/m2"),
        F("irradiance.T_colour_K", "Colour temperature", cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single"
          and p["irradiance"]["type"] == "broadband" and p["irradiance"]["spectrum"] == "colour", unit="K"),
        F("irradiance.preset", "Natural source", "choice", [(n, "%s (peak %g)" % (n, P.NATURAL_SOURCES[n]["peak"])) for n in P.SOURCE_NAMES],
          cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single" and p["irradiance"]["type"] == "broadband"
          and p["irradiance"]["spectrum"] == "preset"),
        F("irradiance.E_peak", "Irradiance at peak", cond=lambda p: NOT_THERMAL(p) and p["irradiance"]["mode"] == "single"
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
        F("atmosphere.mode", "Transmission via", "choice", [("extinction", "Extinction coefficient (Beer's law)"),
                                                           ("visibility", "Visual range (Visible only)")]),
    ] + [f for i in range(3) for f in (
        F("atmosphere.atm.%d.on" % i, "Atmosphere %d" % (i + 1), "bool"),
        F("atmosphere.atm.%d.sigma" % i, "  extinction coefficient", unit="1/km",
          cond=(lambda i=i: lambda p: p["atmosphere"]["atm"][i]["on"] and not (VISIBLE(p) and p["atmosphere"]["mode"] == "visibility"))()),
        F("atmosphere.atm.%d.V_km" % i, "  visual range", unit="km",
          cond=(lambda i=i: lambda p: p["atmosphere"]["atm"][i]["on"] and VISIBLE(p) and p["atmosphere"]["mode"] == "visibility")()),
        F("atmosphere.atm.%d.tau0" % i, "  initial transmission", cond=(lambda i=i: lambda p: p["atmosphere"]["atm"][i]["on"])()),
        F("atmosphere.atm.%d.T_air_K" % i, "  air temperature", unit="K",
          cond=(lambda i=i: lambda p: p["atmosphere"]["atm"][i]["on"] and GENERAL(p))()),
        F("atmosphere.atm.%d.F_PR" % i, "  path radiance factor",
          cond=(lambda i=i: lambda p: p["atmosphere"]["atm"][i]["on"] and NOT_THERMAL(p))()))] + [
        H("Turbulence (Sec. 2.28)", cond=NOT_THERMAL),
        F("turbulence.on", "Consider turbulence", "bool", cond=NOT_THERMAL),
        F("turbulence.exposure", "Type of MTF", "choice", [("short", "Short exposure"), ("long", "Long exposure")],
          cond=lambda p: NOT_THERMAL(p) and p["turbulence"]["on"]),
        F("turbulence.cn2_mode", "Cn2 specified via", "choice", [("fixed", "Fixed value"), ("height", "Simplified height dependence")],
          cond=lambda p: NOT_THERMAL(p) and p["turbulence"]["on"]),
        F("turbulence.cn2", "Cn2", cond=lambda p: NOT_THERMAL(p) and p["turbulence"]["on"], unit="m^-2/3"),
        F("turbulence.h_ref_m", "Cn2 specified at height", cond=lambda p: NOT_THERMAL(p) and p["turbulence"]["on"]
          and p["turbulence"]["cn2_mode"] == "height", unit="m"),
        F("turbulence.time", "Day / night", "choice", [("day", "Day"), ("night", "Night")],
          cond=lambda p: NOT_THERMAL(p) and p["turbulence"]["on"] and p["turbulence"]["cn2_mode"] == "height"),
    ]),
]


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
        self.result = None
        self.model = None
        self.busy = False
        self.file_path = None
        self.saved_state = None
        self.dirty = False
        self.calc_time = None
        splash.say("Building parameter pages...")
        self._build()
        splash.say("Loading default template...")
        self._load_into_form(self.project)
        self._restore_window()
        self.protocol("WM_DELETE_WINDOW", self.exit_app)
        self.after(max(0, int(1100 - (time.time() - t0) * 1000)), lambda: (splash.destroy(), self.deiconify(),
                                                                           self.lift(), self.focus_force(),
                                                                           self.after(80, self._place_sash)))

    def _place_sash(self):
        self.update_idletasks()
        try:
            self.paned.sashpos(0, int(self.paned.winfo_width() * 0.42))
        except tk.TclError:
            pass

    def report_callback_exception(self, exc, val, tb):
        messagebox.showerror("Unexpected error", "".join(traceback.format_exception(exc, val, tb)), parent=self)

    def _load_icons(self):
        self.logo_big = self.logo_small = None
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
        for tab_name, fields in TABS:
            sf = ScrollFrame(self.page_host, padding=(10, 4, 16, 16))
            fr = sf.inner
            fr.columnconfigure(1, weight=1)
            for f in fields:
                self._make_field(fr, f)
            self.pages[tab_name] = sf
        self.current_page = None

        # results
        right = ttk.Notebook(pw)
        pw.add(right, weight=3)
        self.summary = ScrollFrame(right, padding=(22, 18, 22, 22))
        right.add(self.summary, text="Summary")
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
        right.add(tree_fr, text="System data")
        self.tab_mtf = PlotTab(right)
        right.add(self.tab_mtf, text="MTF")
        self.tab_amop = PlotTab(right)
        right.add(self.tab_amop, text="AMOP")
        self.tab_fom = PlotTab(right)
        right.add(self.tab_fom, text="MTDP / MDSP")
        self.tab_range = PlotTab(right)
        right.add(self.tab_range, text="Range")
        self.tab_niirs = PlotTab(right)
        right.add(self.tab_niirs, text="NIIRS")
        self.tab_spec = PlotTab(right)
        right.add(self.tab_spec, text="Spectral")
        msg_fr = ttk.Frame(right, padding=8)
        self.msg = tk.Text(msg_fr, wrap="word", height=10, relief="flat", font=FONT, padx=12, pady=10,
                           background=SURFACE, foreground=TEXT, highlightthickness=0, spacing1=2, spacing3=4)
        self.msg.tag_configure("title", font=("Segoe UI Semibold", 12), spacing3=8)
        self.msg.tag_configure("warn", foreground=WARN, lmargin1=8, lmargin2=24)
        self.msg.tag_configure("ok", foreground=OK)
        self.msg.pack(fill="both", expand=True)
        right.add(msg_fr, text="Messages")
        self.right = right
        self.msg_tab = msg_fr
        self._show_summary_placeholder()
        self.show_page(self.settings.get("page") if self.settings.get("page") in self.pages else TABS[0][0])

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
        mf.add_command(label="Export current plot...", accelerator="Ctrl+P", command=self.export_plot)
        mf.add_separator()
        mf.add_command(label="Exit", accelerator="Alt+F4", command=self.exit_app)
        m.add_cascade(label="File", menu=mf)

        mv = tk.Menu(m, tearoff=False)
        for i, (name, _) in enumerate(TABS):
            mv.add_command(label=name, accelerator="Ctrl+%d" % (i + 1) if i < 9 else "",
                           command=lambda n=name: self.show_page(n))
        m.add_cascade(label="Parameters", menu=mv)

        mr = tk.Menu(m, tearoff=False)
        mr.add_command(label="Calculate", accelerator="F5", command=self.calculate)
        mr.add_command(label="Detector lookup...", accelerator="Ctrl+D", command=self.detector_lookup)
        m.add_cascade(label="Run", menu=mr)

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
        for i, (name, _) in enumerate(TABS[:9]):
            self.bind_all("<Control-Key-%d>" % (i + 1), lambda e, n=name: self.show_page(n))

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
                   tip="Find detector parameters from datasheets with Claude  (Ctrl+D)").pack(side="left")
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
        side = tk.Frame(body, bg=SIDEBAR, width=int(230 * self.k))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="PARAMETERS", font=("Segoe UI Semibold", 8), fg="#7f8ba0", bg=SIDEBAR,
                 anchor="w").pack(fill="x", padx=18, pady=(16, 6))
        self.side_items = {}
        for name, _ in TABS:
            it = SidebarItem(side, name, self.show_page)
            it.pack(fill="x")
            self.side_items[name] = it
        foot = tk.Frame(side, bg=SIDEBAR)
        foot.pack(side="bottom", fill="x", padx=18, pady=14)
        tk.Label(foot, text="TRM4.v3 model  ·  v%s" % __version__, font=("Segoe UI", 8), fg="#6f7b90",
                 bg=SIDEBAR, anchor="w").pack(fill="x")
        tk.Label(foot, text="Fraunhofer IOSB TR 2021/04", font=("Segoe UI", 8), fg="#6f7b90", bg=SIDEBAR,
                 anchor="w").pack(fill="x")

    def show_page(self, name):
        if self.current_page == name:
            return
        if self.current_page:
            self.pages[self.current_page].pack_forget()
            self.side_items[self.current_page].select(False)
        self.pages[name].pack(fill="both", expand=True)
        self.side_items[name].select(True)
        self.page_title.configure(text=name)
        self.page_sub.configure(text=PAGE_INFO.get(name, ""))
        self.current_page = name

    def _make_field(self, fr, f):
        row = fr.grid_size()[1]
        if f["kind"] == "header":
            w = ttk.Label(fr, text=f["label"], style="Head.TLabel")
            w.grid(row=row, column=0, columnspan=4, sticky="w", padx=8, pady=(16 if row else 8, 4))
            self.rows.append((f, [w], None))
            return
        lab = ttk.Label(fr, text=f["label"])
        lab.grid(row=row, column=0, sticky="w", padx=(18, 10), pady=3)
        path, kind = f["path"], f["kind"]
        widgets = [lab]
        if kind == "bool":
            var = tk.BooleanVar()
            w = ttk.Checkbutton(fr, variable=var, command=self.refresh)
        elif kind == "choice":
            var = tk.StringVar()
            labels = [l for _, l in f["opts"]]
            w = ttk.Combobox(fr, values=labels, state="readonly")
            w.bind("<<ComboboxSelected>>", lambda e, w=w, f=f, var=var: self._choice_selected(w, f, var))
            var._combo = w
        elif kind == "multiline":
            var = None
            w = tk.Text(fr, height=6, width=30, relief="flat", font=("Consolas", 10), highlightthickness=1,
                        highlightbackground=BORDER, highlightcolor=ACCENT, padx=6, pady=4)
            w.bind("<KeyRelease>", lambda e: self._schedule_dirty_check())
        elif kind == "file":
            # imported text file stored in the project as {"name", "text"} (JSON in the variable)
            var = tk.StringVar(value=json.dumps({"name": "", "text": ""}))
            w = ttk.Frame(fr)
            ttk.Button(w, text="Import...", command=lambda f=f, var=var: self._import_file(f, var)).pack(side="left")
            ttk.Button(w, text="Clear", command=lambda var=var: (var.set(json.dumps({"name": "", "text": ""})),
                                                                 self.refresh())).pack(side="left", padx=(4, 0))
            info = ttk.Label(w, style="Muted.TLabel", wraplength=int(360 * self.k), justify="left")
            info.pack(side="left", padx=(10, 0), fill="x", expand=True)
            var.trace_add("write", lambda *_a, f=f, var=var, info=info: self._show_file_info(f, var, info))
            self._show_file_info(f, var, info)
        else:
            var = tk.StringVar()
            w = ttk.Entry(fr, textvariable=var)
            w.bind("<FocusOut>", lambda e: self.refresh())
            w.bind("<Return>", lambda e: self.refresh())
            w.bind("<KeyRelease>", lambda e: self._schedule_dirty_check())
        w.grid(row=row, column=1, sticky="we", padx=4, pady=3)
        widgets.append(w)
        if f["unit"]:
            u = ttk.Label(fr, text=f["unit"], style="Unit.TLabel")
            u.grid(row=row, column=2, sticky="w", padx=(2, 8))
            widgets.append(u)
        text = help_for(path)
        if text:
            q = tk.Label(fr, text="?", font=("Segoe UI Semibold", 8), bg=ACCENT_SOFT, fg=ACCENT, width=2,
                         cursor="question_arrow")
            q.grid(row=row, column=3, sticky="w", padx=(0, 4))
            q.bind("<Enter>", lambda e: q.configure(bg=ACCENT, fg="white"), add="+")
            q.bind("<Leave>", lambda e: q.configure(bg=ACCENT_SOFT, fg=ACCENT), add="+")
            Tooltip(q, text, delay=150, wrap=int(340 * self.k), click=True)
            widgets.append(q)
        self.rows.append((f, widgets, (var, w)))
        self.vars.setdefault(path, []).append((f, var, w))

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
            info.configure(text="%s\n%s" % (v.get("name", ""), f["opts"]["check"](v["text"])), foreground=MUTED)
        except Exception as e:
            info.configure(text="%s\n%s" % (v.get("name", ""), e), foreground=WARN)

    def _import_file(self, f, var):
        fn = filedialog.askopenfilename(parent=self, title=f["opts"]["title"], initialdir=self._start_dir(),
                                        filetypes=[("Zemax OpticStudio export", "*.csv *.txt"), ("All files", "*.*")])
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
        self.refresh()
        self.status.set("Imported %s  -  %s" % (os.path.basename(fn), summary))

    def _choice_selected(self, w, f, var):
        lab = w.get()
        for val, l in f["opts"]:
            if l == lab:
                var.set(json.dumps(val))
        if f["path"] == "category":
            cat = json.loads(var.get())
            self._set_value("imager_type", "cooled" if cat == "Thermal" else "staring")
        if f["path"] == "target.preset":
            name = json.loads(var.get())
            if name in P.THERMAL_TARGETS:
                t = P.THERMAL_TARGETS[name]
                for k in ("W_m", "H_m", "D_m", "T_bg_K", "dT_K"):
                    self._set_value("target." + k, t[k])
                for i, (lp, on) in enumerate(zip(t["tasks"], t["task_on"])):
                    self._set_value("target.tasks.%d.lp" % i, lp)
                    self._set_value("target.tasks.%d.on" % i, on)
        if f["path"] == "irradiance.preset":
            self._set_value("irradiance.E_peak", P.NATURAL_SOURCES[json.loads(var.get())]["peak"])
        self.refresh()

    # ------------------------------------------------------------------ values
    def _set_value(self, path, value):
        for f, var, w in self.vars.get(path, []):
            k = f["kind"]
            if k == "bool":
                var.set(bool(value))
            elif k == "choice":
                var.set(json.dumps(value))
                lab = next((l for v, l in f["opts"] if v == value), None)
                w.set(lab if lab is not None else "")
            elif k == "multiline":
                w.delete("1.0", "end")
                w.insert("1.0", str(value))
            elif k == "list":
                var.set(", ".join(fmt(x) for x in value))
            elif k == "file":
                var.set(json.dumps(value if isinstance(value, dict) else {"name": "", "text": ""}))
            else:
                var.set(fmt(value))

    def _load_into_form(self, project):
        self.project = P.deep_merge(P.DEFAULT_PROJECT, project)
        for path in self.vars:
            try:
                self._set_value(path, get_path(self.project, path))
            except (KeyError, IndexError):
                pass
        self.refresh()
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
        self.cat_label.set("%s%s  ·  %s" % (p.get("category", ""), " / " + kind if p.get("category") == "Thermal" else "",
                                           "Field" if p["mode"]["environment"] == "field" else "Laboratory"))

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
            p_cur = p
            for f, var, w in entries:
                if f["kind"] == "choice" and not f["cond"](p_cur) and len(entries) > 1:
                    continue
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
        if strict and errors:
            raise ValueError("\n".join(errors))
        return p

    def refresh(self):
        p = self.collect()
        self.project = p
        for f, widgets, _ in self.rows:
            try:
                show = f["cond"](p)
            except Exception:
                show = True
            for w in widgets:
                if show:
                    w.grid()
                else:
                    w.grid_remove()
        if self.saved_state is not None:
            self._set_dirty(self._state_of(p) != self.saved_state)

    # ------------------------------------------------------------------ actions
    def _start_dir(self):
        d = self.settings.get("last_dir")
        return d if d and os.path.isdir(d) else PROJECT_DIR

    def _clear_results(self):
        self.result = self.model = None
        self.info_tree.delete(*self.info_tree.get_children())
        for tab in (self.tab_mtf, self.tab_amop, self.tab_fom, self.tab_range, self.tab_niirs, self.tab_spec):
            tab.placeholder("Results appear here after the calculation (F5).")
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
            report.write_report(fn, self.project, self.result)
            self.settings["last_dir"] = os.path.dirname(fn)
            self.status.set("Report written to %s" % fn)

    def export_plot(self):
        tab = self.nametowidget(self.right.select())
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
        self.settings["page"] = self.current_page
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
                ("Ctrl+D", "Detector lookup"), ("Ctrl+1 ... 9", "Go to parameter page"), ("F1", "Documentation")]
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
        ttk.Label(fr, text="Version %s" % __version__, style="Muted.TLabel").grid(row=1, column=1, sticky="w")
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

    def _show_summary(self, res):
        fr = self._clear_summary()
        p = self.project
        ttk.Label(fr, text=p.get("name") or "Untitled project", font=("Segoe UI Semibold", 17)).pack(anchor="w")
        sub = "%s  ·  %s  ·  %s  ·  calculated %s" % (
            res["category"] + (" (%s)" % p["imager_type"] if res["category"] == "Thermal" else ""),
            "Field performance" if p["mode"]["environment"] == "field" else "Laboratory performance",
            "video" if p["mode"]["stream"] == "video" else "still image", self.calc_time)
        ttk.Label(fr, text=sub, style="Muted.TLabel").pack(anchor="w", pady=(2, 0))

        # range performance
        rg = res.get("range")
        if rg and rg["atm"]:
            self._section(fr, "Range performance  ·  %s" % rg["atm"][0]["label"])
            cards = []
            a0 = rg["atm"][0]
            for i, t in enumerate(a0["tasks"]):
                R0 = t["R0"]
                if R0 is None:
                    txt = "< %.2f" % a0["R"][0]
                elif not np.isfinite(R0):
                    txt = "> %.0f" % a0["R"][-1]
                else:
                    txt = "%.2f" % R0
                cards.append((("%s  (%g lp)" % (t["name"], t["lp"]), txt, "km"),
                              {"color": TASK_COLORS[i % len(TASK_COLORS)]}))
            self._grid_cards(fr, cards, cols=max(1, min(3, len(cards))))
            if len(rg["atm"]) > 1:
                cols = ["task"] + ["a%d" % i for i in range(len(rg["atm"]))]
                tv = ttk.Treeview(fr, columns=cols, show="headings", height=len(a0["tasks"]))
                tv.heading("task", text="Task", anchor="w")
                for i, a in enumerate(rg["atm"]):
                    tv.heading("a%d" % i, text=a["label"], anchor="w")
                for it, t in enumerate(a0["tasks"]):
                    vals = [t["name"]]
                    for a in rg["atm"]:
                        R0 = a["tasks"][it]["R0"]
                        vals.append("< %.2f km" % a["R"][0] if R0 is None else (
                            "> %.0f km" % a["R"][-1] if not np.isfinite(R0) else "%.2f km" % R0))
                    tv.insert("", "end", values=vals)
                tv.pack(fill="x", pady=(4, 0))
        elif p["mode"]["environment"] != "field":
            self._section(fr, "Range performance")
            ttk.Label(fr, text="Ranges are calculated in 'Field performance' mode (General page).",
                      style="Muted.TLabel").pack(anchor="w")

        # key system figures
        self._section(fr, "Key system figures")
        kpis = []

        def add(caption, needle, first=True, take=None):
            v = self._info_get(res, needle, first)
            if v:
                val, unit = v
                if take is not None:
                    val = val.split(" / ")[take]
                    unit = unit.split(" / ")[take] if " / " in unit else unit
                kpis.append(((caption, val.replace(" x ", " × "), unit), {}))

        add("Field of view (h × v)", "Field of view h x v")
        add("Samples (h × v)", "Number of samples h x v")
        add("Detector angular subtense", "Detector angular subtense h x v")
        add("Nyquist frequency", "Nyquist frequency h x v")
        add("Effective focal length", "Effective focal length")
        add("Effective F-number", "Effective F-number")
        if res["category"] == "Thermal":
            add("NETD", "NETD used")
            add("IETD", "IETD used")
        else:
            add("SNR at reference range", "SNR (difference signal / NES)")
            add("Well fill (background)", "Well fill (background)")
        add("%s at Nyquist (h)" % res["fom"]["name"], "at Nyquist (h)", first=False)
        add("System magnification", "System magnification")
        self._grid_cards(fr, kpis, cols=3)

        # diagnostics
        w = res["warnings"]
        self._section(fr, "Diagnostics")
        line = ttk.Frame(fr)
        line.pack(fill="x")
        if ICON_FONT:
            tk.Label(line, text="" if w else "", font=(ICON_FONT, 12), bg=SURFACE,
                     fg=WARN if w else OK).pack(side="left", padx=(0, 8))
        ttk.Label(line, text=("%d warning(s) - see the Messages tab" % len(w)) if w else
                  "No warnings", foreground=WARN if w else OK).pack(side="left")
        for msg in w[:4]:
            ttk.Label(fr, text="•  " + msg, wraplength=int(620 * self.k), justify="left",
                      style="Muted.TLabel").pack(anchor="w", padx=(26, 0), pady=(4, 0))
        if len(w) > 4:
            ttk.Label(fr, text="   ... and %d more" % (len(w) - 4), style="Muted.TLabel").pack(anchor="w", padx=(26, 0))
        self.summary.canvas.yview_moveto(0)

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
        n = len(res["warnings"])
        self.right.tab(self.msg_tab, text="Messages (%d)" % n if n else "Messages")
        self._show_summary(res)
        self._plot_mtf(res)
        self._plot_amop(res)
        self._plot_fom(res)
        self._plot_range(res)
        self._plot_niirs(res)
        self._plot_spec(res)

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
        ax1, ax2 = self.tab_spec.axes(2, 1)
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
        ax2.set_xlabel("wavelength [um]")
        ax2.grid(alpha=0.3)
        if ax2.lines:
            ax2.legend(fontsize=8)
        else:
            ax2.text(0.5, 0.5, "Thermal category: blackbody target/background", ha="center", transform=ax2.transAxes)
        self.tab_spec.draw()


class DetectorDialog(tk.Toplevel):
    """Look up a detector with Claude, review/edit the found values, apply the selected ones."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Detector lookup (Claude + web search)")
        k = dpi_scale(app)
        self.result = None
        self.rows = []

        top = ttk.Frame(self, padding=(14, 14, 14, 6))
        top.pack(fill="x")
        ttk.Label(top, text="Detector (manufacturer + model):").grid(row=0, column=0, sticky="w")
        self.name = tk.StringVar()
        e = ttk.Entry(top, textvariable=self.name, width=50)
        e.grid(row=0, column=1, sticky="we", padx=4)
        e.bind("<Return>", lambda ev: self.search())
        e.focus_set()
        self.search_btn = ttk.Button(top, text="Search", style="Accent.TButton", command=self.search)
        self.search_btn.grid(row=0, column=2)
        ttk.Label(top, text="Anthropic API key (blank = use ANTHROPIC_API_KEY):").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.key = tk.StringVar()
        ttk.Entry(top, textvariable=self.key, show="*", width=50).grid(row=1, column=1, sticky="we", padx=4, pady=(4, 0))
        self.dl = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Download datasheet PDFs", variable=self.dl).grid(row=1, column=2, sticky="w", pady=(4, 0))
        top.columnconfigure(1, weight=1)
        self.status = tk.StringVar(value="Enter a detector name, e.g. 'SCD Blackbird 1920 XBn' or 'Lynred Daphnis HD MW'.")
        st = ttk.Frame(self, padding=(14, 4))
        st.pack(fill="x")
        self.prog = ttk.Progressbar(st, mode="indeterminate", length=120)
        self.prog.pack(side="right")
        ttk.Label(st, textvariable=self.status, wraplength=int(820 * k), style="Muted.TLabel").pack(side="left", fill="x")

        self.summary = tk.Text(self, height=4, wrap="word", relief="flat", font=FONT, bg=SURFACE_ALT, padx=10, pady=8,
                               highlightthickness=1, highlightbackground=BORDER)
        self.summary.pack(fill="x", padx=14, pady=6)
        self.table = ScrollFrame(self)
        self.table.pack(fill="both", expand=True, padx=14)

        bot = ttk.Frame(self, padding=14)
        bot.pack(fill="x")
        ttk.Button(bot, text="Apply selected to project", style="Accent.TButton", command=self.apply).pack(side="left")
        self.folder_btn = ttk.Button(bot, text="Open datasheet folder", command=self.open_folder, state="disabled")
        self.folder_btn.pack(side="left", padx=6)
        ttk.Button(bot, text="Close", command=self.destroy).pack(side="right")

    # ------------------------------------------------------------------
    def search(self):
        name = self.name.get().strip()
        if not name:
            return
        self.search_btn.state(["disabled"])
        self.prog.start(12)
        key, dl = self.key.get().strip().strip("'\"").strip() or None, self.dl.get()

        def progress(msg):
            self.after(0, lambda: self.status.set(msg))

        def work():
            from . import detector_lookup as DL
            try:
                res = DL.lookup(name, api_key=key, progress=progress, download=dl)
                self.after(0, lambda: self._show(res, None))
            except DL.DetectorLookupError as e:
                self.after(0, lambda e=e: self._show(None, str(e)))
            except Exception:
                tb = traceback.format_exc()
                self.after(0, lambda: self._show(None, tb))

        threading.Thread(target=work, daemon=True).start()

    def _show(self, res, err):
        if not self.winfo_exists():
            return
        self.prog.stop()
        self.search_btn.state(["!disabled"])
        if err:
            self.status.set("Lookup failed")
            messagebox.showerror("Detector lookup", err, parent=self)
            return
        self.result = res
        info = res["info"]
        msg = "Found %d parameter(s) for %s %s." % (len(res["suggestions"]), info["manufacturer"], info["detector_name"])
        if res["pdfs"]:
            msg += "  %d PDF(s) saved to %s" % (len(res["pdfs"]), res["folder"])
        if res["pdf_failures"]:
            msg += "  (%d download(s) failed)" % len(res["pdf_failures"])
        self.status.set(msg + "  Review / edit the values, untick what you don't want, then Apply.")
        self.folder_btn.state(["!disabled"] if os.path.isdir(res["folder"]) else ["disabled"])
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", info["summary"] + "\n\nSources: " + "; ".join(info["sources"]) +
                            ("\nFailed downloads: " + "; ".join(res["pdf_failures"]) if res["pdf_failures"] else ""))

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
            on = tk.BooleanVar(value=True)
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
        for path, label, on, get in self.rows:
            if not on.get():
                continue
            raw = get().strip()
            try:
                if path in ("category", "imager_type"):
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
            n += 1
            # switch the related mode so the applied value is actually used
            if path == "detector.qe_custom":
                a._set_value("detector.qe_preset", "Custom")
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
        a._set_value("name", self.result["info"]["detector_name"])
        a.refresh()
        a.status.set("Applied %d detector parameter(s) - you can still edit them in the parameter tabs" % n)
        if errors:
            messagebox.showwarning("Detector lookup", "Not applied:\n" + "\n".join(errors), parent=self)

    def open_folder(self):
        if self.result and os.path.isdir(self.result["folder"]):
            os.startfile(self.result["folder"])


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
