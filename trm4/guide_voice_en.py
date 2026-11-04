"""English narration of the interactive guide (the screen stays in Hebrew; the user may choose to listen in English).

PARAMS mirrors the core entries of guide_he.PARAMS (title, impact_note, what, why, typical, source, mistakes) and
STEPS the hand-written steps of guide_he.LESSONS, keyed by (lesson id, Hebrew step title).  Each translation was made
from a given Hebrew text: tools/make_guide_voice.py --stamp records a hash of that text in
assets/voice/en_sources.json, and tests/test_guide_voice.py reports a translation whose Hebrew source changed since.
A field without an entry here is narrated in English from its form label, its impact rating and the check result.
"""

LESSONS = {
    "first": ("Your first calculation", "From a ready template to detection, recognition and identification "
                                         "ranges, in the Quick Prediction workflow."),
    "engineering": ("Entering a real system", "Optics, detector, display and stabilization, in order of impact, in "
                                              "the Engineering Analysis workflow."),
    "results": ("Reading the results and improving them", "What limits the range, what is most worth improving, "
                                                           "uncertainty, and the Hebrew report."),
    "tour": ("A full tour of the application", "Every page and every field your project shows, group by group: "
                                               "what each field means, a check of your value and its effect on "
                                               "the range."),
}

IMPACT = {3: "High impact on the range", 2: "Medium impact on the range", 1: "Low impact on the range",
          0: "Does not affect the range"}

PAGES = {
    "General": "the first decisions: the sensor category, field or laboratory, and video or a single image.",
    "Basic imager": "frame rate, field of view check, micro-scan, pixel binning and exposure timing.",
    "Optics": "the aperture, the focal length, the lens MTF and the transmission. This is where the IFOV, "
              "diffraction and the amount of light are set, some of the strongest levers on the range.",
    "Detector geometry": "the number of pixels, the pitch and the active size. Together with the focal length, the "
                         "pitch sets the IFOV.",
    "Detector sensitivity": "the spectral band, the noise, the integration time, the well and the cold shield. "
                            "This matters mostly in noise-limited systems: at night, or with low contrast.",
    "Signal processing": "frame averaging, filters, zoom, compression and the tone curve. Most fields here are off "
                         "by default.",
    "Display & observer": "how the observer sees the image: a monitor or an eyepiece, the viewing distance, the "
                          "brightness and the observer calibration constants.",
    "Stabilization & MTFs": "line of sight motion: jitter, linear motion and vibration. In a narrow field of view "
                            "this is an important lever.",
    "Target & scenario": "the target, the contrast, the geometry and the task criteria, the strongest levers on "
                         "the range.",
    "Irradiance": "the light source of a reflective sensor. In a thermal project this page is not used.",
    "Atmosphere & turbulence": "attenuation dominates detection; turbulence blurs mostly in the visible band and "
                               "on long ground paths by day.",
    "Metadata": "documentation of imported data and operating modes. It is not part of the calculation, but it goes "
                "into the report.",
    "Validation data": "laboratory measurements, such as MRTD, MTF and NETD, to compare with the prediction.",
}

HOME = ("Choose a lesson. Each lesson takes you through the real screens, highlights the field and checks the value "
        "you entered. You can also run a check of all your values at once, and while the guide is open, clicking a "
        "field of the form shows its explanation here.")

