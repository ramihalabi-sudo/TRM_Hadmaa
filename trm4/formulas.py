"""How every input field enters the range calculation: the stage of the calculation chain and the formula.

Shown to the user in three places: after the help text of the '?' of a field (English), in the field card of the
guide (the stage in Hebrew, the formula as written here) and in Help > How the range is calculated.  The formulas are
the ones the engine evaluates (trm4/model.py, mtf.py, extensions.py); equation numbers refer to the TRM4.v3
documentation.  Symbols: p pixel pitch, a active pixel size, f focal length, D aperture, F = f / D, lambda
wavelength, r spatial frequency [cycles/mrad], R range [km], tau transmission, N carriers, NETD noise equivalent
temperature difference, AMOP average modulation at optimum phase, MTDP / MDSP minimum temperature difference / signal
perceived.
"""
import re

# key -> (English title, Hebrew title, English text, Hebrew text), in the order of the calculation
STAGES = {
    "scenario": ("Scenario", "בחירת התרחיש",
                 "Selects which branch of the model runs; it has no formula of its own.",
                 "בוחר איזה ענף של המודל רץ. אין לו נוסחה משלו."),
    "geometry": ("Step 1 - geometry and sampling", "שלב 1 - גאומטריה ודגימה",
                 "IFOV = p / f,  FOV = [(n - 1) p + a] / f,  Nyquist frequency r_N = f / (2 p).",
                 "קובע מה כל פיקסל רואה: זווית הפיקסל, שדה הראייה ותדר נייקוויסט."),
    "signal": ("Step 2 - signal on the detector", "שלב 2 - האות על הגלאי",
               "Carriers N = (pi / 4F^2) x Int L(lambda) tau_atm tau_opt QE dlambda x A_det x t_int (Eq. 3.110).",
               "קובע כמה אלקטרונים המטרה והרקע יוצרים בפיקסל."),
    "noise": ("Step 3 - noise", "שלב 3 - רעש",
              "sigma^2 = [NF^2 (j_T + j_B) / 2 + j_dark] A g^2 t_int + n_reads (read^2 + LSB^2 / 12) (Eq. 3.130); "
              "NETD = sigma / (dN/dT).",
              "קובע את הרעש שמתחרה באות: רעש ירייה, חושך, קריאה, קוונטיזציה ורעש קבוע."),
    "mtf_pre": ("Step 4 - sharpness before sampling", "שלב 4 - חדות לפני הדגימה",
                "MTF_pre = MTF_optics x MTF_detector x MTF_motion x MTF_turbulence; it enters AMOP.",
                "קובע כמה ניגוד נשאר בכל תדר מרחבי לפני שהגלאי דוגם את התמונה."),
    "mtf_post": ("Step 5 - processing, display and eye", "שלב 5 - עיבוד, תצוגה ועין",
                 "MTF_post = MTF_filter x MTF_zoom x MTF_display x MTF_eye; it filters signal and noise alike.",
                 "קובע מה קורה לתמונה אחרי הדגימה, עד שהיא מגיעה לעין הצופה."),
    "threshold": ("Step 6 - system threshold", "שלב 6 - סף המערכת",
                  "MTDP(r) = (pi / 2) SNR_th sqrt(Psi(r)) / AMOP(r),  Psi = NETD^2 / N_int x E_h E_v + Psi_FPN "
                  "(Eq. 3.175).",
                  "קובע את האות הקטן ביותר שהצופה מבחין בו בכל תדר מרחבי."),
    "atmosphere": ("Step 7a - the signal at the range", "שלב 7א - האות בטווח",
                   "Signal(R) = signal x tau_atm(R),  tau_atm = tau0 exp(-sigma R) (Eq. 2.29).",
                   "קובע כמה מהאות מגיע מהמטרה אל המצלמה דרך האוויר."),
    "criterion": ("Step 7b - the range", "שלב 7ב - הטווח",
                  "Range: the largest R with Signal(R) >= MTDP(r) at r = N_task R / sqrt(W H) (Eqs. 3.210-3.215).",
                  "קובע איזה תדר מרחבי המשימה דורשת, ולכן באיזה טווח האות עוד עובר את הסף."),
    "output": ("Extra output", "פלט נוסף",
               "Adds a result next to the TRM4 ranges; the TRM4 ranges are not changed.",
               "מוסיף תוצאה לצד טווחי TRM4. הטווחים עצמם לא משתנים."),
    "check": ("Check / diagnostic", "בדיקה או אבחון",
              "Used for a consistency check, a warning or a diagnostic; it does not enter the range.",
              "משמש לבדיקת עקביות, לאזהרה או לאבחון. לא נכנס לחישוב הטווח."),
    "doc": ("Documentation", "תיעוד",
            "Traceability only: it is written to the report and does not enter the calculation.",
            "לעקיבות בלבד: נכתב לדוח ולא נכנס לחישוב."),
}

_N = "noise"
_S = "signal"
_G = "geometry"
_P = "mtf_pre"
_Q = "mtf_post"
_A = "atmosphere"
_C = "criterion"

