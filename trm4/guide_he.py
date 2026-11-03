"""Interactive Hebrew guide: parameter knowledge base and lessons.

PARAMS holds, for the parameters that decide the ranges, what the value means, how strongly it moves the DRI
ranges, typical values, where to take it from, common mistakes and a plausibility check of the entered value.
The impact ratings come from the parameter-sensitivity study (reports/השפעת פרמטרים על טווחי תצפית TRM.md,
Table 2 and Table 5: elasticities over four representative systems).

LESSONS are the guided tours shown by the guide panel of the GUI (gui.GuidePanel).  A step names the page and
the parameter to highlight; its field card is taken from PARAMS.  The "tour" lesson is built from the form itself
(tour_steps): one step per group of fields of every page, so that it covers every field the project shows.
review() checks every shown field of a project at once.

The cards of all other fields of the form are in guide_kb_he.MORE.
"""
import re

from .guide_kb_he import MORE, _check_jitter_preset, _check_tint, _n, _range

IMPACT_TEXT = {3: "השפעה גבוהה על הטווח", 2: "השפעה בינונית", 1: "השפעה נמוכה", 0: "לא משפיע על הטווח"}
IMPACT_STYLE = {3: "high", 2: "mid", 1: "low", 0: "info"}


def _cat(p):
    return p.get("category", "Thermal")


def _thermal(p):
    return _cat(p) == "Thermal"


def _visible(p):
    return _cat(p) == "Visible"


def _field(p):
    return p.get("mode", {}).get("environment", "field") == "field"


def _refl_mode(p, who):
    return p.get("target", {}).get(who + "_refl_mode", "effective")


def _check_materials(p):
    t = p.get("target", {})
    if t.get("t_refl_mode") == "spectral" and t.get("b_refl_mode") == "spectral":
        if t.get("t_refl_preset") == t.get("b_refl_preset"):
            return ("warn", "המטרה והרקע מאותו חומר (%s): אין ניגוד, ולכן לא יהיה טווח." % t.get("t_refl_preset"))
        return ("ok", "מטרה: %s, רקע: %s." % (t.get("t_refl_preset"), t.get("b_refl_preset")))
    return None


def _check_f(v, p):
    if not isinstance(v, (int, float)):
        return None
    if v <= 0:
        return ("warn", "אורך מוקד חייב להיות חיובי.")
    if v < 3:
        return ("warn", "פחות מ-3 mm - ייתכן שהוזן בס\"מ במקום מ\"מ. מוקד קצר פי 10 נותן IFOV גדול פי 10, והטווחים "
                        "יוצאים קצרים פי 5-10.", round(v * 10, 3))
    if v > 3000:
        return ("warn", "יותר מ-3000 mm - חריג מאוד. ייתכן שהוזן במיקרון או שיש טעות הקלדה. מוקד ארוך מדי מנפח את "
                        "הטווח במערכת מוגבלת-דגימה.")
    D = p.get("optics", {}).get("D_mm") or 0
    if p.get("optics", {}).get("aperture") == "circular" and D > 0:
        F = v / D
        if F < 0.7 or F > 12:
            return ("warn", "היחס f/D יוצא F/%.1f - לא סביר (עדשות אמיתיות: F/0.8-F/8). קוטר שגוי משנה את העקיפה "
                            "ואת כמות האור. בדקו את הקוטר D." % F)
        return ("ok", "f = %s mm עם D = %s mm נותן F/%.2g." % (_n(v), _n(D), F))
    return ("ok", "f = %s mm." % _n(v))


def _check_D(v, p):
    if not isinstance(v, (int, float)):
        return None
    if v < 0:
        return ("warn", "הקוטר לא יכול להיות שלילי.")
    if v == 0:
        return ("ok", "0 = מפתח מלבני לפי רוחב וגובה (מתקדם).")
    f = p.get("optics", {}).get("f_mm") or 0
    if f and f / v < 0.7:
        return ("warn", "הקוטר גדול מדי ביחס למוקד (F/%.2g) - עדשה כזו לא קיימת, והיא מנפחת את האות ומקטינה את "
                        "העקיפה. ייתכן שהוזן ה-F-number או ערך שגוי." % (f / v))
    if f and f / v > 12:
        return ("warn", "הקוטר קטן מאוד ביחס למוקד (F/%.2g): עקיפה חזקה ומעט אור. ייתכן שהוזן הרדיוס או ה-F-number "
                        "במקום הקוטר." % (f / v))
    return _range(2, 600, "mm")(v, p)


def _check_netd(v, p):
    if not isinstance(v, (int, float)):
        return None
    if 0 < v < 1:
        return ("warn", "נראה שה-NETD הוזן ב-K במקום ב-mK: %s K = %s mK. NETD קטן פי 1000 מנפח את הרגישות." %
                (_n(v), _n(v * 1000)), v * 1000)
    if p.get("imager_type") == "uncooled":
        return _range(15, 150, "mK", "לא-מקורר טיפוסי: 30-80 mK")(v, p)
    return _range(5, 100, "mK", "מקורר טיפוסי: 15-40 mK")(v, p)


def _check_pitch(v, p):
    if not isinstance(v, (int, float)):
        return None
    if _thermal(p):
        return _range(5, 50, "µm", "תרמי: 8-25 µm")(v, p)
    return _range(0.8, 30, "µm", "נראה: 1.4-6 µm, SWIR: 5-20 µm")(v, p)


def _check_lp(v, p):
    if not isinstance(v, (int, float)):
        return None
    if v <= 0:
        return ("warn", "מספר זוגות הקווים חייב להיות חיובי.")
    if v > 15:
        return ("warn", "יותר מ-15 זוגות קווים - חריג. ערכים מקובלים: 0.75-8.")
    return ("ok", "%s זוגות קווים." % _n(v))


def _check_dT(v, p):
    if not isinstance(v, (int, float)):
        return None
    if v == 0:
        return ("warn", "ΔT = 0: אין ניגוד ולכן אין טווח. זה מתאים רק למעבר תרמי (שחר / דמדומים). לדרישה "
                        "מקובל ΔT = 2 K.", 2.0)
    if abs(v) > 20:
        return ("warn", "ΔT מעל 20 K - נדיר למטרה טיפוסית (מנוע חם, אש?). ניגוד גבוה מדי מנפח בעיקר את טווח הגילוי. "
                        "בדקו שזה ניגוד ולא טמפרטורה.")
    if abs(v) < 0.5:
        return ("ok", "ניגוד נמוך מאוד - תרחיש קשה. כאן NETD ועיבוד אות מתחילים להשפיע.")
    return ("ok", "ΔT = %s K, בתחום המקובל (תקן: 2 K)." % _n(v))


def _check_Tbg(v, p):
    if not isinstance(v, (int, float)):
        return None
    if v < 200 or v > 340:
        msg = ("טמפרטורת רקע של %s K (%.0f °C) חריגה. שימו לב: הערך בקלווין, לא בצלזיוס. רקע קר מאוד מוריד את "
               "קרינת הרקע ואת הרגישות, ומקצר את הטווח." % (_n(v), v - 273.15))
        if -60 <= v <= 80:
            return ("warn", msg + " %s °C = %s K." % (_n(v), _n(round(v + 273.15, 2))), round(v + 273.15, 2))
        return ("warn", msg)
    return ("ok", "%s K = %.0f °C." % (_n(v), v - 273.15))


def _check_refl(v, p):
    if not isinstance(v, (int, float)):
        return None
    if 1 < v <= 100:
        return ("warn", "החזרות היא שבר בין 0 ל-1, לא אחוזים: %s נראה כמו %s%%. ההחזרות קובעת את הניגוד, ולכן "
                        "ערך שגוי משנה את כל הטווחים." % (_n(v), _n(v)), round(v / 100.0, 4))
    if v < 0 or v > 1:
        return ("warn", "החזרות היא שבר בין 0 ל-1, לא אחוזים.")
    t = p.get("target", {})
    other = t.get("b_refl") if v == t.get("t_refl") else t.get("t_refl")
    if p.get("category") != "Thermal" and isinstance(other, (int, float)) and abs(v - other) < 0.02 and \
            t.get("t_refl_mode") == t.get("b_refl_mode") == "effective":
        return ("warn", "ההחזרות של המטרה (%s) ושל הרקע (%s) כמעט שוות: כמעט אין ניגוד, והטווחים יהיו קצרים מאוד. "
                        "בדקו את שני הערכים." % (_n(t.get("t_refl")), _n(t.get("b_refl"))))
    return ("ok", "החזרות %s." % _n(v))


