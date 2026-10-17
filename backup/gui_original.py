"""Tkinter graphical user interface for the TRM4 model.

The parameter dialogs follow the structure of the "Modify Individual Parameters" dialog of the
TRM4 software (Chapter 2 of the documentation).  Results are shown in tabs: system performance
data, MTFs, AMOP, MTDP/MDSP (MCP), range performance, NIIRS and spectral data.
"""
import copy
import json
import math
import os
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from . import presets as P
from .model import run_project, ModelError
from . import report

THERMAL = lambda p: p["category"] == "Thermal"
VISIBLE = lambda p: p["category"] == "Visible"
GENERAL = lambda p: p["category"] == "General"
NOT_THERMAL = lambda p: p["category"] != "Thermal"
COOLED = lambda p: p["category"] != "Thermal" or p["imager_type"] == "cooled"
UNCOOLED = lambda p: p["category"] == "Thermal" and p["imager_type"] == "uncooled"
RADIOMETRIC = lambda p: COOLED(p) and not (THERMAL(p) and p["detector"]["noise_mode"] == "measured")
ALWAYS = lambda p: True


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
        F("optics.diffraction", "Diffraction MTF", "choice", [("spectral", "Automatic spectral weighting"),
                                                             ("single", "Single wavelength")]),
        F("optics.lambda_diff_um", "Wavelength for diffraction", cond=lambda p: p["optics"]["diffraction"] == "single", unit="um"),
        F("optics.aberration", "Aberration", "choice", [("none", "No aberration"), ("q", "Aberration parameter q"),
                                                       ("blur", "Gaussian blur")]),
        F("optics.q", "Aberration parameter q (>1)", cond=lambda p: p["optics"]["aberration"] == "q"),
        F("optics.blur_um", "Gaussian blur sigma", cond=lambda p: p["optics"]["aberration"] == "blur", unit="um"),
        H("Transmission"),
        F("optics.tau_opt", "Peak transmission optics (w/o obscuration)"),
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
    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.inner.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.inner.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120), "units")


