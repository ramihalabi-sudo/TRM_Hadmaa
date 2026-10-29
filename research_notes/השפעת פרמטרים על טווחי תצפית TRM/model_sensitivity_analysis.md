# Quantitative sensitivity of the TRM_HADMAA (TRM4.v3 re-implementation) DRI ranges and image-quality outputs to its input parameters

All numbers below were produced by running the model in the local repository (`trm4.model.run_project`, engine "TRM4.v3 model / TRM_HADMAAv1 engine 2.4") on 2026-10-28. The repository was not modified; all scripts and results are in the scratchpad folder
`C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/` (below: **SP/**).
"Elasticity" e = d ln R / d ln p, computed as ln(R(1.1p)/R(0.9p)) / ln(1.1/0.9) (central ±10 %), unless stated otherwise. D/R/I = Detection / Recognition / Identification. "atm 1" = good weather (first atmosphere of the template), "atm 2" = bad weather (second atmosphere).

## Q1 - Which parameters dominate DRI range for each system type and task, and which have negligible effect?

### Takeaway
Across all four systems the biggest single levers are the task criterion (line pairs), the target size, focal length / IFOV and (for MWIR/SWIR) aperture diameter, with atmosphere dominating Detection. Noise parameters (NETD, read noise) are second-order (|e| ≤ 0.2) in the baseline configurations except for the photon-starved SWIR night camera. 69-75 of ~104 non-zero numeric inputs per system have **no measurable effect** (<0.1 %) on any DRI range in the given configuration, many of them shown in the GUI at the "base" level.

### Setup and reproducibility (baseline record)
- Scripts: SP/sens_common.py (system definitions + evaluator), SP/oat_scan.py (one-at-a-time scan of every numeric project leaf at x0.75/x0.9/x1.1/x1.25), SP/sweeps.py (physically meaningful 1-D sweeps and 2-D grids), SP/fine_edge.py (fine sweeps + edge cases), SP/analyze_oat.py, SP/analyze_sweeps.py, SP/gui_levels.py. Python 3.14.3, numpy 2.4.3, scipy 1.18.1, matplotlib 3.10.8 at `C:/Users/ramih/AppData/Local/Python/bin/python.exe`.
- **MWIR cooled (SCD Blackbird 1920 XBn-based)** = template "Thermal - MWIR cooled staring 640x512 (XBn 3.6-4.2 um)" + values from `Detector datasheets/SCD_Blackbird_1920_XBn/lookup.json`: n_h×n_v = 1920×1536, pitch = active = 10 µm, storage_e = 2.0e6 e-, noise_floor_e = 330 e-, dark_A = 2e-13 A, lsb_e = 244 e-, T_cs_K = 150 K, QE preset "XBn MWIR 3.6-4.2 um", noise_mode "calculated", tint_mode "wellfill" 60 %, frame rate 60 Hz (lookup gives 120 Hz max), optics f = 300 mm, D = 75 mm (F/4), tau_opt 0.8, cs_eff 1.0, display 1920×1536 @ 0.27 mm, 50 cm, 50 cd/m², STANAG 4347 target 2.3×2.3 m, ΔT 2 K, T_bg 288 K, atm 1 σ = 0.2 /km, atm 2 σ = 1.0 /km, both tau0 = 0.8 (template value). Derived: IFOV 33.3 µrad, calculated NETD 57.7 mK, t_int 16.67 ms (frame-time-limited; well fill only 18 %), λ_peak 4.10 µm, Fλ/d = 1.64, MTF@Nyquist 0.070, MTF50 6.90 cy/mrad. [SP/baseline.py output; SP/sens_common.py]
- **LWIR uncooled** = template "Thermal - LWIR uncooled microbolometer 640x480": 17 µm pitch (16 µm active), f = 50 mm, D = 50 mm (F/1), tau_opt 0.9, flat response 8-14 µm, noise_mode "device" NETD 50 mK, FPN 0.5×NETD, t_th 10 ms, 30 Hz, display 800×600 @ 0.3 mm; same target; atm σ = 0.2 / 1.0 /km, tau0 = 1. Derived: IFOV 340 µrad, Fλ/d = 0.82 (λ_peak = 14 µm because QE is flat; ≈0.59 at 10 µm), MTF@Nyquist 0.40 (aliasing "high").
- **VIS daylight** = template "Visible - CMOS daylight camera 1920x1080": 5 µm pitch, f = 100 mm, D = 25 mm (F/4), tint 0.25 ms, direct sun (E_peak 1239), olive paint on dry grass (spectral), visibility atm 1 V = 23 km / atm 2 V = 5 km (F_PR 0.2), turbulence ON, Cn² = 1e-14 (fixed, short exposure). Derived: IFOV 50 µrad, Fλ/d = 0.52, MTF@Nyquist 0.43; warning "brightest pixel saturates (245 %)".
- **SWIR night** = template "Visible/SWIR - InGaAs night camera 640x512": 15 µm, f = 150 mm, D = 75 mm (F/2), tint 30 ms, full moon (E_peak 1.74e-3), read noise 30 e-, V = 23 / 5 km, turbulence OFF. Derived: IFOV 100 µrad, Fλ/d = 0.19, "read-noise limited" warning (345 background e-/frame).
- Baseline DRI ranges [km] (atm 1 | atm 2): MWIR 16.95 / 8.97 / 5.35 | 5.19 / 4.05 / 3.11; LWIR 5.25 / 1.80 / 0.91 | 2.89 / 1.62 / 0.88; VIS 14.73 / 8.18 / 5.00 | 5.78 / 4.22 / 3.11; SWIR 9.04 / 4.78 / 2.66 | 3.86 / 2.53 / 1.81. [SP/oat_analysis.txt]
- Scan size: 1 763 rows (1 598 successful runs, 165 zero-valued leaves recorded but not perturbable multiplicatively, 0 errors); 557 1-D sweep runs; 82 2-D grid runs; 161 fine-sweep runs; 122 edge-case runs.

### Cited Findings
**Elasticity ranking, good weather (atm 1), ±10 % central differences** - [SP/oat_analysis.txt](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/oat_analysis.txt), full table in [SP/oat_elasticities.csv](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/oat_elasticities.csv)

| System | Parameter (baseline) | e_D | e_R | e_I |
|---|---|---|---|---|
| MWIR | target.T_bg_K (288 K) | 1.17 | 1.14 | 1.15 |
| MWIR | optics.D_mm (75) | 0.41 | 0.58 | 0.93 |
| MWIR | task line pairs (1/3/6) | -0.40 | -0.71 | -0.83 |
| MWIR | atm 1 extinction σ (0.2/km) | -0.60 | -0.28 | -0.16 |
| MWIR | target W or H (2.3 m), each | 0.18 | 0.36 | 0.42 |
| MWIR | ΔT, tau0, tau_opt, tau_filter | 0.20 | 0.16 | 0.15 |
| MWIR | display.snr_th (2.5) | -0.19 | -0.16 | -0.15 |
| MWIR | pitch_v (10 µm, f fixed) | -0.14 | -0.13 | -0.06 |
| MWIR | noise_figure / qe_scale / fpn_fraction | -0.14 / 0.12 / -0.11 | -0.11 / 0.10 / -0.10 | -0.11 / 0.10 / -0.09 |
| MWIR | frame_rate (60 Hz) | -0.07 | -0.07 | -0.06 |
| MWIR | optics.f_mm (D fixed) | 0.04 | 0.12 | -0.04 (non-monotonic) |
| MWIR | noise_floor_e (330 e-) | -0.03 | -0.04 | -0.03 |
| LWIR | task line pairs | -0.93 | -0.98 | -0.99 |
| LWIR | optics.f_mm (D fixed, NETD fixed) | 0.74 | 0.86 | 0.87 |
| LWIR | target W or H, each | 0.47 | 0.49 | 0.50 |
| LWIR | pitch_v / a_v (17/16 µm) | -0.22 / -0.19 | -0.06 / 0.04 | -0.09 / 0.01 (non-monotonic) |
| LWIR | optics.D_mm (diffraction only) | 0.17 | 0.13 | 0.13 |
| LWIR | detector.netd_mK (50) and snr_th | -0.06 | -0.04 | -0.04 |
| LWIR | ΔT | 0.07 | 0.04 | 0.04 |
| LWIR | atm 1 σ | -0.07 | -0.02 | -0.01 |
| VIS | task line pairs | -0.52 | -0.60 | -0.80 |
| VIS | atm 1 visual range V (23 km) | 0.41 | 0.25 | 0.07 |
| VIS | optics.f_mm (D fixed) | 0.27 | 0.24 | 0.42 |
| VIS | target W / H | 0.26 / 0.25 | 0.30 / 0.33 | 0.41 / 0.41 |
| VIS | pitch_v (5 µm) | -0.17 | -0.10 | +0.23 (non-monotonic) |
| VIS | snr_th / tau0 | -0.16 / 0.16 | -0.17 / 0.19 | -0.09 / 0.08 |
| VIS | F_PR path-radiance factor (0.2) | -0.13 | -0.10 | -0.04 |
| VIS | sun elevation beta_v (45°) / PRNU (0.5 %) | -0.12 / -0.11 | -0.10 / -0.11 | -0.04 / -0.06 |
| VIS | Cn² (1e-14, ±10 %) | -0.10 | -0.13 | -0.06 |
| VIS | D_mm (25) | 0.08 | 0.13 | 0.09 |
| VIS | tint, E_peak, qe_scale, tau_opt | 0.03 | 0.02 | 0.01 |
| SWIR | task line pairs | -0.48 | -0.71 | -0.89 |
| SWIR | optics.D_mm (75) | 0.50 | 0.71 | 0.43 |
| SWIR | atm 1 V (23 km) | 0.38 | 0.31 | 0.09 |
| SWIR | tau_opt, E_peak (moon), qe_scale | 0.24 | 0.36 | 0.19 |
| SWIR | snr_th | -0.25 | -0.37 | -0.21 |
| SWIR | tint (30 ms) / electron_gain | 0.21 / 0.17 | 0.32 / 0.26 | 0.17 / 0.13 |
| SWIR | target W / H | 0.28 / 0.23 | 0.38 / 0.36 | 0.47 / 0.48 |
| SWIR | optics.f_mm (D fixed) | -0.23 | 0.14 | 0.49 (non-monotonic) |
| SWIR | read noise (30 e-) | -0.13 | -0.20 | -0.10 |

**Physically meaningful steps** - [SP/sweeps_1d_analysis.txt](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/sweeps_1d_analysis.txt), raw data [SP/sweeps_1d.csv](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/sweeps_1d.csv)
- MWIR F-number at f = 300 mm (D = f/F): F/2 → D 20.44, R 12.98, I 8.09 km (+21 / +45 / +51 % vs F/4); F/8 → 12.01 / 5.45 / 2.94 km (-29 / -39 / -45 %). Calculated NETD 27.4 mK at F/2 vs 57.7 mK at F/4 vs 157 mK at F/8.
- MWIR focal length with F fixed: 300 → 600 mm gives D +26 %, R +55 %, I +68 % (21.3 / 13.9 / 8.97 km); 300 → 150 mm gives 11.8 / 5.35 / 2.90 km.
- MWIR focal length with D fixed (75 mm): 150 → 600 mm changes D only 15.65 → 16.57 km and I 4.32 → 5.45 km, non-monotonic in R (8.09, 8.98, 9.12, 8.97, 9.25, 9.40, 9.31).
- MWIR measured-NETD mode: 20 → 40 mK: D 19.89 → 17.98 km (-9.6 %), R 10.68 → 9.55 (-10.6 %), I 6.09 → 5.65 (-7.2 %); 10 → 130 mK: D 21.8 → 14.5 km (e ≈ -0.16).
- MWIR random LOS jitter (rms, both axes; baseline 0): 10 µrad → I -5.6 %; 20 µrad → D -7 %, R -14 %, I -18.5 %; 50 µrad → I -47 %; 100 µrad → I -68 %. Linear motion 5 mrad/s → I -29 %.
- MWIR detector: read noise negligible below ≈300 e- (30 → 300 e-: -2 %), 330 → 932 e-: -9 % (D); dark current negligible below 3e-13 A, 1e-11 A: -12 %, 1e-10 A: -47 %; ADC LSB negligible below ≈600 e-; storage capacity and well-fill target have **zero** effect above 0.8 Me- / 20 % because integration is frame-time-limited; cold-shield temperature negligible up to 170 K, 200 K: -1.6 %, 230 K: -10 %.
- MWIR display/observer: viewing distance 50 → 100 cm: I -9 %; 20 cm: I +5 %; display luminance 50 → 0.5 cd/m²: I -7 %; eye integration 0.1 → 0.04 s: -4.5 %; SNR threshold 2.5 → 4: I -8 %.
- MWIR task presets: "sandia148" (1/4/8) R -18 %, I -22 %; "johnson1958" (1/4/6.4) R -18 %, I -5 %.
- LWIR NETD (device mode) 50 → 20 mK: D +3.8 %, R +3.9 %, I +4.0 %; 50 → 100 mK: D -8 %, R -2.9 %, I -2.9 %.
- LWIR pitch at fixed f (active size scales): 17 → 12 µm: D +22 %, R +30 %, I +31 %; 17 → 8 µm: D +42 %, R +59 %, I +63 %.
- LWIR focal length with F fixed: 50 → 100 mm: D +75 %, R +97 %, I +99 % (e ≈ 0.8-1.0).
- LWIR target size (W = H) 2 → 2.83 m: D e = 0.91, I e = 0.99 (pure geometry, sampling-limited).
- VIS visual range: 23 → 10 km: D -35 %, R -27 %, I -16 %; 23 → 5 km: D -61 %, R -48 %, I -38 %; 50 km: D +27 %.
- VIS F_PR = 0 (no path radiance) vs 0.2: D +35 %, R +19 %, I +6 %.
- VIS illumination ×0.01 (dusk): D -30 %, R -35 %, I -35 %; ×1e-4: D -87 %.
- VIS integration time 0.25 → 0.02 ms: D -12 %, I -13 %; 0.25 → 5 ms: +3 % (saturation is not penalised, see Q4).
- SWIR read noise 30 → 3 e-: D +15 %, R +9 %, I +7 %; 30 → 300 e-: D -48 %, R -57 %, I -57 %. Illumination ×0.1 (≈ quarter-moon-to-starlight levels) D -55 %, R -62 %, I -63 %. Dark current 2e-15 → 1e-13 A: D -30 %.

**Zero-influence inputs** (no change > 0.1 % on any DRI range in either atmosphere at any of the four perturbations) - [SP/oat_analysis.txt](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/oat_analysis.txt), cross-referenced with the GUI levels (gui.TABS "base"/"adv") in [SP/zero_vs_gui.txt](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/zero_vs_gui.txt)
- MWIR: 70 inputs, among them dark_A (at 2e-13), lsb_e, storage_e, wellfill_pct, cuton/cutoff_um, netd_mK (calculated mode), n_h, n_v, t_th_ms, Cn² and all turbulence inputs, target.alt_m, all reflectance/irradiance inputs, V_km, F_PR, T_air.
- LWIR (device NETD): 75 inputs, including **optics.tau_opt and tau_filter**, qe_scale, all photon-detector inputs (noise_floor_e, dark_A, storage_e, wellfill, lsb, T_cs, cs_eff), t_th_ms (only used with linear motion), n_h, n_v, Cn².
- VIS: 71 inputs, including noise_floor_e, dark_A, dsnu_A, lsb_e, electron_gain, storage_e (despite saturation), target.D_m (front aspect), target.T_bg_K, target.alt_m (fixed-Cn² mode).
- SWIR: 69 inputs, including storage_e, target.D_m, T_bg_K, alt_m.
- GUI "base"-level and visible but zero-influence in these configurations: detector.n_h / n_v (all systems - only FOV), detector.wellfill_pct and storage_e (MWIR, frame-time-limited), optics.tau_opt / tau_filter and detector.t_th_ms (LWIR uncooled, device NETD), storage_e, target.D_m and target.T_bg_K (VIS/SWIR). Visible "adv" inputs with zero influence: optics.rel_illum (reporting only), display.n_h/n_v/pitch_h_mm, target.alt_m, detector.fill_limit_pct, bright_refl, bright_dT_K, smear_allow_px (exposure-budget diagnostics only). [SP/zero_vs_gui.txt]
- By design (TRM4): the TRM4.v3 documentation says the Turbulence dialog "is active for imager categories Visible and General only" (Sec. 2.28) and that target altitude "for category Thermal ... does not affect range calculation" (Sec. 2.24.1) - [TRM4v3_ModelDocumentation_260930_095803.pdf, p. 99 and p. 84](C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf); code: `turbulence_active()` returns False for Thermal ([trm4/model.py L1502-1504](C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/trm4/model.py)). Sweep confirms: MWIR Cn² 1e-16 … 1e-12 with turbulence on gives identical ranges.

**Image-quality outputs (elasticities, ±10 %)** - [SP/oat_analysis.txt "IQ elasticities"](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/oat_analysis.txt)
- MTF50 (object space, cy/mrad) vs aperture D: MWIR 0.82, LWIR 0.46, VIS 0.35, SWIR 0.10; vs active detector size: MWIR -0.18, LWIR -0.54, VIS -0.65, SWIR -0.90; vs f (D fixed): MWIR 0.19, LWIR 0.54, VIS 0.65, SWIR 0.91.
- MTF at Nyquist vs pitch: MWIR 7.1 (MTF@Nyq only 0.07, close to the diffraction cut-off), LWIR 1.53, VIS 1.51, SWIR 1.15.
- MWIR calculated NETD: e = -6.5 vs T_bg (±29 K), -1.29 vs D, +1.28 vs f, -1.0 vs tau_opt, -0.64 vs qe_scale, +0.71 vs noise_figure, +0.62 vs frame rate (t_int is frame-limited), -0.36 vs cs_eff, +0.23 vs read noise, +0.02 vs dark current, +0.01 vs LSB. CNR at zero range is the exact inverse.
- SWIR CNR(0): +1.76 vs D, -1.76 vs f, +0.88 vs tau/E/QE, +0.79 vs tint, -0.43 vs read noise. VIS CNR(0): +0.66 vs D, +0.33 vs tau/E/QE/tint, -0.35 vs PRNU, -0.65 vs noise_figure (FPN/photon-limited daylight).

### Inferences
- In these TRM4-type calculations the "Johnson-like" geometric chain (line pairs, target size, focal length/IFOV) dominates Identification (|e| ≈ 0.4-1.0), while sensor noise is usually second order (|e| ≤ 0.2). Only in the photon-starved SWIR case do illumination, transmission, QE, integration time and read noise reach |e| ≈ 0.2-0.4.
- For the MWIR XBn configuration, aperture D (not focal length) is the hardware lever: with Fλ/d = 1.64 the system is near the optics-limited region, so f at fixed D buys almost nothing, while D raises both resolution and flux (NETD ∝ ~F^1.1-1.3 here).
- The extreme MWIR sensitivity to background temperature (e ≈ 1.15, NETD e ≈ -6.5) comes from the narrow 3.6-4.2 µm band with frame-time-limited integration (well fill only 18 % at 288 K); the user-facing implication is that MWIR XBn predictions at cold backgrounds (243 K: NETD 252 mK, D -26 %) need care.
- Candidates for hiding as "advanced" or auto-greying: detector.n_h / n_v (affect only FOV), storage_e / wellfill_pct when integration is frame-limited, photon-detector inputs when an uncooled device NETD is used, target.D_m for front aspect / horizontal paths, target.T_bg_K in the Visible category, display.pitch_h_mm, optics.rel_illum, exposure-budget inputs (fill_limit_pct, bright_refl, bright_dT_K, smear_allow_px, snr_req), turbulence inputs in Thermal.

### Gaps
- One representative configuration per system type; elasticities are local and change with regime (see Q2/Q3). No verification against the original Fraunhofer TRM4 executable or measured field data was possible.
- The GUI-level cross-check ignores header-level visibility conditions (only field conditions evaluated).
- ±25 % on absolute temperature (T_bg in K) is not physically meaningful; use the 1-D T_bg sweep (243-318 K) instead.

## Q2 - How do the dominant parameters change between short and long range, and between good/bad weather and turbulence?

### Takeaway
Detection (longest range) is atmosphere-limited and Identification (shortest) is resolution-limited: MWIR σ-elasticity is -0.60 for D but -0.16 for I; VIS visual-range elasticity is 0.41 for D but 0.07 for I. In bad weather the atmosphere takes over all tasks (MWIR σ: -0.82/-0.69/-0.50; VIS V: 0.78/0.59/0.54) and hardware elasticities roughly halve. In the Visible category turbulence becomes the dominant limitation above Cn² ≈ 1e-13 m^-2/3, where aperture no longer matters; in the Thermal category turbulence has no effect at all.

### Cited Findings
- Good vs bad weather elasticities (e_D/e_R/e_I) - [SP/oat_analysis.txt](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/oat_analysis.txt):
  - MWIR extinction: atm 1 (σ 0.2) -0.60/-0.28/-0.16 → atm 2 (σ 1.0) -0.82/-0.69/-0.50; D_mm 0.41/0.58/0.93 → 0.22/0.29/0.37; target W (each) 0.18/0.36/0.42 → 0.09/0.16/0.25; task lp D -0.40 → -0.18, I -0.83 → -0.50.
  - LWIR extinction: -0.07/-0.02/-0.01 → -0.71/-0.23/-0.04; NETD -0.06/-0.04/-0.04 → -0.25/-0.14/-0.04 (4× more important for D in bad weather); f_mm 0.74/0.86/0.87 → 0.19/0.53/0.80.
  - VIS visual range: 0.41/0.25/0.07 → 0.78/0.59/0.54; f_mm 0.27/0.24/0.42 → 0.14/0.26/0.37; target W 0.26/0.30/0.41 → 0.11/0.19/0.26.
  - SWIR visual range: 0.38/0.31/0.09 → 0.72/0.49/0.50; D_mm 0.50/0.71/0.43 → 0.47/0.51/0.75.
- MWIR extinction sweep (atm 1): σ = 0.02 → D 34.3, R 12.1, I 6.10 km; 0.2 → 16.9/8.97/5.35; 2.0 → 2.91/2.40/2.02 km. Local D elasticity grows from ≈-0.2 at σ = 0.03 to ≈-0.8 at σ ≥ 0.4 (Beer-Lambert: ETD = ΔT·τ, Eq. 3.208, [TRM4 doc p. 153](C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)). [SP/sweeps_1d_analysis.txt]
- MWIR NETD × σ grid (measured-NETD mode): NETD 15 → 120 mK costs D -28 % at σ 0.05 (35.5 → 25.7 km) and -25 % at σ 2.0 (3.48 → 2.60 km); for I it costs -17 % at σ 0.05 (6.54 → 5.41) but -29 % at σ 2.0 (2.49 → 1.77). [SP/sweeps_2d.csv](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/sweeps_2d.csv)
- VIS turbulence (Cn² fixed along the path, short exposure): 1e-16 → D 16.71, R 9.80, I 5.70 km; 1e-14 (baseline) → 14.73/8.18/5.00; 1e-13 → 9.87/5.04/3.21 (-33/-38/-36 %); 1e-12 → 5.03/2.51/1.60 (-66/-69/-68 %). Long exposure at 1e-14: D -3.6 %, I -3.6 %; height-dependent Cn² (day) at 1e-14: D -11 %, I -12 %. Cn² = 1e-11: D 2.12, I 0.73 km. [SP/sweeps_1d_analysis.txt; SP/edge.csv](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/edge.csv)
- Turbulence is switched off by design for Thermal (TRM4.v3 doc Sec. 2.28, p. 99) - [TRM4 doc](C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf); the MWIR sweep with turbulence on, Cn² 1e-16 … 1e-12, returns 16.949/8.974/5.346 km every time. [SP/sweeps_1d_analysis.txt]
- Removing VIS path radiance (F_PR 0.2 → 0) raises Detection by 35 % but Identification by only 6 %: path radiance is a long-range (Detection) effect. [SP/sweeps_1d_analysis.txt]

### Inferences
- The ranking flips with range: for long Detection ranges, invest in atmosphere knowledge (σ / V uncertainty is the dominant uncertainty), for Identification in focal length / aperture / target-size definition.
- In bad weather NETD and aperture matter less in relative terms for MWIR, but the uncooled LWIR system gains noticeably more from a better NETD in bad weather (e_D from -0.06 to -0.25), because its good-weather ranges are sampling-limited.
- For daytime long-range VIS (and, physically, also MWIR), turbulence must be part of any study: Cn² uncertainty of one decade is worth ±35 % in range, larger than any hardware parameter. That the model gives MWIR zero turbulence sensitivity is a TRM4 scope limit, not a physical result (r0 ∝ λ^6/5, so MWIR is less but not un-affected).

### Gaps
- Only two weather states per template (σ 0.2/1.0 /km thermal, V 23/5 km visible) were scanned exhaustively; spectral (MODTRAN) atmospheres and imported path radiance were not tested.
- No thermal turbulence sensitivity can be quantified with this model (feature absent).

## Q3 - Interactions and regime changes (Fλ/d / Q, sampling vs diffraction vs noise vs atmosphere/turbulence)

### Takeaway
The Fλ/d (Q) regime controls which hardware parameter pays off: at Q ≲ 1 (LWIR uncooled 0.82, VIS 0.52, SWIR 0.19) ranges scale almost 1:1 with IFOV (f/pitch) and target size and are labelled "sampling (beyond Nyquist)"; at Q ≳ 1.6-2 (MWIR XBn F/4 and slower) pitch and f-at-fixed-D stop mattering and only D (diffraction + flux) helps. Turbulence × aperture: above Cn² ≈ 1e-13 the aperture becomes irrelevant in the VIS system.

### Cited Findings
- MWIR F-number × pitch grid at f = 300 mm (Identification, km; Q = λ_peak F / d): at F/2 pitch 5/8/10/15/20 µm → 8.98/8.83/8.09/6.05/5.08 (Q 1.64…0.41, pitch matters: 10 → 20 µm -37 %); at F/8 → 2.83/2.92/2.94/2.88/2.90 (Q 6.6…1.6, pitch irrelevant, ±4 %); at F/4 → 5.45/5.32/5.35/5.03/4.32. Detection at F/2: 21.3 … 16.9 km; at F/8: 11.1 … 12.1 km (smallest pitch is worst at F/8). [SP/sweeps_2d.csv](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/sweeps_2d.csv)
- MWIR pitch at fixed f = 300 mm, F/4: 5 µm (Q 3.3) → I 5.45 km but calculated NETD 157 mK; 25 µm (Q 0.66) → I 3.88 km, NETD 27.5 mK. Range is almost flat from 5 to 12 µm (I 5.45 → 5.29) - smaller pixels do not help once Q ≳ 1.4. Pitch with IFOV and F held fixed (f and D scale with pitch): 10 → 20 µm (f 600, D 150 mm) I +51 %, 10 → 5 µm I -45 %. [SP/sweeps_1d_analysis.txt]
- MWIR dashboard limiter switches with F-number: F ≤ 3.4 "sampling (beyond Nyquist)", F/4 "sampling (near Nyquist)", F/4.5-5.6 "contrast / noise", F ≥ 6.5 "resolution (MTF)" (MTF@Nyquist 0.40 at F/1.5 → 0 at F/6.5). [SP/sweeps_1d_analysis.txt]
- These thresholds are consistent with Holst's Fλ/d framework: "Small Fλ/d values represent detector-limited operation, whereas large values represent optics-limited operation", with a transition "in the region 0.41 < Fλ/d < 1.0" for resolution and no aliasing for Fλ/d ≥ 2 - [Holst 2007, Opt. Eng. 46(10) 103204](https://proceedings.spiedigitallibrary.org/journals/optical-engineering/volume-46/issue-10/103204/Imaging-system-performance-based-upon-F%ce%bbd/10.1117/1.2790066.full); [Holst 2012, Small detectors in infrared system design](https://spiedigitallibrary.org/journals/Optical-Engineering/volume-51/issue-9/096401/Small-detectors-in-infrared-system-design/10.1117/1.OE.51.9.096401.pdf); [Photonics.com summary](https://www.photonics.com/Article.aspx?AID=29926). In the optics-limited region "decreasing the detector size does not generally increase range" (same sources, via search summary).
- MTF50 elasticity to D (0.82 MWIR … 0.10 SWIR) and to active pixel size (-0.18 MWIR … -0.90 SWIR) is an independent regime indicator that orders the systems exactly like Q (1.64 > 0.82 > 0.52 > 0.19). [SP/oat_analysis.txt]
- LWIR NETD × focal length (F/1 kept): NETD 20 → 120 mK costs D -10 % at f = 25 mm (2.79 → 2.52 km) but -27 % at f = 100 mm (10.37 → 7.58 km); Identification only -14 % / -9 %. Longer lenses move the system out of the sampling limit into the noise/atmosphere limit. [SP/sweeps_2d.csv]
- LWIR F-number: with the device NETD held fixed, F/1 → F/2 only costs D -22 % (diffraction); with Eq. 3.142 scaling (noise_mode "detector", NETD ∝ F²: 50 → 200 mK) D -39 %, R -35 %, I -34 %. NETD ∝ F² is the standard approximation (normalisation "NETD_f/1 = NETD/(f/#)²") - [arXiv 2601.11733](https://arxiv.org/pdf/2601.11733); TRM4 Eq. 3.142 - [TRM4 doc p. 136](C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf). [SP/sweeps_1d_analysis.txt]
- VIS Cn² × F-number (f = 100 mm): Detection at Cn² 1e-15: F/2 17.36, F/4 16.48, F/8 14.52 km (aperture matters, 20 %); at 5e-13: 6.23 / 6.24 / 6.14 km (aperture irrelevant, larger aperture marginally worse for Identification 2.01 vs 2.02 km - short-exposure turbulence MTF). [SP/sweeps_2d.csv]
- MWIR regime switches in detector inputs: integration time frame-limited at 60 Hz (well fill 18 %); storage capacity becomes binding below ≈0.8 Me- (0.2 Me- → D -13 %); well-fill target binds below 20 %; at T_bg ≥ ≈330 K the well fill (60 %) binds and range decreases again (317 K: D 18.32 km, NETD 35 mK; 360 K: D 17.84 km, NETD 42 mK, t_int 4.7 ms). [SP/oat_scan_MWIR_LWIR_SWIR_VIS.csv](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/oat_scan_MWIR_LWIR_SWIR_VIS.csv)
- MWIR frame rate: 15 Hz → D 17.8 km (NETD 28.9 mK, t_int 55 ms - well-limited), 240 Hz → 14.5 km (NETD 151 mK). [SP/sweeps_1d_analysis.txt]

### Inferences
- Design rule supported by the model: for the 10 µm XBn at F/4 (Q = 1.64) a smaller pitch or longer f at the same D gives no range; a larger aperture (F/2-F/3 at the same f) gives +25 to +50 % Identification. For the 17 µm uncooled at F/1 (Q ≈ 0.6-0.8) moving to 12 µm pixels or a longer lens gives near-proportional range gains, and NETD is nearly irrelevant in clear weather.
- NETD interacts with focal length (LWIR) and with weather (MWIR Identification): noise matters when the system is not sampling-limited.
- At strong turbulence, aperture and pitch upgrades in the Visible band are wasted.

### Gaps
- Only four 2-D grids were run (MWIR F#×pitch, MWIR NETD×σ, LWIR NETD×f, VIS Cn²×F#); jitter × focal length and integration time × motion were not gridded.
- Q is reported with the peak-responsivity wavelength (λ_peak); for the flat 8-14 µm uncooled response λ_peak = 14 µm overstates Q (≈0.59 at 10 µm).

## Q4 - Results contradicting physical expectations (suspected bugs), numerical problems and runtime errors

### Takeaway
No crash in the 1 598 one-at-a-time runs, but the edge-case and sweep runs found one unhandled exception (cooled thermal, τ_opt = 0), one wrong-result failure (Visible with turbulence ON returns no Detection range for large targets / long lenses), non-physical range increases with more motion blur or lower display luminance, and quantisation steps of ±4-9 % in sampling-limited systems that make small-step derivatives unreliable.

### Cited Findings
Reproduction: `from sens_common import *; p = sys_xxx(); <change>; run_project(p)` using [SP/sens_common.py](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/sens_common.py); edge results in [SP/edge.csv](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/edge.csv).
1. **Unhandled ZeroDivisionError (bug).** MWIR system with `p["optics"]["tau_opt"] = 0.0` → `ZeroDivisionError` at `self.netd_calc = self.sigma_B / self.dndt` ([trm4/model.py L989](C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/trm4/model.py)). τ_opt = 0 passes the [0, 1] check in `_optics_transmission`. It is not a `ModelError`, so `analysis._run_case` / sweeps (which catch only `ModelError`) would abort. (qe_scale = 0 is likely to hit the same line - not tested.)
2. **Visible + turbulence: Detection range lost for large angular targets (bug).** VIS template, `target.W_m = target.H_m = 20` → D = None (NaN), R 22.8, I 17.6 km; W = H = 50 m → D 0.015 km, R/I None; `f_mm = 3000, D_mm = 750` (F/4) → D None, R 0.012 km, I None. The same cases with `turbulence.on = False` give 34.6/29.0/25.4 km (W = H = 50) and 36.2/30.7/27.1 km (f = 3000). No warning is issued. Likely mechanism (inferred, not traced line by line): with turbulence active `amop_at` calls `amop_direct` for every range, and at the first grid range (10 m) the bar frequency lp·R/a is far below the AMOP table range; the direct simulation then returns AMOP ≤ 0.001 → MDSP = ∞ → the `dead` flag in `_ranges_signal` (model.py L2619-2629) ends the MNDS curve → R0 = None. The non-turbulence path clamps rp < rt[0] to at[0] (L1643-1645).
3. **More blur → longer range (non-physical).** MWIR, `stab.lin_on = True, lin_h = lin_v = 20 → 50 mrad/s`: Recognition 2.33 → 2.64 km, bad-weather Identification 1.11 → 1.29 km; at 20 mrad/s Identification (2.12 km) ≈ Recognition (2.33 km). Likely cause: the linear-motion MTF sinc(t·w·r) (model.py L1385) has negative lobes that the AMOP bar simulation credits as modulation (spurious response).
4. **Lower display quality → longer range (non-physical), and range plateaus.** LWIR: display luminance 50 → 0.5 cd/m² raises R 1.801 → 1.887 km and I 0.907 → 0.943 km; viewing distance 50 → 70 cm raises R 1.80 → 1.89 km and I to 0.943; F/1.1 → F/1.2 (device NETD) raises R 1.779 → 1.886 km. NETD 20 → 15 mK jumps R by +9 % (1.871 → 2.039 km) while 30 → 20 mK gives +1.7 %. Identical plateau values recur for unrelated changes (LWIR R 2.039 / I 1.020 km for NETD 15, ΔT ≥ 6.6 K; LWIR R 1.992 / I 0.996 for F/0.8 and pitch-keep-IFOV 25 µm; SWIR R 5.803 / I 2.970 for illumination ×3.16 … ×100, F/1.2; VIS R 5.803 / I 2.970 for pitch 10 µm). Inferred cause: in `_ranges_thermal` an unreached MTDP sets the resolved frequency to `r_last`, the last finite point of the 70-point log-spaced AMOP/MTDP table (frequency step ≈8.3 %; `amop_table` also stops after three AMOP ≤ 0.001 values), so the range is quantised and capped by the table, and small MTF changes (eye, display, diffraction) move the AMOP cut-off by whole table steps.
5. **Small-step derivative noise.** Fine sweeps (21 points over ±7 %): MWIR D_mm 73.0 → 73.5 mm lowers I 5.249 → 5.225 km (local elasticity -0.66 against a mean of +0.88; std 0.37); MWIR σ: local D elasticity -0.41 … -0.78 (std 0.10); SWIR target size: local D elasticity 0.03 … 0.99 (staircase from the 56-point range grid of the Visible/General range solver, model.py L2611); LWIR NETD and f are smooth (std ≤ 0.04). The built-in `analysis.uncertainty` 1 % derivative consequently returns a *negative* target-width elasticity for SWIR Detection (-1.10) and VIS Identification (-0.15) (see Q5). Also, `analysis.limiting_factors` reports that an ideal eye/display MTF *lowers* MWIR Detection by 0.7 %. One-at-a-time ±10 % scans flagged non-monotonic 3-point responses for pitch / active size / f in MWIR, LWIR, SWIR and VIS (e.g. VIS pitch_v 4.5/5/5.5 µm → I 5.10/5.00/5.35 km). [SP/fine_analysis.txt](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/fine_analysis.txt)
6. **Uncooled device-NETD mode ignores optics throughput.** LWIR with `tau_opt = 0` still gives D 5.22 km (baseline 5.25); τ_opt 0.5 … 1.0 gives identical ranges; F-number only acts through diffraction. The code holds the measured camera NETD constant by design (analysis.apply_policy only adds a note); physically NETD ∝ F²/τ. The alternative "detector" mode (Eq. 3.142) does scale it.
7. **Saturation and impossible exposure are warnings only.** VIS: storage_e has zero effect although the exposure budget reports the brightest pixel at 245 % of capacity; integration time 30 ms at 50 Hz (> 20 ms frame) is accepted with a warning and *increases* D to 15.2 km (+3 %); `wellfill_pct = 150` is accepted without a warning (MWIR/SWIR).
8. **Inconsistent "no-target" sentinels.** Thermal ΔT = 0 → R0 = None (NaN); Visible with τ_opt = 0, tint = 0, illumination 0 or equal reflectivities → R0 = 0.01 km (first grid point). `analysis.model_ranges` maps None → first grid range and ∞ → 100 km ([trm4/analysis.py L158-163](C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/trm4/analysis.py)), while `advisor._ranges` maps None → 0 ([trm4/advisor.py L81-85](C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/trm4/advisor.py)). The range grid is hard-capped at 0.01-100 km (model.py L2513-2515).
9. **Physically plausible, not bugs (but surprising):** MWIR range decreasing for T_bg 317 → 360 K (well-fill regime switch); MWIR f at fixed D nearly flat (optics-limited); SWIR smaller pixels lower Detection (5 µm: 7.61 km vs 15 µm: 9.04 km, photon-starved); display.pitch_h_mm has no effect while pitch_v_mm does (system magnification uses the vertical direction only, model.py L344).

### Inferences
- Items 1-4 should be raised as bugs: 1 is a trivial validation fix (τ_opt > 0, QE > 0, or catch ZeroDivisionError → ModelError); 2 produces silently wrong (zero/NaN) ranges in a supported configuration; 3 and 4 make "more blur / worse display → longer range" possible, which can mislead the advisor's ranking.
- Because of item 4/5, sensitivity derivatives should use ≥ 5-10 % steps (or a denser AMOP frequency table), and any |ΔR| < ≈5 % in sampling-limited systems should be treated as within numerical noise.

### Gaps
- Root causes of items 2-4 are inferred from code reading and behaviour; they were not instrumented line by line.
- The General category and imported data (Zemax MTF, measured jitter/PSD, spectral atmosphere) were not exercised.

## Q5 - Runtime per evaluation, and agreement with the existing analysis.py / advisor.py sensitivity tooling

### Takeaway
One full evaluation takes ≈0.5-0.8 s for thermal and night-SWIR cases and ≈6 s for the Visible daylight template, ten times longer because turbulence forces a direct AMOP simulation at every range (≈21 s for a large target). The built-in tools (`advisor.sensitivities` ±5 %, `analysis.uncertainty` 1 % derivatives, `analysis.limiting_factors`) agree with this study within ≈0.05 in elasticity for smooth parameters (aperture, extinction/visibility, noise, transmission, Cn²). They disagree, sometimes in sign, for target size, focal length and pitch in sampling-limited systems, where small steps fall inside the model's quantisation noise.

### Cited Findings
- Single uncontended runs: MWIR 0.73-0.77 s, LWIR 0.51-0.70 s, SWIR 0.55-0.73 s, VIS 6.2-6.3 s (turbulence on), VIS ≈0.8 s with turbulence off, VIS with W = H = 20 m and turbulence on 20.8 s. [SP/baseline.py output, SP/oat_scan_MWIR_LWIR_SWIR_VIS.csv]
- Profile of one VIS run: 650 calls of `amop_direct` take 59.1 of 63.8 s (run under heavy parallel load), dominated by numpy FFTs in `amop.amop` and `_extrema_modulation` (cProfile). [scratchpad profile output]
- In an 11-process pool on a 12-thread machine the median wall time per run was 2.4-3.1 s (thermal/SWIR) and 32-35 s (VIS); the full 1 763-row scan took 1 722 s, the 557-run 1-D sweep 424 s. [SP/oat_scan.log, SP/sweeps_1d.log]
- Existing tooling: `analysis.uncertainty` computes OAT runs plus local elasticities with a 1 % central-difference step (`deriv_step=0.01`, [trm4/analysis.py L703-721](C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/trm4/analysis.py)); `advisor.sensitivities` uses ±5 % and a fixed parameter list (f, D or F#, pitch, τ_opt, NETD or read noise, tint, V or σ, ΔT, H, jitter) ([trm4/advisor.py L179-251](C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/trm4/advisor.py)); `analysis.limiting_factors` removes one degradation at a time.
- The application's own tools were run on the same four systems ([SP/compare_tools.py](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/compare_tools.py) → [SP/tools_MWIR_LWIR_SWIR_VIS.json](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/tools_MWIR_LWIR_SWIR_VIS.json), side-by-side in [SP/tools_comparison.txt](C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/tools_comparison.txt)). Wall times (11 worker processes for limiting factors / advisor; `uncertainty` runs serially): limiting factors 4-5 s (thermal, SWIR) and 135 s (VIS); advisor sensitivities 4-5 s and 53 s; `analysis.uncertainty` 17-21 s and 243 s.
- **Agreement for smooth parameters.** advisor (±5 %) / uncertainty (±1 %) / this study (±10 %) elasticities for MWIR: D_mm 0.40/0.61/0.87 vs 0.41/0.58/0.93; σ -0.61/-0.29/-0.16 (advisor), -0.54/-0.29/-0.16 (uncertainty) vs -0.60/-0.28/-0.16; read noise -0.03/-0.04/-0.03 in all three; target H 0.17/0.36/0.42 vs 0.18/0.36/0.42. SWIR: D_mm, τ_opt, read noise, tint and V agree within 0.05. VIS: D_mm, τ_opt, V and Cn² (uncertainty -0.10/-0.12/-0.06 vs -0.10/-0.13/-0.06) agree within 0.04. ΔT differs slightly (0.15-0.17 vs 0.20 for MWIR Detection - curvature of the ±10 % step).
- **Disagreement for geometric parameters in sampling-limited systems** (the quantisation of Q4 item 4/5): SWIR target width with the 1 % step gives e_D = -1.10 (a wider target → shorter Detection) and height +1.62, vs +0.28 / +0.23 at ±10 %; VIS target width e_I = -0.15 (1 %) vs +0.41 (±10 %), height e_I = 0.83 vs 0.41; LWIR advisor gives f_mm e_R = 0.08 but D_mm e_R = 0.92 (±5 %), vs 0.86 and 0.13 at ±10 %; MWIR f_mm e_I = -0.23 (1 %) vs -0.04 (±10 %). (The advisor's pitch row uses the "ff2" policy, both axes + active size, so it is not comparable with the single-axis OAT pitch_h row.)
- `analysis.uncertainty` itself flags several of these as "asymmetric response … the linear RSS approximation is questionable; use Monte Carlo" (e.g. SWIR target width -10 %: -0.145 km, +10 %: +0.378 km). [SP/tools_comparison.txt]
- `analysis.limiting_factors` (gain when a degradation is removed, D/R/I): MWIR atmosphere +122/+40/+17 % (dominant), eye/display -0.7/+7.0/+9.1 %, pixel MTF +2.1/+5.3/+7.1 %, FPN +7.5/+8.5/+6.8 %, noise halved +3.1/+2.9/+2.7 %; LWIR pixel MTF +12/+13/+22 % (dominant; classified "sampling" for all tasks), atmosphere +4.6/+1.5/+0.8 %, noise halved +1.1/+1.2/+1.2 %; SWIR atmosphere +91/+21/+10 %, noise halved +27/+19/+12 %, eye/display +16/+16/+22 %; VIS atmosphere +62/+22/+8 %, turbulence +14/+20/+13 %, eye/display +5/+7/+31 %. These rankings agree with the OAT results (atmosphere for Detection, geometry/MTF for Identification, noise second-order except SWIR). The MWIR "ideal eye" case lowering Detection (-0.7 %) is another instance of Q4 item 4. [SP/tools_comparison.txt]

### Inferences
- A complete one-at-a-time scan over every numeric leaf (≈400 runs per system) takes ≈5 min per thermal system and ≈35 min for the turbulent Visible system on this 12-thread PC; any interactive sensitivity feature in the GUI should restrict itself to the ≈15-30 inputs that matter (Q1 list) and to ≥ 5 % steps.
- The 1 % step used by `analysis.uncertainty` lies inside the numerical noise found in Q4 (item 5) for sampling-limited systems; ±5-10 % steps are more robust. RSS uncertainty contributions from target size and focal length in the SWIR/VIS/LWIR cases are therefore unreliable (wrong sign possible); Monte Carlo or larger steps should be preferred there.
- The limiting-factor analysis is a cheap (≈5 s thermal) and robust first diagnosis that matches the OAT ranking. The advisor's fixed parameter list misses some parameters that matter in these runs: target width, the task criterion, display viewing distance and luminance, SNR threshold, path-radiance factor F_PR, PRNU/FPN fraction and (for MWIR) background temperature and the frame-rate/well-fill regime.

### Gaps
- Timing was measured on one Windows PC partly under load from another process pool; numbers are indicative only.

### Chart index (all PNG, 120-130 dpi)
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/tornado_MWIR_R0_D.png` - MWIR Blackbird XBn: top-16 OAT ±25 % effects on Detection range (good weather).
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/tornado_MWIR_R0_I.png` - MWIR: top-16 OAT ±25 % effects on Identification range (good weather); T_bg, task lp and D_mm lead.
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/tornado_MWIR_R1_I.png` - MWIR: Identification tornado in bad weather (σ = 1 /km); extinction dominates.
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/tornado_LWIR_R0_D.png` - LWIR uncooled: Detection tornado; task lp, focal length and target size lead, NETD near the bottom.
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/tornado_LWIR_R0_I.png` - LWIR uncooled: Identification tornado (sampling-limited; near-unit elasticities for f and target size).
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/tornado_LWIR_R1_I.png` - LWIR uncooled: Identification tornado in bad weather.
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/tornado_VIS_R0_D.png` - VIS daylight: Detection tornado; visual range and path radiance prominent.
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/tornado_VIS_R0_I.png` - VIS daylight: Identification tornado; task lp, focal length, target size lead.
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/tornado_VIS_R1_I.png` - VIS daylight: Identification tornado in bad weather (V = 5 km).
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/tornado_SWIR_R0_D.png` - SWIR night (full moon): Detection tornado; aperture, illumination/transmission/QE and read noise matter.
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/tornado_SWIR_R0_I.png` - SWIR night: Identification tornado.
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/tornado_SWIR_R1_I.png` - SWIR night: Identification tornado in bad weather.
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/sweeps_MWIR.png` - MWIR range vs F-number, pitch, focal length, NETD, read noise, frame rate, extinction, ΔT and jitter (solid = good, dashed = bad weather).
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/sweeps_LWIR.png` - LWIR uncooled range vs NETD, F-number (device vs F²-scaled NETD), pitch, focal length, frame rate, extinction, ΔT and display luminance (shows the luminance reversal of Q4 item 4).
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/sweeps_VIS_SWIR.png` - VIS range vs visual range, Cn², F-number, pitch, integration time, illumination; SWIR range vs read noise, illumination (plateau of Q4 item 4) and F-number.
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/heat_MWIR_F_pitch_I.png` - MWIR Identification range over F-number × pixel pitch at f = 300 mm (Fλ/d regime map).
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/heat_MWIR_F_pitch_D.png` - Same grid for Detection range.
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/heat_MWIR_NETD_sigma_D.png` - MWIR Detection range over measured NETD × extinction coefficient (noise vs weather).
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/heat_MWIR_NETD_sigma_I.png` - Same grid for Identification range.
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/heat_LWIR_NETD_f_I.png` - LWIR uncooled Identification range over NETD × focal length (F/1 kept).
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/heat_VIS_Cn2_F_I.png` - VIS Identification range over Cn² × F-number (turbulence × aperture).
- `C:/Users/ramih/AppData/Local/Temp/claude/C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa/acff95aa-b3cc-43e6-8d65-31aa7be98ad5/scratchpad/sensitivity/charts/heat_VIS_Cn2_F_D.png` - Same grid for Detection range.
