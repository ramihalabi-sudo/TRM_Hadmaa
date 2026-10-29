# TRM_HADMAAv1 – Thermal Range Model (Python implementation of TRM4.v3)

Implementation of the model described in *"TRM4.v3 – Parameter Description and Model
Documentation"* (Fraunhofer IOSB Technical Report 2021/04), with a desktop GUI.

## Run

```
TRM_HADMAAv1.lnk / .pyw / .bat     (double-click)               -> GUI, no console window
python run_trm4.py                                              -> GUI (from a console)
python run_trm4.py --list                                       -> list templates
python run_trm4.py --cli 0 --out report.txt                     -> batch run of template 0
python run_trm4.py --cli myproject.json                         -> batch run of a saved project
```

Requirements: Python 3 with `numpy`, `matplotlib`, `tkinter` (all already present on this PC).

```
python run_trm4.py --cli 0 --limiting --uncertainty --out report.txt   -> batch run incl. analyses
python -m unittest discover -s tests                                   -> regression / acceptance tests
python run_trm4.py --cli 0 --pdf-he report.pdf                         -> Hebrew DRI report (PDF, runs the advisor)
```

### Hebrew DRI report (PDF)

*File > Export Hebrew DRI report (PDF)...* (or *Hebrew PDF report...* on the Sensitivity tab, `--pdf-he` on the
command line) writes a right-to-left scholarly report in Hebrew, structured like
"TRM_Range_Improvement_Advisor_Scientific_RTL_Hebrew.pdf": title page, abstract with the key finding, table of
contents, baseline snapshot, DRI results (ranges, pixels / cycles on target, MTF, CNR, limiter, range-vs-threshold
figure), bottleneck diagnosis and limiting factors, normalized sensitivities, all what-if actions, decision cards
of the top 3 recommendations (before / after per task, evidence level, trade-offs, robustness, validation method),
guidance per bottleneck type, *measure first*, limitations, model warnings and bibliography. The advisor result
of the Sensitivity tab is reused when it matches the current inputs, otherwise the advisor is run first.
Implemented in `trm4/report_he.py` with matplotlib only (own bidi / RTL layout; Hebrew in Frank Ruehl / David,
Latin and numbers in Times New Roman, headings in Arial, DejaVu fallback).

Run time: the advisor's ~60 independent model runs go to a process pool (`analysis.Runner`, cores - 1 workers,
max. 8, `TRM4_WORKERS` overrides; identical results to a serial run), and the AMOP wiggle removal is O(n log n)
instead of O(n^2) (same merges, `tests/test_performance.py`). Typical advisor times: LWIR / SWIR templates
~20 s (was ~85 s), daylight CMOS template with turbulence ~5 min (was over an hour). While the advisor runs for
the report, the Sensitivity tab shows the progress, elapsed time and *Stop*.

### Detector Atlas news

The Detectors_Atlas GitHub repository runs a watcher every 6 h that scans manufacturer catalogs and records
newly detected listings as events in `data/live.json`. TRM reads that feed (GitHub Pages, then raw GitHub, then
the local copy in `detector_lookup_HTML/`) a few seconds after start-up and every hour while it is open
(`trm4/atlas_news.py`). New detectors open the *Detector Atlas news* window and the menu shows *News (n new)*.
*Close* keeps an item unread (it is shown again at the next start); *Mark as read* / *Mark all as read* hide it for
good (ids stored under `atlas_news` in `%APPDATA%\TRM4\settings.json`). *News > Detector Atlas news...* reopens the
window, including already-read items.

## Version 2.6 - roadmap phase 3: extensions beyond TRM4 (reports/)

TRM4 is line-pair deterministic: one range per task criterion, no probability, no clutter, no meteorological
extinction, no turbulence in the Thermal category and no machine observer. The ten capabilities of the report's
phase 3 are added as **extensions** (`trm4/extensions.py`, each with its source and limits of validity). Every one
is off by default or an extra output next to the TRM4 result, so the template DRI ranges are unchanged (engine
version 2.6). The Summary, the text and Hebrew reports and the DRI context list the extensions in use.

