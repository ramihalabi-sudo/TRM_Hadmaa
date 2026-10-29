# Parameter inventory of the TRM_HADMAAv1 application (TRM4.v3 re-implementation) and how each parameter reaches image quality and DRI ranges

Scope and method

- Primary source: the code in `trm4/` (engine version string `TRM4.v3 model / TRM_HADMAAv1 engine 2.4`, `trm4/model.py:24`), the launchers `TRM_HADMAAv1.pyw` and `run_trm4.py`, the tests in `tests/`, `README.md` and the six PDFs in the repository root. The `backup/` folder was only checked for removed parameters.
- Citations are repository-relative `file:line` (the source of the finding). PDF citations give the file name and page.
- In addition to reading the code, I ran a read-only empirical check (scripts and outputs in the session scratchpad, not in the repository): `C:\Users\ramih\AppData\Local\Temp\claude\C--Users-ramih-OneDrive-Desktop-Desktop-TRM-Hadmaa\acff95aa-b3cc-43e6-8d65-31aa7be98ad5\scratchpad\oat_effect.py` and its output `oat_result.json` in the same folder.
  - **OAT -10 %:** every numeric GUI parameter (the 149 that the Parameter-sweep tab offers) was changed by -10 %, one at a time. Integers starting at 1 were set to 2. Parameters with a default of 0 were not changed, because 0 means the feature is off. The test used four templates: **LWc** = Thermal LWIR cooled CMT 640x512, **LWu** = LWIR uncooled 640x480, **SWIR** = Visible/SWIR InGaAs 640x512, **GenMW** = General MWIR sun-lit. Each run was a full model run. The results are the % change of the D/R/I range for atmosphere 1.
  - **Switch tests:** 14 mode switches on LWc and SWIR.
  - Base ranges for atmosphere 1 (km, D/R/I): LWc 9.128 / 3.415 / 1.735; LWu 5.247 / 1.801 / 0.907; SWIR 9.036 / 4.780 / 2.657; GenMW 18.27 / 7.628 / 3.983. These match `tests/reference/template_ranges.json`.
- Status tags used in the tables:
  - **CORE**: enters the DRI computation in the default path.
  - **COND**: only enters in a specific mode, category or switch.
  - **CHECK**: consistency warning or diagnostic only; does not change ranges.
  - **DOC**: traceability or documentation text only.
  - **DEAD**: never read by the engine.
  - **UI-PRESET**: a GUI selector that overwrites other fields.

---

## Q1. Which parameters does the GUI expose (by subsystem), with code name, label, units, default, validation, consumer and physical role?

### Takeaway
- **Size:** the GUI exposes about 316 parameter widgets (319 rows including duplicates) in 13 pages. 207 are at level "base", 110 "advanced" and 2 "legacy". On top of these are a Quick-setup page and a Camera-profile page that re-use the same paths. The project dictionary has 302 leaf keys, up from 191 in the original version. No parameter was ever removed.
- **What really drives DRI:** only about 60 parameters enter the range engine in a typical configuration. The ranges are dominated by:
  - geometry and sampling: f, pitch, binning, target W/H, task line-pairs;
  - aperture diameter, through diffraction and F-number;
  - the observer chain: observer type, eye MTF, display magnification, zoom, SNR threshold;
  - transmissions and the atmosphere.
- **What has little effect in the templates:** most detector-noise parameters change the range by less than about 2 % in the templates tested.
- **Text-only fields:** about 40 fields are documentation text.

### Cited Findings

#### 1.0 Structure of the parameter set
- **Where parameters are defined:**
  - Each GUI parameter is declared once in the `TABS` list as `F(path, label, kind, opts, cond, unit, level)`: `trm4/gui.py:259-260`, `trm4/gui.py:295-823`.
  - Group headers carry a level (`base` / `adv` / `legacy`) and an `active(p)` predicate. An advanced group is shown only with "Show advanced parameters" or while its predicate is true: `trm4/gui.py:253-266`, `trm4/gui.py:3138-3153`.
  - The authoritative defaults live in `P.DEFAULT_PROJECT`: `trm4/presets.py:312-437`. Every project is deep-merged onto it before a run: `trm4/model.py:148`.
- **Pages, in GUI order:**
  - General: 7 parameters.
  - Basic imager: 20.
  - Optics: 35.
  - Detector geometry: 16.
  - Detector sensitivity: 59.
  - Signal processing: 21.
  - Display & observer: 15.
  - Stabilization & MTFs: 26.
  - Target & scenario: 35.
  - Irradiance: 13.
  - Atmosphere & turbulence: 46.
  - Validation data: 26.
  - These counts come from enumerating `TABS` (dump of `trm4/gui.py:295-823`).
- **Workflows:**
  - Quick shows only "Quick setup" and "Camera profile".
  - Engineering shows all pages except "Validation data".
  - Lab adds "Validation data".
  - Source: `trm4/gui.py:869-875`.
- **Quick setup fields:**
  - category, imager_type, f_mm;
  - target preset, W, H, D, aspect;
  - dT, T_bg and the reflectivity fields;
  - illumination mode, type, spectrum, preset and E_peak;
  - atmosphere preset and atm-1 extinction or visual range;
  - turbulence on/off and its preset;
  - field/lab and video/still;
  - the three tasks;
  - plus the read-only derived panel.
  - Source: `trm4/gui.py:843-865`.
- **Read-only "derived" panel** (`trm4/derived.py:18-157`):
  - computed: FOV, IFOV = p/f, DAS, angular and focal-plane Nyquist, samples, fill factor;
  - the counterpart of D or F#, Q = lambda·F/p, the diffraction cut-off and cut-off/Nyquist;
  - frame interval, t_max and duty cycle.
- **GUI validation is type-only.** `collect()` only parses float, int and list values; failures are listed and raised only in strict mode (`trm4/gui.py:3092-3136`). There are no per-field min/max limits in the GUI. Physical limits are checked in the engine (ModelError or warnings) and in the derived panel.
- **Parameter growth:** the original `backup/trm4_before_roadmap_20261009/presets.py` had 191 leaf keys, the version before the field map had 231, and the current one has 302. None was removed (key-set diff). The original GUI field list (`backup/gui_original.py`, 178 unique `F()` paths) is a subset of the current one (294 unique paths).

#### 1.1 How parameters flow into image quality and DRI (calculation chain)

1. **Geometry and sampling.**
   - From f, pitch, active size, binning, micro-scan and interlace the engine computes:
     - the FOV;
     - the sampling distance alpha_s = p_eff/(f·N_steps) [mrad];
     - the Nyquist frequency r_N = 1/(2·alpha_s) and the DAS (detector angular subtense).
     - Source: `trm4/model.py:180-267`.
   - Timing: t_max = 1/(FR·N_steps) and the timing limit: `trm4/model.py:282-316`.
   - Display magnification: m_sys = n_fov_v·pitch_v,display/(FOV_v·viewing distance), `trm4/model.py:335-345`.
2. **Spectral radiometry.**
   - The QE curve defines the wavelength grid, scaled by qe_scale (`trm4/model.py:406-454`).
   - Optics × filter transmission: `trm4/model.py:512-550`.
   - Target and background radiance: Thermal uses blackbodies, Visible uses reflectivity, General uses both (`trm4/model.py:456-476`).
   - Illumination spectrum: `trm4/model.py:570-608`.
   - Carrier flux in the focal plane uses pi/(4F²)·tau_o·QE, plus path radiance and internal (optics/device/cold-shield) emission: `trm4/model.py:834-874`, `trm4/model.py:770-829`.
3. **Signal and noise.**
   - Integration time (direct / duty / well-fill): `trm4/model.py:881-902`.
   - Temporal noise = shot + dark + read + quantization: `trm4/model.py:920-927`.
   - Thermal: NETD is calculated at zero range (`trm4/model.py:985-998`), or a measured / scaled NETD is used (`trm4/model.py:961-984`).
   - Fixed-pattern noise: IETD (`trm4/model.py:999-1008`) or PRNU/DSNU/estimate (`trm4/model.py:1095-1104`).
   - Per-range state (signal, NES, IES, well fill): `trm4/model.py:1079-1108`.
4. **MTF chain.**
   - Pre-filter = optics × detector × additional-pre, then × motion × turbulence(R): `trm4/model.py:1562-1566`.
   - Optics: diffraction from the pupil overlap with spectral weighting, then aberration (q or Gaussian blur), or an imported curve (modes A/B/C): `trm4/model.py:1147-1210`.
   - Detector: pixel geometry × binning × CTE × crosstalk × micro-scan integration: `trm4/model.py:1325-1345`.
   - Post-filter = FIR × zoom / replication × display × additional-post (`trm4/model.py:1587-1599`), then × eye MTF (`trm4/model.py:1601-1607`).
5. **AMOP.** A 4-bar pattern is simulated through pre-filter → sampling at the optimum phase → post-filter: `trm4/amop.py:164-207`, `trm4/model.py:1618-1653`.
6. **Perceived noise and threshold.**
   - Eye/brain spatial integrals: `trm4/model.py:1655-1679`.
   - Perceived noise psi(rp) = NES²/n_int·E_N + IES²·E_I/(Δf_I,h·Δf_I,v): `trm4/model.py:1684-1692`.
   - MTDP/MDSP = (π/2)·SNR_th·√psi/AMOP: `trm4/model.py:1694-1699`.
7. **Ranges.**
   - Thermal: ETD(R) = |ΔT|·tau(R). The resolved line pairs n(R) come from the MTDP crossing and the projected target size, and D/R/I are the ranges where n(R) = lp: `trm4/model.py:2559-2607`.
   - Visible/General: EDS(R) is compared with MNDS(R), averaged over the H and V directions: `trm4/model.py:2609-2646`.
   - Range grid: log-spaced from 0.01 km to max(100 km, 10·R_min). It has 300 points for Thermal and 56 for Visible/General (`trm4/model.py:2513-2515`, `trm4/model.py:2561`, `trm4/model.py:2611`).
8. **Diagnostics, not inputs to the ranges.** The dashboard reports pixels and cycles on target, MTF at the task frequency, CNR, a limiter label, occupancy and aliasing risk: `trm4/model.py:2249-2338`.

#### 1.2 Master parameter table

Columns:
- **Code name:** path in the project dictionary.
- **GUI label @ line:** label in `trm4/gui.py`.
- **Default:** `DEFAULT_PROJECT` value; template overrides are noted.
- **Range / validation:** "type" means GUI type parsing only.
- **Used where:** `trm4/model.py` unless another file is named.
- **OAT:** -10 % one-at-a-time result as D/R/I % (see method above).

