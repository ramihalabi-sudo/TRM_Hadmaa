"""System considerations of the interactive guide beyond the TRM4 range: size, weight and power (SWaP) and the image
defects of the optics (geometric distortion, spherical aberration, coma, astigmatism / field curvature, chromatic
aberration, thermal defocus, edge illumination) that the field values imply.

TRM4 computes the ranges on the optical axis with one MTF for the whole field, so none of this enters the ranges -
except through the aberration model (optics.aberration q / blur) or an imported MTF.  The numbers here are first-order
engineering estimates (rules of thumb) for a first sizing, marked as such in the guide; a lens design (Zemax) and
datasheets replace them.  Sources and derivations: research_notes/system_considerations_he.md.

  estimates(p)    live numbers for the project (geometry, lens size / mass, focus, aberration indicators ...)
  blocks(path, p) the "system considerations" section of a field card
  notes(p)        design notes of the review (not range warnings)
"""
import math

from . import presets as P

# thermo-optic constant gamma = (dn/dT) / (n - 1) - CTE [1/K] and density [g/cm3] of a typical lens material per band
# Ge: dn/dT 396e-6, n 4.0, CTE 5.7e-6 -> 126e-6 (Umicore); chalcogenide (GASIR) ~ 23.5e-6; Si (MWIR): dn/dT ~160e-6,
# n 3.43 -> ~63e-6; optical glass (BK7: dn/dT ~3e-6, n 1.517, CTE 7.1e-6) ~ -1.3e-6 - the housing dominates.
# The focus moves by f (gamma + CTE_housing) dT for one thin element in a housing of length ~ f.
MATERIAL = {"LWIR": ("גרמניום (Ge)", 126e-6, 5.33), "MWIR": ("סיליקון / גרמניום (Si / Ge)", 63e-6, 2.33),
            "SWIR": ("זכוכית אופטית", -1.0e-6, 3.0), "VIS/NIR": ("זכוכית אופטית", -1.3e-6, 2.6)}