| Capability | Implementation | Source / limits |
|---|---|---|
| P50 / P80 / P90 | The TRM4 criterion is the 50 % value N50; the P80 / P90 ranges use N50 x 1.45 / x 1.75 (Johnson / Lawson TTPF, *Also report P80 / P90 ranges*, on by default). Shown on the Summary cards, in System data and both reports. Where the range is resolution-limited R90 = 0.57 R50 (LWIR Identification 1.735 -> 0.998 km). | Sandia SAND2015-6368; not a TRM4 output, the observer scatter is not modelled |
| Range bands | Sensitivity tab *Range bands*: every active atmosphere x Cn2 / 10, nominal, x 10 (r0 scaled by 10^-+3/5 in the r0 mode); cards, band chart, table, CSV, report. Daylight template: Detection 5.4 - 16.5 km around 14.7 km. | Scenario envelope, not a probability interval |
| Clutter | *Clutter raises the Detection criterion*: ACQUIRE-LC factor C [(C/dT)^2 + 1] / [(1/dT)^2 + 1], C = 1 / 1.5 / 2 / 2.7 (6.1 for high clutter at dT = 2 K); C outside the Thermal category. Acts on the first task (Detection) only and is capped at the Recognition criterion. The clutter level moved from *Metadata* to *Target & scenario*. | The entered criterion is taken as the low-clutter value; dT_RSS approximated by dT |
| Extinction from the weather | Atmosphere mode *Visual range + humidity + air temperature*: spectral extinction = aerosol (3.912 / V)(lambda / 0.55)^-q (Kruse; Kim et al. below 6 km) + water-vapour continuum 8-14 um (Roberts, Selby & Biberman 1976), Beer-Lambert per wavelength. LWIR at 15 C / 50 %: 0.044 /km; 30 C / 80 %: 0.47 /km at 10 um. New input *relative humidity* per slot (also an uncertainty and advisor input). | No gas-line absorption: a lower bound in clear air; MWIR is aerosol only and warned; fog below 1 km warned |
| Turbulence in the Thermal category | *Apply turbulence in the Thermal category*: MTDP_R = MTDP_0 AMOP_0 / AMOP_R with AMOP simulated at 9 ranges. MWIR: Cn2 1e-14 Detection -4 %, 1e-13 Detection -21 %, Identification -7 % (run ~2.6 s). | TRM4 neglects it by design (Sec. 2.28) |
| Jitter | Preset *Typical residual LOS jitter, 70 urad rms* (US Army NV-IPM practice). Without jitter, an assumption flags fields of view where 70 urad exceeds 1/3 IFOV. The template defaults stay 0. | NV-IPM practice value; Gaussian MTF valid below ~1/3 IFOV |
| Scan smear | Smear of the linear motion per thermal time constant (microbolometer) or integration time in pixels: System data, derived panel, warning above 1 pixel (uncooled, 10 deg/s: 5.1 pixels). The first-order smear MTF was already applied. | - |
| Algorithm observer | *Algorithm task criterion*: TRM4 line pairs (uncalibrated, as before) or **pixels on target + pixel CNR**: 60 / 250 / 350 pixels on the projected area per task, pixel CNR of the processed frame >= 3; the shorter range counts and its limit is named. LWIR: Detection 1.98 km (human 9.13 km, uncalibrated line-pair algorithm 16.4 km). | Holst & Mahalanobis 2023; thresholds generic until calibrated |
| Global sensitivity | Uncertainty methods *Global: Morris screening* (r trajectories, mu* / sigma per task) and *Global: Sobol indices* (S_i Saltelli 2010, S_Ti Jansen 1999, 95 % bootstrap) over the stated +/- intervals (uniform), with a run cache and the process pool. MWIR, 15 inputs, r = 6: 94 runs, 15 s. | Estimators checked against an analytic function |
| Compression, turbulence mitigation | Lossy compression as an equivalent Gaussian blur in pixels on the digital frame (*Signal processing*, moved from *Metadata*); daylight template 0.5 px: Recognition -19 %. Mitigation as an effective r0 gain: x2 / x3 give Recognition +12 / +16 % (published +10 to +25 %). | O'Shea et al. 2008; empirical, to be fitted to the codec / processing |

The P80 / P90 ranges roughly double the run time of a Visible run with turbulence (1.7 -> 3.2 s); the analyses
(sweeps, uncertainty, advisor, bands) skip them (`analysis.fast`). Not done: gas-line absorption in the weather
mode, aerosol MTF, a TTP / V50 path and a geometric quick mode (report phase 3 items outside the roadmap list).
`tests/test_extensions.py` covers these items; `tests/test_gui_layout.py` the new inputs.

## Version 2.5 - corrections from the parameter-sensitivity study (reports/)

A one-at-a-time and 2-D sensitivity study over four representative systems (about 2,500 runs) found results
that contradict simple physical expectations. They are corrected in the engine (engine version 2.5):

| Finding | Correction |
|---|---|
| Cooled thermal with optics transmission, QE scale or integration time 0 crashed (ZeroDivisionError) | Rejected with a `ModelError` (dN/dT = 0); electron gain must be > 0. |
| Visible / General with turbulence: no Detection range for large targets or long focal lengths | At bar frequencies below the AMOP band the 4-bar pattern did not fit the simulation window (AMOP = 0). The band's lowest frequency is used there, as in the tabulated path. |
| More linear motion blur gave a longer range (e.g. 20 -> 35 mrad/s: Recognition +70 %) | Bar frequencies above the first zero of the signed motion MTF (sinc / J0 / frame integration) are contrast-reversed (spurious resolution) and are no longer credited; the zero is listed under assumptions. |
| A darker display, a longer viewing distance or a higher NETD could lengthen the range; ranges showed plateaus | The resolution limit (first AMOP <= 0.1 %) was found only to the 8 % step of the 70-point frequency grid. It is now refined by bisection, so the limiting frequency varies continuously. |