def _check_sigma(v, p):
    if not isinstance(v, (int, float)):
        return None
    if v < 0:
        return ("warn", "מקדם הנחתה לא יכול להיות שלילי.")
    if 0 < v < 0.005:
        return ("warn", "σ = %s 1/km - אוויר כמעט ריק. ייתכן שהוזן ב-1/m: %s 1/m = %s 1/km. הנחתה נמוכה מדי מנפחת "
                        "את טווח הגילוי." % (_n(v), _n(v), _n(v * 1000)), round(v * 1000, 4))
    if v > 5:
        return ("warn", "σ מעל 5 1/km - ערפל כבד; הטווחים יהיו קצרים מאוד.")
    T = 2.718281828 ** (-v * 5)
    return ("ok", "σ = %s 1/km: העברה של %.0f%% ב-5 ק\"מ." % (_n(v), 100 * T))


def _check_V(v, p):
    if not isinstance(v, (int, float)):
        return None
    if v <= 0:
        return ("warn", "טווח הראות חייב להיות חיובי.")
    if v < 1:
        return ("ok", "טווח ראות מתחת ל-1 ק\"מ: ערפל. הטווחים יוגבלו מאוד.")
    return _range(0.05, 100, "km", "יום בהיר: 20-40 km")(v, p)


def _check_jitter(v, p):
    if not isinstance(v, (int, float)):
        return None
    det = p.get("detector", {})
    f = p.get("optics", {}).get("f_mm") or 0
    pitch = det.get("pitch_h_um") or 0
    if not (f and pitch):
        return None
    ifov = pitch / f                                       # mrad (um / mm)
    ratio = v / ifov if ifov else 0
    if v < 0:
        return ("warn", "ריצוד לא יכול להיות שלילי.", 0.0)
    if v >= 1 and ratio > 5:
        return ("warn", "%s mrad זה ריצוד עצום (פי %.0f מהפיקסל) - נראה שהוזן ב-µrad בשדה של mrad." % (_n(v), ratio),
                round(v / 1000.0, 4))
    if ratio > 1:
        return ("warn", "הריצוד (%s mrad) גדול מה-IFOV (%.3g mrad): התמונה נמרחת על יותר מפיקסל בכל חשיפה, והוא "
                        "יגביל את ההכרה והזיהוי מאוד." % (_n(v), ifov))
    if v == 0 and ifov < 0.21:
        return ("warn", "IFOV של %.3g mrad (שדה צר) בלי ריצוד - התחזית אופטימית: כל מערכת אמיתית רועדת. שקלו "
                        "0.07 mrad (נוהג NV-IPM), או הזינו מדידת ייצוב." % ifov, 0.07)
    return ("ok", "ריצוד / IFOV = %.2f." % ratio)


def _check_snr(v, p):
    if not isinstance(v, (int, float)):
        return None
    if v <= 0:
        return ("warn", "סף SNR חייב להיות חיובי.", 2.5)
    if v < 1.5 or v > 6:
        return ("warn", "סף SNR של %s מחוץ לתחום המקובל (2.5-3). זה קבוע כיול של הצופה: סף נמוך מנפח את הטווח, סף "
                        "גבוה מקצר אותו. השאירו 2.5 אלא אם יש כיול." % _n(v), 2.5)
    return ("ok", "הערך %s בתחום הסביר (מקובל: 2.5-3)." % _n(v))


def _check_size(v, p):
    if not isinstance(v, (int, float)):
        return None
    if v <= 0:
        return ("warn", "ממד המטרה חייב להיות חיובי (0 נותן מטרה בגודל אפס).")
    if v > 60:
        return ("warn", "יותר מ-60 מ' - חריג. ייתכן שהוזן בס\"מ. מטרה גדולה פי 100 נותנת טווח ארוך בהרבה.",
                round(v / 100.0, 3))
    return ("ok", "%s מ'." % _n(v))


def _check_cn2(v, p):
    if not isinstance(v, (int, float)):
        return None
    if v < 0:
        return ("warn", "Cn² לא יכול להיות שלילי.")
    if v >= 1:
        return ("warn", "Cn² של %s - נראה שהוזן המעריך במקום הערך: 1e-%s m^-2/3." % (_n(v), _n(v)), 10.0 ** -v)
    if v > 1e-11:
        return ("warn", "Cn² מעל 1e-11 - חריג מאוד (חום קיצוני מעל אספלט). טורבולנציה כזו מטשטשת כמעט כל פרט "
                        "בנתיב של קילומטרים.")
    lvl = "חלשה" if v < 1e-15 else ("בינונית" if v < 1e-13 else "חזקה")
    return ("ok", "טורבולנציה %s (%s m^-2/3)." % (lvl, "%.1e" % v))