FIELD = {
    # ---------------------------------------------------------------- scenario
    "category": ("scenario", "Thermal: signal = dT x tau_atm in kelvin. Visible / General: signal in carriers from the "
                             "reflected (and, in General, emitted) radiance."),
    "imager_type": ("scenario", "Cooled: noise from the detector physics (or a measured NETD). Uncooled: a measured "
                                "NETD and a thermal time constant."),
    "mode.environment": ("scenario", "Field: ranges through the atmosphere. Laboratory: MTDP / MDSP at zero range."),
    "mode.stream": (_N, "Video: N_int = frame rate x t_eye frames are integrated by the eye. Still: only the frames "
                        "the processing integrates."),
    "mode.ref_range_km": (_S, "The spectral weights w(lambda) of the diffraction MTF and the reference signal are "
                              "evaluated with tau_atm(lambda, R_ref)."),
    "mode.niirs": ("output", "NIIRS = GIQE 5 (GSD, RER, SNR)."),
    "name": ("doc", ""),
    # ---------------------------------------------------------------- optics
    "optics.f_mm": (_G, "IFOV = p / f;  Nyquist r_N = f / (2 p);  FOV = [(n - 1) p + a] / f;  F = f / D."),
    "optics.f_v_mm": (_G, "Vertical focal length of an anamorphic lens: IFOV_v = p_v / f_v."),
    "optics.diff_focal": (_G, "Allows a different vertical focal length."),
    "optics.aperture": (_P, "Shape of the pupil; the diffraction MTF is the overlap area of the pupil with itself "
                            "displaced by lambda r (App. B)."),
    "optics.D_mm": (_P, "Diffraction cut-off r_c = D / lambda;  MTF_diff(r) = (2/pi)[acos(x) - x sqrt(1 - x^2)], "
                        "x = lambda r / D.  Signal ~ 1 / F^2 = D^2 / f^2."),
    "optics.F_general": (_S, "F-number of a general aperture: irradiance ~ pi / (4 F^2); D = f / F for the cut-off."),
    "optics.D_obsc_mm": (_P, "Pupil with a central hole: collecting area x (1 - (D_obsc / D)^2); the overlap integral "
                             "lowers the mid frequencies."),
    "optics.W_trunc_h_mm": (_P, "Pupil cut to this width: the horizontal overlap integral and the area change."),
    "optics.W_trunc_v_mm": (_P, "Pupil cut to this width: the vertical overlap integral and the area change."),
    "optics.F_spec": ("check", "Compared with the calculated F = f / D_eff; a difference above 5 % is warned."),
    "optics.mtf_source": (_P, "Computed: diffraction x aberration. Imported: the file replaces them (never both)."),
    "optics.zemax_mtf": (_P, "MTF_optics(r) = the imported curve, interpolated."),
    "optics.zemax_mtf_unit": (_P, "cycles/mm -> cycles/mrad: r = nu x f / 1000."),
    "optics.zemax_mtf_field": (_P, "Selects the field point of the imported MTF file."),
    "optics.zemax_mtf_h": (_P, "Sagittal or tangential curve used for the horizontal direction."),
    "optics.mtf_incl_diffraction": (_P, "If the import excludes diffraction: MTF_optics = import x MTF_diff."),
    "optics.mtf_incl_detector": (_P, "If the import includes the detector: MTF_detector is set to 1."),
    "optics.mtf_incl_motion": (_P, "If the import includes motion: MTF_motion is set to 1."),
    "optics.diffraction": (_P, "Spectral: MTF_diff(r) = Int w(lambda) MTF_diff(r, lambda) dlambda. Single: at one "
                               "wavelength."),
    "optics.lambda_diff_um": (_P, "x = lambda r / D in the diffraction MTF (0 = signal-weighted mean wavelength)."),
    "optics.aberration": (_P, "None: MTF_diff. q: MTF_diff^q (Eq. 4.11). Blur: MTF_diff x Gaussian (Eq. 4.14)."),
    "optics.q": (_P, "MTF_optics = MTF_diff^q."),
    "optics.blur_um": (_P, "MTF_optics = MTF_diff x exp[-2 (pi sigma r / f)^2], sigma in um, f in mm."),
    "optics.defocus_um": (_P, "OTF(r) = Int_overlap cos(2 pi dz r u / f^2) du dy / pupil area; depth of focus "
                              "+-2 lambda F^2; blur disc dz / (F f)."),
    "optics.tau_mode": (_S, "Constant transmission or an imported tau_opt(lambda)."),
    "optics.tau_opt": (_S, "N ~ tau_opt.  Thermal: the optics also emit (1 - tau_opt) L_BB(T_optics) (Eq. 3.104)."),
    "optics.zemax_tau": (_S, "tau_opt(lambda) from the file, inside the spectral integral."),
    "optics.tau_kind": (_S, "Absolute: used as is. Normalized: scaled by tau_opt."),
    "optics.tau_scope": (_S, "Whether the imported curve already contains the filter."),
    "optics.tau_filter": (_S, "N ~ tau_filter (multiplies tau_opt)."),
    "optics.rel_illum": ("check", "Signal at the field edge = centre x relative illumination; the ranges are for "
                                  "the centre."),
    # ---------------------------------------------------------------- basic imager
    "basic.frame_rate": (_N, "t_int <= 1 / frame rate;  N_int = frame rate x t_eye (Eq. 3.181);  perceived noise "
                             "~ 1 / sqrt(N_int)."),
    "basic.fov_mode": ("check", "Calculated FOV = [(n - 1) p + a] / f, or an entered FOV for a cross-check."),
    "basic.fov_h_deg": ("check", "Compared with [(n_h - 1) p_h + a_h] / f."),
    "basic.fov_v_deg": ("check", "Compared with [(n_v - 1) p_v + a_v] / f."),
    "basic.microscan": (_G, "Sampling distance = p / (steps f): the Nyquist frequency rises by the number of steps."),
    "basic.ms_steps_h": (_G, "alpha_s,h = p_h / (steps_h f)."),
    "basic.ms_steps_v": (_G, "alpha_s,v = p_v / (steps_v f)."),
    "basic.integ_during_move": (_P, "Adds the smear MTF of integrating while the micro-scan moves (Eqs. 4.36-4.39)."),
    "basic.bin_h": (_G, "Pitch x n;  MTF x sin(n pi p r / f) / [n sin(pi p r / f)] (Eq. 4.26);  signal x n."),
    "basic.bin_v": (_G, "Pitch x n;  MTF x sin(n pi p r / f) / [n sin(pi p r / f)];  signal x n."),
    "basic.bin_kind": (_N, "Charge binning: read noise once. Digital: read noise of every summed pixel."),
    "basic.n_sensors": (_N, "N_int x number of sensors."),
    "basic.readout": ("check", "Rolling shutter: geometric skew = image velocity x readout time (warning)."),
    "basic.exp_overlap": (_N, "Largest integration time = 1 / frame rate, or minus the readout time."),
    "basic.readout_ms": (_N, "t_int <= 1 / frame rate - readout time when the exposure does not overlap readout."),
    "basic.guard_ms": (_N, "t_int <= frame interval - readout - guard time."),
    "basic.exp_min_ms": (_N, "Lower limit of the integration time in well-fill mode."),
    "basic.exp_max_ms": (_N, "Upper limit of the integration time in well-fill mode."),
    "basic.interlace": (_G, "Pseudo interlace: vertical MTF x cos(pi p_v r / f) (Eq. 4.27)."),
    "basic.roi": ("doc", ""),
    # ---------------------------------------------------------------- detector geometry
    "detector.n_h": (_G, "FOV_h = [(n_h - 1) p_h + a_h] / f (Eq. 3.11). It does not enter the range."),
    "detector.n_v": (_G, "FOV_v = [(n_v - 1) p_v + a_v] / f (Eq. 3.11). It does not enter the range."),
    "detector.square": (_G, "The vertical pitch and active size follow the horizontal ones."),
    "detector.pitch_h_um": (_G, "IFOV_h = p_h / f;  Nyquist r_N = f / (2 p_h)."),
    "detector.pitch_v_um": (_G, "IFOV_v = p_v / f;  Nyquist r_N = f / (2 p_v)."),
    "detector.a_h_um": (_P, "MTF_detector = sinc(a_h r / f) (Eq. 4.21);  A_det = a_h a_v collects the signal."),
    "detector.a_v_um": (_P, "MTF_detector = sinc(a_v r / f);  A_det = a_h a_v collects the signal."),
    "detector.shape": (_P, "Rectangular: sinc. Rhombic: sinc^2. Circular: 2 J1(x) / x (Eqs. 4.21-4.24)."),
    "detector.d_um": (_P, "Circular detector: MTF = 2 J1(pi d r / f) / (pi d r / f)."),
    "detector.d_hole_um": (_P, "Loop-hole detector: ring between d_hole and d."),
    "detector.cte_on": (_P, "CCD: MTF x exp[-n (1 - CTE)(1 - cos(2 pi r / r_s))] (Eq. 4.28)."),
    "detector.cte_h": (_P, "MTF_CTE = exp[-n_tr (1 - CTE)(1 - cos(2 pi r / r_s))]."),
    "detector.ntr_h": (_P, "Number of transfers n_tr in MTF_CTE."),
    "detector.cte_v": (_P, "MTF_CTE = exp[-n_tr (1 - CTE)(1 - cos(2 pi r / r_s))]."),
    "detector.ntr_v": (_P, "Number of transfers n_tr in MTF_CTE."),
    "detector.xtalk_h": (_P, "MTF_crosstalk = 1 / [1 + (2 pi D_diff r)^2], D_diff from the specified MTF at Nyquist "
                             "(Eqs. 4.29, 4.30)."),
    "detector.xtalk_v": (_P, "MTF_crosstalk = 1 / [1 + (2 pi D_diff r)^2], D_diff from the specified MTF at Nyquist."),
    # ---------------------------------------------------------------- detector spectral response
    "detector.uncooled_response": (_S, "Flat response between cut-on and cut-off, or a custom curve."),
    "detector.cuton_um": (_S, "Lower limit of the spectral integral."),
    "detector.cutoff_um": (_S, "Upper limit of the spectral integral."),
    "detector.qe_preset": (_S, "QE(lambda) inside N = Int L tau QE dlambda; it also sets the band."),
    "detector.qe_scale": (_S, "QE(lambda) x scale."),
    "detector.qe_custom": (_S, "QE(lambda) from the table."),
    "detector.qe_unit": (_S, "Percent or fraction of the QE table."),
    "detector.qe_basis": ("check", "QE per active area (fill factor applied to the signal) or per pixel area."),
    # ---------------------------------------------------------------- detector noise
    "detector.noise_mode": (_N, "Physics model: sigma from the noise equation. Measured NETD: replaces it; "
                                "converted: NETD x (F / F_test)^2."),
    "detector.netd_mK": (_N, "Psi = NETD^2 / N_int x E_h E_v;  MTDP ~ NETD."),
    "detector.netd_TB_K": ("check", "Compared with the background temperature (warning above 10 K difference)."),
    "detector.t_th_ms": (_P, "Uncooled: response MTF = 1 / sqrt[1 + (2 pi nu t_th)^2], nu = image velocity x r "
                             "(Eq. 4.17)."),
    "detector.noise_floor_e": (_N, "sigma^2 += n_reads x read noise^2."),
    "detector.netd_F": (_N, "Converted mode: NETD x (F / F_test)^2. Otherwise a check (warning above 5 %)."),
    "detector.netd_tint_ms": ("check", "Compared with the integration time of the scenario."),
    "detector.netd_frames": ("check", "A NETD averaged over frames counts the frame integration twice (warning)."),
    "detector.noise_port": ("check", "Where the NETD was measured (RAW / after NUC / processed video)."),
    "detector.meas_F": (_N, "NETD = NETD_meas x (F / F_meas)^2 x Int(tau_meas R dL/dT) / Int(tau R dL/dT) "
                            "(Eq. 3.142)."),
    "detector.meas_tau": (_N, "Transmission of the test lens in Eq. (3.142)."),
    "detector.meas_TB_K": (_N, "Blackbody temperature of the NETD test in Eq. (3.142)."),
    "detector.readout_mK": (_N, "NETD = sqrt(NETD_scaled^2 + readout^2)."),
    "detector.tint_mode": (_N, "Direct t_int, a duty cycle of the frame time, or the time that fills the well."),
    "detector.tint_ms": (_N, "Signal ~ t_int; shot noise ~ sqrt(t_int)."),
    "detector.duty": (_N, "t_int = duty / frame rate."),
    "detector.wellfill_pct": (_N, "t_int = fill x N_well / [(j_B + j_dark) A g] (Eq. 3.76)."),
    "detector.storage_e": (_N, "N_well in t_int = fill x N_well / [(j_B + j_dark) A g]; background-limited "
                               "NETD ~ 1 / sqrt(fill x N_well)."),
    "detector.cap_node": ("check", "Which node the capacity refers to (pixel / ROIC / camera)."),
    "detector.sat_e": (_N, "Usable capacity: the smaller of the storage and the saturation capacity."),
    "detector.fill_limit_pct": ("check", "Exposure budget: allowed well fill of the brightest pixel."),
    "detector.bright_refl": ("check", "Exposure budget: reflectivity of the brightest scene element."),
    "detector.bright_dT_K": ("check", "Exposure budget: temperature of the hottest scene element."),
    "detector.snr_req": ("check", "Exposure budget: required SNR."),
    "detector.electron_gain": (_N, "Carriers x g; shot-noise variance x g^2 (APD / EMCCD)."),
    "detector.dark_mode": (_N, "j_dark from one value, a table over temperature, or Rule 07."),
    "detector.dark_A": (_N, "j_dark = I_dark / (q A_det); sigma^2 += j_dark A g^2 t_int; it also fills the well."),
    "detector.dark_table": (_N, "I_dark(T_sensor), log-linear interpolation."),
    "detector.T_sensor_K": (_N, "Table: I_dark(T). Rule 07: J = 8367 exp[-1.1624 x 1.24 q / (k lambda_c T)] A/cm^2."),
    "detector.noise_figure": (_N, "Shot-noise variance x NF^2."),
    "detector.adc_mode": (_N, "Quantization noise from an LSB in carriers or in mK."),
    "detector.lsb_e": (_N, "sigma^2 += n_reads x LSB^2 / 12 (Eq. 2.12)."),
    "detector.lsb_mK": (_N, "Quantization noise = LSB [K] x dN/dT / sqrt(12)."),
    "detector.adc_bits": ("check", "ADC clipping check: full scale = 2^bits x LSB."),
    "detector.T_off_dev_K": (_N, "Warm device surfaces add background (1 - eta_cs) / eta_cs x L_BB(T) (Eq. 3.105)."),
    "detector.T_off_opt_K": (_N, "Optics emit (1 - tau_opt) L_BB(T_optics) onto the detector (Eq. 3.104)."),
    "detector.T_cs_K": (_N, "The cold shield emits L_BB(T_cs) outside the lens cone (Eq. 3.106)."),
    "detector.cs_mode": (_N, "Cold shield efficiency given directly or from its F-number."),
    "detector.cs_eff": (_N, "eta_cs: fraction of the background that comes through the lens."),
    "detector.cs_F": (_N, "eta_cs = (4 F_cs^2 + 1) / (4 F^2 + 1) (Eq. 2.10)."),
    "detector.nps_file": ("check", "Measured noise power spectrum: checks the white-noise assumption."),
    "detector.nps_unit": ("check", "Frequency unit of the noise power spectrum."),
    "detector.nps_stage": ("check", "Where the noise power spectrum was measured."),
    "detector.fpn_mode": (_N, "Fixed pattern noise: none, an estimate (fraction of NETD) or measured."),
    "detector.ietd_mK": (_N, "Psi_FPN = IETD^2 x eye integrals - not divided by N_int (Eq. 3.184)."),
    "detector.prnu_pct": (_N, "FPN carriers = PRNU x background carriers (Eq. 3.166)."),
    "detector.dsnu_A": (_N, "FPN carriers = DSNU x t_int / q (Eq. 3.167)."),
    "detector.fpn_fraction": (_N, "IETD = fraction x NETD."),
    "detector.op_mode": ("doc", ""),
    "detector.netd_nuc": ("doc", ""),
    # ---------------------------------------------------------------- signal processing
    "dsp.frames_on": (_N, "Switches frame integration on."),
    "dsp.n_frames": (_N, "Temporal noise / sqrt(n); with motion a smear MTF is added."),
    "dsp.iir_on": (_N, "Switches recursive frame integration on."),
    "dsp.iir_alpha": (_N, "Equivalent frames = n (1 + alpha) / (1 - alpha) (Eq. 3.141); smear MTF (Eq. 4.72)."),
    "dsp.filter_on": (_Q, "Switches the digital filter on."),
    "dsp.filter_dir": (_Q, "Direction the filter acts in."),
    "dsp.h_type": (_Q, "Odd or even symmetric filter."),
    "dsp.h_coef": (_Q, "H(r) = sum c_n cos(2 pi n alpha_s r) / sum c_n (Eq. 4.46)."),
    "dsp.v_type": (_Q, "Odd or even symmetric filter."),
    "dsp.v_coef": (_Q, "H(r) = sum c_n cos(2 pi n alpha_s r) / sum c_n."),
    "dsp.credit_boost": (_Q, "Whether a filter gain above 1 (sharpening) is credited in the ranges."),
    "dsp.zoom": (_Q, "System magnification x zoom; replication MTF = sinc (Eqs. 4.52-4.56)."),
    "dsp.zoom_type": (_Q, "Pixel replication: sinc. Linear interpolation: sinc^2."),
    "dsp.lrep": (_Q, "Line replication: vertical magnification x n, MTF = sinc."),
    "dsp.lrep_type": (_Q, "Replication: sinc. Interpolation: sinc^2."),
    "dsp.crep": (_Q, "Column replication: horizontal magnification x n, MTF = sinc."),
    "dsp.crep_type": (_Q, "Replication: sinc. Interpolation: sinc^2."),
    "dsp.pl_compression": (_Q, "Lossy compression switches the equivalent blur on."),
    "dsp.comp_blur_px": (_Q, "MTF x exp[-2 pi^2 (sigma_px alpha_s)^2 r^2]."),
    "dsp.tone_mode": (_N, "Signal and noise pass the same slope; the output rounding adds noise."),
    "dsp.tone_bits": (_N, "Rounding noise = 1 / (sqrt(12) x slope), slope ~ 2^bits / input range."),
    "dsp.tone_gamma": (_N, "Slope of the gamma curve at the signal level."),
    "dsp.tone_k": (_N, "Slope of the logarithmic curve at the signal level."),
    "dsp.tone_span_K": (_N, "Thermal: temperature span mapped onto the output range."),
    "dsp.pl_denoise": ("doc", ""),
    "dsp.pl_order": ("doc", ""),
    "dsp.pl_version": ("doc", ""),
    # ---------------------------------------------------------------- display and observer
    "display.observer": ("threshold", "Human: display and eye MTF, eye integration. Algorithm: none of them."),
    "display.algo_calib": ("doc", ""),
    "display.algo_criterion": (_C, "Line pairs, or pixels on target with a pixel CNR."),
    "display.algo_cnr_min": (_C, "Pixels-on-target criterion: range where CNR >= this value."),
    "display.algo_id": ("doc", ""),
    "display.algo_roc": ("doc", ""),
    "display.observation": (_Q, "Direct view: distance to the display. Eyepiece: its focal length."),
    "display.distance_cm": (_Q, "M_sys = n_v p_disp / (FOV_v d);  MTF_eye = exp(-Gamma r / M_sys) (Eq. 4.79)."),
    "display.f_eyepiece_mm": (_Q, "M_sys = n_v p_disp / (FOV_v f_eyepiece)."),
    "display.n_h": ("check", "Compared with the number of image samples."),
    "display.n_v": ("check", "Compared with the number of image samples."),
    "display.pitch_h_mm": (_Q, "Display MTF = sinc(r / (r_s zoom)); geometric distortion check."),
    "display.pitch_v_mm": (_Q, "M_sys = n_v p_disp / (FOV_v d): a larger element gives a larger image."),
    "display.luminance": (_Q, "Gamma(L) of the eye, Table 4.2: 2.28 at 0.01 fL to 0.81 at 1000 fL; "
                              "MTF_eye = exp(-Gamma r / M_sys)."),
    "display.ambient_lux": ("check", "L_refl = reflectance x E / pi; displayed contrast x L / (L + L_refl)."),
    "display.reflectance": ("check", "L_refl = reflectance x E / pi."),
    "display.snr_th": ("threshold", "MTDP = (pi / 2) SNR_th sqrt(Psi) / AMOP."),
    "display.t_eye_s": (_N, "N_int = frame rate x t_eye; perceived noise ~ 1 / sqrt(N_int)."),
    "display.neglect_eye": (_Q, "MTF_eye = 1."),
    # ---------------------------------------------------------------- stabilization
    "stab.jitter_mode": (_P, "Motion from the vibration models, a measured time series or a PSD."),
    "stab.psd_file": (_P, "sigma^2 = Int PSD(f) [1 - sinc^2(f t_int)] df; MTF = exp(-2 pi^2 sigma^2 r^2)."),
    "stab.psd_unit": (_P, "Converts the PSD to mrad^2 / Hz."),
    "stab.eis": (_P, "Frame-to-frame jitter MTF exp(-2 pi^2 sigma_f^2 r^2) set to 1; the blur within the exposure "
                     "stays."),
    "stab.residual_los": ("check", "Whether the data are the residual line of sight or the platform motion."),
    "stab.jitter_file": (_P, "Blur within the exposure and frame-to-frame jitter from the measured angles."),
    "stab.jitter_unit": (_P, "Converts the measured angles to mrad."),
    "stab.jitter_rate_hz": (_P, "Sampling rate of the measured angles."),
    "stab.jitter_preset": (_P, "Fills the random vibration amplitude."),
    "stab.random_on": (_P, "Switches the random vibration on."),
    "stab.rand_h_mrad": (_P, "MTF = exp(-2 pi^2 sigma^2 r^2); at Nyquist exp[-4.93 (sigma / IFOV)^2]."),
    "stab.rand_v_mrad": (_P, "MTF = exp(-2 pi^2 sigma^2 r^2); at Nyquist exp[-4.93 (sigma / IFOV)^2]."),
    "stab.lin_on": (_P, "Switches the linear motion on."),
    "stab.lin_h": (_P, "MTF = sinc(omega t_int r); first zero at r = 1 / (omega t_int)."),
    "stab.lin_v": (_P, "MTF = sinc(omega t_int r); first zero at r = 1 / (omega t_int)."),
    "stab.smear_allow_px": ("check", "Exposure budget: t_int <= smear x IFOV / omega."),
    "stab.sin_on": (_P, "Switches the sinusoidal vibration on."),
    "stab.sin_h": (_P, "MTF = J0(2 pi A r); first zero at A r = 0.38."),
    "stab.sin_v": (_P, "MTF = J0(2 pi A r); first zero at A r = 0.38."),
    "stab.neglect": (_P, "MTF_motion = 1."),
    "additional.type": ("mtf_pre", "Extra MTF: sinc(r / r0), sinc^2(r / r0), exp[-r^2 / (2 r0^2)] or a cut at r0 - "
                                   "pre: before sampling, post: after it."),
    "additional.par": ("mtf_pre", "The frequency r0 of the extra MTF."),
    # ---------------------------------------------------------------- target and tasks
    "target.preset": (_C, "Fills the target size, temperature difference and task criteria."),
    "target.W_m": (_C, "Critical dimension sqrt(W H): required frequency r = N_task R / sqrt(W H), so R ~ sqrt(W H)."),
    "target.H_m": (_C, "Critical dimension sqrt(W H): required frequency r = N_task R / sqrt(W H), so R ~ sqrt(W H)."),
    "target.D_m": (_C, "Projected area of the side / diagonal aspect and of the look-down view (Eqs. 3.81-3.84)."),
    "target.aspect": (_C, "Which faces of the target are seen: front W x H, side D x H, diagonal both."),
    "target.dT_K": (_A, "Thermal signal = dT x tau_atm(R)."),
    "target.T_bg_K": (_N, "Background flux L_BB(T_bg): sets t_int in well-fill mode and dN/dT, hence the NETD."),
    "target.t_refl_mode": (_S, "Effective value or a spectral preset of the target reflectivity."),
    "target.t_refl": (_S, "dN ~ Int E (rho_T - rho_B) tau QE dlambda (Eq. 3.111)."),
    "target.t_refl_preset": (_S, "rho_T(lambda) of the material."),
    "target.b_refl_mode": (_S, "Effective value or a spectral preset of the background reflectivity."),
    "target.b_refl": (_S, "dN ~ Int E (rho_T - rho_B) tau QE dlambda; the background also sets the shot noise."),
    "target.b_refl_preset": (_S, "rho_B(lambda) of the material."),
    "target.t_emis_mode": (_S, "Blackbody, an effective value or a spectral preset."),
    "target.t_emis": (_S, "L_T = eps_T L_BB(T_T) (General category)."),
    "target.t_emis_preset": (_S, "eps_T(lambda) of the material."),
    "target.b_emis_mode": (_S, "Blackbody, an effective value or a spectral preset."),
    "target.b_emis": (_S, "L_B = eps_B L_BB(T_bg) (General category)."),
    "target.b_emis_preset": (_S, "eps_B(lambda) of the material."),
    "target.alt_m": (_P, "Height of the turbulence path: Cn2(h) = Cn2(h_ref)(h / h_ref)^(-4/3); horizon "
                         "3.86 (sqrt(h_imager) + sqrt(h_target)) km."),
    "target.flight": (_C, "Constant altitude: look-down angle = asin(h / R). Constant angle: as entered."),
    "target.altitude_m": (_C, "Look-down angle = asin(h / R): projected target area, path height, shortest range."),
    "target.angle_deg": (_C, "Fixed look-down angle: projected target area and path height."),
    "target.task_preset": (_C, "Fills the line pairs of the tasks."),
    "target.tasks.N.on": (_C, "Whether a range is calculated for this task."),
    "target.tasks.N.name": ("doc", ""),
    "target.tasks.N.lp": (_C, "N_task: range where r_s(R) sqrt(W H) / R = N_task, so R ~ 1 / N_task when the "
                              "resolution limits."),
    "target.tasks.N.pot": (_C, "Pixels on target: R = sqrt(W H / POT) / IFOV, if the pixel CNR suffices."),
    "target.tasks.N.v50": ("output", "TTP: range where V(R) = V50, V = TTP x sqrt(W H) / R."),
    "target.prob_levels": ("output", "N80 = 1.45 N50, N90 = 1.75 N50 (Johnson TTPF)."),
    "target.ttp": ("output", "TTP = Int sqrt(signal / threshold) dr."),
    "target.geo_limit": ("output", "R_geo = sqrt(W H) / (N_task x max(2 IFOV, lambda / D))."),
    "target.point": ("output", "SNR = signal x (target solid angle / pixel solid angle) x pixel energy / noise."),
    "target.point_snr": ("output", "Point target: range where the single-pixel SNR equals this value."),
    "target.clutter": (_C, "With the clutter model: N_detection x C [(C / dT)^2 + 1] / [(1 / dT)^2 + 1]."),
    "target.clutter_model": (_C, "Switches the clutter factor of the Detection criterion on."),
    "target.scene_id": ("doc", ""),
    # ---------------------------------------------------------------- irradiance
    "irradiance.mode": (_S, "No source, one source or the scene illumination geometry."),
    "irradiance.type": (_S, "Broadband, monochromatic (laser) or blackbody source."),
    "irradiance.spectrum": (_S, "Shape of E(lambda): colour temperature or a preset."),
    "irradiance.preset": (_S, "E(lambda) of the sun, moon or starlight: peak 1239 (sun) to 7e-4 (stars)."),
    "irradiance.E_peak": (_S, "Scales E(lambda): N ~ E."),
    "irradiance.T_bb_K": (_S, "E(lambda) ~ Planck(T)."),
    "irradiance.E_eff": (_S, "Effective irradiance in the band: N ~ E."),
    "irradiance.T_colour_K": (_S, "E(lambda) ~ Planck(T_colour)."),
    "irradiance.lambda_um": (_S, "Wavelength of a monochromatic source."),
    "irradiance.E_mono": (_S, "Irradiance of the monochromatic source: N ~ E."),
    "irradiance.geometry": (_S, "How the irradiance reaches target and background faces (Eqs. 3.92-3.99)."),
    "irradiance.beta_h_deg": (_S, "Azimuth of the source: irradiation factors of the target faces."),
    "irradiance.beta_v_deg": (_S, "Elevation of the source: irradiation factors of the faces."),
    # ---------------------------------------------------------------- atmosphere
    "atmosphere.preset": (_A, "Fills the extinction coefficients for the band."),
    "atmosphere.mode": (_A, "Extinction: tau0 exp(-sigma R). Visual range: sigma = 3.912 / V. Weather: aerosol + "
                            "water vapour. Spectral: imported tau(lambda, R)."),
    "atmosphere.atm.N.on": ("scenario", "Whether ranges are calculated for this atmosphere."),
    "atmosphere.atm.N.sigma": (_A, "tau_atm = tau0 exp(-sigma R)."),
    "atmosphere.atm.N.V_km": (_A, "sigma = 3.912 / V at 0.55 um; weather mode: (3.912 / V)(lambda / 0.55)^-q."),
    "atmosphere.atm.N.rh_pct": (_A, "Water-vapour continuum 8-14 um ~ absolute humidity (weather mode)."),
    "atmosphere.atm.N.tau0": (_A, "tau_atm = tau0 exp(-sigma R)."),
    "atmosphere.atm.N.T_air_K": (_S, "Path radiance L_BB(T_air)(1 - tau_atm) (Eq. 3.107); humidity in weather mode."),
    "atmosphere.atm.N.F_PR": (_S, "Path radiance E F_PR (1 - tau_atm) / pi (Eq. 3.108): background without signal."),
    "atmosphere.spec_file": (_A, "tau_atm(lambda, R) from the file, inside the spectral integral."),
    "atmosphere.spec_L_km": (_A, "One column: tau(lambda, R) = tau(lambda, L)^(R / L)."),
    "atmosphere.scale_height_km": (_A, "sigma x mean of exp(-h / H) along the line of sight: "
                                       "(H / dh)(1 - exp(-dh / H)) from the ground."),
    "atmosphere.rain_mmh": (_A, "sigma += 1.2924 R^0.6436 / 4.343 per km, the same in every band."),
    "atmosphere.extra_sigma": (_A, "sigma += this value, in every atmosphere."),
    "atmosphere.path_mode": (_S, "Path radiance from the model or from a file."),
    "atmosphere.path_file": (_S, "L_path(lambda, R) from the file."),
    "atmosphere.path_L_km": (_S, "One column: scaled with (1 - tau(R)) / (1 - tau(L))."),
    # ---------------------------------------------------------------- turbulence
    "turbulence.on": (_P, "Adds MTF_turb(r, R) to the pre-sampling MTF (Visible / General; Thermal as an option)."),
    "turbulence.cn2_preset": (_P, "Fills Cn2 from the climate table."),
    "turbulence.thermal": (_P, "Thermal: MTDP_R = MTDP_0 x AMOP_0 / AMOP_R."),
    "turbulence.exposure": (_P, "Long: exp[-3.44 (lambda r / r0)^(5/3)]. Short: x [1 - a (lambda r / D)^(1/3)]."),
    "turbulence.wind_ms": (_P, "Exposure-time MTF: tilt removed over the aperture D + v tau."),
    "turbulence.se_factor": (_P, "a = 1/2 (far field), 1 (near field) or by D / sqrt(lambda L)."),
    "turbulence.cn2_mode": (_P, "Constant Cn2, a height law, an altitude profile, the weather or r0."),
    "turbulence.cn2": (_P, "r0 = 0.185 [lambda^2 / Int Cn2(z)(z / L)^(5/3) dz]^(3/5), so r0 ~ Cn2^(-3/5)."),
    "turbulence.hv_wind_ms": (_P, "Hufnagel-Valley: Cn2(h) = 0.00594 (v / 27)^2 (1e-5 h)^10 exp(-h / 1000) + ..."),
    "turbulence.wx_T_K": (_P, "Cn2 at 15 m from the weather regression (Sadot & Kopeika)."),
    "turbulence.wx_rh_pct": (_P, "Cn2 at 15 m from the weather regression."),
    "turbulence.wx_wind_ms": (_P, "Cn2 at 15 m from the weather regression."),
    "turbulence.wx_hour": (_P, "Temporal-hour weight W of the weather regression."),
    "turbulence.wx_W": (_P, "Weight W in Cn2 = 3.8e-14 W + ..."),
    "turbulence.wx_calib": (_P, "Cn2 x calibration factor."),
    "turbulence.r0_cm": (_P, "MTF_turb = exp[-3.44 (lambda r / r0)^(5/3)]."),
    "turbulence.r0_lambda_um": (_P, "r0 scales with lambda^(6/5)."),
    "turbulence.r0_L_km": (_P, "r0 scales with L^(-3/5)."),
    "turbulence.h_ref_m": (_P, "Cn2(h) = Cn2(h_ref)(h / h_ref)^(-4/3) by day, ^(-2/3) at night (Eq. 4.84)."),
    "turbulence.time": (_P, "Exponent of the height law: -4/3 by day, -2/3 at night."),
    "turbulence.L0_m": (_P, "Outer scale: structure function x [1 - 1.485 (s / L0)^(1/3)]."),
    "turbulence.mit_model": (_P, "Gain: r0 x gain. Physical: part of the tilt removed, lucky regions."),
    "turbulence.mitigation": (_P, "r0_effective = r0 x gain."),
    "turbulence.mit_alpha": (_P, "Fraction a of the tilt removed in MTF_turb."),
    "turbulence.mit_select": (_P, "Lucky-region selection among the integrated frames."),
    "turbulence.aniso": ("check", "Isoplanatic angle theta0: whether the target distorts within itself."),
    "turbulence.scint": ("check", "sigma_A^2 = 0.124 k^(7/6) L^(11/6) Cn2: fluctuation of a point target."),
    # ---------------------------------------------------------------- measured data
    "measured.fom_file": ("threshold", "Measured MTDP / MRTD / MCP curve: compared with, or replacing, the model."),
    "measured.fom_kind": ("threshold", "Which figure of merit the file holds."),
    "measured.fom_unit": ("threshold", "Frequency unit of the file."),
    "measured.fom_vunit": ("threshold", "Value unit of the file."),
    "measured.fom_use": ("threshold", "Compare with the model, or use the measured curve for the ranges."),
    "measured.sfr_file": ("check", "Measured MTF / SFR compared with the modelled MTF."),
    "measured.sfr_kind": ("check", "Device MTF or the delivered image."),
    "measured.sfr_unit": ("check", "Frequency unit of the file."),
    "measured.netd_mK": ("check", "Measured NETD compared with the modelled NETD."),
    "measured.netd_TB_K": ("check", "Temperature of the NETD measurement."),
}