ALPHA_AL = 23e-6                      # aluminium housing CTE [1/K]
GE_USD_KG = 4100.0                    # germanium metal, 2025 average (USGS Mineral Commodity Summaries 2026)
GE_WASTE = (1.5, 3.0)                 # blank mass / finished element mass (generating, grinding, rejects)
COOLER_H = (8000, 27000)              # Stirling cryocooler MTTF range [h] (vendor and Teledyne FLIR FL-100 data)
DELTA_T = 40.0                        # operating temperature excursion from the focus temperature [K]
REF_F, REF_THETA = 2.0, math.radians(2.5)   # reference "easy" lens for the aberration indicators


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def estimates(p):
    """Live first-order numbers of the project, or None when the optics / detector inputs are incomplete."""
    o, d, b = p.get("optics", {}), p.get("detector", {}), p.get("basic", {})
    f = _f(o.get("f_mm"))
    pitch = _f(d.get("pitch_h_um"))
    nh, nv = int(_f(d.get("n_h"))), int(_f(d.get("n_v")))
    if f <= 0 or pitch <= 0 or nh <= 0 or nv <= 0:
        return None
    if o.get("aperture") == "general" or _f(o.get("D_mm")) <= 0:
        F = _f(o.get("F_general"), 2.0) or 2.0
        D = f / F
    else:
        D = _f(o.get("D_mm"))
        F = f / D
    try:
        win = P.qe_window(p) or (8.0, 12.0)
    except Exception:
        win = (8.0, 12.0)
    lam = 0.5 * (win[0] + win[1])
    band = P.band_of(*win)
    mat, gamma, rho = MATERIAL.get(band, MATERIAL["LWIR"])
    diag_mm = math.hypot(nh, nv) * pitch / 1000.0
    theta = math.atan(diag_mm / 2.0 / f)                      # half diagonal field angle
    hfov = math.degrees(2 * math.atan(nh * pitch / 2000.0 / f))
    ifov_urad = pitch / f * 1000.0
    cooled = p.get("category") != "Thermal" and band in ("MWIR", "LWIR") or p.get("imager_type") == "cooled"
    rear_stop = cooled and band in ("MWIR", "LWIR")           # cold stop at the detector: 100 % cold-stop efficiency
    # track length: refractive prime ~ f, telephoto, then folded / catadioptric
    if f <= 150:
        track = (1.0 * f, 1.3 * f)
    elif f <= 500:
        track = (0.6 * f, 0.9 * f)
    else:
        track = (0.3 * f, 0.5 * f)
    front = D * 1.1 if not rear_stop else D + 2 * track[0] * math.tan(theta)
    n_el = (2 if F >= 1.5 else 3) + (1 if math.degrees(theta) > 15 else 0) + (3 if band in ("VIS/NIR", "SWIR") else 0)
    t = max(0.08 * front, 2.0)                                # mm, element thickness
    glass_g = n_el * rho * math.pi * (front / 20.0) ** 2 * (t / 10.0) * 0.7
    lens_g = (glass_g * 1.6, glass_g * 2.5)                   # with cell / housing
    dof = 2 * lam * F * F                                     # +- um, quarter-wave defocus
    defocus = f * 1000.0 * (gamma + ALPHA_AL) * DELTA_T       # um over +- DELTA_T, simple element in aluminium
    th = theta / REF_THETA
    q = lam * F / pitch
    rN = 0.5 / ifov_urad * 1000.0                             # cy/mrad
    return {
        "f": f, "D": D, "F": F, "lam": lam, "band": band, "material": mat, "gamma": gamma, "diag_mm": diag_mm,
        "glass_g": glass_g, "theta_deg": math.degrees(theta), "hfov_deg": hfov, "ifov_urad": ifov_urad, "cooled": cooled,
        "rear_stop": rear_stop, "track": track, "front": front, "n_el": n_el, "lens_g": lens_g, "dof_um": dof,
        "defocus_um": defocus, "spherical": (REF_F / F) ** 3, "coma": th * (REF_F / F) ** 2,
        "astig": th * th * (REF_F / F), "distortion": _distortion(math.degrees(theta)),
        "rel_illum": math.cos(theta) ** 4, "airy_um": 2.44 * lam * F, "Q": q, "rN": rN,
        "edge_px": math.hypot(nh, nv) / 2.0, "chrom": (win[1] - win[0]) / lam,
        "jitter_need_urad": 0.3 * ifov_urad,
    }


def _distortion(theta_deg):
    """Typical barrel distortion at the field corner of a lens with this half field (rule of thumb): (lo, hi) %."""
    for lim, rng in ((5, (0.1, 0.5)), (15, (0.5, 2.0)), (30, (2.0, 5.0)), (45, (5.0, 10.0))):
        if theta_deg <= lim:
            return rng
    return (10.0, 30.0)


def _level(x):
    return "נמוך" if x <= 1.5 else ("בינוני" if x <= 6 else "גבוה")


def _g(x):
    return ("%.0f g" % x) if x < 1000 else ("%.1f kg" % (x / 1000.0))