PARAMS = {
    "category": {
        "title": "Sensor category, the spectral band",
        "impact_note": "It sets the whole structure of the calculation.",
        "what": "It sets how the model describes the scene. Thermal: temperatures only, for MWIR and LWIR. Visible: "
                "reflectances and an illumination source, for visible, NIR and SWIR. General: both reflection and "
                "emission, for example MWIR by day.",
        "why": "This is the first decision of the project. It decides which parameters are shown and which "
               "radiometry is calculated.",
        "typical": ["A cooled or uncooled thermal camera: Thermal.", "A day camera, NIR, or a SWIR night camera: "
                    "Visible.", "MWIR that also sees sun reflections: General."],
        "source": "The camera datasheet, the waveband.",
        "mistakes": ["Choosing Thermal for a SWIR camera. SWIR is a reflective sensor, so it is Visible."],
    },
    "imager_type": {
        "title": "Thermal detector type",
        "impact_note": "It selects the noise model.",
        "what": "Cooled: a cooled photon detector, such as InSb, MCT or XBn, with an integration time and an "
                "electron well. Uncooled: a microbolometer, with an NETD and a thermal time constant.",
        "why": "It sets the noise model. In a bolometer the sensitivity is given by the NETD; in a cooled detector "
               "it is calculated from the detector data.",
        "typical": ["A camera that needs a cooler, such as a Stirling, at F/4 to F/5.5: Cooled.",
                    "A light camera at F/1 to F/1.4, with a 12 to 17 micron pitch: Uncooled."],
        "source": "The datasheet: cooled or uncooled. VOx or amorphous silicon means uncooled.",
        "mistakes": [],
    },
    "mode.environment": {
        "title": "Field or laboratory",
        "impact_note": "Without Field there are no ranges in the field.",
        "what": "Field: performance at range, through the atmosphere, as range curves. Laboratory: performance at "
                "the camera entrance, without an atmosphere, as MRTD or MTDP.",
        "why": "To predict DRI ranges, choose Field. Laboratory is for comparing with laboratory measurements.",
        "typical": ["Range prediction: Field."],
        "source": "The purpose of the analysis.",
        "mistakes": ["Calculating in Laboratory mode and expecting ranges in kilometers."],
    },
    "mode.stream": {
        "title": "Video or a single image",
        "impact_note": "It matters mostly in noise-limited systems.",
        "what": "Video: the eye integrates several frames and cleans temporal noise. Still: the observer looks at "
                "a single frame.",
        "why": "In video the effective noise is lower, so the range is usually longer.",
        "typical": ["Live viewing on a monitor: Video.", "Photography or image intelligence: Still."],
        "source": "How the system is used.",
        "mistakes": [],
    },
    "optics.f_mm": {
        "title": "Focal length",
        "impact_note": "It is especially strong when the system is sampling limited.",
        "what": "The effective focal length of the lens. Together with the detector pitch it sets the IFOV, the "
                "angle each pixel sees, and the field of view.",
        "why": "A longer focal length means each pixel sees a smaller angle, so more pixels fall on the target and "
               "the range is longer. In uncooled LWIR this is the strongest hardware lever, with an elasticity of "
               "0.75 to 0.87. In cooled MWIR with a fixed diameter the effect is small, because there the diameter "
               "is the limit.",
        "typical": ["A handheld thermal camera: 25 to 75 millimeters.", "A ground surveillance system: 100 to 300 "
                    "millimeters.", "A long range or airborne system: 300 to 1500 millimeters."],
        "source": "The lens datasheet. For a zoom lens, enter the focal length of the position you analyze, usually "
                  "the narrow field of view.",
        "mistakes": ["Entering centimeters instead of millimeters.", "Changing the focal length without updating "
                     "the diameter. That changes the F-number too."],
    },
    "optics.aperture": {
        "title": "How the aperture is defined",
        "impact_note": "A choice of input form.",
        "what": "Clear aperture diameter: you enter the exact diameter D, which is correct for diffraction and "
                "radiometry. F-number: you enter only the F-number, and a round aperture without obscuration is "
                "assumed.",
        "why": "The diameter D is what sets diffraction and the amount of light. When the datasheet gives the "
               "diameter, prefer it.",
        "typical": ["The datasheet gives D: Clear aperture diameter.", "Only the F-number is known: F-number."],
        "source": "The lens datasheet.",
        "mistakes": [],
    },
    "optics.D_mm": {
        "title": "Aperture diameter",
        "impact_note": "It is strong when the system is diffraction limited.",
        "what": "The diameter of the entrance pupil of the lens. The F-number is the focal length divided by D.",
        "why": "It sets the diffraction limit and the amount of signal. In cooled MWIR and in night systems, such "
               "as SWIR, this is the strong lever, with an elasticity of up to 0.93 for identification. In uncooled "
               "LWIR the effect is small, about 0.15.",
        "typical": ["Uncooled at F/1 to F/1.4: D is close to the focal length.", "Cooled MWIR at F/4 to F/5.5: D is "
                    "the focal length divided by 4 to 5.5."],
        "source": "The datasheet, as the aperture or the entrance pupil, or the focal length divided by the "
                  "F-number.",
        "mistakes": ["Entering the F-number instead of the diameter.", "Entering the radius instead of the "
                     "diameter."],
    },
    "optics.F_general": {
        "title": "Effective F-number",
        "impact_note": "It acts through the diameter D.",
        "what": "The ratio between the focal length and the aperture diameter.",
        "why": "A small F-number gives more light and less diffraction blur. In a cooled camera the F-number has to "
               "match the cold shield.",
        "typical": ["Uncooled: F/1 to F/1.4.", "Cooled MWIR: F/4 to F/5.5.", "A day camera: F/2 to F/8."],
        "source": "The datasheet.",
        "mistakes": [],
    },
    "optics.tau_opt": {
        "title": "Optics transmission",
        "impact_note": "It matters at night and in low signal systems.",
        "what": "The fraction of the light that passes through the lenses, from 0 to 1, without the central "
                "obscuration.",
        "why": "It reduces the signal directly. It is significant in photon starved systems, such as SWIR at "
               "night, with an elasticity of up to 0.36. It hardly matters in an uncooled camera.",
        "typical": ["A good thermal lens: 0.8 to 0.9.", "A complex zoom, or a lens with a window: 0.6 to 0.75."],
        "source": "The datasheet or a measurement.",
        "mistakes": ["Entering a percentage, 85, instead of a fraction, 0.85."],
    },
    "detector.n_h": {
        "title": "Number of horizontal pixels",
        "impact_note": "It sets the field of view, not the range.",
        "what": "The number of columns of the detector, for example 640 in a 640 by 512 detector.",
        "why": "Together with the pitch and the focal length it sets the field of view. It does not change the "
               "range itself, only the width of the field.",
        "typical": ["Thermal: 320, 640 or 1280.", "Visible: 1920, 2048 or 4096."],
        "source": "The detector or camera datasheet.",
        "mistakes": [],
    },
    "detector.pitch_h_um": {
        "title": "Pixel pitch",
        "impact_note": "It depends on the F lambda over d ratio.",
        "what": "The distance between the centers of neighboring pixels, in microns.",
        "why": "Together with the focal length it sets the IFOV, which is the pitch divided by the focal length. A "
               "smaller pixel with the same focal length puts more pixels on the target, but only if the optics are "
               "sharp enough. In LWIR, going from 17 to 12 microns added 22 to 31 percent to the range; in MWIR at "
               "F/4 it changed almost nothing.",
        "typical": ["Uncooled: 10, 12 or 17 microns.", "Cooled: 8 to 15 microns.", "A CMOS day camera: 1.4 to 6 "
                    "microns."],
        "source": "The detector datasheet, as the pixel pitch. You can also use Run, Detector lookup.",
        "mistakes": ["Confusing the pitch with the size of the sensitive area, the fill factor."],
    },
    "detector.noise_mode": {
        "title": "Source of the noise data",
        "impact_note": "A choice of source, not a value.",
        "what": "Physics model: the noise is calculated from the detector data. Measured camera NETD: the measured "
                "NETD replaces the noise model.",
        "why": "When there is a measured NETD of the complete camera, it is a more reliable source than a "
               "calculation.",
        "typical": ["The camera datasheet gives an NETD: Measured."],
        "source": "The datasheet or a measurement.",
        "mistakes": ["Entering a detector-level NETD as if it were the camera's. You need the F-number and the "
                     "transmission it was measured with."],
    },
    "detector.netd_mK": {
        "title": "NETD, the thermal sensitivity",
        "impact_note": "It matters with low contrast and in bad weather.",
        "what": "The smallest temperature difference that gives a signal to noise ratio of one. The smaller it is, "
                "the more sensitive the camera.",
        "why": "It matters less than expected: the elasticity is at most 0.2 in most cases. It matters when the "
               "contrast is low, in bad weather, or with a long focal length.",
        "typical": ["Uncooled: 30 to 80 millikelvin.", "Cooled: 15 to 40 millikelvin."],
        "source": "The datasheet. It is important to know at which F-number, background temperature and frame rate "
                  "it was measured.",
        "mistakes": ["Comparing NETD values measured at different F-numbers.", "Entering kelvin instead of "
                     "millikelvin."],
    },
    "detector.tint_ms": {
        "title": "Integration time",
        "impact_note": "It matters in light starved systems.",
        "what": "How long the detector collects photons in each frame.",
        "why": "More time means more signal and less noise, until the well fills up. It matters for SWIR at night, "
               "with an elasticity of up to 0.32; in a cooled camera by day the well is the limit.",
        "typical": ["Cooled MWIR or LWIR: 0.1 to 10 milliseconds.", "SWIR at night: 10 to 33 milliseconds.",
                    "Day: 0.01 to 5 milliseconds."],
        "source": "The camera settings in the scenario.",
        "mistakes": ["An integration time longer than the frame time, which is one over the frame rate."],
    },
    "detector.noise_floor_e": {
        "title": "Read noise",
        "impact_note": "It matters at night.",
        "what": "A fixed electronic noise that does not depend on the signal, in electrons rms.",
        "why": "In night systems, such as SWIR, this is a major lever: going from 30 to 300 electrons shortened the "
               "range by 57 percent. By day it hardly matters.",
        "typical": ["Modern CMOS: 1 to 5 electrons.", "InGaAs: 20 to 100 electrons.", "Cooled infrared: 50 to 500 "
                    "electrons."],
        "source": "The detector datasheet, as the read noise.",
        "mistakes": [],
    },
    "basic.frame_rate": {
        "title": "Frame rate",
        "impact_note": "Secondary.",
        "what": "The number of frames per second.",
        "why": "It sets the maximum integration time and how many frames the eye integrates. The effect is small in "
               "the usual range.",
        "typical": ["25, 30, 50 or 60 hertz."],
        "source": "The datasheet.",
        "mistakes": [],
    },
    "display.observation": {
        "title": "How the image is viewed",
        "impact_note": "It acts through the magnification.",
        "what": "Direct viewing of a monitor, or viewing through an eyepiece.",
        "why": "It sets the angular magnification the eye sees. A wrongly defined display is a common source of "
               "error.",
        "typical": ["A monitor at a workstation: Direct.", "A sight or binoculars: Eyepiece."],
        "source": "The system configuration.",
        "mistakes": [],
    },
    "display.distance_cm": {
        "title": "Viewing distance from the monitor",
        "impact_note": "A display lever.",
        "what": "The distance from the observer's eye to the monitor.",
        "why": "It sets the angular magnification. A closer monitor makes details larger to the eye; a two times "
               "zoom gave up to 13.5 percent more range.",
        "typical": ["A desktop monitor: 50 to 70 centimeters.", "A tablet or a handheld display: 30 to 40 "
                    "centimeters."],
        "source": "The workstation configuration.",
        "mistakes": [],
    },
    "display.snr_th": {
        "title": "Observer SNR threshold",
        "impact_note": "A calibration constant. Do not change it without a reason.",
        "what": "The signal to noise ratio the observer needs to make out a pattern.",
        "why": "It is a calibration constant of the observer model. A high value means a cautious observer and a "
               "shorter range, with an elasticity of down to minus 0.37 in SWIR.",
        "typical": ["The default: 2.5. The accepted range is 2.5 to 3."],
        "source": "Keep the default, unless you have an observer calibration.",
        "mistakes": ["Lowering the threshold just to get a range."],
    },
    "stab.jitter_preset": {
        "title": "Line of sight jitter preset",
        "impact_note": "It matters in a narrow field of view.",
        "what": "It fills in a typical random jitter: 70 microradians rms, the practice in NV-IPM.",
        "why": "Without jitter, systems with a narrow field of view, an IFOV under 210 microradians, get a "
               "prediction that is too optimistic.",
        "typical": ["No measurement of the stabilizer: 70 microradians.", "There is a measurement: enter it."],
        "source": "A stabilization measurement, or the gimbal datasheet.",
        "mistakes": [],
    },
    "stab.rand_h_mrad": {
        "title": "Random jitter, rms",
        "impact_note": "Relative to the IFOV, not as an absolute value.",
        "what": "The magnitude of the random jitter during the integration time, in milliradians rms.",
        "why": "What matters is the ratio to the pixel size, the IFOV. A jitter of 0.6 IFOV shortened "
               "identification by 18.5 percent; 50 microradians shortened it by 47 percent.",
        "typical": ["A well stabilized gimbal: 0.005 to 0.02 milliradians.", "A tripod or a vehicle: 0.05 to 0.2 "
                    "milliradians."],
        "source": "A stabilization measurement.",
        "mistakes": ["Entering microradians in a milliradian field: 70 instead of 0.07."],
    },
    "target.preset": {
        "title": "Standard target model",
        "impact_note": "It sets the dimensions and the criteria.",
        "what": "A ready target with dimensions, contrast and criteria. STANAG 4347: a 2.3 by 2.3 meter vehicle, "
                "with a delta T of 2 kelvin.",
        "why": "A consistent starting point for comparing systems.",
        "typical": ["A vehicle: STANAG 4347.", "A person: Persons, 0.6 by 1.7 meters.", "An object in the hand: "
                    "Handheld objects."],
        "source": "The system requirements, or the scenario.",
        "mistakes": [],
    },
    "target.W_m": {
        "title": "Target width",
        "impact_note": "The second most important lever.",
        "what": "The width of the target in meters, as seen from the viewing direction.",
        "why": "Pure geometry: a target twice as large gives almost twice the range in sampling limited systems. "
               "The elasticity is 0.2 to 0.5 for each dimension.",
        "typical": ["A vehicle: 2.3 meters.", "A person: 0.5 to 0.6 meters.", "A truck: 2.5 meters."],
        "source": "The target definition in the requirements.",
        "mistakes": ["Entering centimeters.", "Leaving it at zero."],
    },
    "target.H_m": {
        "title": "Target height",
        "impact_note": "The second most important lever.",
        "what": "The height of the target in meters.",
        "why": "Together with the width it sets the critical dimension, the square root of the area. It has the "
               "same high impact as the width.",
        "typical": ["A vehicle: 2.3 meters.", "A standing person: 1.7 to 1.8 meters."],
        "source": "The target definition.",
        "mistakes": [],
    },
    "target.D_m": {
        "title": "Target depth, its length",
        "impact_note": "It depends on the viewing angle.",
        "what": "The length of the target. It is seen only from the side, at an oblique angle, or from above.",
        "why": "It changes the visible area according to the viewing angle.",
        "typical": ["A vehicle: 4 to 7 meters.", "Zero means it is not used, a front view."],
        "source": "The target definition.",
        "mistakes": [],
    },
    "target.aspect": {
        "title": "Viewing angle of the target",
        "impact_note": "It acts through the visible area.",
        "what": "Which side of the target is seen: the front, the side or an oblique view.",
        "why": "It selects which dimensions make up the visible area. From the side a vehicle looks larger than "
               "from the front.",
        "typical": ["The worst case: Front."],
        "source": "The scenario.",
        "mistakes": [],
    },
    "target.dT_K": {
        "title": "Thermal contrast, delta T",
        "impact_note": "High uncertainty in the field.",
        "what": "The apparent temperature difference between the target and the background, in kelvin.",
        "why": "In the model the elasticity is fairly low, 0.04 to 0.2, but the uncertainty in the field is huge, a "
               "factor of 2 to 5. At dawn and dusk delta T collapses to zero. Halving delta T from 2 to 1 kelvin "
               "shortens MWIR detection by about 13 percent.",
        "typical": ["The STANAG standard: 2 kelvin.", "A vehicle with a running engine: 3 to 10 kelvin.",
                    "Thermal crossover: 0 to 0.5 kelvin."],
        "source": "A field measurement, or the system requirement. If it is not known, use 2 kelvin, and check 1 "
                  "kelvin as well.",
        "mistakes": ["Entering the target temperature instead of the difference."],
    },
    "target.T_bg_K": {
        "title": "Background temperature",
        "impact_note": "Very important in narrow band MWIR.",
        "what": "The temperature of the scene behind the target, in kelvin.",
        "why": "It sets the background radiance and the noise. In a narrow band MWIR detector, such as XBn, it "
               "matters a lot, with an elasticity of about 1.15: at 243 kelvin, detection dropped by 26 percent.",
        "typical": ["Average: 288 kelvin, which is 15 degrees Celsius.", "Desert summer: 305 to 320 kelvin.",
                    "Winter: 270 to 280 kelvin."],
        "source": "The scenario conditions.",
        "mistakes": ["Entering Celsius: 15 instead of 288."],
    },
    "target.t_refl": {
        "title": "Target reflectance",
        "impact_note": "It creates the contrast in a reflective sensor.",
        "what": "The fraction of the light the target reflects in the waveband, from 0 to 1.",
        "why": "In a reflective sensor, the contrast comes from the difference between the target and background "
               "reflectances. Equal reflectances mean no contrast, and no range.",
        "typical": ["A military vehicle: 0.1 to 0.3.", "Vegetation in NIR: 0.4 to 0.6.", "Asphalt: 0.05 to 0.1."],
        "source": "A materials library, or a measurement.",
        "mistakes": ["Entering a percentage."],
    },
    "target.b_refl": {
        "title": "Background reflectance",
        "impact_note": "It creates the contrast in a reflective sensor.",
        "what": "The fraction of the light the background reflects in the waveband, from 0 to 1.",
        "why": "The contrast is the difference between it and the target reflectance.",
        "typical": ["Dry soil: 0.2 to 0.35.", "Vegetation, in the visible band: 0.05 to 0.15."],
        "source": "A materials library, or a measurement.",
        "mistakes": [],
    },
    "target.t_refl_preset": {
        "title": "Target material, spectral reflectance",
        "impact_note": "It creates the contrast in a reflective sensor.",
        "what": "A material whose reflectance curve over wavelength is used for the target: grass, forest, asphalt, "
                "concrete, sand and more.",
        "why": "In a reflective sensor the contrast is the difference between the target and background "
               "reflectances in the camera waveband. The same two materials can look very different in SWIR and "
               "almost the same in the visible band.",
        "typical": ["A painted target or a vehicle: choose a close material, or switch to Effective and enter a "
                    "value."],
        "source": "The materials library of the application, or a spectral measurement.",
        "mistakes": ["Choosing the same material for the target and the background. The contrast will be zero."],
    },
    "target.b_refl_preset": {
        "title": "Background material, spectral reflectance",
        "impact_note": "It creates the contrast in a reflective sensor.",
        "what": "A material whose reflectance curve is used for the background behind the target.",
        "why": "The contrast is the difference between it and the target material.",
        "typical": ["Open terrain: dry or green grassland.", "Urban: asphalt or concrete.", "Desert: dark sand."],
        "source": "The scenario.",
        "mistakes": [],
    },
    "target.task_preset": {
        "title": "Version of the task criteria",
        "impact_note": "The strongest lever.",
        "what": "How many line pairs are needed on the target to detect, recognize or identify it. The default is "
                "1, 3 and 6, as in TRM4 and STANAG.",
        "why": "This is the strongest lever in every system. Going from 1, 3, 6 to 1, 4, 8 shortens recognition by "
               "18 percent and identification by 22 percent, more than most hardware upgrades.",
        "typical": ["Comparison with TRM4 results: 1, 3, 6.", "A requirement by the Johnson criteria: 1, 4, 6.4."],
        "source": "The customer requirements, or the standard. Always state in the report which set you used.",
        "mistakes": ["Comparing the ranges of two systems calculated with different sets."],
    },
    "target.tasks.N.lp": {
        "title": "Line pairs for the task",
        "impact_note": "The strongest lever.",
        "what": "The number of line pairs, or cycles, on the critical dimension that the task needs at a 50 percent "
                "probability.",
        "why": "More line pairs mean a harder task and a shorter range. In a sampling limited system the range is "
               "inversely proportional to this value, with an elasticity of down to minus 0.99.",
        "typical": ["Detection: 1.", "Recognition: 3 to 4.", "Identification: 6 to 8."],
        "source": "The task criteria.",
        "mistakes": [],
    },
    "irradiance.preset": {
        "title": "Natural illumination source",
        "impact_note": "It sets the signal level.",
        "what": "The sun, the moon or starlight: the spectrum and the intensity of the illumination.",
        "why": "In a reflective sensor the illumination sets how much signal there is. At night, under the moon or "
               "the stars, the system becomes light starved, and then the diameter, the integration time and the "
               "read noise decide.",
        "typical": ["Day: direct sunlight.", "An overcast day: Overcast.", "Night: full or quarter moon, or "
                    "starlight."],
        "source": "The scenario.",
        "mistakes": [],
    },
    "atmosphere.preset": {
        "title": "Quick atmosphere setting",
        "impact_note": "It dominates the detection range.",
        "what": "A typical attenuation for the waveband: clear, average or adverse. Compare fills in all three, to "
                "compare them.",
        "why": "The atmosphere dominates detection and hardly touches identification. Going from a sigma of 0.2 to "
               "0.35 shortens detection by 22 to 40 percent.",
        "typical": ["A report for a requirement: Compare, which shows all three conditions."],
        "source": "These are engineering assumptions. Weather data or MODTRAN are better.",
        "mistakes": [],
    },
    "atmosphere.atm.N.sigma": {
        "title": "Extinction coefficient, sigma",
        "impact_note": "It dominates detection.",
        "what": "The transmission is tau zero times the exponent of minus sigma times the range. A high value means "
                "bad weather and a short range.",
        "why": "The elasticity of MWIR detection is minus 0.6 in good weather, and down to minus 0.82 in bad "
               "weather. For identification the effect is much smaller.",
        "typical": ["MWIR: clear 0.15, average 0.3, adverse 0.8 per kilometer.", "Visible and NIR: 0.17, 0.39 and "
                    "1.3 per kilometer.", "SWIR: 0.1, 0.25 and 0.9 per kilometer."],
        "source": "MODTRAN, weather data, or the preset.",
        "mistakes": ["Entering per meter instead of per kilometer."],
    },
    "atmosphere.atm.N.V_km": {
        "title": "Meteorological visual range",
        "impact_note": "It dominates detection.",
        "what": "The visual range, converted to an extinction coefficient.",
        "why": "In the visible band the elasticity of detection is 0.41 in good weather, and up to 0.78 in bad "
               "weather.",
        "typical": ["Clear: 23 to 40 kilometers.", "Haze: 5 to 10 kilometers.", "Fog: under 1 kilometer."],
        "source": "A meteorological station.",
        "mistakes": [],
    },
    "turbulence.on": {
        "title": "Turbulence",
        "impact_note": "It matters in the visible and SWIR bands, by day, on ground paths.",
        "what": "It includes the blur caused by fluctuations of the refractive index of the air.",
        "why": "It matters mostly in the visible band, on a long ground path, on a hot day: a factor of ten in C n "
               "squared is about plus or minus 35 percent of range. In thermal bands the effect is much smaller.",
        "typical": ["A horizontal path over 2 kilometers by day: turn it on."],
        "source": "The scenario.",
        "mistakes": [],
    },
    "turbulence.cn2_preset": {
        "title": "C n squared scenario",
        "impact_note": "It matters in the visible and SWIR bands.",
        "what": "A typical C n squared by climate, day or night, season and percentile, from TRM4 table C.2.",
        "why": "At a C n squared of ten to the minus twelve, hot asphalt at noon, the visible band range dropped by "
               "66 to 69 percent.",
        "typical": ["Israel, the Negev: Arid.", "The north and the center: Moderate."],
        "source": "Table C.2, or a measurement, for example r zero from video.",
        "mistakes": [],
    },
    "turbulence.cn2": {
        "title": "Turbulence strength, C n squared",
        "impact_note": "It matters in the visible and SWIR bands.",
        "what": "The refractive index structure constant, in meters to the minus two thirds.",
        "why": "Ten to the minus fifteen is weak, ten to the minus fourteen moderate, ten to the minus thirteen "
               "strong, and ten to the minus twelve extreme.",
        "typical": ["Night: ten to the minus sixteen to ten to the minus fifteen.", "An average day: ten to the "
                    "minus fourteen.", "Noon over the desert: ten to the minus thirteen to ten to the minus twelve."],
        "source": "A measurement with a scintillometer, or a preset.",
        "mistakes": ["Entering ten to the minus fourteen as 14, or as ten to the fourteen."],
    },
}

