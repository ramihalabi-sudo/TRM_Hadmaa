"""Short explanations for the parameter form ("?" icons in the GUI).

Each entry says what the parameter means and why the model needs it.  Keys are the parameter
paths used in gui.TABS; list indices (tasks, atmospheres) are written as "N".
"""
import re

HELP = {
    # ---------------------------------------------------------------- General
    "name": "Free name of the project. Shown in the window title and in reports; not used in the calculation.",
    "category": "Spectral category of the imager.\n"
                "Thermal: scene is described by temperatures only (emission, MWIR/LWIR).\n"
                "Visible/NIR/SWIR: scene is described by reflectivity and an illumination source.\n"
                "General: both reflection and emission are modelled.\n"
                "It decides which radiometry and which parameters are used.",
    "imager_type": "Detector technology of a thermal imager. Cooled FPAs use a photon-detector noise model "
                   "(integration time, well capacity, cold shield); uncooled microbolometers use NETD and a "
                   "thermal time constant.",
    "mode.environment": "Field: performance at range through the atmosphere (range curves, NIIRS).\n"
                        "Laboratory: performance at the imager entrance, without atmosphere (e.g. MRTD/MTDP).",
    "mode.ref_range_km": "Range at which the atmosphere / turbulence MTF and the MDSP are evaluated for the "
                         "frequency-domain plots. Needed because these quantities depend on range.",
    "mode.stream": "Video: the eye integrates several frames (temporal noise averaging).\n"
                   "Still: a single frame is observed, so noise is not averaged by the eye.",
    "mode.niirs": "Also compute the image-quality rating NIIRS with the General Image Quality Equation "
                  "(GIQE 5) versus range.",

    # ---------------------------------------------------------------- Basic imager
    "basic.frame_rate": "Number of frames per second. Sets the maximum integration time and how many frames "
                        "the eye integrates, so it affects temporal noise.",
    "basic.fov_mode": "Calculate the field of view from detector count, pitch and focal length, or enter a "
                      "measured FOV to check it against the calculated one.",
    "basic.fov_h_deg": "Measured horizontal field of view. Used only to compare with the calculated FOV.",
    "basic.fov_v_deg": "Measured vertical field of view. Used only to compare with the calculated FOV.",
    "basic.interlace": "How lines are read out. Interlace changes the vertical sampling and the effective "
                       "number of lines seen per frame.",
    "basic.microscan": "Sub-pixel image shift between frames (dither). Increases sampling and reduces "
                       "aliasing, at the cost of frame rate.",
    "basic.ms_steps_h": "Number of micro-scan positions in horizontal direction (rectangular pattern).",
    "basic.ms_steps_v": "Number of micro-scan positions in vertical direction (rectangular pattern).",
    "basic.integ_during_move": "Detector integrates while the micro-scanner moves. Adds a motion blur MTF.",
    "basic.bin_h": "Number of adjacent pixels summed horizontally. Improves signal-to-noise but reduces "
                   "resolution (1 = no binning).",
    "basic.bin_v": "Number of adjacent pixels summed vertically. Improves signal-to-noise but reduces "
                   "resolution (1 = no binning).",
    "basic.n_sensors": "Number of identical sensors whose images are combined. Two sensors reduce temporal "
                       "noise by about sqrt(2).",

    # ---------------------------------------------------------------- Optics
    "optics.aperture": "Specific aperture: give diameter, obscuration and truncation (exact diffraction MTF "
                       "and radiometry).\nGeneral: give only the F-number (circular, unobscured aperture assumed).",
    "optics.D_mm": "Entrance pupil diameter. Sets the diffraction MTF and the collected signal (F-number = f / D). "
                   "0 = rectangular aperture defined by width and height below.",
    "optics.D_obsc_mm": "Diameter of a central obscuration (e.g. secondary mirror of a reflective telescope). "
                        "Reduces signal and changes the diffraction MTF. 0 = none.",
    "optics.W_trunc_h_mm": "Width of an aperture truncated in horizontal direction. 0 = not truncated.",
    "optics.W_trunc_v_mm": "Height of an aperture truncated in vertical direction. 0 = not truncated.",
    "optics.F_general": "Effective F-number (focal length / aperture diameter). Determines diffraction blur and "
                        "the irradiance on the detector.",
    "optics.f_mm": "Effective focal length. Converts detector size to angles: sets IFOV, FOV and magnification, "
                   "and thus the range performance.",
    "optics.diff_focal": "Use a different focal length in vertical direction (anamorphic optics).",
    "optics.f_v_mm": "Focal length in vertical direction for anamorphic optics.",
    "optics.mtf_source": "Where the optics MTF comes from: the built-in model (diffraction + aberration), or "
                         "an MTF exported from Zemax OpticStudio for your real lens design.",
    "optics.diffraction": "Diffraction MTF weighted over the spectral band (accurate), or computed at a single "
                          "wavelength (quick estimate).",
    "optics.lambda_diff_um": "Wavelength used for the diffraction MTF when 'single wavelength' is selected.",
    "optics.aberration": "How lens aberrations reduce the MTF: none (diffraction-limited), aberration "
                         "parameter q, or a Gaussian blur spot.",
    "optics.q": "Aberration parameter q (> 1). Ratio of real blur to diffraction blur; 1 means "
                "diffraction-limited, larger values mean poorer optics.",
    "optics.blur_um": "Standard deviation of a Gaussian blur spot in the image plane that represents the "
                      "optical aberrations.",
    "optics.zemax_mtf": "Import the FFT or Huygens MTF text export from Zemax OpticStudio. It replaces the "
                        "modelled diffraction/aberration MTF.",
    "optics.zemax_mtf_unit": "Unit of the spatial frequency column in the Zemax file. cycles/mm for focal "
                             "systems, cycles/mrad for afocal systems.",
    "optics.zemax_mtf_field": "Which field point of the Zemax export to use (1 = first field, usually on-axis).",
    "optics.zemax_mtf_h": "Which Zemax curve (sagittal or tangential) is used for the horizontal direction; the "
                          "other one is used for vertical.",
    "optics.tau_mode": "Give the optics transmission as one value, or import spectral transmission vs. "
                       "wavelength from Zemax.",
    "optics.tau_opt": "Peak transmission of the optics (0..1), without obscuration losses. Scales the signal "
                      "reaching the detector.",
    "optics.zemax_tau": "Import transmission vs. wavelength exported from Zemax OpticStudio.",
    "optics.tau_filter": "Transmission (0..1) of an additional filter or window in the optical path.",

    # ---------------------------------------------------------------- Detector geometry
    "detector.shape": "Shape of the light-sensitive area of one detector element. Determines the detector "
                      "(spatial integration) MTF.",
    "detector.a_h_um": "Horizontal size of the active area of one detector. Sets the detector MTF and the "
                       "collected signal.",
    "detector.a_v_um": "Vertical size of the active area of one detector. Sets the detector MTF and the "
                       "collected signal.",
    "detector.d_um": "Diameter of the active area of a circular detector.",
    "detector.d_hole_um": "Diameter of the inactive hole in a 'loop-hole' detector (e.g. HgCdTe with via hole).",
    "detector.n_h": "Number of detector columns (horizontal pixels). Together with pitch and focal length "
                    "it sets the horizontal FOV.",
    "detector.n_v": "Number of detector rows (vertical pixels). Together with pitch and focal length it sets "
                    "the vertical FOV.",
    "detector.pitch_h_um": "Center-to-center distance of detectors horizontally. Sets the sampling frequency "
                           "(Nyquist) and the IFOV.",
    "detector.pitch_v_um": "Center-to-center distance of detectors vertically. Sets the sampling frequency "
                           "(Nyquist) and the IFOV.",
    "detector.cte_on": "Model charge transfer inefficiency of CCD-type read-out (adds an MTF loss).",
    "detector.cte_h": "Charge transfer efficiency per horizontal transfer (close to 1, e.g. 0.99999).",
    "detector.ntr_h": "Number of horizontal charge transfers to the read-out.",
    "detector.cte_v": "Charge transfer efficiency per vertical transfer (close to 1).",
    "detector.ntr_v": "Number of vertical charge transfers to the read-out.",
    "detector.xtalk_h": "Crosstalk between neighbouring pixels, given as the resulting MTF value at the "
                        "Nyquist frequency (horizontal). 0 = no crosstalk.",
    "detector.xtalk_v": "Crosstalk between neighbouring pixels, given as the resulting MTF value at the "
                        "Nyquist frequency (vertical). 0 = no crosstalk.",

    # ---------------------------------------------------------------- Detector sensitivity
    "detector.uncooled_response": "Spectral response of the uncooled detector: flat between cut-on and cut-off, "
                                  "or a preset / custom quantum-efficiency curve.",
    "detector.cuton_um": "Shortest wavelength the detector responds to. Defines the spectral band.",
    "detector.cutoff_um": "Longest wavelength the detector responds to. Defines the spectral band.",
    "detector.qe_preset": "Spectral quantum efficiency curve of the detector material (e.g. InSb, MCT). It also "
                          "defines the spectral band used for all radiometry.",
    "detector.qe_scale": "Multiplies the QE curve, to match the measured QE of your detector (1 = as preset).",
    "detector.qe_custom": "Your own QE curve: one line per point, 'wavelength[um] QE[%]'.",
    "detector.noise_mode": "How temporal noise is defined.\n"
                           "Cooled: calculated from photon/dark/read noise, or taken from a measured NETD.\n"
                           "Uncooled: NETD measured for the complete device, or for the detector alone "
                           "(then converted to the project optics).",
    "detector.netd_mK": "Noise Equivalent Temperature Difference: smallest temperature difference giving "
                        "SNR = 1. The main sensitivity figure of a thermal imager.",
    "detector.meas_F": "F-number used when the detector NETD was measured, to convert it to this project's "
                       "optics. 0 = same as the project.",
    "detector.meas_tau": "Optics transmission used during the NETD measurement. 0 = same as the project.",
    "detector.meas_TB_K": "Blackbody (scene) temperature during the NETD measurement. 0 = same as the project.",
    "detector.readout_mK": "Read-out noise floor expressed in mK. This part of the noise does not scale with "
                           "F-number when NETD is converted.",
    "detector.t_th_ms": "Thermal time constant of the microbolometer. Acts like the integration time and causes "
                        "motion blur for moving scenes.",
    "detector.tint_mode": "How the integration time is specified: directly, as a fraction of the frame time, "
                          "or from a desired well fill.",
    "detector.tint_ms": "Time the detector collects photons in each frame. Longer integration = more signal "
                        "and lower noise, until the well is full.",
    "detector.duty": "Integration time as a fraction (0..1) of the frame time.",
    "detector.wellfill_pct": "Integration time is chosen so the charge well is filled to this percentage by "
                             "the background.",
    "detector.storage_e": "Charge well capacity (max. number of carriers per pixel). Limits the integration "
                          "time and the signal.",
    "detector.electron_gain": "Internal gain of the detector (e.g. avalanche / EMCCD). 1 for normal detectors.",
    "detector.dark_A": "Dark current per pixel. Generates shot noise even without light.",
    "detector.noise_floor_e": "Additive read-out noise in electrons (rms), independent of signal.",
    "detector.noise_figure": "Excess noise factor of the gain process (1 = noiseless gain).",
    "detector.adc_mode": "Quantization noise of the A/D converter: not modelled, LSB in carriers, or LSB in mK.",
    "detector.lsb_e": "Size of one A/D converter step (least significant bit) in carriers.",
    "detector.lsb_mK": "Size of one A/D converter step (least significant bit) in mK.",
    "detector.T_off_dev_K": "Temperature of the imager housing relative to the scene background. Housing "
                            "radiation adds background photons and noise.",
    "detector.T_off_opt_K": "Temperature of the optics relative to the scene background. Emission of the optics "
                            "adds background photons and noise.",
    "detector.T_cs_K": "Temperature of the cold shield around the detector. Radiation from it adds "
                       "background (negligible when very cold).",
    "detector.cs_mode": "Define the cold shield by its efficiency or by its effective F-number.",
    "detector.cs_eff": "Cold shield efficiency: ratio of optics F-number to cold-shield F-number "
                       "(1 = perfectly matched, no stray warm radiation).",
    "detector.cs_F": "Effective F-number of the cold shield opening. Determines how much warm housing "
                     "radiation the detector sees.",
    "detector.fpn_mode": "Fixed pattern (spatial) noise left after non-uniformity correction: none, "
                         "measured, or estimated as a fraction of temporal noise.",
    "detector.ietd_mK": "Spatial noise (fixed pattern noise) of a thermal imager expressed in mK.",
    "detector.prnu_pct": "Photo-response non-uniformity: pixel-to-pixel gain variation, in % of the signal.",
    "detector.dsnu_A": "Dark signal non-uniformity: pixel-to-pixel variation of the dark current.",
    "detector.fpn_fraction": "Fixed pattern noise as a fraction of the temporal noise (NETD or NES).",

    # ---------------------------------------------------------------- Signal processing
    "dsp.filter_on": "Apply a digital (FIR) filter, e.g. sharpening or smoothing. It changes the MTF and noise.",
    "dsp.filter_dir": "Direction(s) in which the digital filter is applied.",
    "dsp.h_type": "Odd: filter with a center tap (2N+1 taps).\nEven: filter without a center tap (2N taps).",
    "dsp.h_coef": "Filter coefficients c0..c4 for the horizontal direction (c0 = center), comma separated.",
    "dsp.v_type": "Odd: filter with a center tap (2N+1 taps).\nEven: filter without a center tap (2N taps).",
    "dsp.v_coef": "Filter coefficients c0..c4 for the vertical direction (c0 = center), comma separated.",
    "dsp.zoom": "Electronic zoom factor (1 = none). Enlarges the image on the display without adding detail.",
    "dsp.zoom_type": "Interpolation used by the electronic zoom. Affects the reconstruction MTF.",
    "dsp.lrep": "Each image line is shown this many times on the display (1 = none).",
    "dsp.lrep_type": "Interpolation used for line replication.",
    "dsp.crep": "Each image column is shown this many times on the display (1 = none).",
    "dsp.crep_type": "Interpolation used for column replication.",
    "dsp.frames_on": "Average several frames to reduce temporal noise.",
    "dsp.n_frames": "Number of frames averaged. Noise drops by about sqrt(N).",
    "dsp.iir_on": "Recursive (IIR) frame averaging filter for temporal noise reduction.",
    "dsp.iir_alpha": "Weight of the new frame in the IIR filter (0..1). Smaller = stronger noise reduction "
                     "but more lag.",

    # ---------------------------------------------------------------- Display & observer
    "display.n_h": "Number of display pixels horizontally.",
    "display.n_v": "Number of display pixels vertically.",
    "display.pitch_h_mm": "Horizontal size of one display pixel. With viewing distance it sets how large the "
                          "image appears to the eye.",
    "display.pitch_v_mm": "Vertical size of one display pixel.",
    "display.luminance": "Average brightness of the display. The eye's contrast sensitivity depends on it.",
    "display.neglect_eye": "Ignore the eye MTF (assume a perfect eye), e.g. when the display is magnified "
                           "enough.",
    "display.observation": "Display viewed directly, or through an eyepiece (e.g. a viewfinder).",
    "display.distance_cm": "Distance from the observer's eye to the display. Determines the angular "
                           "magnification seen by the eye.",
    "display.f_eyepiece_mm": "Focal length of the eyepiece. Determines the angular magnification of the display.",
    "display.snr_th": "Signal-to-noise ratio the observer needs to detect a pattern (typically about 2.5-3).",
    "display.t_eye_s": "Integration time of the eye (typically 0.04-0.1 s). In video mode the eye averages the "
                       "frames in this time.",

    # ---------------------------------------------------------------- Stabilization & MTFs
    "stab.neglect": "Ignore all line-of-sight motion (perfectly stable platform).",
    "stab.random_on": "Include random vibration (jitter) of the line of sight.",
    "stab.rand_h_mrad": "RMS amplitude of the random horizontal jitter during integration. Causes blur.",
    "stab.rand_v_mrad": "RMS amplitude of the random vertical jitter during integration. Causes blur.",
    "stab.lin_on": "Include linear image motion during the integration time (smear).",
    "stab.lin_h": "Horizontal angular velocity of the image during integration.",
    "stab.lin_v": "Vertical angular velocity of the image during integration.",
    "stab.sin_on": "Include high-frequency sinusoidal vibration of the line of sight.",
    "stab.sin_h": "Amplitude of the horizontal sinusoidal vibration.",
    "stab.sin_v": "Amplitude of the vertical sinusoidal vibration.",
    "additional.type": "Extra MTF component not covered by the model (e.g. from measurement). Prefilter acts "
                       "before sampling (affects aliasing), postfilter after sampling.",
    "additional.par": "Shape parameter of the additional MTF: first zero for sinc / rectangular, standard "
                      "deviation for Gaussian, in object-space spatial frequency.",

    # ---------------------------------------------------------------- Target & scenario
    "target.preset": "Pick a standard target (size, contrast, line pairs for each task) or define your own.",
    "target.alt_m": "Height of the target above the ground. Used with the imager altitude for the slant-path "
                    "geometry.",
    "target.dT_K": "Apparent temperature difference between target and background. The thermal contrast "
                   "the imager must resolve.",
    "target.W_m": "Target width. Together with height and depth it gives the visible critical dimension.",
    "target.H_m": "Target height. Together with width and depth it gives the visible critical dimension.",
    "target.D_m": "Target depth (length). Visible depending on the viewing aspect.",
    "target.t_emis_mode": "How the target emissivity is given: blackbody (1), greybody (constant) or a "
                          "spectral material preset.",
    "target.t_emis": "Constant emissivity of the target (0..1).",
    "target.t_emis_preset": "Material whose spectral emissivity is used for the target.",
    "target.t_refl_mode": "Target reflectivity as one effective value or a spectral material curve.",
    "target.t_refl": "Effective reflectivity of the target (0..1) in the spectral band.",
    "target.t_refl_preset": "Material whose spectral reflectivity is used for the target.",
    "target.T_bg_K": "Temperature of the scene background. Sets the background radiance, detector "
                     "background flux and noise.",
    "target.b_emis_mode": "How the background emissivity is given: blackbody, greybody or spectral preset.",
    "target.b_emis": "Constant emissivity of the background (0..1).",
    "target.b_emis_preset": "Material whose spectral emissivity is used for the background.",
    "target.b_refl_mode": "Background reflectivity as one effective value or a spectral material curve.",
    "target.b_refl": "Effective reflectivity of the background (0..1). Target contrast = difference to the "
                     "target reflectivity.",
    "target.b_refl_preset": "Material whose spectral reflectivity is used for the background.",
    "target.aspect": "From which side the target is seen. Selects which dimensions form the visible area.",
    "target.flight": "Imager moves at constant altitude (look-down angle changes with range) or at a constant "
                     "observation angle.",
    "target.altitude_m": "Imager height above the target. Defines the slant range and look-down angle.",
    "target.angle_deg": "Fixed look-down angle to the target (positive = looking down).",
    "target.tasks.N.on": "Calculate the range for this task (e.g. detection, recognition, identification).",
    "target.tasks.N.name": "Name of the task, shown in plots and tables.",
    "target.tasks.N.lp": "Number of line pairs (cycles) across the target needed for this task with 50% "
                         "probability. More line pairs = harder task = shorter range.",

    # ---------------------------------------------------------------- Irradiance
    "irradiance.mode": "Whether the scene is illuminated by a source (sun, moon, lamp). Required for reflective "
                       "bands; General may use emission only.",
    "irradiance.type": "Kind of illumination source: hemispherical blackbody, broadband source, or a "
                       "monochromatic one (laser).",
    "irradiance.T_bb_K": "Temperature of the blackbody that illuminates the scene.",
    "irradiance.spectrum": "How the broadband spectrum is given: a flat effective value, a colour temperature, "
                           "or a natural source preset (sun, moon, starlight ...).",
    "irradiance.E_eff": "Scene irradiance within the spectral band (flat spectrum).",
    "irradiance.T_colour_K": "Colour temperature describing the spectral shape of the source.",
    "irradiance.preset": "Natural illumination source whose spectrum is used.",
    "irradiance.E_peak": "Spectral irradiance at the peak of the spectrum. Scales the selected spectral shape.",
    "irradiance.lambda_um": "Wavelength of the monochromatic source.",
    "irradiance.E_mono": "Scene irradiance of the monochromatic source.",
    "irradiance.geometry": "Extended (diffuse, from all directions) or a point source fixed in space (e.g. the "
                           "sun), which creates shading on the target faces.",
    "irradiance.beta_h_deg": "Horizontal angle between the source direction and the target front.",
    "irradiance.beta_v_deg": "Vertical angle between the source direction and the target front.",

    # ---------------------------------------------------------------- Atmosphere & turbulence
    "atmosphere.mode": "Define atmospheric loss by an extinction coefficient (Beer's law), or by the "
                       "meteorological visual range (Visible only).",
    "atmosphere.atm.N.on": "Calculate ranges for this atmosphere (up to three weather conditions are compared).",
    "atmosphere.atm.N.sigma": "Extinction coefficient: transmission = tau0 * exp(-sigma * range). Larger value "
                              "= worse weather, shorter range.",
    "atmosphere.atm.N.V_km": "Meteorological visual range; converted to an extinction coefficient.",
    "atmosphere.atm.N.tau0": "Transmission at zero range (losses that do not depend on range, e.g. "
                             "absorption lines). Usually 1.",
    "atmosphere.atm.N.T_air_K": "Air temperature along the path. The atmosphere emits path radiance at this "
                                "temperature.",
    "atmosphere.atm.N.F_PR": "Factor for scattered light (path radiance) added along the line of sight. It "
                             "reduces target contrast.",
    "turbulence.on": "Include the blur caused by air turbulence (important for long horizontal paths).",
    "turbulence.exposure": "Short exposure: image motion removed (only blur).\nLong exposure: includes image "
                           "wander (stronger blur).",
    "turbulence.cn2_mode": "Turbulence strength Cn2 constant along the path, or varying with height.",
    "turbulence.cn2": "Refractive index structure constant: strength of turbulence (e.g. 1e-15 weak, 1e-13 "
                      "strong).",
    "turbulence.h_ref_m": "Height above ground where the Cn2 value is given.",
    "turbulence.time": "Day or night height profile of turbulence (stronger near the ground in daytime).",
}

_ADDITIONAL = re.compile(r"additional\.(pre|post)_[hv]_(type|par)$")


def help_for(path):
    """Help text for a parameter path, or '' if none is defined."""
    m = _ADDITIONAL.match(path)
    if m:
        return HELP["additional." + m.group(2)]
    return HELP.get(re.sub(r"\.\d+\.", ".N.", path), "")