# ---------------------------------------------------------------------------------------------
# live lines (keys per field)
# ---------------------------------------------------------------------------------------------
def _lines(e, keys, p):
    L = []
    for k in keys:
        if k == "size":
            L.append("אורך העדשה (track) בקירוב %.0f-%.0f mm%s; עדשה קדמית ~%.0f mm%s." % (
                e["track"][0], e["track"][1], " (טלפוטו / מקופל)" if e["f"] > 150 else "", e["front"],
                " - עם cold stop בגלאי האישון אחורי והעדשה הקדמית גדלה עם השדה" if e["rear_stop"] else ""))
        elif k == "mass":
            L.append("משקל העדשה בקירוב %s-%s (%d אלמנטים מ%s, כולל בית)." % (
                _g(e["lens_g"][0]), _g(e["lens_g"][1]), e["n_el"], e["material"]))
        elif k == "focus":
            r = e["defocus_um"] / e["dof_um"]
            L.append("עומק מוקד ±%.0f µm (±2λF²). שינוי טמפרטורה של ±%.0f K מזיז את המוקד ב-~%.0f µm (%s, בית "
                     "אלומיניום) - %s." % (e["dof_um"], DELTA_T, e["defocus_um"], e["material"],
                                         "פי %.0f מעומק המוקד: נדרשת אתרמליזציה (אופטית / מכנית) או מיקוד מנועי" % r
                                         if r > 1 else "בתוך עומק המוקד"))
        elif k == "aberr":
            L.append("סטיות (מדד קושי ביחס לעדשה F/2 בשדה 2.5°): כדורית %s (∝1/F³), קומה %s (∝θ/F²), "
                     "אסטיגמטיזם ועקמומיות שדה %s (∝θ²/F)." % (_level(e["spherical"]), _level(e["coma"]),
                                                             _level(e["astig"])))
        elif k == "dist":
            lo, hi = e["distortion"]
            L.append("חצי שדה אלכסוני %.1f°: עיוות גאומטרי טיפוסי בפינה %s%%-%s%% - הזזה של %.0f-%.0f פיקסלים "
                     "בפינה. עיוות לא מטשטש, אבל משנה מידות ומיקומים בשולי התמונה (מדידה, רישום, מיזוג, מעקב)." % (
                         e["theta_deg"], lo, hi, e["edge_px"] * lo / 100, e["edge_px"] * hi / 100))
        elif k == "illum":
            L.append("הארה בפינת השדה ~%.0f%% מהמרכז (cos⁴θ, בלי ויגנטינג): פחות אות ויותר רעש יחסי בשוליים." %
                     (100 * e["rel_illum"]))
        elif k == "airy":
            L.append("כתם Airy בקוטר %.1f µm מול פיקסל %s µm (Q = Fλ/d = %.2f): %s." % (
                e["airy_um"], _n(p["detector"]["pitch_h_um"]), e["Q"],
                "הגלאי מגביל - פיקסל קטן יותר או מוקד ארוך יותר יעזרו" if e["Q"] < 1 else
                ("האופטיקה מגבילה - פיקסל קטן יותר כמעט לא יוסיף פרטים" if e["Q"] > 1.5 else "מאוזן")))
        elif k == "pitch_scale":
            L.append("לאותו IFOV, המוקד והקוטר יחסיים לפסיעה: פסיעה קטנה פי 0.7 (17→12 µm) מקטינה את העדשה פי "
                     "0.7 בכל ממד ואת משקלה לבערך שליש (∝ פסיעה³).")
        elif k == "chrom":
            L.append("רוחב פס יחסי Δλ/λ = %.2f: %s" % (e["chrom"], "ב-LWIR גרמניום כמעט לא מפזר - עדשה פשוטה "
                     "אפשרית." if e["band"] == "LWIR" else "צריך תיקון כרומטי (שילוב חומרים / אכרומט) - אחרת צבעים "
                     "מתפצלים בשוליים (lateral color) והמוקד תלוי באורך הגל."))
        elif k == "core":
            L.append("גלאי מקורר: מכלול Dewar-cooler של כ-200-600 g, הספק של וואטים בודדים ועד עשרות בקירור "
                     "הראשוני, זמן קירור של דקות וחיי מקרר מוגבלים. לא-מקורר: ליבה של 25-100 g ופחות מ-1-2 W." if
                     e["cooled"] else "גלאי לא-מקורר / CMOS: ליבה קלה (עשרות גרמים) והספק נמוך; אין מקרר.")
        elif k == "gimbal":
            need = e["jitter_need_urad"]
            cls = ("חצובה / יד יציבה מספיקה" if need > 100 else
                   ("ייצוב רכב / גימבל בינוני" if need > 20 else "גימבל מיוצב איכותי - כבד ויקר"))
            L.append("כדי שהריצוד לא יגביל (< 0.3 IFOV) צריך ריצוד שיורי של עד ~%.0f µrad: %s. שדה צר יותר מחייב "
                     "ייצוב כבד יותר." % (need, cls))
        elif k == "turb":
            r0 = _r0_cm(p, e)
            if r0:
                L.append("בטורבולנציה הנוכחית r0 ≈ %.1f cm (באורך הגל של המצלמה, %s ק\"מ): D/r0 = %.1f. %s" % (
                    r0, _n(_turb_L(p)), e["D"] / 10.0 / r0, "מעבר ל-D ≈ 3 r0 קוטר גדול יותר מוסיף משקל אבל כמעט לא "
                    "רזולוציה ביום." if e["D"] / 10.0 / r0 > 3 else "המפתח עדיין מנוצל."))
    return L