class PlotTab(ttk.Frame):
    def __init__(self, master, nrows=1, ncols=1):
        super().__init__(master)
        self.fig = Figure(figsize=(7, 5), dpi=100, constrained_layout=True)
        self.nrows, self.ncols = nrows, ncols
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        NavigationToolbar2Tk(self.canvas, self).update()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def axes(self, nrows=None, ncols=None):
        self.fig.clear()
        n, m = nrows or self.nrows, ncols or self.ncols
        return [self.fig.add_subplot(n, m, i + 1) for i in range(n * m)]

    def draw(self):
        self.canvas.draw_idle()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TRM4 - Thermal Range Model (TRM4.v3)")
        self.geometry("1500x900")
        self.project = P.make_template(list(P.TEMPLATES)[0])
        self.vars = {}
        self.rows = []
        self.result = None
        self.model = None
        self.busy = False
        self.file_path = None
        self._build()
        self._load_into_form(self.project)

    # ------------------------------------------------------------------ layout
    def _build(self):
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Head.TLabel", font=("Segoe UI", 9, "bold"), foreground="#1a5e8a")
        bar = ttk.Frame(self, padding=4)
        bar.pack(fill="x")
        ttk.Label(bar, text="Template:").pack(side="left")
        self.tpl = tk.StringVar(value=list(P.TEMPLATES)[0])
        ttk.Combobox(bar, textvariable=self.tpl, values=list(P.TEMPLATES), width=52, state="readonly").pack(side="left", padx=4)
        ttk.Button(bar, text="Load template", command=self.load_template).pack(side="left")
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(bar, text="Open project...", command=self.open_project).pack(side="left")
        ttk.Button(bar, text="Save project...", command=self.save_project).pack(side="left", padx=4)
        ttk.Button(bar, text="Export report...", command=self.export_report).pack(side="left")
        ttk.Button(bar, text="Detector lookup...", command=lambda: DetectorDialog(self)).pack(side="left", padx=4)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)
        self.calc_btn = ttk.Button(bar, text="Calculate  (F5)", command=self.calculate)
        self.calc_btn.pack(side="left")
        self.bind("<F5>", lambda e: self.calculate())
        self.prog = ttk.Progressbar(bar, length=180, maximum=1.0)
        self.prog.pack(side="right", padx=4)
        self.status = tk.StringVar(value="Ready")
        ttk.Label(bar, textvariable=self.status).pack(side="right", padx=8)

        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True)
        left = ttk.Notebook(pw)
        right = ttk.Notebook(pw)
        pw.add(left, weight=2)
        pw.add(right, weight=3)

        for tab_name, fields in TABS:
            sf = ScrollFrame(left)
            left.add(sf, text=tab_name)
            fr = sf.inner
            fr.columnconfigure(1, weight=1)
            for f in fields:
                self._make_field(fr, f)

        # results
        self.info_tree = ttk.Treeview(right, columns=("value", "unit"), show="tree headings")
        self.info_tree.heading("#0", text="Parameter")
        self.info_tree.heading("value", text="Value")
        self.info_tree.heading("unit", text="Unit")
        self.info_tree.column("#0", width=360)
        self.info_tree.column("value", width=220)
        self.info_tree.column("unit", width=90)
        right.add(self.info_tree, text="System data")
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
        self.msg = tk.Text(right, wrap="word", height=10)
        right.add(self.msg, text="Messages")
        self.right = right

    def _make_field(self, fr, f):
        r = len(fr.grid_slaves(column=0)) + len(fr.grid_slaves(column=2)) + 100
        row = fr.grid_size()[1]
        if f["kind"] == "header":
            w = ttk.Label(fr, text=f["label"], style="Head.TLabel")
            w.grid(row=row, column=0, columnspan=3, sticky="w", padx=6, pady=(10, 2))
            self.rows.append((f, [w], None))
            return
        lab = ttk.Label(fr, text=f["label"])
        lab.grid(row=row, column=0, sticky="w", padx=(12, 4), pady=1)
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
            w = tk.Text(fr, height=6, width=30)
        else:
            var = tk.StringVar()
            w = ttk.Entry(fr, textvariable=var)
            w.bind("<FocusOut>", lambda e: self.refresh())
            w.bind("<Return>", lambda e: self.refresh())
        w.grid(row=row, column=1, sticky="we", padx=4, pady=1)
        widgets.append(w)
        if f["unit"]:
            u = ttk.Label(fr, text=f["unit"], foreground="#555")
            u.grid(row=row, column=2, sticky="w", padx=(0, 8))
            widgets.append(u)
        self.rows.append((f, widgets, (var, w)))
        self.vars.setdefault(path, []).append((f, var, w))

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

    # ------------------------------------------------------------------ actions
    def load_template(self):
        self.file_path = None
        self._load_into_form(P.make_template(self.tpl.get()))
        self.status.set("Template loaded: %s" % self.tpl.get())

    def open_project(self):
        fn = filedialog.askopenfilename(filetypes=[("TRM4 project", "*.json"), ("All files", "*.*")])
        if not fn:
            return
        try:
            with open(fn, "r", encoding="utf-8") as fh:
                self._load_into_form(json.load(fh))
            self.file_path = fn
            self.status.set("Opened %s" % fn)
        except Exception as e:
            messagebox.showerror("Open project", str(e))

    def save_project(self):
        try:
            p = self.collect(strict=True)
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
            return
        fn = filedialog.asksaveasfilename(defaultextension=".json", initialfile=(p.get("name") or "project") + ".json",
                                          filetypes=[("TRM4 project", "*.json")])
        if fn:
            with open(fn, "w", encoding="utf-8") as fh:
                json.dump(p, fh, indent=2)
            self.file_path = fn
            self.status.set("Saved %s" % fn)

    def export_report(self):
        if not self.result:
            messagebox.showinfo("Export report", "Run a calculation first.")
            return
        fn = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text report", "*.txt")])
        if fn:
            report.write_report(fn, self.project, self.result)
            self.status.set("Report written to %s" % fn)

    def calculate(self):
        if self.busy:
            return
        try:
            p = self.collect(strict=True)
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
            return
        self.project = p
        self.busy = True
        self.calc_btn.state(["disabled"])
        self.prog["value"] = 0

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
        self.calc_btn.state(["!disabled"])
        if err:
            self.status.set("Error")
            messagebox.showerror("Calculation error", err)
            return
        self.model, self.result = model, res
        self.status.set("Calculation finished (%d warning(s))" % len(res["warnings"]))
        self.prog["value"] = 1.0
        try:
            self._show(res)
        except Exception:
            messagebox.showerror("Display error", traceback.format_exc())

    # ------------------------------------------------------------------ result display
    def _show(self, res):
        t = self.info_tree
        t.delete(*t.get_children())
        secs = {}
        for sec, name, val, unit in res["info"]:
            if sec not in secs:
                secs[sec] = t.insert("", "end", text=sec, open=True)
            t.insert(secs[sec], "end", text=name, values=(val, unit))
        self.msg.delete("1.0", "end")
        self.msg.insert("end", "Warnings / diagnostics:\n\n" + ("\n".join("- " + w for w in res["warnings"]) or "none"))
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
        self.geometry("1000x680")
        self.result = None
        self.rows = []

        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        ttk.Label(top, text="Detector (manufacturer + model):").grid(row=0, column=0, sticky="w")
        self.name = tk.StringVar()
        e = ttk.Entry(top, textvariable=self.name, width=50)
        e.grid(row=0, column=1, sticky="we", padx=4)
        e.bind("<Return>", lambda ev: self.search())
        e.focus_set()
        self.search_btn = ttk.Button(top, text="Search", command=self.search)
        self.search_btn.grid(row=0, column=2)
        ttk.Label(top, text="Anthropic API key (blank = use ANTHROPIC_API_KEY):").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.key = tk.StringVar()
        ttk.Entry(top, textvariable=self.key, show="*", width=50).grid(row=1, column=1, sticky="we", padx=4, pady=(4, 0))
        self.dl = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Download datasheet PDFs", variable=self.dl).grid(row=1, column=2, sticky="w", pady=(4, 0))
        top.columnconfigure(1, weight=1)
        self.status = tk.StringVar(value="Enter a detector name, e.g. 'SCD Blackbird 1920 XBn' or 'Lynred Daphnis HD MW'.")
        st = ttk.Frame(self, padding=(6, 0))
        st.pack(fill="x")
        self.prog = ttk.Progressbar(st, mode="indeterminate", length=120)
        self.prog.pack(side="right")
        ttk.Label(st, textvariable=self.status, wraplength=820).pack(side="left", fill="x")

        self.summary = tk.Text(self, height=4, wrap="word")
        self.summary.pack(fill="x", padx=6, pady=4)
        self.table = ScrollFrame(self)
        self.table.pack(fill="both", expand=True, padx=6)

        bot = ttk.Frame(self, padding=6)
        bot.pack(fill="x")
        ttk.Button(bot, text="Apply selected to project", command=self.apply).pack(side="left")
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
        key, dl = self.key.get().strip() or None, self.dl.get()

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
            ttk.Label(fr, text=fmt(current), foreground="#555").grid(row=i, column=2, sticky="w", padx=4)
            w.grid(row=i, column=3, sticky="w", padx=4, pady=1)
            ttk.Label(fr, text=unit, foreground="#555").grid(row=i, column=4, sticky="w")
            ttk.Label(fr, text=note, wraplength=380, foreground="#333").grid(row=i, column=5, sticky="w", padx=4)
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


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