# (lesson id, Hebrew step title) -> (English title, [English narration paragraphs])
STEPS = {
    ("first", "ברוכים הבאים"): ("Welcome", [
        "Hello, and welcome. I will take you through a complete range calculation, step by step. At each step I will highlight the field, explain "
        "what it means, and check that the value you entered makes sense.",
        "Three rules for smart input. Start from a template close to your system, and replace only what you know. "
        "Do the influential parameters first: the task, the target, the optics and the atmosphere. The noise "
        "parameters come later. And any value whose source tag is preset or assumed is better replaced with real "
        "data of your system.",
        "How to work with the guide: the relevant field is highlighted in the form. You enter a value, and the "
        "guide checks it right away. Next moves to the next step, and you can close the guide and come back at any "
        "time."]),
    ("first", "בחרו תבנית"): ("Choose a template", [
        "The template fills in all the hundreds of parameters with consistent values. Choose the one closest to your "
        "system through File, New from template, or with the New button of the toolbar.",
        "Thermal LWIR uncooled is an uncooled thermal camera. Thermal MWIR or LWIR cooled is a cooled thermal "
        "camera. Visible CMOS is a day camera, and Visible SWIR InGaAs is a night camera.",
        "Do you have a saved camera profile? Choose it at the top of the Quick setup page."]),
    ("first", "המטרה"): ("The target", [
        "Choose a standard target. It fills in the dimensions, the contrast and the criteria at once."]),
    ("first", "קריטריון הזיהוי"): ("The identification criterion", [
        "The three tasks, detection, recognition and identification, appear at the bottom of the page. This is the "
        "identification field, the hardest task."]),
    ("first", "מחשבים"): ("Calculating", [
        "Click Calculate in the toolbar, or press F5, or use the Calculate now button here. The calculation takes a "
        "few seconds.",
        "If a calculation error message appears, it tells you which value is invalid. Fix it and calculate again."]),
    ("first", "קוראים את התוצאה"): ("Reading the result", [
        "The Summary page shows the detection, recognition and identification ranges, in kilometers.",
        "Detection means there is something there. Recognition is the class, a vehicle or a person. Identification "
        "is which vehicle. Each range is at a 50 percent probability, with the criteria you chose. The range curve "
        "shows how the performance falls with range."]),
    ("first", "לפני שמשתמשים במספר"): ("Before you use the number", [
        "Go over the Messages page: it lists all the warnings and the assumptions the calculation relies on.",
        "This is important: a number that looks good is not necessarily right. A range without its assumptions is "
        "not worth much.",
        "You have finished the first lesson. In the next lesson we will enter a real system, at the engineering "
        "level."]),
    ("engineering", "סדר העבודה"): ("The order of work", [
        "In Engineering mode all the pages are shown. You do not need to fill in everything: fill them in the order "
        "of their impact on the range.",
        "What really sets the range: first the task criterion, then the target dimensions, the focal length and the "
        "IFOV, the diameter, and the atmosphere. Then turbulence, jitter, and the display and observer. The NETD and "
        "the noise come last.",
        "In every system, about 70 of the roughly 100 parameters hardly matter. Do not spend time on their "
        "accuracy."]),
    ("engineering", "Fλ/d - מי מגביל?"): ("F lambda over d: what is the limit?", [
        "The ratio F lambda over d, the F-number times the wavelength, divided by the pitch, tells you what limits "
        "the system.",
        "Below one, the detector is the limit: the system is sampling limited, and a longer focal length or a "
        "smaller pixel helps a lot. Above 1.5, the optics are the limit, through diffraction: a larger diameter "
        "helps, and a smaller pixel hardly does.",
        "The value is shown in the panel of calculated values at the bottom of the Optics page."]),
    ("engineering", "פסיעת הפיקסלים"): ("Pixel pitch", [
        "A tip: Run, Detector lookup, or Control D, fills in the detector data from the catalog."]),
    ("engineering", "מקדם ההנחתה"): ("Extinction coefficient", [
        "Atmosphere one is entered here. You can turn on up to three atmospheres, to compare them."]),
    ("engineering", "תג המקור של כל ערך"): ("The source tag of each value", [
        "Next to each field there is a small tag: preset, datasheet, measured, assumed and more. Clicking it "
        "changes it.",
        "The reports show, for each range, which data it relies on. A value that is still a preset is a general "
        "guess, so update at least the influential parameters.",
        "To sum up: you have entered everything that really sets the range. Calculate with F5, and move on to "
        "lesson three."]),
    ("results", "המסך Summary"): ("The Summary screen", [
        "Summary shows the DRI ranges for each atmosphere, the confidence level and the main reason for each "
        "range.",
        "If you have not calculated yet, click Calculate now."]),
    ("results", "System data"): ("System data", [
        "All the calculated values: the IFOV, the field of view, F lambda over d, the effective NETD, the well fill "
        "and more. This is where you check that the system you entered is really the system you meant.",
        "Do the IFOV and the field of view match the datasheet? Is the well fill reasonable, not zero and not 100 "
        "percent?"]),
    ("results", "מה מגביל את הטווח"): ("What limits the range", [
        "Run, Limiting factors, shows for each task what limits it: the atmosphere, diffraction, sampling, noise or "
        "jitter.",
        "Why this matters: upgrading a factor that is not the limit will not change the range. Find the bottleneck "
        "first."]),
    ("results", "יועץ השיפור"): ("The improvement advisor", [
        "Run, Improve performance, ranks the possible changes by their benefit to the range, with a card for each "
        "action.",
        "The advisor only advises; it does not change the project. Measure first marks parameters worth measuring "
        "before you invest in hardware."]),
    ("results", "סריקת פרמטר ואי-ודאות"): ("Parameter sweep and uncertainty", [
        "Parameter sweep shows how one parameter changes the range, as a curve and a table.",
        "Uncertainty study gives the range with its uncertainty, by RSS or Monte Carlo. Enter plus or minus values "
        "for the uncertain parameters: delta T, sigma and the task criterion.",
        "Scenario comparison shows several scenarios side by side."]),
    ("results", "דוח ושמירה"): ("Report and saving", [
        "File, Export Hebrew DRI report, gives a full report in Hebrew, as a PDF. File, Export report, gives a text "
        "report with all the assumptions. And File, Save, saves the project with its source tags.",
        "You are done! You can open the guide again at any time from Help, Interactive guide, or keep it open: "
        "clicking a field shows its explanation card."]),
    ("tour", "איך עובד הסיור"): ("How the tour works", [
        "We will go over every page of the form in Engineering mode, group by group. Each step shows the fields of "
        "the group: your value, a check of it, and how much it affects the range.",
        "Clicking a field in the list opens its full card, with a live calculation of its effect on the detection, "
        "recognition and identification ranges. A field marked with a warning sign needs a check, and an "
        "information sign marks a field that does not affect the range.",
        "Only the fields your project uses are shown. A tip: you do not need to change every field. A field with "
        "one star, or no star, can stay at its default if there is no better data."]),
    ("tour", "בדיקת כל הערכים"): ("Checking all the values", [
        "You have finished the tour. Here are all the notes about your values, sorted by their impact on the range. "
        "Clicking a row opens the field."]),
}