def _n(v):
    v = float(v)
    return str(int(v)) if v == int(v) else ("%.3g" % v)


def _turb_L(p):
    return _f(p.get("mode", {}).get("ref_range_km")) or 5.0


def _r0_cm(p, e):
    """Plane-wave Fried parameter at the band centre over the reference range for a constant Cn2, or None."""
    t = p.get("turbulence", {})
    if not t.get("on") or t.get("cn2_mode", "fixed") not in ("fixed", "height") or _f(t.get("cn2")) <= 0:
        return None
    k = 2 * math.pi / (e["lam"] * 1e-6)
    return 100.0 * (0.423 * k * k * _f(t["cn2"]) * _turb_L(p) * 1000.0) ** (-0.6)


# ---------------------------------------------------------------------------------------------
# static considerations per field: (size / weight / power, image)
# ---------------------------------------------------------------------------------------------
SYSTEM = {
    "optics.f_mm": (["מוקד ארוך = עדשה ארוכה וכבדה יותר; מעבר ל-150-300 mm עוברים לטלפוטו או לאופטיקה מקופלת / "
                     "קטדיופטרית כדי לקצר.", "שדה צר דורש ייצוב טוב יותר (גימבל כבד יותר)."],
                    ["מוקד קצר = שדה רחב: יותר עיוות גאומטרי, אסטיגמטיזם ועקמומיות שדה וירידת הארה בשוליים.",
                     "מוקד ארוך רגיש יותר לטמפרטורה: הזזת המוקד ∝ f."],
                    ("size", "mass", "focus", "dist", "aberr", "gimbal")),
    "optics.D_mm": (["קוטר גדול = עדשות כבדות (משקל הזכוכית ∝ D² עד D³), חלון / כיפה גדולים יותר וגימבל חזק יותר.",
                     "בגרמניום כל אלמנט בקוטר 100 mm שוקל מאות גרמים."],
                    ["F קטן (קוטר גדול לאותו מוקד) מגדיל מהר את הכדורית (∝1/F³) ואת הקומה (∝θ/F²) - צריך יותר "
                     "אלמנטים או משטחים אספריים.", "עומק המוקד קטן כמו F²: עדשה מהירה רגישה יותר לטמפרטורה ולהרכבה."],
                    ("mass", "size", "aberr", "focus", "airy", "turb")),
    "optics.F_general": ([], ["F קטן: יותר אור ופחות עקיפה, אבל כדורית וקומה חזקות יותר ועומק מוקד קטן (±2λF²)."],
                         ("aberr", "focus", "airy")),
    "optics.aperture": ([], ["עם קוטר מדויק אפשר להעריך גם את גודל העדשה והחלון; עם F בלבד הקוטר מחושב כ-f/F."],
                        ("size",)),
    "optics.D_obsc_mm": (["אופטיקה מחזירה עם הסתרה (קסגרן) קצרה וקלה בהרבה מעדשה שבירה באותו מוקד."],
                         ["ההסתרה מחלישה את ה-MTF בתדרים בינוניים ומוסיפה טבעות לתמונת נקודה."], ()),
    "optics.aberration": ([], ["TRM4 מחשב טווח על הציר. קומה, אסטיגמטיזם ועקמומיות שדה פוגעים בעיקר בשולי השדה, ולכן "
                               "מטרה בשוליים תיראה גרוע יותר מהתחזית. כדי לבדוק אותה, הזינו q או blur של שולי השדה, "
                               "או ייבאו MTF של Zemax ב-field הרלוונטי."], ("aberr", "dist")),
    "optics.q": ([], ["q מתאר את כל הסטיות יחד כטשטוש אחד. לעדשה מהירה או רחבת שדה צפו ל-q גבוה יותר בשוליים."],
                 ("aberr",)),
    "optics.blur_um": ([], ["כתם גאוסי מתאר כדורית, קומה וחוסר מיקוד יחד. מעיוות גאומטרי הוא לא מושפע - עיוות לא "
                            "מטשטש."], ("airy",)),
    "optics.mtf_source": ([], ["MTF מיובא מ-Zemax יכול לייצג גם נקודת שדה שאינה על הציר - כך נכנסות קומה ואסטיגמטיזם "
                               "לטווח."], ()),
    "optics.tau_opt": (["יותר אלמנטים (לתיקון סטיות) = יותר משטחים: כל משטח IR מצופה מאבד 1%-2%."], [], ()),
    "optics.rel_illum": ([], ["ירידת הארה בשוליים (ויגנטינג x cos⁴) נותנת אות חלש יותר בפינות ופוגעת באחידות "
                              "(NUC)."], ("illum",)),
    "optics.diff_focal": ([], ["אופטיקה אנמורפית מעוותת יחס צדדים - דורשת תיקון בתצוגה."], ()),
    "detector.pitch_h_um": (["פיקסל קטן מאפשר עדשה קטנה וקלה יותר לאותו IFOV ולאותו F."],
                            ["פיקסל קטן מקטין את טולרנס המיקוד בפיקסלים ודורש עדשה חדה יותר (Q גבוה יותר)."],
                            ("pitch_scale", "airy")),
    "detector.n_h": (["גלאי גדול יותר (יותר פיקסלים באותה פסיעה) = מעגל תמונה גדול: עדשה גדולה יותר ושדה רחב יותר."],
                     ["שדה רחב יותר מגדיל עיוות, סטיות בשוליים וירידת הארה בפינות."], ("dist", "illum")),
    "detector.n_v": ([], ["משפיע על אלכסון התמונה ולכן על העיוות והסטיות בפינות."], ("dist",)),
    "imager_type": (["מקורר: מקרר Stirling, Dewar, הספק וזמן קירור; לא-מקורר: קל, זול ומיידי."],
                    ["מקורר דורש cold stop - האישון ליד הגלאי, ולכן עדשה קדמית גדולה יותר או אופטיקת העברה "
                     "(relay)."], ("core", "size")),
    "category": ([], ["התחום קובע את חומרי העדשה: גרמניום / כלקוגניד ב-LWIR, סיליקון / גרמניום ב-MWIR, זכוכית "
                      "בנראה וב-SWIR - ואיתם את המשקל, הרגישות לטמפרטורה והתיקון הכרומטי."], ("chrom", "focus")),
    "detector.qe_preset": ([], ["חומר הגלאי קובע את התחום, ולכן את חומרי העדשה ואת התיקון הכרומטי הנדרש."],
                           ("chrom",)),
    "detector.cuton_um": ([], ["פס רחב יותר = יותר אות, אבל תיקון כרומטי קשה יותר."], ("chrom",)),
    "detector.cutoff_um": ([], ["פס רחב יותר = יותר אות, אבל תיקון כרומטי קשה יותר."], ("chrom",)),
    "detector.cs_F": (["F של המגן הקר קובע את F של העדשה: מגן F/4 עם עדשה מהירה יותר מבזבז מפתח (וגם משקל)."], [], ()),
    "detector.cs_eff": ([], ["יעילות מגן נמוכה = קרינה חמה מהבית - צל או 'נרקיס' (narcissus) בתמונה."], ()),
    "detector.T_cs_K": (["טמפרטורת קירור נמוכה יותר דורשת יותר הספק מהמקרר."], [], ("core",)),
    "basic.frame_rate": (["קצב גבוה = יותר הספק ופס תקשורת."], ["קצב נמוך = מריחה ותנועה מקוטעת במטרה נעה."], ()),
    "basic.readout": ([], ["Rolling shutter עם תנועה: עיוות גאומטרי (shear) - קווים ישרים נטויים ועצמים נעים "
                           "מעוותים."], ()),
    "basic.microscan": (["מנגנון מיקרו-סריקה (מראה / דוחף פיאזו) מוסיף משקל, הספק ונקודת כשל."],
                        ["בתנועה יוצר תמונות כפולות (artifacts) אם הסצנה זזה בין המיקומים."], ()),
    "basic.bin_h": ([], ["איחוד פיקסלים מכפיל את ה-IFOV: פחות פרטים, אבל העיוות בפיקסלים קטן בהתאם."], ()),
    "detector.tint_ms": ([], ["זמן אינטגרציה ארוך + תנועה = מריחה; עם rolling shutter גם עיוות."], ()),
    "stab.jitter_preset": (["דרישת הייצוב נגזרת מה-IFOV: גימבל מדויק יותר כבד ויקר יותר."], [], ("gimbal",)),
    "stab.rand_h_mrad": (["דרישת הייצוב נגזרת מה-IFOV: גימבל מדויק יותר כבד ויקר יותר."], [], ("gimbal",)),
    "stab.jitter_mode": (["דרישת הייצוב נגזרת מה-IFOV: גימבל מדויק יותר כבד ויקר יותר."], [], ("gimbal",)),
    "turbulence.on": (["בטורבולנציה חזקה קוטר מעל ~3 r0 לא משפר רזולוציה: משקל בלי תועלת ביום."], [], ("turb",)),
    "turbulence.cn2": (["בטורבולנציה חזקה קוטר מעל ~3 r0 לא משפר רזולוציה."], [], ("turb",)),
    "dsp.zoom": ([], ["זום אלקטרוני לא מתקן עיוות או סטיות - רק מגדיל אותם."], ()),
    "dsp.pl_compression": ([], ["דחיסה מאבדת יוצרת בלוקים ומריחת קצוות - עיוות שאינו אופטי."], ()),
    "display.observation": (["עינית מוסיפה אופטיקה, משקל ונקודת עין; מסך מוסיף הספק."], [], ()),
}