# ---------------------------------------------------------------------------------------------
# knowledge base
# ---------------------------------------------------------------------------------------------
PARAMS = {
    "category": {
        "title": "קטגוריית החיישן (תחום ספקטרלי)",
        "what": "קובע איך המודל מתאר את הסצנה. Thermal: טמפרטורות בלבד (MWIR / LWIR). Visible: החזרות ומקור "
                "הארה (נראה, NIR, SWIR). General: גם החזרה וגם פליטה (למשל MWIR ביום).",
        "why": "ההחלטה הראשונה בפרויקט. היא קובעת אילו פרמטרים מוצגים ואיזו רדיומטריה מחושבת.",
        "impact": 3, "impact_note": "קובע את כל מבנה החישוב",
        "typical": ["מצלמה תרמית מקוררת או לא-מקוררת: Thermal.", "מצלמת יום, NIR או SWIR לילה: Visible.",
                    "MWIR שרואה גם השתקפות שמש: General."],
        "source": "דף הנתונים של המצלמה (תחום הגל).",
        "mistakes": ["לבחור Thermal למצלמת SWIR - SWIR היא חיישן מחזיר (Visible)."],
    },
    "imager_type": {
        "title": "סוג הגלאי התרמי",
        "what": "Cooled: גלאי פוטונים מקורר (InSb, MCT, XBn) עם זמן אינטגרציה ובאר אלקטרונים. Uncooled: "
                "מיקרובולומטר עם NETD וקבוע זמן תרמי.",
        "why": "קובע את מודל הרעש. בבולומטר הרגישות נקבעת ב-NETD; במקורר היא מחושבת מנתוני הגלאי.",
        "impact": 2, "impact_note": "בוחר את מודל הרעש",
        "typical": ["מצלמה שצריכה קירור (Stirling) ו-F/4-F/5.5: Cooled.", "מצלמה קלה, F/1-F/1.4, פסיעה 12-17 µm: Uncooled."],
        "source": "דף הנתונים: Cooled / Uncooled, VOx / a-Si = Uncooled.",
        "mistakes": [],
    },
    "mode.environment": {
        "title": "שדה או מעבדה",
        "what": "Field: ביצועים בטווח דרך האטמוספרה (עקומות טווח). Laboratory: ביצועים בכניסה למצלמה בלי "
                "אטמוספרה (MRTD / MTDP).",
        "why": "לחיזוי טווחי DRI בוחרים Field. Laboratory משמש להשוואה למדידות מעבדה.",
        "impact": 3, "impact_note": "בלי Field אין טווחים בשטח",
        "typical": ["חיזוי טווחים: Field."], "source": "מטרת הניתוח.",
        "mistakes": ["לחשב ב-Laboratory ולצפות לטווחים בק\"מ."],
    },
    "mode.stream": {
        "title": "וידאו או תמונה בודדת",
        "what": "Video: העין משלבת כמה פריימים ומנקה רעש זמני. Still: צופה בפריים בודד.",
        "why": "בווידאו הרעש האפקטיבי נמוך יותר, ולכן הטווח לרוב ארוך יותר.",
        "impact": 1, "impact_note": "משנה בעיקר במערכות מוגבלות-רעש",
        "typical": ["צפייה חיה במסך: Video.", "צילום / מודיעין תמונה: Still."], "source": "אופן השימוש.",
        "mistakes": [],
    },
    "optics.f_mm": {
        "title": "אורך מוקד (f)",
        "what": "אורך המוקד האפקטיבי של העדשה. יחד עם פסיעת הגלאי הוא קובע את ה-IFOV (הזווית שכל פיקסל רואה) "
                "ואת שדה הראייה.",
        "why": "מוקד ארוך = פיקסל רואה זווית קטנה יותר = יותר פיקסלים על המטרה = טווח ארוך יותר. ב-LWIR "
               "לא-מקורר זה המנוף החומרתי החזק ביותר (גמישות 0.75-0.87). ב-MWIR מקורר עם קוטר קבוע ההשפעה "
               "קטנה, כי שם הקוטר מגביל.",
        "impact": 3, "impact_note": "חזק במיוחד כשהמערכת מוגבלת-דגימה (Fλ/d < 1)",
        "typical": ["מצלמה תרמית ידנית: 25-75 mm.", "מערכת תצפית יבשתית: 100-300 mm.",
                    "מערכת ארוכת טווח / מוטסת: 300-1500 mm."],
        "source": "דף הנתונים של העדשה. בזום - הזינו את המוקד במצב שאותו מנתחים (בדרך כלל NFOV).",
        "mistakes": ["להזין בס\"מ במקום מ\"מ.", "לשנות מוקד בלי לעדכן את הקוטר - זה משנה גם את ה-F-number."],
        "check": _check_f,
    },
    "optics.aperture": {
        "title": "איך מגדירים את המפתח",
        "what": "Clear aperture diameter: מזינים קוטר D מדויק (נכון לעקיפה ולרדיומטריה). F-number: מזינים רק "
                "F/# ומניחים מפתח עגול ללא הסתרה.",
        "why": "הקוטר D הוא שקובע את העקיפה ואת כמות האור. כשיש קוטר בדף הנתונים - העדיפו אותו.",
        "impact": 1, "impact_note": "בחירת צורת קלט",
        "typical": ["יש D בדף הנתונים: Clear aperture diameter.", "יש רק F/#: F-number."],
        "source": "דף הנתונים של העדשה.", "mistakes": [],
    },
    "optics.D_mm": {
        "title": "קוטר המפתח (D)",
        "what": "קוטר אישון הכניסה של העדשה. F-number = f / D.",
        "why": "קובע את גבול העקיפה ואת כמות האות. ב-MWIR מקורר ובמערכות לילה (SWIR) זה המנוף החזק (גמישות עד "
               "0.93 בזיהוי). ב-LWIR לא-מקורר ההשפעה קטנה (~0.15).",
        "impact": 3, "impact_note": "חזק כשהמערכת מוגבלת-עקיפה (Fλ/d > 1.5)",
        "typical": ["לא-מקורר F/1-F/1.4: D קרוב ל-f.", "מקורר MWIR F/4-F/5.5: D = f / 4 עד f / 5.5."],
        "source": "דף הנתונים (Aperture / Entrance pupil), או f חלקי ה-F-number.",
        "mistakes": ["להזין את ה-F-number במקום הקוטר.", "להזין רדיוס במקום קוטר."],
        "check": _check_D,
    },
    "optics.F_general": {
        "title": "F-number אפקטיבי",
        "what": "היחס בין אורך המוקד לקוטר המפתח (f/D).",
        "why": "F קטן = יותר אור ופחות טשטוש עקיפה. במקורר ה-F צריך להתאים למגן הקר (cold shield).",
        "impact": 2, "impact_note": "דרך הקוטר D",
        "typical": ["לא-מקורר: F/1-F/1.4.", "MWIR מקורר: F/4-F/5.5.", "מצלמת יום: F/2-F/8."],
        "source": "דף הנתונים.", "mistakes": [],
        "check": _range(0.7, 16, "", None),
    },
    "optics.tau_opt": {
        "title": "העברת האופטיקה (τ)",
        "what": "איזה חלק מהאור עובר דרך העדשות (0-1), בלי הסתרה מרכזית.",
        "why": "מקטין את האות באופן ישיר. משמעותי במערכות מורעבות-פוטונים (SWIR לילה: גמישות עד 0.36); "
               "כמעט לא משנה בלא-מקורר.",
        "impact": 2, "impact_note": "חשוב בלילה ובמערכות חלשות-אות",
        "typical": ["עדשה תרמית טובה: 0.8-0.9.", "זום מורכב או עם חלון: 0.6-0.75."],
        "source": "דף הנתונים או מדידה.", "mistakes": ["להזין באחוזים (85) במקום שבר (0.85)."],
        "check": _range(0.2, 1.0, "", "טיפוסי 0.7-0.9", suggest=lambda v: round(v / 100.0, 4) if 1 < v <= 100 else None),
    },
    "detector.n_h": {
        "title": "מספר פיקסלים אופקי",
        "what": "מספר העמודות בגלאי (למשל 640 ב-640x512).",
        "why": "יחד עם הפסיעה והמוקד קובע את שדה הראייה. לא משנה את הטווח עצמו - רק את רוחב השדה.",
        "impact": 1, "impact_note": "קובע FOV, לא טווח",
        "typical": ["תרמי: 320, 640, 1280.", "נראה: 1920, 2048, 4096."],
        "source": "דף הנתונים של הגלאי / המצלמה.", "mistakes": [],
        "check": _range(64, 20000, "", None),
    },
    "detector.pitch_h_um": {
        "title": "פסיעת הפיקסלים",
        "what": "המרחק בין מרכזי פיקסלים סמוכים, במיקרון.",
        "why": "יחד עם המוקד קובע את ה-IFOV (= פסיעה / מוקד). פיקסל קטן יותר באותו מוקד נותן יותר פיקסלים על "
               "המטרה - אבל רק אם האופטיקה מספיק חדה (Fλ/d). ב-LWIR, מעבר מ-17 ל-12 µm הוסיף 22%-31% לטווח; "
               "ב-MWIR ב-F/4 כמעט ללא שינוי.",
        "impact": 2, "impact_note": "תלוי ביחס Fλ/d",
        "typical": ["לא-מקורר: 10, 12, 17 µm.", "מקורר: 8-15 µm.", "CMOS יום: 1.4-6 µm."],
        "source": "דף הנתונים של הגלאי (Pixel pitch). אפשר גם Run > Detector lookup.",
        "mistakes": ["לבלבל בין פסיעה לגודל האזור הרגיש (fill factor)."],
        "check": _check_pitch,
    },
    "detector.noise_mode": {
        "title": "מקור נתוני הרעש",
        "what": "Physics model: הרעש מחושב מנתוני הגלאי. Measured camera NETD: ה-NETD שנמדד מחליף את מודל הרעש.",
        "why": "כשיש NETD מדוד למצלמה השלמה - זה מקור אמין יותר מחישוב.",
        "impact": 1, "impact_note": "בחירת מקור, לא ערך",
        "typical": ["יש NETD בדף הנתונים של המצלמה: Measured."], "source": "דף הנתונים או מדידה.",
        "mistakes": ["להזין NETD של הגלאי (detector-level) כאילו הוא של המצלמה - צריך את ה-F וה-τ שבהם נמדד."],
    },
    "detector.netd_mK": {
        "title": "NETD - רגישות תרמית",
        "what": "הפרש הטמפרטורה הקטן ביותר שנותן יחס אות-לרעש 1. ככל שהוא קטן - המצלמה רגישה יותר.",
        "why": "משפיע פחות ממה שמצפים: |גמישות| ≤ 0.2 ברוב המקרים. הוא חשוב כשהניגוד ΔT נמוך, במזג אוויר "
               "גרוע או במוקד ארוך.",
        "impact": 1, "impact_note": "חשוב בניגוד נמוך ובמזג אוויר גרוע",
        "typical": ["לא-מקורר: 30-80 mK.", "מקורר: 15-40 mK."],
        "source": "דף הנתונים. חשוב: באיזה F, טמפרטורת רקע וקצב פריימים נמדד.",
        "mistakes": ["להשוות NETD שנמדדו ב-F שונה.", "להזין ב-K במקום ב-mK."],
        "check": _check_netd,
    },
    "detector.tint_ms": {
        "title": "זמן אינטגרציה",
        "what": "כמה זמן הגלאי אוסף פוטונים בכל פריים.",
        "why": "יותר זמן = יותר אות ופחות רעש, עד שהבאר מתמלאת. חשוב ב-SWIR לילה (גמישות עד 0.32); "
               "במקורר ביום הבאר מגבילה.",
        "impact": 2, "impact_note": "חשוב במערכות מורעבות-אור",
        "typical": ["MWIR / LWIR מקורר: 0.1-10 ms.", "SWIR לילה: 10-33 ms.", "יום: 0.01-5 ms."],
        "source": "הגדרות המצלמה בתרחיש.", "mistakes": ["זמן אינטגרציה ארוך מזמן הפריים (1/קצב)."],
        "check": _check_tint,
    },
    "detector.noise_floor_e": {
        "title": "רעש קריאה",
        "what": "רעש אלקטרוני קבוע שלא תלוי באות, באלקטרונים (rms).",
        "why": "במערכות לילה (SWIR) זה מנוף מרכזי: מעבר מ-30 ל-300 e- קיצר את הטווח ב-57%. ביום כמעט לא משפיע.",
        "impact": 2, "impact_note": "חשוב בלילה",
        "typical": ["CMOS מודרני: 1-5 e-.", "InGaAs: 20-100 e-.", "מקורר IR: 50-500 e-."],
        "source": "דף הנתונים של הגלאי (Read noise).", "mistakes": [],
        "check": _range(0, 5000, "e-", None),
    },
    "basic.frame_rate": {
        "title": "קצב פריימים",
        "what": "מספר פריימים בשנייה.",
        "why": "קובע את זמן האינטגרציה המקסימלי וכמה פריימים העין משלבת. השפעה קטנה בתחום הרגיל.",
        "impact": 1, "impact_note": "משני",
        "typical": ["25, 30, 50 או 60 Hz."], "source": "דף הנתונים.", "mistakes": [],
        "check": _range(1, 1000, "Hz", None),
    },
    "display.observation": {
        "title": "אופן הצפייה",
        "what": "צפייה ישירה במסך, או דרך עינית.",
        "why": "קובע את ההגדלה הזוויתית שהעין רואה. תצוגה שהוגדרה לא נכון היא מקור נפוץ לטעות.",
        "impact": 2, "impact_note": "דרך ההגדלה",
        "typical": ["מסך בעמדה: Direct.", "כוונת / משקפת: Eyepiece."], "source": "תצורת המערכת.", "mistakes": [],
    },
    "display.distance_cm": {
        "title": "מרחק צפייה במסך",
        "what": "המרחק מעין הצופה למסך.",
        "why": "קובע את ההגדלה הזוויתית. מסך קרוב יותר = פרטים גדולים יותר לעין (זום x2: עד +13.5%).",
        "impact": 2, "impact_note": "מנוף תצוגה",
        "typical": ["מסך שולחני: 50-70 cm.", "טאבלט / מסך ידני: 30-40 cm."],
        "source": "תצורת העמדה.", "mistakes": [],
        "check": _range(5, 300, "cm", None),
    },
    "display.snr_th": {
        "title": "סף SNR של הצופה",
        "what": "יחס האות-לרעש שהצופה צריך כדי להבחין בדפוס.",
        "why": "קבוע כיול של מודל הצופה. ערך גבוה = צופה זהיר = טווח קצר יותר (גמישות עד -0.37 ב-SWIR).",
        "impact": 2, "impact_note": "קבוע כיול - לא לשנות בלי סיבה",
        "typical": ["ברירת המחדל: 2.5 (מקובל 2.5-3)."],
        "source": "השאירו את ברירת המחדל, אלא אם יש כיול של צופים.",
        "mistakes": ["להוריד את הסף כדי \"לקבל טווח\"."],
        "check": _check_snr,
    },
    "stab.jitter_preset": {
        "title": "ריצוד קו הראייה (preset)",
        "what": "ממלא ריצוד אקראי טיפוסי: 70 µrad rms - הנוהג ב-NV-IPM.",
        "why": "בלי ריצוד, מערכות עם שדה צר (IFOV < 210 µrad) מקבלות תחזית אופטימית מדי.",
        "impact": 3, "impact_note": "חשוב בשדה צר",
        "typical": ["אין מדידה של המייצב: 70 µrad (NV-IPM).", "יש מדידה: הזינו אותה."],
        "source": "מדידת ייצוב / דף נתונים של הגימבל.", "mistakes": [],
        "check": _check_jitter_preset,
    },
    "stab.rand_h_mrad": {
        "title": "ריצוד אקראי (rms)",
        "what": "עוצמת הריצוד האקראי בזמן האינטגרציה, ב-mrad rms.",
        "why": "מה שקובע הוא היחס לגודל הפיקסל (IFOV). ריצוד של 0.6 IFOV קיצר זיהוי ב-18.5%; 50 µrad קיצרו ב-47%.",
        "impact": 3, "impact_note": "ביחס ל-IFOV, לא בערך המוחלט",
        "typical": ["גימבל מיוצב טוב: 0.005-0.02 mrad.", "חצובה / רכב: 0.05-0.2 mrad."],
        "source": "מדידת ייצוב.", "mistakes": ["להזין ב-µrad בשדה של mrad (70 במקום 0.07)."],
        "check": _check_jitter,
    },
    "target.preset": {
        "title": "מודל מטרה תקני",
        "what": "מטרה מוכנה עם מידות, ניגוד וקריטריונים. STANAG 4347: רכב 2.3x2.3 m, ΔT = 2 K.",
        "why": "נקודת התחלה עקבית להשוואה בין מערכות.",
        "impact": 3, "impact_note": "קובע מידות וקריטריונים",
        "typical": ["רכב: STANAG 4347.", "אדם: Persons (0.6x1.7 m).", "חפץ ביד: Handheld objects."],
        "source": "דרישות המערכת / התרחיש.", "mistakes": [],
    },
    "target.W_m": {
        "title": "רוחב המטרה",
        "what": "רוחב המטרה במטרים, כפי שרואים אותו מכיוון הצפייה.",
        "why": "גאומטריה טהורה: מטרה גדולה פי 2 נותנת טווח ארוך כמעט פי 2 במערכות מוגבלות-דגימה. "
               "גמישות 0.2-0.5 לכל ממד.",
        "impact": 3, "impact_note": "המנוף השני בחשיבותו",
        "typical": ["רכב: 2.3 m.", "אדם: 0.5-0.6 m.", "משאית: 2.5 m."],
        "source": "הגדרת המטרה בדרישות.", "mistakes": ["להזין בס\"מ.", "להשאיר 0."],
        "check": _check_size,
    },
    "target.H_m": {
        "title": "גובה המטרה",
        "what": "גובה המטרה במטרים.",
        "why": "יחד עם הרוחב קובע את הממד הקריטי (שורש השטח). אותה השפעה גבוהה כמו הרוחב.",
        "impact": 3, "impact_note": "המנוף השני בחשיבותו",
        "typical": ["רכב: 2.3 m.", "אדם עומד: 1.7-1.8 m."], "source": "הגדרת המטרה.", "mistakes": [],
        "check": _check_size,
    },
    "target.D_m": {
        "title": "עומק (אורך) המטרה",
        "what": "אורך המטרה - נראה רק בצפייה מהצד, באלכסון או מלמעלה.",
        "why": "משנה את השטח הנראה לפי זווית הצפייה.",
        "impact": 2, "impact_note": "תלוי בזווית הצפייה",
        "typical": ["רכב: 4-7 m.", "0 = לא בשימוש (צפייה מלפנים)."], "source": "הגדרת המטרה.", "mistakes": [],
        "check": lambda v, p: None if not isinstance(v, (int, float)) else (
            ("warn", "העומק לא יכול להיות שלילי.") if v < 0 else ("ok", "%s מ'." % _n(v))),
    },
    "target.aspect": {
        "title": "זווית הצפייה במטרה",
        "what": "מאיזה צד רואים את המטרה: חזית, צד או אלכסון.",
        "why": "בוחר אילו ממדים יוצרים את השטח הנראה. מהצד רכב נראה גדול יותר מאשר מלפנים.",
        "impact": 2, "impact_note": "דרך השטח הנראה",
        "typical": ["מקרה גרוע: Front."], "source": "התרחיש.", "mistakes": [],
    },
    "target.dT_K": {
        "title": "ניגוד תרמי ΔT",
        "what": "הפרש הטמפרטורה הנראה בין המטרה לרקע, בקלווין.",
        "why": "במודל הגמישות נמוכה יחסית (0.04-0.2), אבל אי-הוודאות בשטח עצומה: פי 2-5. בשחר ובדמדומים "
               "ΔT קורס לאפס. חציית ΔT מ-2 ל-1 K מקצרת גילוי ב-MWIR בכ-13%.",
        "impact": 2, "impact_note": "אי-ודאות גבוהה בשטח",
        "typical": ["תקן STANAG: 2 K.", "רכב עם מנוע פועל: 3-10 K.", "מעבר תרמי: 0-0.5 K."],
        "source": "מדידה בשטח או דרישת המערכת. אם לא ידוע - 2 K, ובדקו גם 1 K.",
        "mistakes": ["להזין את טמפרטורת המטרה במקום ההפרש."],
        "check": _check_dT,
    },
    "target.T_bg_K": {
        "title": "טמפרטורת הרקע",
        "what": "טמפרטורת הסצנה מאחורי המטרה, בקלווין.",
        "why": "קובעת את קרינת הרקע ואת הרעש. בגלאי MWIR בפס צר (XBn) היא חשובה מאוד (גמישות ~1.15): ב-243 K "
               "הגילוי ירד ב-26%.",
        "impact": 2, "impact_note": "חשובה מאוד ב-MWIR בפס צר",
        "typical": ["ממוצע: 288 K (15 °C).", "קיץ במדבר: 305-320 K.", "חורף: 270-280 K."],
        "source": "תנאי התרחיש.", "mistakes": ["להזין בצלזיוס (15 במקום 288)."],
        "check": _check_Tbg,
    },
    "target.t_refl": {
        "title": "החזרות המטרה",
        "what": "איזה חלק מהאור המטרה מחזירה בתחום הגל (0-1).",
        "why": "בחיישן מחזיר, הניגוד נוצר מההפרש בין החזרות המטרה לרקע. החזרות שוות = אין ניגוד = אין טווח.",
        "impact": 3, "impact_note": "יוצר את הניגוד בחיישן מחזיר",
        "typical": ["רכב צבאי: 0.1-0.3.", "צמחייה ב-NIR: 0.4-0.6.", "אספלט: 0.05-0.1."],
        "source": "ספריית חומרים / מדידה.", "mistakes": ["להזין באחוזים."],
        "check": _check_refl,
    },
    "target.b_refl": {
        "title": "החזרות הרקע",
        "what": "איזה חלק מהאור הרקע מחזיר בתחום הגל (0-1).",
        "why": "הניגוד הוא ההפרש בינה לבין החזרות המטרה.",
        "impact": 3, "impact_note": "יוצר את הניגוד בחיישן מחזיר",
        "typical": ["אדמה יבשה: 0.2-0.35.", "צמחייה (נראה): 0.05-0.15."], "source": "ספריית חומרים / מדידה.",
        "mistakes": [], "check": _check_refl,
    },
    "target.t_refl_preset": {
        "title": "חומר המטרה (החזרות ספקטרלית)",
        "what": "חומר שעקומת ההחזרות שלו לאורך הגל משמשת למטרה: דשא, יער, אספלט, בטון, חול ועוד.",
        "why": "בחיישן מחזיר הניגוד הוא ההפרש בין החזרות המטרה לרקע בתחום הגל של המצלמה. אותם שני חומרים "
               "יכולים להיראות שונים מאוד ב-SWIR וכמעט זהים בנראה.",
        "impact": 3, "impact_note": "יוצר את הניגוד בחיישן מחזיר",
        "typical": ["מטרה צבועה / רכב: בחרו חומר קרוב, או עברו ל-Effective והזינו ערך."],
        "source": "ספריית החומרים של התוכנה, או מדידה ספקטרלית.",
        "mistakes": ["לבחור לאותה מטרה ולרקע את אותו החומר - הניגוד יהיה אפס."],
        "check": lambda v, p: _check_materials(p),
    },
    "target.b_refl_preset": {
        "title": "חומר הרקע (החזרות ספקטרלית)",
        "what": "חומר שעקומת ההחזרות שלו משמשת לרקע שמאחורי המטרה.",
        "why": "הניגוד הוא ההפרש בינו לבין חומר המטרה.",
        "impact": 3, "impact_note": "יוצר את הניגוד בחיישן מחזיר",
        "typical": ["שטח פתוח: Dry / Green grassland.", "עירוני: Asphalt / Concrete.", "מדבר: Dark Sand."],
        "source": "התרחיש.", "mistakes": [],
        "check": lambda v, p: _check_materials(p),
    },
    "target.task_preset": {
        "title": "גרסת קריטריוני המשימה",
        "what": "כמה זוגות קווים צריך על המטרה כדי לגלות / להכיר / לזהות. ברירת המחדל: 1/3/6 (TRM4 / STANAG).",
        "why": "זה המנוף החזק ביותר בכל המערכות. מעבר מ-1/3/6 ל-1/4/8 מקצר את ההכרה ב-18% ואת הזיהוי ב-22% - "
               "יותר מרוב שדרוגי החומרה.",
        "impact": 3, "impact_note": "המנוף החזק ביותר",
        "typical": ["השוואה לתוצאות TRM4: 1/3/6.", "דרישה לפי Johnson: 1/4/6.4."],
        "source": "דרישות הלקוח / התקן. תמיד ציינו בדוח באיזה סט השתמשתם.",
        "mistakes": ["להשוות טווחים של שתי מערכות שחושבו עם סטים שונים."],
    },
    "target.tasks.N.lp": {
        "title": "זוגות קווים למשימה",
        "what": "מספר זוגות הקווים (מחזורים) על הממד הקריטי שנדרש למשימה בהסתברות 50%.",
        "why": "יותר זוגות קווים = משימה קשה יותר = טווח קצר יותר. במערכת מוגבלת-דגימה הטווח הפוך-יחסי "
               "לערך (גמישות עד -0.99).",
        "impact": 3, "impact_note": "המנוף החזק ביותר",
        "typical": ["גילוי: 1.", "הכרה: 3-4.", "זיהוי: 6-8."], "source": "קריטריוני המשימה.",
        "mistakes": [], "check": _check_lp,
    },
    "irradiance.preset": {
        "title": "מקור ההארה הטבעי",
        "what": "השמש, הירח או אור הכוכבים - הספקטרום והעוצמה של ההארה.",
        "why": "בחיישן מחזיר ההארה קובעת כמה אות יש. בלילה (ירח / כוכבים) המערכת הופכת למורעבת-אור, ושם "
               "הקוטר, זמן האינטגרציה ורעש הקריאה מכריעים.",
        "impact": 3, "impact_note": "קובע את רמת האות",
        "typical": ["יום: Direct sunlight.", "יום מעונן: Overcast.", "לילה: Full / Quarter moon, Star light."],
        "source": "התרחיש.", "mistakes": [],
    },
    "atmosphere.preset": {
        "title": "מצב אטמוספרה מהיר",
        "what": "הנחתה טיפוסית לתחום הגל: Clear / Average / Adverse. Compare ממלא את שלושתם להשוואה.",
        "why": "האטמוספרה שולטת בגילוי וכמעט לא נוגעת בזיהוי. מ-σ = 0.2 ל-0.35 הגילוי מתקצר ב-22%-40%.",
        "impact": 3, "impact_note": "שולטת בטווח הגילוי",
        "typical": ["דוח לדרישה: Compare - מציג את שלושת המצבים."],
        "source": "אלה הנחות הנדסיות. נתוני מזג אוויר או MODTRAN עדיפים.", "mistakes": [],
    },
    "atmosphere.atm.N.sigma": {
        "title": "מקדם הנחתה σ",
        "what": "העברה = τ0 · exp(-σ · טווח). ערך גבוה = מזג אוויר גרוע = טווח קצר.",
        "why": "גמישות הגילוי ב-MWIR: -0.6 במזג טוב ועד -0.82 בגרוע. בזיהוי ההשפעה קטנה בהרבה.",
        "impact": 3, "impact_note": "שולט בגילוי",
        "typical": ["MWIR: בהיר 0.15, ממוצע 0.3, גרוע 0.8 1/km.", "VIS/NIR: 0.17 / 0.39 / 1.3 1/km.",
                    "SWIR: 0.1 / 0.25 / 0.9 1/km."],
        "source": "MODTRAN / נתוני מזג אוויר / ה-preset.", "mistakes": ["להזין 1/m במקום 1/km."],
        "check": _check_sigma,
    },
    "atmosphere.atm.N.V_km": {
        "title": "טווח ראות מטאורולוגי",
        "what": "טווח הראות (Visual range) - מומר למקדם הנחתה.",
        "why": "בתחום הנראה גמישות 0.41 בגילוי (במזג טוב) ועד 0.78 במזג גרוע.",
        "impact": 3, "impact_note": "שולט בגילוי",
        "typical": ["בהיר: 23-40 km.", "אובך: 5-10 km.", "ערפל: פחות מ-1 km."],
        "source": "תחנה מטאורולוגית.", "mistakes": [],
        "check": _check_V,
    },
    "turbulence.on": {
        "title": "טורבולנציה",
        "what": "כולל את הטשטוש שנגרם מתנודות במקדם השבירה של האוויר.",
        "why": "חשובה בעיקר בתחום הנראה, בנתיב קרקעי ארוך וביום חם: עשור ב-Cn² ≈ ±35% בטווח. בתרמי ההשפעה "
               "קטנה בהרבה.",
        "impact": 3, "impact_note": "חשובה ב-VIS/SWIR, יום, נתיב קרקעי",
        "typical": ["נתיב אופקי מעל 2 ק\"מ ביום: להפעיל."], "source": "התרחיש.", "mistakes": [],
    },
    "turbulence.cn2_preset": {
        "title": "תרחיש Cn²",
        "what": "Cn² טיפוסי לפי אקלים, יום / לילה, עונה ואחוזון (TRM4 טבלה C.2).",
        "why": "ב-Cn² של 1e-12 (אספלט חם בצהריים) הטווח בתחום הנראה התקצר ב-66%-69%.",
        "impact": 3, "impact_note": "חשוב ב-VIS/SWIR",
        "typical": ["ישראל, נגב: Arid.", "צפון / מרכז: Moderate."], "source": "טבלה C.2, או מדידה (r0 מווידאו).",
        "mistakes": [],
    },
    "turbulence.cn2": {
        "title": "עוצמת הטורבולנציה Cn²",
        "what": "קבוע המבנה של מקדם השבירה, ב-m^-2/3.",
        "why": "1e-15 חלשה, 1e-14 בינונית, 1e-13 חזקה, 1e-12 קיצונית.",
        "impact": 3, "impact_note": "חשוב ב-VIS/SWIR",
        "typical": ["לילה: 1e-16-1e-15.", "יום ממוצע: 1e-14.", "צהריים מעל מדבר: 1e-13-1e-12."],
        "source": "מדידה (scintillometer) או preset.", "mistakes": ["להזין 1e-14 כ-14 או כ-1e14."],
        "check": _check_cn2,
    },
}


