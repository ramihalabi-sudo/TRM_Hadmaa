# Atmosphere, Turbulence, Environment and Target/Scene Parameters vs. Imager Image Quality and DRI Range (TRM4 / NVIPM context)

Scope: thermal (MWIR/LWIR) and reflective-band (VIS/NIR/SWIR) imagers. Covers how each environmental and target parameter is defined, how it enters TRM4 (Fraunhofer IOSB) and NVIPM/NVThermIP (US Army C5ISR/NVESD, TTP metric), how much it moves DRI range, realistic values, and how to expose it in an app.
Source quality: anything published before 2000 is flagged **[foundational]**. Numbers marked "(calc.)" are my own arithmetic from the cited formulas. They are not quoted from literature.

---

## Q1. Atmospheric transmission, extinction, path radiance and band dependence

### Takeaway
Range models apply transmission as a multiplicative loss on apparent target signal (Beer–Lambert, τ = exp(−σR), or a MODTRAN-computed band τ(R)). In IR, absorption by water vapour and gases dominates σ in clear air, and scattering only matters in haze or fog. Common "standard" IR conditions are σ ≈ 0.2 km⁻¹ (good, 23 km visibility) and ≈ 0.35 km⁻¹ (poor, about 5 km visibility, humid climate). In one published comparison, moving from σ = 0.2 to 0.35 km⁻¹ cut predicted thermal detection range by 14–40% and identification range by 0–31%. The loss is largest for the longest-range tasks and systems.

