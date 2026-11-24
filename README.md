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
python tests/run_parallel.py                                           -> the same tests, modules in parallel
python run_trm4.py --cli 0 --pdf-he report.pdf                         -> Hebrew DRI report (PDF, runs the advisor)
python run_trm4.py --cli 0 --ttp                                       -> incl. TTP / V50 ranges
python run_trm4.py --cli 0 --quick                                     -> geometric quick estimate, no model run
python run_trm4.py --sfr edge.png --out sfr.txt                        -> slanted-edge SFR of an edge image
packaging\build_exe.bat                                                -> Windows EXE (dist\TRM_HADMAAv1\)
packaging\build_installer.bat                                          -> installer dist\installer\TRM_HADMAAv1_Setup_2.27.exe
python run_trm4.py --cli 4 --cn2-stats Arid:summer --overcast         -> ranges for the Cn2 statistics (Table C.2)
python run_trm4.py --cli 4 --cn2-stats Arid:winter --overcast --neutral-day   -> the same, overcast / winter noon h^-2/3
python run_trm4.py --r0-frames seq.npy --lam 0.55 --focal 500 --pitch 5 --aperture 100 --path-km 2 --out r0.txt
                                                                       -> turbulence r0 measured from a frame sequence
```

Installer (Inno Setup 6, `packaging/TRM_HADMAAv1.iss`): per-user installation in `%LOCALAPPDATA%\Programs\TRM_HADMAAv1`
(no administrator rights), Start menu and optional desktop shortcut, uninstall entry in Windows Settings, English /
Hebrew setup dialogs, Windows 10 / 11 x64. Installing does not touch this source folder; after code changes run
`packaging\build_installer.bat` again and install the new setup over the old one. User guide (Hebrew):
`USER_GUIDE_HE.md`.

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

## Versions

Every substantial change gets a new version. The version is set once in `trm4/version.py` (package, model version /
run ID); `CHANGELOG.md` lists in Hebrew what each version changed against the previous one, and
`python tools/version_report.py` writes the report `reports/version_history.html`. `tests/test_version.py` checks that
`trm4/version.py`, the installer (`packaging/TRM_HADMAAv1.iss`), the top `CHANGELOG.md` entry and the newest section
below agree.

## Version 2.37 - the partly implemented items extended: systematic search, scene-following AGC span, stabilization interpolation and crop, IIR filter text corrected

Off by default: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation | Source / limits |
|---|---|---|
| Temporal denoising (text fix) | The recursive temporal filter is the TRM4 IIR filter (`dsp.iir_alpha`, Eq. 3.141: (1 + alpha) / (1 - alpha) equivalent frames, alpha = feedback weight). The help text, the guide card and the guide check described alpha the other way round ((2 - alpha) / alpha, "weight of the new frame"); they are corrected. The engine is unchanged. | TRM4 Eq. 3.141; checked on a simulated filter (test). |
| Systematic search | `target.search_mode` = systematic with `target.search_dwell_s`: tau_FOR = (2 - Ps) / (2 Ps) (N - 1) t0 + tau_FOV, Ps = 1 - e^(-t0 / tau_FOV) (`extensions.search_tau_for`). MWIR template, 50 fields of view, tau = 3 s, 120 s: random 10.02 km, systematic with 3 s stay 8.91 km, with 6 s not reached. | Friedman, Mark & Skirlo, Opt. Eng. 58(9) 093103 (2019), Eq. 4. It tends to N tau for a short stay. |
| Scene-following AGC span | `display.contrast_span_mode` = scene: the contrast term of the threshold is scaled by the atmospheric transmission at each range (the threshold tables are built with and without the term, `_ranges_thermal`). LWIR template, 20 K: Detection 4.01 km fixed, 5.02 km scene; second atmosphere 2.03 / 4.19 km. | Structure of the TTP system contrast threshold, CTF_sys = CTF_eye / MTF x sqrt(1 + alpha^2 sigma^2 / SCT^2), target contrast dT / (2 SCT), AGC span = 2 SCT, "apparent SCT" propagated through the atmosphere (Jordan, MSc thesis, Univ. of Arizona 2024, quoting Vollmerhausen & Jacobs). The noise term is that of TRM4: not validated, still PROVISIONAL. Not applied to Visible / General (no readable source for the contrast definition). TTP ranges keep the fixed span. |
| Stabilization interpolation and crop | `stab.eis_interp` = bilinear: digital MTF x mean over the sub-pixel shift d of sqrt(1 - 2 d (1 - d) (1 - cos(2 pi r alpha))), 1/2 at Nyquist (`extensions.shift_interp_mtf`); `stab.eis_crop_pct`: the reported field of view and the number of fields of view of the search. MWIR template with 45 urad jitter: Detection 14.40 -> 13.10 km. | Derived and checked on simulated shifts (test); no published model was found. The crop does not change the task ranges. |
| Colour camera | Unchanged: no quantitative source for the luminance noise after demosaicing was found; the factor 2 stays an assumption. | - |
| Tests | `tests/test_extended_items.py` (16 tests). Five new fields with help, Hebrew guide cards without recordings and formula entries. | - |

## Version 2.36 - colour camera with a Bayer colour filter array (U9, PROVISIONAL)

Off by default: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation | Source / limits |
|---|---|---|
| U9 Bayer colour filter array | *Colour filter array* and *Interpolation of the colour image* (Detector geometry page, `detector.cfa`, `detector.demosaic`, Visible and General): the perceived noise power is x 2 (`TRM4Model.psi`); with bilinear interpolation the digital MTF is x (3 + cos(2 pi r alpha)) / 4 (`extensions.bayer_bilinear_mtf`), with adaptive interpolation it is unchanged along the axes. Daylight template: Detection 14.73 -> 13.93 km (adaptive), 13.24 km (bilinear); Identification 5.00 -> 4.77 / 4.22 km. | Palum, "Image sampling with the Bayer color filter array", IS&T PICS 2001: the resolution comes from the green plane, Nyquist on the axes as for the monochrome array, half on the diagonals and for red and blue; adaptive interpolation along the smaller gradient. The bilinear transfer is derived and checked on a simulated mosaic (test). The noise factor is an assumption (luminance from the green plane alone). Colour contrast, colour aliasing and the red and blue planes are not modelled; there is no validated range model for colour cameras. |
| Tests | `tests/test_colour_camera.py` (12 tests). The two new fields have help, a Hebrew guide card without a recording and a formula entry. | - |

## Version 2.35 - wavefront error (U5), contrast threshold of the eye (U6), search in a limited time (U10)

Off by default: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation | Source / limits |
|---|---|---|
| U5 Wavefront error | *Wavefront error rms* (Optics page, `optics.wfe_rms_um`, um of optical path): the optics MTF is multiplied by exp{-(2 pi sigma / lambda)^2 [1 - rho(s)]}, spectrally weighted (`extensions.wfe_transfer`); mid and high frequencies fall by the Strehl ratio. LWIR template: 0.7 um (lambda/14, Strehl 0.80) Detection 9.13 -> 8.81 km; 1.4 um (Strehl 0.41) -> 7.89 km. | Harvey & Kotha, Proc. SPIE 2576 (1995), Eq. 2; Juergens, OPTI 517. rho is Gaussian with a correlation length of 0.25 x the aperture (assumption that only shapes the lowest frequencies). Above 0.1 wave only a rough guide (noted). Not applied to an imported optics MTF. |
| U6 Contrast threshold of the eye (PROVISIONAL) | *Include the contrast threshold of the eye* (Display page, `display.contrast_limit`, Thermal only): MTDP = sqrt(MTDP_noise^2 + (m_t x span / (C x AMOP))^2) with m_t = 1 / S of the Barten model, span = the AGC span and C = L / (L + L_reflected) (`TRM4Model.contrast_floor`). LWIR template, 20 K span: Detection 9.13 -> 4.01 km, with 5000 lux on the display 3.24 km; a very narrow span returns the TRM4 range. | Barten model as printed in DICOM PS3.14 Annex A; reproduces Table B-1 of the standard within 4 % (test). The quadrature combination, the linear span mapping and the constant sensitivity below its best frequency are assumptions, not TRM4. Not applied to Visible / General (no input for the displayed span) or to an algorithm observer. |
| U10 Search in a limited time | *Also report the detection range with search in a limited time* (Target page, `target.search*`): P(t) = P_inf (1 - e^(-t / (N tau_FOV))), N = field of regard / field of view; the reported range is where P(t) = 50 %, i.e. the cycle criterion x TTPF^-1(0.5 / (1 - e^(-t / (N tau)))). MWIR template, 30 x 10 deg, tau = 3 s: 13.83 km in 300 s (14.48 km without search); in 60 s "not reached". | Friedman, Mark & Skirlo, Opt. Eng. 58(9) 093103 (2019), Eqs. 2-3 (random search). tau_FOV has no analytical model, so it is an input without a default. The TRM4 ranges are not changed. |
| Still blocked | U9 colour camera: no verified model (Palum, Kodak 2001: on the axes the green plane keeps the monochrome Nyquist frequency, so the "/ 1.4" estimate of the report was too pessimistic). U4 gas absorption tables: ITU-R P.1814 gives none; the manual extra extinction stays. | - |
| Tests | `tests/test_observer_search.py` (25 tests). The seven new fields have help, a Hebrew guide card without a recording and a formula entry. | - |

## Version 2.34 - electronic stabilization and the documented processing steps (U12); U14 closed by a check

Off by default: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation | Source / limits |
|---|---|---|
| U12 Electronic image stabilization | *Electronic stabilization: frame-to-frame jitter removed* (Stabilization page, `stab.eis`, for measured or PSD motion): the frame-to-frame Gaussian MTF of `_psd_mtf` / `_jitter_mtf` is not applied (`TRM4Model._eis`); the blur within the exposure stays. MWIR template with 45 urad rms of mostly slow motion: Identification 2.63 -> 3.32 km (3.35 km without motion). | Best case: the interpolation of the shifted frames and the cropped field of view are not modelled (listed under assumptions). No effect on the random-vibration model or on a still frame. |
| U12 Documented processing | With *Denoising active* the assumption and the help text say how to describe it with the existing inputs: temporal denoising = frame integration, spatial denoising = the digital filter, super-resolution = micro-scan. | The flag itself still changes no range. |
| U14 Range-dependent noise | Nothing to add: in the Thermal category target, background and air are blackbodies at one temperature, so the background flux - and with it the NETD - is the same at every range (`test_thermal_background_flux_does_not_depend_on_the_range`); the General category already evaluates the noise at every range. | The report item was wrong on this point. |
| Tests | `tests/test_processing_blocks.py` (7 tests). The new field has a Hebrew guide card without a recording and a formula entry. | - |

## Version 2.33 - every field shows the step of the calculation it enters and its formula

The model is not touched: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation |
|---|---|
| Step and formula of every field | `trm4/formulas.py`: `FIELD` maps each of the 404 form fields (339 paths) to one of the steps of the calculation - geometry and sampling, signal, noise, sharpness before sampling, processing / display / eye, system threshold, the signal at the range, the range - or to *extra output*, *check / diagnostic*, *documentation*, with the formula the engine evaluates (equation numbers of the TRM4.v3 documentation). |
| '?' of a field | The help tooltip ends with "In the calculation - <step>:" and the formula (`formulas.help_addendum`). |
| Guide card | New section "איך זה נכנס לחישוב": the step and its explanation in Hebrew, and the formula (`guide_he.field_blocks`). It is shown, not narrated, so it needs no recordings. |
| Help menu | *How the range is calculated*: the whole chain with the formulas of every step (`formulas.chain_text`, `App.show_calculation`). |
| Checked against the engine | `tests/test_formulas.py` (13 tests): every form field has a step, no entry for a field that does not exist, a field the guide rates "no effect" is not presented as part of the range chain, and the quoted formulas equal the engine (IFOV, Nyquist, FOV = [(n - 1) p + a] / f, F, jitter / diffraction / blur / eye MTF, system magnification, MTDP, eye frame integration, extinction, rain, probability levels, horizon). |
| Open | The recordings of the guide cards added in 2.32 are still missing: `test_every_fixed_sentence_is_recorded` fails until `py tools/make_guide_voice.py` is run. |

## Version 2.32 - extensions of the field report: atmospheric path, focus error, point target, dark current vs temperature

Items U3, U4 (partly), U5 (partly), U6 (diagnostic), U7, U8, U11 and U13 of
`reports/TRM_Hadmaa_Field_Effects_and_Upgrades_HE_2026-11-23.pdf`. Every one is off by default (0 or unticked), so the
template ranges are identical (`tests/test_dri_reference.py`); where one is on it is named in the assumptions.

| Item | Implementation | Source / limits |
|---|---|---|
| U3 Extinction scale height | *Extinction scale height* (Atmosphere page, `atmosphere.scale_height_km`): the entered extinction is the ground-level value and is multiplied by the mean of exp(-h / H) along the line of sight between imager and target height (`extensions.height_factor`, `Atmosphere.height`); extinction, visual-range and weather modes. Look-down from 3 km with H = 1.2 km: factor 0.37; MWIR template Detection 14.4 -> 18.9 km. | Measured aerosol scale heights 0.63 +- 0.33 km (clean) to 1.71 +- 0.84 km (haze), J. Korean Assoc. Geographic Information Studies 16(2), 2013; water vapour 1 - 2 km. Not applied to imported spectral data or to rain. |
| U13 Rain | *Rain rate* (`atmosphere.rain_mmh`): gamma = 1.2924 R^0.6436 dB/km added in every band, homogeneous along the path (`extensions.rain_extinction`). 10 mm/h: 1.31 /km. | Recommendation ITU-R P.1814-1 (09/2025), Eq. (11), Table 4 (Gamma drop size distribution, mu = 0; the assumption lists the span of mu = -2 ... 2). |
| U4 Additional extinction (partly) | *Additional extinction* (`atmosphere.extra_sigma`): a user-supplied coefficient added to every atmosphere, e.g. the gas absorption the weather mode does not contain below 8 um. | No absorption tables were added - no verified source for them. |
| U5 Focus error (partly) | *Focus error at the image plane* (`optics.defocus_um`): the optics MTF is the transfer function of the defocused pupil, `mtf.DefocusMTF` - the row integration of `pupil_overlap` with the phase 2 pi dz u d / (lambda f^2), every aperture shape; spatial frequencies beyond its first zero are contrast-reversed and not credited. Checked against a 2-D FFT autocorrelation of the pupil (difference < 0.006). LWIR template: 0.5 depths of focus -1 %, 2 depths -19 ... -32 %, 4 depths about -78 %. | Hopkins 1955; depth of focus +-2 lambda F^2 (Juergens, OPTI 517). Not applied to an imported MTF. An rms wavefront error input was not added: the Shannon approximation is inaccurate (error up to 0.7 in MTF at lambda / 14) and no other verified model was at hand. |
| U6 Ambient light (diagnostic) | *Ambient light on the display*, *Diffuse reflectance of the screen*: reflected luminance rho E / pi and the displayed contrast factor L / (L + L_refl) in System data; warning below 0.5. | The ranges are not changed: the TRM4 observer has no contrast threshold. The reflectance default 0.04 is an assumption. |
| U7 Point target | *Also report the detection range as a point (sub-pixel) target* with a single-pixel SNR criterion (default 5): pixel signal = difference signal x target solid angle / pixel solid angle (at most 1) x pixel energy fraction a Int MTF_pre dr per direction; noise = temporal noise after frame / eye integration plus FPN (`TRM4Model._point_target`, `point` per atmosphere, System data). MWIR template, 0.5 m target: 8.7 km against 4.3 km for one line pair. | Best phase (target centred on a pixel); clutter and search are not included; the SNR criterion is an assumption. TRM4.v4 adds sub-pixel target detection of its own (Fraunhofer IOSB TRM4 page). |
| U8 Rule 07 dark current | *Dark current via: Rule 07 (HgCdTe)*: J = J0 exp[C q 1.24 / (k lambda_e T)] at the sensor temperature and the 50 % cut-off of the QE curve, times the pitch area (`extensions.rule07_current_density`). MWIR template: NETD 17 mK at 80 and 120 K, 23 mK at 150 K. | Tennant et al., J. Electron. Mater. 37, 1406 (2008), constants as in the lentil library; p-on-n HgCdTe only, newer devices can lie below it. |
| U11 Range bands with the target | `analysis.range_bands(target=True)`, ticked by default on the Sensitivity tab: adds target size -/+ 25 % and, outside the Visible category, dT / 2 and x 2 at the nominal turbulence. | The spans are assumptions for a scenario envelope, not probabilities. |
| Small | Pixel pitch <= 10 um with an ideal detector MTF is listed under assumptions; with a relative illumination < 1, System data says that the ranges are for the centre of the field. | Gravrand et al., Opto-Electronics Review 31 (2023). |
| Not implemented | U9 colour cameras and U10 time-limited search (no verified model from a source that was read), U12 processing blocks and U14 range-dependent noise (deferred). | - |
| Guide | The new fields have Hebrew cards (`guide_kb_he.MORE`). **Their recordings are not made yet**: `test_every_fixed_sentence_is_recorded` fails until `py tools/make_guide_voice.py` is run; the narrator uses the live recording or the Windows voice for them. | - |
| Tests | `tests/test_atmosphere_path.py` (11), `tests/test_image_quality_extensions.py` (13), `test_extensions.RangeBands.test_target_in_the_envelope`. | - |

## Version 2.31 - corrections of the displayed range: grid steps, horizon, camera NETD and the lens

The first three items (U0, U1, U2) of `reports/TRM_Hadmaa_Field_Effects_and_Upgrades_HE_2026-11-23.pdf`. One template
range changes: General (MWIR sun-lit scene), Atm 1, Identification 3.511 -> 3.987 km (+13.6 %); all other template
ranges are identical (`tests/test_dri_reference.py`). U1 and U2 are extensions: U1 is a new option that is off by
default, U2 never changes a range.

| Item | Implementation | Source / limits |
|---|---|---|
| U0 Resolution-limited range (Visible / General) | `TRM4Model._ranges_signal`: where the MNDS becomes infinite between two points of the 56-point range grid (the bar frequency passes the resolution limit), the limit is located by bisection (16 steps) and seven ranges are added below it, per direction; the average MNDS curve and the crossing use the refined grid. Before, a task limited by the resolution and not by the signal took the range of a grid point (18 % steps): InGaAs camera in daylight, Identification 2.970 km for f = 140 ... 160 mm, then 3.511 km; now 3.066 / 3.174 / 3.280 / 3.386 / 3.490 km. The curves returned for the plots stay on the 56-point grid. | Numerical correction; the Thermal category already inverted the MTDP continuously. A well-sampled, signal-limited camera (daylight template) is unchanged. |
| U2 Line of sight | `extensions.horizon_km`, `TRM4Model._horizon`: after the ranges, every task range is compared with k (sqrt(h_imager) + sqrt(h_target)) km, k = 3.86 with standard refraction and 3.57 geometric; heights from *target height above ground* and the look-down geometry (the turbulence path geometry). A range beyond the horizon: one warning, `horizon.beyond` in the task; System data shows the heights and the horizon. The ranges are never changed. Templates (imager and target 1 m above ground): horizon 7.72 km. | A. T. Young, "Distance to the Horizon", San Diego State University (effective radius 7/6). Flat terrain or sea only; the refraction varies from day to day. |
| U1 Camera NETD and the lens (uncooled) | *Noise / sensitivity source: Measured camera NETD, converted to the scenario F-number* (`detector.noise_mode = device_scaled`): NETD x (F / test F-number)^2, the F-number term of Eq. (3.142); it needs the test F-number (`ModelError` otherwise) and is listed under assumptions. Sweeps and the advisor then say that the NETD follows the F-number instead of "held constant" (`analysis._netd_follows_F`). Uncooled template, F/1 -> F/1.4: ranges -17 / -13 / -12 % with the conversion, -10 / -7 / -7 % with the NETD held. | Default unchanged (measured NETD not converted, decision of 2.5). Lens transmission of the test taken as that of the project; the exact law for very fast optics is (4 F^2 + 1) (Foote, JPL). A measured NETD of a cooled camera is still not converted. |
| Tests | `tests/test_range_bias_fixes.py` (11 tests); reference range of the General template updated. | - |

## Version 2.30 - guide: the sentences built from the project in the Gemini voice too

The model is not touched: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation |
|---|---|
| In advance | `guide_voice.template_texts`: what the guide says of the values of every template (`presets.TEMPLATES`) in every lesson step, the walks of lesson 4 and every field card (the check, the suggestion, weight / cost, sensitivity), Hebrew; part of `static_texts`, recorded as the part `templates` of `tools/make_guide_voice.py` (223 sentences). |
| While running | `trm4/voice_live.py`: the narrator asks Gemini (`GEMINI` model and voice) for the sentences without a recording, one request per batch of up to 12, at most one every 6.5 s; the audio is cut at the pauses (`split`, shared with `tools/voice_gemini.py`) into WAV files in `%APPDATA%\TRM4\voice_cache\he`, which `recording()` finds next time. A sentence waits up to `Narrator.GEMINI_WAIT_S` (8 s) for its recording, then the Windows voice says it. Needs `google-genai` and a key (`GEMINI_API_KEY` or `%USERPROFILE%\.gemini_key`); a used-up daily quota turns it off until 10:00. The sentences sent include the project's values. |
| Packaging | `google.genai` submodules are hidden imports of `packaging/TRM_HADMAAv1.spec`. |
| Checked | `LiveVoice` tests (cutting, cache, quota, template sentences); every template sentence recorded. |

## Version 2.29 - guide: the derived-values panel is framed after a page switch

The model is not touched: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation |
|---|---|
| Fix | `guide_point.Pointer.boxes("derived")` goes to Camera profile / Quick setup when the panel is not on the current page; it now runs `app.update()` after `goto_page`, because the page's canvas maps its form and takes its width only on the Map / Configure events, which `update_idletasks` does not run. Before, nothing was framed in intro step 3 unless the last page opened was Camera profile. |
| Checked | `test_frames_in_the_window` passes; `test_guide` and `test_guide_voice` (63 tests) pass. |

## Version 2.28 - guide: every sentence recorded with the Gemini voice, old recordings removed

The model is not touched: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation |
|---|---|
| Recordings | All 2,044 Hebrew and 742 English guide sentences have a Gemini recording (`py tools/make_guide_voice.py --plan`: 0 missing); the 1,090 made since 2.27 are packaged for the first time. |
| Two sentences | `stab.jitter_mode` (`guide_kb_he.py`) reworded so it reads as a sentence; `guide_voice.speech` says a PSD unit without a number (`urad²/Hz`, `mrad²/Hz`) in words ("מיקרורדיאן בריבוע להרץ"). Both were rejected by the batch cut ("the pauses did not fit"). |
| Size | `--prune` removed 2,753 Microsoft recordings (he-IL-AvriNeural) no longer played: `trm4/assets/voice/he` 152 MB -> 55 MB, and the installer with it. |

## Version 2.27 - guide: what is explained stays shown until the next topic

The model is not touched: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation |
|---|---|
| Rule | What a demonstration shows (frame, open menu, list, bubble, card) stays until the next part of the screen is named, the step's closing sentence (`guide_point.END_WORDS`, added to every step's `show` by `step_script` as a `clear`), or the end of the narration (`GuidePanel._voice_state` clears on idle). A menu that is only shown no longer closes by itself. |
| In-menu moves | `menuitem:<label>` moves the highlight inside the menu still open (`MenuWalk.move_to`, up / down arrows, several in one sentence 1.6 s apart); `Pointer.show` keeps the menu open for them. *Choose a template*: File > New from template stays open while LWIR uncooled, the cooled ones, CMOS and SWIR are explained, the profile bar (`profile`) closes it; no template is loaded there any more. |
| Closing | `MenuWalk.close`: `EndMenu`, then `WM_CANCELMODE`, then Escape while the open menu is still this window's, up to 4 times 150 ms apart; a new walk (`MenuWalk._gen`) stops the checks of the one before, which used to close the next menu (File > Open after Save, Uncertainty after Parameter sweep). |
| Checked | All 17 demonstrating steps narrated end to end in Hebrew and English: no menu cut short, every choice in time, nothing open or framed at the end of a step, the project back. |

## Version 2.26 - guide: every lesson narrated end to end, timing fixes

The model is not touched: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation |
|---|---|
| End-to-end check | Every lesson step with demonstrations (17) narrated start to end in the real window with its event loop, the player timed by each recording's length: Hebrew 110 sentences (8.6 min), English 94 (7.8 min); every demonstration with its sentence, every menu choice in time, no menu cut short, project / workflow / page back after every step. |
| Shown menus close | `MenuWalk.SHOW_MS`: a menu that is only shown closes 2.5 s after the highlight reaches the item (before: open until the next demonstration, ~20 s over the closing sentences of the last lesson). `MenuWalk.walked` marks the item reached. |
| Step-open frame | The frame a step shows when it opens is skipped while the narration speaks (its first English sentence names Save and closed the File > Save menu the voice had just opened) and when another step is already shown. |
| Flaky test | `Panel.test_walk_follows_fields_and_cursor` failed now and then: the user's auto-play started the last step's narration 450 ms after the guide opened, in the middle of the walk; and the whole Optics page is now ~100 fields / ~1,400 sentences. The test turns auto-play off for its run (not saved) and walks the first group of the page. |

## Version 2.25 - guide: a lecturer that opens the real menus

The model is not touched: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation |
|---|---|
| Menus | `guide_point.MenuWalk`: `menu:<Top>><Item>[><Sub>]` opens the real menu-bar menu (Windows: `WM_SYSCOMMAND` / `SC_KEYMENU` with the menu's letter) and walks the highlight down to the item with arrow keys, separators skipped, opening a sub-menu with the right arrow, one key every 330 ms. A key is sent only while this window's own menu is open (`GetGUIThreadInfo`: `GUI_INMENUMODE` and the menu owner), never Enter; `EndMenu` closes it at the next sentence. Tk serves its timers inside the Windows menu loop, so the narration goes on. |
| Doing the item | `menudo:` also does the item: *File > New from template > X* is loaded by the guide (`_load_into_form`, no "save changes?" question) and the user's project, file name and saved state come back when the step ends; other items are invoked as the menu invokes them (analysis modes, *Limiting factors*), and any project change they make (the uncertainty defaults) is put back too. Items that open a file dialog are only shown. When the next sentence comes first, the menu is closed and the item done at once (`MenuWalk.finish`). |
| Tag menu | `badgemenu:<path>` opens the data-source menu of a field's tag, after the action returns (the menu runs its own loop), closed at the next sentence. |
| Lessons | *first* "choose a template" (File > New from template, loaded), "save" (File > Save, File > Open project), *results* "what limits" (Run > Limiting factors, run), *improve* (Run > Improve performance; Run > Parameter sweep / Uncertainty study / Scenario comparison, opened; File > Export report / Export Hebrew DRI report / Save), intro "the tag" (its menu); field cards: Run > Detector lookup. |
| Tests | `PointAtScreen.test_menus_walk_and_come_back`: every menu path of the lessons exists, the walk keys, a template loaded and the project restored. Checked in the real window with its event loop: 9 steps, project / workflow / page / file identical before and after each. |

## Version 2.24 - guide: it demonstrates what it explains

The model is not touched: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation |
|---|---|
| Demonstrations | `guide_point.Pointer` targets that act while their sentence is said: `help:<path>` presses the field's "?" (its explanation bubble opens; `help:` = the first field of the open page), `card:<path>` opens the field card in the guide, `pick:<path>=<option>` posts the field's list and selects the option in it without choosing it (`ttk::combobox::Post`), `page:<name>`, `workflow:<mode>`, `show_advanced`, `calculate` (runs the model, so the result tabs shown next are filled). |
| Undo | What a demonstration opens (bubble, list, card) is closed before the next sentence (`Pointer.clear`); what it changes for the step (workflow, page, *Show advanced*) is restored when the step ends (`Pointer.reset`, called by `show_step`, by any other view and on closing). No project value changes. A step shown without narration only frames its first part, without acting. |
| Lessons | intro 2 switches Quick / Engineering / Lab, intro 3 opens a page, intro 5 opens the focal-length card and presses its "?" (a new sentence in the screen text, `guide_teach` and `guide_voice_en`), intro 6 and *first* 14 calculate; *System data* frames its tab; "Clicking the tag" frames the tag. |
| Field cards | `guide_point.card_show`: every option a card names (by its label or its first word) opens the list at it - 68 sentences; Detector lookup, System data, Credit sharpening and Messages are framed when a card names them. The opening screen frames the "?", Calculate, Summary and the narrator's language / speed / auto-play controls (`HOME_SHOW`). |
| Tests | `PointAtScreen`: the "?" bubble opens and closes, the card opens and the step comes back, the list opens at the option and closes with the value untouched, workflow / page / *Show advanced* restored after every step, a card sentence opens its option. |

## Version 2.23 - guide: where the calculated values really are

The model is not touched: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation |
|---|---|
| Text | Lesson *intro*, step 3 said the calculated values are at the bottom of every page; the `D()` panel exists on *Camera profile* and *Quick setup* only. The screen text (`guide_he`), the Hebrew narration (`guide_teach.HE_STEPS`) and the English one (`guide_voice_en.STEPS`, re-stamped) now name those pages. |
| Pointer | The `derived` target goes to *Camera profile* (*Quick setup* in the Quick workflow) when the open page has no panel, scrolls to it and frames it; `PointAtScreen.test_frames_in_the_window` now checks it too. |
| Recordings | The English sentence is recorded; the Hebrew one waits for the next Gemini run (the live Windows voice says it until then). |

## Version 2.22 - guide: it frames on the screen what it talks about

The model is not touched: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation |
|---|---|
| Problem | 15 lesson steps explain a part of the screen that is not a form field (the WORKFLOW selector, the page list, the source tag, Calculate, the result tabs, New / Open / Save / Report, the Sensitivity modes, the narrator's play button and *Explain page*), but a step could only highlight a field. |
| Step key | `show: [(keywords, targets), ...]` on a step (`guide_he.LESSONS`). `guide_voice.step_script(..., point=)` inserts, before the first sentence that contains a keyword (a whole word, case as written; a Hebrew word may carry its one-letter prefixes), a `{"do": ...}` action that frames the targets while that sentence is said. The sentences are unchanged, so the recordings stay. 35 links, every one found in both languages. |
| Pointer | `trm4/guide_point.py`: `Pointer.show(targets)` finds each part (`wf[:mode]`, `pages`, `advanced`, `derived`, `badge:<path>`, `field:<path>`, `tool:<text>`, `tabs`, `tab:<name>`, `sens:<mode>`, `sensbtn:<text>`, `guide:play / walk`, `gbtn:<text>`), opens the tab or Sensitivity mode it is in, and draws a blinking orange frame over the window; cleared by the next step, another view or closing the guide. A step shown without narration frames its first part. A Sensitivity mode or button cut off by a narrow window falls back to framing the whole tab. |
| Recordings | 958 of the 2,046 Hebrew sentences now have their Gemini recording; the rest still play the Microsoft one. |
| Tests | `tests/test_guide_voice.py` `PointAtScreen`: every link in both languages, the sentences unchanged, whole-word keywords, and every target framed in the real window. |

## Version 2.21 - guide: the Hebrew narration in a Gemini voice

The model is not touched: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation |
|---|---|
| Voice | Every Hebrew recording (`guide_voice.static_texts("he")`, 2,046 sentences) is made by Google Gemini TTS, `guide_voice.GEMINI` (`gemini-3.8-flash-tts`, voice `Charon`, the text only: a style instruction was read aloud); `is_gemini`. Until a sentence has its Gemini recording, `recording` plays its Microsoft one (`legacy_key`), which `--prune` keeps. English keeps `en-US-AndrewNeural`; sentences that depend on the project keep the live Windows voice. |
| Key | `rec_key` keys a Hebrew sentence with the Gemini model, voice and prompt, so a change of any of them means new recordings. |
| Tool | `tools/voice_gemini.py` (google-genai, ffmpeg; PCM 24 kHz to mp3 48k, silence trimmed) is called by `tools/make_guide_voice.py`: the opening screen first, `--batch` consecutive sentences per request (default 20; the daily limit of 100 counts requests), cut at the pauses by dynamic programming against each sentence's share of letters, `--gemini-jobs` requests at a time; a batch that does not fit is retried in batches of 4, then one by one, and the run stops cleanly when the daily quota is used up. Every new recording is checked by `gemini-3.8-flash` listening to it against its sentence (`voice_gemini.check`); a rejected one is deleted and made again on the next run. The API key comes from `GEMINI_API_KEY` or `~/.gemini_key`; the application never needs it. |

## Version 2.20 - guide: lesson order for a new user, and a lesson that enters every parameter

The model is not touched: template ranges are unchanged; the run IDs change with the version number.

| Item | Implementation |
|---|---|
| Order | `guide_he.LESSONS`: `intro`, `first`, `results`, `engineering`, `improve`, `system`, each with a `group` heading (beginners, working with the results, advanced) and a `short` title for the panel header. The home view numbers the lessons and lists the review of all values under "tools". |
| Lesson 1 | `intro` (new): what the program calculates, the workflows, the form and pages, the result tabs, the source tag, the field card and the narrator. |
| Lesson 4 | `engineering` is dynamic (`guide_he.entry_steps`): every shown field, page by page in the order of `ENTRY_CHAPTERS` (9 chapters). Impact 3 and 2 fields get a step each; impact 3 is critical: a red `crit` box (`critical_box`, with a warning while a numeric value is still preset / assumed, `is_guess`), a red highlight of the form label (`GuideCrit.TLabel`) and a spoken sentence (`guide_voice.CRIT_TEXT`). The impact 0-1 fields of a page are one group step. The last step lists the critical fields with value, check and source tag. Repeated titles (the three tasks, atmospheres) get the form label. |
| Split / moved | The old `results` lesson is split into `results` and `improve`; `Fλ/d` moves to `system`; the source tag moves to `intro`; `first` ends with saving the project. |
| Tour | `tour` is in `guide_he.HIDDEN_LESSONS`: not on the home page, still walked by *Explain page*. |
| Voice | Hebrew (`guide_teach.HE_STEPS`) and English (`guide_voice_en`) narration of every new or changed step; recordings made and stamped with `tools/make_guide_voice.py`. |

## Version 2.19 - system considerations: the system-parameters research, checked

The research "system parameters with system considerations" was checked against datasheets and the literature
(`research_notes/system_parameters_review_he.md`: kept / changed / added, with sources). New guide lesson `system`
(8 steps, written in Hebrew and narrated in Hebrew and English, recorded). `guide_design_he.sensitivity(path, p)`
adds a live -50 ... +50 % sensitivity line to the cards of the focal length, diameter / F, pitch, format and frame
rate (lens mass and length from `estimates()`, NETD ~ F^2, die area, data rate, the 9 Hz export threshold of
uncooled cameras); `spoken_sensitivity` says it in the narration. New cost notes for NETD, read noise and frame rate.
No effect on the ranges.

## Version 2.18 - spoken guide: cause and result

`guide_voice._connect` marks results between sentences (`_RESULT_HE` / `_RESULT_EN`: verbs of effect such as
shortens, gives, drops) with "as a result" / "so" / "because of that", in turn; `_because` opens the answer to
"why does it matter?" with "because"; `_clause` turns an explaining dash into "because" and a consequence dash into
"so that", and "(= X)" into "that is X". The warning, the suggested value and the effect on the ranges are said as
reason -> action -> result ("because ...", "so I would try ...", "if you move to ..., the ranges become ...", "so in
your system ..."), as in a structured interview answer (situation, action, result). Hand-written spoken text (the
analogies of `guide_teach.LESSON`) is said as written (`auto=False`). `GuidePanel._focused_path` also reads the
field Tk keeps for the window (`focus_lastfor`) when another window has the system focus.

## Version 2.17 - spoken guide: the flow of a spoken explanation

`guide_voice.field_script` follows the structure of a spoken lesson, with a signpost question opening each part
(`guide_teach.FRAME`: preview, idea, why, numbers, source, "now let's look at yours", the effect on the ranges, a tip,
the recap). Screen text is rewritten for the ear: `_clause` (an "A = B = C" chain becomes "A, that is B, and so C";
a single "=" in prose becomes "means"; brackets become asides), `_connect` (discourse markers: "for example" for the
first context sentence, "by contrast" for the next), `_typical` (the typical values as one sentence), `_source` and
`_mistakes`. `walk_script` previews the fields of the group, bridges between fields (`guide_teach.transition`) and
recaps the group. `guide_design_he.COST` adds manufacturing and cost points to the system considerations of 16
fields, and `_cost_lines` live estimates: the germanium raw material of the lens (glass mass x 1.5-3 for machining
losses x 4,100 USD/kg, the 2025 USGS average) and the Stirling cooler life (8,000-27,000 h); sources in
`research_notes/system_considerations_he.md`, section 4a. The approach follows writing-for-the-ear guidance (short sentences, rhetorical questions,
introduction / body / recap) and the listening studies on discourse markers in lectures.

## Version 2.16 - spoken guide: walk through the fields, follow the cursor

`guide_voice.walk_script` walks a group of fields: before each field an action segment (`{"do": fn}`, run by the
`Narrator` when it is reached) highlights the field in the form, puts the cursor in it and shows its card
(`GuidePanel._walk_field`), then the field gets a brief spoken lesson (`field_script(brief=True)`). *Explain page* in
the narrator strip walks every tour group of the current page (`walk_page`); a tour group step walks its fields, and
with auto-play the walk continues to the next group. A lesson step puts the cursor in its field (`_focus_field`), and
play explains the field that has the keyboard focus when the user moved to another one (`_focused_path`). Focus moves
made by the guide itself are not treated as the user's choice (`_own_focus`); views opened by the narration do not
stop it (`_quiet`). Template ranges are unchanged; the run IDs change with the version number.

## Version 2.15 - guide: spoken narration in Hebrew and English

The interactive guide can be listened to. `trm4/guide_voice.py` builds the narration of the current view and says it
sentence by sentence; the narrator strip of the panel (`guide_panel.NarratorBar`) shows a speaking avatar, the
caption of the sentence and the controls. Nothing of it enters the model; template ranges are unchanged, the run IDs
change with the version number.

| Item | Implementation |
|---|---|
| Teaching | The narrator teaches instead of reading the card: `trm4/guide_teach.py` holds a spoken lesson for each of the 41 core fields in both languages (opening, an intuitive explanation or analogy, the bottom line), the spoken lesson steps in Hebrew (`HE_STEPS`), and `FRAME`: openings, transitions, the reaction to the user's value and closings by impact rating, picked per field (stable) for every other field. |
| Scripts | `field_script` (opening, idea, the user's value and the suggested one, why it matters, a feel for the numbers, source, system considerations, the common mistake, the computed effect on the ranges - evaluated when it is reached - and the bottom line), `step_script`, `group_script` (tour), `home_script`, `review_script`. |
| Languages | The screen stays Hebrew; the listener chooses Hebrew or English. `trm4/guide_voice_en.py`: English narration of the 41 core fields, of every hand-written lesson step, the pages and the lessons. Other fields are said in English from their form label, impact rating and check result. |
| Speech text | `speech(text, lang)`: units, symbols (delta T, sigma, F lambda / d, Cn2), ranges, powers of ten, menu paths and acronyms (letter by letter in Hebrew, with a word list). |
| Voices | Recorded neural voices (`he-IL-AvriNeural`, `en-US-AndrewNeural`) for every fixed sentence, in `trm4/assets/voice/<lang>/<sha1>.mp3`, packaged with the application; the sentences that depend on the project are said live by the Windows voice (`trm4/assets/tts_windows.ps1`: Windows.Media.SpeechSynthesis, falling back to System.Speech). Playback through the Windows MCI player; no Python package is needed at run time. |
| Tools | `tools/make_guide_voice.py` makes the missing recordings (needs `edge-tts` and the internet, at build time only), `--check` / `--prune` / `--stamp`; `assets/voice/en_sources.json` records the Hebrew source of each translation. |
| Settings | `settings["guide"]["voice"]`: language, speed (0.9 - 1.3), auto-play on every new view. F9 = listen / pause. |
| Tests | `tests/test_guide_voice.py`. |

## Version 2.14 - guide: size, weight and image defects

`trm4/guide_design_he.py` adds a "system considerations" section to the field cards of the fields that drive the
optics and the platform, and design notes to the review. Nothing of it enters the TRM4 ranges (computed on axis with
one MTF); template ranges are unchanged, the run IDs change with the version number.

| Item | Implementation |
|---|---|
| Estimates | `estimates(p)`: band and lens material (Ge / Si / glass), track length (prime / telephoto / folded), front element (x1.1 D, or D + 2 L tan(theta) with a cold stop), lens mass (elements x density x 1.6-2.5 for the housing), depth of focus +-2 lambda F^2, thermal focus shift f (gamma + alpha_Al) dT over +-40 K (Ge gamma 126e-6), Seidel difficulty indicators against an F/2, 2.5 deg lens (spherical 1/F^3, coma theta/F^2, astigmatism theta^2/F), typical corner distortion by half field and its pixel shift, cos^4 corner illumination, Airy vs pitch, chromatic band width, cooled vs uncooled core, stabilization need 0.3 IFOV, plane-wave r0 and D/r0. |
| Field cards | `SYSTEM[path]`: size / weight and image bullets and the live estimate lines of the field. |
| Review | `notes(p)`: athermalization, very fast lens, wide field, heavy lens, large front element with a cold stop, aperture above 3 r0, high stabilization need, rolling shutter with motion. |
| Background | `research_notes/system_considerations_he.md`: rules, constants and sources. |
| Version tracking | Every version has an annotated git tag `vX.Y` (`v2.4` = the initial commit with 2.0 - 2.4). `tools/version_report.py` compares each version with the previous tag: commits, changed files, `git diff vA vB` and the GitHub compare link; `--diff A B` prints the changelog entries, commits and files between any two versions. |

## Version 2.13 - guide: feedback on every value and its effect on the range

The interactive guide now covers the whole form. The model is not touched: template ranges are unchanged; the run IDs
change with the version number.

| Item | Implementation |
|---|---|
| All fields | `trm4/guide_kb_he.py` `MORE`: a card for every field of the form beyond the 40 of `guide_he.PARAMS` (about 300 paths), merged into `PARAMS`. Impact 0 = not used in the range calculation (documentation, cross-check, diagnostic). |
| Checks | A check returns `(state, message[, suggested value])`. New cross-field checks: integration time vs frame time, active size vs pitch, NETD test F-number / integration time / averaged frames / processed port, cold-shield F vs the lens, smear per exposure, AGC rounding vs NETD, no target-background contrast, narrow IFOV without jitter (also on `stab.jitter_preset` / `stab.jitter_mode`, shown when random jitter is off). Unit mistakes offer the corrected value. |
| Live impact | `trm4/guide_impact.py`: the field card runs `analysis.model_ranges` for the project and for alternatives (suggested value, +-20 % or +-10 K / % / deg, the other state of a switch, up to 5 other options of a choice) in one worker thread (newest request only, results passed to Tk through a queue), cached by the project state; it shows the DRI ranges, the change in % and the changed image-quality values of `derived.compute` (IFOV, FOV, Q, F-number, magnification ...). `apply_value` mirrors the form (pitch / focal-length policy, presets, square pixels). |
| Apply / undo | The panel applies a suggested value through the form (choices through `_choice_selected`, so presets fill their values) and can undo it. |
| Full tour | Lesson `tour` (`guide_he.tour_steps`): one step per shown group of every Engineering page and the validation page, listing each field with its value, check and impact; a click opens its card. |
| Review | `guide_he.review`: every shown field checked at once, warnings sorted by impact, with the current ranges; reachable from the home view and as the last step of the tour. |

## Version 2.12 - interactive guide in Hebrew (optional)

An optional guide panel for new users, in Hebrew: *Help > Interactive guide*, the *Guide* toolbar button or Ctrl+G
open it at the right of the window; it is off by default and its state (lesson, step, completed lessons, open at exit)
is kept under `guide` in `%APPDATA%\TRM4\settings.json`. The model is not touched: template ranges are unchanged; the
run IDs change with the version number.

| Item | Implementation |
|---|---|
| Lessons | `trm4/guide_he.py` `LESSONS`: *first calculation* (Quick Prediction), *entering a real system* in the order of influence (Engineering Analysis) and *reading the results and improving*. A step switches workflow, page and result tab, highlights the parameter's label (flash, scrolled into view) and shows its field card. Steps that do not apply to the project (category, reflectivity mode, aperture input, noise source, atmosphere mode) are skipped. |
| Knowledge base | `PARAMS`: about 40 parameters that decide the ranges - meaning, why it matters, impact rating (1-3) from the parameter-sensitivity study (`reports/השפעת פרמטרים על טווחי תצפית TRM.md`, Tables 2 and 5), typical values, where to take the value from, common mistakes. |
| Value checks | Live plausibility check of the entered value at the top of the card: unit mistakes (cm / mm, Celsius / Kelvin, percent / fraction, mrad / urad), F-number from f and D, LOS jitter relative to the IFOV (warns on a narrow field without jitter, NV-IPM 70 urad), same target and background material, zero contrast or size. |
| Field cards | While the guide is open, clicking or focusing a field shows its card. |
| Right-to-left text | Tk 8.6 on Windows does not lay out right-to-left paragraphs. `trm4/rtl_tk.py` uses the bidi pass of `report_he` and draws Latin / digit runs as one canvas item and Hebrew one character at a time from right to left (`RtlCanvas`, `RtlButton`). |

`tests/test_guide.py` checks the knowledge base and lessons against the parameter pages, the value checks, the
right-to-left ordering and walks every step of every lesson in the real window (Thermal and Visible templates).

## Version 2.11 - scintillation diagnostic for point targets and active illumination

Roadmap item 4 of Table 6 of `reports/מחקר טורבולנציה - שלב ב.pdf` (Sec. 4.8, Appendix B). Engine version 2.11; the
diagnostic is an extension that is off by default and never changes a range, so the TRM4 template ranges are
bit-identical (`tests/test_dri_reference.py`). Where it is on, it is named in the assumptions, in `extensions()` and in
its System data rows.

| Item | Implementation | Source / limits |
|---|---|---|
| Scintillation diagnostic | *Scintillation diagnostic* (turbulence page, `turbulence.scint`; `extensions.scintillation`, `TRM4Model._scintillation`). At the evaluation range of the turbulence rows (reference range, else the most demanding task) and the peak-responsivity wavelength (the laser wavelength with a monochromatic source): log-amplitude variance sigma_A^2 = 0.124 k^(7/6) L^(11/6) Cn2 of a spherical wave, with the Cn2 of the line of sight (`_cn2_path`, every Cn2 mode; r0 mode: the uniform Cn2 its scaling implies) averaged with the spherical-wave weight [z (L - z) / L]^(5/6) - symmetric, the **middle of the path weighs most** (r0 weighs the imager end, theta0 the target end); intensity variance sigma_I^2 = exp(4 sigma_A^2) - 1 at a point; aperture-averaging factor A = [1 + 0.214 (k D^2 / 4L)^(7/6)]^-1 for the camera aperture D and A sigma_I^2, the frame-to-frame fluctuation of a point target's signal. Flag when 4 sigma_A^2 >= 1: outside the weak regime the sigma_I rows say "not valid" instead of a percentage. Warning only where it matters, from an rms fluctuation of 10 % (or outside the weak regime): a target smaller than one pixel / blur spot (the dashboard occupancy check) at a task range or the reference range - System data then also shows the value through the aperture at that range - or a monochromatic (laser) illumination source (the point value of the illumination at the target, illuminator at the imager). Visible template, Cn2 1e-14, Identification 5.0 km at 0.65 um: 4 sigma_A^2 = 4.2, strong scintillation, flagged; the target is 9 x the pixel - no warning. Cn2 1e-16: sigma_I 23 % through the 25 mm aperture (A = 0.96). General template with a 2.3 x 1 m target, Cn2 1e-15: sub-pixel at Detection (14.1 km), sigma_I 52 % - warning. | sigma_A^2 and sigma_I^2: Weiss-Wrana, FGAN-FOM 2005/09 (report Sec. 4.8). Path weighting: weak-fluctuation (Rytov) theory of the spherical wave, 0.124 / B(11/6, 11/6) = 0.562 k^(7/6) Int Cn2 w dz. Aperture averaging: Churnside, "Aperture averaging of optical scintillations in the turbulent atmosphere", Appl. Opt. 30(15), 1982 (1991), spherical wave, weak turbulence (as reproduced in Kaushal & Kaddoum, arXiv:1506.04836, Eq. 21). Weak regime = Rytov variance < 1: Andrews & Phillips, "Laser Beam Propagation through Random Media", 2nd ed., SPIE Press (2005). Near the ground, paths of a few km are often beyond the weak regime: there the scintillation index saturates near 1 and these formulas over-predict - a strong-scintillation model (e.g. the all-regime forms of Andrews & Phillips) is not implemented. Time averaging within the exposure / eye integration and the ensquared energy of a point target are not modelled. |

`tests/test_turbulence_scintillation.py` covers the formulas (hand values, path weighting, aperture-averaging limits,
the weak-turbulence flag) and the diagnostic (off by default, ranges unchanged, point-target and active-illumination
warnings, r0 mode); `tests/test_gui_layout.py` the new input. Still open (Table 6): a field validation in the Negev,
the full W table of Sadot & Kopeika, the BKB albedo term, the Middle East vertical profile (Zilberman & Kopeika 2005)
and a strong-scintillation model.

## Version 2.10 - turbulence research stage B: anisoplanatism, Cn2 profiles and weather, r0 from video

The remaining recommendations of `reports/מחקר טורבולנציה - שלב ב.pdf` (Sec. 4.5 - 4.9, Appendix B, Table 6). Engine
version 2.10; every item is an extension that is off by default, so the TRM4 template ranges are bit-identical
(`tests/test_dri_reference.py`). Where an item is on, it is named in the assumptions, in `extensions()` (Summary, DRI
context, reports) and in its System data rows.

| Item | Implementation | Source / limits |
|---|---|---|
| Anisoplanatism diagnostic | *Anisoplanatism diagnostic* (turbulence page). System data at the evaluation range of the turbulence rows (reference range, else the most demanding task): isoplanatic angle theta0 = [2.914 k^2 Int Cn2 z^5/3 dz]^-3/5 = 0.314 r0 / h_bar with the plane-wave r0 and h_bar = [Int Cn2 z^5/3 / Int Cn2]^3/5 (z from the imager, so the **target end weighs most** - the TRM4 spherical-wave r0 weighs the imager end; both checked in a test), rms image tilt per axis sqrt(0.182) (lambda/D)(D/r0)^5/6, tilt-correlation angle ~ D / L and the angular size of the target. Warning when the target is larger than the tilt-correlation angle **and** the tilt reaches 0.5 IFOV (below that the internal distortion is sub-pixel): the target distorts within itself, which hurts Identification. The ranges are not changed. Visible template, Cn2 1e-14 at Identification (5.0 km): theta0 1.2 urad = 0.02 IFOV, tilt 0.28 IFOV, D / L 5 urad, target 92 x D / L - no warning; at Cn2 9.2e-13 (arid noon) the tilt is 1.5 IFOV - warning. | Fried, JOSA 72, 52 (1982). Reproduces Hardie et al. 2021, Table 2 (r0, theta0 and rms tilt within 0.5 %). The D / L angle is an order of magnitude (the ray bundles of two object points separate over the target half of the path); literature: ~120 urad for 1 km / 6 cm (~2 D/L) against theta0 ~1.3 urad. The perceptual effect of the distortion is not modelled. |
| Cn2 altitude profiles | *Turbulence specified via*: SLC night, SLC day, Greenwood good / poor seeing, Brookner Cn0^2 h^-5/6 exp(-h/320 m) (the Cn2 field is Cn0^2, i.e. Cn2 at 1 m; the other profiles have no Cn2 input). Along the slant path like the HV profile (801 path points); System data shows Cn2 at both ends of the path. Range bands scale the whole profile (`_scale_turbulence`, `cn2_scale`); the uncertainty study does not offer the unused Cn2 field. Visible template (1 m path), Recognition: fixed 1e-14 8.18 km, SLC night 8.36, SLC day 7.46, Greenwood good 8.21, poor 5.06 km. | Formulas: Quatresooz & Oestges, IEEE Access 13, 21279 (2025). Astronomical-site / free-atmosphere models: the assumption text repeats TRM4 App. C.7.2 - such profiles tend to **underestimate the turbulence close to the ground**; use them for slant / airborne paths. |
| h^-2/3 daytime option of the Cn2 statistics | Sensitivity tab *Cn2 statistics*: *Overcast / winter noon: h^-2/3* (and `--neutral-day`): the overcast noon rows and, in winter, the noon rows use h^-2/3 instead of h^-4/3 (labels and method say so). Visible template, arid winter noon 50 %: Recognition 3.41 -> 3.90 km; overcast noon 50 %: 6.26 -> 7.02 km (the 1 m path sees less of the Cn2 given at 2 m with the flatter profile; above 2 m the effect reverses). | FGAN-FOM (Weiss-Wrana 2005): the -4/3 exponent holds under a clear sky only; on overcast (winter) days -2/3 fits better. |
| Cn2 from the weather | *Turbulence specified via: Cn2 from the weather - Sadot & Kopeika 1992 (PROVISIONAL)*: Cn2(15 m) = 3.8e-14 W + 2.0e-15 T - 2.5e-15 U + 1.2e-15 U^2 - 8.5e-17 U^3 - 2.8e-15 RH + 2.9e-17 RH^2 - 1.1e-19 RH^3 - 5.3e-13 (T [K], RH [%], U [m/s]), times a local calibration factor, scaled from 15 m to the path with the TRM4 height dependence (day h^-4/3 / night h^-2/3). Temporal-hour weight W = user input with the verified presets (more than 3 h before sunrise 0.11, 3 - 2 h before 0.07, 3 - 4 / 4 - 5 / 5 - 6 temporal hours after sunrise 0.75 / 0.95 / 1.00; temporal hour = (t - sunrise) / (day length / 12), `extensions.temporal_hour`), marked PROVISIONAL until the full table of the paper is entered. Warning outside 9 - 35 C, RH 14 - 92 %, 0 - 10 m/s; a regression value <= 0 (cool, humid nights) is an error. Visible template, 25 C, RH 40 %, 3 m/s, W = 1: 3.3e-14 at 15 m, 1.2e-12 on the 1 m path, Recognition 2.37 km. | Sadot & Kopeika, Opt. Eng. 31, 200 (1992), fitted in the Negev (Beer Sheva, Sde Boker); 15 m fit height and the Mauna Loa test (R^2 = 0.02): Jellen et al., AIES (2024) - the assumption says it transfers poorly and needs a local calibration. The BKB model (Bendersky, Kopeika & Blaunstein 2004) is not implemented: its albedo term is ambiguous in the open sources. |
| r0 from a frame sequence | `trm4/labtools.py` `r0_from_frames`, *Run > Lab: turbulence r0 from a frame sequence (spectral ratio)...*, `--r0-frames`: Tukey-windowed frames, ratio \|FFT(mean frame)\| / mean \|FFT(frame)\| (magnitude spectra), median over the angle, noise-floor correction of the N-frame average, Gaussian fit ln G = -rho^2 / (2 sigma_G^2); **units**: sigma_G in cycles per metre of the focal plane (cycles/pixel / pitch), r0 = [6.88 (lambda l sigma_G)^2 (1 - alpha) / D^(1/3)]^(3/5). Optional global registration (phase correlation + phase-slope fit, sub-0.01 pixel) for camera motion with the tilt correction factor alpha. With the path length the result fills the r0 inputs (r0, wavelength, path; source *measured*) and gives the path-averaged Cn2 (TRM4 Eq. 4.82, uniform path). | Hardie, Rucci, Bose-Pillai & Van Hook, arXiv:2108.00528 (2021), Sec. 5, Eqs. 34 - 36, 44. Synthetic sequences (static scene, known short-exposure OTF, random Gaussian tilts of the known r0): 300 frames of 128 x 128, r0 1.5 - 6 cm, 5 seeds - within 5.3 % (test tolerance 10 %); 5 % noise 2.4 %; alpha ignored after a registration: +29 to +61 % (as in the paper). Needs a static scene, frames from one fixed exposure / focus; moving objects bias r0 low. |

`tests/test_turbulence_stage_b.py` covers items 1 - 4, `tests/test_labtools.py` (class `FriedParameterFromFrames`) item 5
and `tests/test_gui_layout.py` the new inputs. Still open (Table 6): scintillation for point / sub-pixel targets, a
field validation in the Negev (scintillometer, camera, weather station), the full W table of Sadot & Kopeika, the BKB
albedo term and the Middle East vertical profile (Zilberman & Kopeika 2005).

## Version 2.9 - turbulence stage 2: exposure time, short-exposure regime, physical mitigation, Cn2 statistics

From the turbulence literature review (research notes in this session: TRM4 documentation, FGAN-FOM / IOSB, TNO,
Ben-Gurion University, AFRL / University of Dayton, Purdue). Engine version 2.9; the TRM4 defaults (short exposure,
factor 1/2, no mitigation) are unchanged and the template ranges are bit-identical.

One general form of the turbulence phase structure function carries all regimes:
phi = phi_LE [1 - f a (lambda r / D)^(1/3)], with a the fraction of the image tilt removed (1 short exposure, 0 long
exposure) and f the short-exposure factor (1/2 far field, 1 near field). For f = 1 the residual tilt is exactly the
Gaussian of Hardie et al. 2021, Eq. (34) (test).

| Item | Implementation | Source / limits |
|---|---|---|
| Exposure-time turbulence MTF | *Type of MTF: Exposure-time dependent* with a new input *crosswind speed*. Window tau = eye integration time (video observer; the frame integration if longer) or the frame exposure (still, algorithm). a = (D / (D + v tau))^(1/3). Visible template, v = 2 m/s, 0.1 s: a = 0.48, Recognition 7.89 km (short 8.18, long 7.68). | TRM4 Sec. 2.28.1 recommends short exposure (the observer ignores the image motion) while Sec. 4 says an eye integrating 100 - 200 ms sees long exposure - this option resolves it. Effective aperture D + v tau: Azoulay (FGAN 1990), used by Weiss-Wrana (FGAN-FOM 2003). Frozen flow; turbulence evolution during tau neglected (more blur). |
| Short-exposure factor | *Short-exposure term*: far field 1/2 (TRM4 Eq. 4.83, default), near field 1, or auto 1/2 + 1/2 min(1, D / sqrt(lambda L)) per wavelength and range. System data shows D / sqrt(lambda L) and the factor used. Visible template, Cn2 1e-14: near field +8 % Recognition; at Cn2 9.2e-13 (arid noon): +14 %. | Fried (1966) limits; Tofsted (2011, 2014): the near-field form holds down to D ~ sqrt(lambda L). The auto mode interpolates linearly between the two limits (assumption). |
| Physical mitigation model | *Mitigation processing model: Physical*: registration removes a fraction a of the tilt (input, default 0.5), lucky-region selection among the N frames of the frame integration: Fried P = 5.6 exp[-0.1557 (D/r0)^2] per frame, a lucky region behaves as D/r0 = 3.34 (1 rad^2 tilt-removed phase variance, Noll), expected MTF = p MTF_lucky + (1 - p) MTF, p = 1 - (1 - P)^N. Frame averaging = frame integration, deconvolution = digital filter with *Credit sharpening* (existing TRM4 inputs, so the noise is consistent). The empirical r0 gain stays as the other model. | Hardie et al. 2021 (tilt correction factor); Fried 1978; van Eekeren et al. (IOSB / TNO) 2014: +10 to +18 % (3 x 3 m targets) and +18 to +25 % (5 x 5 m). Visible template against the unprocessed video (exposure-time MTF, 2 m/s): registration + selection (N = 10) +1 to +2 % at Cn2 1e-14, +4 to +8 % at 1e-13; with credited sharpening (boost 1.4) +3 to +6 % and +5 to +12 % - conservative against the published values. Note that the TRM4 short-exposure MTF already assumes all tilt removed. |
| Cn2 statistics | Sensitivity tab *Cn2 statistics* (and `--cn2-stats CLIMATE:SEASON [--overcast]`): climate (Arid / Moderate / Subarctic) and season from TRM4 Table C.2 - noon and night, the Cn2 not exceeded on 50 % and 90 % of the occasions (at 2 m, simplified height dependence); optional overcast noon (Cn2 x 0.1); arid summer adds the typical sunrise minimum (1.1e-15 at 2 m). Cards, bar chart, table, CSV, text report; process pool. Visible template, arid summer: Recognition noon 1.80 - 1.89 km, night 5.1 - 7.7 km, sunrise 9.47 km (nominal 8.18 km at Cn2 1e-14). | Table C.2: Fraunhofer IOSB (FGAN-FOM) long-term scintillometer measurements - the arid data were measured in the **Negev, Israel** (SLS20 scintillometers, 100 m path, 2.3 m above stony ground; Weiss-Wrana & Balfour, SPIE 4538, 2002; Weiss-Wrana, FGAN-FOM 2005/09). Sunrise minimum (about 1e-15 at 2.3 m, scaled to 2 m with h^-2/3) and "clouds reduce the midday Cn2 by 1 - 2 orders": same reports (x 0.1, the smaller reduction, is used). Thermal needs the turbulence extension. |

`tests/test_turbulence_stage2.py` covers these items. Not done in 2.9 (need the full papers or data): Cn2 from macro-
meteorology (Sadot & Kopeika 1992; Bendersky, Kopeika & Blaunstein 2004 for coastal Israel), the Middle East vertical
profile (Zilberman & Kopeika 2005), anisoplanatism / scintillation diagnostics and r0 measured from video - see
Version 2.10 for what followed.

## Version 2.8 - Cn2 altitude profile, tone mapping, lab tools, CLI, CI and a Windows EXE

Roadmap items P2 (Cn2 profiles) and P3 (nonlinear video processing) of "TRM4v3_Research_Improvements_English.pdf"
and the laboratory frame tools. Engine version 2.8; the TRM4 template ranges are unchanged - both new model inputs
are off by default.

| Item | Implementation | Source / limits |
|---|---|---|
| Hufnagel-Valley Cn2 profile | *Turbulence specified via: Cn2 - Hufnagel-Valley altitude profile*. Cn2(h) = 0.00594 (v/27)^2 (1e-5 h)^10 e^(-h/1000) + 2.7e-16 e^(-h/1500) + A e^(-h/100) along the slant path (h above ground from the target altitude to the imager), A = the Cn2 field, new input *rms upper-altitude wind* v (21 m/s). r0 from the path integral with 801 points (the 100 m boundary-layer term). Range bands scale the whole profile. | HV 5/7 check: vertical r0 = 4.97 cm at 0.5 um (published 5 cm). A free-atmosphere model; near the ground the surface layer can differ by an order of magnitude - use the TRM4 height mode there. |
| Tone mapping / AGC (HDR) | *Signal processing > Tone mapping / AGC of the output*: none (linear RAW, TRM4), linear AGC, gamma, logarithmic; output bit depth; Thermal: AGC span in K. Signal and noise share the curve's local slope, so only the rounding to the output levels is added: 1 / (sqrt(12) slope) referred to the input, in quadrature to the temporal noise (input range = usable capacity; Thermal: background at mid-span). The FPN estimate still refers to the sensor noise. | LWIR template, 8 bit: span 20 K -> Detection -1.7 %, 100 K -> -16 %, 14 bit -> no change. InGaAs night template: linear 8 bit -74 %, gamma 0.45 -6 %, log (k = 1000) -1 % - why such cameras use a compressive curve. Local / adaptive operators (CLAHE, HDR fusion) are not modelled. |
| Slanted-edge SFR | `trm4/labtools.py`, *Run > Lab: slanted-edge SFR from an image...* and `--sfr`: ISO 12233 e-SFR (edge centroids per row with a windowed second / third pass, line fit, 4x oversampled ESF, Hamming-windowed LSF, derivative correction), near-vertical or near-horizontal edges, angle check. The result can go straight into *Validation data > Measured MTF / SFR* (cycles/pixel). Frames: .npy, .csv / .txt, PNG / TIFF. | Verified on synthetic edges (Gaussian PSF x pixel aperture): within 0.03 of the exact MTF to Nyquist without noise, 0.05 with noise. |
| Photon transfer (EMVA 1288) | *Run > Lab: photon transfer (EMVA 1288) from flat / dark frames...*: frame pairs at several levels and a dark pair -> conversion gain K, read noise, saturation capacity, DSNU, PRNU, dark current (dark series), written on request into the detector inputs (ADC step, read noise, camera saturation capacity, PRNU, DSNU / dark current, FPN measured; source *measured*). Nonlinearity of the photon-transfer curve is flagged. | Verified on synthetic Poisson frames: K within 3 %, read noise, PRNU, DSNU and dark current recovered. The camera's operating mode, processing state and temperature have to be recorded separately (Metadata). |
| Command line | `--ttp`, `--quick`, `--sfr IMAGE [--out]` in `run_trm4.py`. | - |
| Tests and CI | `tests/run_parallel.py` runs the modules in parallel processes, longest first (12 cores: 148 s instead of 283 - 506 s serially). `.github/workflows/tests.yml` runs them on every push (Windows, Python 3.13). | - |
| Windows EXE | `packaging/build_exe.bat` (PyInstaller spec `packaging/TRM_HADMAAv1.spec`): one folder `dist\TRM_HADMAAv1\` (~105 MB) with the GUI, the Detector Atlas, the datasheets and the model documentation; the command-line options work too. `freeze_support()` keeps the process pool of the analyses working in the frozen app. | Built and checked here: GUI starts; `--cli 0 --ttp --limiting` gives the same ranges as the Python run. |

`tests/test_metrics.py` (HV profile, tone mapping) and `tests/test_labtools.py` cover these items.

## Version 2.7 - other range metrics: TTP / V50, geometric quick mode, aerosol MTF, parallel Monte Carlo

The items left open in 2.6 (and the Monte Carlo run time). Engine version 2.7; the TRM4 ranges are bit-identical,
every metric is an extra output next to them and is skipped by the analyses (`analysis.fast`).

| Item | Implementation | Source / limits |
|---|---|---|
| TTP / V50 ranges | *Also report TTP / V50 ranges* (Target & scenario, off by default) and a V50 per task (defaults 2.7 / 14.5 / 20.8 cycles). TTP = integral of sqrt(signal / threshold) over the bar frequencies the TRM4 MTDP / MDSP resolves; cycles on target V = TTP sqrt(a_h a_v) / R; P50 where V = V50, P80 / P90 from P = x^E / (1 + x^E), E = 1.51 + 0.24 x. Summary table, System data, both reports. Thermal: on the 300-point range grid, no extra run time. Visible / General: 16 ranges, MDSP on every second AMOP frequency; with turbulence the tabulated AMOP is scaled by MTF_turb(R) / MTF_turb(R_ref) (daylight template 3.2 -> 4.0 s, within 1 % of a per-range AMOP simulation). Computed after the TRM4 ranges so it cannot change them through the model caches. | Vollmerhausen, Jacobs & Driggers, Opt. Eng. 43(11) 2806 (2004). The TRM4 threshold replaces CTF_sys / C, so V50 values are not interchangeable with NV-IPM values and must be calibrated. Template ratios TTP / TRM4 (P50) range 0.6 - 2.4, mostly at Identification. |
| Geometric reference range and quick mode | *Also report the geometric reference range* (on by default): the range at which the task line pairs fit across sqrt(a_h a_v) with one line pair = max(2 IFOV, lambda / D), fixed-point iteration on slant paths. *Run > Quick geometric estimate* gives the same values without the AMOP simulation, noise, contrast or atmosphere (`model.quick_estimate`). | A sizing reference, **not** a bound: the TRM4 4-bar AMOP also credits bars beyond Nyquist, so the TRM4 range can be longer (LWIR Detection 9.1 km vs 7.7 km geometric). |
| Aerosol MTF | Kopeika aerosol MTF exp[-S R (r / xi_c)^2] below xi_c = a / lambda, exp(-S R) above (`extensions.aerosol_mtf`). For weather-derived atmospheres System data shows xi_c for haze (1 um) and fog (10 um) and the ratio of the lowest task bar frequency to the fog cutoff; a warning when it is below 3 in fog (visual range < 1 km). The ranges are not changed. | Kopeika (SPIE Press 1998, Ch. 17). For all templates xi_c is 2 - 4 orders of magnitude below the task frequencies, where the aerosol MTF is the flat scattering transmission that Beer-Lambert already applies to the signal; applying it again would double-count. |
| Monte Carlo in the process pool | The uncertainty method *Monte Carlo* draws all samples first (same seed, same order) and runs them through `analysis.Runner`; the result does not depend on the number of processes (`test_pool_equals_serial`). | - |

`tests/test_metrics.py` covers these items. Still not done: gas-line absorption in the weather mode (needs
HITRAN / MODTRAN data) and the laboratory frame / video tools.

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