Consistency and transparency (first batch of the report's phase 1):

| Item | Change |
|---|---|
| Physical bounds | Target W, H > 0, D >= 0; T_bg > 0; threshold SNR and eye integration time > 0; q >= 1; CTE, duty cycle in (0, 1]; well fill in (0, 100] %; Cn2 >= 0; path radiance factor >= 0 - otherwise a `ModelError` (before: parsed as numbers only). |
| "No range" convention | Visible / General report `None` ("< first range") when the task fails already at the first range, as Thermal does (before: 0.01 km). Analyses and advisor share `analysis.task_ranges()` (analyses: first range; advisor: 0, no percentage gain). |
| NIIRS | Ticking *Calculate NIIRS* no longer switches the DRI ranges to still-frame noise; Still is used for the NIIRS curves only (TRM4 Sec. 2). |
| Uncertainty derivative step | Default 5 % instead of 1 % (1 % lies inside the grid quantisation and gave wrong signs); the step is clipped to the input's valid interval and the actual step is used. |
| Detector Atlas | The FPA operating temperature goes to *Sensor operating temperature* (not the cold shield temperature); the active size follows the pitch (100 % fill, editable); the maximum frame rate is offered but not ticked. |
| F lambda / d indicator | Summary card and System data: F lambda / d with the signal-weighted mean wavelength and the effective pitch, the regime (detector-limited < 1, balanced 1-2, optics-limited >= 2) and the hardware lever in that regime. |
| Generic defaults | Read noise and ADC step equal to the generic defaults (500 e-, 1000 e-) are listed under assumptions unless their provenance is a datasheet / measurement. |
| Single-wavelength diffraction | *Wavelength for diffraction* 0 (new default) = the signal-weighted mean wavelength of the band, instead of a fixed 10 um that was wrong for VIS / SWIR / MWIR. Templates and saved projects keep their explicit values. |
| Turbulence run time | A Visible run with turbulence takes about 2 s (before: 6 s, 21 s for large targets) - a consequence of the low-frequency AMOP fix above, which no longer simulates oversized bar patterns. |
| Measured NETD - not converted (decision) | Considered and kept as is: a measured NETD whose F-number, integration time or frame averaging differ from the scenario is used unchanged and flagged in the warnings (DS-03, no false precision; TRM4 does not scale a *Device measured* NETD). For a scaled value use *Detector measured* or *Calculate*. |

`tests/test_consistency.py` covers these items.

Analyses and advisor (rest of the report's phase 1, first part of phase 2 - no change of the template ranges):

| Item | Change |
|---|---|
| Atmosphere of the analyses | *Atmosphere* selector on the Sensitivity tab: sweeps, uncertainty, limiting factors and the advisor evaluate the chosen active atmosphere (`analysis_atm` in the project; default the first active slot). Before: always the first result and always slot 1's extinction input - with slot 1 switched off that input had no effect. |
| Advisor: actions | New *Better non-uniformity correction* (residual FPN x0.5; estimate-based FPN = approximate evidence) and *Display*: closer viewing distance / shorter eyepiece focal length, brighter display below 100 cd/m2 (operational, observer constants flagged). |
| Advisor: sensitivities | Added target width, background temperature, path radiance factor (not Thermal), the cycle criterion of every task, threshold SNR and the FPN fraction - assumptions next to the hardware levers. |
| Advisor: weather | One model run computes all active atmospheres, so every action reports its gain per atmosphere at no extra cost; the report names the best action per atmosphere and flags when it changes materially with the weather (near ties are not flagged). |
| Advisor: measure first | Generic task criterion and generic observer constants (threshold SNR, eye integration time) are listed. |
| Uncertainty inputs | Added aperture diameter (or F-number), pixel pitch (both axes, constant fill factor), the criterion of each task (+/-25 %, Johnson 1958 scatter), threshold SNR (+/-20 %) and eye integration time (+/-25 %, video only). Projects with stored uncertainty settings keep them; new inputs start unticked there. |
| Sweep list | The task criteria can be swept; inputs that only feed checks, the exposure budget or the system data (`analysis.NO_RANGE_EFFECT`) are no longer offered. |
| Turbulence diagnostics | System data: r0, D/r0 and lambda/r0 in IFOV units at the reference range, or at the range of the most demanding task when no reference range is set. |
| Help texts | The 38 input fields without help (timing, exposure budget, capacity node, dark-current table, outer scale, metadata) now have one; a test keeps every GUI field documented. |

`tests/test_analysis_scope.py` covers these items.

Input layout (roadmap phase 2 - the calculation and the template ranges are unchanged; every template loads into the
form and is collected back without a difference):

| Item | Change |
|---|---|
| Metadata page | New page for traceability only: description of the imported optics MTF and atmosphere, sensor operating mode, NETD test state, ROI, processing pipeline, algorithm ID / ROC definition and scene ID (24 fields in 2.5, before spread over 7 pages; clutter and compression act on the ranges since 2.6 and moved to the pages they act on). The original places point to it. |
| One entry per pixel pair | *Square pixels* (Detector geometry): one entry for pitch and active size; the vertical values follow. Set from the values whenever a project, template, profile or datasheet is loaded, so rectangular pixels keep their vertical values. GUI state only - the engine reads the h / v values. |
| Active values not hidden | The fixed pattern noise group opens when FPN is estimated (it acts on the ranges), the ADC group whenever an ADC step is set, the read noise is a base input for photon detectors, threshold SNR and eye integration time are shown as *observer calibration constants*. |
| Checks and overrides out of the way | Measured-FOV cross-check is advanced, CCD charge transfer is legacy (shown only while used), *Neglect eye MTF* only in laboratory mode (or while ticked), target depth only for side / diagonal aspect or an oblique line of sight. |
| Labels | Detector count "sets the FOV, not the resolution"; zoom and line / column replication "add no information"; help for reference range (it can change the ranges, not only the plots) and target altitude (turbulence path height only) corrected. |
| Merged counterparts | The derived-value panel shows the counterpart of each principal entry: signal throughput tau_opt x tau_filter x QE scale, extinction <-> visual range (Visible), integration time in duty mode, system magnification M with the eye MTF at Nyquist (warning below 0.2), random jitter in urad and IFOV units (warning above 1/3), dark current in e-/s and nA/cm2. |

Not changed on purpose: a selected integration time longer than the frame / timing / hardware limit is flagged in the
exposure budget, not clipped (research review spec Sec. 7.3, `test_rr43_timing_violation_reported`). The six
illumination definitions and the remaining H / V pairs of the motion inputs stay as they are.
`tests/test_gui_layout.py` covers the layout.

The template DRI values are unchanged except *General - MWIR sun-lit scene*, Atm 1: Recognition 7.628 -> 7.557 km,
Identification 3.983 -> 3.511 km. A 2,800-point frequency grid gives 7.558 / 3.511 km, i.e. the previous values
were a grid artefact. `tests/test_invariants.py` checks that more motion, a darker display or a higher NETD never
lengthen a range, that zero throughput is rejected and that turbulence keeps the Detection range of large targets.

## Version 2.4 - changes from "TRM4v3_Research_Improvements_English.pdf"

The review keeps TRM4's physics and asks for correct input semantics, operating-point consistency and
traceability. Items the application already had (MTF component coverage / no double diffraction, required MTF
frequency unit, spectral L_sensor = tau L + L_path, imported path radiance, measured SFR and aliasing, pipeline
documentation, observer types, run ID / scenario record, Monte Carlo percentiles, separate NIIRS) are unchanged.
New inputs default to the previous behaviour, so the template DRI values are unchanged (only checks and reports
are added). Engine version 2.4.

| Review item | Implementation |
|---|---|
| 3.5 / 7.2 QE basis (critical) | *QE refers to*: not stated (TRM active-area convention) / active area / full pixel area (total or EMVA 1288 QE). With *full pixel area* the photon -> carrier conversion uses the pixel area and the fill factor is not applied again (active size only for the detector MTF). Not stated + fill factor < 1 is an assumption, or a warning when the QE comes from a datasheet / measurement. |
| 3.6 / 3.7 / 7.1 Saturation capacity (critical) | *Capacity above refers to* (physical full well / ROIC node / camera saturation / not stated), optional *input-referred camera saturation capacity*, and the ADC full scale: the smallest is the **usable capacity** that the well fill and the well-fill exposure use. An unverified capacity is flagged (warning when the exposure is chosen from it). *Operating mode* text ties capacity, read noise and dark current to one gain / readout / temperature mode. |
| 3.7 / 7.3 Brightest pixel | Well fill is also checked for the brightest credible scene pixel (reflectivity 0.9 / +30 K by default, editable); saturation is reported. 70 % is a design margin input, not a rule. |
| 3.1 / 3.8 Operating mode and timing | Exposure overlap with readout, readout and guard time, hardware min / max exposure, ROI; *charge* vs *digital* binning (digital adds the read noise of every summed read-out). The timing limit is reported separately from the saturation and motion limits. |
| 4.3 / 7.3 Exposure budget | t_int <= min(t_sat, t_timing, t_motion, t_hardware) with t_motion = allowed smear x IFOV / image velocity, and SNR(t) >= required SNR (optional). Violations at the selected time and infeasible combinations are warned; shown on Summary, in the report and the scenario record. |
| 4.1 / 3.9 Radiometry bookkeeping | Background photon arrival rate and photoelectron rate per pixel (photons/s, e-/s); field-edge rate with a relative-illumination input; sub-pixel target warning (target smaller than the pixel / diffraction blur at a task range). |
| 3.11 Dark current vs temperature | *Calibrated table* I_dark(T_sensor), log-linear interpolation, warning outside the table (no generic doubling rule). |
| 3.10 / 7.5 Noise port, 3.12 bolometers | Measured camera NETD port (RAW / after NUC / processed video; processed is flagged as possible double counting). Microbolometers: explicit note that no full-well model is applied and the time constant is not an exposure. |
| 3.3 / 3.21 / 7.4 MTF metadata | Band, focus, temperature and uncertainty of imported MTF data; incomplete metadata is listed. |
| 3.18 / 7.6 Atmosphere versioning | Spectroscopy database edition (e.g. HITRAN2024), RT code / version, profile, aerosol, resolution for imported spectral data. |
| 3.20 Turbulence | Optional von Karman outer scale L0 (first-order structure-function correction). |
| 3.24 Preset lifecycle | Every preset in use is reported with source, date, applicability, uncertainty, warning and data version. |
| 3.22 / 7.7 DRI context | Every range is reported with task, target geometry, operating point (incl. capacity basis and QE basis), scene / atmosphere, MTF source, observer, uncertainty and validation status, and "a nominal range is not an assured operational outcome". |
| Sec. 5 Test metadata | Validation metadata adds firmware, gain / readout mode, frame rate, ROI, exposure, F-number, RAW file references and calibration IDs. |
| Tests | `tests/test_research_review.py`: the Sec. 4.4 SWIR worked example through the engine (5.16e7 photons/s, 41.28 % at 10 ms, 16.96 ms to 70 %), QE basis, capacity limits, timing, motion / SNR / infeasible budget, brightest pixel, dark table, digital binning, noise port, presets, atmosphere versioning, DRI context, outer scale. |

Not implemented (laboratory / research work in the review): observer trials and success probabilities, BRDF and
spectral reflectance import, nonlinear (HDR / learned) processing profiles, measured slant-path Cn2 profiles,
and the Sec. 5 bench tests themselves.

## Version 2.3 - changes from "TRM_Range_Improvement_Advisor_Scientific_RTL_Hebrew.pdf"

New *Sensitivity > Improve performance* mode (also *Run > Improve performance (advisor)*, `--advisor [--min-fov DEG]`
on the command line), implemented in `trm4/advisor.py`. It is advisory only: the project is never modified and the
existing *Calculate* flow is unchanged (T-01).

| Report item | Implementation |
|---|---|
| Ch. 2.1 Baseline snapshot | `baseline_id` + deterministic run ID, model version, inputs, ranges, geometry, time. |
| Ch. 2.2 / 2.3 Delta and evidence | Delta_R = R(x_a) - R(x_0) and Gain % per task through the same engine, target and environment; no % when R_0 = 0 (T-03); every action is labelled *Model-supported*, *Approximate estimate* or *Measure first*. |
| Ch. 4 Bottleneck diagnosis | Per task a *bottleneck candidate* (angular sampling, optical MTF, SNR/contrast, environment, motion, observer) with the reason (cycles vs Nyquist, CNR, largest limiting-factor gain) and the separation test of the report's table. |
| Ch. 5.1 / 6 Consistent actions | Longer lens at the same F-number (f and D together) or same aperture, faster optics, a complete smaller-pitch detector at the same FOV (flagged *incomplete simulation*, T-06), more pixels (shows FOV, not IFOV, changes), lower NETD / read noise, frame rate / integration time (conditional, T-07), transmission, diffraction-limited optics, stabilization; clearer atmosphere only as a *scenario* (T-08). Each case is validated before the run. |
| Ch. 5.2 Sensitivities | S_i = (x_i / R) dR/dx_i by central differences (+/-5 %), zero-effect inputs flagged as a possible model limitation. |
| Ch. 5.3 / 8.1 Ranking and cards | Top 3 materially different actions (one per group) for the chosen task, inside a minimum-FOV constraint (T-09); Pareto flag on gain vs FOV; before/after, trade-offs (FOV, F-number, mass), evidence and notes per action. |
| Ch. 5.4 Uncertainty | Paired robustness: base and action recalculated on the same low/high values of the main assumptions (atmosphere, target) - a range of Delta_R, no invented confidence. |
| Ch. 8 usability rule | *Measure first* list (theoretical MTF, calculated NETD, generic QE, preset target / atmosphere, no LOS motion) with the measurement to make. |
| App. A tests | `tests/test_advisor.py`: T-01, T-02, T-03, T-06 ... T-10, consistent lens change, pixel count vs IFOV, distinct top 3, report / CSV. |

## Version 2.2 - changes from "TRM_Imaging_Research_Engineering_Field_Map_HE_v1_1.pdf"

The field map (Ch. 12-15) asks for a reproducible measurement chain *behind* the existing screens, not for new
screens or a "Sharpness" factor. No sidebar page was added or renamed; new inputs sit inside the existing pages
(mostly under *Show advanced parameters*). Johnson/TRM4 legacy criteria stay the default and the template DRI
values are unchanged (V-06).

| Field map item | Implementation |
|---|---|
| 15.4 Source-of-truth matrix / no double counting | Every chain component (`optics, diffraction, detector_aperture, electronics, processing, motion, turbulence, atmosphere_radiometry, path_radiance`) comes from exactly one source; `check_coverage` rejects overlaps (`ModelCoverageError`). The resolved coverage table is shown in Messages, the report and the scenario record. |
| 15.2.4 Optics (P0) | *Optical MTF source*: Theoretical / Zemax CSV / **Measured lens MTF** / measured device prefilter (end-to-end). Coverage flags for imported data: *includes diffraction* (else the computed diffraction MTF is applied once), *includes detector aperture*, *includes motion*. A file without a stated frequency unit is rejected instead of guessed (V-05); single-field data are flagged as not representing off-axis performance. |
| 15.2.5 Detector geometry | Read-only IFOV = p/f, Nyquist = 1/(2p) [cy/mm], angular Nyquist = f/(2000p) [cy/mrad]; note that IFOV is not a PSF. Aliasing risk (presampled MTF at Nyquist + in-band spurious response) on the Summary and MTF plot. |
| 15.2.6 Detector sensitivity (P0-P1) | *Noise / sensitivity source*: Physics model / Measured camera NETD / detector-level NETD. Camera NETD test conditions (F-number, integration time, frames averaged, gain/NUC); mismatches are flagged, never silently converted; missing conditions mark the noise as *partial*. Measured NPS import as a white-noise quality check (not used for ranges). |
| 15.2.3 Basic imager | Global / rolling shutter with readout time; rolling-shutter geometric distortion reported (not blur). Motion model is linked to the exposure (integration time). |
| 15.2.7 Signal processing (SP-01) | A sharpening filter (boost > 1) is **not credited** in the ranges unless *Credit sharpening* is ticked. Pipeline documentation (denoise, compression, step order, algorithm version); unmodelled steps are listed as assumptions. Measured SFR50 and SFR > 1 overshoot in Validation. |
| 15.2.8 Display & observer | *Observer*: Legacy-neutral / Human / Algorithm. Algorithm = no display/eye MTF, no eye integration, result labelled *Uncalibrated estimate* (calibration set, ROC definition recorded). |
| 15.2.9 Stabilization & MTFs (P0) | *Motion source*: None / RMS-jitter assumption / time series / **angular PSD** (urad^2/Hz, mrad^2/Hz, pixel^2/Hz) split into intra-frame blur and frame-to-frame jitter by the exposure window; residual-LOS flag; motion contained in an imported MTF is not applied again. |
| 15.2.10 Target & scenario | Versioned *criteria preset* (TRM4 legacy 1/3/6 default, 1/4/8, Johnson 1958 1/4/6.4, target model, custom); clutter level and scene ID documented (not modelled). |
| 15.2.11 Irradiance | L_sensor = tau L_scene + L_path kept spectral; band radiances at the aperture, target/background mean signal in e- and DN, low-signal (read-noise limited) warning; illumination-at-target assumption avoids double attenuation. |
| 15.2.12 Atmosphere & turbulence | Documentation of imported atmospheric data (geometry, generating model, conditions); turbulence from **r0 with its reference wavelength and path length** (rejected without them). |
| 12.7 / 15.3 Results | One diagnostic row per D/R/I: Pixels / Cycles / MTF @ task frequency / CNR / indicative limiter (double-click for the explanation), plus Model, Calibration status, Confidence method and Input provenance. No probability is claimed. |
| 12.1 / 12.8 / App. D Traceability | Deterministic **run ID** (inputs + model version), separate model and validation versions, *File > Export scenario record (JSON)* / `--scenario` with the Sec. 12.8 schema. Camera profiles carry profile_id, schema_version, channel, source_id, calibration_date, file hashes and a content hash (CP-01). Lab: measured data of another configuration are flagged. |
| 13.2 / App. C tests | `tests/test_field_map.py` (34 tests): V-01...V-08, CP-01, GE-01, BI-01, OP-01...03, DG-01, DS-01...03, SP-01, DO-01, ST-01...03, TS-01, IR-01, AT-01/03, run ID, auditability. |

Not implemented (the document marks these as research / P2 or outside the app): TTP/TOD research comparison,
calibrated detection probabilities, NPS-driven noise model, replacing the prediction by a measured end-to-end SFR
(it remains a comparison in Validation), clutter modelling.

## Version 2.1 - changes from "Sensitivity_Analysis_Improvements.pdf"

| Plan item | Implementation (Sensitivity tab, `trm4/analysis.py`) |
|---|---|
| P0 Uncertainty semantics | Per input: +/- value, what it means (limits / 95 % interval / 1 sigma) and distribution (normal, uniform, triangular, lognormal) -> standard uncertainty. Three outputs that are never mixed: **one-at-a-time** range changes (tornado, labelled "not a probability interval"), **RSS** combined standard uncertainty u(R) = sqrt(c' R c) with local sensitivities (central differences) and correlations, expanded U = k u, and **Monte Carlo** percentiles with stated coverage, sample count and fixed seed. The words "credible interval" are gone. Asymmetric (nonlinear) responses and very large perturbations are flagged. |
| P0 Plot/result state by mode | Every mode keeps its own result; a mode without a result shows "No ... result yet". A result whose inputs changed shows a "Results not updated" banner. Run history (last 30 runs) can be recalled. Stop button; Reset per mode. Analyses that are stale are not put into the report. |
| P0 Full recomputation + dependency validation | Engine contract: clone -> apply hold-constant policy -> validate (impossible F-number, active size > pitch, ...) -> full model run -> save D/R/I + diagnostics. Policies: detector pitch (both axes / one axis, constant fill factor, keep active size, keep FOV), focal length (keep D or keep F#); notes when a measured NETD stays constant or an input has no effect. |
| P1 Sweep curves, table, baseline | DRI vs parameter with baseline marker, rejected points marked, linear/log sampling, units, engine mode and hold-constant assumptions; table with value, D/R/I, % delta, validity and diagnostics. |
| P1 Interactive tornado, rankings | Outcome selector D/R/I, delta or absolute km view, sort by max range effect / normalized sensitivity (%/%) / uncertainty contribution, neutral "input decreased / increased" colours, "below display resolution" label, click a bar for baseline, low/high input and recomputed D/R/I with deltas. "Calculation details" answers the three questions (largest effect, largest uncertainty contribution, highest sensitivity). |
| P1 Cards and export | Result cards per task (nominal + method-labelled interval / sweep span), method line, *Calculation details* tab, CSV export of every analysis, analyses in the text report. |
| P2 Monte Carlo + correlations | Gaussian-copula sampling with a correlation list (linked inputs), reproducible with the seed; histogram with percentiles. |
| P2 2-D grid, scenarios | Heatmap for two parameters (same-quantity pairs rejected, invalid cells marked); scenario comparison of saved configurations (stored in the project) with deltas. |
| Verification (6.2) | `tests/test_analysis.py`: zero perturbation reproduces the nominal DRI exactly, linear toy model = RSS theory (incl. rho = +/-1), MC std = RSS, fixed seed reproducible, nonlinear asymmetry flagged, sign/direction (more extinction -> shorter range), repeated sweep points identical, dependency policies, invalid points rejected, 2-D grid behaviour. |

## Version 2.0 - changes from "TRM4_Application_Changes.pdf" (roadmap P0, P1 and core P2)

| Roadmap item | Implementation |
|---|---|
| Three workflows (Sec. 01/05) | Sidebar switch **Quick / Engineering / Lab** (also *Workflow* menu, Ctrl+Shift+1/2/3). Quick Prediction shows one *Quick setup* page (camera profile, target, signature, illumination, atmosphere preset, tasks, lab/field, still/video) and only Summary / Range / Messages. Engineering shows all parameter pages and engineering views. Lab adds the *Validation data* page and *Validation* results tab. |
| KEEP / SIMPLIFY / ADVANCED / REMOVE (Sec. 02-04) | Every parameter group has a level. ADVANCED groups (pupil obscuration, micro-scan, binning, CTE, crosstalk, charge-based noise sources, ADC, cold shield, FPN, digital filters, zoom, display panel, observer overrides, 3D geometry, NIIRS, additional MTFs) are shown with *Show advanced parameters* - or automatically while the feature is in use. REMOVE items (electronic/pseudo interlace) are only shown while an old project still uses them. The physics stays in the engine. |
| Camera profiles (Sec. 02/05, P0) | *Camera profile* page: built-in generic profiles (from the templates, incl. a dual-FOV example) and user profiles (`profiles/*.json`) with several optical configurations (zoom / FOV). Apply, save the current camera as a profile, add the current optics as a configuration, delete. |
| Automatic calculations (Sec. 05) | Read-only panel on the Quick setup, Camera profile, Basic imager, Optics and Detector geometry pages: FOV, IFOV, sampling, Nyquist (object and focal plane), samples, fill factor, effective F-number or aperture (one principal entry), Q = lambda F / p, diffraction cut-off, frame interval, max. integration time, duty cycle - updated live, with warnings for inconsistent redundant inputs (measured FOV, manufacturer F-number, impossible F#, active size > pitch, display too small, band/category mismatch). |
| Data provenance (Sec. 05/07) | Small source badge next to every value (preset, assumed, user, datasheet, measured, import, profile); click to change. Values typed by the user, applied from a profile, from *Detector lookup* (datasheet) or imported are marked automatically. Stored in the project and listed in the report. |
| Optics data precedence (Sec. 06-A) | *Optics MTF from*: **A** computed, **B** imported optics MTF (replaces diffraction + aberration, never diffracted twice), **C** imported device prefilter MTF (optics, detector, pre-sampling submodels bypassed). |
| Import contracts (Sec. 06-B) | MTF: frequency unit (auto / cycles/mm / cycles/mrad), axis (sagittal/tangential -> h/v), field, metadata text; checks for MTF > 1, MTF(0) != 1, data ending below Nyquist. Transmission: absolute or normalized, optics-only or full system (filter then not applied twice), range [0,1]. QE: % or fraction, um or nm. Every import is recorded with its SHA-256 hash. |
| Detector chain (Sec. 07) | NETD test temperature with extrapolation warning; saturation (full well) and ADC clipping checks (new *ADC bits*); low-SNR / no-contrast diagnostics; FPN estimate listed as assumption. Frame interval and integration time reported separately. |
| Atmosphere (Sec. 08) | Fast mode with clear / average / adverse presets per band (labelled assumptions) or user extinction; **spectral import** (wavelength x range table or one column + path length, Beer-Lambert per wavelength); **path radiance** modelled or imported independently of the transmittance; warning when visual range is used outside the Visible category; effective transmission vs range plot. |
| Turbulence / stabilization (Sec. 08) | Cn2 scenario defaults from Table C.2; **measured jitter time series** (t h v or h v + rate, urad / mrad / pixels): offset and drift removed and reported, intra-frame blur from the measured motion, frame-to-frame jitter in video mode. |
| Results dashboard (Sec. 09) | D/R/I ranges, target pixels and cycles at Nyquist at each task range (sampling-limited flag), MTF50 and MTF at Nyquist, CNR, dominant limiting factor, key inputs by data source, assumptions, nominal-prediction label or uncertainty interval, diagnostics. |
| Sensitivity / P2 (Sec. 09/11) | *Sensitivity* tab: **limiting factors** (each degradation removed in turn), **parameter sweep** (DRI vs any numeric input), **uncertainty** (one-at-a-time with stated +/- %, tornado chart, RSS interval). No invented confidence score. |
| Validation (Sec. 07/10) | *Validation data*: measured MTDP / MRTD / MCP (compare or replace the modelled MTDP for ranges), measured MTF / SFR (device or delivered image), measured NETD, calibration metadata. *Validation* tab plots measured vs predicted with deviations; lab-vs-field and NETD-temperature mismatches are flagged. |
| Traceability (Sec. 10) | Report sections: traceability (model version, time, profile, imports + hashes), key inputs with sources, assumptions, DRI summary, analyses, validation. |
| Verification plan (Sec. 10) | `tests/` - 57 unittest checks: geometry, sampling/binning, diffraction-limited MTF, no re-diffraction of imported MTF, device-prefilter bypass, absolute/normalized transmission, Beer-Lambert, spectral = fast mode for a grey atmosphere, path radiance, shot/read/dark/quantization noise, saturation and ADC clipping, measured NETD/MTDP, zero/non-zero jitter, turbulence, template DRI reference values (0.5 %), edge cases, provenance, profiles, analyses. |

Not part of this change package (as stated in the roadmap or deferred): new/adaptive Johnson criteria or
learned thresholds; the laboratory frame/video tools (flat-field, dark-frame and test-video analysis,
slanted-edge SFR computed from images, automatic metadata matching); Monte Carlo uncertainty; legacy
scanners, intensifiers, CRT / analog video. Fix included: for Visible/General imagers a task whose bar
pattern exceeds the resolution limit inside the range grid was reported as "> 100 km"; it now ends at the
resolution-limited range (none of the templates were affected).

## GUI

* Window: splash screen, application icon (also in the taskbar), menu bar, toolbar with tooltips,
  status bar (status, category/mode, file, progress), sharp text on high-DPI screens. Window size,
  last parameter page and recent files are remembered in `%APPDATA%\TRM4\settings.json`.
* Sidebar + parameter page: the parameter dialogs follow the TRM4 *Modify Individual Parameters* dialog
  (General, Basic imager, Optics, Detector geometry/sensitivity, Signal processing, Display & observer,
  Stabilization & additional MTFs, Target & scenario, Irradiance, Atmosphere & turbulence).
  Fields appear/disappear depending on category and options.
* Projects behave like documents: the title shows the file name and `*` when there are unsaved changes,
  and you are asked to save before closing, opening another project or starting a new one.
* File menu: New / New from template, Open, Open recent, Save (Ctrl+S), Save as, Export report (Ctrl+E),
  Export current plot as PNG/PDF/SVG (Ctrl+P). Run menu: **Calculate (F5)**, **Detector lookup (Ctrl+D)**.
  Help menu: model documentation PDF (F1), keyboard shortcuts, About. Ctrl+1...9 jump to parameter pages.
* **Summary** tab (results dashboard): range per task, a range table when there are several atmospheres,
  key system figures (FOV, samples, DAS, Nyquist, focal length, F#, NETD/SNR, MTDP/MDSP at Nyquist)
  and a list of the warnings.
* **Detector lookup...**: picks any detector of the **Detectors_Atlas website**. *Atlas source* lists
  the local copy of the website in `detector_lookup_HTML/Detectors_Atlas/` (read from `data/live.json`,
  else `data/catalog.json`, else the catalog embedded in `index.html`; works offline - `git pull` in that
  folder to update it) and the website's published feed on GitHub Pages (`.../data/live.json`, found from
  the folder's git remote; downloaded in the background, usually newer than the local copy). Single
  atlas HTML pages / JSON catalogs placed in `detector_lookup_HTML/` are listed too; *Browse...* opens
  another file and *View in browser* opens the website. Listings the website's watcher found recently
  are shown in blue (*New listings only* filters them; their specs need review). Search or filter by
  band, pick a detector, and its values are
  mapped onto the TRM4 parameters: category, cooled/uncooled, format, pitch, frame rate, read noise,
  NETD and FPA operating temperature, when the atlas gives them. Spectral QE:
  - material with a QE preset (InGaAs, XBn, InSb, MCT/CMT, QWIP, silicon CMOS/CCD) and a stated QE
    (e.g. "QE >80% at 1550nm") and/or a verified spectral range (e.g. "(3.7 ± 0.2)–(4.8 ± 0.2) µm"):
    a custom QE table, the material curve scaled to the stated QE and limited to the verified band
    (when the verified band equals the preset's own band, e.g. XBn 3.6-4.2 um, the preset itself);
  - material with a preset but no QE / range: that QE preset;
  - verified range but no preset for the material (T2SL, HFM, CQD, IGN/T2SL...): a flat table over the
    band at an assumed 70 % (edit the level if known);
  - MWIR detectors without cooling information are set to cooled (photon detectors);
  - uncooled detectors: the range goes to the flat-response cut-on / cut-off;
  - nothing known (or the atlas says "Not verified"): the current QE setting is kept, for the user to set.
  The found values are shown next to the current ones. You can edit them, untick the ones you don't
  want, then *Apply*. Everything stays editable in the parameter tabs afterwards. Atlas notes, spectral
  verification, cooler data and the source links (product, spectral, technology, cooling) are shown
  above the table. Always check the values against the datasheet.
* Results: System performance data, MTFs (+AMOP), AMOP vs system MTF, MTDP/MDSP (+ average, MCP in
  lab mode), range performance (ETD/EDS vs MNTD/MNDS, resolved line pairs), NIIRS, spectral data,
  warnings/diagnostics.

## What is implemented (document section)

| Area | Implemented |
|---|---|
| Categories | Thermal (cooled 2nd-gen staring / micro-scan, uncooled), Visible/NIR/SWIR (CCD/CMOS staring), General (staring) |
| Basic imager | FOV (3.11), sampling (3.41–3.44), binning (3.1–3.5), electronic/pseudo interlace, rectangular/circular/diagonal micro-scan, integration time (3.74–3.76), 1/2 sensors |
| Optics | circular, central obscuration, symmetric truncation, rectangular and *General* apertures; diffraction MTF by pupil overlap (App. B), spectral weighting (4.1–4.3), aberration q / Gaussian blur, effective F-number, cold shield (2.10, 3.50–3.52); optional import of Zemax OpticStudio MTF (FFT/Huygens MTF text/CSV export, replaces diffraction + aberration) and spectral transmission (.csv/.txt) |
| Detector | rectangular / rhombic / circular / loop-hole MTF, binning, pseudo interlace, CTE, crosstalk (4.20–4.30), micro-scan integration MTF (4.36–4.39), preset QE curves |
| Radiometry | Planck, emitted/reflected radiance, target 3-D geometry & aspect (3.80–3.84), irradiation correction factors (3.92–3.99), focal-plane flux incl. optics/device/cold-shield/path radiance (3.100–3.112), dark current |
| Noise | integrating detector noise (3.130), NETD, NES, uncooled NETD scaling (3.142), IETD / PRNU / DSNU (3.166–3.168), frame integration, eye frame integration (3.181) |
| Signal processing | FIR digital filters (4.46/4.47), zoom, line/column replication, IIR / simple frame integration |
| Display / eye | flat panel MTF, system magnification, Kornfeld-Lawson eye MTF with Table 4.2 |
| Stabilization | random, sinusoidal, linear motion (4.65–4.73), additional pre/post MTFs |
| Atmosphere | Beer’s law with initial transmission, Koschmieder visibility, path radiance factor, up to 3 atmospheres |
| Turbulence | Fried parameter, long/short exposure MTF, fixed or height-dependent Cn² (4.80–4.84) |
| Figures of merit | AMOP by simulation of the 4-bar pattern at optimum phase, eye/brain integrals (3.195–3.202), MTDP/MDSP (3.175/3.176), average MDSP, MCP (3.177/3.178) |
| Range | Thermal: resolved line pairs method (3.210–3.215); Visible/General: MNDS vs EDS with directional averaging (3.219–3.221) |
| NIIRS | GIQE 5 with GSD, RER, DSNR (3.227–3.235) |

## Not implemented / approximations

* Opto-mechanically scanned imagers (1st/2nd generation scanning), ICCD/ICMOS, NVG and direct-view
  devices, CRT/LED displays and the analog video chain, sky background, asymmetric truncations,
  two illumination sources. (External optics MTF / transmission is supported only via Zemax exports.)
* **Preset spectra** (detector QE, reflectivities, emissivities, natural sources) were digitised
  approximately from the graphs of Appendix C (the original data files are not in the document).
  Tabulated values (peak irradiances, Cn² table, STANAG targets, eye Γ, phosphor data) are exact.
  A custom QE table can be entered.
* The circular detector MTF uses the standard 2·J1(πdr/f)/(πdr/f) form (the printed Eq. 4.23 appears
  to contain a factor-of-two typo).
* AMOP is obtained with a 1-D simulation; the "average modulation" is taken as the mean difference of
  adjacent apparent maxima/minima, with small ripples (<10 % of the largest swing) ignored.
