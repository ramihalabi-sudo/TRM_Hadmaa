# EO/IR Range-Performance Models: Methodology, Validation, Tool Landscape and Sensitivity Practice (TRM4 / NVIPM / Johnson / DRI)

Scope note: Research as of 28 Oct 2026. Pre-2000 sources are marked **[foundational]**. One primary source is the licensed Fraunhofer IOSB document *TRM4.v3 Parameter Description and Model Documentation* (Fraunhofer IOSB Technical Report 2021/04), which is in the project folder at `C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf`. It is cited below as "TRM4.v3 Doc" with section numbers. It is copyrighted (BMVg/BAAINBw right of use), so the notes summarise it and do not reproduce it.

---

## Q1. What are the key equations and parameters of AMOP/MTDP in TRM4? How does TRM4.v3 differ from earlier versions? Which inputs are required and which are defaults?

### Takeaway
TRM4 is a deterministic, bar-pattern ("modified Johnson") model. It replaces the system MTF with AMOP (Average Modulation at Optimum Phase), which is found by simulating a 4-bar pattern through the sampled imager. AMOP and the perceived noise give MTDP (thermal) or MDSP/MCP (reflective/general). The range is where the atmosphere-attenuated target signal equals the task-scaled MTDP/MDSP, with the task given only as a number of line pairs. TRM4 itself outputs no probability-vs-range curve. TRM4.v3 (Sept 2021) added image-intensifier/NVG/direct-view systems, MCP for VIS–SWIR, NIIRS (GIQE-5), sky backgrounds and interactive help. TRM4.v4 (Aug 2026) added colour cameras, sub-pixel and air-to-air targets, GRD and diagnostic tooltips.