for _k, _e in MORE.items():
    PARAMS.setdefault(_k, _e)

_ADDITIONAL = re.compile(r"additional\.(pre|post)_[hv]_(type|par)$")


def param(path):
    """Knowledge-base entry of a parameter path, or None."""
    m = _ADDITIONAL.match(path or "")
    if m:
        return PARAMS.get("additional." + m.group(2))
    return PARAMS.get(path) or PARAMS.get(re.sub(r"\.\d+\.", ".N.", path or ""))


def suggestion(res):
    """Suggested value of a check result, or None."""
    return res[2] if res and len(res) > 2 else None


def check(path, value, project):
    """('ok' | 'warn', message[, suggested value]) for the entered value, or None."""
    e = param(path)
    fn = e.get("check") if e else None
    if not fn:
        return None
    try:
        return fn(value, project)
    except Exception:
        return None


# ---------------------------------------------------------------------------------------------
# lessons
# ---------------------------------------------------------------------------------------------
# step keys: title, blocks (RtlCanvas blocks), workflow, page, path, cond(project), tab (result tab), action
def _s(title, *blocks, **kw):
    d = {"title": title, "blocks": list(blocks)}
    d.update(kw)
    return d


P_ = lambda t: ("p", t)
LI = lambda t: ("li", t)
H_ = lambda t: ("h", t)

