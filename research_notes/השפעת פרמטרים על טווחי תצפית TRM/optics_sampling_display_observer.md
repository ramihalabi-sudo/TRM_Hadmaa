# How optics, sampling, image processing, display/observer and stabilisation parameters affect image quality and DRI range (TRM4 and NVIPM/TTP)

Scope note. These notes cover the imaging chain after the atmosphere: optics, sampling, processing, display, observer and line-of-sight motion. Atmosphere, target signature and detector noise are covered by sibling notes in the same folder. Some sources are older than 2000 or are model manuals; each is flagged where used. Several primary sources sit behind SPIE or Optica paywalls, or blocked automated fetching (DTIC 403, Optica "please wait" pages). Where only an abstract or a search-index summary could be read, the finding says so.

Two primary documents were read in full text:
- The TRM4.v3 model documentation: R. Gal, S. Keßler, J. Pérez, D. Steiner, W. Wittenstein, *TRM4.v3 Parameter Description and Model Documentation*, Fraunhofer IOSB Technical Report 2021/04. A local copy is in the project root (`TRM4v3_ModelDocumentation_260930_095803.pdf`), cited below as **[TRM4doc]**. It is a licensed, non-public document.
- The NVTherm manual: *Night Vision Thermal Imaging Systems Performance Model – User's Manual & Reference Guide, Rev 5*, U.S. Army NVESD, 12 March 2001, https://zieg.com/links/sensors/NVThermManual5.pdf, cited as **[NVTherm2001]**. It is a foundational, pre-TTP model. Its treatment of sampling, magnification, boost and vibration is the ancestor of NVThermIP/NVIPM.

---

## Q1. Optics: focal length, aperture, F-number, FOV/IFOV, diffraction MTF, aberrations/WFE/Strehl, defocus, transmission, central obscuration, stray light/narcissus, imported (Zemax) MTF, focal-length vs aperture trade, and the Fλ/d (Q) metric

### Takeaway
For modern small-pitch FPAs, one dimensionless number dominates range: Fλ/d, where F is the F-number, λ the wavelength and d the detector pitch. The papers use the same quantity under the names Q and Fλ/p.
- Fλ/d < ~1: detector-limited. Range scales with IFOV = d/f.
- Fλ/d > ~2: optics-limited. Range scales with aperture D/λ.
- Optimum for MWIR target acquisition: about Fλ/d ≈ 2 for high-contrast targets (ΔT ≈ 4 K) and about 1.5 for low-contrast, photon-starved cases (ΔT ≈ 0.1 K) (Holst, Driggers & Furxhi 2020).

Under fixed F-number, growing the focal length grows the aperture by the same factor. Fλ/d and NETD stay roughly constant, so resolution-limited range grows roughly in proportion to f. Aberrations, defocus and obscuration act as multiplicative MTF losses. Transmission and stray light act through SNR and contrast.