# manufacturing difficulty and cost, by field (sources: research_notes/system_considerations_he.md, section 7)
COST = {
    "optics.f_mm": ["מוקד ארוך = יותר חומר ועדשה ארוכה; בטלפוטו גם יותר אלמנטים, וכל אלמנט מוסיף חומר, ליטוש, ציפוי "
                    "ויישור.", "זום רציף יקר ומורכב בהרבה מעדשה קבועה או משני שדות: מנגנון, יישור ואטימות."],
    "optics.D_mm": ["עלות העדשה עולה מהר עם הקוטר: יותר חומר, גביש גדול יותר ויותר פסולת בעיבוד. לפי ספקים, עדשה "
                    "ב-F/1.0 עולה פי 2-3 מאותה עדשה ב-F/1.5.", "בגרמניום, גידול גביש בקוטר של 100 mm ומעלה הוא אתגר "
                    "ייצורי בפני עצמו."],
    "optics.F_general": ["F קטן = קוטר גדול ויותר אלמנטים או משטחים אספריים (חריטת יהלום): יקר יותר לייצור ולהרכבה."],
    "optics.D_obsc_mm": ["אופטיקה מחזירה (מראות): זולה וקלה יותר בקוטר גדול, אבל היישור רגיש ודורש מבנה יציב."],
    "optics.tau_opt": ["ציפוי נגד החזרות (AR) איכותי ל-LWIR יכול להגיע ל-20%-30% מעלות ייצור העדשה (לפי ספקים)."],
    "category": ["LWIR ו-MWIR נשענים על גרמניום: חומר יקר ותנודתי. הממוצע ב-2025 היה כ-$4,100 לק\"ג (USGS), פי 4 "
                 "מתחילת 2023, אחרי מגבלות הייצוא של סין.", "בכמויות של יותר מ-1,000 יחידות, עדשות כלקוגניד בכבישה "
                 "(molding) זולות יותר מגרמניום בחריטת יהלום (לפי ספקים); בכמויות קטנות - להפך.",
                 "SWIR עם InGaAs: גלאי יקר בהרבה מ-CMOS, ולעיתים כפוף למגבלות ייצוא (ITAR / EAR)."],
    "imager_type": ["מקורר: ליבה יקרה בהרבה, ומקרר Stirling עם אורך חיים של כ-8,000-27,000 שעות - צריך לתכנן "
                    "תחזוקה והחלפה, וזה חלק מעלות המחזור.", "לא-מקורר: בלי חלקים נעים, אורך חיים ארוך ועלות נמוכה. "
                    "אבל במוקד ארוך (לפי מקור בתעשייה, מעל ~350 mm) העדשה המהירה שהוא צריך עלולה לעלות יותר ממערכת "
                    "מקוררת שלמה."],
    "detector.pitch_h_um": ["פיקסל קטן = שבב קטן = יותר שבבים בפרוסה, ולכן גלאי זול יותר. אבל אם הוא מחייב עדשה "
                            "מהירה יותר (F/1), החיסכון יכול להיעלם בעלות העדשה."],
    "detector.n_h": ["פורמט גדול = שבב גדול: פחות שבבים בפרוסה ותפוקה (yield) נמוכה יותר, ולכן גלאי יקר יותר - "
                     "ועדשה גדולה יותר."],
    "detector.cuton_um": ["פס רחב מחייב תיקון כרומטי: עוד אלמנטים או חומרים מיוחדים, ולכן עלות גבוהה יותר."],
    "detector.cutoff_um": ["פס רחב מחייב תיקון כרומטי: עוד אלמנטים או חומרים מיוחדים, ולכן עלות גבוהה יותר."],
    "basic.microscan": ["מנגנון נוסף שצריך לייצר, לכייל ולתחזק."],
    "stab.jitter_preset": ["ככל שדרישת הייצוב מחמירה, הגימבל צריך חיישנים ומנועים מדויקים יותר: העלות והמשקל עולים "
                           "מהר."],
    "stab.rand_h_mrad": ["ככל שדרישת הייצוב מחמירה, הגימבל צריך חיישנים ומנועים מדויקים יותר: העלות והמשקל עולים "
                         "מהר."],
    "stab.jitter_mode": ["ככל שדרישת הייצוב מחמירה, הגימבל צריך חיישנים ומנועים מדויקים יותר: העלות והמשקל עולים "
                         "מהר."],
    "display.observation": ["עינית איכותית היא רכיב אופטי נוסף לייצור; מסך הוא בדרך כלל רכיב מדף, זול יחסית."],
}