LESSONS = [
    {"id": "first", "title": "החישוב הראשון", "minutes": 8,
     "summary": "מתבנית מוכנה לטווחי גילוי, הכרה וזיהוי - בתהליך Quick Prediction.",
     "steps": [
         _s("ברוכים הבאים",
            P_("המדריך יוביל אתכם בחישוב טווחים מלא: נעבור על השדות החשובים, נסביר מה כל אחד אומר ונבדוק שהערך "
               "שהזנתם סביר."),
            H_("שלושה כללים להזנה חכמה"),
            LI("מתחילים מתבנית קרובה למערכת שלכם, ומחליפים רק את מה שידוע."),
            LI("קודם הפרמטרים המשפיעים - המשימה, המטרה, האופטיקה והאטמוספרה. פרמטרי הרעש באים אחר כך."),
            LI("לכל ערך שתג המקור שלו preset או assumed - עדיף להחליף בנתון של המערכת."),
            ("box", "tip", ["איך עובדים עם המדריך",
                            "השדה הרלוונטי מסומן בטופס. מזינים ערך, והמדריך בודק אותו מיד. 'הבא' ממשיך לשלב "
                            "הבא; אפשר לסגור ולחזור בכל רגע."], True),
            workflow="quick", page="Quick setup"),
         _s("בחרו תבנית",
            P_("התבנית ממלאת את כל מאות הפרמטרים בערכים עקביים. בחרו את הקרובה למערכת שלכם דרך "
               "File > New from template, או בכפתור New בסרגל הכלים."),
            LI("Thermal LWIR uncooled - מצלמה תרמית לא-מקוררת."),
            LI("Thermal MWIR / LWIR cooled - מצלמה תרמית מקוררת."),
            LI("Visible CMOS - מצלמת יום; Visible/SWIR InGaAs - מצלמת לילה."),
            ("box", "info", ["יש לכם פרופיל מצלמה שמור? בחרו אותו בראש העמוד Quick setup."]),
            workflow="quick", page="Quick setup"),
         _s("קטגוריית החיישן", workflow="quick", page="Quick setup", path="category"),
         _s("סוג הגלאי", workflow="quick", page="Quick setup", path="imager_type", cond=_thermal),
         _s("אורך המוקד", workflow="quick", page="Quick setup", path="optics.f_mm"),
         _s("המטרה", P_("בחרו מטרה תקנית - היא ממלאת מידות, ניגוד וקריטריונים בבת אחת."),
            workflow="quick", page="Quick setup", path="target.preset"),
         _s("רוחב המטרה", workflow="quick", page="Quick setup", path="target.W_m"),
         _s("גובה המטרה", workflow="quick", page="Quick setup", path="target.H_m"),
         _s("הניגוד התרמי", workflow="quick", page="Quick setup", path="target.dT_K", cond=_thermal),
         _s("טמפרטורת הרקע", workflow="quick", page="Quick setup", path="target.T_bg_K", cond=_thermal),
         _s("החזרות המטרה", workflow="quick", page="Quick setup", path="target.t_refl",
            cond=lambda p: not _thermal(p) and _refl_mode(p, "t") == "effective"),
         _s("חומר המטרה", workflow="quick", page="Quick setup", path="target.t_refl_preset",
            cond=lambda p: not _thermal(p) and _refl_mode(p, "t") != "effective"),
         _s("החזרות הרקע", workflow="quick", page="Quick setup", path="target.b_refl",
            cond=lambda p: not _thermal(p) and _refl_mode(p, "b") == "effective"),
         _s("חומר הרקע", workflow="quick", page="Quick setup", path="target.b_refl_preset",
            cond=lambda p: not _thermal(p) and _refl_mode(p, "b") != "effective"),
         _s("ההארה", workflow="quick", page="Quick setup", path="irradiance.preset",
            cond=lambda p: not _thermal(p)),
         _s("האטמוספרה", workflow="quick", page="Quick setup", path="atmosphere.preset", cond=_field),
         _s("טורבולנציה", workflow="quick", page="Quick setup", path="turbulence.on",
            cond=lambda p: _field(p) and not _thermal(p)),
         _s("שדה או מעבדה", workflow="quick", page="Quick setup", path="mode.environment"),
         _s("קריטריון הזיהוי", P_("שלוש המשימות (גילוי, הכרה, זיהוי) מופיעות בתחתית העמוד. זה השדה של "
                                  "הזיהוי - המשימה הקשה ביותר."),
            workflow="quick", page="Quick setup", path="target.tasks.2.lp"),
         _s("מחשבים",
            P_("לחצו Calculate בסרגל הכלים (או F5), או השתמשו בכפתור 'חשב עכשיו' כאן. החישוב לוקח כמה שניות."),
            ("box", "info", ["אם מופיעה הודעת Calculation error - היא אומרת איזה ערך לא תקין. תקנו וחשבו שוב."]),
            workflow="quick", page="Quick setup", action="calculate"),
         _s("קוראים את התוצאה",
            P_("בעמוד Summary מופיעים טווחי הגילוי, ההכרה והזיהוי בק\"מ."),
            LI("גילוי: יש משהו שם. הכרה: סוג (רכב / אדם). זיהוי: איזה רכב."),
            LI("כל טווח הוא בהסתברות 50%, עם הקריטריונים שבחרתם."),
            LI("עקומת Range מראה איך הביצועים יורדים עם הטווח."),
            workflow="quick", tab="Summary"),
         _s("לפני שמשתמשים במספר",
            P_("עברו על Messages: שם כל האזהרות וההנחות שעליהן נשען החישוב."),
            ("box", "warn", ["חשוב", "מספר שנראה טוב אינו בהכרח נכון. טווח בלי ההנחות שלו לא שווה הרבה."], True),
            P_("סיימתם את השיעור הראשון. בשיעור הבא נזין מערכת אמיתית ברמה ההנדסית."),
            workflow="quick", tab="Messages"),
     ]},
    {"id": "engineering", "title": "הזנת מערכת אמיתית", "minutes": 12,
     "summary": "אופטיקה, גלאי, תצוגה וייצוב - לפי סדר ההשפעה, בתהליך Engineering Analysis.",
     "steps": [
         _s("סדר העבודה",
            P_("במצב Engineering מוצגים כל העמודים. לא צריך למלא הכול: ממלאים לפי סדר ההשפעה על הטווח."),
            H_("מה באמת קובע את הטווח"),
            ("chips", [("1. קריטריון המשימה", "high"), ("2. מידות המטרה", "high"), ("3. מוקד / IFOV", "high"),
                       ("4. קוטר D", "high"), ("5. אטמוספרה", "high"), ("6. טורבולנציה", "mid"),
                       ("7. ריצוד", "mid"), ("8. תצוגה וצופה", "mid"), ("NETD ורעש", "low")]),
            P_("בכל מערכת כ-70 מתוך כ-100 פרמטרים כמעט לא משפיעים. אל תבזבזו זמן על הדיוק שלהם."),
            workflow="engineering", page="General"),
         _s("Fλ/d - מי מגביל?",
            P_("היחס Fλ/d (F-number כפול אורך הגל, חלקי הפסיעה) אומר מה מגביל את המערכת:"),
            LI("Fλ/d < 1: הגלאי מגביל (מוגבל-דגימה). מוקד ארוך יותר או פיקסל קטן יותר עוזרים מאוד."),
            LI("Fλ/d > 1.5: האופטיקה מגבילה (עקיפה). קוטר גדול יותר עוזר; פיקסל קטן יותר כמעט לא."),
            ("box", "info", ["הערך מוצג בפאנל הערכים המחושבים בתחתית עמוד Optics."]),
            workflow="engineering", page="Optics"),
         _s("איך מוגדר המפתח", workflow="engineering", page="Optics", path="optics.aperture"),
         _s("קוטר המפתח", workflow="engineering", page="Optics", path="optics.D_mm",
            cond=lambda p: p.get("optics", {}).get("aperture") == "circular"),
         _s("F-number", workflow="engineering", page="Optics", path="optics.F_general",
            cond=lambda p: p.get("optics", {}).get("aperture") != "circular"),
         _s("אורך המוקד", workflow="engineering", page="Optics", path="optics.f_mm"),
         _s("העברת האופטיקה", workflow="engineering", page="Optics", path="optics.tau_opt"),
         _s("מספר הפיקסלים", workflow="engineering", page="Detector geometry", path="detector.n_h"),
         _s("פסיעת הפיקסלים", P_("טיפ: Run > Detector lookup (Ctrl+D) ממלא את נתוני הגלאי מהקטלוג."),
            workflow="engineering", page="Detector geometry", path="detector.pitch_h_um"),
         _s("מקור נתוני הרעש", workflow="engineering", page="Detector sensitivity", path="detector.noise_mode",
            cond=_thermal),
         _s("NETD", workflow="engineering", page="Detector sensitivity", path="detector.netd_mK",
            cond=lambda p: _thermal(p) and (p.get("imager_type") == "uncooled" or
                                            p.get("detector", {}).get("noise_mode") == "measured")),
         _s("זמן אינטגרציה", workflow="engineering", page="Detector sensitivity", path="detector.tint_ms",
            cond=lambda p: p.get("imager_type") != "uncooled"),
         _s("רעש קריאה", workflow="engineering", page="Detector sensitivity", path="detector.noise_floor_e",
            cond=lambda p: not _thermal(p)),
         _s("קצב פריימים", workflow="engineering", page="Basic imager", path="basic.frame_rate"),
         _s("אופן הצפייה", workflow="engineering", page="Display & observer", path="display.observation"),
         _s("מרחק הצפייה", workflow="engineering", page="Display & observer", path="display.distance_cm",
            cond=lambda p: p.get("display", {}).get("observation") == "direct"),
         _s("סף ה-SNR", workflow="engineering", page="Display & observer", path="display.snr_th"),
         _s("ריצוד", workflow="engineering", page="Stabilization & MTFs", path="stab.jitter_preset"),
         _s("ריצוד אקראי", workflow="engineering", page="Stabilization & MTFs", path="stab.rand_h_mrad"),
         _s("גרסת הקריטריונים", workflow="engineering", page="Target & scenario", path="target.task_preset"),
         _s("זווית הצפייה", workflow="engineering", page="Target & scenario", path="target.aspect"),
         _s("מקדם ההנחתה", P_("כאן מזינים את האטמוספרה 1. אפשר להפעיל עד שלוש אטמוספרות להשוואה."),
            workflow="engineering", page="Atmosphere & turbulence", path="atmosphere.atm.0.sigma",
            cond=lambda p: _field(p) and p.get("atmosphere", {}).get("mode") == "extinction"),
         _s("טווח הראות", workflow="engineering", page="Atmosphere & turbulence", path="atmosphere.atm.0.V_km",
            cond=lambda p: _field(p) and p.get("atmosphere", {}).get("mode") in ("visibility", "weather")),
         _s("תג המקור של כל ערך",
            P_("ליד כל שדה יש תג קטן: preset, datasheet, measured, assumed ועוד. לחיצה עליו משנה אותו."),
            LI("הדוחות מציגים לכל טווח על אילו נתונים הוא נשען."),
            LI("ערך שנשאר preset הוא ניחוש כללי. עדכנו לפחות את הפרמטרים המשפיעים."),
            ("box", "ok", ["סיכום", "הזנתם את כל מה שבאמת קובע את הטווח. חשבו (F5) ועברו לשיעור 3."], True),
            workflow="engineering", page="Optics", action="calculate"),
     ]},
    {"id": "results", "title": "קריאת התוצאות ושיפור", "minutes": 7,
     "summary": "מה מגביל את הטווח, מה הכי כדאי לשפר, אי-ודאות ודוח בעברית.",
     "steps": [
         _s("המסך Summary",
            P_("Summary מציג את טווחי ה-DRI לכל אטמוספרה, את רמת הביטחון ואת הסיבה העיקרית לכל טווח."),
            ("box", "info", ["אם עוד לא חישבתם - לחצו 'חשב עכשיו'."]),
            workflow="engineering", tab="Summary", action="calculate"),
         _s("System data", P_("כל הערכים המחושבים: IFOV, FOV, Fλ/d, NETD אפקטיבי, מילוי באר ועוד. כאן בודקים "
                              "שהמערכת שהזנתם היא באמת המערכת שהתכוונתם אליה."),
            LI("IFOV ו-FOV תואמים לדף הנתונים?"), LI("מילוי הבאר סביר (לא 0% ולא 100%)?"),
            workflow="engineering", tab="System data"),
         _s("מה מגביל את הטווח",
            P_("Run > Limiting factors מראה לכל משימה מה מגביל אותה: אטמוספרה, עקיפה, דגימה, רעש או ריצוד."),
            ("box", "tip", ["למה זה חשוב", "שדרוג של גורם שאינו מגביל לא ישנה את הטווח. קודם מוצאים את "
                            "צוואר הבקבוק."], True),
            workflow="engineering", tab="Sensitivity"),
         _s("יועץ השיפור",
            P_("Run > Improve performance (advisor) מדרג שינויים אפשריים לפי התועלת בטווח, עם כרטיס לכל פעולה."),
            LI("היועץ מייעץ בלבד - הוא לא משנה את הפרויקט."),
            LI("'Measure first' מסמן פרמטרים שכדאי למדוד לפני שמשקיעים בחומרה."),
            workflow="engineering", tab="Sensitivity"),
         _s("סריקת פרמטר ואי-ודאות",
            LI("Parameter sweep: איך פרמטר אחד משנה את הטווח - עקומה וטבלה."),
            LI("Uncertainty study: טווח עם אי-ודאות (RSS או Monte Carlo). הזינו ± לפרמטרים הלא-ודאיים: "
               "ΔT, σ וקריטריון המשימה."),
            LI("Scenario comparison: כמה תרחישים זה לצד זה."),
            workflow="engineering", tab="Sensitivity"),
         _s("דוח ושמירה",
            LI("File > Export Hebrew DRI report (PDF) - דוח מלא בעברית."),
            LI("File > Export report - דוח טקסט עם כל ההנחות."),
            LI("File > Save - שומר את הפרויקט (json) עם תגי המקור."),
            ("box", "ok", ["סיימתם!", "אפשר לפתוח את המדריך שוב בכל עת מ-Help > Interactive guide, או "
                           "להשאיר אותו פתוח: בלחיצה על שדה מוצג כרטיס הסבר שלו."], True),
            workflow="engineering", tab="Summary"),
     ]},
]