_DOC = re.compile(r"(\.meta\.|^optics\.mtf_(meta|band|focus|temp|uncert)$)")
_ADDITIONAL = re.compile(r"additional\.(pre|post)_[hv]_(type|par)$")


def formula_for(path):
    """(stage key, formula text) of a field path, or None when the field is unknown."""
    p = re.sub(r"\.\d+\.", ".N.", path)
    m = _ADDITIONAL.match(p)
    if m:
        stage, text = FIELD["additional." + m.group(2)]
        return ("mtf_pre" if m.group(1) == "pre" else "mtf_post"), text
    if p in FIELD:
        return FIELD[p]
    if _DOC.search(p):
        return ("doc", "")
    return None


def help_addendum(path):
    """Text appended to the '?' help of a field: where it enters the calculation and the formula."""
    f = formula_for(path)
    if not f:
        return ""
    stage, text = f
    title, _he, desc, _hd = STAGES[stage]
    return "\n\nIn the calculation - %s:\n%s" % (title, text or desc)


def card_lines(path):
    """[Hebrew stage title, Hebrew stage text, formula] for the field card of the guide (None: unknown field)."""
    f = formula_for(path)
    if not f:
        return None
    stage, text = f
    _en, he, _desc, he_desc = STAGES[stage]
    return [he, he_desc] + ([text] if text else [])