COST_KEYS = {"optics.f_mm": ("ge", "cooler"), "optics.D_mm": ("ge",), "optics.F_general": ("ge",),
             "category": ("ge",), "imager_type": ("cooler",), "detector.pitch_h_um": ("ge",)}


def _usd(x):
    return ("$%.0f" % x) if x < 1000 else ("$%.1fk" % (x / 1000.0))


def _cost_lines(e, path):
    """Live cost and maintenance estimates of a field card."""
    L = []
    for k in COST_KEYS.get(path, ()):
        if k == "ge" and "גרמניום" in e["material"]:
            share = 1.0 if e["band"] == "LWIR" else 0.5            # MWIR: part of the elements are silicon
            kg = e["glass_g"] * share / 1000.0
            lo, hi = kg * GE_WASTE[0] * GE_USD_KG, kg * GE_WASTE[1] * GE_USD_KG
            L.append("חומר הגלם (גרמניום) לבדו: כ-%s-%s לעדשה, לפי $%s לק\"ג (ממוצע 2025) וכולל פחת עיבוד - "
                     "לפני ליטוש, ציפוי, בית והרכבה." % (_usd(lo), _usd(hi), "{:,.0f}".format(GE_USD_KG)))
        elif k == "cooler" and e["cooled"]:
            lo, hi = COOLER_H
            L.append("מקרר Stirling: כ-%s-%s שעות עד תחזוקה; בעבודה של 8 שעות ביום, כ-%.0f-%.0f שנים." % (
                "{:,}".format(lo), "{:,}".format(hi), lo / 8 / 365, hi / 8 / 365))
    return L