| Subsystem | Code name | GUI label @gui.py | Units | Default | Range / validation | Used where (file:line) | Physical effect → IQ / DRI | Status, notes, redundancy, OAT |
|---|---|---|---|---|---|---|---|---|
| Project | `name` | Project name @298 | – | '' | type | excluded from run ID 72-73; reports | none | DOC |
| Project | `category` | Imager category / sensing band @299 | Thermal / Visible / General | Thermal | unknown → ModelError 184-185; derived band-vs-category warning `derived.py:108-115` | 183, 459-473, 575-578, 617-624, 858-861, 1086-1089, 1503, 2552 | Selects the physics branch:<br>• Thermal: blackbody target and background; ETD = ΔT·τ; NETD and MTDP; turbulence and path radiance ignored.<br>• Visible: reflection only; MDSP in carriers.<br>• General: emission + reflection. | CORE. A GUI change resets imager_type (`gui.py:2966-2968`). |
| Project | `imager_type` | Imager type (Thermal) @300 | cooled / uncooled (staring for Visible/General) | cooled | no engine check (anything except 'uncooled' = photon detector) | 186, 961-984, 1359-1360, 1381-1382, 1872-1875 | uncooled → NETD-only noise; the thermal time constant becomes the motion low-pass; no full-well model | CORE |
| Mode | `mode.environment` | Field / Lab @303 | field / lab | field | choice | 187, 616, 1711, 1753, 1763 | Lab → no atmosphere and no ranges; Visible lab → MCP | CORE (lab = no DRI) |
| Mode | `mode.ref_range_km` | Reference range (MTF/MDSP) @305 | km | 0 | clamped ≥0 and ≥ minimum slant range (1711-1714) | 1711-1726 (spectral weights `_setup_weights` 1131-1145; reference state; `t_ref` for the motion MTF), 1737-1745 (MTF/AMOP plots) | Visible/General only. The ranges use per-range states, but the spectral weighting of diffraction/turbulence and the exposure in the motion MTF come from R_ref. | COND. The help says it is only for the plots (`help_text.py:21-22`), so the help is incomplete. |
| Mode | `mode.stream` | Video / Still @307 | video / still | video | choice | 188, 944-950, 1433, 1491 | Still → no eye temporal integration of frames → more perceived noise | CORE. Switch to still: LWc -7.1/-4.1/-2.9; SWIR -11.3/-17.4/-14.0 |
| Mode | `mode.niirs` | Calculate NIIRS (GIQE 5) @309 | bool | False | – | 188, 1774-1776, 2656-2693 | Adds a separate NIIRS output (GSD, RER, DSNR). **It also forces `self.still = True` (188), so the DRI ranges change to still-frame mode.** | COND. Has a side effect on DRI. |
| Basic | `basic.frame_rate` | Frame rate @313 | Hz | 50 (uncooled template 30) | ≤0 → ModelError 284-285 | 283-292 (t_max), 947-949 (eye frames FR·t_eye), 1386-1389 (frame sum / IIR motion) | More frames per eye time → lower perceived noise; also the t_max limit on exposure | CORE. OAT: LWc -0.3/-0.1/-0.1; SWIR -1.0/-1.7/-0.9. The Atlas sets it to the *maximum* fps (`detector_atlas.py:394`). |
| Basic | `basic.fov_mode`, `fov_h_deg`, `fov_v_deg` | FOV / Measured h/v FOV @314-316 | deg | calculate, 0, 0 | warning if more than 2 % or 10 % from the calculated FOV (269-280; `derived.py:144-150`) | warnings only | none | CHECK. Redundant with n·p/f. |
| Basic | `basic.microscan` | Micro-scan / dither @318 (adv) | none / rect / circular / diagonal | none | choice | 197-205, 262-267, 286-289, 1340-1344, 1597-1598, 1660-1677 | Finer sampling alpha_s/N; shorter t_max; diagonal-zoom MTF; eye integrals | COND |
| Basic | `basic.ms_steps_h/_v` | Horizontal / Vertical steps @320-321 | int | 2 | max(1, int) 199 | 199 | Number of micro-scan steps | COND (rectangular only). OAT 0. |
| Basic | `basic.integ_during_move` | Integration during movement @322 | bool | False | – | 1340-1344 | Micro-scan smear MTF | COND |
| Basic | `basic.bin_h/_v` | Binned pixels @326-327 (adv) | int | 1 | max(1, int) 207 | 207-240, 1331 | Larger effective pixel → coarser IFOV; more signal | COND, large effect. OAT 1→2: bin_h LWc -15.6/-17.1/-17.9, SWIR +3.2/-26.7/-30.4; bin_v LWc -18.6/-23.3/-23.9 |
| Basic | `basic.bin_kind` | Binning type @329 | charge / digital | charge | choice | 238-239, 926 | Digital adds read and quantization noise for each summed read-out | COND |
| Basic | `basic.n_sensors` | Number of identical sensors @328 (adv) | 1 / 2 | 1 | choice | 953 | n_int × 2 → perceived temporal noise / √2 | COND. Switch to 2: LWc +1.3/+0.6/+0.6; SWIR +7.0/+7.2/+5.3 |
| Basic | `basic.readout` | Readout mode @337 (adv) | global / rolling | global | rolling needs readout_ms > 0 (296-298) | 294-301, 1822-1836 | Rolling shutter: warnings about geometric distortion only; no MTF effect | CHECK |
| Basic | `basic.readout_ms` | Frame readout time @339 | ms | 0 | > frame interval → warning 299-301 | 295, 308 | Reduces the timing limit t_timing when exposure does not overlap readout | COND (caps the well-fill exposure only) |
| Basic | `basic.exp_overlap` | Exposure may overlap readout @338 | bool | True | t_timing ≤ 0 → ModelError 309-311 | 304-312, 897 | Timing limit | COND. It caps only the well-fill mode: direct and duty modes are checked against t_max (886-887, 890), not t_timing. |
| Basic | `basic.guard_ms` | Guard / trigger dead time @341 | ms | 0 | – | 305-306 | Timing limit | COND (same caveat) |
| Basic | `basic.exp_min_ms` | Hardware minimum exposure @342 | ms | 0 | – | 313, 2024-2033 | Exposure-budget violation and infeasibility warnings | CHECK |
| Basic | `basic.exp_max_ms` | Hardware maximum exposure @343 | ms | 0 (= none) | max < min → ModelError 315-316 | 314, 897, 2022-2023 | Caps the well-fill exposure | COND |
| Basic | `basic.roi` | ROI / window mode (documentation) @344 | text | '' | – | `scenario.py:68` only | none | DOC |
| Basic | `basic.interlace` | Electronic interlace @347 (legacy) | progressive / electronic / pseudo | progressive | choice | 241-246, 290-291, 1332-1333 | Pseudo-interlace area, pitch and MTF; t_max/2 | COND, legacy. Hidden unless in use. |
| Optics | `optics.aperture` | Aperture specified by @353 | circular (D) / general (F#) | circular | choice | 772-788 | Selects the principal entry: D or F# | CORE. One-of-two redundancy. |
| Optics | `optics.D_mm` | Aperture diameter D (0 = rectangular) @355 | mm | 50 (CMOS 25, SWIR 75) | D ≤ 0 needs both truncation widths (780-781) | 778-789; diffraction `mtf.py:60-73`; flux ∝ 1/(4F²) 847-850; cold shield 800-822; short-exposure turbulence 1551 | Diffraction cut-off D/lambda; light collection | CORE. OAT: LWc -5.2/-6.1/-5.4; SWIR -5.1/-8.2/-4.3; GenMW -3.4/-3.4/-11.8. The meaning "0 = rectangular aperture" is overloaded onto this field. |
| Optics | `optics.F_general` | Effective F-number @356 | – | 2.0 | ≤ 0 → ModelError 774-775 | 773-776, 788 | Same physics as D (D = f/F) | COND (only aperture=general). Redundant with D_mm. OAT 0 in the templates. |
| Optics | `optics.f_mm` | Focal length @357 | mm | 100 (MWIR 200, uncooled 50) | ≤ 0 → ModelError 192-193; `profiles.py:141-142` | 190-195, 263-267 (FOV, alpha_s, r_N), `mtf.py:84-90` (pixel MTF a/f), 788 (F = f/D), 1289 (mm→mrad conversion of imported MTF) | IFOV, Nyquist and F#: the main geometric lever | CORE. OAT (D fixed): LWc -3.5/-5.2/-4.9; LWu -8.5/-8.8/-8.8; SWIR +6.2/-0.6/-4.2 (photon-starved: a faster F helps detection); GenMW -3.7/-10.1/-11.8 |
| Optics | `optics.D_obsc_mm` | Central obscuration diameter @360 (adv) | mm | 0 | must be < D (782-783) | `mtf.py:14-58` pupil overlap, 785-788 area → D_eff | Mid-frequency MTF dip; less light | COND |
| Optics | `optics.W_trunc_h_mm/_v_mm` | Width / Height of truncated aperture @361-362 (adv) | mm | 0 | – | 779-784 | Symmetric truncation (asymmetric not implemented, model.py:10) | COND |
| Optics | `optics.diff_focal`, `optics.f_v_mm` | Different / Vertical focal length @365-366 (adv) | bool, mm | False, 100 | f_v > 0 | 191-195 (f_eff = √(f_h·f_v)) | Anamorphic optics | COND. Redundant in symmetric systems. |
| Optics | `optics.F_spec` | Manufacturer F-number (0 = none) @367 | – | 0 | warning if more than 5 % from f/D (793-797; `derived.py:97-100`) | warning only | none | CHECK, redundant |
| Optics | `optics.mtf_source` | Optical MTF source @369 | model (A) / zemax (B) / measured (B) / device (C) | model | choice | 1156-1210, 1327, 1498, 2052-2061 | Replaces the computed optics MTF (B) or the optics + detector MTF (C) | CORE |
| Optics | `optics.zemax_mtf` | MTF data file @374 | file | – | required in B/C (1251-1252) | 1247-1302; `zemax.py:121-166` | Imported polychromatic MTF; single field applied to the whole FOV (1281-1283) | COND |
| Optics | `optics.zemax_mtf_unit` | Spatial frequency in file @376 | auto / mm / mrad | auto | auto with no stated unit → ModelError 1261-1267 | 1289 | Unit conversion r = ν·f/1000 | COND |
| Optics | `optics.zemax_mtf_field` | Field number @379 | int | 1 | 1..n (1257-1259) | 1257-1260 | Field selection | COND |
| Optics | `optics.zemax_mtf_h` | Horizontal MTF uses @380 | sagittal / tangential | sagittal | – | 1268-1269 | Axis mapping | COND |
| Optics | `optics.mtf_meta`, `mtf_band`, `mtf_focus`, `mtf_temp`, `mtf_uncert` | Spectrum/field/zoom text; Band; Focus; Temperature; Uncertainty @383-387 | text | '' | – | 1284-1285, 1889-1895 | none (assumption text) | DOC. mtf_meta overlaps the four structured fields. |
| Optics | `optics.mtf_incl_diffraction/_detector/_motion` | Data include diffraction / detector aperture / motion @389-392 | bool | True / False / False | coverage overlap → ModelCoverageError (48-56, 2087) | 1158-1170, 1197-1205, 1327, 1351 | Prevents double counting of MTF components | COND |
| Optics | `optics.diffraction` | Diffraction MTF @396 (adv) | spectral / single | spectral | choice | 1182-1192 | Spectrally weighted versus single-wavelength diffraction | COND. Switch to single (default lambda = 10 µm): LWc -4.5/-5.7/-5.8; SWIR ≈0 (template lambda 1.3 µm) |
| Optics | `optics.lambda_diff_um` | Wavelength for diffraction @398 (adv) | µm | 10 (templates override) | warning if outside the band (1189-1191) | 1188 | Diffraction cut-off | COND. Default 10 µm is used even for VIS/SWIR projects that do not override it. |
| Optics | `optics.aberration` | Aberration (approximation) @400 (adv) | none / q / blur | none | choice | 1172-1175, 1206-1209 | Optics-quality approximation | COND. Switch to q = 1.3: LWc -6.4/-6.5/-6.4; SWIR -0.7/-1.8/-1.2 |
| Optics | `optics.q` | Aberration parameter q (>1) @403 | – | 1.3 | **not enforced** (q < 1 makes the MTF better than diffraction) | 1207 (MTF_diff^q) | Optics blur | COND. Hard for users to know. |
| Optics | `optics.blur_um` | Gaussian blur sigma @404 | µm | 5 | – | 1209; `mtf.py:76-79` | Optics blur | COND |
| Optics | `optics.tau_mode` | Optics transmission @406 | value / zemax | value | – | 519 | Scalar or spectral transmission | COND |
| Optics | `optics.tau_opt` | Peak transmission optics @408 | 0–1 | 0.8 (uncooled 0.9, VIS/SWIR 0.85) | outside [0,1] → ModelError 516-518 | 520-521, 538, 846, 820 (optics emission (1-τ)), 970, 661-664 | Signal level; thermal self-emission of the optics | CORE. OAT: LWc -1.1/-0.7/-0.5; SWIR -2.5/-3.9/-2.0; **LWu 0, because the measured NETD is not rescaled** |
| Optics | `optics.zemax_tau`, `tau_kind`, `tau_scope` | Transmission file; absolute / normalized; optics / system @409-417 | file, choice | –, absolute, optics | data must cover the band, otherwise edge values are held (530-532) | 522-550 | Spectral τ(λ). 'system' scope disables tau_filter to avoid double counting. | COND |
| Optics | `optics.tau_filter` | Transmission additional filter @418 | 0–1 | 1.0 | [0,1] (516-518) | 515, 521, 550 | Multiplies τ_o | CORE. Only the product τ_opt·τ_filter matters (OAT identical to tau_opt). |
| Optics | `optics.rel_illum` | Relative illumination at the field edge @422 (adv) | 0–1 | 1.0 | outside (0,1] → ModelError 1931-1933 | 1934, 2853-2855 (info row) | none on ranges | CHECK/DOC. OAT 0. |
| Det. geom. | `detector.n_h/_v` | Number of h / v detectors @426-427 | int | 640 / 512 | > 0 (`derived.py:34-35`) | 231, 262-263, 336-339 | FOV only (and the display-size check) | No DRI effect (OAT 0). |
| Det. geom. | `detector.pitch_h_um/_v_um` | Horizontal / vertical detector pitch @428-429 | µm | 15 | > 0 (215-216) | 210, 233-236, 254, 264 (alpha_s), 1216-1219, 1331, 1337, 1991, 2309 | IFOV, Nyquist, pixel area, binning MTF | CORE. OAT with f and a fixed: pitch_h LWc -0.1/+0.7/+0.9; pitch_v GenMW +0.7/+6.0/+7.6 (finer sampling, larger fill factor). The sweep policies couple pitch with active size and f (`analysis.py:204-270`). |
| Det. geom. | `detector.a_h_um/_a_v_um` | Horizontal / vertical active size @430-431 | µm | 14 (uncooled 16; CMOS 5) | > 0; a > pitch only warns (217-219) | 214, 220-221, 232, 1330 (sinc(a·r/f)) | Pixel MTF and active area | CORE. OAT: LWc +0.8/+0.6/+0.8; GenMW (v) +0.5/+4.8/+6.2. **Not set by the Atlas lookup**, so it can become larger than a newly applied pitch. |
| Det. geom. | `detector.shape` | Detector shape @433 (adv) | rect / rhombic / circular / loophole | rect | choice | 209-227, 1217, 1330; `mtf.py:84-101` | Pixel MTF and area | COND |
| Det. geom. | `detector.d_um`, `d_hole_um` | Detector diameter / hole @435-436 | µm | 14 / 2 | – | 212, 225-227, 1218, 1330 | Pixel MTF and area for circular shapes | COND |
| Det. geom. | `detector.cte_on`, `cte_h/_v`, `ntr_h/_v` | Charge transfer efficiency @438-442 (adv) | –, int | False, 0.9999, 320/256 | **CTE not range-checked** (CTE > 1 gives MTF > 1) | 1334-1337; `mtf.py:114-117` | CCD charge-transfer MTF | COND |
| Det. geom. | `detector.xtalk_h/_v` | MTF at Nyquist (0 = off) @444-445 (adv) | 0–1 | 0 | ≥ geometric MTF → warning, no crosstalk (1220-1222) | 1213-1222, 1338-1339; `mtf.py:120-129` | Crosstalk diffusion MTF | COND. Hard to know. |
| Det. sens. | `detector.uncooled_response` | Spectral response @449 | flat / preset | flat | – | 409 | Uncooled band definition | COND (uncooled) |
| Det. sens. | `detector.cuton_um`, `cutoff_um` | Cut-on / cut-off wavelength @451-452 | µm | 8 / 14 | cutoff > cuton (411-412) | 410-415 | Flat QE of 100 % in the band | COND. OAT LWu: +0.6/+0.6/+0.7 (cutoff), +0.6/+0.5/+0.5 (cuton). Set by the Atlas for uncooled detectors. |
| Det. sens. | `detector.qe_preset` | Spectral quantum efficiency @453 | 10 presets + Custom | CMT LWIR generic | choice | 417-445; `presets.py:12-36` | Defines the wavelength grid and band, the signal, NETD and spectral weights | CORE. Generic digitised curves are recorded as an assumption (477-479). |
| Det. sens. | `detector.qe_scale` | QE scale factor @455 | – | 1.0 | QE > 100 % → warning and clip (443-445) | 442 | Scales the signal | CORE. OAT SWIR -2.5/-3.9/-2.0 (same as τ); LWc 0 (well fill compensates). Redundant with τ and a custom QE. |
| Det. sens. | `detector.qe_custom`, `qe_unit` | Custom QE 'λ QE' per line; percent / fraction @456-458 | text | '' / auto | ≥ 2 rows; nm auto-converted; negative → error (418-431) | 418-435 | Custom spectral response | COND |
| Det. sens. | `detector.qe_basis` | QE refers to @461 | unspecified / active_area / pixel_area | unspecified | unknown → ModelError 251-252 | 250-256 (A_det), 1843-1859 | Reference area for the photon → carrier conversion (fill factor counted once) | COND. Switch to pixel_area: 0 % in LWc (well-fill mode compensates) and SWIR (fill factor 1). |
| Det. sens. | `detector.noise_mode` | Noise / sensitivity source @465 and @468 (two widgets) | cooled: calculated / measured; uncooled: device / detector | calculated | choice | 961-990, 1013-1040, 1861, 1882-1883, 2006 | Source of truth for temporal noise | CORE |
| Det. sens. | `detector.netd_mK` | NETD @470 | mK | 30 (uncooled 50) | – | 966, 990 → NES in Thermal (1088) | Temporal noise in the MTDP | COND (uncooled, or cooled measured). OAT LWu +0.4/+0.4/+0.4; LWc 0 (calculated mode). |
| Det. sens. | `detector.netd_TB_K` | NETD test temperature @471 | K | 0 | – | 1027-1037 | Warning if more than 10 K from T_bg | CHECK |
| Det. sens. | `detector.t_th_ms` | Detector thermal time constant @473 | ms | 10 | – | 983-984, 1359-1360, 1381-1382, 1418-1419 | Uncooled motion low-pass and exposure window | COND (OAT 0, no motion in the template) |
| Det. sens. | `detector.netd_F`, `netd_tint_ms`, `netd_frames`, `netd_nuc` | Camera NETD test conditions @475-479 | –, ms, int, text | 0, 0, 1, '' | – | 1042-1077 | Warnings and a "partial" quality flag; never converts the NETD | CHECK |
| Det. sens. | `detector.noise_port` | Measurement port @480 | raw / post_nuc / processed | raw | – | 1882-1887 | Warning only | CHECK |
| Det. sens. | `detector.meas_F`, `meas_tau`, `meas_TB_K`, `readout_mK` | Measurement F#, τ, BB temperature, read-out noise @483-486 | –, –, K, mK | 0 (= project values) | – | 967-981 (Eq. 3.142 scaling) | Scales a detector-level NETD to this optics | COND (uncooled detector mode) |
| Det. sens. | `detector.tint_mode` | Integration time via @488 | direct / duty / wellfill | wellfill (VIS/SWIR templates: direct) | choice | 881-902 | Exposure → signal, shot noise, motion smear | CORE (photon detectors) |
| Det. sens. | `detector.tint_ms` | Integration time @490 | ms | 0.2 | > t_max → warning only (886-887); t_timing and hardware limits are not enforced | 885, 965 | Exposure | COND. OAT SWIR -2.2/-3.5/-1.8 |
| Det. sens. | `detector.duty` | Integration duty cycle @491 | – | 0.5 | **no ≤ 1 check** | 889-890, 963 | t = duty·t_max | COND. Redundant with tint_ms. |
| Det. sens. | `detector.wellfill_pct` | Well fill (of usable capacity) @492 | % | 50 (MWIR 60) | > 100 → overflow warning (992-993) | 891-902 | t = fill·C_usable/(flux·A·g) | COND. OAT LWc -0.6/-0.3/-0.3 |
| Det. sens. | `detector.op_mode` | Operating mode text @494 | text | '' | – | 365, 1869-1871, 2348-2349 | none | DOC |
| Det. sens. | `detector.storage_e` | Full well (storage) capacity @495 | carriers | 1.5e7 (MWIR 7e6; CMOS 2e4; SWIR 1e6) | > 0 needed for well fill (893-894) | 235, 367-380 (usable capacity), 896, 934 | Sets the exposure in well-fill mode | COND. OAT LWc -0.6/-0.3/-0.3 |
| Det. sens. | `detector.cap_node` | Capacity refers to @496 | unknown / pixel / roic / camera | unknown | – | 366-382 | Label plus the "verified" flag | CHECK/DOC |
| Det. sens. | `detector.sat_e` | Camera saturation capacity @500 | e- | 0 | – | 370-372 | Usable capacity = min(storage, saturation, ADC full scale) | COND |
| Det. sens. | `detector.fill_limit_pct`, `bright_refl`, `bright_dT_K`, `snr_req` | Exposure-budget inputs @503-507 (adv) | %, –, K, – | 70, 0.9, 30, 0 | clipped (1951, 1975) | 1939-2043 | Warnings only; "the selected integration time is not changed" (1968-1969) | CHECK. OAT 0. |
| Det. sens. | `detector.electron_gain` | Electron gain @511 (adv) | – | 1 | **no check (0 → division by zero, 896)** | 895-896, 908-910, 923-927, 934, 1093-1107 | Internal (EM/APD) gain | COND. OAT LWc +0.5/+0.2/+0.2; SWIR -1.8/-2.8/-1.4. Hard to know. |
| Det. sens. | `detector.dark_mode`, `dark_A`, `dark_table`, `T_sensor_K` | Dark current via; dark current; I(T) table; sensor temperature @512-520 (adv) | –, A per pixel, text, K | value, 1e-12, '', 0 | table needs ≥ 2 rows, values > 0 and T > 0 (389-399) | 385-401, 877-879 (j_dark), 925, 896 | Dark shot noise; uses well capacity | COND. OAT dark_A SWIR +0.3/+0.4/+0.2. Datasheets usually give nA/cm² or e-/s, not A per pixel. |
| Det. sens. | `detector.noise_floor_e` | Read noise (additive floor) @521 (adv) | e- rms | 500 (CMOS 5; SWIR 30) | – | 926 | Additive temporal noise | COND. OAT SWIR +1.3/+2.0/+1.0; LWc 0. **Hidden by default** although active. |
| Det. sens. | `detector.noise_figure` | Noise figure (multiplicative) @522 (adv) | – | 1 | – | 923 (NF² on shot noise) | Excess noise factor of the gain | COND. OAT LWc +1.1/+0.5/+0.5. Hard to know. |
| Det. sens. | `detector.adc_mode` | ADC quantization noise @524 (adv) | none / carriers / mK | carriers | – | 912-918, 374-375, 1119-1126 | Quantization noise LSB/√12 | COND. Switch to none: SWIR +2.4/+3.3/+1.8. **Active by default (1000 e- LSB → 289 e- rms) but in a hidden group (active only if adc_bits > 0, gui 523).** |
| Det. sens. | `detector.lsb_e`, `lsb_mK` | LSB @526-527 | carriers, mK | 1000, 0 | – | 915-917, 375, 978, 1123 | Quantization noise; ADC full-scale capacity | COND. OAT lsb_e SWIR +0.4/+0.6/+0.3 |
| Det. sens. | `detector.adc_bits` | ADC bits (0 = no clipping check) @528 | int | 0 | – | 373-375, 1119-1126 | Clipping warnings; can lower the usable capacity and so change the well-fill exposure | COND |
| Det. sens. | `detector.T_off_dev_K`, `T_off_opt_K`, `T_cs_K`, `cs_mode`, `cs_eff`, `cs_F` | Housing / optics temperature offsets; cold-shield temperature, mode, efficiency, F-number @532-539 (adv) | K, K, K, –, –, – | 0, 0, 77 (XBn 150), efficiency, 1.0, 2.0 | cs_eff > 1 clamped; below the hemispherical minimum clamped (807-813) | 799-829 (j_internal added to the background flux, 872) | Internal radiation → background shot noise and well fill | COND (Thermal/General cooled). OAT cs_eff LWc -1.1/-0.7/-0.5; T_cs 0. The Atlas maps "FPA operating temperature" onto T_cs_K (`detector_atlas.py:398-399`). |
| Det. sens. | `detector.nps_file`, `nps_unit`, `nps_stage` | Measured NPS @542-545 (adv) | file, choice | – | – | 2090-2119 | Whiteness quality check only | CHECK |
| Det. sens. | `detector.fpn_mode` | Fixed pattern noise @549 (adv) | none / measured / estimate | **estimate** | choice | 999-1008, 1095-1104 | Spatial noise added to the perceived noise (psi_I, 1689-1691) | CORE. **Default IETD = 0.5 × NETD.** Switch to none: LWc +4.3/+1.9/+1.9; SWIR +3.0/+4.0/+2.5. Hidden unless fpn_mode = measured (gui 547-548). |
| Det. sens. | `detector.ietd_mK` | IETD @551 | mK | 20 | – | 1001 | Spatial noise (Thermal) | COND |
| Det. sens. | `detector.prnu_pct`, `dsnu_A` | PRNU / DSNU @552-553 | %, A | 0.5, 1e-15 | – | 1097-1099 | Spatial noise (Visible/General) | COND |
| Det. sens. | `detector.fpn_fraction` | Fraction of NETD / NES @554 | – | 0.5 | – | 1003, 1101, 2494 | Spatial noise estimate | COND. OAT LWc +0.6/+0.3/+0.3 |
| DSP | `dsp.frames_on`, `n_frames` | Simple frame averaging @558-559 | bool, int | False, 1 | n ≥ 1 (323) | 323, 943, 1386-1387 | Noise ÷ √n; motion smear | COND |
| DSP | `dsp.iir_on`, `iir_alpha` | IIR frame integration @560-561 | bool, – | False, 0 | alpha outside [0,1) → ModelError 325-326 | 324, 943-949, 1388-1389 | Noise reduction (1+α)/(1-α); IIR smear MTF | COND |
| DSP | `dsp.filter_on`, `filter_dir`, `h_type`, `v_type`, `h_coef`, `v_coef` | Digital filter; direction; type; c0..c4 @563-569 (adv) | –, –, odd/even, 5 floats | False, both, odd, [1, .5, 0, 0, 0] | list is padded to 5 values | 1226-1240, 1568-1580; `mtf.py:154-165` | FIR sharpening / smoothing applied to the post-filter and to the noise bandwidth | COND |
| DSP | `dsp.credit_boost` | Credit sharpening in the ranges @570 | bool | False | – | 1233-1240, 1577-1580 | If False and the boost is > 1.01, **the whole filter is ignored** (both MTF and noise) | COND |
| DSP | `dsp.pl_denoise`, `pl_compression` | Denoising; compression @574-575 | bool, choice | False, none | – | 1241-1245 (assumption text) | none | DOC |
| DSP | `dsp.pl_order`, `pl_version` | Order of steps; algorithm version @577-578 | text | '' | – | not read by the engine | none | DEAD (documentation) |
| DSP | `dsp.zoom`, `zoom_type` | Electronic zoom factor / type @581-582 (adv) | int | 1, pixel | max(1, round) 319 | 335 (n_fov → m_sys 344), 1591, 1585, 1668 | Raises the displayed magnification (eye MTF) and adds a replication MTF | COND. OAT 1→2: LWc +2.8/+2.0/+2.6; **SWIR +13.5/+7.2/+6.4** (digital zoom raises the predicted range) |
| DSP | `dsp.lrep`, `lrep_type` | Line replication @583-584 | int | 1, pixel | max(1, round) 320 | 322, 335, 344, 1590-1592 | Vertical magnification | COND. OAT 1→2: same as zoom. Overlaps zoom. |
| DSP | `dsp.crep`, `crep_type` | Column replication @585-586 | int | 1, pixel | max(1, round) 321 | 322, 335, 1590-1592 | Horizontal replication MTF (m_sys uses only the vertical) | COND. OAT 1→2: LWc 0; GenMW +0/+4.5/+6.0; adds a distortion warning |
| Display | `display.observer` | Observer @590 (adv) | legacy / human / algorithm | legacy | ModelError if unknown (331-332) | 330-333, 951-952, 1491, 1583-1585, 1602 | algorithm → no display MTF, no eye MTF, no eye temporal integration | CORE. **human = legacy (0.0 % change, label only).** algorithm: LWc +80/+60/+58 %; SWIR +107/+265/+205 % (uncalibrated) |
| Display | `display.algo_id`, `algo_calib` | Algorithm ID; calibration set ID @593-594 | text | '' | – | 489-492, 2328-2331, 2369 | Labels and the "uncalibrated" warning | DOC |
| Display | `display.algo_roc` | ROC / false-alarm definition @595 | text | '' | – | **not read** (only `presets.py:386`, `help_text.py:414`) | none | DEAD |
| Display | `display.observation` | Observation @597 | direct / eyepiece | direct | – | 340-343 | Viewing distance used in m_sys | COND |
| Display | `display.distance_cm` | Distance display - observer @599 | cm | 50 (CMOS 60) | – | 343-344 | Magnification → eye MTF exp(-Γ·r/M) (`mtf.py:233-235`) | CORE. OAT: LWc +0.7/+0.4/+0.5; SWIR +1.6/+2.3/+1.3 |
| Display | `display.f_eyepiece_mm` | Focal length of eyepiece @600 | mm | 25 | – | 341 | Same role as the viewing distance | COND |
| Display | `display.n_h/_v` | Number of h / v elements @602-603 (adv) | int | 1280 / 1024 | – | 336-339 (warning: "TRM4 treats this as a fatal inconsistency") | none on ranges (display MTF assumes one element per displayed sample, `mtf.py:182-184`) | CHECK. OAT 0. |
| Display | `display.pitch_h_mm` | Horizontal element pitch @604 (adv) | mm | 0.27 | – | 346-350 (distortion warning) | none on ranges | CHECK. OAT 0. |
| Display | `display.pitch_v_mm` | Vertical element pitch @605 (adv) | mm | 0.27 | – | 344 (m_sys) | Magnification → eye MTF and eye integrals | CORE. OAT: LWc -0.8/-0.7/-0.6; SWIR -1.8/-1.6/-1.3. The h and v pitches play asymmetric roles. |
| Display | `display.luminance` | Operational display luminance @606 (adv) | cd/m² | 50 | max(·, 1e-6) | 345; `mtf.py:224-230` (Γ of the eye from Table 4.2, converted to fL) | Eye PSF width | CORE (weak). OAT: SWIR -0.2/+0.3/-0.2 |
| Display | `display.neglect_eye` | Neglect eye MTF @608 (adv) | bool | False | – | 1602 | Eye MTF = 1 | COND. Switch on: LWc +5.2/+6.8/+5.1; SWIR +16.0/+16.3/+21.6 |
| Display | `display.snr_th` | Threshold SNR @609 (adv) | – | 2.5 | **none** | 352, 1699 (MDSP ∝ SNR_th) | Observer threshold | CORE. OAT: LWc +1.1/+0.5/+0.5; SWIR +2.7/+3.6/+2.2. **Hidden by default** (group active only if neglect_eye, gui 607). |
| Display | `display.t_eye_s` | Eye integration time @610 (adv) | s | 0.1 | n_int is floored at the frame-integration factor | 353, 947-949 | Eye temporal noise averaging | CORE. OAT: LWc -0.3/-0.1/-0.1; SWIR -1.0/-1.7/-0.9. Hidden by default. |
| Stab. | `stab.jitter_mode` | Motion source @614 | none / model / measured / psd | model | – | 1347-1372 | Selects the motion MTF source | CORE when motion is present |
| Stab. | `stab.random_on`, `rand_h_mrad`, `rand_v_mrad` | Random vibrations rms @630-632 | bool, mrad | False, 0 (NIIRS template 0.003) | – | 1373-1374 (exp(-2π²σ²r²)) | Gaussian jitter MTF | COND. Switch on with 0.02 mrad: LWc -1.4/-1.7/-1.2; SWIR -3.0/-10.6/-8.8 |
| Stab. | `stab.lin_on`, `lin_h`, `lin_v` | Linear image velocity @633-635 | bool, mrad/s | False, 0 | – | 1377-1389, 1829-1836, 1986-1995 | Smear sinc(t·ω·r) using the exposure; frame sum; IIR | COND |
| Stab. | `stab.smear_allow_px` | Allowed smear per exposure @636 | pixels | 0.5 | – | 1987, 2026 | Exposure-budget warning only | CHECK |
| Stab. | `stab.sin_on`, `sin_h`, `sin_v` | Sinusoidal amplitude @638-640 | bool, mrad | False, 0 | – | 1375-1376 (J0) | Sinusoidal vibration MTF | COND |
| Stab. | `stab.jitter_file`, `jitter_unit`, `jitter_rate_hz` | Jitter time series @625-629 | file, urad/mrad/pixels, Hz | – | parsed by `imports.py:141-213` | 1392-1442 | Measured intra-frame and frame-to-frame jitter MTF | COND |
| Stab. | `stab.psd_file`, `psd_unit`, `residual_los` | Angular PSD @619-623 | file, urad²/mrad²/pixel² per Hz, bool | –, urad2, True | unknown unit → ModelError 1463-1464 | 1444-1493 | Gaussian MTFs from the PSD split | COND. residual_los is a warning only (1470-1472). |
| Stab. | `stab.neglect` | Neglect stabilization MTF @642 (legacy) | bool | False | – | 1351 | Motion MTF = 1 | LEGACY. Redundant with jitter_mode = none. |
| Add. MTF | `additional.{pre,post}_{h,v}_type` / `_par` | Additional pre/post-filter h/v @646-648 (adv) | none / sinc / sinc² / gauss / rect; cycles/mrad | none, 10 | – | 1495-1500; `mtf.py:208-219` | Extra analytic MTFs; the pre-filter set is bypassed in mode C (1498) | COND. OAT par 0 (type none). |
| Target | `target.preset` | Standard target model @652 (Thermal) | STANAG 4347 / Handheld / Persons / custom | STANAG 4347 | – | GUI only: writes W, H, D, T_bg, dT, tasks and task_preset (`gui.py:2969-2979`; `presets.py:144-151`) | – | UI-PRESET |
| Target | `target.W_m`, `target.H_m` | Width / Height @654-655 | m | 2.3 / 2.3 | **none** (0 → zero projected size) | 670, 734-741, 2296-2302, 2600, 2625-2626 | Projected critical dimension → task frequency rp = lp·R/a | CORE. OAT (each): LWc -4.2/-5.0/-5.1; SWIR W -1.6/-4.3/-3.9, H -1.0/-3.2/-5.3 |
| Target | `target.D_m` | Depth @656 | m | 0 (VIS/General templates 6) | – | 670, 675, 737-740, 753-756 | Side / diagonal aspect; projection at slant angles | COND (OAT 0 for a front view) |
| Target | `target.aspect` | Target viewing aspect @657 | front / side / diagonal | front | – | 671-677 | Projected width | COND |
| Target | `target.dT_K` | Temperature difference target - background @659 | K | 2 (General template 5) | abs() only (1089, 2562) | 458, 1089, 2563 | Thermal ETD = |ΔT|·τ(R); General T_T = T_B + ΔT | CORE. OAT: LWc -1.1/-0.7/-0.5; LWu -0.9/-0.4/-0.4 (ranges are mostly resolution-limited) |
| Target | `target.T_bg_K` | Background temperature @670 | K | 288 | **no > 0 check** | 457, 474-475, 907, 623/642 (T_air = T_B in Thermal), 816-817 | Planck dL/dT (NETD), background flux | CORE. OAT: LWc +1.6/+0.5/+0.3; GenMW +0.5/+1.5/+2.3 |
| Target | `target.t_emis_mode`, `t_emis`, `t_emis_preset`; `b_emis_*` | Target / background emissivity @660-675 (General) | blackbody / grey / spectral; 0–1; material | blackbody, 0.9, Olive / Green grass | – | 470-473 (ρ = 1 - ε), 558-568 | Emission and reflection contrast | COND (General) |
| Target | `target.t_refl_mode`, `t_refl`, `t_refl_preset`; `b_refl_*` | Target / background reflectivity @665-679 (Visible) | effective / spectral; 0–1; material | effective, 0.3 / 0.15 | – | 467-468, 552-556 | Reflectance contrast | COND. OAT 0 on SWIR (the template uses spectral presets). |
| Target | `target.alt_m` | Target altitude above ground @683 (adv) | m | 1 | max(·, 0.1) | **1512 only (turbulence path height)** | Cn² height profile | COND. The help says it is used for the slant geometry (`help_text.py:251-252`), which is inaccurate. |
| Target | `target.flight`, `altitude_m`, `angle_deg` | Imager flight path; altitude; observation angle @684-686 (adv) | –, m, deg | altitude, 0, 0 | negative → sky-background warning (678-681) | 715-732, 734-741, 2660-2663 | Line-of-sight angle → projected size and minimum range; NIIRS needs a slant path | COND |
| Target | `target.clutter`, `scene_id` | Background clutter; scene ID @689-691 (adv) | choice, text | not_specified, '' | – | 500-503 (assumption text) | none (clutter is not modelled) | DOC |
| Task | `target.task_preset` | Criteria preset (version) @693 | legacy / sandia148 / johnson1958 / target / custom | legacy | – | GUI writes lp (2980-2987); model warns on mismatch (504-510) | – | UI-PRESET |
| Task | `target.tasks.N.on/name/lp` | Task N active; name; number of line pairs @694-696 | –, text, lp | on, D/R/I, 1 / 3 / 6 | lp ≤ 0 or off → task dropped (2511) | 2511, 2585-2606 (Thermal), 2615-2642 (signal) | The lp count directly scales the required spatial frequency | CORE. Excluded from sweeps (`gui.py:1408-1410`). |
| Irradiance | `irradiance.mode` | Irradiance @699 | none / single | none (VIS templates: single) | Visible with none → warning (576-577) | 575-578 | Illumination on/off | CORE (Visible/General) |
| Irradiance | `irradiance.type` | Source type @701 | blackbody / broadband / monochromatic | broadband | – | 579-592 | Spectral shape of the source | COND |
| Irradiance | `irradiance.T_bb_K` | Blackbody temperature @704 | K | 6000 | – | 582 | E = π·L_bb (hemispherical) | COND |
| Irradiance | `irradiance.spectrum` | Characterisation @706 | effective / colour / preset | colour | – | 593-608 | Shape choice | COND |
| Irradiance | `irradiance.E_eff` | Effective scene irradiance (band-integrated) @709 | W/m² | 100 | – | 594-595 (flat across the detector band) | Illumination level | COND |
| Irradiance | `irradiance.T_colour_K` | Colour temperature @711 | K | 5800 | – | 596-599 | Shape, normalised at the peak | COND |
| Irradiance | `irradiance.preset` | Natural source @713 | 5 natural sources | Direct sunlight | – | 600-608; GUI writes E_peak (2988-2990) | Spectral shape | COND |
| Irradiance | `irradiance.E_peak` | Spectral irradiance at peak (at the target) @716 | W/(m² µm) | 1239 | – | 599, 608 | Illumination level | CORE for reflective bands. OAT: SWIR -2.5/-3.9/-2.0; GenMW -1.0/-0.6/-0.6 |
| Irradiance | `irradiance.lambda_um`, `E_mono` | Wavelength; scene irradiance @718-720 | µm, W/m² | 0.85, 1 | outside the band → warning (586-588) | 583-592 | Monochromatic (e.g. laser) illuminator | COND |
| Irradiance | `irradiance.geometry` | Source geometry @722 | extended / fixed_space | extended | – | 579, 745-746 | Extended source vs. point-source angles | COND |
| Irradiance | `irradiance.beta_h_deg`, `beta_v_deg` | Angle to target front h / v @724-726 | deg | 0 / 45 | – | 743-765 | Irradiation factors F_irr,T and F_irr,B | COND. OAT GenMW β_v -10 %: +0.7/+0.3/+0.3 |
| Atmosphere | `atmosphere.preset` | Fast-mode preset @732 | custom / clear / average / adverse / all | custom | – | GUI writes σ, τ0 = 1 and V = 3.912/σ for atmospheres 1-3 and sets mode = extinction (`gui.py:2991-3003`; `presets.py:177-236`); assumption text 645-647 | Band-dependent extinction table | UI-PRESET. **Resets tau0 to 1** (the MWIR templates use 0.8). |
| Atmosphere | `atmosphere.mode` | Transmission via @733 | extinction / visibility / spectral | extinction (VIS templates: visibility) | visibility outside Visible → warning, extinction used (617-619) | 613-668 | Fast or spectral transmission | CORE |
| Atmosphere | `atmosphere.atm.N.on` | Atmosphere N @282 | bool | atmospheres 1 and 2 on, 3 off | – | 629 | Ranges per atmosphere. The analyses use atmosphere 1 only (`analysis.py:24`, `analysis.py:155`). | CORE |
| Atmosphere | `atmosphere.atm.N.sigma` | Extinction coefficient @283 | 1/km | 0.2 / 1.0 / 0.5 | σ < 0 → ModelError 640-641 | 638, 123 (τ = τ0·e^(-σR)) | Signal (and contrast) attenuation | CORE. OAT atm 1: LWc +2.0/+0.3/+0.2; GenMW +4.3/+1.0/+0.5 |
| Atmosphere | `atmosphere.atm.N.V_km` | Visual range @285 | km | 20 (VIS templates 23 / 5 / 10) | ≤ 0 → ModelError 633-634 | 632-635 (σ = 3.912/V, Koschmieder) | Same as σ | COND (Visible + visibility mode). OAT SWIR -3.9/-3.3/-1.0. Redundant with σ. |
| Atmosphere | `atmosphere.atm.N.tau0` | Initial transmission @287 | 0–1 | 1.0 (MWIR 0.8) | must be in (0, 1] (640-641) | 123, 644 | Range-independent transmission factor | CORE. OAT: LWc -1.1/-0.7/-0.5; SWIR -2.5/-4.0/-2.0. Hard to know. |
| Atmosphere | `atmosphere.atm.N.T_air_K` | Air temperature @288 and @739 (two widgets) | K | 288 | – | 623, 642, 859 | Thermal path emission (General only; Thermal uses T_B) | COND. OAT GenMW +6.7/+3.4/+2.3 |
| Atmosphere | `atmosphere.atm.N.F_PR` | Path radiance factor @290 and @740 | – | 0.15 (templates 0.05-0.2) | – | 624, 643, 861 (L_path = I·F_PR·(1-τ)/π) | Scattered path radiance → contrast loss and noise | COND (not Thermal). OAT ≈ +0.1 % |
| Atmosphere | `atmosphere.spec_file`, `spec_L_km` | Spectral transmission file; path length @736-738 | file, km | –, 1 | required in spectral mode (693-694) | 690-701; `imports.py:62-99` | τ(λ, R) | COND |
| Atmosphere | `atmosphere.path_mode`, `path_file`, `path_L_km` | Path radiance model / import @744-749 | –, file, km | model, –, 1 | required when import (706-707) | 616, 703-713, 855-856 | Imported L_path(λ, R) | COND |
| Atmosphere | `atmosphere.meta.{geometry, source, conditions, database, rt_code, profile, aerosol, resolution}` | Import documentation @752-759 | text | '' | – | 648-653, 1898-1906 | none (assumptions) | DOC |
| Turbulence | `turbulence.on` | Consider turbulence @761 | bool | False (CMOS and NIIRS templates: True) | – | 1502-1504 (requires category ≠ Thermal) | Turbulence MTF(R) | COND. Switch on (Cn² 1e-14): SWIR -3.2/-5.5/-2.0; **LWc 0 (ignored for Thermal)** |
| Turbulence | `turbulence.cn2_preset` | Scenario default (Table C.2) @762 | 24 presets / custom | custom | – | GUI writes cn2, mode = height, h_ref = 2, time (`gui.py:3004-3010`); record 1921-1922 | – | UI-PRESET |
| Turbulence | `turbulence.exposure` | Type of MTF @764 | short / long | short | – | 1551; `mtf.py:258-274` | Short exposure removes tip-tilt | COND |
| Turbulence | `turbulence.cn2_mode` | Turbulence specified via @767 | fixed / height / r0 | fixed | – | 1517-1538 | Profile model | COND |
| Turbulence | `turbulence.cn2` | Cn² @771 | m^-2/3 | 1e-14 | **no sign check** (≤ 0 → r0 = ∞) | 1516-1526, 1538; `mtf.py:241-255` | Fried parameter r0 | COND |
| Turbulence | `turbulence.h_ref_m`, `time` | Cn² specified at height; day/night @779-782 | m, – | 2, day | – | 1518-1523 | Cn²(h) ∝ h^(-4/3) by day, h^(-2/3) at night | COND |
| Turbulence | `turbulence.r0_cm`, `r0_lambda_um`, `r0_L_km` | Fried parameter and its reference conditions @773-778 | cm, µm, km | 5, 0.55, 1 | all must be > 0 (1531-1533) | 1527-1536 | r0 scaled with λ^(6/5) and L^(-3/5) | COND |
| Turbulence | `turbulence.L0_m` | Outer scale L0 (0 = Kolmogorov) @783 | m | 0 | – | 1544-1547; `mtf.py:258-274` | von Kármán correction | COND |
| Validation | `measured.fom_file`, `fom_kind`, `fom_unit`, `fom_vunit`, `fom_use` | Measured MTDP / MRTD / MCP @788-794 | file, choice | –, MTDP, mrad, K, compare | replace only for Thermal MTDP/MRTD (2139-2147) | 2121-2148, 1755-1767 | 'replace' → ranges from the measured curve | COND (Lab) |
| Validation | `measured.sfr_file`, `sfr_kind`, `sfr_unit` | Measured MTF / SFR @797-801 | file, choice | – | – | 2169-2193 | Comparison only | CHECK |
| Validation | `measured.netd_mK`, `netd_TB_K` | Measured NETD; BB temperature @803-804 | mK, K | 0 | – | 2194-2202 | Comparison only | CHECK. Duplicates the concept of `detector.netd_mK`. |
| Validation | `measured.meta.*` (16 fields) | Calibration metadata @806-821 | text | '' | – | 2205-2217 (config_id compared with profile.config) | none | DOC |
| Internal | `profile.{name, config, profile_id, content_hash}` | set by profile apply | – | '' | – | `profiles.py:171-172`; `model.py:2214` | Traceability | DOC |
| Internal | `provenance{path: source}` | source badge next to each value (`gui.py:2851-2857`) | preset / assumption / user / manufacturer / measurement / import / profile | {} | – | 175, 1038-1040, 1852-1856; `advisor.py:475-507` | Changes only messages and the "measure first" list | DOC |
| Internal | `uncertainty{}`, `scenarios[]` | Sensitivity tab | – | {} / [] | – | `analysis.py:558-595`, `analysis.py:814-837` | Analysis settings; excluded from the run ID (72-73) | analysis-only |
| Internal | `_what_if{}` | not in the GUI | no_aberr, ideal_det, noise_scale, fpn_scale, ideal_eye, no_atm, no_stab, no_turb | – | – | 156, 654-655, 1085, 1195, 1327, 1351, 1504, 1602 | Counterfactual switches for limiting factors and the advisor | internal |

**Hard-coded model constants** (not editable, but they shape the results):

| Constant | Value / role | Location |
|---|---|---|
| Eye-PSF width table | Γ versus luminance (Table 4.2) | `presets.py:141` |
| AMOP simulation | 8 phases; wiggle threshold 10 % | `amop.py:164`, `amop.py:118` |
| AMOP table | 70 frequencies | `model.py:1744` |
| Eye integrals | 140 frequencies | `model.py:1659` |
| Koschmieder constant | 3.912 | `model.py:635` |
| Range grid | 0.01 → 100 km; 300 points (Thermal) / 56 points (Visible/General) | `model.py:2513-2515`, `model.py:2561`, `model.py:2611` |
| Dashboard heuristics: aliasing levels | MTF at Nyquist 0.1 / 0.3; spurious response 0.15 / 0.4 | `model.py:2232-2238` |
| Dashboard heuristics: sampling-limited flag | lp ≥ 0.9 × cycles at Nyquist | `model.py:2298` |
| Dashboard heuristics: "resolution" limiter | MTF at the task frequency < 0.1 | `model.py:2319` |
| Dashboard heuristics: sub-pixel warning | target occupancy < 1 | `model.py:2311` |
| Band classification thresholds | mid-wavelength < 1.1 / 3 / 6 µm | `presets.py:187-196` |
| Advisor "no effect" threshold | 0.5 % | `advisor.py:37` |

#### 1.3 Empirical ranking of numeric parameters (OAT -10 %, largest |Δ| over D/R/I and templates)
- **Large effect (more than 5 % on at least one task):**
  - binning 1→2: up to -33 %.
  - digital zoom or line replication 1→2: up to +14 %.
  - focal length: up to -12 %.
  - aperture D: up to -12 %.
  - target W or H: about -5 %.
  - pitch_v (GenMW): up to +7.6 %.
  - active size a_v (GenMW): up to +6.2 %.
  - column replication (GenMW): up to +6 %.
  - air temperature (General): +6.7 %.
- **Medium effect (1-5 %):** extinction σ; visual range; τ0; τ_opt; τ_filter; qe_scale; E_peak; t_int; snr_th; display distance and vertical pitch; read noise (SWIR); electron gain (SWIR); target T_bg; ΔT (about 1 %); cs_eff; noise figure.
- **Small effect (< 1 %):** frame rate; eye time; NETD (uncooled); dark current; LSB; storage capacity; well fill; FPN fraction; luminance; F_PR; cut-on/cut-off.
- **Zero effect in all four templates (dead or check-only in these configurations):**
  - display n_h/n_v and pitch_h;
  - n_h/n_v (FOV only);
  - fill_limit, bright_refl, bright_dT and smear_allow;
  - rel_illum; F_general (D mode); f_v; lambda_diff (spectral mode); q and blur (no aberration);
  - CTE/ntr, d_um/d_hole, micro-scan steps;
  - t_th (no motion); T_cs (LWIR); ietd, prnu, dsnu (not in measured FPN mode);
  - target alt_m; all turbulence values (turbulence off);
  - atmospheres 2 and 3 (analyses use atmosphere 1);
  - zemax_mtf_field; spec_L_km and path_L_km.
  - Source: OAT run, `oat_result.json`.
- **Switch tests:**
  - observer = algorithm gives the largest single effect of any input: +58 % to +265 %;
  - neglect_eye: +5 % to +22 %;
  - still mode: -3 % to -17 %;
  - FPN none: +2 % to +4 %;
  - n_sensors = 2: up to +7 %;
  - aberration q = 1.3: -6 % (LWIR);
  - single-λ diffraction at 10 µm: -6 % (LWIR);
  - turbulence on: -2 % to -5.5 % (SWIR), 0 for Thermal;
  - ADC none: up to +3.3 % (SWIR);
  - qe_basis, cap_node and exp_overlap: 0 in these templates;
  - observer human: 0.

### Inferences
- **What dominates the ranges.** In every template tested, the DRI ranges are mainly sampling- and resolution-limited. Geometry (f, pitch, binning, target size, lp), aperture/diffraction and the observer and display chain dominate. Most detector-noise inputs change the ranges by only a few percent. A user-facing plan can therefore treat about 15 parameters as first-class and keep the noise micro-parameters behind profiles. The caveat: the photon-starved SWIR night case shows larger noise sensitivity, so the hierarchy depends on the operating point.
- **The observer and display chain is a strong, weakly grounded lever.** Changing it alone moves ranges more than most hardware changes:
  - digital zoom ×2: up to +14 %;
  - eye MTF off: up to +22 %;
  - algorithm observer: up to +265 %.
  - These inputs need calibration or default locking. Otherwise users can raise predicted DRI without any change in information content.
- **Hidden-but-active defaults decide the results.** The hidden groups contain values that change the ranges by default: FPN estimate 0.5 × NETD, ADC LSB 1000 e-, read noise 500 e-, SNR_th, eye time and display pitch. Their group predicates hide them because the predicates test "non-default", not "active" (`gui.py:508-510`, `gui.py:523`, `gui.py:547-548`, `gui.py:601`, `gui.py:607`).

### Gaps
- **Coverage of the OAT run.**
  - It used -10 % steps on four templates and atmosphere 1 only. It does not measure interactions or non-linearity, and it does not cover the daylight CMOS (5.9 s per run) or NIIRS templates. Turbulence-on behaviour was not swept, nor the effect of measured-file imports.
  - Parameters with a default of 0 (jitter, readout and guard times, exp_max, sat_e, adc_bits, L0, obscuration and others) were not perturbed. Their effect is known only from the code path.
- **Display and observer magnitudes.** Their effect sizes come from the TRM4 eye model. They have not been validated against observer data in this repository: the README states no observer trials were implemented (`README.md:80-82`).

---

## Q2. Which parameters are used by the computation and which are dead, duplicated, derivable, cosmetic or overridden? Which have inconsistent units, no validation, or are hard for a user to know?

### Takeaway
- **Dead or cosmetic:** about 70 GUI fields never affect DRI. About 40 are documentation text and about 30 are checks or warnings only. Two are completely dead (`display.algo_roc`, `dsp.pl_order/pl_version`), and one switch is cosmetic (observer "human" = "legacy").
- **Redundant:** at least 20 groups are redundant or derivable (F# vs D; FOV vs n·p/f; σ vs V; duty vs t_int; cs_eff vs cs_F; zoom vs line replication; tau_opt × tau_filter × qe_scale × tau0).
- **Validation:** GUI validation is type-only. The engine validates about 30 conditions. Many physically bounded inputs (q, CTE, duty, electron gain, target size, T_bg, Cn², SNR_th) are unchecked.
- **Help text:** the 38 newest fields (v2.4 research-review items) have no help text, and two existing help texts are inaccurate.

### Cited Findings

#### 2.1 Parameters with no effect on ranges

| Class | Parameters | Evidence |
|---|---|---|
| Completely dead (stored, never read by the engine) | `display.algo_roc`; `dsp.pl_order`; `dsp.pl_version` | grep: `algo_roc` appears only in `presets.py:386`, `gui.py:595`, `help_text.py:414`. `pl_order`/`pl_version` appear in no engine module (cross-reference run). |
| Cosmetic switch | `display.observer = "human"` (identical to "legacy"; changes text only) | `model.py:330-333`, `model.py:494-496`; switch test 0.0 % |
| Documentation text only | `name`; `basic.roi`; `detector.op_mode`; `detector.netd_nuc`; `optics.mtf_meta/band/focus/temp/uncert`; `dsp.pl_denoise/pl_compression`; `display.algo_id/algo_calib`; `target.clutter/scene_id`; `target.tasks.N.name`; `atmosphere.meta.*` (8); `measured.meta.*` (16); `profile.*` | Assumption or warning text only: `model.py:1241-1245`, `model.py:1284-1285`, `model.py:1869-1906`, `model.py:500-503`, `model.py:2205-2217` |
| Checks / warnings only | `basic.fov_mode`, `fov_h_deg`, `fov_v_deg`; `optics.F_spec`; `optics.rel_illum`; `display.n_h/_v`; `display.pitch_h_mm`; `basic.readout` (rolling); `basic.exp_min_ms`; `detector.netd_TB_K`, `netd_F`, `netd_tint_ms`, `netd_frames`; `detector.noise_port`; `detector.cap_node`; `detector.fill_limit_pct`, `bright_refl`, `bright_dT_K`, `snr_req`; `stab.smear_allow_px`; `stab.residual_los`; `detector.nps_*`; `measured.sfr_*`; `measured.netd_*` | `model.py:269-280`, `model.py:793-797`, `model.py:1931-1934`, `model.py:336-350`, `model.py:1822-1836`, `model.py:1939-2043` ("the selected integration time is not changed", 1968-1969), `model.py:1013-1077`, `model.py:2090-2119`, `model.py:2169-2202` |
| Ignored by category (TRM4 inheritance) | Thermal: all `turbulence.*`; `atmosphere.atm.N.T_air_K` and `F_PR`; path radiance overall (the Thermal range uses ETD = ΔT·τ only); `irradiance.*`; emissivity/reflectivity. Visible: `target.dT_K`, `T_air`. | `model.py:1502-1504`, `model.py:623-624`, `model.py:642-643`, `model.py:2562-2563`, `model.py:575`, `model.py:459-463`. TRM4 itself restricts turbulence to Visible and General (`TRM4v3_ModelDocumentation_260930_095803.pdf` p.99, §2.28). |
| No effect on the result in common modes | n_h/n_v (FOV only); `qe_basis` and `cap_node` in well-fill mode; `tau_opt` with a measured NETD (the measured NETD is held constant; `analysis.py:288-290` notes this) | OAT 0; `model.py:966`, `model.py:990` |

#### 2.2 Redundant, duplicated or derivable parameter groups

| Group | Members | How handled | Recommendation hint (from in-repo docs) |
|---|---|---|---|
| Aperture | `optics.aperture` + `D_mm` ↔ `F_general` (D = f/F); `F_spec` cross-check; `D_mm = 0` doubles as the rectangular-aperture switch | One principal entry; the counterpart is shown in the derived panel (`derived.py:63-94`); F_spec only warns (`model.py:793-797`) | "Use one principal entry and calculate its consistent counterpart" (`TRM4_Application_Changes.pdf` p.3) |
| FOV | `fov_mode`, `fov_h_deg`, `fov_v_deg` versus n·p/f | Cross-check warning only (`model.py:269-280`) | "Calculate and display; allow measured FOV as a cross-check" (`TRM4_Application_Changes.pdf` p.3) |
| Detector area | `a_h/a_v` vs pitch (fill factor); `d_um`/`d_hole` for circular shapes; `qe_basis` | Fill factor derived (`model.py:255`); a > pitch only warns (`model.py:217-219`) | Research review §3.5 (`TRM4v3_Research_Improvements_English.pdf` p.4-5) |
| H/V pairs | pitch, active size, n, bin, ms_steps, xtalk, cte, ntr, rand, lin, sin, additional pre/post, display pitch, f_h/f_v | Separate inputs; symmetric in all templates (`presets.py:452-558`) | Anisotropy is needed only for special optics ("Keep horizontal and vertical MTF information when possible", `TRM4_Application_Changes.pdf` p.7) |
| Exposure | `tint_mode` with `tint_ms` / `duty` / `wellfill_pct` (three definitions of one quantity; duty = t/t_max) | `model.py:881-902` | "distinguish integration time from frame interval" (`TRM4_Application_Changes.pdf` p.8) |
| Capacity | `storage_e`, `sat_e`, ADC full scale = 2^bits × `lsb_e` → usable = min | `model.py:356-382` | Research review §3.6 |
| Cold shield | `cs_mode`: `cs_eff` ↔ `cs_F` (Eq. 2.10 converts) | `model.py:801-815` | – |
| Noise source | `noise_mode` (calculated vs measured) duplicates the whole charge-noise chain; `netd_mK` vs `measured.netd_mK` | Mutually exclusive (`model.py:961-990`); the validation NETD is compare-only (`model.py:2194-2202`) | Field map §15.4: measured NETD and modelled electronics are alternatives (`TRM_Imaging_Research_Engineering_Field_Map_HE_v1_1.pdf` p.25) |
| Spatial noise | `fpn_mode` with `ietd_mK` / (`prnu_pct`, `dsnu_A`) / `fpn_fraction` | `model.py:999-1008`, `model.py:1095-1104` | "do not assume a universal fixed fraction of NETD" (`TRM4_Application_Changes.pdf` p.4), yet the default is estimate 0.5 (`presets.py:358`) |
| Quantization | `adc_mode` with `lsb_e` / `lsb_mK`; `adc_bits` | `model.py:912-918` | – |
| Transmission scalars | `tau_opt` × `tau_filter` × `qe_scale` × `tau0` (atmosphere) — identical OAT signatures in Visible (-2.5/-3.9/-2.0) | `model.py:521`, `model.py:442`, `model.py:123` | – |
| Atmosphere | σ ↔ V (σ = 3.912/V, Visible only); preset → σ, τ0, V; three atmosphere slots, but analyses use only slot 1; `T_air`/`F_PR` have duplicate widgets in spectral mode (gui 739-740 vs 288-290) | `model.py:631-639`; `analysis.py:155` | "Do not equate visual visibility with a universal infrared extinction coefficient" (`TRM4_Application_Changes.pdf` p.9) |
| Turbulence | Cn² fixed / height (cn2, h_ref, time) / r0 (r0, λ, L); `cn2_preset` writes cn2 and mode | `model.py:1516-1538`; `gui.py:3004-3010` | – |
| Illumination level | `E_peak`, `E_eff`, `E_mono`, `T_bb_K`, `T_colour_K`, `preset` (six ways) | `model.py:570-608` | – |
| Motion off | `stab.neglect` (legacy) = `jitter_mode = none` | `model.py:1351` | – |
| Eye off | `display.neglect_eye` and observer = algorithm both remove the eye MTF | `model.py:1602` | – |
| Magnification | `dsp.zoom` vs `lrep`/`crep`; display `distance_cm` vs `f_eyepiece_mm`; display pitch_v | `model.py:335-345` | – |
| Imported-MTF metadata | `mtf_meta` (free text) vs `mtf_band`/`focus`/`temp`/`uncert`; `atmosphere.meta.source` vs `rt_code`/`database` | `model.py:1284`, `model.py:1889-1906` | – |
| Task criteria | `target.preset` (sets tasks) vs `task_preset` vs per-task lp | `gui.py:2969-2987`; `model.py:504-510` | – |

#### 2.3 Values overwritten by presets, profiles and lookups (hidden coupling)

| Trigger | What it overwrites | Source |
|---|---|---|
| Category change | `imager_type` (cooled / staring) | `gui.py:2966-2968` |
| Target preset | W, H, D, T_bg, dT, task lp and on/off; sets task_preset = target | `gui.py:2969-2979` |
| Task preset | the three lp values | `gui.py:2980-2987` |
| Natural-source preset | E_peak | `gui.py:2988-2990` |
| Atmosphere preset | σ, τ0 (= 1.0), V for all three slots; mode = extinction | `gui.py:2991-3003`, `presets.py:222-236` |
| Cn² preset | cn2, cn2_mode = height, h_ref = 2, time | `gui.py:3004-3010` |
| Manual edit of a preset-controlled value | Flips the preset to "custom" | `gui.py:2908-2918` |
| Camera profile apply | Whole `category`, `imager_type`, `basic`, `detector`, `dsp` sections plus 31 optics keys; provenance set | `profiles.py:24-30`, `profiles.py:151-173` |
| Detector Atlas apply | imager_type, n_h, n_v, pitch_h/v, frame_rate (= max fps), noise_floor_e, netd_mK, **T_cs_K ← FPA operating temperature**, cut-on/off (uncooled), qe_preset or qe_custom (flat 70 % if unknown), plus mode switches (qe_preset = Custom, cs_mode, adc_mode, uncooled_response). **Active size is not updated.** | `detector_atlas.py:377-407`, `detector_atlas.py:274-324`, `gui.py:4503-4541` |
| Claude-API detector lookup | Also active size, storage, dark current (from A/cm²), LSB, cold-shield F#, t_th | `detector_lookup.py:18-39` |
| Sensitivity sweep policies | Pitch → active size and d_um (and f for keep-FOV); f → D or F_general; D/F with measured NETD → note only | `analysis.py:204-293` |

#### 2.4 Unit inconsistencies (all labelled, but mixed)
- **Angles:**
  - random and sinusoidal jitter in mrad, linear rate in mrad/s (`gui.py:631-640`);
  - jitter files in urad, mrad or pixels; PSD in urad²/Hz, mrad²/Hz or pixel²/Hz (`gui.py:621-628`);
  - FOV in degrees (`gui.py:315`);
  - IFOV shown in urad in the derived panel (`derived.py:51`) but in mrad in System data (`model.py:2709-2710`);
  - additional MTF parameter in cycles/mrad, labelled "1/mrad" (`gui.py:648`).
- **Lengths:** pitch and active size in µm; f, D and eyepiece focal length in mm; display pitch in mm; viewing distance in cm; target size and altitude in m; ranges in km; r0 in cm with its path in km; L0 in m (`gui.py:355-786`).
- **Time:** t_eye in s, all other times in ms (`gui.py:610` vs `gui.py:339-343`, `gui.py:490`).
- **Charge:** `storage_e` in "carriers" while `sat_e` and read noise are in "e-"; the LSB is in "carriers" (`gui.py:495`, `gui.py:500`, `gui.py:521`, `gui.py:526`).
- **Currents:** dark current and DSNU in A per pixel (`gui.py:515`, `gui.py:553`). Datasheets give nA/cm² or e-/s/pixel, and the lookup prompt asks for conversion from A/cm² (`detector_lookup.py:31`).
- **Fractions vs percent:** transmissions, reflectivity and emissivity are fractions; QE presets, PRNU, well fill and fill limit are %; custom QE is auto-detected (`model.py:424-429`).
- **Photometric vs radiometric:** display luminance in cd/m² (converted internally to fL, `mtf.py:226`); irradiance in W/m² (E_eff, E_mono) vs W/(m² µm) (E_peak).

#### 2.5 Validation coverage
- **GUI:** type parsing only (`gui.py:3110-3135`). The derived panel warns on:
  - f, n or pitch ≤ 0 (`derived.py:34-35`);
  - F < 0.5 (`derived.py:95-96`);
  - obscuration ≥ D (`derived.py:77-79`);
  - band/category mismatch (`derived.py:110-115`);
  - t_int > t_max (`derived.py:128-130`);
  - rolling readout settings (`derived.py:135-138`);
  - a > pitch (`derived.py:141-143`);
  - measured FOV (`derived.py:144-150`);
  - display too small (`derived.py:155-156`).
  - The sweep rejects cases whose new warnings contain the hard words `impossible`, `must be > 0`, `larger than the pitch`, ... (`analysis.py:296-307`).
- **Engine hard errors (ModelError):**
  - category; f; pitch and active size; frame rate; rolling readout; timing ≤ 0; hardware max < min; IIR α; observer; QE basis; dark table; cut-off ≤ cut-on; custom QE (rows, negative, zero) (`model.py:184-438`);
  - τ outside [0,1] (`model.py:516-518`);
  - missing import files (`model.py:523-524`, `model.py:693-694`, `model.py:706-707`, `model.py:1251-1252`, `model.py:1396-1397`, `model.py:1448-1449`);
  - V ≤ 0; σ < 0; τ0 outside (0,1] (`model.py:633-641`);
  - F ≤ 0; aperture; obscuration (`model.py:774-783`);
  - well fill without capacity (`model.py:893-894`);
  - MTF field and unit (`model.py:1258-1267`);
  - r0 reference conditions (`model.py:1531-1533`);
  - rel_illum (`model.py:1932-1933`);
  - PSD unit (`model.py:1463-1464`);
  - coverage overlap (`model.py:48-56`).
- **Unvalidated inputs with physical bounds (found by reading the code):**
  - `optics.q` (should be ≥ 1; label only, `gui.py:403`);
  - `detector.cte_h/_v` (≤ 1);
  - `detector.duty` (≤ 1; t can exceed t_max silently);
  - `detector.electron_gain` (> 0; 0 → ZeroDivision at `model.py:896`);
  - `target.W_m`, `H_m` (> 0);
  - `target.T_bg_K` and `irradiance.T_*` (> 0 K);
  - `display.snr_th`, `t_eye_s`, `distance_cm` (> 0);
  - `turbulence.cn2` (≥ 0);
  - `atmosphere.atm.N.F_PR` (≥ 0);
  - `detector.wellfill_pct` (0–100);
  - `detector.qe_scale` (≥ 0);
  - `target.tasks.N.lp` (only ≤ 0 is dropped);
  - reflectivity and emissivity scalars (0–1);
  - `detector.noise_figure` (≥ 1);
  - `stab.*` amplitudes (≥ 0).
- **Tests:** 154 unit tests. They cover geometry, sampling, radiometry, noise, MTF import, atmosphere, turbulence and motion, edge cases, provenance, analyses, the advisor and the research-review items, plus template DRI references within 0.5 % (`tests/test_dri_reference.py:14-33`; count from grep `def test` in `tests/*.py`). There are no tests of per-field range validation (`tests/test_edge_cases.py:42` tests only a few invalid inputs).

#### 2.6 Parameters that are hard for a user to know
- **Cold shield and internal radiation:** cs_eff or cs_F, T_off_dev, T_off_opt, T_cs (`gui.py:529-539`). Dewar data are rarely on datasheets.
- **Gain and noise chain:** noise_figure, electron_gain, lsb_e and adc_mode, storage node (cap_node, sat_e), op_mode. The research review stresses that capacity, read noise and conversion gain are mode-specific (`TRM4v3_Research_Improvements_English.pdf` p.5).
- **Spatial noise:** fpn_fraction, IETD, PRNU and DSNU (DSNU in A).
- **Optics quality:** q, blur σ, crosstalk "MTF at Nyquist", CTE/n_transfers.
- **Observer:** snr_th, t_eye, display luminance, pitch, distance. These are observer-calibration constants, not system data.
- **Atmosphere:** τ0 ("initial transmission"), F_PR (path-radiance factor), T_air, Cn², h_ref and day/night, r0 with its reference conditions, L0.
- **Illumination:** E_peak and colour temperature for non-preset sources; β_h/β_v angles.
- **Range-geometry semantics:** target.alt_m vs altitude_m vs angle_deg; ref_range_km.
- **Help text:**
  - 38 GUI fields have no help text, including all v2.4 additions: qe_basis, cap_node, sat_e, exposure budget, dark table, noise_port, bin_kind, exposure timing, rel_illum, MTF metadata, L0, smear_allow, atmosphere versioning and part of measured.meta. Source: `help_for()` check over all GUI paths, `help_text.py:441-446`.
  - Two help texts disagree with the code: `target.alt_m` (help: slant geometry; code: turbulence only, `model.py:1512`) and `mode.ref_range_km` (help: plots only; code: also spectral weights and motion exposure, `model.py:1716`, `model.py:1726`).

#### 2.7 Semantic and modelling issues found while tracing parameters
- **NIIRS side effect:** `mode.niirs = True` silently forces still-frame noise in the DRI calculation (`model.py:188`).
- **Algorithm observer:** removes the eye and display but keeps the human SNR_th and lp criteria. This gives +58 % to +265 % ranges, labelled "uncalibrated" (`model.py:486-492`, `model.py:2328-2331`; switch test).
- **Sharpening ignored entirely:** a sharpening FIR with credit_boost = False is dropped completely, including its noise-bandwidth effect, not only the boost (`model.py:1577-1580`, `model.py:1587-1593`).
- **Exposure checks differ by mode:** direct and duty exposures are checked only against t_max, not against the timing or hardware limits used by well-fill mode (`model.py:884-890` vs `model.py:897`).
- **Motion exposure taken at R_ref:** for Visible/General, motion blur uses the exposure at R_ref (`t_ref`, `model.py:1726`, `model.py:1384`), while signal and noise use a per-range exposure in well-fill mode (`model.py:1091-1092`).
- **Thermal NETD at zero range:** Thermal NETD and MTDP are computed once at zero range (`model.py:1711`, `model.py:959-998`). Range-dependent background and path radiance do not change the noise; this is TRM4 behaviour.
- **Display element count unused:** display n_h/n_v have no physical effect. The display MTF assumes one display element per displayed sample (`mtf.py:182-184`), even though TRM4 calls a too-small display "fatal" (`model.py:336-339`).
- **Atlas mapping risks:** the Atlas apply leaves the active size unchanged when the pitch changes (`gui.py:4503-4541`, no a_h/a_v handling), maps the FPA temperature onto the cold-shield temperature (`detector_atlas.py:398-399`), and sets the frame rate to the maximum fps (`detector_atlas.py:394`).

### Inferences
- **Remove or merge candidates** (zero effect and no traceability value beyond what other fields give): `display.algo_roc`, `dsp.pl_order`, `dsp.pl_version`, observer "human", `stab.neglect`, `display.n_h/_v` and `pitch_h_mm` (or make them physical), `basic.fov_*` (keep as a measured cross-check), `optics.F_spec`, `optics.rel_illum` (or make it affect the edge-of-field range), and `measured.netd_*` (duplicate of the NETD test conditions).
- **Group H/V pairs and redundant scalar factors.** Show a single "symmetric" input by default and keep the second axis behind an "anisotropic" switch. Several scalar factors are numerically interchangeable for the range (τ_opt, τ_filter, qe_scale, τ0) and could be presented as one "throughput" budget with a breakdown.
- **Hidden-but-active defaults are the main correctness and usability risk:** FPN = 0.5 × NETD, LSB = 1000 e-, read noise = 500 e-, SNR_th, eye time, display magnification. They should either be shown with a provenance badge of "assumption" or have their group `active` predicates changed to "contributes to the result".

### Gaps
- **Untested parameter interactions:** I did not test combined effects, for example whether the qe_basis effect re-appears in direct-exposure mode with a fill factor below 1, or how ref_range interacts with motion in well-fill mode. Their magnitude is unquantified.
- **TRM4 reference for snr_th / t_eye:** whether the TRM4 original exposes snr_th and t_eye as user inputs could not be confirmed beyond the app's own comment that they are the "standard observer" values (`model.py:494-496`).

---

## Q3. What do presets.py and profiles.py define, and what do analysis.py and advisor.py already do?

### Takeaway
- **Presets and profiles:**
  - `presets.py` holds the Appendix-C preset data and the defaults:
    - 10 QE curves;
    - 18 materials with spectral reflectance and emissivity;
    - 5 natural sources;
    - 24 Cn² presets;
    - per-band atmosphere presets;
    - 3 thermal targets and 5 task-criteria presets;
    - preset lifecycle metadata;
    - `DEFAULT_PROJECT` and 8 templates.
  - `profiles.py` turns the templates into 8 built-in camera profiles (including one dual-FOV profile) and stores user profiles as JSON.
- **Analyses (Sensitivity tab):**
  - `analysis.py` provides limiting factors (8 what-if removals), 1-D and 2-D sweeps with dependency policies, uncertainty (one-at-a-time, RSS/GUM with correlations, and Monte Carlo) and scenario comparison.
  - `advisor.py` adds the "Improve performance" counterfactual advisor:
    - a frozen baseline;
    - bottleneck diagnosis;
    - normalized sensitivities on 8-10 inputs;
    - a catalogue of 8-12 consistent actions;
    - top 3 ranking with a FOV constraint;
    - paired robustness;
    - a "measure first" list.

### Cited Findings

#### 3.1 presets.py

| Item | Content | Source |
|---|---|---|
| Detector QE (`DETECTOR_QE`) | CCD silicon; InGaAs; extended InGaAs; CMT MWIR; QWIP MWIR; InSb MWIR; XBn 3.6–4.2 µm (not from Appendix C); CMT LWIR; QWIP LWIR. Curves digitised approximately; plus "Custom". | `presets.py:12-36`, `presets.py:157` |
| Spectral reflectance / emissivity | 18 materials (vegetation, man-made, soils, rocks, target paints and metals), 0.4–2.5 µm reflectance and 2.5–14 µm emissivity | `presets.py:41-111` |
| Natural sources | Direct sunlight 1239, overcast 14.19, full moon 1.74e-3, quarter moon 7.84e-4, starlight 7.04e-4 W/(m² µm) peak, with blackbody or tabulated shapes | `presets.py:117-125` |
| Cn² Table C.2 | 3 climates × night/noon × 4 percentiles → 24 presets at 2 m height | `presets.py:131-138`, `presets.py:240-244` |
| Eye Γ (Table 4.2), phosphors (Table 4.1, unused "for future ICCD use") | – | `presets.py:141`, `presets.py:153-155` |
| Thermal targets (Table 2.1) | STANAG 4347 2.3 × 2.3 m, ΔT 2 K, 1/3/6 lp; handheld objects 0.08 × 0.70 m, 1 K, 2.5/3.5/5.4; persons 0.6 × 1.7 m, 2 K, 1/2.5/(6 off) | `presets.py:144-151` |
| Atmosphere fast presets (1/km) | VIS/NIR 0.17/0.39/1.30; SWIR 0.10/0.25/0.90; MWIR 0.15/0.30/0.80; LWIR 0.20/0.40/1.00 (clear/average/adverse; "assumptions, not measurements"); band chosen from the QE window | `presets.py:171-196` |
| Task criteria presets | legacy 1/3/6; Sandia 1/4/8; Johnson 1958 1/4/6.4; from target; custom | `presets.py:246-265` |
| Preset lifecycle | Source, date, applicability, uncertainty and warning for each family (qe, material, source, cn2, atmosphere); version "preset data 1.1" | `presets.py:268-305` |
| Data-source categories (provenance badges) | preset, assumption, user, manufacturer, measurement, import, profile | `presets.py:307-310` |

**Templates** (`presets.py:452-558`; reference DRI in `tests/reference/template_ranges.json`):

| Template | Key settings | Atm-1 D/R/I (km) |
|---|---|---|
| LWIR cooled CMT 640×512 | Defaults: f 100, D 50 (F/2), 15/14 µm, well fill 50 %, 1.5e7 e-, read noise 500 e-, LSB 1000, FPN est. 0.5, STANAG, σ 0.2/1.0 | 9.13 / 3.41 / 1.74 |
| MWIR cooled InSb | f 200, D 50 (F/4), 7e6 e-, fill 60 %, read noise 300, LSB 500, τ0 0.8 | 14.48 / 6.42 / 3.35 |
| MWIR XBn 3.6–4.2 µm | As InSb + XBn QE, T_cs 150 K | 13.20 / 6.52 / 3.49 |
| LWIR uncooled 640×480 17 µm | f 50, D 50 (F/1), τ 0.9, NETD 50 mK (device), t_th 10 ms, 30 Hz | 5.25 / 1.80 / 0.91 |
| Visible CMOS 1920×1080 | f 100, D 25, 5 µm, t_int 0.25 ms, 2e4 e-, read noise 5, PRNU 0.5 %, DSNU 4e-17 A, sun at β 30/45, V 23/5 km, turbulence Cn² 1e-14 | 14.73 / 8.18 / 5.00 |
| SWIR InGaAs 640×512 | f 150, D 75, 15 µm, t_int 30 ms, 1e6 e-, read noise 30, full moon, V 23/5 km | 9.04 / 4.78 / 2.66 |
| General MWIR sun-lit | InSb, ΔT 5 K, spectral emissivity (olive paint on green grass), sunlight, τ0 0.8, F_PR 0.05 | 18.27 / 7.63 / 3.98 |
| NIIRS airborne visible | 4096×3072, 5.5 µm, f 500, D 100, altitude 3 km, jitter 3 µrad, Cn² height model 1e-13 | (NIIRS output) |

#### 3.2 profiles.py
- **Content of a profile:** a profile is `{name, vendor, source, notes, sensor, configs[{name, optics}], provenance, calibration_date}`.
  - The sensor part covers `category, imager_type, basic, detector, dsp`.
  - Each optical configuration holds 31 optics keys: aperture, D, F, f, transmission, MTF source and metadata, aberration, rel_illum.
  - Source: `profiles.py:24-30`, `profiles.py:176-187`.
- **Not part of a profile:** display, stabilization (platform jitter), target, atmosphere, turbulence and observer. They are treated as scene or observer data (`profiles.py:24`).
- **Built-in profiles:** the 7 non-NIIRS templates plus "Generic: MWIR cooled 640x512, dual FOV" (WFOV f = 60 mm / NFOV f = 240 mm at F/4) (`profiles.py:95-109`).
- **User profiles and identity:**
  - User profiles are `profiles/*.json` (`profiles.py:22`, `profiles.py:112-125`).
  - `stamp()` adds profile_id, schema_version, channel, source_id, calibration_date, file hashes and a content hash (`profiles.py:65-82`).
- **Validation:** only f > 0 and active size ≤ pitch (`profiles.py:132-148`).
- **Applying a profile:** sets provenance to the profile's source for every applied leaf (`profiles.py:151-173`).

#### 3.3 analysis.py (Sensitivity tab; `README.md:130-142`)

| Feature | Details | Source |
|---|---|---|
| Engine contract | Clone → policy → validate (derived hard warnings) → full model run → D/R/I + diagnostics; atmosphere 1 only; criteria never changed | `analysis.py:1-29`, `analysis.py:299-307`, `analysis.py:413-433` |
| Runner | Process pool (cores - 1, max 8; `TRM4_WORKERS`), identical results to a serial run | `analysis.py:55-118` |
| Limiting factors | Removes one degradation at a time: aberration, detector footprint, noise ×0.5, FPN, eye, atmosphere, LOS motion, turbulence. Ranked by gain on the last task. Classifies sampling vs sensitivity per task. | `analysis.py:313-398` |
| Sweep 1-D / 2-D | Any float or int GUI field except lp and measured.* (`gui.py:1408-1410`); linear or log grid; dependency policies (pitch ff2/ff1/keep_a/keep_fov; f keep_D/keep_F; D; F; n); same-quantity 2-D pairs rejected | `analysis.py:204-293`, `analysis.py:404-495` |
| Uncertainty | 16 default inputs with typical ± % (NETD 20, read noise 20, dark 50, ΔT 25, reflectivities 15, W/H 10, σ or V 30, f 2, τ 5, q 10, jitter 30, Cn² 50), filtered to the applicable ones; meaning (bound / 95 % / 1σ) and distribution (normal, uniform, triangular, lognormal); one-at-a-time tornado, RSS with correlations (GUM), Monte Carlo with Gaussian copula and seed | `analysis.py:502-805` |
| Scenarios | Compare saved project snapshots against the first one | `analysis.py:814-837` |

#### 3.4 advisor.py ("Improve performance"; `README.md:84-100`)

| Feature | Details | Source |
|---|---|---|
| Baseline | Frozen snapshot, `baseline_id` = B-<run-id>, model version, geometry | `advisor.py:90-99` |
| Diagnosis | Per task: sampling (lp > cycles at Nyquist), SNR (contrast/noise limiter) or optics; overridden by the top limiting factor when its gain is over 15 %; separation test text | `advisor.py:118-173` |
| Local sensitivities | S = (x/R)·dR/dx by ±5 % central differences on f (D fixed), D or F, pitch (ff2), τ_opt, NETD or read noise, t_int (Visible direct), V or σ, ΔT (not Visible), target H, random jitter h; zero-effect inputs flagged | `advisor.py:179-251` |
| Action catalogue | Longer lens at the same F#; longer f at the same D; faster optics; smaller pitch at the same FOV ("approx", incomplete detector); more pixels; NETD ×0.75 or read noise ×0.5; lower frame rate (Thermal, well fill, video); longer t_int (non-thermal direct); τ × 1.10; diffraction-limited optics (what-if); stabilization ×0.5; clearer atmosphere (scenario only). Evidence levels: model / approx / measure. | `advisor.py:261-369` |
| Ranking | Top 3 materially different groups for the decisive (last) task inside min-FOV; Pareto flag (gain vs FOV); no-effect threshold 0.5 % | `advisor.py:513-593` |
| Robustness | Paired base / action runs on the low/high values of up to 3 assumptions (atmosphere, ΔT, H, t_refl, Cn²) | `advisor.py:428-469` |
| Measure first | Theoretical MTF, calculated NETD, generic QE, preset target or atmosphere, no LOS motion → the measurement to make (ISO 12233, ASTM E1543, EMVA 1288) | `advisor.py:475-507` |
| Not in the catalogue (by inspection) | QE or band change; cold-shield or F-matched dewar; integration time for cooled thermal (only via frame rate); frame averaging or IIR; display, observer, magnification; binning or micro-scan; aperture obscuration; turbulence mitigation; spectral filter; target-specific criteria | `advisor.py:261-369` |

### Inferences
- **Analysis features already exist:** limiting factors, sweeps with consistency policies, GUM/MC uncertainty and a counterfactual advisor are all implemented and tested. A new plan should not re-propose these generically.
  - **Gap 1, sweep pre-filtering:** the sweep list offers parameters with zero range effect (display n, fill limit, F_spec, ...) without warning.
  - **Gap 2, advisor coverage:** the advisor does not reach the observer, display, DSP and spectral-band levers, although the OAT run shows these levers (zoom, eye, frame averaging, SNR_th) can be as large as hardware changes.
  - **Gap 3, uncertainty defaults:** the uncertainty defaults omit high-effect inputs found here: D, pitch, lp, SNR_th, binning and observer.
- **Profiles exclude platform data.** Profiles leave out the display and the platform jitter, so a "camera + platform" configuration cannot be saved as one unit.

### Gaps
- **Advisor run time on the daylight CMOS template:** not re-run. The README claims about 5 min with turbulence (`README.md:37-41`); I did not measure it.

---

## Q4. What do the in-repo documents say, and which improvements were already proposed or implemented?

### Takeaway
- **Five improvement documents.** The repository contains five improvement documents (9–25 Oct 2026) and the Fraunhofer TRM4.v3 documentation. Each improvement document maps to a README version that lists what was implemented:
  - roadmap → v2.0;
  - sensitivity plan → v2.1;
  - field map → v2.2;
  - advisor → v2.3;
  - research review → v2.4.
- **Common thread:** all of them keep the TRM4 physics and Johnson/AMOP criteria. They add input semantics, data precedence, traceability, uncertainty and diagnostics.
- **Still not done:** observer calibration, TTP/TOD, NPS-driven noise, BRDF, measured end-to-end SFR replacing the prediction, clutter, Cn² profiles, and the laboratory tools.

### Cited Findings

| Document (date) | Main proposals | Implemented (README) | Explicitly not implemented / deferred |
|---|---|---|---|
| `TRM4_Application_Changes.pdf` (09 Oct 2026, 12 pp.) | Quick/Engineering/Lab workflows; KEEP / SIMPLIFY / ADVANCED / REMOVE table per input (p.3-5); camera profiles; one principal F#/D entry; MTF data precedence A/B/C and import contracts (p.7); detector branching and noise separation (p.8); fast + spectral atmosphere, path radiance, turbulence, measured jitter (p.9); dashboard and diagnostics (p.10); verification plan (p.11); excludes new or adaptive Johnson criteria (p.1, p.12) | v2.0: all workflows, levels, profiles, derived panel, provenance, modes A/B/C, imports, detector checks, atmosphere, jitter, dashboard, Sensitivity tab, validation, traceability, 57 tests (`README.md:144-162`) | New criteria; lab frame/video tools (flat-field, dark-frame, slanted-edge from images); Monte Carlo (later added in v2.1); scanners, intensifiers, CRT (`README.md:164-169`) |
| `Sensitivity_Analysis_Improvements.pdf` (09 Oct 2026, 8 pp.) | Separate OAT / RSS / MC; uncertainty meaning and distribution; correlations; no "credible interval"; result state per mode; DRI-vs-parameter sweeps with hold-constant policies (p.5-6); limiting factors vs uncertainty drivers vs design variables (p.7); 2-D heatmap, scenarios (p.7-8) | v2.1: all P0-P2 items, `tests/test_analysis.py` (`README.md:130-142`) | Image simulation is explicitly out of scope ("NOT A SIMULATED IMAGE", p.6) |
| `TRM_Imaging_Research_Engineering_Field_Map_HE_v1_1.pdf` (14 Oct 2026, 29 pp., Hebrew) | Ch. 15 per-page change table (p.19-20); source-of-truth matrix and no double counting (p.25); Optics MTF source + coverage (P0); noise source selector (P0-P1); motion source incl. PSD (P0); target, irradiance and atmosphere (P1); observer types (P2); no "Sharpness" factor (p.26); Johnson vs TTP vs TOD vs ideal observer as parallel metrics, TTP as an optional engineering path (p.10-12) | v2.2: COMPONENTS / `check_coverage`, MTF sources, NETD conditions, NPS QA, rolling shutter, SP-01 sharpening not credited, observer types, PSD, criteria presets, r0 with reference, run ID, scenario record, 34 tests (`README.md:102-124`) | TTP/TOD research comparison; calibrated detection probabilities; NPS-driven noise model; measured end-to-end SFR replacing the prediction; clutter modelling (`README.md:126-128`) |
| `TRM_Range_Improvement_Advisor_Scientific_RTL_Hebrew.pdf` (Oct 2026, 19 pp., Hebrew) | Baseline snapshot; ΔR and Gain %; evidence levels (Ch. 2); bottleneck types and separation tests (Ch. 4, p.6-7); counterfactual actions as consistent parameter groups; utility/Pareto; S_i sensitivities; paired MC robustness (Ch. 5, p.7-8); parameter-improvement matrix covering f, D/F#, p, format, focus, MTF, T(λ), QE/noise, NETD, exposure, jitter, processing, atmosphere and clutter (Ch. 6, p.9); complete hardware profile before component swaps (p.9) | v2.3: `advisor.py`, Hebrew PDF report, tests T-01 … T-10 (`README.md:84-100`) | Multi-criteria utility with cost, mass and power (Score = w_R·Gain - w_C·Cost - …, p.8) is not implemented (ranking is by range gain plus a FOV constraint, `advisor.py:558-568`); focus is not a parameter in the app |
| `TRM4v3_Research_Improvements_English.pdf` (25 Oct 2026, 16 pp.) | 26 findings (§3.1-3.26). Critical: QE basis, saturation node, imported MTF once (p.2, p.4-5). Exposure budget and SWIR worked example (§4, p.9-12). Lab test plan T01-T09 (p.12-13). Input dictionary (§9, p.15). | v2.4: QE basis, capacity node / saturation / ADC, brightest pixel, timing and binning, exposure budget, photon/electron rates, rel_illum (info), dark table, noise port, MTF metadata, atmosphere versioning, L0, preset lifecycle, DRI context, test metadata (`README.md:53-78`) | Observer trials and success probabilities; BRDF and spectral reflectance import; nonlinear (HDR / learned) processing profiles; measured slant-path Cn² profiles; the Sec. 5 bench tests (`README.md:80-82`). Field-dependent throughput is information-only (rel_illum does not affect ranges). Etendue for fast optics is only an assumption note (`model.py:1935-1937`). |
| `TRM4v3_ModelDocumentation_260930_095803.pdf` (Fraunhofer IOSB TR 2021/04, 216 pp.) | Reference model: Ch. 2 parameter dialogs §2.2-2.28 (p.17-102), Ch. 3 performance assessment, Ch. 4 MTFs, App. A-D | Basis of the engine (`model.py:1-13`, `README.md:217-234`) | See Q5 |

Additional doc details relevant to a keep/change/remove plan:
- **Disposition rules.** The roadmap's KEEP / SIMPLIFY / ADVANCED / REMOVE rules are explicitly "proposed engineering decisions, not requirements stated by Fraunhofer" (`TRM4_Application_Changes.pdf` p.12). The app applies them as GUI levels (`gui.py:253-256`).
  - REMOVE so far applies only to electronic/pseudo interlace and the "neglect stabilization" switch (level legacy, `gui.py:345-349`, `gui.py:641-642`).
- **Field-map acceptance rule.** Every added field needs a schema, units, a missing-value policy, a physical range, provenance, a dependency graph and a test ID (`TRM_Imaging_Research_Engineering_Field_Map_HE_v1_1.pdf` p.26). The current GUI meets "units" and "provenance", but not "physical range" (see Q2.5).
- **Advisor document warning.** If doubling f does not improve the range, either the range is limited by contrast, MTF or turbulence, or the parameter is "not connected to the engine", and the two must be distinguished (`TRM_Range_Improvement_Advisor_Scientific_RTL_Hebrew.pdf` p.7). The OAT table in Q1.3 provides exactly this connectivity map.

### Inferences
- **Remaining gaps are calibration and research items.** What remains open in all five documents is calibration and validation (observer trials, probabilities, TTP/TOD), richer scene physics (BRDF, clutter, Cn² profiles) and lab tooling. Parameter-level UX work was already done once (v2.0 levels).
- **Two documented rules are not fully met:** the field-map "physical range per field" rule and the roadmap "no universal fraction of NETD" rule are not satisfied by the current defaults and validation.

### Gaps
- **Hebrew PDF extraction:** the two Hebrew PDFs were read from extracted text (pypdf). Some right-to-left table cells may be scrambled in extraction, so I summarised only the clearly legible content.

---

## Q5. Which modelling capabilities are missing compared with official TRM4.v3 and with NVIPM?

### Takeaway
- **Compared with TRM4.v3, the app does not implement:**
  - scanning imagers, D* specification and 1/f noise;
  - image intensifiers;
  - TDI, frame-transfer smear and temporal detector MTF;
  - the analog / video / ADC / DAC chain and CRT/LED displays;
  - most "External data" MTF imports (detector, display, eye, additional, stabilization, analog filter);
  - spectral (per-wavelength) external optics MTF;
  - two illumination sources and external irradiance spectra;
  - sky background and asymmetric truncation;
  - MCP/MRC-based range performance.
- **Thermal category:** TRM4 itself excludes turbulence for Thermal, so MWIR/LWIR systems in the Thermal category get no turbulence MTF.
- **Compared with NVIPM,** the repository documents only mention TTP/TOD/ideal-observer metrics as missing (the app is Johnson/AMOP only, with no probability-vs-range output). Any further NVIPM comparison must come from external sources.

### Cited Findings

| TRM4.v3 capability (doc section) | Status in app | Evidence |
|---|---|---|
| Opto-mechanical scanning, 1st/2nd generation thermal (§2.5.4, §3.2.7-3.2.8) | Not implemented | `model.py:8`; `README.md:238-240` |
| D* specification / calculation, 1/f knee frequency (§2.10.1-2.10.2, §2.10.9, §2.13.8) | Not implemented (QE + charge-noise model only) | TOC of `TRM4v3_ModelDocumentation_260930_095803.pdf` (PDF pp. 5-7); no D* or knee in `model.py` (grep) |
| Image intensifier and coupling, ICCD/ICMOS/NVG (§2.7-2.8, §3.7.6, §3.11.7) | Not implemented; phosphor table stored "for future ICCD use" | `model.py:8-9`; `presets.py:153-155` |
| TDI mismatch (§2.9.3), frame-transfer smear (§2.9.5), external detector MTF (§2.9.7), temporal detector MTF (§2.10.4) | Not implemented (only the device-prefilter import route C covers a measured detector MTF) | TOC, PDF p. 6; `model.py:1156-1170` |
| Visible responsivity measurement setup (§2.12.2-2.12.3) | Not implemented (QE route only) | TOC, PDF p. 7 |
| Analog signal processing HP/LP/boost (§2.14), ADC MTF (§2.16.2), video processing / DAC / output signal (§2.17) | Not implemented | `model.py:9`; TOC, PDF p. 7 |
| CRT / LED displays (§2.18.2-2.18.3); external display and eye MTF (§2.18.6, §2.18.9) | Flat panel only; eye model fixed | `model.py:7-10`; `mtf.py:182-235` |
| External stabilization MTF (§2.19.3), external additional MTFs (§2.20.2) | Replaced by jitter time series / PSD import; additional MTFs analytic only | `gui.py:612-649` |
| External optics MTF, spectral (§2.6.8) | Only polychromatic MTF per field; spectral MTF not supported | `zemax.py:121-126` |
| Two illumination sources (§2.26.1); external normalized spectral irradiance (§2.26.5) | Single source, presets or analytic shapes only | `README.md:239-240`; `model.py:570-608` |
| Sky background (upward look) | Not implemented (warning) | `model.py:678-681` |
| Asymmetric aperture truncation | Not implemented | `model.py:10` |
| Range performance from measured MCP/MRC (§3.12.5) | Not implemented: a measured MCP is compare-only; only Thermal MTDP/MRTD can replace the model | `model.py:2138-2147` |
| Turbulence for the Thermal category | Not available (also restricted in TRM4: "active for imager categories Visible and General only") | `model.py:1502-1504`; `TRM4v3_ModelDocumentation_260930_095803.pdf` p.99 |
| Implemented TRM4 core | Staring cooled / uncooled / visible / general; binning, micro-scan, pseudo-interlace; diffraction by pupil overlap; aberration; cold shield; noise (3.130), NETD, IETD, PRNU/DSNU; FIR, zoom, replication, frame integration; flat panel + Kornfeld-Lawson eye; vibration MTFs; Beer-Lambert + Koschmieder + path radiance; turbulence with fixed or height Cn²; AMOP simulation, MTDP/MDSP/MCP; Johnson ranges; NIIRS GIQE 5 | `README.md:217-234` |

**NVIPM and other task-performance models** (only what the in-repo docs state):
- **TTP and other metrics.** The field map lists Johnson vs TTP vs TOD vs the ideal observer (d'/ROC) as parallel frameworks.
  - It recommends keeping Johnson as the legacy baseline and adding TTP only as an optional, calibrated engineering path, never as an automatic replacement.
  - It cites TNO comparisons that found differences between TOD, NVTherm and TRM3 for undersampled systems, and a later NV-IPM TTP change that helped one target set but hurt another.
  - Source: `TRM_Imaging_Research_Engineering_Field_Map_HE_v1_1.pdf` p.10-12.
- **Not implemented:** "TTP/TOD research comparison, calibrated detection probabilities" (`README.md:126-127`). The dashboard explicitly claims no probability (`model.py:2324-2335`).
- **Advisor bibliography:** cites Vollmerhausen, Jacobs and Driggers (2004) on the new TTP metric (`TRM_Range_Improvement_Advisor_Scientific_RTL_Hebrew.pdf` p.19 bibliography; `report_he.py:782`).

### Inferences
- **Missing TRM4 features target legacy hardware.** The missing TRM4.v3 features are mostly legacy-hardware branches (scanners, intensifiers, analog video, CRT) that the roadmap deliberately classed as REMOVE / optional (`TRM4_Application_Changes.pdf` p.3-5, p.12). The ones that matter for modern staring EO/IR are:
  - per-wavelength external optics MTF;
  - external display and eye MTFs;
  - temporal detector MTF and TDI (for scanning or TDI line sensors);
  - two illumination sources;
  - measured MCP-based ranges for Visible;
  - turbulence for MWIR/LWIR. This requires deviating from TRM4's category rule, for example by running MWIR in the General category, or by an explicit extension.
- **NVIPM-class outputs (inference, not sourced in the repository):**
  - probability of task performance versus range (a TTPF curve rather than single thresholds);
  - the TTP metric with V50 task difficulty;
  - explicit sampling or aliasing penalties;
  - noise- and clutter-limited detection;
  - These are absent from the app according to its own README and dashboard wording. The exact NVIPM feature list must come from the external research stream.

### Gaps
- **External sources not consulted:** no official NVIPM documentation is in the repository. Its feature set (TTP implementation details, V50 tables, reflective-band models, display models, laser-illuminated active imaging, sensor-noise 3-D model) could not be verified here and needs external sources.
- **Partial TRM4 coverage check:** the Fraunhofer documentation was checked through its table of contents and §2.28 only. A full parameter-by-parameter comparison of the 216-page TRM4 dialogs with the app's 302 keys was not done.