LESSONS.append(
    {"id": "tour", "title": "סיור מלא באפליקציה", "minutes": 30, "dynamic": True,
     "summary": "כל העמודים וכל השדות שהפרויקט שלכם מציג, קבוצה אחר קבוצה: מה כל שדה אומר, בדיקה של הערך שלכם "
                "וההשפעה שלו על הטווח.",
     "steps": []})

# Hebrew name and purpose of every page of the form (the tour)
PAGE_HE = {
    "General": ("כללי", "ההחלטות הראשונות: קטגוריית החיישן, שדה או מעבדה, וידאו או תמונה בודדת."),
    "Basic imager": ("המצלמה הבסיסית", "קצב פריימים, בדיקת FOV, מיקרו-סריקה, איחוד פיקסלים ותזמון החשיפה."),
    "Optics": ("אופטיקה", "המפתח, אורך המוקד, ה-MTF של העדשה וההעברה. כאן נקבעים ה-IFOV, העקיפה וכמות האור - "
                          "מהמנופים החזקים של הטווח."),
    "Detector geometry": ("גאומטריית הגלאי", "מספר הפיקסלים, הפסיעה והגודל הפעיל. הפסיעה יחד עם המוקד קובעת את "
                                             "ה-IFOV."),
    "Detector sensitivity": ("רגישות הגלאי", "התחום הספקטרלי, הרעש (NETD או מודל פיזיקלי), זמן האינטגרציה, הבאר "
                                             "והמגן הקר. חשוב בעיקר במערכות מוגבלות-רעש: לילה, ניגוד נמוך."),
    "Signal processing": ("עיבוד אות", "מיצוע פריימים, מסננים, זום, דחיסה ועקומת טון. רוב השדות כאן כבויים "
                                       "בברירת המחדל."),
    "Display & observer": ("תצוגה וצופה", "איך הצופה רואה את התמונה: מסך או עינית, מרחק, בהירות וקבועי הכיול של "
                                          "הצופה."),
    "Stabilization & MTFs": ("ייצוב ו-MTF נוספים", "תנועת קו הראייה: ריצוד, תנועה ליניארית ורטט. בשדה צר זה מנוף "
                                                   "חשוב."),
    "Target & scenario": ("מטרה ותרחיש", "המטרה, הניגוד, הגאומטריה וקריטריוני המשימה - המנופים החזקים ביותר על "
                                         "הטווח."),
    "Irradiance": ("הארה", "מקור האור בחיישן מחזיר (נראה / SWIR / General). בתרמי העמוד לא בשימוש."),
    "Atmosphere & turbulence": ("אטמוספרה וטורבולנציה", "ההנחתה שולטת בגילוי; הטורבולנציה מטשטשת בעיקר בנראה "
                                                        "ובנתיב קרקעי ארוך ביום."),
    "Metadata": ("מטא-דאטה", "תיעוד של נתונים מיובאים ומצבי עבודה. לא משתתף בחישוב, אבל נכנס לדוח."),
    "Validation data": ("נתוני אימות", "מדידות מעבדה (MTDP / MRTD, MTF, NETD) להשוואה עם התחזית."),
}