### Cited Findings
**Model structure and equations**
- TRM4 estimates the maximum target–observer distance at which a perception task (D/R/I) succeeds with a specified probability. It uses modified Johnson criteria: the real target is replaced by an equivalent bar pattern whose size, number of line pairs and signal difference depend on the target and task — [Fraunhofer IOSB TRM4 page](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html)
- AMOP replaces the system MTF of earlier models. It was originally developed and validated for undersampled thermal imagers, for which no system MTF is defined, but it applies to all imagers. MTDP is the figure of merit for thermal imagers. MDSP (difference signal in carriers) is the general figure of merit — [TRM4.v3 Doc §1.1](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)
- **MTDP equation (TRM4.v3 Doc Eq. 3.175):** MTDP_z(r_p) = (π/2)·SNR_th·Ψ_z^{1/2}(r_p) / AMOP_z(r_p). Here r_p is the 4-bar spatial frequency, Ψ_z the total perceived (system-filtered) noise variance, SNR_th the eye's threshold SNR, and z the horizontal or vertical direction. MDSP uses the same form, but Ψ and AMOP also depend on range R (Eq. 3.176) — [TRM4.v3 Doc §3.11.2](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)
- **AMOP definition:** for each pattern frequency, the reproduced modulation depends on the phase of the 4-bar pattern relative to the sampling grid. AMOP is the average modulation at the phase that maximises it. AMOP cannot be calculated analytically; TRM simulates imaging of the 4-bar pattern in both directions — [TRM4.v3 Doc §3.11.3](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf). The ECOMOS slides give the average modulation of the reconstructed, post-filtered sampled signal as 1/(2(N_pb−1))·Σ_{i=1}^{N_pb−1}(S_max,i + S_max,i+1 − 2·S_min,i). The optimum phase is the one with the largest average modulation among phases where the maximum number of bars is resolvable — [Keßler & Wittenstein, "ECOMOS Scientific Background: TRM4", ECOMOS workshop, Ettlingen, 21–22 June 2017](https://ecomos.org/wp-content/uploads/2018/01/ECOMOS_20170621_03_TRM4_Background_WS_Kessler.pdf)
- Above about Nyquist, an undersampled imager resolves only 3 or 2 "apparent" (aliased) bars, and MTDP/MDSP still assesses performance there. MTDP is set to infinity when AMOP < 0.1%. In the classical MRTD approach (no longer supported in TRM4), image modulation was approximated as (4/π)·MTF_sys, which is valid only for well-sampled systems — [TRM4.v3 Doc §3.11.2–3.11.3](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)
- **Noise:** temporal and spatial (fixed-pattern) noise are treated as statistically independent and combined by root-sum-square. Noise folding by sampling is included. Perceived noise uses the eye's temporal integration (number of integrated frames) and the noise bandwidths for NETD (temporal) and IETD (non-uniformity) — [TRM4.v3 Doc §3.11.1](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf); [ECOMOS TRM4 slides 2017](https://ecomos.org/wp-content/uploads/2018/01/ECOMOS_20170621_03_TRM4_Background_WS_Kessler.pdf). The temporal noise terms are shot noise (target, background, optics, walls, cold shield), dark-signal noise, ADC quantisation, 1/f and additional noise. The FPN terms are DSNU, PRNU and micro-defects — [ECOMOS TRM4 slides 2017](https://ecomos.org/wp-content/uploads/2018/01/ECOMOS_20170621_03_TRM4_Background_WS_Kessler.pdf)
- When FPN dominates, measured MTDP depends on where the pattern falls relative to the FPN. TRM4 computes an *average* MTDP, and IOSB recommends averaging measurements over several pattern positions — [TRM4.v3 Doc §3.11.1](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)
- **Observer/eye defaults:** recommended threshold SNR = 2.5 and eye integration time = 0.1 s. The eye MTF is a simplified Kornfeld–Lawson model scaled by display luminance and display-to-observer distance (or eyepiece focal length), and it can be replaced by external data — [TRM4.v3 Doc §2.18.7–2.18.9, §4.2.12](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)
- **Range calculation (Thermal category, per STANAG 4347):**
  1. Bar frequency at range R is r = n_lp/a_tar·R (Eq. 3.206).
  2. The Effective Temperature Difference is ETD(R) = N_TDI·ΔT0·τ_atm(R) (Eq. 3.208).
  3. For each direction z, the number of resolved line pairs n_lp_res,z(R) solves ETD(R) = MTDP_z(n·R/a_tar,z) (Eq. 3.210).
  4. The averaged value is n̄ = √(n_h·n_v) (Eq. 3.211).
  5. Range R0 is where n̄ = n_lp_perc (Eq. 3.212).

  Equivalently, the task-dependent MNTD curve intersects ETD (Eqs. 3.215–3.218) — [TRM4.v3 Doc §3.12.1–3.12.3](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)
- **Visible/General categories:** EDS(R) = N_TDI·∫DS(λ,0)·τ_atm(λ,R)dλ, and R0 solves EDS(R0) = MNDS(R0). MDSP depends explicitly on range, through the turbulence MTF, spectral transmission and background shot noise. Unlike the Thermal category, it is not a simple frequency-axis rescaling of a lab curve. This can produce "surprising results like contrast reversal" — [TRM4.v3 Doc §3.12.4, §3.12.6](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)
- **Thermal-category simplifying assumptions:** blackbody target and background, air temperature equal to background, wavelength-independent grey atmosphere, very small contrast. Consequently noise, AMOP and MTFs are range-independent, and MNTD is a linear rescaling of MTDP: MNTD_z(R) = MTDP_z(n_lp_z·R/a_tar_z) (Eq. 3.226) — [TRM4.v3 Doc §3.12.6, Table 3.1](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)
- **Task definition:** up to three tasks are specified at once, and "only the number of line pairs is relevant for TRM4 calculations". The labels D/R/I are auxiliary — [TRM4.v3 Doc §2.24.4](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)

**Built-in standard target models (Thermal category, TRM4.v3 Doc Table 2.1)**

| Model | Size (W×H×D) | T_bkg | ΔT | D | R | I | Atmosphere |
|---|---|---|---|---|---|---|---|
| STANAG 4347 | 2.3×2.3 m | 288 K | 2 K | 1 lp | 3 lp | 6 lp | σ = 0.2/km or 1.0/km |
| Handheld objects | 0.08×0.70×0.08 m | 288 K | 1 K | 2.5 lp | 3.5 lp | 5.4 lp | — |
| Persons | 0.6×1.7×0.4 m | 288 K | 2 K | 1 lp | 2.5 lp | — | — |

  Source: [TRM4.v3 Doc §2.24.5](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf). The handheld data come from Adomeit, Proc. SPIE 8541 (2012).
- TRM4 ships these "standard" sets so that *nominal* ranges can be compared under STANAG 4347 conditions. For real targets, the standard target dimensions, ΔT and atmosphere must be replaced with actual data — [TRM4.v3 Doc §1.3](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)

**Imager categories and atmosphere**
- There are three imager categories: Thermal (emission only, compatible with TRM3), Visible/NIR/SWIR (reflection only) and General (both). Additional features: 3D targets, slant paths, spectral MTFs, uncooled detectors, two illuminators (one may be on the imager platform), turbulence and path radiance — [TRM4.v3 Doc §1.1](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)
- Atmosphere: Beer's-law transmission τ = τ0·e^(−σR) or spectral transmission (MATISSE is mentioned), a path-radiance factor, air temperature, and Kolmogorov turbulence with short- and long-exposure MTFs — [ECOMOS TRM4 slides 2017](https://ecomos.org/wp-content/uploads/2018/01/ECOMOS_20170621_03_TRM4_Background_WS_Kessler.pdf). The TRM4.v3 Doc has dialogs for turbulence (type of MTF; Cn² specified directly or via profile) and for external atmospheric transmission and path-radiance data — [TRM4.v3 Doc §2.27–2.28](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)
- For 3–5 µm imagers, sensitivity and MTDP "may strongly depend on the background temperature". D*/NETD inputs must therefore be valid for the specified background temperature — [TRM4.v3 Doc §2.24.2](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)

**Version history**
- TRM3.v3 (Dec 2003).
- TRM4.v1 (Aug 2010): VIS/NIR/SWIR and General categories, 3D targets, slant path, detailed atmosphere with turbulence and spectral transmission.
- TRM4.v1.1 (Jul 2013): handheld and person presets, TRM3→TRM4 file conversion.
- TRM4.v2 (Jun 2016): uncooled thermal imagers.
- TRM4.v3 (Sep 2021): iCCD/iCMOS, NVGs and direct-view systems; NIIRS for aerial imaging; MCP for VIS–SWIR; targets against sky; interactive help.
- TRM4.v4 (Aug 2026): lab and range calculations for colour cameras; sub-pixel target modelling incl. air-to-air; ground-resolved distance for aerial imaging; diagnostics tooltips.

  Source: [Fraunhofer IOSB TRM4 page](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html)
- The TRM4.v3 overview paper is "Imager performance assessment with TRM4 version 3: an overview", Proc. SPIE 11866 (2021), DOI 10.1117/12.2597723 — [Fraunhofer publica record](https://publica.fraunhofer.de/entities/publication/bea49a7c-9aec-446f-9381-22adf2651ba2); listed on the [TRM4 page](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html). The TRM4.v4 paper is DOI 10.1117/12.3070119 — [TRM4 page](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html). A search-result abstract of the v3 overview (not opened in full; the publica page was bot-blocked) says v3 adds a NIIRS-based image quality metric and extends aerial-imaging support. Another snippet says v3 "features a validated approach to consider aliasing" (unverified paraphrase).
- The model paper is Keßler, Gal & Wittenstein, "TRM4: Range performance model for electro-optical imaging systems", Proc. SPIE 10178 (2017), DOI 10.1117/12.2262543 — [SPIE](https://spie.org/Publications/Proceedings/Paper/10.1117/12.2262543). The original MTDP paper is Wittenstein, Opt. Eng. 38(5) (1999), DOI 10.1117/1.602265 **[foundational]** — [TRM4 page publications list](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html)
- NIIRS in TRM4 uses GIQE-5 inputs: ground sampled distance, relative edge response and difference-signal-to-noise ratio — [TRM4.v3 Doc §3.13](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf); GIQE-5 reference (Harrington et al., NGA 2015) per the [TRM4 page](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html)

**Inputs, defaults and templates**
- The user specifies every component of the chain: scene, atmosphere, optics, sensor, signal processing, display and observer. A built-in library supplies generic spectral data (illuminants, reflectivities, detector sensitivities), and measured MTDP can be used as input — [TRM4 page](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html)
- The package contains templates for different imager types and fixed built-in data sets for reference purposes. A "Modify individual parameters" dialog sets, among other things, the reference range for the MDSP display — [TRM4.v3 Doc §1.2, §2.4](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)
- **Parameter groups** (TRM4.v3 Doc chapter 2):
  - Basic data: FOV, frame rate, sampling, scanning, interlace, micro-scan/dither, binning, number of sensors.
  - Optics: aperture type and dimensions, effective F#, diffraction, aberration, external or spectral MTF, transmission.
  - Image intensifier and coupling.
  - Detector geometry: shape, pitch and fill, TDI mismatch, CTE, smear, MTF at Nyquist.
  - Detector sensitivity by category: D* or NETD, spectral response, integration time, well capacity, ADC, 1/f knee, FPN, temporal noise.
  - Analog and digital processing: filters, boost, frame integration.
  - ADC; video; display (type, luminance, MTF); observation (direct or eyepiece, viewing distance); eye (SNR_th, integration time, external eye MTF).
  - Stabilisation: random, sinusoidal or linear motion MTF.
  - Additional MTFs; prefilter MTF *or* measured MTDP/MCP.
  - Target, background, scenario (aspect front/side/diagonal, constant altitude or constant angle) and task.
  - Irradiance sources; atmosphere; turbulence.

  Source: [TRM4.v3 Doc TOC and §2](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)
- Outputs include system performance parameters, MTFs/AMOP, MTDP/MCP/MDSP, signal/noise/SNR vs range, MNTD/ETD (thermal) or MNDS/EDS, D/R/I ranges and NIIRS — [TRM4.v3 Doc §1.2](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf). Batch mode and customer-specific integrations are available under licence — [TRM4 page](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html)

**Recent research around TRM4 (2020–2026)**
- Pinsky & Yaron (2020), "Range prediction for color imagers: toward a joint TRM and …", Proc. SPIE 11538, 115380G, DOI 10.1117/12.2571247. It combines TRM4 reflective mode with a colour-difference metric, applied per primary colour — [SPIE](https://opticalengineering.spiedigitallibrary.org/conference-proceedings-of-spie/11538/115380G/Range-prediction-for-color-imagers-toward-a-joint-TRM-and/10.1117/12.2571247.full)
- Günther & Keßler (2024), "Concept study for the TRM4 display observer model: effects of glare", Proc. SPIE 13200, 132000V, DOI 10.1117/12.3031651 — [SPIE](https://proceedings.spiedigitallibrary.org/conference-proceedings-of-spie/13200/132000V/Concept-study-for-the-TRM4-display-observer-model--effects/10.1117/12.3031651.full)
- A 2023 Fraunhofer IOSB paper (surfaced as a publica abstract in search) describes ongoing work on sub-pixel targets and colour cameras. It computes the SNR of the extra target signal over target positions on the detector grid and extends AMOP to Bayer sampling and demosaicing — [Fraunhofer publica (record surfaced in search; exact record ID not verified)](https://publica.fraunhofer.de/entities/publication/15bc0083-661c-4312-b21a-01b89c2f1ad1)
- An intensified-camera module for TRM4 is documented on publica — [publica 408257](https://publica.fraunhofer.de/handle/publica/408257)

### Inferences
- TRM4 is "line-pair deterministic". An app that adds probability curves P(R) on top of TRM4 departs from the TRM4 method and needs its own justified TTPF, for example the Johnson/Lawson form under Q2. In the UI it should be labelled as an extension, not as TRM4 output.
- The parameters that most change the *shape* of the TRM4 result are those that enter AMOP (pitch/fill, optics blur incl. F#/diffraction, micro-scan, reconstruction/display MTF, stabilisation, turbulence) and those that enter Ψ (NETD/IETD, frame rate × eye integration time, frame integration). Range then scales with ΔT0, τ_atm(R), a_tar and n_lp. SNR_th (2.5) and t_eye (0.1 s) are expert-level defaults and should stay "advanced/locked".
- For an app: keep the three categories (Thermal / VIS-NIR-SWIR / General), since the physics differ (range-independent MTDP vs range-dependent MDSP). Keep the STANAG/handheld/person presets as named templates. Expose "measured MTDP/MCP import" as an alternative to a bottom-up sensor description.

### Gaps
- The full text of the TRM4.v3 overview (SPIE 11866) and the TRM4.v4 paper (DOI 10.1117/12.3070119) could not be retrieved; the v4 feature list comes only from the IOSB web page.
- Exact current TRM4 handling of image enhancement and turbulence *mitigation* processing: not stated on the IOSB page. The v3 Doc covers only the turbulence MTF and digital filters, frame integration and "special features".

---

## Q2. What are the TTP metric equations, V50 values for D/R/I, and what parameters does NVIPM require?

### Takeaway
The TTP metric integrates √(C_tgt/CTF_sys(ξ)) over the spatial frequencies where target contrast exceeds the system contrast threshold. It multiplies by √A_tgt/R to give V, which goes into a logistic TTPF with β = 1.51 + 0.24·V/V50. NVIPM's default V50s are 2.0 (D), 7.5 (R) and 13.0 (I). Measured V50s, though, are task-, target-set- and clutter-specific (e.g., 5.5–6.7 for cluttered NIR/LWIR detection). The old Johnson N50s are 1.0/1.4/4.0/6.4 cycles (D/O/R/I), and V50 ≈ 2.7×N50 is the common rough conversion.

### Cited Findings
- **Johnson (1958) N50 [foundational]:** Detection 1.0 ± 0.25, Orientation 1.4 ± 0.35, Recognition 4.0 ± 0.8, Identification 6.4 ± 1.5 cycles across the critical dimension — [Sjaardema, Smith & Birch, "History and Evolution of the Johnson Criteria", Sandia SAND2015-6368 (2015)](https://www.osti.gov/servlets/purl/1222446)
- **Johnson/Lawson TTPF (1974) [foundational]:** P∞ = (N/N50)^E / (1 + (N/N50)^E), E = 2.7 + 0.7·(N/N50). With search time, P(t) = P∞[1 − exp(−t/τ_FOV)] — [Sandia SAND2015-6368](https://www.osti.gov/servlets/purl/1222446)
- **TTP metric equations:**
  - C_tgt = √(Δμ_tgt² + σ_tgt²)/(2·μ_bkg)
  - V = ∫_{ξ_cut-on}^{ξ_cut-off} √(C_tgt/CTF_sys(ξ)) dξ · √A_tgt / R
  - Johnson equivalent: N = ξ_cutoff·√A_tgt/R
  - P = (V/V50)^β / (1 + (V/V50)^β), with β = 1.51 + 0.24·(V/V50)

  Source: [Sandia SAND2015-6368 Eqs. 10–13](https://www.osti.gov/servlets/purl/1222446). The original source is Vollmerhausen, Jacobs & Driggers, "New metric for predicting target acquisition performance", Opt. Eng. 43(11):2806–2818 (2004), DOI 10.1117/1.1799111 — [SPIE](https://spie.org/Publications/Journal/10.1117/1.1799111)
- Zhang et al. (2024) confirm that NV-IPM's TTPF uses empirical constants A = 1.51 and B = 0.24 by default, and that "the default A and B parameters built into NV-IPM yield satisfactory results" — [Zhang, Martino, Furxhi, Jacobs, Driggers, Renshaw, Sensors 24(20):6662 (2024), DOI 10.3390/s24206662](https://pmc.ncbi.nlm.nih.gov/articles/PMC11511018)
- Unlike Johnson, TTP applies directly to sampled imagers and to imagers with coloured noise. Johnson criteria are "fundamentally flawed" because they ignore effects below the limiting frequency. (Paraphrased from a search summary of Vollmerhausen et al. material; primary full text not opened.) — [ResearchGate: Vollmerhausen & Jacobs, "The TTP Metric: A New Model for Predicting Target Acquisition Performance" (NVESD report, 2004)](https://www.researchgate.net/publication/235211165_The_Targeting_Task_Performance_TTP_Metric_A_New_Model_for_Predicting_Target_Acquisition_Performance)
- **V50 vs N50:** there is no set standard for V50; it must be determined experimentally for each system, scene and target combination. TTP corrects for chance, so V50 and N50 are not directly comparable. As a quick approximation, Hixson suggests V50 ≈ 2.7 × N50, at a cost in accuracy — [Sandia SAND2015-6368 §4.2](https://www.osti.gov/servlets/purl/1222446); see also [Hixson, Jacobs & Vollmerhausen, "Target detection cycle criteria when using the targeting task performance metric", Proc. SPIE 5612 (2004)](https://ui.adsabs.harvard.edu/abs/2004SPIE.5612..275H/abstract)
- **NV-IPM default V50s:** Detection 2.0, Recognition 7.5, Identification 13.0. These are shown in the NV-IPM TTP specification screen used with "the default V50 values for detection, recognition, and identification" — [Irwin, "Performance prediction from EO system measurements using IRWindows and NV-IPM", Proc. SPIE 10625, 1062502 (2018), DOI 10.1117/12.2315492](https://www.sbir.com/PDFs/SPIE-Std-Products-Publications/PerformancePredictionfromEOSystemMeasurements.pdf)
- **Task-specific V50 example:** detection of targets in cluttered scenes gave fitted V50 = 6.7 for LWIR (R² = 0.94) and 5.5 for NIR (R² = 0.91), about 3× the generic default of 2.0 — [Zhang et al. 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11511018)
- There is a dedicated SPIE paper on V50 definition and usage: "What is V50?", Proc. SPIE 10625 (2018), DOI 10.1117/12.2309638 — [SPIE](https://www.spiedigitallibrary.org/conference-proceedings-of-spie/10625/2309638/What-is-V50/10.1117/12.2309638.short?SSO=1) (content not retrieved)
- **N50 variability:**
  - For moving targets, N50 is traditionally taken as 2/3 of the static value.
  - Detection N50 measured across data sets ranged 0.75–4.1 cycles (mean 1.8 ± 0.93).
  - Clutter raised detection cycles from about 1.3 to 2.5.
  - ACQUIRE-LC defines clutter-dependent N50, e.g. N50 = 0.75·C·[(C/ΔT_RSS)² + 1] with C = 1/1.5/2.0/2.7 for low to high clutter.

  Source: [Sandia SAND2015-6368](https://www.osti.gov/servlets/purl/1222446)
- **Small craft (SWIR/MWIR/visible):** N50 for ID of 3.9 m boats was 4.0 (visible greyscale), 2.8 (MWIR) and 3.5 (SWIR) — [Sandia SAND2015-6368](https://www.osti.gov/servlets/purl/1222446), citing Krapels, Driggers et al., "Small craft ID criteria (N50/V50) for short wave infrared sensors in maritime security" — [Semantic Scholar](https://www.semanticscholar.org/paper/Small-craft-ID-criteria-(N50-V50)-for-short-wave-in-Krapels-Driggers/f95c801734c24b3d795cbfd982572d9ea43e3acb)
- **NVIPM inputs and architecture:**
  - NV-IPM is "a versatile tool used in conducting trade studies of EOIR imaging system performance" — [Teaney et al., "NVIPM for modeling laboratory measurements", Proc. SPIE 12533, 1253309 (2023), DOI 10.1117/12.2663355](https://www.spiedigitallibrary.org/conference-proceedings-of-spie/12533/1253309/NVIPM-for-modeling-laboratory-measurements/10.1117/12.2663355.full)
  - The *measured system component* combines SITF, 3D noise, IFOV and MTF measurements and plugs directly into NV-IPM for performance and specification evaluation. Many programmes of record specify range requirements with TTP plus such measurements — [Irwin 2018](https://www.sbir.com/PDFs/SPIE-Std-Products-Publications/PerformancePredictionfromEOSystemMeasurements.pdf)
  - Measured system components arrived in NV-IPM v1.6 along with 2D MTF and noise signals (non-separable MTFs). Haefner & Teaney (2017) describe interpolating 2D MTF from 1D measurements and a signal-dependent (additive and multiplicative) noise model. (Summarised from search abstracts.) — [SPIE Proc. Vol. 9820 abstracts](https://www.spie.org/Publications/Proceedings/Volume/9820); [High-fidelity imager emulator of measured systems, SPIE 10178](https://remotesensing.spiedigitallibrary.org/conference-proceedings-of-spie/10178/101780B/High-fidelity-imager-emulator-of-measured-systems/10.1117/12.2260887.full)
- A TRM4 component exists inside NV-IPM: it computes AMOP and MDSP for comparison with TRM4 — [Teaney, Reynolds, Du Bosq & Repasi, "A TRM4 component for the Night Vision Integrated Performance Model (NV-IPM)", Proc. SPIE 9452, 94520H (2015), DOI 10.1117/12.2180002](https://www.researchgate.net/publication/299848075_A_TRM4_component_for_the_Night_Vision_Integrated_Performance_Model_NV-IPM)
- NVThermIP predicts the system CTF and uses it to predict target-acquisition range — [Perić et al., Sensors 19(15):3313 (2019)](https://www.mdpi.com/1424-8220/19/15/3313)

### Inferences
- A TTP option would need the following inputs that TRM4 does not ask for:
  - Target contrast as mean *and* internal standard deviation (σ_tgt), plus mean scene/background luminance or radiance.
  - A display/observer CTF model: display luminance, magnification, viewing distance.
  - Task V50 and target set.
  - Optionally the TTPF constants (1.51, 0.24) and, for search, τ_FOV.
- V50 choice can move ranges by large factors. The Zhang et al. cluttered-detection V50 is about 3× the default, and range scales roughly inversely with V50 in the resolution-limited regime. V50 should therefore be a first-class, preset-driven, uncertainty-bearing input, not a hidden constant.

### Gaps
- No primary NVIPM user manual parameter list was retrieved. Parameter coverage is assembled from papers.
- The authoritative V50 tables for standard NVESD target sets (e.g., 12-vehicle tracked set) under the 2013+ observer model were not retrieved.
- The exact current NVIPM version number and feature list as of 2026 were not found.

---

## Q3. What do comparison and validation studies conclude (accuracy, biases, where each model fails)? Which input parameters have the largest uncertainty in practice?

### Takeaway
No published head-to-head perception-experiment validation of TRM4 vs NVIPM on identical data was found. Computational comparisons (TOD vs NVTherm vs TRM3) show the models disagree most on the effect of **sampling vs pre/post-blur** in undersampled imagers. Johnson-style resolution-only metrics under-predict identification on high-resolution sensors and ignore contrast. NVIPM's post-2013 observer/CTF change is disputed by the TTP's originator. In practice the largest range uncertainties come from **scene/target signature (ΔT, clutter), atmosphere, observer and observation time, and the V50/N50 task constant**, not from imager parameters, which are about 30% according to one review.

### Cited Findings
**Model-to-model comparisons**
- Bijl, Hogervorst & Valeton (2002) ran TOD, NVTherm and TRM3 on the same hypothetical undersampled cameras with varied pre- and post-filter MTFs. The models diverged: TOD predicts performance is driven mainly by sampling frequency, while NVTherm predicts pre- and post-filter blur dominate. TRM3 anomalously predicted that adding micro-scan *decreases* TA performance, traced to the periodic 4-bar pattern and the MTDP definition. The authors judged TOD the most general and noted validation of model predictions was "very limited" — [Bijl, Hogervorst & Valeton, "TOD, NVTherm and TRM3 model calculations: a comparison", Proc. SPIE 4719, 51–62 (2002)](https://repository.tno.nl/SingleDoc?docId=8779)
- TOD was validated against two observer experiments: naked eye and a simulated staring thermal sensor — [Hogervorst, Bijl & Valeton, "Capturing the sampling effects: a TOD sensor performance model", Proc. SPIE 4372 (2001), DOI 10.1117/12.439162](https://nanolithography.spiedigitallibrary.org/conference-proceedings-of-spie/4372/0000/Capturing-the-sampling-effects-a-TOD-sensor-performance-model/10.1117/12.439162.full). It was also tested against NATO field-trial ID and recognition data for 4 staring and 2 scanning imagers — [Bijl et al., "TOD Predicts Target Acquisition Performance for Staring and Scanning Thermal Imagers", SPIE (2000)](https://repository.tno.nl/islandora/object/uuid:a6798c60-e979-4015-aecb-72729dca815d)
- The TRM4 component inside NV-IPM was meant for comparison with actual TRM4 results across imaging systems — [Teaney et al. 2015](https://www.researchgate.net/publication/299848075_A_TRM4_component_for_the_Night_Vision_Integrated_Performance_Model_NV-IPM). A later review states the TRM4 components in NV-IPM "have not been officially published", so the comparison could not be completed — [Burgener, "A Survey and Comparison of Various Optical Performance Metrics", MS Report, Univ. of Arizona (2021)](https://wp.optics.arizona.edu/alumni/wp-content/uploads/sites/113/2023/06/Burgener-Mark-Dissertation-2021.pdf)
- Burgener (2021) compared Johnson, the Legacy TTPM and the 2013 TTPM in NV-IPM:
  - Johnson *under-predicts identification* relative to both TTPMs, falls between them for detection, and is mixed for recognition.
  - The Legacy TTPM "should not be used for visible imaging applications".
  - The 2013 TTPM is judged the best all-round metric.
  - "Simplification of imager performance to resolution simply does not work". Contrast and display magnification cannot be ignored.

  Source: [Burgener 2021, §5](https://wp.optics.arizona.edu/alumni/wp-content/uploads/sites/113/2023/06/Burgener-Mark-Dissertation-2021.pdf)
- Vollmerhausen (2016) evaluated the NVIPM change against perception and field data. Per the abstract, predictions of the original TTP model are more accurate at all ranges than the modified NVIPM version — [Vollmerhausen, "Night vision integrated performance model: impact of a recent change on the model's predictive accuracy", Optics Express 24(21):23654–23666 (2016)](https://www.researchgate.net/publication/322253573_Night_vision_integrated_performance_model_impact_of_a_recent_change_on_the_model's_predictive_accuracy). The dispute centres on NVIPM's redefinition of the CTF. This is a contested, single-author critique and should be presented as such.
- A study with triangle-orientation-discrimination (TOD) perception experiments found the results "do not agree with the NVIPM modeling of range improvement" for small-pitch, high-dynamic-range, digitally restored LWIR systems — [PubMed 31503776: "Performance benefits of small-pitch, high-dynamic-range, digitally restored infrared imaging systems using TOD and NVIPM"](https://pubmed.ncbi.nlm.nih.gov/31503776/)

**Model vs field/perception data**
- Zhang et al. (2024), NIR vs LWIR target localisation in clutter:
  - Default NV-IPM *over-predicts* detection at large V, especially in NIR, which the authors attribute to clutter and confusers such as poles.
  - R50 was 3.38 km (NIR) vs 1.37 km (LWIR). LWIR fell off sharply beyond about 1 km because of low transmission in hot, humid air.

  Source: [Zhang et al., Sensors 24(20):6662 (2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11511018)
- Fraunhofer validates TRM4 mainly by comparing measured and calculated MTDP. Because the analytical model simplifies targets, scene, atmosphere and perception, exactly the same range cannot be expected in human-observer experiments — [Fraunhofer IOSB TRM4 page](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html)
- Perić, Livada, Perić & Vujić (2019) tabulate inaccuracy contributions to field range estimation:

  | Factor | Contribution |
  |---|---|
  | Scene signature | 50–250% |
  | Target properties | up to 200% |
  | Atmospheric conditions | about 100% |
  | Observation time | about 200% |
  | Display & observer | about 100% (ambient light, training) |
  | Thermal imager parameters | about 30% (model accuracy, measurement error) |

  They conclude that imager-model accuracy "makes the lowest contribution to the overall inaccuracy". Their comparison of geometric (pixel), NVThermIP (standard and bad atmosphere, 0.2 and 0.35 km⁻¹) and MRTD-lab/STANAG 4347 predictions for three surveillance systems shows multi-fold spreads between methods. Geometric criteria used D/R/I = 2/7/13 px per target size; targets were a human 1.8×0.5 m and a vehicle 2.3×2.3 m, both with ΔT = 2 K — [Perić et al., "Thermal Imager Range: Predictions, Expectations, and Reality", Sensors 19(15):3313 (2019), DOI 10.3390/s19153313](https://www.mdpi.com/1424-8220/19/15/3313)
- Nichols, Hines & Nichols (2013) proposed using Akaike's Information Criterion on observer ID experiments (visible and IR, 3 maritime targets at multiple ranges) to select among competing range models. Model-based inference gave more precise estimates than traditional inference and allowed extrapolation beyond tested ranges — [Nichols, Hines & Nichols, Opt. Eng. 52(11):113108 (2013), DOI 10.1117/1.OE.52.11.113108](https://www.usgs.gov/publications/selecting-among-competing-models-electro-optic-infrared-camera-system-range)
- Holst & Mahalanobis (2023) compared pixels-on-target thresholds with NV-IPM probability predictions for a typical LWIR sensor. Current algorithm studies suggest POT (pixels on target *area*) of 50–70 for detection, 150 for classification, 250 for recognition and 350 for identification of tank-sized targets — [Holst & Mahalanobis, "Comparing pixels on target with NV-IPM range predictions", Proc. SPIE 12533 (2023)](https://spie.org/Publications/Proceedings/Volume/12533)

**Historical sources of bias [foundational context]**
- Johnson's model tends to *overestimate* performance at low SNR (Rosell & Willson 1973). Observer variability is large: individual performance ranged 50–97% in the 1969 studies. Aspect angle, clutter and background (foliage vs sand) shift performance — [Sandia SAND2015-6368](https://www.osti.gov/servlets/purl/1222446)

### Inferences
- **Regimes where the models disagree or fail:**
  1. Undersampled imagers near or above Nyquist: AMOP/MTDP vs TTP vs TOD treat aliasing differently.
  2. Micro-scan/dither and reconstruction filters, given the TRM3 anomaly.
  3. Low-contrast and noise-limited conditions, where resolution-only and Johnson methods over-predict.
  4. High-resolution sensors at ID, where Johnson under-predicts relative to TTP.
  5. Cluttered scenes, where default V50 over-predicts.
  6. Humid LWIR paths, where atmosphere dominates.
- **Parameters with the largest practical uncertainty**, which deserve uncertainty distributions in the app: target ΔT or contrast (and σ_tgt for TTP); atmospheric extinction σ (visibility, humidity, aerosol model); V50/N50 (task, target set, clutter); observer and display factors; turbulence Cn². Well-measured sensor parameters (NETD, MTF, pitch, focal length) are comparatively tight.
- Present model output as *nominal under standard conditions* (STANAG framing) plus a scenario-specific band, not as a single "true" range.

### Gaps
- No quantitative RMS or percentage error statistics for TRM4 vs field trials were found in open sources.
- The Somerville MS report "Systematic Evaluation of the Night Vision Integrated Performance Model" (Univ. of Arizona) likely contains quantitative NVIPM-vs-data comparisons but was not read — [link](https://wp.optics.arizona.edu/alumni/wp-content/uploads/sites/113/2023/06/MastersReport_Somerville_Signed.pdf)
- A search-engine summary claimed that "for identification all models substantially overestimated performance". This could not be traced to a primary source and is excluded.

---

## Q4. How do mature tools structure parameters (basic vs advanced, presets, derived quantities, measured-data import)? What do simple vendor DRI calculators reduce to?

### Takeaway
Mature analytical tools (TRM4, NVIPM) are organised along the **imaging chain**: scene/target, atmosphere, optics, detector, processing, display, observer, task. They provide templates/presets, standard target sets, external-data hooks at every MTF/noise stage, and measured-data import (MTDP/MCP in TRM4; SITF + 3D-noise + MTF + IFOV "measured system component" in NVIPM). Vendor DRI calculators reduce everything to **pixels (or cycles) on target**: R = a·f/(n·p), with n ≈ 1.5–2 / 6–8 / 12–13 px for D/R/I on a 2.3 m vehicle or a 1.7–1.8 m × 0.5 m human. CCTV uses IEC 62676-4 pixel density: 25 / 62–63 / 125 / 250 px/m.

### Cited Findings
**TRM4 / NVIPM structure**
- TRM4 parameter dialogs follow the chain: imager category → imager type → basic data → optics → (II/coupling) → detector geometry/sensitivity → analog/digital/video processing → display/observation/eye → stabilisation → additional MTFs → prefilter MTF *or* measured MTDP/MCP → target/scenario/task → irradiance → atmosphere → turbulence. Each MTF stage accepts "External data". Templates and built-in libraries supply defaults — [TRM4.v3 Doc ch. 2](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)
- TRM4 outputs derived quantities for diagnosis: MNTD/ETD and MNDS/EDS curves, introduced "to better understand the limiting factors"; number of resolved line pairs and pixels vs range; signal, noise and SNR vs range; MTFs and AMOP — [TRM4.v3 Doc §1.2, §3.12.3](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf). TRM4.v4 adds "diagnostics tooltips" — [TRM4 page](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html)
- NV-IPM is component-based (e.g., parametric camera vs measured system component), supports looping and parametric sweeps across ranges, and has a TTP specification panel with editable V50 per task — [Irwin 2018](https://www.sbir.com/PDFs/SPIE-Std-Products-Publications/PerformancePredictionfromEOSystemMeasurements.pdf). Lab-measurement tie-in is a current development focus — [Teaney et al. 2023](https://www.spiedigitallibrary.org/conference-proceedings-of-spie/12533/1253309/NVIPM-for-modeling-laboratory-measurements/10.1117/12.2663355.full)
- IRWindows 4 (SBIR) test software produces SITF, 3D noise, IFOV and MTF results that generate an NV-IPM measured system component. This allows side-by-side comparison of the measured system with the idealised parametric model, and agreement between labs is shown — [Irwin 2018](https://www.sbir.com/PDFs/SPIE-Std-Products-Publications/PerformancePredictionfromEOSystemMeasurements.pdf)
- Historic NVESD models (FLIR90/FLIR92) introduced 3D noise components: temporal and spatial pixel noise, temporal line and column bounce, spatial row and column non-uniformity; FLIR92 added frame-to-frame noise — [Sandia SAND2015-6368](https://www.osti.gov/servlets/purl/1222446) **[foundational]**

**IEC 62676-4 (CCTV, visible)**

| Level | px/face | px/m | Purpose |
|---|---|---|---|
| Detection | 4 | 25 | presence |
| Observation | 10 | 63 (often 62) | count and characteristic details |
| Recognition | 20 | 125 | same person seen before |
| Identification | 40 | 250 | identity |

- Basis: average face width 16 cm. Axis calls the model a "simplified rule of thumb". Optics, lighting direction, compression and display resolution matter. Video analytics and thermal imaging use different definitions. AXIS Site Designer visualises px/m coverage and supports manual entry of IEC 62676-4:2025 values — [Axis whitepaper, "Pixel density based on IEC 62676-4:2014"](https://whitepapers.axis.com/en-us/pixel-density-based-on-iec-62676-4-2014). Vendor FAQs repeat 25/62/125/250 px/m as "DORI" for visible cameras and "DRI/Johnson" for thermal — [TP-Link/Omada "What is DORI?"](https://www.omadanetworks.com/gr/support/faq/4098/)

**Thermal vendor DRI conventions**
- Axis cites about 1.5 px across the object for detection and 6 px for recognition (Johnson-based) — [Axis thermal technology glossary](https://www.axis.com/dam/public/e1/df/a5/thermal-technology-glossary-en-US-111749.pdf) (via search summary).
- Consumer and security vendors give about 2 / 6 / 12 px for D/R/I on a 1.8 m object — [NatureSpy, "Thermal Imaging Specifications Explained"](https://naturespy.org/help-articles_item/thermal-imaging-specifications-explained/)
- Dahua uses a 1.8 m human height (e.g., 3.6 px/1.8 m = 2 px per meter for detection) and separately specifies IVS (analytics) ranges — [Dahua, "Thermal Camera Range Performance for DRI and IVS V2.0" (2020)](https://www.dahuasecurity.com/asset/upload/uploads/soft/20201105/Therma-Camera_Range-Performance-for-DRI-and-IVS_V2.0.pdf)
- Typical reference targets: vehicle 2.3×2.3 m, person 1.7×0.5 m; Johnson is a 50%-probability standard — [Infiniti Optics, "DRI Explained"](https://www.infinitioptics.com/dri)
- Some integrators argue the classic Johnson pixel counts are too lax for always-on surveillance and propose stricter thresholds, e.g., 8 vertical pixels for detection — [Kintronics, "Detection, Recognition, Identification: The New Criteria"](https://kintronics.com/detection-recognition-identification-new-criteria/)
- The Perić et al. "geometric" method uses 2/7/13 px for D/R/I — [Perić et al. 2019](https://www.mdpi.com/1424-8220/19/15/3313)
- Pixel-count calculators ignore contrast, noise, atmosphere and display. Burgener shows that designing to resolution alone "simply does not work" — [Burgener 2021](https://wp.optics.arizona.edu/alumni/wp-content/uploads/sites/113/2023/06/Burgener-Mark-Dissertation-2021.pdf)

### Inferences
**Recommended UI layering for a TRM4-based app**
1. **Quick/geometric mode:** focal length, pitch, array size and target critical dimension, giving IFOV, GSD/px-on-target vs range, IEC 62676-4 px/m and Johnson-pixel D/R/I as a sanity bound. This is clearly labelled "resolution-only upper bound, no atmosphere/contrast".
2. **Standard mode:** TRM4 core with presets (STANAG 4347 vehicle, person, handheld; standard atmospheres σ = 0.2 and 1.0 km⁻¹). Required inputs: ΔT or contrast, atmosphere, F#, focal length, pitch, NETD, frame rate.
3. **Advanced mode:** every MTF and noise stage, eye/display, stabilisation, turbulence, external data import (MTF curves, measured MTDP/MCP, NETD vs T_bkg, spectral transmission).

**Derived quantities worth showing:** F·λ/d, Nyquist frequency, IFOV, GSD at range, resolved line pairs vs range, MNTD/ETD crossing, the limiting factor (noise-limited vs resolution-limited), and px/m at each DRI range for cross-reference with CCTV specs.

**Measured-data import mirroring NVIPM:** MTF (H/V), SITF, 3D-noise components (σ_tvh, σ_vh, σ_tv, σ_th, σ_v, σ_h), measured MTDP/MCP at several pattern positions.

### Gaps
- Teledyne FLIR, SCD, Lynred and Hikvision online DRI calculators were not retrieved directly. Their exact pixel thresholds, target sizes and probability levels are unverified. The Leonardo DRS white paper "The truth about range data" (2017) returned 404.
- No NVIPM GUI screenshot or official parameter list (basic vs advanced) was retrieved.
- The IEC 62676-4:2025 values were not verified.

---

## Q5. What are recommended practices for presenting sensitivity results (tornado, elasticity, Sobol) and uncertainty (confidence bands on range)?

### Takeaway
One-at-a-time (OAT) sensitivity, the basis of classic tornado charts, misses interactions and leaves most of the input space unexplored. Saltelli et al. found 42% of highly cited sensitivity analyses fail on this point. Range models are strongly non-additive (ΔT × τ_atm × MTDP crossing; noise-limited vs resolution-limited regimes), so global methods are preferred: Morris screening, then Sobol first-order and total indices on Monte Carlo or quasi-MC samples. Uncertainty should be shown as distributions or percentile bands on range. One EO/IR precedent (ONERA) used factorial screening → QMC dispersion → metamodel.

### Cited Findings
- Many sensitivity analyses still explore the input space along one-dimensional corridors, "leaving space of the input factors mostly unexplored". In a bibliometric review, 42% of highly cited papers failed to explore the input space properly. A global sensitivity measure must capture interaction effects, which matters most for non-linear, non-additive models — [Saltelli et al., "Why so many published sensitivity analyses are false: A systematic review of sensitivity analysis practices", Environmental Modelling & Software 114:29–39 (2019), DOI 10.1016/j.envsoft.2019.01.012](https://discovery-pp.ucl.ac.uk/id/eprint/10066597); [BORA repository](https://bora.uib.no:443/bora-xmlui/handle/1956/21628)
- OAT is the most popular SA practice. Its shortcomings are known, and alternatives based on experimental design and regression exist — [Saltelli & Annoni, "How to avoid a perfunctory sensitivity analysis", Environmental Modelling & Software 25 (2010)](https://hero.epa.gov/reference/1060594)
- The Sobol variance-based indices and their Monte Carlo estimators: Sobol, "Global sensitivity indices for nonlinear mathematical models and their Monte Carlo estimates", Mathematics and Computers in Simulation 55:271–280 (2001), DOI 10.1016/S0378-4754(00)00270-6, cited as the standard reference in — [arXiv 1303.6447 (Sobol pick-freeze inference)](https://arxiv.org/pdf/1303.6447)
- **EO/IR precedent (ONERA):**
  - 28 uncertain inputs: 9 surface optical properties, 7 flight and aspect, 12 atmospheric (visibility, humidity, air temperature, aerosol model, clouds, albedo, time, season deviations).
  - Full Sobol was too CPU-expensive (about 3 min per run), so two-level fractional factorial designs were used to estimate Sobol indices, kept because interactions matter. Ten significant factors were retained.
  - The output dispersion was then propagated with quasi-Monte Carlo (low-discrepancy) sampling, and a neural-network metamodel was built.
  - The performance criterion is a non-detection probability against a threshold.

  Source: [Lefebvre, Roblin, Varet & Durand, "Statistical Estimation of Aircraft Infrared Signature Dispersion", ENBIS-EMSE 2009](https://events.mines-stetienne.fr/enbis-emse2009/pdf/articles/Lefebvre.pdf); [slides](https://events.mines-stetienne.fr/enbis-emse2009/pdf/slides/S.%20Lefebvre.pdf)
- For uncertainty propagation, quasi-MC with Sobol sequences spreads samples more evenly than random sampling and converges faster (finding from a structural-model UQ study surfaced in search) — [arXiv 2201.09659](https://arxiv.org/pdf/2201.09659)
- Field-range inaccuracy magnitudes for setting input distributions: scene signature 50–250%, target up to 200%, atmosphere about 100%, observer/display about 100%, observation time about 200%, imager about 30% — [Perić et al. 2019](https://www.mdpi.com/1424-8220/19/15/3313)
- Treating range performance statistically, with AIC-based model selection on observer data, yields more precise estimates and supports extrapolation — [Nichols et al. 2013](https://www.usgs.gov/publications/selecting-among-competing-models-electro-optic-infrared-camera-system-range)

### Inferences (no EO/IR-specific source was found for the presentation conventions below; these follow from the sources above and standard practice)
**Two-tier presentation for engineers**
1. Keep a **local tornado or elasticity chart** for intuitive "what-if" around the design point. Elasticity is %ΔR / %Δx, which is unitless and comparable across parameters. Swing ranges should be realistic (e.g., ±1σ or P10–P90 per parameter), not arbitrary ±10%. Label it explicitly as local/OAT.
2. Add a **global panel**: Morris μ*/σ screening as a cheap first pass, since σ flags interactions and non-linearity. Then show Sobol S_i (first-order) and S_Ti (total) bars for the top inputs. S_Ti − S_i shows interaction share, which is large where the model switches between noise- and resolution-limited regimes.

**Range uncertainty display**
- Run Monte Carlo over input distributions (ΔT, σ_atm, V50/N50, NETD, MTF scaling, Cn²).
- Report median range with P10–P90 (or 5–95%) bands per task.
- Show a "range-exceedance" curve P(R_achieved ≥ R) and/or a fan chart of the D/R/I probability curves.
- Separate *aleatory* (weather, target) from *epistemic* (model, V50) uncertainty where possible.

**Cost**
- Saltelli-type Sobol estimation needs roughly N·(d+2) model runs (standard result; not re-verified here).
- TRM4 core runs are fast, but AMOP simulation per frequency may be costly. Caching AMOP (it is range-independent in the Thermal category) or using a surrogate (polynomial chaos, Gaussian process, or neural net as in ONERA) makes global SA practical.

### Gaps
- No published Sobol or Morris study on TRM4 or NVIPM range outputs was found.
- No standard (e.g., NATO or SPIE) on how to present range uncertainty bands was found.
- No source with empirically recommended input distributions for ΔT, visibility or V50 was found, beyond the Perić et al. percentages and the Sandia N50 spread of 0.75–4.1.

---

## Q6. What are the emerging topics (2020–2026) relevant to such an app?

### Takeaway
Topics to track:
- **AI/machine-vision observers**, which need pixels-on-target or algorithm-specific criteria rather than human V50, and which outperform humans at long range in contrast-limited LWIR.
- **Small-pixel (5–10 µm) and HOT detectors**, which push systems into the optics-limited regime (F·λ/d) and make lower F#, crosstalk and background-temperature-dependent NETD critical.
- **Turbulence mitigation processing**, with reported +10–25% recognition range.
- **Colour, sub-pixel and air-to-air targets, and display glare** in TRM4.v4-era modelling.

### Cited Findings
**AI and machine vision**
- Deep-learning techniques are "increasingly deployed in infrared imaging systems for long-range target detection, localization, and identification" — [SPIE Proc. Vol. 12533, Infrared Imaging Systems XXXIV (2023), volume description](https://spie.org/Publications/Proceedings/Volume/12533)
- Algorithm POT thresholds for tank-sized targets: 50–70 (D), 150 (classification), 250 (R), 350 (I) pixels on target area. Machine-learning algorithms can be used to evaluate detection probability and time to detect — [Holst & Mahalanobis 2023, SPIE 12533](https://spie.org/Publications/Proceedings/Volume/12533)
- In LWIR, an AI tower detector beat human observers beyond about 1100 m, which suggests AI is advantaged when *contrast* rather than resolution limits performance. The authors caution about limited training data and say AI range-performance data are lacking in the literature — [Zhang et al. 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11511018)
- Vendors already publish separate "IVS" (video analytics) ranges alongside human DRI — [Dahua DRI & IVS V2.0](https://www.dahuasecurity.com/asset/upload/uploads/soft/20201105/Therma-Camera_Range-Performance-for-DRI-and-IVS_V2.0.pdf). Axis notes video analytics use different definitions than IEC 62676-4 human levels — [Axis whitepaper](https://whitepapers.axis.com/en-us/pixel-density-based-on-iec-62676-4-2014)

**Small-pitch and HOT detectors**
- MWIR pitch has shrunk from 15 µm to as little as 5 µm and LWIR from 17 µm to 8 µm. Shrinking pitch at fixed format requires lower-F# optics, lenses designed for larger pitch incur a penalty, and pixel crosstalk becomes more problematic — [European Security & Defence (sponsored), "Next-gen optics for smaller pixel pitch MWIR & LWIR detectors" (Oct 2025)](https://euro-sd.com/2025/10/sponsored-content/46118/shrinking-pixels-maintaining-performance-infrared-imaging-systems/)
- SCD reported a 5 µm-pitch HOT XBn-InAsSb MWIR array at 150 K — [Bar-Ilan CRIS record, "HOT MWIR detector with 5 µm pitch"](https://cris.biu.ac.il/en/publications/hot-mwir-detector-with-5-um-pitch/). It was later productised as Sparrow-HD (HOT XBn 150 K and HOT full-mid-wave configurations) — [FW-Mag, 30 Sep 2024](https://fw-mag.com/shownews/189/scd-unveils-sparrow-hd-high-definition-mid-wave-infrared-mwir-detector)
- AIM has HOT from SWIR to VLWIR, with 10 µm LWIR in XGA being introduced — [AIM, "HOT all the way from SWIR to VLWIR at AIM", Proc. SPIE 13046 (2024)](https://electronicimaging.spiedigitallibrary.org/conference-proceedings-of-spie/13046/130460F/HOT-all-the-way-from-SWIR-to-VLWIR-at-AIM/10.1117/12.3016046.full). See also [Towards HOT and small-pitch MCT LWIR, Proc. SPIE 12107 (2022)](https://nanophotonics.spiedigitallibrary.org/conference-proceedings-of-spie/12107/121070T/Towards-high-operating-temperature-and-small-pixel-pitch-MCT-LWIR/10.1117/12.2618780.full)
- Lynred says 8 µm pitches are at the R&D stage and that smaller pitch reduces the IR flux absorbed per pixel, which affects signal — [Lynred blog](https://www.lynred.com/blog/infrared-detectors-three-technical-innovations-you-should-know-about)
- A NVIPM-vs-TOD perception study on small-pitch, HDR, digitally restored LWIR found perception results disagreed with NVIPM's predicted range improvement — [PubMed 31503776](https://pubmed.ncbi.nlm.nih.gov/31503776/)
- TRM4 warns that 3–5 µm sensitivity depends strongly on background temperature. This becomes more relevant with HOT MWIR operating at higher dark current and temperature — [TRM4.v3 Doc §2.24.2](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)

**Turbulence and its mitigation**
- Software turbulence mitigation reduces blur and tilt and "enlarges the recognition range", estimated at up to 25% for an operational system — [Fraunhofer IOSB publica record](https://publica.fraunhofer.de/entities/publication/84b8c5a2-733f-40d6-998a-0f17ec4e47fc). TNO reports simulated recognition-range gains of 10–25% and notes turbulence is spatially varying — [van Eekeren et al., TNO (2014)](https://publications.tno.nl/publication/34610519/GQU8NK/eekeren-2014-evaluation.pdf)
- Turbulence can severely limit large-aperture long-range systems. Mitigation algorithms have been tested with human observers on handheld-weapon ID (SPIE 2012) — [Miller et al., "Turbulence degradation and mitigation performance for handheld weapon ID"](https://independent.academia.edu/JasonMiller254)
- TRM4 models turbulence as a Kolmogorov short- or long-exposure MTF with a Cn² specification — [ECOMOS TRM4 slides](https://ecomos.org/wp-content/uploads/2018/01/ECOMOS_20170621_03_TRM4_Background_WS_Kessler.pdf); [TRM4.v3 Doc §2.28, §4.2.13](file:///C:/Users/ramih/OneDrive/Desktop/Desktop/TRM_Hadmaa/TRM4v3_ModelDocumentation_260930_095803.pdf)

**TRM4 evolution**
- TRM4.v4 (Aug 2026): colour cameras, sub-pixel targets incl. air-to-air, GRD for aerial imaging, diagnostics tooltips — [Fraunhofer IOSB TRM4 page](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html)
- Display/observer glare modelling (2024) — [Günther & Keßler, SPIE 13200](https://proceedings.spiedigitallibrary.org/conference-proceedings-of-spie/13200/132000V/Concept-study-for-the-TRM4-display-observer-model--effects/10.1117/12.3031651.full)
- Colour-imager range prediction joint with TRM (2020) — [Pinsky & Yaron, SPIE 11538](https://opticalengineering.spiedigitallibrary.org/conference-proceedings-of-spie/11538/115380G/Range-prediction-for-color-imagers-toward-a-joint-TRM-and/10.1117/12.2571247.full)
- ECOMOS (European Computer Model for Optronic System Performance Prediction) uses TRM4 as its analytical model and its GUI to specify imagers. TRM4 MTF and noise feed image-based simulation (TOD-type observer experiments with simulated imagery) — [ECOMOS TRM4 slides](https://ecomos.org/wp-content/uploads/2018/01/ECOMOS_20170621_03_TRM4_Background_WS_Kessler.pdf); [ECOMOS TRM page](https://ecomos.org/information/trm/); ECOMOS paper DOI 10.1117/12.2279820 per the [TRM4 page](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html)

### Inferences
- **Add an "observer type" switch:** human (TRM4 line pairs / Johnson N50 / TTP V50) vs algorithm (POT area thresholds such as 50–70/150/250/350, or user-defined detector-specific curves). For algorithms, contrast/SNR-limited behaviour should still enter, for example as a minimum SNR per pixel on target, not only pixel counts.
- **Small-pixel support:** show F·λ/d and flag the regimes (detector-limited < ~1, balanced 1–2, optics-limited > 2). Ensure the AMOP and diffraction MTF handle pitch below λ (e.g., 5 µm in LWIR). Add crosstalk/detector-MTF degradation and NETD vs T_bkg inputs for HOT MWIR.
- **Turbulence:** keep Cn² and short- vs long-exposure MTF. Optionally add a "mitigation gain" parameter, a residual-MTF factor or frame-averaging model, clearly marked as empirical (10–25% range gain reported).
- **Deep-learning observer models** that replace human V50 with CNN-based or task-performance curves did not surface as an established, validated method in 2020–2026 open literature. Treat them as research items.

### Gaps
- No open publication was found that defines a validated range model for AI/ATR observers equivalent to TTP/V50; the POT figures are from a single conference abstract.
- No quantitative F·λ/d-vs-range study for 5–8 µm HOT arrays was retrieved.
- Computational imaging (e.g., super-resolution, coded aperture) in range models: no specific 2020–2026 range-model source was retrieved.
- Whether NVIPM includes an explicit turbulence-mitigation component in 2026: not found.