### Cited Findings
**Beer–Lambert and visibility relations**
- Total attenuation is σ(λ) = σ_abs(λ) + σ_sc(λ), and τ_ATM(λ,R) = exp(−σ(λ)·R). Koschmieder's law, with a 2% eye contrast threshold at 0.55 µm, links meteorological visibility R_V to visible extinction: σ_V = 3.912/R_V. For the IR, scattering in a continental climate is scaled as σ_sc = (3.91/R_V)·(0.55/λ)^q with q = 0.585·R_V^(1/3), using λ = 4 µm for MWIR and λ = 10 µm for LWIR. Absorption has to be added separately from the water-vapour content of the path. — [Perić, Livada, Perić, Vujić, "Thermal Imager Range: Predictions, Expectations, and Reality," *Sensors* 19(15):3313, 2019, DOI 10.3390/s19153313](https://www.mdpi.com/1424-8220/19/15/3313)
- Kruse wavelength exponent: q = 1.6 for V > 50 km, q = 1.3 for 6 < V < 50 km, q = 0.585·V^(1/3) for V < 6 km. — [arXiv 2309.13417 review (restating Kruse)](https://arxiv.org/pdf/2309.13417)
- Kim's correction for low visibility: q = 0.16V + 0.34 for 1–6 km, q = V − 0.5 for 0.5–1 km, q = 0 for V < 0.5 km (fog). With q = 0, extinction becomes wavelength-independent across VIS–NIR–SWIR in dense fog. — [Radioengineering 2010 (restating Kim)](https://www.radioeng.cz/fulltexts/2010/10_04_596_600.pdf)
- Kim, McArthur & Korevaar (SPIE 4214, 2001, DOI 10.1117/12.417512) found that 1550 nm is attenuated less than 785/850 nm in haze with visibility > 2 km, but all three are attenuated about equally in fog with visibility < 500 m. — [SPIE record](https://medicalimaging.spiedigitallibrary.org/conference-proceedings-of-spie/4214/0000/Comparison-of-laser-beam-propagation-at-785-nm-and-1550/10.1117/12.417512.full)
- A secondary source warns that the Kruse model is weak below 1 km visibility and understates attenuation at longer wavelengths. — [MUET Research Journal](https://publications.muet.edu.pk/index.php/muetrj/article/download/197/71)

**Typical "standard" extinction values used in thermal range predictions**
- NVThermIP calculations in Perić et al. used a "standard US atmosphere with 23 km meteorological visibility" with an atmospheric attenuation factor of **0.2 km⁻¹**. "Bad atmospheric conditions" (mid-latitude summer and tropical climate, 5 km visibility) used **0.35 km⁻¹**. The STANAG 4347 laboratory range-prediction procedure applies an absorption coefficient of 0.2 km⁻¹, which is "usually considered a good atmospheric condition." — [Perić et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)
- Perić et al. computed MWIR (4 µm) and LWIR (10 µm) extinction with MODTRAN for four climate/aerosol models: mid-latitude summer urban, tropical desert, tropical navy aerosol, and US Standard 1976 rural. Each was run at visibilities of 23, 5 and 1 km over a 1 km path. The numeric values appear only in a figure and could not be extracted. — [Perić et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)
- NVThermIP accepts atmosphere as MODTRAN output, a Beer's-law coefficient, or a user transmission table. — [Sjaardema, Smith, Birch, "History and Evolution of the Johnson Criteria," Sandia SAND2015-6368, 2015](https://www.osti.gov/servlets/purl/1222446)

**Measured range impact of extinction (NVThermIP, three real long-range systems, ΔT = 2 K; human target 1.8×0.5 m, vehicle 2.3×2.3 m)** — [Perić et al. 2019, Table 7](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)

| System / target | Task | σ = 0.2 km⁻¹ | σ = 0.35 km⁻¹ | Change (calc.) | Geometric (2/7/13 px) |
|---|---|---|---|---|---|
| SYS1 (MWIR) vehicle | Detection | 13.9 km | 9.9 km | −29% | 33.7 km |
| SYS1 vehicle | Recognition | 5.3 | 4.6 | −13% | 8.4 |
| SYS1 vehicle | Identification | 4.2 | 3.9 | −7% | 4.3 |
| SYS2 (MWIR, long FL) vehicle | Detection | 22.4 | 13.5 | −40% | >50 |
| SYS2 vehicle | Recognition | 13.6 | 9.1 | −33% | 30.7 |
| SYS2 vehicle | Identification | 12.2 | 8.4 | −31% | 15.3 |
| SYS2 human | Detection | 18.1 | 11.3 | −38% | 50 |
| SYS3 (LWIR) vehicle | Detection | 7.6 | 5.9 | −22% | 15.2 |
| SYS3 vehicle | Identification | 1.8 | 1.8 | 0% | 2.6 |

- In the same paper, geometric (pixel-count) range "is always highly optimistic." Users should expect that most of the time the imager will only see as far as the MRTD-based range. — [Perić et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)

**Band dependence (VIS / SWIR / MWIR / LWIR)**
- Band properties from Perić et al. Table 2:

  | Band | Solar irradiance (W/m²) | 300 K blackbody exitance (W/m²) | Relative thermal contrast | Absorption | Scattering |
  |---|---|---|---|---|---|
  | VIS | 750 | 0 | – | high | high |
  | MWIR | 24 | 1.5 | 0.39 | lower | higher |
  | LWIR | 1.5 | 130 | 0.17 | higher | lower |

  The "relative thermal contrast" column is labelled "ΔT/T" in the paper. — [Perić et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)
- Fog: in an automotive fog-chamber study, LWIR consistently outperformed MWIR, SWIR and visible. SWIR and visible were the most degraded. — [SPIE 11002, 110021F, 2019, "Automotive sensing: assessing the impact of fog on LWIR, MWIR, SWIR, visible…"](https://www.spiedigitallibrary.org/conference-proceedings-of-spie/11002/110021F/Automotive-sensing--assessing-the-impact-of-fog-on-LWIR/10.1117/12.2519423.pdf)
- Fog extinction ratios from visible to far-IR, measured across several field campaigns, are tabulated in "Empirical relationships between extinction coefficient and visibility in fog," *Applied Optics* 44(18):3795, 2005. Values were not retrieved. — [Optica](https://opg.optica.org/ao/abstract.cfm?uri=ao-44-18-3795)
- One modelling study reports that haze barely changes LWIR acquisition range but reduces MWIR range by about 13%. It also reports a band crossover at about 6 km. The snippet does not make clear which band wins beyond 6 km, so verify against the paper. — ["Range Performance Modelling of Thermal Imaging System based on Single Parameter Characterised by Ambient Temperature and Relative Humidity"](https://www.researchgate.net/publication/327838448_Range_Performance_Modelling_of_Thermal_Imaging_System_based_on_Single_Parameter_Characterised_by_Ambient_Temperature_and_Relative_Humidity)
- Vendor and secondary sources disagree on MWIR vs LWIR in humid air. Some say LWIR's wider window copes better with humidity, others say MWIR has the edge in high humidity. Treat these as unreliable. — [LightPath](https://www.lightpath.com/insights/mid-wave-infrared-vs-long-wave-infrared-imaging-comparison); [Axiom Optics](https://www.axiomoptics.com/blog/the-differences-between-swir-mwir-and-lwir-cameras/)

**Aerosol MTF (scattering blur, not only loss)**
- Dror & Kopeika (Ben-Gurion University) measured aerosol and turbulence MTFs simultaneously over the same horizontal open-air path. The aerosol MTF was nearly always significant and often dominated the turbulence MTF, except around midday. Their conclusion is that turbulence-only atmospheric MTFs and restoration filters underperform. **[foundational]** — [Dror & Kopeika, *JOSA A* 12(5):970–980, 1995](https://opg.optica.org/josaa/abstract.cfm?uri=josaa-12-5-970)
- The instrumentation-based aerosol MTF depends on field of view, dynamic range and spectral bandwidth. Its measured high-frequency asymptote lies well above the classical turbid-medium prediction. **[foundational]** — [Sadot & Kopeika, *JOSA A* 10(1):172–179, 1993](https://opg.optica.org/josaa/abstract.cfm?uri=josaa-10-1-172). Updated in [Kopeika, Zilberman, Yitzhaky, "Aerosol MTF revisited," Proc. SPIE 9071, 2014](https://www.researchgate.net/publication/271426827_Aerosol_MTF_revisited)
- Krapels et al. (2001) at NVESD evaluated the Ben-Gurion atmospheric (turbulence) MTF model and concluded it was viable for use in the US Army model. — [Sandia SAND2015-6368](https://www.osti.gov/servlets/purl/1222446)

**Weather in general**
- "Heavy fog" is an arbitrary label, and particle size and number data would be needed. Ratches & Lawson's 1975 fog detection model was about ±20% accurate in the best case **[foundational]**. Rotman et al. (1991) found that fluctuating obscurants yield higher detection probability than a constant obscurant of the same mean density **[foundational]**. — [Sandia SAND2015-6368](https://www.osti.gov/servlets/purl/1222446)
- An illustrative Beer's-law table shows detection probability at 10 km falling from 0.845 (10-km average τ = 100%) to 0.315 (average τ = 10%). — [Sandia SAND2015-6368, Table 6](https://www.osti.gov/servlets/purl/1222446)

**TRM4 specifics**
- TRM4.v1 (August 2010) added a "detailed atmospheric model (turbulence and spectral transmissivity)," plus slant-path observation and 3D targets. TRM4.v3 (2021) added targets against sky background and MCP (Minimum Contrast Perceived) for VIS–SWIR. TRM4.v4 (August 2026) added colour cameras, subpixel detection including air-to-air, and ground-resolved distance. — [Fraunhofer IOSB TRM4 page](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html)
- The TRM4 paper by Keßler, Gal & Wittenstein (Proc. SPIE 10178, 101780P, 2017) describes newly introduced features: atmospheric turbulence, irradiation sources and libraries. Search snippets also indicate that TRM4 includes path radiance. — [ResearchGate](https://www.researchgate.net/publication/316713606_TRM4_Range_performance_model_for_electro-optical_imaging_systems); [ADS](https://ui.adsabs.harvard.edu/abs/2017SPIE10178E..0PK/abstract)

### Inferences
- Clear-air IR extinction is absorption-dominated (calc. from the Kruse formula above). At V = 23 km, scattering σ_sc ≈ 0.013 km⁻¹ at 4 µm and ≈ 0.004 km⁻¹ at 10 µm. At V = 5 km, it is ≈ 0.11 km⁻¹ (4 µm) and ≈ 0.04 km⁻¹ (10 µm). So the 0.2 and 0.35 km⁻¹ "standard" values are mostly water-vapour and gas absorption. **Humidity / absolute water vapour and air temperature should drive IR σ more than visibility does**, except in haze or fog. Note that 0.35 km⁻¹ is an IR value, not the Koschmieder visible value of 0.78 km⁻¹ at 5 km.
- SWIR (1.55 µm), calc.: σ_sc ≈ 0.044 km⁻¹ at V = 23 km and ≈ 0.28 km⁻¹ at V = 5 km. Visible at V = 5 km is 0.78 km⁻¹. SWIR therefore gains strongly over VIS in haze, but the gain vanishes in fog (Kim, q→0).
- Beer–Lambert range sensitivity, calc.: apparent ΔT at the sensor is τ·ΔT. With ΔT = 2 K at 10 km, it is 0.27 K for σ = 0.2 and 0.06 K for σ = 0.35, a 4.5× contrast loss. This explains why long-range detection is hit hardest while short-range identification (where τ ≈ 1) barely moves, as the Perić table shows.
- Band-averaged MODTRAN transmission is not a pure exponential in R (spectral line saturation). A single σ fitted at 1 km can misstate τ at 10+ km. This is standard radiative-transfer behaviour; I did not find a source quantifying it in this session.
- Path radiance: in reflective bands, path radiance adds to both target and background radiance and lowers apparent contrast. The classical Duntley/Koschmieder "sky-to-ground ratio" form is C(R) = C₀/[1 + SGR·(e^{σR} − 1)]. In thermal bands, the transmitted radiance difference τ·ΔL is unchanged, but path radiance raises background flux and noise and compresses dynamic range. This is textbook physics **[foundational]** and was not re-verified here.
- App treatment: offer selectable standard conditions (σ_IR = 0.2 km⁻¹ "STANAG/good" and 0.35 km⁻¹ "poor/humid"), plus a visibility + RH + temperature → σ derivation, plus an expert direct σ or τ(R) table input. Use Kim (not Kruse) for V < 6 km in VIS/SWIR. Allow MODTRAN-style τ(R) import for long paths.

### Gaps
- Tabulated MODTRAN MWIR/LWIR extinction per climate model (mid-latitude summer, tropical, desert, maritime) at 23/5/1 km could not be extracted (figure only).
- No primary source retrieved that quantifies band-averaged non-Beer behaviour, or the size of path-radiance contrast loss for VIS/SWIR range in TRM4 or NVIPM.
- Rain-rate → extinction relations (e.g. σ vs mm/h) were not retrieved.
- Slant-path aerosol scale-height treatment in TRM4 and NVIPM was not documented in accessible sources.

---

## Q2. Turbulence: Cn², r₀, isoplanatic angle, turbulence MTF, and when turbulence limits range

### Takeaway
Near-ground horizontal paths in daytime have Cn² of about 10⁻¹⁴–10⁻¹³ m⁻²/³, sometimes up to 10⁻¹². Under these conditions r₀ is a few cm in VIS/SWIR and roughly 5–50 cm in MWIR/LWIR over a few km. Once D/r₀ > 1 or λ/r₀ approaches the pixel IFOV, turbulence rather than optics sets resolution. This erases MWIR's diffraction advantage over LWIR, so long-focal-length, ground-to-ground identification is the turbulence-limited case. Night, maritime and elevated paths are often weak (10⁻¹⁶–10⁻¹⁵).

### Cited Findings
**Definitions and formulas**
- Fried parameter, spherical wave (point source), as given by Schutte et al.: r₀ = [0.423 k² ∫₀ᴸ Cn²(z)(z/L)^{5/3} dz]^{−3/5}, with k = 2π/λ. When r₀ < D (D/r₀ > 1), image resolution is turbulence-limited. Isoplanatic angle: θ₀ = [2.91 k² L^{5/3} ∫ Cn²(z)(1 − z/L)^{5/3} dz]^{−3/5}. Over long horizontal paths θ₀ is typically very small, so correction must be done patch by patch. Imaging regimes are long exposure, short exposure without scintillation, and short exposure with scintillation. The short/long-exposure distinction is whether image tilt (wander) is removed. — [Schutte et al., "An overview of turbulence compensation," Proc. SPIE 8542, 2012](https://publications.tno.nl/publication/102606/Ug60dZ/schutte-2012-overview.pdf)
- Lawson & Carrano give an alternative spherical-wave r₀ form with coefficient 0.185 and a (z/L)^{5/3} weighting. Note that conventions differ, with coefficients of 0.423 (plane) vs 0.158 or 0.185 (spherical/horizontal) appearing in the literature. — [Lawson & Carrano, "Using historic models of Cn² to predict r₀…," UCRL-CONF-222540 / SPIE Optics & Photonics 2006](https://www.osti.gov/servlets/purl/897959)
- Short-exposure turbulence MTF: MTF_SE(ξ) = exp{−57.4·a·Cn²·L·λ^{−1/3}·ξ^{5/3}·[1 − μ(λξ/D)^{1/3}]}, with a = 3/8 (spherical) or 1 (plane), and μ = 0.5 (far field) or 1 (near field). Setting μ = 0 gives the long-exposure MTF, which equals exp[−3.44(λξ/r₀)^{5/3}]. — [arXiv 2603.01398 (2026)](https://arxiv.org/pdf/2603.01398)
- Short-exposure turbulence MTF extended to annular (obscured) apertures by Fraunhofer IOSB authors, separating the long-exposure kernel from tilt-variance and tilt-phase-correlation corrections. — [Repasi et al., "Short-exposure turbulence effects on the MTF of annular aperture optical systems," *Opt. Eng.* 56(1):015105, 2017](https://www.spiedigitallibrary.org/journals/optical-engineering/volume-56/issue-01/015105/Short-exposure-turbulence-effects-on-the-modulation-transfer-function-of/10.1117/1.OE.56.1.015105.full)

**Cn² profiles and realistic values**
- Hufnagel–Valley: Cn²(h) = 5.94×10⁻⁵³(v/27)² h¹⁰ e^{−h/1000} + 2.7×10⁻¹⁶ e^{−h/1500} + A·e^{−h/100}. Common values are A = 1.7×10⁻¹⁴ m⁻²/³ and v = 21 m/s, with v = 57 m/s for strong wind. The Brookner sunny-day model uses Cn₀² = 3.6×10⁻¹³ at h₀ = 320 m. SLC-Day uses 1.70×10⁻¹⁴ for h < 18.5 m. HV and SLC treat the ground layer poorly. — [Lawson & Carrano 2006](https://www.osti.gov/servlets/purl/897959)
- The horizontal or near-horizontal path is "the most challenging" case, where even the longer wavelengths lose r₀. Raising the platform from 10 m to 20 m increases r₀ by about 50%, and higher platforms on slant paths keep good r₀ except for long visible paths. — [Lawson & Carrano 2006](https://www.osti.gov/servlets/purl/897959)
- Daytime convective Cn² is typically 10⁻¹⁴–10⁻¹² m⁻²/³. Stable night is often below 10⁻¹⁵. This comes from a patent, a lower-quality source. — [US patent 10654499](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10654499)
- Cn² peaks near noon at about 10⁻¹⁴–10⁻¹³. Weak turbulence is about 10⁻¹⁵ and strong about 10⁻¹³. — [ScienceDirect topic overview, "Atmospheric Turbulence"](https://www.sciencedirect.com/topics/materials-science/atmospheric-turbulence)
- Measured "weak turbulence" field cases: Cn² = 2.9×10⁻¹⁶ m⁻²/³ over 15.7 km at sea (FATMOSE, False Bay, South Africa), and 6.9×10⁻¹⁶ over about 7 km on land (NATO SET-165, Dayton, Ohio). — [Schutte et al. 2012](https://publications.tno.nl/publication/102606/Ug60dZ/schutte-2012-overview.pdf)

**MWIR vs LWIR vs VIS under turbulence; impact on DRI**
- Earlier work at a single low turbulence level found similar MWIR/LWIR detection ranges, with an MWIR identification advantage from its smaller diffraction spot. As turbulence increases, the MWIR identification advantage erodes until the bands are about equal, and LWIR is slightly better for some systems. Field measurements in multiple environments show moderate-to-high turbulence is common, so the MWIR advantage holds only under limited conditions, and LWIR can outperform it in daytime desert. The authors recommend dual-band sensors. — [Richardson & Driggers, "Atmospheric turbulence effects on 3rd generation FLIR performance," Proc. SPIE 6207, 2006, DOI 10.1117/12.665836](https://ui.adsabs.harvard.edu/abs/2006SPIE.6207E..06R/abstract)
- The Army still uses LWIR in primary targeting sights, partly because of its performance in high turbulence. This is search-snippet level, and the attribution to this paper is uncertain. Verify before citing. — [Holst & Driggers, "Small detectors in infrared system design," *Opt. Eng.* 51(9):096401, 2012](https://www.spiedigitallibrary.org/JournalArticle/Download?urlId=10.1117%2F1.OE.51.9.096401)
- "In most long range conditions image resolution is limited by atmospheric conditions." Turbulence compensation's main benefit is a longer identification range. — [Schutte et al. 2012](https://publications.tno.nl/publication/102606/Ug60dZ/schutte-2012-overview.pdf)
- LLNL simulated MWIR and LWIR horizontal-path imagery at 2–10 km over several Cn² values to evaluate speckle-imaging recovery. — [LLNL, "Bispectral Speckle Imaging Algorithm Performance…"](https://www.osti.gov/servlets/purl/1108864)

**How the models handle it**
- TRM4: turbulence has been part of the "detailed atmospheric model" since v1 (2010). Turbulence was highlighted as a new feature in the 2017 SPIE paper. — [Fraunhofer IOSB](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html); [Keßler et al. 2017](https://www.researchgate.net/publication/316713606_TRM4_Range_performance_model_for_electro-optical_imaging_systems)
- Perić et al. treat turbulence (heat haze) as a turbulence component of the atmospheric MTF. They call this a first-order approximation, not exact, because the MTF assumes linear shift-invariance while turbulence varies across the image. — [Perić et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)
- NVIPM: NVESD/ARL researchers fed line-of-sight turbulence measured by a JHU/APL laser DIMM (Differential Image Motion Monitor), together with measured system resolution, into NV-IPM to predict performance. NV-IPM therefore accepts a path-integrated Cn² input. — [Science.gov NVESD topic listing](https://www.science.gov/topicpages/n/nvesd+sensor+performance)

### Inferences
- r₀ for a uniform horizontal path, spherical wave, L = 5 km (calc. from r₀ = (0.159 k² Cn² L)^{−3/5}, i.e. 0.423 × 3/8):

  | Cn² (m⁻²/³) | VIS 0.55 µm | SWIR 1.55 µm | MWIR 4 µm | LWIR 10 µm |
  |---|---|---|---|---|
  | 1e-15 (night/weak) | 6.2 cm | 21 cm | 67 cm | 2.0 m |
  | 1e-14 (moderate) | 1.6 cm | 5.4 cm | 17 cm | 50 cm |
  | 1e-13 (strong day) | 0.4 cm | 1.4 cm | 4.2 cm | 13 cm |

- Turbulence blur angle λ/r₀ scales as λ^{−1/5} (nearly band-independent, slightly worse at short λ), while diffraction λ/D scales as λ. When turbulence dominates, the shorter-wavelength resolution advantage (MWIR over LWIR, VIS/SWIR over IR) largely disappears, which is the mechanism behind Richardson & Driggers' result.
- Example (calc.): Cn² = 1e-14, 5 km, MWIR. λ/r₀ ≈ 24 µrad, comparable to a 15 µm pitch / 500 mm focal-length IFOV of 30 µrad. Turbulence is therefore already co-dominant for long-focal-length MWIR ground-to-ground paths in moderate daytime turbulence. LWIR gives λ/r₀ ≈ 20 µrad. A practical "turbulence check" for the app is to flag when λ/r₀ > 0.5 × IFOV or D/r₀ > 1.
- Dror & Kopeika imply the atmospheric MTF should include an aerosol term as well as turbulence, especially morning, evening and in haze.
- App treatment: Cn² via selectable presets (night/overcast about 1e-15, moderate day about 1e-14, hot day/desert about 1e-13), with direct Cn² input for experts and a derived profile option (HV-5/7 or a constant along the path for horizontal paths). Sensor/target heights should enter the slant-path r₀ calculation. Offer a short- vs long-exposure switch: short exposure plus a separate tilt-jitter term suits staring video with frame-to-frame observation, long exposure suits integrated or still frames.

### Gaps
- Exact TRM4 turbulence MTF formulation (short vs long exposure, tilt handling, Cn² path profile) was not available in accessible sources. Fraunhofer authorship of Repasi et al. 2017 suggests a short-exposure plus tilt approach, but this is unconfirmed.
- Exact NVIPM turbulence component equations, default Cn² and the published quantitative ID-range reduction vs Cn² were not retrieved (Richardson & Driggers full text unavailable).
- No source retrieved gives a tabulated percent range loss per Cn² decade for a reference system.

---

## Q3. Target and scene parameters, task criteria and probability

### Takeaway
The NATO/STANAG convention is a 2.3 × 2.3 m vehicle (and a 1.8 × 0.5 m human) with ΔT = 2 K and 50% probability, using Johnson-type cycle criteria (D/R/I ≈ 1 / 3–4 / 6–6.4 cycles, or 2 / 7 / 13 pixels). The TTP metric (NVIPM) uses V50 (reported as about 2 / 7.5–9 / 13 for vehicles with a 3.11 m characteristic dimension) and a logistic TTPF. Contrast definition (RSS including target internal variance), clutter and emissivity can each shift range by factors comparable to or larger than atmosphere. Going from P50 to P90 shortens range to about 0.57× (Johnson TTPF) or about 0.36× (TTP TTPF).

### Cited Findings
**Standard targets and ΔT**
- For modelling and measurement it is "widely accepted" that ΔT = 2 K (citing STANAG 4347), but the real field ΔT cannot be known. Standard targets are a human 1.8 × 0.5 m at ΔT = 2 K and a vehicle 2.3 × 2.3 m at ΔT = 2 K. Laboratory range follows STANAG 4347 (static range performance) and STANAG 4349 (MRTD measurement) at 50% probability. — [Perić et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)
- Emissivity sensitivity: a 1% emissivity change is equivalent to a 0.6 K temperature change in MWIR or 0.9 K in LWIR. Real thermal scenes are often near thermal equilibrium, so emissivity differences contribute significantly to apparent ΔT. — [Perić et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)
- Search snippet (not verified in full text): a paper on DRI specification for the standard NATO target recommends 1, 3 and 6 cycles for D, R and I under STANAG 4347. — [Chevalier, "On the specification of the DRI requirements for a standard NATO target," ResearchGate](https://www.researchgate.net/publication/297497162_On_the_specification_of_the_DRI_requirements_for_a_standard_NATO_target)
- Johnson-based DRI results can differ from other methods by up to about 30%. Atmospheric extinction and true target dimensions are often unspecified, which makes datasheet DRI comparisons unreliable. — ["Measurement and Analysis of the Parameters of Modern Long-Range Thermal Imaging Cameras," *Sensors* 2021](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8434484/)

**Johnson criteria (N50) and their variability**
- Perić et al. Table 3 (50% probability):

  | Task | Detection | Orientation | Recognition | Identification |
  |---|---|---|---|---|
  | Line pairs on target | 1 ± 0.25 | 1.4 ± 0.35 | 4 ± 0.8 | 6.4 ± 1.5 |
  | Pixels on target | 2 | – | 7 | 13 |

  — [Perić et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)
- Johnson/ACQUIRE TTPF: P = (N/N50)^E / [1 + (N/N50)^E], with E = 2.7 + 0.7·(N/N50). For moving targets, N50 is traditionally 2/3 of the static value. N50 was redefined when models moved from 1-D to 2-D characteristic dimension (√area). — [Sandia SAND2015-6368](https://www.osti.gov/servlets/purl/1222446)
- Variability: across 24 IR tests, detection N50 ranged from 0.75 to 4.1 cycles (mean 1.8 ± 0.93). Across 8 visible tests it ranged from 0.72 to 11.7 (mean 4.58 ± 3.45) (Mazz 1998) **[foundational]**. — [Sandia SAND2015-6368](https://www.osti.gov/servlets/purl/1222446)
- O'Connor & Driggers (2003) found that identification N50 differed between the visible (7.5) and IR (11.5) for the same target set, because IR removes cues such as paint colour. — [Sandia SAND2015-6368](https://www.osti.gov/servlets/purl/1222446); [O'Connor & Driggers, Semantic Scholar](https://www.semanticscholar.org/paper/Fifty-percent-probability-of-identification-(N50)-O'Connor-Driggers/1984edbb9854822aa96fa50b54a286147e66051b)
- Small watercraft (characteristic dimension 3.9 m): N50 is 4.0 (VIS), 2.8 (MWIR) and 3.5 (SWIR). V50 is 14.0 (VIS), 10.6 (MWIR) and 11.3 (SWIR) (2008 NVESD study). — [Sandia SAND2015-6368](https://www.osti.gov/servlets/purl/1222446)

**TTP metric / V50 (NVIPM, NVThermIP)**
- TTP TTPF: P = (V/V50)^E / [1 + (V/V50)^E], with E = 1.51 + 0.24·(V/V50). V50 must be determined experimentally for each target set, and there is "no set standard for V50." As a rough conversion, Hixson suggests V50 ≈ 2.7 × N50. — [Sandia SAND2015-6368](https://www.osti.gov/servlets/purl/1222446); [Perić et al. 2019, Eq. 11](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)
- The TTP metric was introduced in Vollmerhausen, Jacobs & Driggers, "New metric for predicting target acquisition performance," *Opt. Eng.* 43(11), 2004. Its examples use a 3.11 m characteristic-dimension vehicle target. — [ResearchGate](https://www.researchgate.net/publication/255636984_New_metric_for_predicting_target_acquisition_performance)
- Reported V50 values (search-snippet level; could not confirm which source gives which set):
  - 2.0 / 7.5 / 13.0 for D/R/I (2004 era).
  - 2 / 9 / 13 for vehicles in a "2013 TTP" table, with a 3.11 m characteristic dimension.

  — [Polish lab-measurement range paper](https://www.researchgate.net/publication/258521549_Determining_the_range_parameters_of_observation_thermal_cameras_on_the_basis_of_laboratory_measurements); [Burgener, U. Arizona dissertation 2021](https://wp.optics.arizona.edu/alumni/wp-content/uploads/sites/113/2023/06/Burgener-Mark-Dissertation-2021.pdf)
- Hixson's group: fitted V50 values improved predictions, but the model's probability-vs-range curves were shallower than human data. Compared with the Johnson criteria, TTP predicted a larger ID-range gain from boost filtering, and perception tests suggested TTP overestimated that gain. — [ResearchGate 340164625](https://www.researchgate.net/publication/340164625_Analysis_and_modeling_of_observer_performance_while_using_an_infrared_imaging_system)

**Contrast definitions and clutter**
- RSS thermal contrast: ΔT_RSS = √[(μ_tgt − μ_bkg)² + σ_tgt²]. This includes target internal variance, not just the mean difference. ACQUIRE-LC / Detect05 clutter-dependent detection N50 = 0.75·C·[(C/ΔT_RSS)² + 1], with C = 1, 1.5, 2.0, 2.7 for low, medium-low, medium and high clutter. — [Sandia SAND2015-6368](https://www.osti.gov/servlets/purl/1222446)
- Detection N50 rose from 0.5 (low clutter) to 2.5 (high clutter) in Schmieder & Weathersby (1983) **[foundational]**. Mazz (1998) reported 1.3–2.5 cycles across four clutter classes, with false detections rising with clutter. — [Sandia SAND2015-6368](https://www.osti.gov/servlets/purl/1222446)
- Detection-probability vs SNR (Rosell-type): P = 0.5 at SNR 2.8, 0.9 at SNR 4.1, 1.0 at SNR 5.5. — [Perić et al. 2019, Table 4](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)

**Models**
- TRM4 replaces targets by equivalent bar patterns whose size, line-pair count and signal difference depend on target and task. It uses "modified Johnson criteria" and the MTDP figure of merit, and MCP in VIS–SWIR. Range is the maximum distance at which the observer perceives the bar-pattern modulation at a specified probability. — [Fraunhofer IOSB](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html)
- NVIPM validation is contested. An advocacy document hosted on nvipm.net claims that "NVIPM is not validated." It argues that only the original NVThermIP/TTP was validated, and that NVIPM's redefinition of the CTF (now depending on target angular size) failed validation. — [nvipm.net document, 2025](https://nvipm.net/wp-content/uploads/2025/09/f48f0eda-e104-49f9-8dc0-288094186a04.pdf). The Army side presents validation data in ["Psychophysical basis and validation data supporting the Army's NVIPM"](https://www.researchgate.net/publication/389524022_Psychophysical_basis_and_validation_data_supporting_the_Army's_Night_Vision_Integrated_Performance_Model). See also ["NVIPM: impact of a recent change on the model's predictive accuracy"](https://www.researchgate.net/publication/322253573_Night_vision_integrated_performance_model_impact_of_a_recent_change_on_the_model's_predictive_accuracy).
- TRM4 can be run as a component inside NV-IPM. — [Teaney, Reynolds, Du Bosq, Repasi, "A TRM4 component for the NV-IPM"](https://www.researchgate.net/publication/299848075_A_TRM4_component_for_the_Night_Vision_Integrated_Performance_Model_NV-IPM)

### Inferences
- P50 → P90, solving each TTPF for P = 0.9 (calc.):
  - Johnson/ACQUIRE: N/N50 = 1.75.
  - TTP: V/V50 = 2.75.
  - In the resolution-limited regime N (or V) ∝ 1/R, so R90 ≈ 0.57·R50 (Johnson) and ≈ 0.36·R50 (TTP). The shallower TTP curve makes P90 ranges much shorter than Johnson-based P90.
  - Users comparing datasheets must know which TTPF and P level is used. A safety-critical app (e.g. border or perimeter) should default to showing P50 and P90 together.
- Clutter (Detect05, calc.): at ΔT_RSS = 2 K, N50 = 0.94 (low clutter, C = 1) and N50 = 5.7 (high clutter, C = 2.7). That is about 6× more cycles needed, which in the resolution-limited regime shortens detection range by up to about 6×. This effect is larger than going from σ = 0.2 to 0.35 km⁻¹.
- Emissivity (calc.): a 3% emissivity contrast in LWIR is about 2.7 K, already larger than the 2 K convention. Diurnal "thermal crossover" (ΔT → 0 at dawn and dusk) can collapse thermal detection range regardless of optics.
- App treatment:
  - Target size: direct input (H×W → √area), with presets for the NATO vehicle 2.3×2.3 m, human 1.8×0.5 m and a 3.11 m vehicle.
  - ΔT: selectable standard (2 K) plus direct input, with an option to derive it from target/background temperatures and emissivities.
  - Reflective bands: target/background reflectance → contrast, with path-radiance reduction.
  - Task criteria: selectable sets (STANAG Johnson 1/3/6 cycles or 2/7/13 px; TTP V50 sets) plus a custom field.
  - Probability: P50/P80/P90 selector.
  - Clutter: low/medium/high selector mapped to C.

### Gaps
- The "ΔT = 1.25 K" convention mentioned in the brief could not be sourced.
- Full STANAG 4347/4349/4350 texts are not public. STANAG 4350 content (MRTD calculation) was not verified, and the cycle definitions in the standard itself (1/3/6 vs 1.5/6.4/12.8 as some calculators quote) remain partly unresolved.
- EN/ISO/IEC DRI standards (e.g. IEC 62676-4 DORI pixel densities for CCTV) were not retrieved.
- Quantitative diurnal ΔT curves for vehicles and humans, and NVESD standard 12-vehicle-set ΔT_RSS values, were not found.
- The V50 values and source mapping should be confirmed against Vollmerhausen et al. 2004 and the current NVIPM defaults.

---

## Q4. Line-of-sight motion and platform (brief)

### Takeaway
Little was retrieved in this session. The models treat LOS jitter and vibration as additional MTFs, and target motion mainly lowers the detection N50. Moving targets need about 2/3 of the static N50.

### Cited Findings
- For moving targets, the detection N50 is traditionally 2/3 of the value for an equivalent static target. Detect05 added moving-target detection. — [Sandia SAND2015-6368](https://www.osti.gov/servlets/purl/1222446)
- Long-exposure imagery through turbulence shows fast random image-centre wander (tilt). Short exposure is defined by removing this tilt. — [Schutte et al. 2012](https://publications.tno.nl/publication/102606/Ug60dZ/schutte-2012-overview.pdf)

### Inferences
- Turbulence tilt and platform jitter both act as random LOS motion. Combined with frame integration time they reduce the MTF as exp[−2π²σ²f²] (Gaussian jitter, standard). The app should take an RMS jitter in µrad as direct input, and should not double-count turbulence tilt when using the long-exposure turbulence MTF.

### Gaps
- No source retrieved for platform vibration MTF values in TRM4 or NVIPM, or for target-motion effects on recognition and identification.

---

## Q5. Which parameters dominate range in practice; size of prediction errors

### Takeaway
Field-oriented sources consistently rank scene/target signature (ΔT, emissivity, clutter) and atmosphere as larger uncertainty sources than the imager's own parameters. Perić et al.'s qualitative error budget gives scene signature 50–250%, target 200% and atmosphere 100%, versus imager 30%. Model-vs-model differences are about 10–30%. Atmosphere dominates long-range detection, and turbulence (plus aerosol MTF) dominates long-focal-length ground-level identification.

### Cited Findings
- Estimated range-prediction inaccuracy contributions (Perić et al. Table 5):

  | Source | Estimated inaccuracy |
  |---|---|
  | Scene signature | 50–250% |
  | Target properties | up to 200% |
  | Observation time | 200% |
  | Atmospheric conditions | 100% |
  | Display and observer | 100% |
  | Thermal-imager parameters | 30% |

  — [Perić et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)
- Weather prediction along the path is "not accurate enough" because the full path data are unknown and transmission depends on range. The image "could be worse than expected in the case of really bad weather," though standard modelling parameters cover most mission conditions. — [Perić et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)
- Model-to-model spread:
  - For under-sampled imagers, NVThermIP predicts about 25% longer ranges than TOD.
  - For well-sampled imagers the two agree within about 10%, except at low contrast.
  - NVThermIP overestimates the impact of noise, which makes it pessimistic for noisy systems.

  — [NVThermIP vs TOD, ResearchGate](https://www.researchgate.net/publication/255630287_NVThermIP_vs_TOD_matching_the_target_acquisition_range_criteria)
- Johnson-based DRI results differ from other methods by up to about 30%. — [*Sensors* 2021, PMC8434484](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8434484/)
- TRM4's developers say the model is validated for several circumstances, mainly by comparing measured and calculated MTDP. An analytical model cannot be expected to reproduce human-observer range exactly. — [Fraunhofer IOSB](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html). Field-trial data are poorly covered in the literature because they are confidential. — [Keßler et al. 2017 snippet](https://www.researchgate.net/publication/316713606_TRM4_Range_performance_model_for_electro-optical_imaging_systems)
- Atmospheric extinction change from 0.2 to 0.35 km⁻¹ reduced predicted thermal range by up to 40% (long-range detection) and by 0–31% for identification. — [Perić et al. 2019, Table 7](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)
- Aerosol MTF is often more significant than turbulence MTF except near midday. — [Dror & Kopeika 1995](https://opg.optica.org/josaa/abstract.cfm?uri=josaa-12-5-970). Moderate-to-high turbulence is common in field measurements and erodes MWIR identification range. — [Richardson & Driggers 2006](https://ui.adsabs.harvard.edu/abs/2006SPIE.6207E..06R/abstract)

### Inferences
- Approximate ranking of sensitivity for a modern, well-designed long-range system (from the cited evidence):
  1. Target ΔT/contrast and clutter (factor-level effects).
  2. Atmosphere: extinction for detection and long ranges; turbulence plus aerosol MTF for ID with long focal lengths near the ground.
  3. Task criteria and probability level (N50 vs V50 sets, P50 vs P90: a 0.36–0.57× range factor).
  4. Imager parameters (about 30%).
- The app should present ranges as bands, e.g. good/standard/poor atmosphere × low/high turbulence. A single number should not imply better than about ±30% accuracy.

### Gaps
- No peer-reviewed field-validation study was found that quantifies range error specifically attributable to atmospheric uncertainty (e.g. MODTRAN-predicted vs measured τ during a DRI trial).
- "Imaging system sensitivity analysis with NV-IPM" (ResearchGate 271426825) was identified but not read: [link](https://www.researchgate.net/publication/271426825_Imaging_system_sensitivity_analysis_with_NV-IPM).

---

## Q6. Recommended treatment of each parameter in a user-facing app (synthesis)

### Takeaway
Expose a small set of standard conditions by default (STANAG-like: σ_IR = 0.2 km⁻¹, ΔT = 2 K, NATO 2.3 m target, P50, low clutter, moderate Cn²). Derive physical quantities (σ from visibility/RH/temperature, r₀ from Cn²/λ/L/heights) where possible, and allow expert direct inputs.

### Cited Findings
- Standard conditions in practice:
  - σ = 0.2 km⁻¹ (good, 23 km visibility) and 0.35 km⁻¹ (poor, 5 km, humid). ΔT = 2 K. NATO vehicle 2.3×2.3 m and human 1.8×0.5 m. P = 50%. — [Perić et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)
  - NVThermIP accepts MODTRAN output, a Beer's coefficient or a transmission table. — [Sandia 2015](https://www.osti.gov/servlets/purl/1222446)
  - HV parameters A = 1.7e-14 and v = 21 m/s. — [Lawson & Carrano 2006](https://www.osti.gov/servlets/purl/897959)
  - Clutter classes C = 1/1.5/2/2.7. — [Sandia 2015](https://www.osti.gov/servlets/purl/1222446)

### Inferences
| Parameter | Physical definition / range | Recommended app treatment |
|---|---|---|
| Extinction σ (or τ(R)) | 0.1–0.5 km⁻¹ clear-to-humid IR; >1 km⁻¹ haze/fog VIS; fog: wavelength-independent VIS–SWIR | **Selectable standard** (good 0.2, poor 0.35) + **derived** (visibility, RH, T, band via Kruse/Kim + water-vapour term) + **direct** σ or τ(R) table/MODTRAN import |
| Meteorological visibility | 1–50 km | Direct input driving the derived σ (scattering) |
| Humidity / temperature | RH %, T °C (water vapour) | Direct input; drives IR absorption term |
| Aerosol model | rural / urban / maritime / desert | Selectable (affects σ and aerosol MTF) |
| Path radiance / SGR | Reflective bands: SGR about 1–5 typical (textbook, unverified here) | Derived from τ and sky/background radiance; expert override |
| Cn² | 1e-16 (sea/night) to 1e-13–1e-12 (hot day) | **Selectable presets** + direct + derived profile (HV, heights for slant paths) |
| r₀, θ₀ | From Cn², λ, L | **Derived only** (display as diagnostics; warn when D/r₀ > 1 or λ/r₀ > ~0.5 IFOV) |
| Exposure regime | Short vs long exposure | Selectable (default short exposure + separate jitter) |
| Target size | √(H×W); 2.3 m NATO, 0.95 m human (1.8×0.5), 3.11 m TTP vehicle | Presets + direct |
| ΔT / contrast | 2 K standard; RSS incl. internal variance; reflective: reflectance contrast | Standard 2 K + direct + derived (T, ε, reflectance) |
| Task criterion | N50 1/3/6 cycles or 2/7/13 px; V50 sets per target class | Selectable sets + custom |
| Probability | P50 / P80 / P90 | Selector; show P50 and P90 together |
| Clutter | Low…high (C = 1–2.7) | Selector |
| Target motion / LOS jitter | Moving → 0.67·N50 (detection); jitter µrad RMS | Toggle + direct jitter input |

### Gaps
- The SGR range and rain-rate presets need sourcing before release.
- The exact defaults currently used inside TRM4.v3/v4 and NVIPM (atmosphere presets, Cn² defaults, V50 tables) are not publicly documented in the sources accessed. Confirm them from the official model manuals if licensed copies are available.