### Cited Findings
**Fλ/d / Q: definitions, regimes, optimum values**
- Holst (2007) shows that Fλ/d governs imaging performance in both the spatial and frequency domains, with three metrics: Schade equivalent resolution, MTFA, and the NVThermIP range model.
  - All three show a detector-limited to optics-limited transition at roughly Fλ/d ≈ 0.41–1.0.
  - Source: G. C. Holst, "Imaging system performance based upon Fλ/d," *Opt. Eng.* 46(10), 103204 (2007), doi:10.1117/1.2790066 — [SPIE](https://proceedings.spiedigitallibrary.org/journals/optical-engineering/volume-46/issue-10/103204/Imaging-system-performance-based-upon-F%ce%bbd/10.1117/1.2790066.full). The abstract was read only through a search-engine summary. That summary also says "aliasing does not occur when Fλ/d is below 2", which inverts the physics; see Inferences.
- Holst's SPIE course summary describes the regimes:
  - With large detectors (Fλ/d < 0.5) the system is detector-limited, and acquisition range falls as detector size grows.
  - With small detectors, changing detector size has little effect on range.
  - Source: [SPIE profile/course summary, G. Holst](https://nanophotonics.spiedigitallibrary.org/profile/Gerald.Holst-6419)
- Holst, Driggers & Furxhi (2020), MWIR design study. Quoted from the abstract:
  - For diffraction-limited systems, acquisition range is set by IFOV (detector-limited) when Fλ/d < 1 and by the optics (optics-limited) when Fλ/d > 2.0. Between those values both limits matter.
  - "Optical system aberrations affect system resolution and decrease range performance."
  - Earlier studies (ΔT = 4 K, tracked vehicles) suggest an initial design point of Fλ/d ≈ 2.0.
  - For low-contrast targets (ΔT ≈ 0.1 K), display gain amplifies noise, and "the optimum Fλ/d appears to be about 1.5 for MWIR sensors."
  - LWIR is less affected because of excess photons in the 8–12 µm band.
  - Source: G. C. Holst, R. G. Driggers, O. Furxhi, "Design considerations for advanced MWIR target acquisition systems," *Appl. Opt.* 59(14), 4339 (2020), doi:10.1364/AO.391225 — [Optica](https://opg.optica.org/ao/fulltext.cfm?uri=ao-59-14-4339&id=431507); abstract via [Semantic Scholar API](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1364/AO.391225)
- Holst & Driggers (2012), smallest useful pitch:
  - With F/1 optics the smallest useful detector is 2 µm in MWIR and 5 µm in LWIR. With the more practical F/1.2, 3 µm (MWIR) and 6 µm (LWIR) are recommended.
  - The sampling-limited transition is placed at Fλ/d = 2.
  - Source: G. C. Holst, R. G. Driggers, "Small detectors in infrared system design," *Opt. Eng.* 51(9), 096401 (2012), doi:10.1117/1.OE.51.9.096401 — [SPIE](https://ebooks.spiedigitallibrary.org/journals/optical-engineering/volume-51/issue-9/096401/Small-detectors-in-infrared-system-design/10.1117/1.OE.51.9.096401.full); summary via [Semantic Scholar](https://www.semanticscholar.org/paper/Small-detectors-in-infrared-system-design-Holst-Driggers/b48035677d747fe682e1ed81ec5486248e0509e3)
- Driggers, Vollmerhausen, Reynolds, Fanning & Holst (2012) studied target discrimination range as a function of detector size and pitch for LWIR and MWIR. Only the abstract was available. Source: "Infrared detector size: how low should you go?", *Opt. Eng.* 51(6), 063202 (2012), doi:10.1117/1.OE.51.6.063202 — [SPIE](https://photonicsforenergy.spiedigitallibrary.org/journals/optical-engineering/volume-51/issue-6/063202/Infrared-detector-size-how-low-should-you-go/10.1117/1.OE.51.6.063202.full)
- Driggers et al. (2021) built a hand-calculator or spreadsheet target-acquisition model based on Fλ/d. It shows "robust agreement" with NVIPM across 10 widely differing MWIR and LWIR sensors, and the paper states the conditions under which it is valid. Source: R. Driggers, G. Goranson, S. Butrimas, G. Holst, O. Furxhi, "Simple target acquisition model based on Fλ/d," *Opt. Eng.* 60(2), 023104 (2021), doi:10.1117/1.OE.60.2.023104 — [U. Arizona record](https://experts.arizona.edu/en/publications/simple-target-acquisition-model-based-on-f%CE%BBd/)
- Fiete's optical Q and aliasing (Fiete's paper is foundational, 1999):
  - Fiete defined optical Q = λ·F/p and related it directly to image quality: "Image quality and λFN/p for remote sensing systems," *Opt. Eng.* 38(7), 1229–1240 (1999).
  - Jaffe et al. (2019) summarise that lowering Q raises SNR and sharpness but leads to aliasing below a certain level. They quote Fiete that Q much below 1.0 can cause objectionable aliasing.
  - Source: L. Jaffe, M. Zelinski, W. Sakla, "Remote sensor design for visual recognition with convolutional neural networks," *IEEE TGRS* (2019), doi:10.1109/TGRS.2019.2925813 — [arXiv:1906.09677](https://arxiv.org/pdf/1906.09677)
- An RIT dissertation (Garma, 2015, advised by Fiete) reportedly states that sensors have historically operated at Q ≈ 1. That accepts some aliasing in exchange for higher MTF and SNR. The dissertation compared Q ≈ 2 (Nyquist) designs with Q ≈ 1 in ΔNIIRS. This comes from a search summary and the exact record was not verified: [RIT repository](https://repository.rit.edu/theses/8770)

**How optics enter TRM4**
- Diffraction MTF supports several pupil geometries, each computed from the overlap of two displaced pupils, with optional spectral weighting over the band [TRM4doc §4.2.1, App. B]:
  - circular
  - circular with a circular central obscuration
  - circular truncated in one or both axes, with or without obscuration
  - rectangular
- Aberrations can be entered in two ways [TRM4doc §2.6.6, Eqs. 2.5/2.6, 4.11]:
  - an "aberration parameter" q > 1, applied as MTF_opt = [MTF_diff]^q;
  - a Gaussian blur multiplier, MTF_opt = MTF_diff · exp(−2(π σ_blur ν / f)²).
  - There is no direct RMS-WFE or Strehl input.
- External optics MTF (for example from Zemax or measured) can be entered as an "effective" MTF or as spectral MTFs, for one or both axes, in object-space units (mrad⁻¹) or focal-plane units (mm⁻¹). It replaces the internal calculation, and is mandatory for a "General" aperture type [TRM4doc §2.6.7–2.6.8].
- Optics transmission is a separate input, used in the radiometry/SNR chain [TRM4doc §2.6.9]. Effective focal length, effective F-number and the cold-shield F-number are derived in [TRM4doc §3.4].
- TRM4.v3 release notes list "Modeling of 3D targets and slant path observation; detailed atmospheric model (turbulence and spectral transmissivity)" and per-component MTFs along the chain — [Fraunhofer IOSB TRM4 page](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html)

**Aberrations, WFE and Strehl (general optics references used for parameter conversion)**
- The Maréchal relation maps Strehl ≈ 0.8 to ≈ λ/13.4 RMS wavefront error, the usual "diffraction-limited" criterion — [Fourier optics notes, arXiv:1802.07161](https://arxiv.org/pdf/1802.07161)
- The Maréchal approximation is reliable only for small aberrations (roughly < λ/8 RMS). Beyond that, Strehl can even be multi-valued for a given wavefront variance — [JOSA A preprint, FH Münster](https://www.hb.fh-muenster.de/opus4/files/10919/370793+JOSA+A%2C+after+Pre-Production+Review.pdf)
- Shannon's empirical aberration transfer function (RMS WFE → MTF) showed large errors against numerical calculation in a library author's tests. That author concludes it should not be used where accuracy matters — [prysm documentation](https://prysm.readthedocs.io/en/v0.19/examples/Numerically%20Calculated%20Aberration%20Transfer%20Function.html)
- At equal RMS error, aberration types differ in MTF impact: a quarter-wave of coma costs about 8% image contrast, versus about 20% for spherical aberration. For small independent errors, the combined Strehl is roughly the product of the individual Strehls — [telescope-optics.net (effects)](https://www.telescope-optics.net/effects1.htm); [telescope-optics.net (MTF)](https://telescope-optics.net/mtf3.htm)

**FOV, magnification and sampling geometry in NVTherm (foundational, 2001)**
- The NVTherm manual calls FOV "one of the most important design parameters."
- System magnification is M = FOV_display / FOV_sensor (vertical), where FOV_display is set by display height and viewing distance. Typical values are 0.5–20, and the possible span is about 1/6 to over 200.
- The manual says the largest of three quantities is "roughly speaking" the limiting aspect of the sensor: detector angular subtense (DAS), Airy disc diameter, and sample spacing.
- Source: [NVTherm2001 §2.2.3, §2.2.4, §3.1.2–3.1.3](https://zieg.com/links/sensors/NVThermManual5.pdf)

### Inferences
**Fλ/d and aliasing.** From first principles: optical cutoff in object space ν_c = D/λ (cy/rad), detector Nyquist ν_N = f/(2d). Therefore ν_N/ν_c = (Fλ/d)/2.
- Fλ/d ≥ 2: the optics remove all content above Nyquist, so there is no aliasing.
- Fλ/d < 2: some aliasing is possible.
- This corrects the inverted search-summary wording attributed to Holst 2007.
- Example: an LWIR 12 µm pitch at F/1.0 (λ ≈ 10 µm) gives Fλ/d ≈ 0.83, which is strongly detector-limited and aliased. An MWIR 10 µm pitch at F/4 (λ ≈ 4 µm) gives Fλ/d ≈ 1.6.

**Focal length vs aperture trade.**
- *Fixed F-number.* Scaling f scales D. IFOV = d/f and the diffraction blur λ/D both shrink by the same factor, and Fλ/d and focal-plane irradiance stay the same. NETD therefore stays roughly constant, while resolution-limited DRI range grows about linearly with f and FOV shrinks by 1/f. In an atmosphere-limited or contrast-limited regime the gain is sub-linear.
- *Fixed D (size or weight capped).* Increasing f increases F, so Fλ/d rises: the system becomes better sampled but diffraction-limited. Irradiance per pixel falls as roughly 1/F², which raises NETD. Range gain then saturates once Fλ/d exceeds ~2. Beyond that point the extra focal length mostly costs FOV and SNR, consistent with the Holst/Driggers optimum of ~1.5–2.

**Transmission and stray light.**
- Optics transmission τ_opt scales the signal (NETD ∝ 1/τ_opt for fixed noise). It matters in noise- or contrast-limited regimes (small ΔT, long paths, low light) and little in resolution-limited regimes.
- Stray light and narcissus add a uniform or structured offset. In the models this behaves as reduced contrast or added fixed-pattern noise, not as MTF loss. TRM4 has no explicit stray-light or narcissus input in the v3 documentation; the closest proxies are background or path radiance and fixed-pattern-noise inputs.

**Central obscuration** (ε = D_obs/D, TRM4 models it explicitly). It removes about ε² of the collected energy and depresses mid-frequency MTF, while slightly raising response near cutoff. For ε ≈ 0.3–0.4 typical of catadioptric telescopes, mid-band MTF loss is significant but cutoff is unchanged.

**Recommended app treatment.**
- Expose f, D (or F#), d, λ_band and FOV, and show Fλ/d live with the regime label: detector-limited < 1, mixed 1–2, optics-limited > 2.
- Model aberrations three ways:
  1. a Gaussian blur σ in µm (TRM4 Eq. 2.6);
  2. a TRM4-style q exponent;
  3. a WFE/Strehl entry converted to q or σ, with a warning beyond λ/8 RMS.
- Allow CSV import of external MTF (Zemax) in mm⁻¹ or mrad⁻¹, which overrides diffraction × aberration as in TRM4.
- Model defocus as an additional Gaussian or a geometric-blur MTF.
- Offer the obscuration ratio input that TRM4 already supports.

### Gaps
- No primary source was found that gives DRI-range sensitivity per unit RMS WFE or defocus (for example, "% range per λ/10 WFE"). Holst/Driggers 2020 states the effect only qualitatively in its abstract. The full text may contain curves.
- Fiete's 1999 optimal-Q curves and Holst 2007's numeric range-vs-Fλ/d curves could not be read (paywalled).
- No source was found that quantifies stray light or narcissus in range models.
- Whether GIQE (used for TRM4 NIIRS) is limited to 1 ≤ Q ≤ 2 appeared only in a search summary without a verifiable source.

---

## Q2. Sampling: Nyquist, aliasing, sample phase, microscan/super-resolution, digital zoom/interpolation; TRM4 AMOP vs NVIPM aliasing treatment

### Takeaway
TRM4 and NVIPM treat undersampling in fundamentally different ways.
- **TRM4 (AMOP).** TRM4 replaces the system MTF with AMOP. It simulates the 4-bar pattern at every sample phase and takes the best-phase average modulation. Partially resolved "apparent" 2–3-bar patterns above Nyquist therefore still count. This tends to credit undersampled imagers with range beyond the Nyquist limit: TRM3 up to +30% over Nyquist-based predictions, versus about +15% for NVTherm.
- **NVESD lineage.** The NVESD models apply penalties instead:
  - NVTherm used an "MTF squeeze" driven by the spurious-response ratio.
  - NVThermIP/TTP (Vollmerhausen) introduced aliasing-as-target-dependent-noise.
  - According to Vollmerhausen's own 2025 critique, current NVIPM uses an equivalent-blur method he considers incorrect. That critique is an advocacy document and has no independent confirmation.

For identification, out-of-band spurious response (raster, pixel replication) hurts much more than in-band aliasing. Microscan and super-resolution gave measured gains of +19% (P = 0.5) to +34% (P = 0.7) in ID range in one LWIR field study.

### Cited Findings
**TRM4 / AMOP**
- AMOP definition [TRM4doc §3.11.3]:
  - It is "the maximum average modulation in the reproduced image of a standard 4-bar target."
  - For each pattern frequency, the optimum phase is the phase with the largest average modulation among phases where the maximum number of bars can be resolved.
  - AMOP "cannot be calculated analytically". TRM4 simulates the imaging of the 4-bar pattern in both directions, as a function of phase.
  - Above roughly Nyquist, only 2 or 3 "apparent bars" (aliasing products) can be perceived, and MTDP/MDSP still assesses performance there.
  - MTDP/MDSP is computed only where AMOP > 0.1%; below that it is set to infinity.
- Same AMOP logic in the ECOMOS slides [Keßler & Wittenstein, "ECOMOS scientific background: TRM4," ECOMOS workshop, Ettlingen, 21–22 June 2017](https://ecomos.org/wp-content/uploads/2018/01/ECOMOS_20170621_03_TRM4_Background_WS_Kessler.pdf):
  - Pipeline: 4-bar input → prefiltered → sampled → reconstructed and postfiltered.
  - Average modulation = 1/(2(p_b−1)) Σ (max_i + max_{i+1} − 2·min_i).
  - Optimum phase = the phase with the largest average modulation among phases where the maximum number of bars is visible. An example plot shows average modulation ≈ 0.5–0.7 varying with phase.
  - MTDP = (2·SNR_th/AMOP)·(perceived noise)^½, with spatial integration over the 4-bar pattern and an eye MTF that depends on display luminance.
- Origin: W. Wittenstein, "Minimum temperature difference perceived – a new approach to assess undersampled thermal imagers," *Opt. Eng.* 38(5) (1999), doi:10.1117/1.602265 — foundational; [SPIE](https://www.spiedigitallibrary.org/journals/optical-engineering/volume-38/issue-5/0000/Minimum-temperature-difference-perceived--a-new-approach-to-assess/10.1117/1.602265.short)
- TRM4 overview papers:
  - Keßler, Gal & Wittenstein (2017): TRM4 uses AMOP to "take into account spatial transfer & sampling characteristics" for well-sampled and undersampled imagers. Source: S. Keßler, R. Gal, W. Wittenstein, "TRM4: Range performance model for electro-optical imaging systems," *Proc. SPIE* 10178 (2017), doi:10.1117/12.2262543 — [Semantic Scholar](https://www.semanticscholar.org/paper/TRM4:-Range-performance-model-for-electro-optical-Kessler-Gal/ebdcd392dcd184ece2d08b6976bcd0c406c3f1d9)
  - Pérez et al. (2023): TRM4 "features a validated approach to consider aliasing in the range performance assessment of focal plane arrays". AMOP is being extended to Bayer-filter sampling with demosaicing. Source: J. Pérez, D. Steiner, D. Assaban, M. An, S. Keßler, "Imager performance assessment with TRM4: recent developments," *Proc. SPIE* 12533 (2023), doi:10.1117/12.2668884 — [SPIE](https://www.spiedigitallibrary.org/conference-proceedings-of-spie/12533/2668884/Imager-performance-assessment-with-TRM4-recent-developments/10.1117/12.2668884.short)
- TRM4 sampling-related inputs:
  - microscan/dither, pixel binning, electronic interlace [TRM4doc §2.5.3–2.5.7];
  - electronic zoom by bilinear interpolation or pixel replication, and line/column replication [TRM4doc §2.15.2].
  - Range uses the geometric mean of resolved line pairs from horizontal and vertical MTDP: lp_res = √(lp_h · lp_v) [TRM4doc §3.12.3, Eq. 3.211].
- Range beyond Nyquist: a QWIP staring-FPA study reports that NVTherm predictions typically exceed Nyquist-based ranges by about 15%, and TRM3 by up to 30% — [Range performance modeling for staring focal plane array infrared detectors (record)](https://ubmr.hds.hebis.de/EdsRecord/edscal%252Cedscal.17833315?lng=en)
- Model divergence: a TNO comparison of TOD, NVTherm and TRM3 found the models diverge strongly as undersampling varies. TOD predicts performance driven mainly by sampling frequency, while NVTherm points to pre- and post-filter blur — [Bijl et al., "TOD, NVTherm and TRM3 model calculations: a comparison," TNO repository](https://repository.tno.nl/SingleDoc?docId=8779)

**NVESD / NVIPM lineage**
- NVTherm 2001 MTF squeeze, foundational [NVTherm2001 §1.3](https://zieg.com/links/sensors/NVThermManual5.pdf):
  - Spurious response is split into a total ratio SR, an in-band part and an out-of-band part.
  - Recognition squeeze: MTF_squeeze = (1 − 0.32·SR_H)(1 − 0.32·SR_V).
  - Identification squeeze: MTF_squeeze = (1 − SR_H,out-of-band)(1 − SR_V,out-of-band).
  - Recognition is "moderately affected" by both in-band and out-of-band spurious response. ID is "strongly affected by out-of-band" and not by in-band aliasing. Low-level tasks such as point detection are affected by in-band but not out-of-band aliasing.
- Experimental basis (foundational): R. Vollmerhausen, R. Driggers, B. O'Kane, "Influence of sampling on target recognition and identification," *Opt. Eng.* 38 (1999), doi:10.1117/1.602043; and Driggers, Vollmerhausen, O'Kane, "Equivalent blur as a function of spurious response…," *JOSA A* 16(5), 1026–1033 (1999). Both are listed via [U. Arizona](https://experts.arizona.edu/en/publications/influence-of-sampling-on-target-recognition-and-identification/).
- Aliasing-as-noise (AAN), Vollmerhausen, Driggers & Wilson (2008):
  - The aliased signal is treated as target-dependent noise, added in quadrature with detector noise.
  - It differs from detector noise in two ways: it disappears as target contrast disappears, and it worsens with range because sampling is constant in angle space.
  - An erratum exists.
  - Source: R. Vollmerhausen, R. Driggers, D. Wilson, "Predicting range performance of sampled imagers by treating aliased signal as target-dependent noise," *JOSA A* 25(8), 2055–2065 (2008), doi:10.1364/JOSAA.25.002055 — [U. Arizona](https://experts.arizona.edu/en/publications/predicting-range-performance-of-sampled-imagers-by-treating-alias/); [erratum](https://experts.arizona.edu/en/publications/erratum-predicting-range-performance-of-sampled-imagers-by-treati/)
- Earlier conceptual basis (foundational): Park & Hazra, "Aliasing as noise: a quantitative and qualitative assessment," *Proc. SPIE* 1969 (1993) — [SPIE](https://ebooks.spiedigitallibrary.org/conference-proceedings-of-spie/1969/0000/Aliasing-as-noise-a-quantitative-and-qualitative-assessment/10.1117/12.154738.full)
- The TTP metric "can be applied directly to sampled imagers and to imagers that exhibit colored noise due to frequency boost." Source: R. Vollmerhausen, E. Jacobs, R. Driggers, "New metric for predicting target acquisition performance," *Opt. Eng.* 43(11), 2806–2818 (2004), doi:10.1117/1.1799111 — [U. Memphis record](https://digitalcommons.memphis.edu/facpubs/14027/); [DTIC TR ADA422493](https://apps.dtic.mil/sti/tr/pdf/ADA422493.pdf), which could not be fetched (403).
- Vollmerhausen's 2025 critique of NVIPM: aliasing "has been treated wrong". He states that NVIPM uses an "EB" (equivalent-blur) method, whereas his "AAN" method is correct. He illustrates with a small optical blur moved across pixel boundaries, which changes the display markedly.
  - This is a non-peer-reviewed advocacy document hosted on nvipm.net and apparently authored by R. Vollmerhausen (it refers readers to RHVElectro-Optics.com). Treat it as one expert's contested opinion — [nvipm.net PDF](https://nvipm.net/wp-content/uploads/2025/07/nvipm_final_1-1.pdf)

**Microscan, super-resolution and motion**
- Fanning et al., LWIR prototype field perception test with the NVESD 8-target set:
  - Lockheed Martin's XR super-resolution increased range at 70% ID probability by about 34% and at 50% by about 19%.
  - A model of a more undersampled commercial MWIR sensor predicted a 45% increase.
  - Source: [U. Arizona record, "IR system field performance with superresolution"](https://experts.arizona.edu/en/publications/ir-system-field-performance-with-superresolution/). Numbers were read from the abstract via search summary.
- Krapels, Driggers & Teaney (2005): undersampled-imager acquisition performance improves with sensor or target motion. The human visual system performs a super-resolution-like reconstruction that mitigates some aliasing. Source: "Target-acquisition performance in undersampled infrared imagers: static imagery to motion video," *Appl. Opt.* 44, 7055 (2005), doi:10.1364/AO.44.007055 — [ISC record](https://search.isc.ac/inventory/10/74909.htm)
- NVThermIP modelling guidance for super-resolution covers static scenes only: [Jacobs et al., "NVThermIP modeling of super-resolution algorithms," Proc. SPIE 5784 (2005)](https://digitalcommons.memphis.edu/facpubs/14034)
- TNO, undersampled uncooled imager: the benefit of dynamic super-resolution was smaller than models predicted, and sensor motion showed no positive effect, partly attributed to motion smear. Source: Beintema et al., "Target acquisition performance: effects of target aspect angle, dynamic imaging and signal processing," *Proc. SPIE* 6941, 69410C (2008), doi:10.1117/12.777561 — [TNO](https://repository.tno.nl/islandora/object/uuid:658acc47-bb8c-46f1-a535-8a8d5dba5ea1)
- TRM4 models the MTF loss from integrating during microscan movement, and diagonal microscan changes the eye/brain spatial-integration factor [TRM4doc §3.11.6; app code `trm4/mtf.py: mtf_microscan_integration`, Eqs. 4.36–4.39].

**Digital zoom and interpolation (NVTherm, foundational)**
- Interpolation creates filler pixels with FIR weights. Example: Vollmerhausen 8-pixel kernel 0.604, −0.13, 0.032, −0.006.
- E-zoom is interpolation plus a 2× magnification step that shows ½ of each FOV dimension.
- Interpolation changes the post-sample MTF and therefore the out-of-band spurious response (raster or replication artefacts).
- Source: [NVTherm2001 §2.5.4–2.5.5, §3.2.10–3.2.11](https://zieg.com/links/sensors/NVThermManual5.pdf)

### Inferences
- **Why the models disagree on undersampled sensors.** AMOP gives credit for resolvable apparent bars above Nyquist at best phase. The NVESD approaches penalise spurious response, either as squeeze/blur or as noise. TRM4 and NVIPM can therefore disagree most for strongly undersampled systems (Fλ/d < ~0.7) and least for Fλ/d ≥ 2. A user-facing app should surface the AMOP-vs-MTF gap: a plot of AMOP vs 4/π·MTF_sys with the Nyquist marker, as in TRM4doc Fig. 3.4.
- **Pixel replication vs interpolation for e-zoom.** Replication creates strong out-of-band spurious response, which by the NVESD finding mainly hurts ID. Interpolation reduces it. The app should default e-zoom to bilinear interpolation and warn on replication.
- **Microscan and super-resolution.** Model them as a halved effective sampling pitch, plus the integration-motion MTF, plus a perceived-noise change. Do not assume the full static-scene gain when platform or target motion is high.

### Gaps
- No primary NVIPM documentation was found that confirms which aliasing model (AAN vs equivalent blur) is the current default. Only Vollmerhausen's advocacy document asserts EB.
- No published side-by-side TRM4-AMOP vs NVIPM range comparison for the same undersampled sensor was retrieved. Teaney et al., "A TRM4 component for NV-IPM," *Proc. SPIE* (2015), doi:10.1117/12.2180002, exists ([ResearchGate](https://www.researchgate.net/publication/299848075_A_TRM4_component_for_the_Night_Vision_Integrated_Performance_Model_NV-IPM)) but its content was not accessible.

---

## Q3. Image processing: boost/sharpening, local-area contrast enhancement (LACE), noise filtering, compression

### Takeaway
Linear, shift-invariant filters (boost, Wiener restoration, FIR interpolation, frame integration) enter both models as MTFs that also shape the noise spectrum.
- TRM4 supports only separable 1-D FIR filters with at most 5 coefficients, plus frame integration.
- NVTherm/NVIPM use symmetric FIR filters.

Validated evidence shows that TTP/NVIPM can significantly *overestimate* boost and Wiener range gains. NVIPM predicted more than 50% for a well-sampled low-noise LWIR system, while perception tests showed much less. Johnson criteria underestimated the gain. For an undersampled MWIR, a measured MTDP including boost predicted number-ID range well.

Nonlinear processing (LACE, AGC, compression, turbulence mitigation) is not handled by the analytical models. It is handled by image-based simulation (ECOMOS/OSIS) or by an equivalent-blur approximation. Compression loss was well modelled as a per-pixel equivalent blur.

### Cited Findings
**Boost / Wiener restoration**
- Short, Littlejohn, Bailey & Driggers:
  - NVIPM predicted a range enhancement of more than 50% with Wiener restoration for a notional high-F#, deep-well, small-pitch LWIR system.
  - In human perception experiments on simulated imagery, the TTP model "was found to significantly overestimate the performance improvement due to boost and restoration filtering."
  - Johnson-criteria predictions "underestimated the impact of boost."
  - Source: R. Short, D. Littlejohn, J. Bailey, R. Driggers, "Infrared sensor performance with boost and restoration filtering," *Appl. Opt.* 60(3), 571–579 (2021; online 2020), doi:10.1364/AO.402312 — abstract via [Semantic Scholar API](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1364/AO.402312)
- Adomeit, IOSB, undersampled MWIR:
  - The imager was run with and without five boost filters: four Laplace and one Wiener.
  - Identification range for numbers from perception experiments was in "good correspondence" with limiting frequencies derived from MTDP measured with the filters.
  - Conclusion: Johnson criteria (with measured MTDP) should predict range including boost.
  - Source: U. Adomeit, "Thermal imagers with boost: range prediction with the Johnson criteria," *Proc. SPIE* (Security + Defence 2023), doi:10.1117/12.2680255 — [ResearchGate](https://www.researchgate.net/publication/374935562_Thermal_imagers_with_boost_range_prediction_with_the_Johnson_criteria)
- TRM4 digital filters [TRM4doc §2.15.1–2.15.3]:
  - "All digital filters in TRM4 are one-dimensional filters with one-dimensional kernels," applied separately per axis.
  - They are linear-phase symmetric odd or even FIR with at most 5 coefficients, and the coefficient sum must be positive.
  - Analog high-frequency boost and analog filter MTFs are separate inputs [§2.14].
  - Frame integration (including IIR) is supported [§2.15.3; Eq. 4.72].
- NVTherm boost (foundational) [NVTherm2001 §2.5.6, §3.2.9, Eq. 3-41](https://zieg.com/links/sensors/NVThermManual5.pdf):
  - Any symmetric odd-length FIR is allowed, with H(ξ) = w₁ + Σ 2wₙ cos(2π(n−1)ξ/ξ_s).
  - Example kernel 0.5 / 0.2 / 0.05 (centre outwards).
  - Frame integration "does not make much difference … until the number of frames integrated approaches the number of frames the eye integrates."
- A search summary reports that Preece, Haefner and Fanning developed a 2-D TTP formulation for non-separable filters such as boost, validated against perception experiments and added to NV-IPM. No primary citation was retrieved — [search context: Fanning research listing](https://www.researchgate.net/scientific-contributions/Jonathan-Fanning-2014166752)

**Nonlinear processing (LACE, AGC, turbulence mitigation)**
- The NVIPM core is linear and shift-invariant. Nonlinear processing such as local-area processing and contrast enhancement, turbulence mitigation and fusion is hard to represent. This is reported in NVIPM-related literature surfaced by search; no single primary citation was retrieved — [Teaney & Reynolds, "Next generation imager performance model," Proc. SPIE (2010), doi:10.1117/12.850876](https://www.researchgate.net/publication/252951320_Next_generation_imager_performance_model)
- A Fraunhofer publica record (exact record not verified) reports that ECOMOS's image-based simulator OSIS is being extended with plug-ins for advanced DSP such as compression, local contrast enhancement and digital turbulence mitigation — [publica.fraunhofer.de](https://publica.fraunhofer.de/handle/publica/412162)
- ECOMOS combines the analytical TRM4 with the image-based TOD model and MATISSE atmosphere. TRM4's MTF and noise calculations feed the image-based simulation — [Repasi, Bijl, Labarre, Wittenstein, Bürsing, "The European computer model for optronic system performance prediction (ECOMOS)," Proc. SPIE 10178 (2017), doi:10.1117/12.2262590](https://ebooks.spiedigitallibrary.org/conference-proceedings-of-spie/10178/101780O/The-European-computer-model-for-optronic-system-performance-prediction-ECOMOS/10.1117/12.2262590.full); [ECOMOS TRM4 slides](https://ecomos.org/wp-content/uploads/2018/01/ECOMOS_20170621_03_TRM4_Background_WS_Kessler.pdf)

**Compression**
- O'Shea, Jacobs & Espinola tested two typical algorithms, including JPEG2000, at two compression levels in target-ID perception experiments. The "performance loss caused by image compression is well modeled by the use of an effective per-pixel blur." Source: *Opt. Eng.* 47(1), 013202 (2008), doi:10.1117/1.2829770 — [SPIE](https://journals.spiedigitallibrary.org/journals/optical-engineering/volume-47/issue-01/013202/Effects-of-image-compression-on-sensor-performance/10.1117/1.2829770.full); conference version *Proc. SPIE* 6207 (2006) — [U. Memphis](https://digitalcommons.memphis.edu/facpubs/13732)
- Reducing 14-bit thermal streams to 8 bits for transmission discards image information — [US patent 10986338](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10986338)

### Inferences
- **Boost should not be credited at face value.** If the app models boost, it should do both of the following:
  1. apply the boost MTF to signal *and* to the noise spectrum, since perceived noise rises with boost;
  2. offer a "conservative" option that caps the predicted range gain from boost or restoration (or reports it as a band), given the documented TTP overestimate.
- **Compression and nonlinear processing.** Represent compression as an equivalent Gaussian blur per pixel, following O'Shea et al., with a user-selectable σ (in pixels). Flag LACE, AGC and turbulence mitigation as "not modelled analytically", with TRM4/NVIPM ranges assuming linear processing. Optionally allow a user-specified equivalent MTF.
- **TRM4 compatibility.** The 1-D separable, at most 5-coefficient TRM4 kernel restriction should be mirrored for compatibility, with non-separable 2-D kernels marked as an approximation.

### Gaps
- No quantitative range-vs-compression-ratio (or bitrate) data was retrieved.
- No validated LACE range-effect data was found.
- The Preece/Haefner/Fanning 2-D TTP paper, and its validation magnitudes, could not be identified.

---

## Q4. Display and observer: display type, luminance, size, viewing distance, display MTF, gamma, eye MTF, CTF (Barten), integration time, eye noise, magnification, monocular/binocular, automated observers

### Takeaway
What really matters for range:
1. **System magnification** (display angular size relative to sensor FOV). It sets where the scene frequencies fall on the eye's MTF and CTF, and too low a magnification makes the eye the limiting element.
2. **Display luminance**, when it is low (night-adapted, < ~1 fL). It changes eye MTF width and CTF.
3. **Display contrast loss**: ambient reflection, glare, minimum luminance, AGC brightness.
4. **Display MTF and raster/replication**: out-of-band spurious response.
5. **Observer threshold settings**, SNR_th and eye integration time.

Usually second-order for well-designed military displays: exact display size or angle when magnification is held fixed (stated explicitly for the original TTP), and gamma, which neither TRM4 nor NVTherm exposes as a parameter.

The NVIPM "display angle = target angle" change in the CTF is controversial. Vollmerhausen (2016) reported that it degraded predictive accuracy for the tactical-vehicle set used in procurement.

Automated observers are outside both models' human-observer core. TRM4 adds SNR-threshold subpixel detection and NIIRS/GIQE. Machine and human interpretability "differ significantly."

### Cited Findings
**TRM4 observer and display model** [TRM4doc §2.18, §3.11, §4.2.12]
- Recommended defaults: threshold SNR = **2.5** and eye integration time = **0.1 s**. The eye integrates over subsequent frames.
- Eye MTF uses a simplified Kornfeld–Lawson model, MTF_eye = exp(−Γ·ν/M_sys). Γ is the PSF width, which depends on display luminance (Table 4.2):

  | Display luminance (cd/m²) | Γ |
  |---|---|
  | 3.4×10³ | 0.813 |
  | 3.4×10² | 0.960 |
  | 3.4×10¹ | 1.098 |
  | 3.4 | 1.465 |
  | 0.34 | 1.830 |
  | 0.034 | 2.277 |

  Implemented in the app as `trm4/mtf.py: mtf_eye(r, gamma, m_sys)`, Γ interpolated in log10(fL), with 1 fL = 3.426 cd/m².
- Display luminance is used for the eye MTF only, and is disabled if the eye MTF is external or neglected.
- Viewing is direct (display–observer distance) or through an eyepiece (focal length). This scales the eye MTF through magnification.
- Display types: CRT (Gaussian spot from resolved TV lines), LED, and flat panel (100% fill factor). External display or eye MTF data are optional.
- Turbulence note: the eye integrates over about 100–200 ms, so over many frames the observer experiences long-exposure turbulence [TRM4doc §4.2.13].
- The TRM4 eye model per the ECOMOS slides covers temporal integration, spatial integration over the 4-bar pattern, threshold SNR, and an eye MTF depending on display luminance (simplified Kornfeld–Lawson) — [Keßler & Wittenstein 2017](https://ecomos.org/wp-content/uploads/2018/01/ECOMOS_20170621_03_TRM4_Background_WS_Kessler.pdf)
- TRM4 display-observer concept study with glare: a Barten-based contrast threshold model with additional display-luminance parameters, where glare (for example sun on a cockpit MFD) is modelled as veiling luminance. It was evaluated for a thermal and a visible imager, each on a desktop monitor and a cockpit MFD. It is a study, not confirmed as shipped. Source: C. Günther, S. Keßler, "Concept study for the TRM4 display-observer model: effects of glare on range performance," *Proc. SPIE* 13200, 132000V (2024), doi:10.1117/12.3031651 — [SPIE](https://proceedings.spiedigitallibrary.org/conference-proceedings-of-spie/13200/132000V/Concept-study-for-the-TRM4-display-observer-model--effects/10.1117/12.3031651.full); abstract via [Semantic Scholar API](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1117/12.3031651)

**NVESD / TTP / NVIPM observer**
- The TTP metric integrates the square root of target contrast over the system-modified CTF across frequency. It accounts for blur, noise (including colored noise) and sampling, and was validated on recognition and identification data — [Vollmerhausen, Jacobs, Driggers 2004 (Opt. Eng. 43(11) 2806)](https://digitalcommons.memphis.edu/facpubs/14027/)
- The engineering observer model describes how imager blur and noise affect human vision and how to integrate it into reflected-light and thermal models. Source: R. Vollmerhausen, "Representing the observer in electro-optical target acquisition models," *Opt. Express* 17(20), 17253 (2009), doi:10.1364/OE.17.017253 — abstract via [Semantic Scholar API](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1364/OE.17.017253)
- Display-angle change in NVIPM, per Vollmerhausen (2016):
  - NVIPM "sets that display angle parameter to the angle subtended by the target at the observer's eye", which makes target angle "a primary determinant of performance". This is a change made to improve facial-ID accuracy.
  - It "degrades NVIPM predictive accuracy for the tactical vehicle target set which is often used in hardware procurement specifications."
  - In the original TTP, w = √(horizontal × vertical angular display size), and "for military display sizes and viewing distances, the exact value of that angle makes little difference."
  - Source: R. Vollmerhausen, "Night vision integrated performance model: impact of a recent change on the model's predictive accuracy," *Opt. Express* 24(21), 23654 (2016), doi:10.1364/OE.24.023654 — [Optica](https://opg.optica.org/oe/fulltext.cfm?uri=oe-24-21-23654&id=350879). Quotes are from the search-engine extract and the API abstract.
- The NVIPM-team counterpart defines the CTF with stimulus size equal to the apparent target angle w, the square root of target area in degrees. Source: B. Preece, J. Olson, J. Reynolds, J. Fanning, D. Haefner, "Human vision noise model validation for the U.S. Army sensor performance metric," *Opt. Eng.* 53(6), 061712 (2014), doi:10.1117/1.OE.53.6.061712. The quote is reproduced in the [nvipm.net critique](https://nvipm.net/wp-content/uploads/2025/07/nvipm_final_1-1.pdf).
- That critique argues that for a 1 m target at 1 km through a 10× scope (0.57°), the NVIPM CTF is about 10× higher than the standard CTF at low frequencies, and converges to standard as the target becomes large on the display. It is advocacy, not peer reviewed.
- The critique says TTP uses Barten's numerical CTF: P. G. J. Barten, "Formula for the contrast sensitivity of the human eye," *Proc. SPIE* 5294, 231–238 (2004). The book is P. G. J. Barten, *Contrast Sensitivity of the Human Eye and Its Effects on Image Quality*, SPIE Press (1999), doi:10.6100/IR523072 (foundational). The critique says the formula is "accurate and easy to use, as long as the display size and luminance are entered correctly" — [nvipm.net critique](https://nvipm.net/wp-content/uploads/2025/07/nvipm_final_1-1.pdf)
- In NVTherm (2001, foundational), eye noise is added quadratically (Kornfeld–Lawson) as N_e ∝ 2·A_L·CTF/SNR_T. SNR_T is not fixed: following Rosell and Wilson it varies with display luminance and spatial frequency, so SNR_T = K_eye·CTF. The eye integration time is an NVESD curve fit decreasing with display luminance, and the manual's example uses 0.2 s for a dark display. Source: [NVTherm2001 §1.2.1–1.2.2, §3.1.5.4](https://zieg.com/links/sensors/NVThermManual5.pdf)
- NVTherm display guidance [§2.6.8–2.6.9](https://zieg.com/links/sensors/NVThermManual5.pdf):
  - tactical display on a dark night: **0.1–0.3 fL**;
  - dim conditions: **1–10 fL**;
  - room light: **≥ 30 fL**.
  - A non-zero minimum display luminance (ambient reflection, or a brightness control raised for low-contrast scenes) reduces displayed contrast and raises MRT.
  - E-zoom doubles magnification per step.

**Validation of observer models**
- A lab experiment with dismounted-soldier targets compared human performance with NV-IPM TTP and Johnson variants. Some model versions fit detection reasonably, but "for the identification task all models substantially overestimated performance." Source: *Proc. SPIE* 10625, 106250R (2018), doi:10.1117/12.2304607 — [SPIE](https://electronicimaging.spiedigitallibrary.org/conference-proceedings-of-spie/10625/106250R/Validating-models-of-target-acquisition-performance-in-the-dismounted-soldier/10.1117/12.2304607.full)

**Automated (machine) observers**
- Jaffe et al. built experimental systems with CNNs on overhead imagery. They conclude "machine and human interpretability differ significantly," while computer-vision performance is "largely self-consistent across a range of disparate conditions" — [Jaffe, Zelinski, Sakla 2019, arXiv:1906.09677](https://arxiv.org/pdf/1906.09677)
- TRM4 2023 development work:
  - Subpixel target SNR as a function of target position on the detector matrix, giving best-case and worst-case detection ranges from the threshold SNRs of detection algorithms (an automated-detection criterion).
  - NIIRS via the latest GIQE for aerial imaging.
  - Source: [Pérez et al. 2023](https://www.spiedigitallibrary.org/conference-proceedings-of-spie/12533/2668884/Imager-performance-assessment-with-TRM4-recent-developments/10.1117/12.2668884.short)
- The IOSB TRM4 page lists TRM4.v4 (August 2026) with color cameras, sub-pixel detection including air-to-air, and ground-resolved distance — [Fraunhofer IOSB](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html)
- A 2024 Russian-language study estimates thermal-imager 50%/100% identification range with a pre-trained CNN and proposes a minimum PSNR for stable network identification — [Helveh, Kobozev, Nikonorov (2024)](https://izvuz_tn_eng.pnzgu.ru/tn8423). Lower confidence: only the abstract was seen.
- FFI study of detection range versus number of target pixels for small vessels — [van Rheenen & Thomassen, "Detection: how many pixels are required?"](https://ffi-publikasjoner.archive.knowledgearc.net/handle/20.500.12242/2800)

### Inferences
**Worked example (TRM4 eye model).** Take an object-space frequency equal to Nyquist of a 60 µrad IFOV system: 8.3 cy/mrad.
- At M_sys = 5 it reaches the eye at 1.67 cy/mrad (~29 cy/deg).
- With Γ ≈ 1.47 (≈ 3.4 cd/m² ≈ 1 fL): MTF_eye ≈ exp(−1.47 × 1.67) ≈ 0.09, so the eye is limiting.
- At M_sys = 15: MTF_eye ≈ 0.44.
- At 100 fL (Γ ≈ 0.96) and M = 5: MTF_eye ≈ 0.20.
- **Magnification is the dominant display/observer lever. Luminance matters mostly below ~1–10 fL.** The values are computed from TRM4doc Table 4.2 and Eq. 4.79.

**Parameters that are usually negligible**, provided the observer is not eye-limited:
- display physical size at fixed magnification;
- display luminance above a few tens of fL;
- gamma, which has no parameter in TRM4 v3 or NVTherm.

**Parameters that are not negligible:**
- glare and minimum luminance (contrast loss);
- low night-adapted luminance;
- pixel replication or visible raster (out-of-band spurious response).

**Recommended app treatment.**
- Inputs:
  - display type;
  - pixel pitch or count, or an external display MTF;
  - operating luminance (cd/m² or fL);
  - minimum luminance or veiling luminance;
  - viewing distance or eyepiece focal length;
  - SNR_th (default 2.5);
  - eye integration time (default 0.1 s).
- Outputs: computed system magnification, plus a warning if the eye MTF at sensor Nyquist is < ~0.2, meaning magnification is too low.
- Model choice: offer a "Human observer (TRM4 MTDP/Johnson)" mode and an "Automated detector (SNR threshold / pixels-on-target)" mode, labelled as not interchangeable.

### Gaps
- No primary quantitative source was found for:
  - binocular vs monocular gain (Barten's model includes a binocular factor, but the paper was not accessible);
  - gamma effects on range;
  - the exact NVIPM default display parameters.
- The NVIPM CTF definition controversy has only two sides represented: Vollmerhausen (2016 and the 2025 critique) versus Preece et al. (2014). An independent adjudication was not found.

---

## Q5. Stabilisation and motion: LOS jitter, platform vibration, motion blur during integration, target/scene motion

### Takeaway
Both model families represent random LOS jitter as a Gaussian MTF, exp(−2π²σ²ν²), with σ the RMS jitter in object space.
- Sinusoidal vibration is a Bessel J₀ MTF; TRM4 models it explicitly.
- Linear motion during integration is a sinc MTF; TRM4 models it, including smear across frame integration, interlace and microscan.
- Only MTF loss is modelled, not image distortion.

Low-frequency drift (< ~5 Hz) is tracked by the eye and excluded. The Gaussian form is valid when RMS motion is < ~⅓ IFOV.

US Army practice assumes about 70 µrad RMS LOS jitter in NVIPM range calculations for vehicle sights. Jitter therefore dominates for narrow-FOV sights whose IFOV is comparable to or smaller than 70 µrad.

### Cited Findings
- TRM4 stabilisation [TRM4doc §2.19, §4.2.10, Eqs. 4.65–4.73]:
  - MTF_stab = MTF_lin · MTF_ran · MTF_sin.
  - Random vibration: Gaussian, MTF = exp(−2π²σ_stab²ν²), with σ defined at exp(−½) of the peak of the amplitude PDF.
  - Sinusoidal vibration: J₀(2π·a·ν).
  - Linear motion: sinc(t_int·ω_lin·ν) for staring or microscanned imagers. Further sinc terms cover smear across interlaced fields or frame integration, and an IIR frame-integration motion MTF.
  - "Only the first effect, MTF degradations, is modelled … The modelling is basic." Low-frequency stabilisation errors "often [have] no degrading effect on image perception." The documentation suggests splitting low- and high-frequency components.
  - The eye is assumed not to add target smear.
  - App implementation: `trm4/mtf.py: mtf_random_vibration`, `mtf_sinusoidal_vibration`, `mtf_iir`.
- NVTherm (foundational) [NVTherm2001 §2.3.7, §3.2.4](https://zieg.com/links/sensors/NVThermManual5.pdf):
  - Vibration/stabilisation blur is Gaussian, specified as RMS, FWHM or 1/e in mrad in object space.
  - "Motions with a period less than 5 Hz are tracked by the eye and are not included."
  - Gimbal motions are often sinusoidal, but "if the RMS motion is less than about 1/3 of an IFOV, then the Gaussian MTF is a reasonable approximation."
- US Army practice: "the USG typically uses jitter value around 70 micro radian RMS line of sight jitter." Ranges are expressed as 70% identification ranges computed by NV-IPM. The Q&A also cites an ID V50 of 13 cycles for a 3.1 m × 3.1 m vehicle-size target. Source: SAM.gov solicitation "Long Range Thermal Imaging Module for Remote Weapon Systems" — [SAM.gov](https://sam.gov/opp/ed00fb73aaa848dc96a1bf685bd2d40d/view); [SAM.gov (related notice)](https://sam.gov/opp/1b1b1e1a988a458e8bd658eb2cc38e18/view). This is a procurement document, not peer reviewed.
- Rule of thumb: once sightline motion exceeds about 25% of pixel pitch during the detector stare time, MTF loss can affect system performance. Linear (translational) jitter matters less at long range — [US patent 9239468, "Imaging device"](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9239468)
- Representative stabilised-sight specification: 0.1 mrad stabilisation accuracy (elevation and azimuth) with a 3 km identification claim — [Elbit MGS datasheet](https://www.elbitsystems-uk.com/what-we-do/land/combat-vehicle-systems/optronics/modular-gunner-sight-mgs.pdf). This is a vendor claim.

### Inferences
**Worked example (Gaussian jitter MTF at the sensor Nyquist frequency, ν_N = 1/(2·IFOV)):**

| RMS jitter σ | MTF at ν_N |
|---|---|
| 0.25 IFOV | ≈ 0.74 |
| ⅓ IFOV | ≈ 0.58 |
| 0.5 IFOV | ≈ 0.29 |
| 1 IFOV | ≈ 0.007 |

- With σ = 70 µrad and a 30 µrad-IFOV narrow-FOV sight, σ ≈ 2.3 IFOV. Resolution is then jitter-limited and range is set by jitter, not by optics or detector.
- In wide FOV (IFOV ≈ 200 µrad), the same jitter costs little.

**Recommended app treatment.**
- Inputs:
  - RMS random jitter in µrad, high-frequency part only;
  - sinusoidal amplitude in µrad;
  - linear angular rate in mrad/s together with integration time;
  - frame-integration count.
- Display σ/IFOV with a warning above ~⅓, the limit of Gaussian validity.
- State that drift below ~5 Hz is excluded.

### Gaps
- No published closed-form or tabulated mapping from µrad RMS jitter to percent DRI range loss was found. The DRDO *Defence Science Journal* paper on LOS jitter and DRI could not be fetched (DNS failure).
- Target or scene motion effects on human acquisition beyond super-resolution or smear (search, dynamic tasks) are outside both models' static-task assumptions. STANAG 4347 nominal range is "static performance, no search" [TRM4doc §1.3].

---

## Q6. What validated sensitivity studies say about the ranking of these parameters

### Takeaway
Within the sensor, range is dominated by the following, in order:
1. Fλ/d together with IFOV, which sets the resolution limit. Holst/Driggers show that a Fλ/d-only model reproduces NVIPM across 10 sensors.
2. Sensitivity (NETD or NES) for low-contrast targets.
3. Sampling and aliasing treatment, which accounts for up to about 15–30% model-to-model range differences for undersampled FPAs.
4. Jitter in narrow FOV.
5. Display magnification and luminance when they are badly chosen.

Across the whole problem, imager parameters contribute the least uncertainty. Perić et al. estimate:

| Factor | Inaccuracy |
|---|---|
| Imager parameters | ~30% |
| Display & observer | ~100% |
| Atmosphere | ~100% |
| Target properties | up to 200% |
| Observation time | ~200% |
| Scene signature | 50–250% |

Model–experiment discrepancies are largest for ID and for nonlinear or boost processing.

### Cited Findings
- Perić et al., Table 5, range-prediction inaccuracy factors:
  - scene signature 50–250%;
  - target properties up to 200%;
  - atmospheric conditions 100%;
  - thermal imager parameters 30%;
  - display and observer 100%;
  - observation time 200%.
  - The authors argue that "thermal imager model accuracy contributes the least" to overall range inaccuracy.
  - They report Johnson cycles: detection 1 ± 0.25, orientation 1.4 ± 0.35, recognition 4 ± 0.8, identification 6.4 ± 1.5.
  - Example system ranges for a human target (geometric vs NVThermIP standard and bad atmosphere vs lab MRTD/STANAG 4347): for SYS2, ID 6.5 / 5.5 / 5.3 / 4.6 km.
  - Source: D. Perić, B. Livada, M. Perić, S. Vujić, "Thermal imager range: predictions, expectations, and reality," *Sensors* 19(15), 3313 (2019), doi:10.3390/s19153313 — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6696215/)
- Fλ/d-only model vs NVIPM: "robust agreement" across 10 MWIR and LWIR sensors — [Driggers et al. 2021](https://experts.arizona.edu/en/publications/simple-target-acquisition-model-based-on-f%CE%BBd/). Optimum Fλ/d is about 2 (high contrast) to 1.5 (low contrast, MWIR) — [Holst, Driggers, Furxhi 2020](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1364/AO.391225)
- Undersampling: NVTherm predictions exceed Nyquist ranges by about 15%, and TRM3 by up to 30% — [QWIP FPA study record](https://ubmr.hds.hebis.de/EdsRecord/edscal%252Cedscal.17833315?lng=en). TOD, NVTherm and TRM3 diverge strongly when undersampling varies — [TNO comparison](https://repository.tno.nl/SingleDoc?docId=8779)
- Boost: TTP overestimates the gain (NVIPM predicted > 50%), and Johnson underestimates it — [Short et al. 2021](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1364/AO.402312). Measured MTDP with boost gives good correspondence — [Adomeit 2023](https://www.researchgate.net/publication/374935562_Thermal_imagers_with_boost_range_prediction_with_the_Johnson_criteria)
- ID overestimation: all models substantially overestimated identification performance for dismounted-soldier targets — [SPIE 10625 106250R (2018)](https://electronicimaging.spiedigitallibrary.org/conference-proceedings-of-spie/10625/106250R/Validating-models-of-target-acquisition-performance-in-the-dismounted-soldier/10.1117/12.2304607.full)
- NVIPM model change (display angle): predictive accuracy degraded for the tactical-vehicle set — [Vollmerhausen 2016](https://opg.optica.org/oe/fulltext.cfm?uri=oe-24-21-23654&id=350879)
- Super-resolution field gains: +19% at P = 0.5 and +34% at P = 0.7 ID range (LWIR), with a model prediction of +45% for a more undersampled MWIR — [Fanning et al.](https://experts.arizona.edu/en/publications/ir-system-field-performance-with-superresolution/)
- A dedicated sensitivity-analysis method exists in NV-IPM: J. Fanning, B. Teaney, "Imaging system sensitivity analysis with NV-IPM," *Proc. SPIE* 9071, 90710J (2014), doi:10.1117/12.2052731 — [Semantic Scholar](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1117/12.2052731). Content not retrieved.
- TRM4 validity is "nominal range performance" under the standard STANAG 4347 conditions:
  - target 2.3 × 2.3 m, ΔT = 2 K;
  - detection, recognition, identification = **1 / 3 / 6 line pairs**;
  - atmosphere σ = 0.2 km⁻¹ or 1.0 km⁻¹;
  - static task, no search.
  - IOSB cautions that "it cannot be expected to find exactly the same range performance in human observer experiments."
  - Sources: [TRM4doc §1.3, Table 2.1]; [Fraunhofer IOSB TRM4 page](https://www.iosb.fraunhofer.de/en/projects-and-products/trm4.html)

### Inferences
**Suggested ranking for a user-facing sensitivity panel** (sensor-side parameters, typical tactical thermal case):

| Rank | Parameter | Notes |
|---|---|---|
| 1 | Focal length / IFOV | Roughly linear range lever at fixed F# |
| 2 | Fλ/d (F#, pitch, λ) | Regime and optimum ~1.5–2 |
| 3 | NETD / sensitivity | Dominant for low ΔT, poor atmosphere and MWIR |
| 4 | Jitter σ/IFOV | Dominant for narrow FOV |
| 5 | Optics aberration / defocus | Multiplicative MTF; WFE ≤ λ/14 RMS is near-negligible |
| 6 | Sampling treatment, microscan / super-resolution | 15–45% |
| 7 | Display magnification and luminance | Large when mis-set, otherwise small |
| 8 | Boost / processing | Credit conservatively |
| 9 | Compression | Equivalent blur |

This ranking is an inference synthesised from the cited studies, not a published table.

**App UX.** The app should run its own one-at-a-time ±x% sensitivity sweep and show tornado bars. It should also display the uncertainty context from Perić et al., so users understand that a ±30% imager-model uncertainty sits inside ±100–250% scenario uncertainty.

### Gaps
- No published, peer-reviewed tornado or sensitivity ranking of optics/sampling/display/observer parameters for TRM4 or NVIPM was retrieved. The Fanning & Teaney 2014 full text was not accessible.
- No validated TRM4-vs-NVIPM range comparison on a common sensor set was found.
