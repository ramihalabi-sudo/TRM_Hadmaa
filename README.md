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
```

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