def _visible_fields(fields, project, visible):
    """[(header, [field])] of one page with the fields the form shows for the project (each path once)."""
    groups, cur, seen = [], None, set()
    for f in fields:
        if f.get("kind") == "header":
            cur = [f, []]
            groups.append(cur)
            continue
        path = f.get("path")
        if not path or f.get("kind") in ("derived", "profile", "profile_manager") or path in seen:
            continue
        if cur is None:
            cur = [None, []]
            groups.append(cur)
        try:
            show = visible(f, cur[0], project)
        except Exception:
            show = True
        if show:
            seen.add(path)
            cur[1].append(f)
    return [(h, fl) for h, fl in groups if fl]


def tour_steps(pages, project, visible):
    """Steps of the full tour: an introduction, then one step per shown group of fields of every page.
    pages: [(page name, fields, workflow)]; visible(field, header, project) is the form's own rule."""
    out = [_s("איך עובד הסיור",
              P_("נעבור על כל עמודי הטופס במצב Engineering, קבוצה אחר קבוצה. בכל שלב מופיעים השדות של הקבוצה: הערך "
                 "שלכם, בדיקה שלו, וכמה הוא משפיע על הטווח."),
              LI("לחיצה על שדה ברשימה פותחת את הכרטיס המלא שלו, עם חישוב חי של ההשפעה על טווחי הגילוי, ההכרה "
                 "והזיהוי."),
              LI("שדה שמסומן ⚠ דורש בדיקה. ⓘ = שדה שלא משפיע על הטווח (תיעוד או בדיקה צולבת)."),
              LI("מוצגים רק השדות שהפרויקט שלכם משתמש בהם. 'Show advanced parameters' מוסיף את השדות המתקדמים."),
              ("box", "tip", ["טיפ", "לא צריך לשנות כל שדה. שדה עם ★ אחד או בלי כוכב אפשר להשאיר בברירת המחדל אם "
                              "אין נתון טוב יותר."], True),
              workflow="engineering", page="General")]
    for name, fields, wf in pages:
        groups = _visible_fields(fields, project, visible)
        he, desc = PAGE_HE.get(name, (name, ""))
        for gi, (hdr, fl) in enumerate(groups):
            blocks = []
            if gi == 0:
                blocks.append(("box", "info", ["עמוד %s (%s)" % (he, name), desc], True))
            if hdr is not None:
                blocks.append(("muted", "קבוצה: " + hdr["label"]))
            out.append(_s("%s · %d/%d" % (he, gi + 1, len(groups)), *blocks, workflow=wf, page=name,
                          path=fl[0]["path"], fields=[f["path"] for f in fl], group=True))
    out.append(_s("בדיקת כל הערכים",
                  P_("סיימתם את הסיור. כאן מופיעות כל ההערות על הערכים שלכם, מסודרות לפי ההשפעה על הטווח. לחיצה על "
                     "שורה פותחת את השדה."),
                  workflow="engineering", page="General", review=True, action="calculate"))
    return out