CHAIN = [
    ("geometry", "IFOV = p / f\nFOV = [(n - 1) p + a] / f\nNyquist frequency r_N = f / (2 p)   [cycles/mrad]"),
    ("signal", "N = (pi / 4F^2) x Int L(lambda) tau_atm(lambda, R) tau_opt(lambda) QE(lambda) dlambda x A_det x t_int\n"
               "Thermal: the signal is dT x tau_atm(R) in kelvin, with dN/dT the same integral over dL/dT."),
    ("noise", "sigma^2 = [NF^2 (j_T + j_B) / 2 + j_dark] A_det g^2 t_int + n_reads (read^2 + LSB^2 / 12)\n"
              "NETD = sigma / (dN/dT)\nFixed pattern noise is added without the division by N_int."),
    ("mtf_pre", "MTF_pre(r, R) = MTF_optics x MTF_detector x MTF_motion x MTF_turbulence(R)\n"
                "MTF_diff = (2/pi)[acos(x) - x sqrt(1 - x^2)], x = lambda r / D\n"
                "MTF_detector = sinc(a r / f)\nMTF_jitter = exp(-2 pi^2 sigma^2 r^2)\n"
                "MTF_turb = exp[-3.44 (lambda r / r0)^(5/3) (1 - a (lambda r / D)^(1/3))]"),
    ("mtf_post", "MTF_post(r) = MTF_filter x MTF_zoom x MTF_display x MTF_eye\n"
                 "MTF_eye = exp(-Gamma(L) r / M_sys),  M_sys = n_v p_display / (FOV_v d_view)"),
    ("threshold", "AMOP(r): modulation of a 4-bar pattern after MTF_pre, the sampling and MTF_post, at the best "
                  "phase\nMTDP(r) = (pi / 2) SNR_th sqrt(Psi(r)) / AMOP(r)\n"
                  "Psi = NETD^2 / N_int x E_h E_v + Psi_FPN,  N_int = frame rate x t_eye"),
    ("atmosphere", "tau_atm(R) = tau0 exp(-sigma R);  sigma = 3.912 / V in the visible\n"
                   "Thermal signal at the range: dT x tau_atm(R)"),
    ("criterion", "Required frequency of a task: r = N_task R / sqrt(W H)\n"
                  "Range = the largest R at which Signal(R) >= MTDP(r); horizontal and vertical are combined by the "
                  "geometric mean\nResolution-limited: R ~ f sqrt(W H) / (p N_task).  Signal-limited: "
                  "R ~ ln(dT / MTDP) / sigma"),
]


def chain_text():
    """The calculation chain as plain text (Help > How the range is calculated)."""
    out = ["How the range is calculated", "",
           "Every input enters the range through one of the steps below. The '?' next to a field names its step "
           "and shows its formula; the guide card of the field does the same in Hebrew.", ""]
    for key, formulas in CHAIN:
        title, _he, desc, _hd = STAGES[key]
        out += [title, desc if key not in ("geometry", "signal", "noise", "threshold") else "", formulas, ""]
    out += ["Fields that do not enter the range",
            "Extra output: " + STAGES["output"][2], "Check / diagnostic: " + STAGES["check"][2],
            "Documentation: " + STAGES["doc"][2]]
    return "\n".join(line for line in out if line is not None)