def blocks(path, p):
    """RtlCanvas blocks of the system-considerations section of a field card ([] when it has none)."""
    s = SYSTEM.get(path)
    cost = COST.get(path, [])
    if not s and not cost:
        return []
    swap, image, keys = s or ([], [], ())
    e = estimates(p) if (keys or COST_KEYS.get(path)) else None
    out = [("h", "שיקולי מערכת: גודל, משקל, ייצור, עלות ואיכות תמונה")]
    out += [("li", "משקל / גודל: " + t) for t in swap]
    out += [("li", "ייצור ועלות: " + t) for t in cost]
    out += [("li", "תמונה: " + t) for t in image]
    if e:
        lines = _lines(e, keys, p) + _cost_lines(e, path)
        if lines:
            out.append(("box", "plain", ["במערכת שלכם (הערכה הנדסית מסדר ראשון)"] + lines, True))
    out.append(("muted", "שיקולים אלה לא נכנסים לטווח של TRM4 (שמחושב על הציר), חוץ ממודל הסטיות (q / blur) או MTF "
                         "מיובא. הם הערכה ראשונית - תכנון אופטי, דפי נתונים והצעות מחיר מחליפים אותם."))
    return out


def notes(p):
    """Design notes of the review: [(path, title, text)].  They do not change the ranges."""
    e = estimates(p)
    if not e:
        return []
    out = []
    if e["defocus_um"] > e["dof_um"]:
        out.append(("optics.f_mm", "הזזת מוקד עם הטמפרטורה",
                    "בשינוי של ±%.0f K עדשה פשוטה זזה במוקד ~%.0f µm, פי %.0f מעומק המוקד (±%.0f µm). ודאו שהעדשה "
                    "אתרמלית (פסיבית) או עם מיקוד מנועי - אחרת התמונה תיטשטש בשטח והטווח בפועל יהיה קצר מהתחזית." % (
                        DELTA_T, e["defocus_um"], e["defocus_um"] / e["dof_um"], e["dof_um"])))
    if e["F"] < 1.0:
        out.append(("optics.D_mm", "עדשה מהירה מאוד (F/%.2f)" % e["F"],
                    "כדורית וקומה גבוהות מאוד: נדרשים משטחים אספריים / אלמנטים נוספים, ועומק המוקד ±%.0f µm בלבד. "
                    "בדקו שהעדשה קיימת בפועל ושה-q / blur מייצגים אותה." % e["dof_um"]))
    if e["theta_deg"] > 20:
        lo, hi = e["distortion"]
        out.append(("optics.f_mm", "שדה רחב - עיוות וסטיות בשוליים",
                    "חצי שדה אלכסוני %.0f°: עיוות טיפוסי %s%%-%s%% בפינה והארה של ~%.0f%%. הטווח מחושב במרכז; מטרה "
                    "בשוליים תיראה גרוע יותר." % (e["theta_deg"], lo, hi, 100 * e["rel_illum"])))
    if e["lens_g"][0] > 2000:
        out.append(("optics.D_mm", "עדשה כבדה",
                    "משקל העדשה בקירוב %s-%s. אם המשקל מוגבל - שקלו מוקד / קוטר קטנים יותר, פיקסל קטן יותר לאותו "
                    "IFOV או אופטיקה מחזירה." % (_g(e["lens_g"][0]), _g(e["lens_g"][1]))))
    if e["rear_stop"] and e["front"] > 1.4 * e["D"]:
        out.append(("optics.D_mm", "עדשה קדמית גדולה (cold stop)",
                    "עם cold stop בגלאי העדשה הקדמית ~%.0f mm לעומת מפתח של %.0f mm. אופטיקת העברה (relay) מקטינה אותה "
                    "אבל מאריכה את המערכת." % (e["front"], e["D"])))
    r0 = _r0_cm(p, e)
    if r0 and e["D"] / 10.0 / r0 > 3:
        out.append(("optics.D_mm", "מפתח גדול מהטורבולנציה",
                    "D/r0 = %.1f: ביום, הגדלת הקוטר כמעט לא תשפר רזולוציה - רק תוסיף משקל." % (e["D"] / 10.0 / r0)))
    if e["jitter_need_urad"] < 20:
        out.append(("stab.jitter_preset", "דרישת ייצוב גבוהה",
                    "IFOV של %.0f µrad: הריצוד השיורי צריך להיות פחות מ-%.0f µrad - גימבל מיוצב איכותי." % (
                        e["ifov_urad"], e["jitter_need_urad"])))
    b, s = p.get("basic", {}), p.get("stab", {})
    if b.get("readout") == "rolling" and (s.get("lin_on") or s.get("sin_on")):
        out.append(("basic.readout", "Rolling shutter בתנועה", "התמונה תתעוות (shear) בתנועה. זה לא נכנס לטווח."))
    return out