def field_summary(path, value, project):
    """(state 'warn' | 'ok' | 'info', title, text, meta) of a field for the lists of the tour and the review."""
    e = param(path)
    if not e:
        return None
    res = check(path, value, project)
    imp = e.get("impact", 1)
    state = "warn" if res and res[0] == "warn" else ("info" if imp == 0 else "ok")
    mark = {"warn": "⚠ ", "info": "ⓘ ", "ok": ""}[state]
    text = res[1] if res else e["why"].split(". ")[0].rstrip(".") + "."
    meta = "ערך: %s · %s" % (_value_text(value), ("★" * imp + " " if imp else "") + IMPACT_TEXT[imp])
    return state, mark + e["title"], text, meta


def review(pages, project, visible, value):
    """Check every shown field of a project -> {"warn": [(impact, path, page, check)], "ok": n, "n": n}.
    value(path) returns the entered value."""
    warns, n, ok, seen = [], 0, 0, set()
    for name, fields, _wf in pages:
        for _h, fl in _visible_fields(fields, project, visible):
            for f in fl:
                path = f["path"]
                if path in seen or not param(path):
                    continue
                seen.add(path)
                res = check(path, value(path), project)
                if not res:
                    continue
                n += 1
                if res[0] == "warn":
                    warns.append((param(path).get("impact", 1), path, name, res))
                else:
                    ok += 1
    warns.sort(key=lambda w: -w[0])
    return {"warn": warns, "ok": ok, "n": n}


def lesson(lesson_id):
    for les in LESSONS:
        if les["id"] == lesson_id:
            return les
    return None


def steps(lesson_id, project, pages=None, visible=None):
    """Steps of a lesson that apply to the project (cond).  The tour needs the form (pages, visible)."""
    les = lesson(lesson_id)
    if les and les.get("dynamic"):
        return tour_steps(pages, project, visible) if pages is not None and visible is not None else []
    out = []
    for st in (les["steps"] if les else []):
        try:
            ok = st.get("cond") is None or st["cond"](project)
        except Exception:
            ok = True
        if ok:
            out.append(st)
    return out


def _value_text(v):
    if isinstance(v, bool):
        return "מופעל" if v else "כבוי"
    if isinstance(v, dict):                         # imported file
        return v.get("name") or "לא יובא קובץ"
    if isinstance(v, list):
        return ", ".join(_n(x) for x in v)
    if v is None or v == "":
        return "ריק"
    return _n(v)


def field_blocks(path, value=None, project=None, extra=()):
    """RtlCanvas blocks of the field card of a parameter.  `extra` (the live effect on the ranges) is placed right
    after the check of the value."""
    e = param(path)
    if not e:
        return []
    imp = e.get("impact", 1)
    chips = [(("★" * imp + "  " if imp else "") + IMPACT_TEXT[imp], IMPACT_STYLE[imp])]
    if e.get("impact_note"):
        chips.append((e["impact_note"], "info"))
    out = [("chips", chips)]
    res = check(path, value, project) if project is not None else None
    if res:                                         # the live check first, where it is seen
        lines = ["הערך שלכם" if res[0] == "ok" else "כדאי לבדוק", res[1]]
        s = suggestion(res)
        if s is not None:
            lines.append("מה לעשות: נסו %s - הכפתור 'החל את הערך המוצע' מזין אותו, ו'בטל' מחזיר." % _value_text(s))
        out.append(("box", "ok" if res[0] == "ok" else "warn", lines, True))
    out += list(extra)
    out += [("p", e["what"]), ("h", "למה זה חשוב"), ("p", e["why"])]
    if e.get("typical"):
        out.append(("h", "ערכים טיפוסיים"))
        out += [("li", t) for t in e["typical"]]
    if e.get("source"):
        out += [("h", "מאיפה לוקחים את הערך"), ("p", e["source"])]
    if e.get("mistakes"):
        out.append(("box", "tip", ["טעויות נפוצות"] + list(e["mistakes"]), True))
    return out
