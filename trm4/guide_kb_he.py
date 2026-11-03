"""Field cards of the interactive Hebrew guide for every parameter of the form beyond the range-deciding ones of
guide_he.PARAMS: what the value means, how strongly it moves the DRI ranges, typical values, where to take it from,
common mistakes and a plausibility check.

A check returns ("ok" | "warn", message) or ("warn", message, suggested value): the message says why the value is
not plausible and what it does to the ranges / image; the suggested value is offered by the guide panel ("try the
suggested value") and its effect on the ranges is computed live (guide_impact).

Impact 0 = not used in the range calculation (documentation, cross-check or diagnostic only).
"""


def _n(v):
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e6:
            return str(int(v))
        if abs(v) < 1e-3 or abs(v) >= 1e5:
            return "%.2g" % v
        return ("%.3f" % v).rstrip("0").rstrip(".")
    return str(v)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _range(lo, hi, unit, typical=None, suggest=None):
    """Plausibility check: warn outside [lo, hi]; `suggest(v)` proposes a corrected value (unit mistakes)."""
    def check(v, p):
        if not _num(v):
            return None
        if v < lo or v > hi:
            msg = "הערך %s %s חריג. הטווח הסביר הוא %s-%s %s. כדאי לבדוק יחידות ומקור." % (
                _n(v), unit, _n(lo), _n(hi), unit)
            s = suggest(v) if suggest else None
            return ("warn", msg, s) if s is not None else ("warn", msg)
        return ("ok", "הערך %s %s בתחום הסביר%s." % (_n(v), unit, (" (" + typical + ")") if typical else ""))
    return check


def _fraction(name, typical=None, allow_zero=True):
    """0..1 quantity; a value in percent is offered divided by 100."""
    def check(v, p):
        if not _num(v):
            return None
        if 1 < v <= 100:
            return ("warn", "%s הוא שבר בין 0 ל-1, לא אחוזים: %s נראה כמו %s%%. ערך מעל 1 מגדיל את האות מעבר "
                            "לפיזיקלי ומנפח את הטווח." % (name, _n(v), _n(v)), round(v / 100.0, 4))
        if v < 0 or v > 1 or (v == 0 and not allow_zero):
            return ("warn", "%s חייב להיות בין 0 ל-1." % name)
        return ("ok", "%s = %s%s." % (name, _n(v), (" (" + typical + ")") if typical else ""))
    return check


def _kelvin(lo, hi, what):
    """Temperature in K; a value that looks like Celsius is offered + 273.15."""
    def check(v, p):
        if not _num(v):
            return None
        if v == 0:
            return ("ok", "0 = לא צוין / כמו בפרויקט.")
        if v < lo or v > hi:
            msg = "%s של %s K (%.0f °C) חריגה. שימו לב: הערך בקלווין." % (what, _n(v), v - 273.15)
            if -60 <= v <= 80:
                return ("warn", msg + " נראה שהוזן בצלזיוס - %s °C = %s K." % (_n(v), _n(round(v + 273.15, 2))),
                        round(v + 273.15, 2))
            return ("warn", msg)
        return ("ok", "%s K = %.0f °C." % (_n(v), v - 273.15))
    return check


def _positive_int(name, lo=1, hi=None):
    def check(v, p):
        if not _num(v):
            return None
        if v < lo:
            return ("warn", "%s חייב להיות לפחות %s." % (name, _n(lo)), lo)
        if hi is not None and v > hi:
            return ("warn", "%s של %s חריג (מעל %s)." % (name, _n(v), _n(hi)))
        return ("ok", "%s = %s." % (name, _n(v)))
    return check


def _nonneg(name, unit=""):
    def check(v, p):
        if not _num(v):
            return None
        if v < 0:
            return ("warn", "%s לא יכול להיות שלילי." % name, 0.0)
        return ("ok", "%s = %s %s." % (name, _n(v), unit))
    return check


def _det(p):
    return p.get("detector", {})


def _opt(p):
    return p.get("optics", {})


def _frame_ms(p):
    fr = p.get("basic", {}).get("frame_rate") or 0
    return 1000.0 / fr if fr else None


def _ifov_mrad(p):
    f = _opt(p).get("f_mm") or 0
    pitch = _det(p).get("pitch_h_um") or 0
    return pitch / f if f and pitch else None


# ---------------------------------------------------------------------------------------------
# cross-field checks
# ---------------------------------------------------------------------------------------------
def _check_n_v(v, p):
    if not _num(v):
        return None
    nh = _det(p).get("n_h") or 0
    if v < 16 or v > 20000:
        return ("warn", "מספר שורות של %s חריג." % _n(v))
    if nh and (v > 4 * nh or nh > 6 * v):
        return ("warn", "יחס הצדדים %s x %s חריג - ייתכן שהוחלפו שורות ועמודות." % (_n(nh), _n(v)))
    return ("ok", "%s x %s פיקסלים." % (_n(nh), _n(v)))


def _check_pitch_v(v, p):
    if not _num(v):
        return None
    ph = _det(p).get("pitch_h_um") or 0
    if v <= 0:
        return ("warn", "הפסיעה חייבת להיות חיובית.", ph or None)
    if ph and abs(v - ph) / ph > 0.5:
        return ("warn", "הפסיעה האנכית (%s µm) שונה מאוד מהאופקית (%s µm). בגלאי רגיל הפיקסל ריבועי; פסיעה אנכית "
                        "גדולה מגדילה את ה-IFOV האנכי ומקצרת את הטווח." % (_n(v), _n(ph)), ph)
    return ("ok", "%s µm." % _n(v))


def _check_active(axis):
    def check(v, p):
        if not _num(v):
            return None
        pitch = _det(p).get("pitch_%s_um" % axis) or 0
        if v <= 0:
            return ("warn", "הגודל הפעיל חייב להיות חיובי.", pitch or None)
        if pitch and v > pitch * 1.001:
            return ("warn", "האזור הפעיל (%s µm) גדול מהפסיעה (%s µm) - זה לא אפשרי פיזית. הפיקסל לא יכול להיות "
                            "גדול מהמרחק בין הפיקסלים." % (_n(v), _n(pitch)), pitch)
        if pitch and v < 0.4 * pitch:
            return ("warn", "מקדם מילוי של %.0f%% (פעיל / פסיעה) נמוך מאוד. זה מקטין את האות. בדקו שלא הוזן "
                            "הרדיוס או גודל אחר." % (100 * v / pitch))
        ff = (v / pitch) if pitch else 0
        return ("ok", "מקדם מילוי ליניארי %.0f%%." % (100 * ff)) if pitch else ("ok", "%s µm." % _n(v))
    return check


def _check_f_v(v, p):
    if not _num(v) or not _opt(p).get("diff_focal"):
        return None
    fh = _opt(p).get("f_mm") or 0
    if v <= 0:
        return ("warn", "אורך מוקד חייב להיות חיובי.", fh or None)
    if fh and (v / fh > 3 or fh / v > 3):
        return ("warn", "המוקד האנכי (%s mm) שונה פי יותר מ-3 מהאופקי (%s mm). אופטיקה אנמורפית כזו נדירה - "
                        "בדקו." % (_n(v), _n(fh)))
    return ("ok", "f אנכי = %s mm." % _n(v))


def _check_F_spec(v, p):
    if not _num(v):
        return None
    if v == 0:
        return ("ok", "0 = אין בדיקה צולבת.")
    o = _opt(p)
    if o.get("aperture") == "circular" and o.get("D_mm"):
        F = (o.get("f_mm") or 0) / o["D_mm"]
        if F and abs(v - F) / F > 0.05:
            return ("warn", "ה-F של היצרן (F/%s) שונה ב-%.0f%% מ-f/D = F/%.2f. אחד הנתונים לא נכון: כנראה הקוטר D. "
                            "קוטר שגוי משנה את העקיפה ואת האות." % (_n(v), 100 * abs(v - F) / F, F))
        return ("ok", "תואם ל-f/D = F/%.2f." % F)
    return _range(0.7, 16, "")(v, p)


def _check_obsc(v, p):
    if not _num(v):
        return None
    D = _opt(p).get("D_mm") or 0
    if v < 0:
        return ("warn", "קוטר ההסתרה לא יכול להיות שלילי.", 0.0)
    if v == 0:
        return ("ok", "אין הסתרה מרכזית (עדשה רגילה).")
    if D and v >= D:
        return ("warn", "ההסתרה (%s mm) גדולה מהמפתח (%s mm) - לא יגיע אור לגלאי." % (_n(v), _n(D)))
    if D and v / D > 0.5:
        return ("warn", "הסתרה של %.0f%% מהקוטר - חריג (טלסקופ טיפוסי: 25%%-40%%). היא מורידה אות ומחלישה את "
                        "ה-MTF בתדרים בינוניים." % (100 * v / D))
    return ("ok", "הסתרה של %.0f%% מהקוטר (%.0f%% מהשטח)." % (100 * v / D, 100 * (v / D) ** 2) if D else
            "%s mm." % _n(v))


def _check_q(v, p):
    if not _num(v):
        return None
    if v < 1:
        return ("warn", "q < 1 פירושו עדשה טובה יותר מגבול העקיפה - לא פיזיקלי.", 1.0)
    if v > 4:
        return ("warn", "q = %s - עדשה גרועה מאוד (הטשטוש פי %s מהעקיפה). זה מקצר מאוד את ההכרה והזיהוי." %
                (_n(v), _n(v)))
    return ("ok", "q = %s (1 = מוגבלת-עקיפה, 1.2-1.5 = עדשה טובה)." % _n(v))


def _check_blur(v, p):
    if not _num(v):
        return None
    pitch = _det(p).get("pitch_h_um") or 0
    if v < 0:
        return ("warn", "סטיית תקן לא יכולה להיות שלילית.", 0.0)
    if pitch and v > pitch:
        return ("warn", "כתם טשטוש של σ = %s µm גדול מהפיקסל (%s µm): העדשה מטשטשת יותר ממה שהגלאי דוגם, "
                        "והזיהוי יתקצר מאוד. ערך טיפוסי לעדשה טובה: 0.2-0.5 פיקסל." % (_n(v), _n(pitch)),
                round(0.35 * pitch, 2))
    return ("ok", "σ = %.2f פיקסל." % (v / pitch) if pitch else "%s µm." % _n(v))


def _check_lambda_diff(v, p):
    if not _num(v):
        return None
    if v == 0:
        return ("ok", "0 = אורך הגל הממוצע של התחום (מומלץ).")
    lo, hi = _det(p).get("cuton_um"), _det(p).get("cutoff_um")
    if lo and hi and p.get("category") == "Thermal" and p.get("imager_type") == "uncooled" and not lo <= v <= hi:
        return ("warn", "אורך הגל %s µm מחוץ לתחום הגלאי (%s-%s µm). העקיפה תחושב לא נכון." % (_n(v), _n(lo), _n(hi)),
                0.0)
    return _range(0.3, 15, "µm")(v, p)


def _check_cut(which):
    def check(v, p):
        if not _num(v):
            return None
        d = _det(p)
        lo, hi = (v, d.get("cutoff_um")) if which == "on" else (d.get("cuton_um"), v)
        if v <= 0 or v > 20:
            return ("warn", "אורך גל של %s µm חריג. שימו לב: מיקרון, לא ננומטר." % _n(v))
        if lo is not None and hi is not None and lo >= hi:
            return ("warn", "תחילת התחום (%s µm) לא קטנה מסופו (%s µm) - אין תחום ספקטרלי." % (_n(lo), _n(hi)))
        return ("ok", "תחום %s-%s µm." % (_n(lo), _n(hi)))
    return check


def _check_qe_scale(v, p):
    if not _num(v):
        return None
    if v <= 0:
        return ("warn", "מקדם QE חייב להיות חיובי.", 1.0)
    if v > 1.5:
        return ("warn", "מקדם %s מכפיל את ה-QE מעבר לפיזיקלי (QE לא עולה על 1). זה מנפח את האות." % _n(v), 1.0)
    return ("ok", "QE x %s." % _n(v))


def _check_tint(v, p):
    if not _num(v):
        return None
    if v <= 0:
        return ("warn", "זמן אינטגרציה חייב להיות חיובי.")
    fm = _frame_ms(p)
    if fm and v > fm:
        return ("warn", "זמן האינטגרציה (%s ms) ארוך מזמן הפריים (%.2f ms ב-%s Hz) - לא אפשרי. המודל יחשב אות "
                        "ורעש לא נכונים." % (_n(v), fm, _n(p["basic"]["frame_rate"])), round(0.9 * fm, 3))
    return _range(0.001, 200, "ms")(v, p)


def _check_duty(v, p):
    if not _num(v):
        return None
    if v <= 0 or v > 1:
        if 1 < v <= 100:
            return ("warn", "מחזור העבודה הוא שבר 0-1, לא אחוזים.", v / 100.0)
        return ("warn", "מחזור העבודה חייב להיות בין 0 ל-1.")
    fm = _frame_ms(p)
    return ("ok", "זמן אינטגרציה %.3g ms." % (v * fm) if fm else "%s." % _n(v))


def _check_wellfill(v, p):
    if not _num(v):
        return None
    if v <= 0 or v > 100:
        return ("warn", "מילוי הבאר הוא אחוז בין 0 ל-100.", 50.0)
    if v > 85:
        return ("warn", "מילוי של %s%% מהרקע משאיר מעט מקום לאות: מטרה חמה או בהירה תרווה (saturation). מקובל "
                        "40%%-70%%." % _n(v), 60.0)
    if v < 15:
        return ("warn", "מילוי של %s%% בלבד: זמן אינטגרציה קצר, אות חלש ורעש יחסי גבוה. מקובל 40%%-70%%." % _n(v),
                50.0)
    return ("ok", "מילוי באר %s%%." % _n(v))


def _check_storage(v, p):
    if not _num(v):
        return None
    if v <= 0:
        return ("warn", "קיבולת הבאר חייבת להיות חיובית.")
    if v < 1e3 or v > 1e8:
        return ("warn", "קיבולת של %s נשאים חריגה (טיפוסי: 5e3-5e4 ב-CMOS, 1e6-2e7 ב-IR מקורר)." % _n(float(v)))
    return ("ok", "%s נשאים." % _n(float(v)))


def _check_dark(v, p):
    if not _num(v):
        return None
    if v < 0:
        return ("warn", "זרם אפל לא יכול להיות שלילי.", 0.0)
    if v > 1e-6:
        return ("warn", "זרם אפל של %s A לפיקסל - חריג מאוד (טיפוסי 1e-15 עד 1e-10 A). ייתכן שהוזן ב-nA או "
                        "בצפיפות לסמ\"ר. זרם אפל גבוה ממלא את הבאר ברעש ומקצר את הטווח." % _n(float(v)))
    return ("ok", "%s A לפיקסל." % _n(float(v)))


def _check_gain(v, p):
    if not _num(v):
        return None
    if v < 1:
        return ("warn", "הגבר אלקטרונים קטן מ-1 לא פיזיקלי. 1 = גלאי רגיל.", 1.0)
    return ("ok", "הגבר %s%s." % (_n(v), "" if v == 1 else " (APD / EMCCD)"))


def _check_lsb_e(v, p):
    if not _num(v):
        return None
    d = _det(p)
    if v <= 0:
        return ("warn", "LSB חייב להיות חיובי.")
    rn = d.get("noise_floor_e") or 0
    if rn and v > 3.5 * rn and d.get("adc_mode") == "carriers":
        return ("warn", "צעד ADC של %s נשאים גדול מאוד ביחס לרעש הקריאה (%s e-): רעש הקוונטיזציה (LSB/√12 = %.0f) "
                        "שולט ומעלה את הרעש." % (_n(v), _n(rn), v / 12 ** 0.5))
    return ("ok", "רעש קוונטיזציה %.0f נשאים rms." % (v / 12 ** 0.5))


def _check_adc_bits(v, p):
    if not _num(v):
        return None
    if v == 0:
        return ("ok", "0 = אין בדיקת רוויה של ה-ADC.")
    if v < 8 or v > 24:
        return ("warn", "%s ביטים חריג (טיפוסי 12-16)." % _n(v))
    return ("ok", "%s ביטים = %d רמות." % (_n(v), 2 ** int(v)))


def _check_Tcs(v, p):
    if not _num(v):
        return None
    if v < 30 or v > 250:
        return ("warn", "מגן קר של %s K חריג (טיפוסי 77-150 K). מגן חם מוסיף קרינת רקע ורעש." % _n(v), 77.0)
    return ("ok", "%s K." % _n(v))


def _check_cs_F(v, p):
    if not _num(v) or p.get("category") == "Thermal" and p.get("imager_type") == "uncooled" or             _det(p).get("cs_mode") != "fnumber":
        return None
    o = _opt(p)
    F = (o.get("f_mm") / o["D_mm"]) if o.get("aperture") == "circular" and o.get("D_mm") else o.get("F_general")
    if v <= 0:
        return ("warn", "ה-F של המגן הקר חייב להיות חיובי.")
    if F and v > F * 1.05:
        return ("warn", "ה-F של המגן הקר (F/%s) גדול מה-F של האופטיקה (F/%.2g): המגן חוסם חלק מהמפתח (ויגנטינג) - "
                        "אובדן אות. בדרך כלל מתאימים את F של העדשה ל-F של המגן." % (_n(v), F), round(F, 2))
    return ("ok", "F/%s מול F/%.2g של האופטיקה." % (_n(v), F) if F else "F/%s." % _n(v))


def _check_netd_F(v, p):
    if not _num(v):
        return None
    if v == 0:
        return ("ok", "0 = לא תועד. מומלץ להזין - NETD תלוי ב-F בריבוע.")
    o = _opt(p)
    F = (o.get("f_mm") / o["D_mm"]) if o.get("aperture") == "circular" and o.get("D_mm") else o.get("F_general")
    if F and abs(v - F) / F > 0.05:
        return ("warn", "ה-NETD נמדד ב-F/%s אבל העדשה בפרויקט F/%.2g. ה-NETD משתנה בערך כמו F²: בעדשה שלכם הוא "
                        "יהיה בערך פי %.2f. עדכנו את ה-NETD או ודאו שהוא נמדד עם העדשה הזו." % (_n(v), F, (F / v) ** 2))
    return ("ok", "תואם לעדשה (F/%.2g)." % F if F else "F/%s." % _n(v))


def _check_netd_tint(v, p):
    if not _num(v):
        return None
    if v == 0:
        return ("ok", "0 = לא תועד.")
    t = _det(p).get("tint_ms")
    if t and abs(v - t) / t > 0.2:
        return ("warn", "ה-NETD נמדד בזמן אינטגרציה %s ms ובתרחיש %s ms. הרעש יחסי בערך ל-1/√t, כך שה-NETD "
                        "בתרחיש שונה בערך פי %.2f." % (_n(v), _n(t), (v / t) ** 0.5))
    return ("ok", "תואם לתרחיש.")


def _check_netd_frames(v, p):
    if not _num(v):
        return None
    if v < 1:
        return ("warn", "לפחות פריים אחד.", 1)
    if v > 1:
        return ("warn", "NETD ממוצע על %s פריימים קטן פי √%s מה-NETD של פריים בודד. המודל מוסיף בעצמו אינטגרציה של "
                        "העין, כך שהרעש יופחת פעמיים והטווח יהיה אופטימי. השתמשו ב-NETD של פריים בודד." %
                (_n(v), _n(v)))
    return ("ok", "NETD של פריים בודד - נכון.")


def _check_noise_port(v, p):
    if v == "processed":
        return ("warn", "NETD שנמדד ביציאת הווידאו המעובדת כבר כולל סינון זמני. המודל יוסיף שוב אינטגרציה של פריימים "
                        "ושל העין - הרעש ייספר כקטן מדי והטווח אופטימי. העדיפו NETD מ-RAW או אחרי NUC.", "raw")
    return ("ok", "RAW / אחרי NUC - עקבי עם המודל.") if v else None


def _check_t_th(v, p):
    if not _num(v):
        return None
    fm = _frame_ms(p)
    if v <= 0:
        return ("warn", "קבוע הזמן חייב להיות חיובי.", 10.0)
    if v > 40:
        return ("warn", "קבוע זמן של %s ms איטי מאוד (טיפוסי 5-15 ms). הוא גורם למריחה בתנועה." % _n(v), 10.0)
    if fm and v > 2 * fm:
        return ("ok", "קבוע הזמן ארוך מפריים (%.1f ms): בתנועה תהיה מריחה (smear)." % fm)
    return ("ok", "%s ms." % _n(v))


def _check_eye_t(v, p):
    if not _num(v):
        return None
    if 1 < v <= 500:
        return ("warn", "זמן אינטגרציה של העין בשניות, לא באלפיות: %s נראה כמו %s ms." % (_n(v), _n(v)), v / 1000.0)
    return _range(0.02, 0.25, "s", "TRM4: 0.1 s")(v, p)


def _check_luminance(v, p):
    if not _num(v):
        return None
    if v <= 0:
        return ("warn", "בהירות התצוגה חייבת להיות חיובית.", 50.0)
    if v < 1:
        return ("warn", "תצוגה של %s cd/m² חשוכה מאוד: רגישות העין לניגוד יורדת ותצוגה חשוכה מקצרת את הטווח." %
                _n(v))
    return _range(1, 2000, "cd/m²", "מסך משרדי: 50-300")(v, p)


def _check_disp_pitch(v, p):
    if not _num(v):
        return None
    if v <= 0:
        return ("warn", "גודל הפיקסל חייב להיות חיובי.")
    if v > 2:
        return ("warn", "פיקסל תצוגה של %s mm - חריג. ייתכן שהוזן במיקרון או שזה גודל המסך." % _n(v))
    return ("ok", "%s mm (מסך 24\" FHD: 0.28 mm, מיקרו-תצוגה: 0.005-0.015 mm)." % _n(v))


def _check_eyepiece(v, p):
    if not _num(v):
        return None
    if v <= 0:
        return ("warn", "מוקד העינית חייב להיות חיובי.", 25.0)
    return _range(5, 80, "mm", "טיפוסי 15-30 mm")(v, p)


def _check_zoom(v, p):
    if not _num(v):
        return None
    if v < 1:
        return ("warn", "פקטור הגדלה לפחות 1.", 1)
    if v > 8:
        return ("warn", "זום אלקטרוני x%s - הוא מגדיל בלבד ולא מוסיף מידע. מעבר ל-x4 לרוב רק מגדיל את הפיקסלים." %
                _n(v))
    return ("ok", "x%s." % _n(v))


def _check_n_frames(v, p):
    if not _num(v):
        return None
    if v < 1:
        return ("warn", "לפחות פריים אחד.", 1)
    if v > 64:
        return ("warn", "מיצוע של %s פריימים מניח סצנה סטטית לגמרי: כל תנועה תטשטש. בתצפית חיה מקובל 2-8." % _n(v), 8)
    return ("ok", "הרעש הזמני יורד בערך פי √%s = %.2f (בסצנה סטטית)." % (_n(v), v ** 0.5))


def _check_iir(v, p):
    if not _num(v) or not p.get("dsp", {}).get("iir_on"):
        return None
    if v <= 0 or v > 1:
        return ("warn", "α חייב להיות בין 0 ל-1 (משקל הפריים החדש).", 0.25)
    return ("ok", "שקול לכ-%.1f פריימים ממוצעים." % ((2 - v) / v))


def _check_coef_axis(axis):
    def check(v, p):
        dsp = p.get("dsp", {})
        if not isinstance(v, (list, tuple)) or not v or not dsp.get("filter_on"):
            return None
        c = list(v) + [0.0] * 5
        if dsp.get(axis + "_type", "odd") == "odd":
            s = sum(c[:5])
            if abs(s) < 1e-12:
                return ("warn", "סכום המקדמים 0 - המסנן לא מוגדר (המודל מנרמל לפי הסכום).")
            m = (c[0] - c[1] + c[2] - c[3] + c[4]) / s
        else:
            s = sum(c[1:5])
            if abs(s) < 1e-12:
                return ("warn", "סכום המקדמים c1..c4 הוא 0 - המסנן הזוגי לא מוגדר.")
            m = 0.0
        if m < -0.05:
            return ("warn", "ה-MTF של המסנן בנייקוויסט שלילי (%.2f): היפוך ניגוד בפרטים העדינים - מסנן חידוד חזק "
                            "מדי." % m)
        if m > 1.05:
            return ("ok", "מסנן חידוד: ה-MTF בנייקוויסט x%.2f. נזקף לטווח רק עם Credit sharpening." % m)
        return ("ok", "מסנן החלקה: ה-MTF בנייקוויסט %.2f (המודל מנרמל לפי סכום המקדמים)." % m)
    return check


def _check_jitter_v(v, p):
    if not _num(v):
        return None
    ifov = _ifov_mrad(p)
    if v < 0:
        return ("warn", "ריצוד לא יכול להיות שלילי.", 0.0)
    if v >= 1 and ifov and v / ifov > 5:
        return ("warn", "%s mrad זה ריצוד עצום - נראה שהוזן ב-µrad בשדה של mrad." % _n(v), round(v / 1000.0, 4))
    if ifov and v / ifov > 1:
        return ("warn", "הריצוד (%s mrad) גדול מה-IFOV (%.3g mrad): התמונה תיטשטש מעל פיקסל והזיהוי יתקצר מאוד." %
                (_n(v), ifov))
    return ("ok", "ריצוד / IFOV = %.2f." % (v / ifov) if ifov else "%s mrad." % _n(v))


def _check_jitter_source(v, p):
    """Narrow IFOV without any line-of-sight jitter: the advice of the sensitivity study (NV-IPM practice)."""
    s = p.get("stab", {})
    ifov = _ifov_mrad(p)
    if not ifov or ifov >= 0.21 or s.get("neglect"):
        return ("ok", "IFOV של %.3g mrad - שדה רחב, הריצוד משפיע מעט." % ifov) if ifov else None
    no_jitter = s.get("jitter_mode") == "none" or s.get("jitter_mode", "model") == "model" and not s.get("random_on")
    if not no_jitter:
        return ("ok", "יש מודל ריצוד למערכת עם שדה צר (IFOV %.3g mrad)." % ifov)
    msg = ("IFOV של %.3g mrad (שדה צר) בלי שום ריצוד של קו הראייה - התחזית אופטימית, בעיקר בהכרה ובזיהוי: כל "
           "מערכת אמיתית רועדת. בלי מדידת ייצוב, הנוהג (NV-IPM) הוא 70 µrad rms." % ifov)
    if s.get("jitter_mode") == "none":
        return ("warn", msg, "model")
    return ("warn", msg, "nvipm70")


def _check_jitter_mode(v, p):
    r = _check_jitter_source(v, p)
    return r if v == "none" or not r or r[0] == "ok" else ("ok", "מקור התנועה: %s." % v)


def _check_jitter_preset(v, p):
    r = _check_jitter_source(v, p)
    return r if p.get("stab", {}).get("jitter_mode", "model") == "model" else None


def _check_lin(v, p):
    if not _num(v):
        return None
    ifov = _ifov_mrad(p)
    t = _det(p).get("tint_ms") or 0
    if ifov and t and v:
        smear = abs(v) * t / 1000.0 / ifov
        if smear > 1:
            return ("warn", "במהירות %s mrad/s ובזמן אינטגרציה %s ms התמונה זזה %.1f פיקסלים בכל חשיפה (smear). "
                            "זה מטשטש את הפרטים. קצרו את זמן האינטגרציה או שפרו את הייצוב." % (_n(v), _n(t), smear))
        return ("ok", "מריחה של %.2f פיקסל בחשיפה." % smear)
    return ("ok", "%s mrad/s." % _n(v))


def _check_sin(v, p):
    if not _num(v):
        return None
    ifov = _ifov_mrad(p)
    if v < 0:
        return ("warn", "משרעת לא יכולה להיות שלילית.", 0.0)
    if ifov and v > ifov:
        return ("warn", "משרעת הרטט (%s mrad) גדולה מה-IFOV (%.3g mrad) - טשטוש חזק." % (_n(v), ifov))
    return ("ok", "%s mrad." % _n(v))


def _check_emis(v, p):
    return _fraction("פליטות", "צבע / צמחייה: 0.85-0.97")(v, p)


def _check_angle(v, p):
    if not _num(v):
        return None
    if v < -90 or v > 90:
        return ("warn", "זווית צפייה חייבת להיות בין -90° ל-90°.")
    return ("ok", "%s° %s." % (_n(v), "כלפי מטה" if v > 0 else ("כלפי מעלה" if v < 0 else "אופקית")))


def _check_altitude(v, p):
    if not _num(v):
        return None
    if v < 0:
        return ("warn", "גובה יחסי שלילי פירושו שהמצלמה מתחת למטרה. בדקו.")
    if v > 20000:
        return ("warn", "גובה של %s מ' - בדקו שזה במטרים ולא ברגל." % _n(v))
    return ("ok", "%s מ' מעל המטרה." % _n(v))


def _check_pot(v, p):
    if not _num(v):
        return None
    if v <= 0:
        return ("warn", "מספר הפיקסלים על המטרה חייב להיות חיובי.")
    return _range(4, 2000, "פיקסלים", "גילוי ~60, הכרה ~250, זיהוי ~350")(v, p)


def _check_v50(v, p):
    if not _num(v):
        return None
    if v <= 0:
        return ("warn", "V50 חייב להיות חיובי.")
    return _range(0.5, 60, "cycles", "2.7 / 14.5 / 20.8")(v, p)


def _check_T_colour(v, p):
    if not _num(v):
        return None
    return _range(1500, 12000, "K", "שמש ~5800 K, נורת להט ~2850 K")(v, p)


def _check_E(unit):
    def check(v, p):
        if not _num(v):
            return None
        if v <= 0:
            return ("warn", "עוצמת ההארה חייבת להיות חיובית - בלי הארה אין אות בחיישן מחזיר.")
        return ("ok", "%s %s." % (_n(v), unit))
    return check


def _check_lambda_mono(v, p):
    if not _num(v):
        return None
    if v > 100:
        return ("warn", "אורך הגל במיקרון, לא בננומטר: %s nm = %s µm." % (_n(v), _n(v / 1000.0)), v / 1000.0)
    return _range(0.3, 14, "µm", "לייזר NIR: 0.808-1.064 µm, SWIR: 1.55 µm")(v, p)


def _check_beta(v, p):
    if not _num(v):
        return None
    if abs(v) > 90:
        return ("warn", "זווית של יותר מ-90°: המקור מאחורי חזית המטרה - החזית בצל.")
    return ("ok", "%s°." % _n(v))


def _check_tau0(v, p):
    if not _num(v):
        return None
    return _fraction("העברה התחלתית", "בדרך כלל 1", allow_zero=False)(v, p)


def _check_F_PR(v, p):
    if not _num(v):
        return None
    if v < 0:
        return ("warn", "מקדם קרינת נתיב לא יכול להיות שלילי.", 0.0)
    if v > 1:
        return ("warn", "מקדם קרינת נתיב מעל 1 חריג (טיפוסי 0.05-0.3). קרינת נתיב גבוהה מורידה את הניגוד בטווח.",
                0.15)
    return ("ok", "%s." % _n(v))


def _check_rh(v, p):
    if not _num(v):
        return None
    if v < 0 or v > 100:
        return ("warn", "לחות יחסית היא אחוז בין 0 ל-100.")
    if 0 < v <= 1:
        return ("warn", "נראה שהלחות הוזנה כשבר (%s). היחידה היא אחוזים." % _n(v), v * 100)
    return ("ok", "%s%%." % _n(v))


def _check_wind(v, p):
    if not _num(v):
        return None
    if v < 0:
        return ("warn", "מהירות רוח לא יכולה להיות שלילית.", 0.0)
    if v > 30:
        return ("warn", "רוח של %s m/s (%.0f קמ\"ש) חריגה - ייתכן שהוזן בקמ\"ש." % (_n(v), v * 3.6),
                round(v / 3.6, 2))
    return ("ok", "%s m/s." % _n(v))


def _check_r0(v, p):
    if not _num(v):
        return None
    if v <= 0:
        return ("warn", "r0 חייב להיות חיובי.")
    if v > 100:
        return ("warn", "r0 של %s cm - חריג (טיפוסי 1-20 cm בנתיב קרקעי). ייתכן שהוזן במ\"מ." % _n(v),
                round(v / 10.0, 3))
    D = (_opt(p).get("D_mm") or 0) / 10.0
    if D:
        return ("ok", "D / r0 = %.1f (%s)." % (D / v, "טורבולנציה חלשה למפתח הזה" if D / v < 1 else
                                              ("בינונית" if D / v < 4 else "חזקה - טשטוש משמעותי")))
    return ("ok", "%s cm." % _n(v))


def _check_mitig(v, p):
    if not _num(v):
        return None
    if v < 1:
        return ("warn", "גבר r0 קטן מ-1 פירושו שהעיבוד מחמיר את הטורבולנציה. 1 = ללא עיבוד.", 1.0)
    if v > 5:
        return ("warn", "גבר של x%s - אופטימי מאוד. מערכות שפורסמו מדווחות על שיפור של 10%%-25%% בטווח ההכרה "
                        "(גבר 2-4)." % _n(v), 3.0)
    return ("ok", "x%s." % _n(v))


def _check_cn2_calib(v, p):
    if not _num(v):
        return None
    if v <= 0:
        return ("warn", "מקדם הכיול חייב להיות חיובי.", 1.0)
    if v > 20 or v < 0.05:
        return ("warn", "מקדם כיול של %s - הפרש של יותר מעשור בין המדידה לתחזית. בדקו את המדידה." % _n(v))
    return ("ok", "x%s." % _n(v))


def _check_ref_range(v, p):
    if not _num(v):
        return None
    if v < 0:
        return ("warn", "טווח הייחוס לא יכול להיות שלילי.", 0.0)
    if v > 100:
        return ("warn", "טווח ייחוס של %s ק\"מ - ייתכן שהוזן במטרים." % _n(v), v / 1000.0)
    return ("ok", "%s ק\"מ%s." % (_n(v), " (במצלמה)" if v == 0 else ""))


def _check_fov(axis):
    def check(v, p):
        if not _num(v):
            return None
        if v == 0:
            return ("ok", "0 = לא הוזן FOV מדוד.")
        if v <= 0 or v > 180:
            return ("warn", "שדה ראייה חייב להיות בין 0 ל-180°.")
        d, f = _det(p), _opt(p).get("f_mm") or 0
        n, pitch = d.get("n_" + axis) or 0, d.get("pitch_%s_um" % axis) or 0
        if f and n and pitch:
            import math
            calc = math.degrees(2 * math.atan(n * pitch / 2000.0 / f))
            if abs(v - calc) / calc > 0.05:
                return ("warn", "ה-FOV הנמדד (%s°) שונה ב-%.0f%% מהמחושב (%.2f°). אחד מהנתונים f, הפסיעה או מספר "
                                "הפיקסלים לא נכון - וזה משנה את ה-IFOV ואת הטווח." % (_n(v), 100 * abs(v - calc) / calc,
                                                                                     calc))
            return ("ok", "תואם למחושב (%.2f°)." % calc)
        return ("ok", "%s°." % _n(v))
    return check


def _check_bin(v, p):
    if not _num(v):
        return None
    if v < 1:
        return ("warn", "לפחות 1 (ללא איחוד).", 1)
    if v > 1:
        return ("ok", "איחוד x%s: אות טוב יותר, אבל הפיקסל האפקטיבי גדל פי %s - ה-IFOV גדל והזיהוי יתקצר במערכת "
                      "מוגבלת-דגימה." % (_n(v), _n(v)))
    return ("ok", "ללא איחוד.")


def _check_xtalk(v, p):
    if not _num(v):
        return None
    if v < 0 or v > 1:
        return ("warn", "MTF בנייקוויסט הוא בין 0 ל-1 (0 = כבוי).", 0.0)
    if 0 < v < 0.5:
        return ("warn", "MTF של %s בנייקוויסט בגלל זליגה - נמוך מאוד; זליגה כזו מטשטשת את הפרטים העדינים." % _n(v))
    return ("ok", "%s." % ("כבוי" if v == 0 else _n(v)))


def _check_cte(v, p):
    if not _num(v):
        return None
    if v <= 0 or v > 1:
        return ("warn", "יעילות העברה היא שבר קרוב ל-1 (למשל 0.99999).", 0.99999)
    if v < 0.999:
        return ("warn", "CTE של %s נמוך מאוד: אחרי אלפי העברות המטען נמרח וה-MTF קורס." % _n(v))
    return ("ok", "%s." % _n(v))


def _check_rel_illum(v, p):
    return _fraction("תאורה יחסית בשולי השדה", "1 = ללא נפילה", allow_zero=False)(v, p)


def _check_comp_blur(v, p):
    if not _num(v):
        return None
    if v < 0:
        return ("warn", "לא יכול להיות שלילי.", 0.0)
    if v > 2:
        return ("warn", "טשטוש של %s פיקסל rms מדחיסה - חריג (קודק סביר: 0.2-0.7). זה כמעט חוצה את הרזולוציה." %
                _n(v))
    return ("ok", "%s." % ("לא ממודל" if v == 0 else "σ = %s פיקסל" % _n(v)))


def _check_tone_bits(v, p):
    if not _num(v):
        return None
    return _range(6, 16, "bit", "וידאו רגיל: 8")(v, p)


def _check_tone_span(v, p):
    if not _num(v):
        return None
    if v <= 0:
        return ("warn", "טווח ה-AGC חייב להיות חיובי.", 20.0)
    bits = p.get("dsp", {}).get("tone_bits") or 8
    q = v / 2 ** bits / 12 ** 0.5 * 1000
    netd = _det(p).get("netd_mK") or 0
    if netd and q > netd:
        return ("warn", "טווח AGC של %s K על %s ביטים נותן רעש עיגול של %.0f mK - יותר מה-NETD (%s mK). הניגודים "
                        "הקטנים נבלעים במדרגות. צמצמו את הטווח או הגדילו את מספר הביטים." % (_n(v), _n(bits), q,
                                                                                         _n(netd)))
    return ("ok", "רעש עיגול %.0f mK." % q)


def _check_snr_req(v, p):
    if not _num(v):
        return None
    if v == 0:
        return ("ok", "0 = לא נבדק.")
    return _range(1, 100, "", None)(v, p)


def _check_fill_limit(v, p):
    if not _num(v):
        return None
    if v <= 0 or v > 100:
        return ("warn", "אחוז בין 0 ל-100.", 70.0)
    return ("ok", "%s%%." % _n(v))


def _check_algo_cnr(v, p):
    if not _num(v):
        return None
    if v <= 0:
        return ("warn", "CNR חייב להיות חיובי.", 3.0)
    return _range(1, 20, "", "הנחה כללית: 3")(v, p)


def _check_h_ref(v, p):
    if not _num(v):
        return None
    if v <= 0:
        return ("warn", "גובה הייחוס חייב להיות חיובי.", 2.0)
    if v > 500:
        return ("warn", "Cn² בגובה %s מ' - בדקו שזה הגובה שבו נמדד הערך (טבלה C.2: 2 מ')." % _n(v))
    return ("ok", "%s מ'." % _n(v))


def _check_L0(v, p):
    if not _num(v):
        return None
    if v < 0:
        return ("warn", "לא יכול להיות שלילי.", 0.0)
    if 0 < v < 0.5:
        return ("warn", "סקאלה חיצונית של %s מ' קטנה מאוד (ליד הקרקע: 1-100 מ'); היא מחלישה את הטורבולנציה "
                        "באופן מלאכותי." % _n(v))
    return ("ok", "%s." % ("קולמוגורוב (אינסופי)" if v == 0 else "%s מ'" % _n(v)))


def _check_wx_T(v, p):
    c = _kelvin(250, 330, "טמפרטורת האוויר")(v, p)
    if c and c[0] == "ok" and _num(v) and not 282 <= v <= 308:
        return ("warn", "%.0f °C מחוץ לתחום ההתאמה של הרגרסיה (9-35 °C): ה-Cn² מוקצן ולא אמין." % (v - 273.15))
    return c


def _check_wx_W(v, p):
    if not _num(v):
        return None
    if v < 0 or v > 1.2:
        return ("warn", "משקל השעה W הוא בערך 0-1 (0.1 בלילה, 1 בצהריים).")
    return ("ok", "W = %s." % _n(v))


def _check_spec_L(v, p):
    if not _num(v):
        return None
    if v <= 0:
        return ("warn", "אורך הנתיב חייב להיות חיובי.")
    if v > 200:
        return ("warn", "%s ק\"מ - ייתכן שהוזן במטרים." % _n(v), v / 1000.0)
    return ("ok", "%s ק\"מ." % _n(v))


def _check_meas_netd(v, p):
    if not _num(v):
        return None
    if v == 0:
        return ("ok", "0 = אין השוואה.")
    if 0 < v < 1:
        return ("warn", "נראה שה-NETD הוזן ב-K: %s K = %s mK." % (_n(v), _n(v * 1000)), v * 1000)
    return _range(5, 200, "mK")(v, p)


def _check_ms_steps(v, p):
    if not _num(v):
        return None
    if v < 1 or v > 4:
        return ("warn", "מקובל 2 צעדים (חצי פיקסל). יותר מ-4 נדיר.", 2)
    return ("ok", "%s צעדים." % _n(v))


def _check_readout_ms(v, p):
    if not _num(v):
        return None
    fm = _frame_ms(p)
    if v < 0:
        return ("warn", "לא יכול להיות שלילי.", 0.0)
    if fm and v > fm:
        return ("warn", "זמן הקריאה (%s ms) ארוך מזמן הפריים (%.2f ms) - לא אפשרי בקצב הזה." % (_n(v), fm))
    return ("ok", "%s ms." % _n(v))


def _check_exp(which):
    def check(v, p):
        if not _num(v):
            return None
        if v < 0:
            return ("warn", "לא יכול להיות שלילי.", 0.0)
        if v == 0:
            return ("ok", "0 = לא צוין.")
        t = _det(p).get("tint_ms") or 0
        if which == "min" and t and t < v:
            return ("warn", "זמן האינטגרציה בתרחיש (%s ms) קצר מהמינימום שהמצלמה תומכת בו (%s ms)." % (_n(t), _n(v)))
        if which == "max" and t and t > v:
            return ("warn", "זמן האינטגרציה בתרחיש (%s ms) ארוך מהמקסימום של המצלמה (%s ms) - אי אפשר להגיע לאות "
                            "הזה בפועל." % (_n(t), _n(v)))
        return ("ok", "%s ms." % _n(v))
    return check


def _check_smear(v, p):
    if not _num(v):
        return None
    if v <= 0:
        return ("warn", "חייב להיות חיובי.", 0.5)
    if v > 2:
        return ("warn", "מריחה של %s פיקסלים בחשיפה מטשטשת את הפרטים העדינים (מקובל 0.3-1)." % _n(v), 0.5)
    return ("ok", "%s פיקסל." % _n(v))


def _check_bright_refl(v, p):
    return _fraction("ההחזרות הבהירה ביותר", "שלג / בטון: 0.6-0.9")(v, p)


def _check_aberr(v, p):
    if v == "none" and p.get("optics", {}).get("mtf_source", "model") == "model":
        return ("ok", "'none' מניח עדשה מושלמת (מוגבלת-עקיפה), כמו ב-TRM4. עדשה אמיתית גרועה מזה, כך שההכרה "
                      "והזיהוי אופטימיים מעט. אם יש נתוני MTF או ידוע שהעדשה בינונית - בחרו q (1.3 לעדשה טובה).")
    return ("ok", "מודל סטיות: %s." % v) if v else None


def _check_obs_algo(v, p):
    if v == "algorithm" and not p.get("display", {}).get("algo_calib"):
        return ("warn", "צופה אלגוריתמי בלי סט כיול: הקריטריונים של TRM4 כוילו לבני אדם, כך שהטווח הוא הערכה לא "
                        "מכוילת - לרוב ארוך בהרבה מזה של צופה אנושי.")
    return ("ok", "צופה: %s." % v) if v else None


def _check_credit(v, p):
    if v is True:
        return ("warn", "חידוד מוגבר נזקף לזכות הטווח. חידוד לא מוסיף מידע ומגביר רעש; בלי כיול זה עלול לנפח את "
                        "הטווח.", False)
    return ("ok", "החידוד לא נזקף לטווח (שמרני).") if v is False else None


def _check_neglect_stab(v, p):
    if v is True:
        return ("warn", "התעלמות מהייצוב מניחה פלטפורמה יציבה לגמרי. במערכת עם שדה צר זה אופטימי מאוד.", False)
    return ("ok", "תנועת קו הראייה ממודלת.") if v is False else None


def _check_neglect_eye(v, p):
    if v is True and p.get("mode", {}).get("environment") == "field":
        return ("warn", "התעלמות מה-MTF של העין במצב שדה מניחה עין מושלמת - הטווח יהיה אופטימי. זו אפשרות למעבדה.",
                False)
    return ("ok", "ה-MTF של העין נכלל.") if v is False else None


def _check_turb_thermal(v, p):
    return ("ok", "טורבולנציה פעילה גם בתרמי (הרחבה). רלוונטי בנתיב קרקעי ארוך ביום חם." if v else
            "כמו TRM4: ללא טורבולנציה בתרמי.") if isinstance(v, bool) else None


def _check_exposure(v, p):
    if v == "long" and p.get("mode", {}).get("stream") == "video":
        return ("ok", "חשיפה ארוכה כוללת את נדידת התמונה - שמרני. לצופה וידאו 'time' מדויק יותר.")
    return ("ok", "סוג MTF: %s." % v) if v else None


def _check_atm_mode(v, p):
    if v == "visibility" and p.get("category") == "Thermal":
        return ("warn", "טווח ראות אינו מקדם הנחתה תקף באינפרא-אדום. בתרמי השתמשו ב-extinction או ב-weather.",
                "extinction")
    return ("ok", "העברה דרך: %s." % v) if v else None


def _check_interlace(v, p):
    if v in ("electronic", "pseudo"):
        return ("warn", "שזירה (interlace) רלוונטית רק למצלמות וידאו אנלוגיות ישנות. מצלמה דיגיטלית מודרנית היא "
                        "progressive; שזירה מורידה את הדגימה האנכית.", "progressive")
    return ("ok", "progressive - נכון למצלמה דיגיטלית.") if v else None


def _check_clutter_model(v, p):
    if v is True and p.get("target", {}).get("clutter") in (None, "not_specified"):
        return ("warn", "מודל העומס פעיל אבל רמת העומס לא צוינה - הוא לא ישפיע. בחרו רמת עומס.")
    return None


# ---------------------------------------------------------------------------------------------
# entries
# ---------------------------------------------------------------------------------------------
def K(title, what, why, impact, note="", typical=(), source="", mistakes=(), check=None):
    e = {"title": title, "what": what, "why": why, "impact": impact, "impact_note": note, "typical": list(typical),
         "source": source or "דף הנתונים / הגדרות המערכת.", "mistakes": list(mistakes)}
    if check:
        e["check"] = check
    return e


def DOC(title, what):
    """Documentation-only field (traceability): not used in the calculation."""
    return K(title, what, "שדה תיעוד: נכנס לדוח ומאפשר לשחזר ולבקר את הנתונים. הוא לא משנה את הטווח - אבל בלעדיו "
                          "הדוח מסמן את הנתון כהנחה.", 0, "תיעוד בלבד",
             source="רישום המדידה / מקור הנתונים.")


MORE = {
    # ------------------------------------------------------------------ General
    "name": K("שם הפרויקט", "שם חופשי שמופיע בכותרת החלון ובדוחות.", "לא משתתף בחישוב. שם ברור עוזר לזהות את "
              "התרחיש בדוח ובהשוואת תרחישים.", 0, "תיעוד בלבד", ["שם המצלמה + העדשה + התרחיש, למשל 'XYZ-640 NFOV, "
              "קיץ, נגב'."], "בחירה שלכם."),
    "mode.ref_range_km": K("טווח ייחוס", "הטווח שבו נקבעים הגדלים התלויים-טווח בתחום הנראה / General: גרפי ה-MTF של "
                           "האטמוספרה והטורבולנציה, משקלי האות, זמן האינטגרציה ומילוי הבאר.", "משפיע גם על הטווחים, "
                           "לא רק על הגרפים: מצב האות (זמן אינטגרציה, מילוי באר) מחושב בטווח הזה. מומלץ טווח קרוב "
                           "לטווח ההכרה הצפוי.", 1, "משני; משפיע על מצב האות", ["0 = במצלמה.", "קרוב לטווח ההכרה: "
                           "2-5 ק\"מ."], "טווח העבודה הצפוי.", ["להזין במטרים."], _check_ref_range),
    "mode.niirs": K("חישוב NIIRS", "מחשב גם את דירוג איכות התמונה NIIRS (GIQE 5) כתלות בטווח.", "נותן מדד איכות תמונה "
                    "סטנדרטי לצילום אווירי / מודיעין. לא משנה את טווחי ה-DRI.", 0, "מדד איכות תמונה, לא טווח",
                    ["צילום אווירי / מודיעין תמונה: להפעיל."], "מטרת הניתוח."),

    # ------------------------------------------------------------------ Basic imager
    "basic.fov_mode": K("שדה ראייה: חישוב או מדידה", "Calculate: ה-FOV מחושב מהפיקסלים, הפסיעה והמוקד. Measured: "
                        "מזינים FOV מדוד לבדיקה צולבת בלבד.", "בדיקה צולבת היא דרך טובה לגלות מוקד או פסיעה שגויים - "
                        "שהם בדיוק מה שקובע את ה-IFOV ואת הטווח.", 0, "בדיקה צולבת",
                        ["יש FOV בדף הנתונים: Measured, כדי לבדוק את הנתונים."], "דף הנתונים של המצלמה."),
    "basic.fov_h_deg": K("FOV אופקי מדוד", "שדה הראייה האופקי לפי דף הנתונים או מדידה, במעלות.", "לא משתתף בחישוב. "
                         "המדריך משווה אותו ל-FOV המחושב: הפרש מעל 5% מצביע על שגיאה במוקד, בפסיעה או במספר הפיקסלים.",
                         0, "בדיקה צולבת", source="דף הנתונים של המצלמה.", check=_check_fov("h")),
    "basic.fov_v_deg": K("FOV אנכי מדוד", "שדה הראייה האנכי לפי דף הנתונים או מדידה.", "בדיקה צולבת בלבד, כמו ה-FOV "
                         "האופקי.", 0, "בדיקה צולבת", source="דף הנתונים של המצלמה.", check=_check_fov("v")),
    "basic.microscan": K("מיקרו-סריקה (dither)", "הזזת התמונה בתת-פיקסל בין פריימים, כדי להכפיל את הדגימה.",
                         "מכפילה את תדר הדגימה ומקטינה התחזות (aliasing). במערכת מוגבלת-דגימה (Fλ/d < 1) זה יכול "
                         "להאריך את ההכרה והזיהוי משמעותית. המחיר: קצב פריימים אפקטיבי נמוך יותר.", 2,
                         "חשוב במערכות מוגבלות-דגימה", ["רוב המצלמות: none.", "מצלמות עם dither (חלק מה-LWIR "
                         "המקוררות): diagonal / rectangular."], "דף הנתונים (microscan / dither).",
                         ["להפעיל מיקרו-סריקה במצלמה שאין לה."]),
    "basic.ms_steps_h": K("צעדי מיקרו-סריקה אופקיים", "מספר מיקומי הסריקה בכיוון האופקי (תבנית מלבנית).", "2 צעדים = "
                          "דגימה כפולה. יותר צעדים מוסיפים מעט ומורידים את הקצב.", 1, "דרך הדגימה",
                          ["2."], "דף הנתונים.", check=_check_ms_steps),
    "basic.ms_steps_v": K("צעדי מיקרו-סריקה אנכיים", "מספר מיקומי הסריקה בכיוון האנכי.", "כמו הצעדים האופקיים.", 1,
                          "דרך הדגימה", ["2."], "דף הנתונים.", check=_check_ms_steps),
    "basic.integ_during_move": K("אינטגרציה בזמן תנועה", "הגלאי אוסף אור בזמן שסורק המיקרו-סריקה זז.", "מוסיף MTF של "
                                 "מריחה - מעט טשטוש.", 1, "טשטוש קטן", source="דף הנתונים / יצרן."),
    "basic.bin_h": K("איחוד פיקסלים אופקי (binning)", "מספר פיקסלים סמוכים שמסוכמים לפיקסל אחד בכיוון האופקי.",
                     "משפר יחס אות-לרעש (חשוב בלילה), אבל מגדיל את הפיקסל האפקטיבי: ה-IFOV גדל פי מספר האיחוד, "
                     "והזיהוי יתקצר במערכת מוגבלת-דגימה. ביום כמעט תמיד מזיק.", 2, "פשרה: רעש מול רזולוציה",
                     ["1 = ללא איחוד.", "SWIR / לילה: 2."], "מצב העבודה של המצלמה.", check=_check_bin),
    "basic.bin_v": K("איחוד פיקסלים אנכי", "מספר פיקסלים סמוכים שמסוכמים בכיוון האנכי.", "כמו האיחוד האופקי.", 2,
                     "פשרה: רעש מול רזולוציה", ["1 = ללא איחוד."], "מצב העבודה של המצלמה.", check=_check_bin),
    "basic.n_sensors": K("מספר חיישנים זהים", "כמה חיישנים זהים שהתמונות שלהם משולבות.", "שני חיישנים מורידים את הרעש "
                         "הזמני פי √2 בערך. משפיע רק במערכת מוגבלת-רעש.", 1, "רק במוגבלת-רעש", ["1."], "תצורת המערכת."),
    "basic.bin_kind": K("סוג האיחוד", "Charge: המטען מסוכם לפני קריאה אחת (רעש קריאה פעם אחת). Digital: סכום של n "
                        "קריאות (רעש הקריאה נוסף n פעמים).", "באיחוד דיגיטלי הרווח ביחס אות-לרעש קטן יותר. חשוב בלילה.",
                        1, "רק כשיש איחוד", ["CCD: charge.", "CMOS: לרוב digital."], "דף הנתונים של החיישן."),
    "basic.readout": K("אופן הקריאה (shutter)", "Global: כל השורות נחשפות יחד. Rolling: השורות מתחילות בזו אחר זו.",
                       "ב-rolling shutter עם תנועה התמונה מתעוותת (שבירה גאומטרית). זה מדווח, אבל לא משנה את הטווח.",
                       0, "מדווח, לא משנה טווח", ["מצלמות IR: global.", "CMOS זולות: rolling."], "דף הנתונים."),
    "basic.exp_overlap": K("חפיפת חשיפה וקריאה", "האם החשיפה של פריים יכולה לרוץ בזמן קריאת הפריים הקודם.", "קובע את "
                           "זמן החשיפה המקסימלי בתקציב החשיפה. לא משנה את הטווח ישירות.", 0, "תקציב חשיפה",
                           source="דף הנתונים / מדריך החיישן."),
    "basic.readout_ms": K("זמן קריאת פריים", "הזמן מהשורה הראשונה לאחרונה בקריאת rolling shutter.", "קובע את עיוות "
                          "ה-rolling shutter ואת זמן החשיפה המקסימלי.", 0, "תקציב חשיפה", source="דף הנתונים.",
                          check=_check_readout_ms),
    "basic.guard_ms": K("זמן מת לפריים", "זמן בכל פריים שלא ניתן לחשיפה (טריגר, איפוס).", "מקטין את זמן החשיפה "
                        "המקסימלי בתקציב החשיפה.", 0, "תקציב חשיפה", source="דף הנתונים.",
                        check=_nonneg("זמן מת", "ms")),
    "basic.exp_min_ms": K("חשיפה מינימלית", "זמן החשיפה הקצר ביותר שהמצלמה תומכת בו.", "התקציב מסמן זמן אינטגרציה "
                          "קצר ממנו - ביום בהיר זה מצב של רוויה.", 0, "תקציב חשיפה", source="דף הנתונים.",
                          check=_check_exp("min")),
    "basic.exp_max_ms": K("חשיפה מקסימלית", "זמן החשיפה הארוך ביותר שהמצלמה תומכת בו.", "התקציב מסמן זמן אינטגרציה "
                          "ארוך ממנו. בלילה זה מגביל את האות בפועל.", 0, "תקציב חשיפה", source="דף הנתונים.",
                          check=_check_exp("max")),
    "basic.interlace": K("שזירה (interlace)", "אופן קריאת השורות בווידאו אנלוגי ישן.", "שזירה משנה את הדגימה האנכית. "
                         "מצלמות דיגיטליות מודרניות הן progressive.", 1, "רק במצלמות ישנות", ["progressive."],
                         "דף הנתונים.", check=_check_interlace),

    # ------------------------------------------------------------------ Optics
    "optics.D_obsc_mm": K("הסתרה מרכזית", "קוטר ההסתרה במרכז המפתח - למשל המראה המשנית בטלסקופ מחזיר.", "מקטינה את "
                          "האות לפי יחס השטחים, ומחלישה את ה-MTF בתדרים בינוניים (פרטים בגודל בינוני) - בעיקר ההכרה.",
                          1, "רק בטלסקופ מחזיר", ["עדשה רגילה: 0.", "קסגרן: 25%-40% מהקוטר."],
                          "שרטוט האופטיקה.", ["להזין את שטח ההסתרה במקום הקוטר."], _check_obsc),
    "optics.W_trunc_h_mm": K("רוחב מפתח קטום", "רוחב המפתח כשהוא חתוך בכיוון האופקי (0 = לא קטום).", "מפתח צר יותר "
                             "בכיוון אחד מגדיל את העקיפה באותו כיוון ומקטין את האות.", 1, "מקרה מיוחד", ["0."],
                             "שרטוט האופטיקה.", check=_nonneg("רוחב", "mm")),
    "optics.W_trunc_v_mm": K("גובה מפתח קטום", "גובה המפתח כשהוא חתוך בכיוון האנכי (0 = לא קטום).", "כמו הרוחב "
                             "הקטום, בכיוון האנכי.", 1, "מקרה מיוחד", ["0."], "שרטוט האופטיקה.",
                             check=_nonneg("גובה", "mm")),
    "optics.diff_focal": K("מוקד אנכי שונה", "אופטיקה אנמורפית: מוקד אחר בכיוון האנכי.", "נדיר. משנה את ה-IFOV האנכי.",
                           1, "נדיר", ["לא מסומן."], "שרטוט האופטיקה."),
    "optics.f_v_mm": K("מוקד אנכי", "אורך המוקד בכיוון האנכי באופטיקה אנמורפית.", "קובע את ה-IFOV האנכי, ולכן את "
                       "הממד האנכי של הדגימה.", 2, "רק באנמורפית", source="שרטוט האופטיקה.", check=_check_f_v),
    "optics.F_spec": K("F-number של היצרן", "ה-F שכתוב בדף הנתונים - לבדיקה צולבת בלבד.", "לא משתתף בחישוב. אם הוא "
                       "שונה ביותר מ-5% מ-f/D, כנראה הקוטר או המוקד שהוזנו לא נכונים.", 0, "בדיקה צולבת",
                       source="דף הנתונים של העדשה.", check=_check_F_spec),
    "optics.mtf_source": K("מקור ה-MTF האופטי", "Model: מחושב מהמפתח ומודל סטיות. Zemax / Measured: עקומת MTF מיובאת. "
                           "Device: MTF מדוד של המצלמה כולה (קצה-לקצה).", "MTF אמיתי של העדשה מדויק יותר ממודל - "
                           "במיוחד לזיהוי, שתלוי בתדרים הגבוהים.", 2, "חשוב לזיהוי",
                           ["אין נתונים: Model עם q.", "יש ייצוא Zemax: Zemax.", "יש מדידת MTF: Measured."],
                           "מעצב האופטיקה / מדידת MTF.",
                           ["לייבא MTF של מצלמה שלמה כ-Measured lens - ה-MTF של הגלאי ייספר פעמיים."]),
    "optics.zemax_mtf": K("קובץ MTF", "טבלת MTF מ-Zemax או ממדידה: תדר ועמודות T/S (או h/v).", "מחליפה את מודל "
                          "האופטיקה. קובץ ביחידות שגויות או ב-field לא נכון משנה מאוד את הזיהוי.", 2, "חשוב לזיהוי",
                          source="ייצוא FFT / Huygens MTF מ-Zemax, או מדידה."),
    "optics.zemax_mtf_unit": K("יחידת התדר בקובץ", "cycles/mm למערכת עם מוקד, cycles/mrad למערכת אפוקלית.", "יחידה "
                               "שגויה מזיזה את כל העקומה פי f/1000 - שגיאה גסה בזיהוי.", 2, "שגיאה גסה אם טועים",
                               ["auto."], "כותרת הקובץ."),
    "optics.zemax_mtf_field": K("שדה (field) בקובץ", "איזו נקודת שדה מהייצוא (1 = בדרך כלל על הציר).", "ה-MTF בשולי "
                                "השדה נמוך יותר. לחיזוי טווח משתמשים במרכז.", 1, "מרכז השדה", ["1."], "הגדרות הייצוא.",
                                check=_positive_int("מספר השדה")),
    "optics.zemax_mtf_h": K("איזו עקומה אופקית", "האם העקומה האופקית היא sagittal או tangential.", "על הציר הן כמעט "
                            "זהות; בשולי השדה הן שונות.", 1, "משני", ["sagittal."], "הגדרות הייצוא."),
    "optics.mtf_incl_diffraction": K("הנתונים כוללים עקיפה", "האם העקומה המיובאת כבר כוללת עקיפה.", "אם מסמנים לא "
                                     "נכון, העקיפה נספרת פעמיים (טווח קצר מדי) או לא נספרת (ארוך מדי).", 2,
                                     "ספירה כפולה", ["FFT MTF של Zemax ומדידות: כוללים."], "מקור הנתונים."),
    "optics.mtf_incl_detector": K("הנתונים כוללים את הגלאי", "האם המדידה נעשתה דרך מצלמה (כולל צמצם הפיקסל).",
                                  "אם כן ולא מסמנים, ה-MTF של הגלאי נספר פעמיים והזיהוי מתקצר.", 2, "ספירה כפולה",
                                  source="מקור הנתונים."),
    "optics.mtf_incl_motion": K("הנתונים כוללים תנועה", "האם המדידה כבר כוללת את תנועת קו הראייה (למשל נמדדה על "
                                "הפלטפורמה).", "אם כן, נתוני הייצוב מתעלמים. אחרת התנועה נספרת פעמיים.", 1, "ספירה כפולה",
                                source="מקור הנתונים."),
    "optics.diffraction": K("חישוב העקיפה", "Spectral: ממוצע על התחום הספקטרלי (מדויק). Single: באורך גל אחד (מהיר).",
                            "בתחום רחב (LWIR 8-12 µm) ההבדל יכול להיות כמה אחוזים בטווח.", 1, "מדויק מול מהיר",
                            ["spectral."], "ברירת המחדל."),
    "optics.lambda_diff_um": K("אורך גל לעקיפה", "אורך הגל לחישוב העקיפה ב-Single (0 = ממוצע התחום).", "אורך גל מחוץ "
                               "לתחום נותן עקיפה שגויה. 0 הוא הבחירה הנכונה כמעט תמיד.", 1, "השאירו 0",
                               ["0."], "ממוצע התחום.", ["להזין 10 µm במצלמה נראית."], _check_lambda_diff),
    "optics.aberration": K("מודל סטיות העדשה", "None: עדשה מושלמת (מוגבלת-עקיפה). q: יחס טשטוש לעקיפה. Blur: כתם "
                           "גאוסי.", "עדשה אמיתית אף פעם לא מושלמת. 'none' נותן תחזית אופטימית, בעיקר בזיהוי. "
                           "q = 1.3 הוא הנחה סבירה לעדשה טובה.", 2, "אופטימי אם none",
                           ["עדשה טובה: q = 1.2-1.5.", "יש מדידת כתם: blur."], "מעצב האופטיקה / מדידה.",
                           check=_check_aberr),
    "optics.q": K("פרמטר סטיות q", "יחס בין הטשטוש האמיתי לטשטוש העקיפה (1 = מושלם).", "q גדול מטשטש את הפרטים "
                  "העדינים: משפיע בעיקר על הזיהוי. במערכת מוגבלת-עקיפה ההשפעה גבוהה.", 2, "בעיקר על זיהוי",
                  ["עדשה איכותית: 1.1-1.3.", "עדשה זולה / זום: 1.5-2.5."], "מעצב האופטיקה, או התאמה למדידת MTF.",
                  check=_check_q),
    "optics.blur_um": K("כתם טשטוש גאוסי", "סטיית התקן של כתם הטשטוש במישור המוקד, במיקרון.", "כתם גדול מחצי פיקסל "
                        "מוריד את ה-MTF בנייקוויסט ומקצר את הזיהוי.", 2, "בעיקר על זיהוי",
                        ["0.2-0.5 פיקסל לעדשה טובה."], "ניתוח Spot diagram / מדידה.", ["להזין את הקוטר במקום σ."],
                        _check_blur),
    "optics.tau_mode": K("העברת האופטיקה: ערך או קובץ", "ערך אחד, או עקומת העברה לפי אורך גל מ-Zemax.", "עקומה "
                         "ספקטרלית מדויקת יותר כשההעברה משתנה בתחום.", 1, "דיוק", ["value."], "מעצב האופטיקה."),
    "optics.zemax_tau": K("קובץ העברה", "העברה כפונקציה של אורך הגל.", "מחליף את הערך הבודד.", 1, "דיוק",
                          source="ייצוא Zemax / מדידה."),
    "optics.tau_kind": K("סוג ערכי ההעברה", "Absolute: ההעברה האמיתית. Normalized: הצורה מנורמלת לשיא שהוזן.",
                         "בחירה שגויה משנה את עוצמת האות.", 1, "רמת האות", source="מקור הקובץ."),
    "optics.tau_scope": K("מה הקובץ כולל", "האם העקומה כוללת כבר את המסנן / החלון.", "מונע ספירה כפולה של ההעברה.", 1,
                          "ספירה כפולה", source="מקור הקובץ."),
    "optics.tau_filter": K("העברת מסנן נוסף", "העברה (0-1) של מסנן או חלון נוסף במסלול.", "מכפיל את האות. משמעותי "
                           "במערכת מורעבת-אור (לילה); כמעט לא משנה בלא-מקורר.", 1, "חשוב בלילה",
                           ["אין מסנן: 1.", "חלון גרמניום מצופה: 0.9-0.95."], "דף הנתונים של המסנן / החלון.",
                           ["להזין באחוזים."], _fraction("העברת המסנן", None, allow_zero=False)),
    "optics.rel_illum": K("תאורה יחסית בשולי השדה", "ההארה בשולי השדה ביחס למרכז (ויגנטינג x cos⁴).", "מדווח בנתוני "
                          "המערכת בלבד - הטווחים מחושבים במרכז השדה.", 0, "מדווח בלבד", ["1 = ללא נפילה.",
                          "עדשה רחבת שדה: 0.5-0.8."], "ניתוח Relative illumination.", check=_check_rel_illum),

    # ------------------------------------------------------------------ Detector geometry
    "detector.n_v": K("מספר פיקסלים אנכי", "מספר השורות בגלאי (למשל 512 ב-640x512).", "קובע את שדה הראייה האנכי. "
                      "לא משנה את הטווח.", 0, "קובע FOV, לא טווח", ["תרמי: 240, 480, 512, 1024.", "נראה: 1080, 2048."],
                      "דף הנתונים.", check=_check_n_v),
    "detector.square": K("פיקסלים ריבועיים", "מסומן: הפסיעה והגודל הפעיל זהים בשני הצירים - מזינים פעם אחת.",
                         "כמעט כל הגלאים המודרניים ריבועיים. ביטול הסימון מאפשר ערכים אנכיים שונים.", 0, "נוחות הזנה",
                         ["מסומן."], "דף הנתונים."),
    "detector.pitch_v_um": K("פסיעה אנכית", "המרחק בין מרכזי פיקסלים בכיוון האנכי.", "קובעת את ה-IFOV האנכי. "
                             "אותה השפעה כמו הפסיעה האופקית, בממד השני.", 2, "תלוי ב-Fλ/d", ["כמו האופקית."],
                             "דף הנתונים.", check=_check_pitch_v),
    "detector.a_h_um": K("גודל פעיל אופקי", "הגודל של האזור הרגיש בפיקסל, בכיוון האופקי.", "קובע את ה-MTF של הגלאי "
                         "(פיקסל גדול יותר מטשטש מעט יותר) ואת כמות האות. היחס לפסיעה הוא מקדם המילוי.", 1,
                         "MTF גלאי ואות", ["0.9-1.0 מהפסיעה בגלאי מודרני."], "דף הנתונים (fill factor).",
                         ["גודל פעיל גדול מהפסיעה."], _check_active("h")),
    "detector.a_v_um": K("גודל פעיל אנכי", "הגודל של האזור הרגיש בפיקסל, בכיוון האנכי.", "כמו הגודל האופקי.", 1,
                         "MTF גלאי ואות", source="דף הנתונים.", check=_check_active("v")),
    "detector.shape": K("צורת הגלאי", "הצורה של האזור הרגיש: מלבני, מעוין, עגול או loophole.", "קובעת את ה-MTF של "
                        "הגלאי. כמעט תמיד מלבני.", 1, "משני", ["rectangular."], "דף הנתונים."),
    "detector.d_um": K("קוטר הגלאי", "קוטר האזור הרגיש בגלאי עגול.", "קובע את ה-MTF של הגלאי העגול.", 1, "משני",
                       source="דף הנתונים.", check=_nonneg("קוטר", "µm")),
    "detector.d_hole_um": K("קוטר החור", "קוטר החור הלא-רגיש בגלאי loophole (HgCdTe עם via).", "מקטין את האות ומשנה "
                            "מעט את ה-MTF.", 1, "משני", source="דף הנתונים.", check=_nonneg("קוטר", "µm")),
    "detector.cte_on": K("יעילות העברת מטען (CCD)", "ממדל אובדן בהעברת המטען בקריאת CCD.", "רלוונטי רק ל-CCD ישן; "
                         "מוסיף אובדן MTF.", 1, "רק CCD", ["לא מסומן."], "דף הנתונים."),
    "detector.cte_h": K("CTE אופקי", "יעילות ההעברה בכל העברה אופקית (קרוב מאוד ל-1).", "אחרי מאות העברות, CTE נמוך "
                        "מורח את המטען ומוריד את ה-MTF.", 1, "רק CCD", ["0.99999."], "דף הנתונים.", check=_check_cte),
    "detector.ntr_h": K("מספר העברות אופקיות", "כמה העברות מטען אופקיות עד הקריאה.", "יחד עם ה-CTE קובע את האובדן.",
                        1, "רק CCD", source="דף הנתונים.", check=_positive_int("מספר ההעברות", 0)),
    "detector.cte_v": K("CTE אנכי", "יעילות ההעברה בכל העברה אנכית.", "כמו ה-CTE האופקי.", 1, "רק CCD", ["0.99999."],
                        "דף הנתונים.", check=_check_cte),
    "detector.ntr_v": K("מספר העברות אנכיות", "כמה העברות מטען אנכיות עד הקריאה.", "כמו ההעברות האופקיות.", 1,
                        "רק CCD", source="דף הנתונים.", check=_positive_int("מספר ההעברות", 0)),
    "detector.xtalk_h": K("זליגה בין פיקסלים (אופקי)", "זליגת אות לפיקסל השכן, כערך ה-MTF בתדר נייקוויסט (0 = כבוי).",
                          "זליגה מטשטשת את הפרטים העדינים ומקצרת את הזיהוי.", 1, "בעיקר על זיהוי",
                          ["0 (כבוי), או 0.8-0.95 אם יש מדידה."], "מדידת MTF של הגלאי.", check=_check_xtalk),
    "detector.xtalk_v": K("זליגה בין פיקסלים (אנכי)", "כמו הזליגה האופקית, בכיוון האנכי.", "כמו הזליגה האופקית.", 1,
                          "בעיקר על זיהוי", ["0."], "מדידת MTF של הגלאי.", check=_check_xtalk),

    # ------------------------------------------------------------------ Detector sensitivity
    "detector.uncooled_response": K("תגובה ספקטרלית (לא-מקורר)", "Flat: תגובה שטוחה בין תחילת התחום לסופו. Preset: "
                                    "עקומת QE.", "קובעת את התחום הספקטרלי של כל הרדיומטריה.", 1, "תחום ספקטרלי",
                                    ["בולומטר: flat 8-14 µm."], "דף הנתונים."),
    "detector.cuton_um": K("תחילת התחום הספקטרלי", "אורך הגל הקצר ביותר שהגלאי מגיב אליו.", "התחום קובע כמה קרינה "
                           "נאספת ואת העקיפה. תחום צר מדי מקטין את האות.", 1, "רדיומטריה",
                           ["LWIR: 7.5-8 µm.", "MWIR: 3-3.7 µm."], "דף הנתונים.", ["להזין בננומטר."], _check_cut("on")),
    "detector.cutoff_um": K("סוף התחום הספקטרלי", "אורך הגל הארוך ביותר שהגלאי מגיב אליו.", "כמו תחילת התחום.", 1,
                            "רדיומטריה", ["LWIR: 12-14 µm.", "MWIR: 4.8-5 µm."], "דף הנתונים.", check=_check_cut("off")),
    "detector.qe_preset": K("עקומת QE", "עקומת היעילות הקוונטית של חומר הגלאי (InSb, MCT, InGaAs, סיליקון).",
                            "קובעת גם את התחום הספקטרלי של כל החישוב. חומר שגוי = תחום שגוי = אטמוספרה, ניגוד ועקיפה "
                            "שגויים.", 2, "קובע את התחום", ["MWIR מקורר: InSb / XBn.", "SWIR: InGaAs.",
                            "יום: CCD Silicon."], "דף הנתונים של הגלאי.", ["לבחור InSb למצלמת LWIR."]),
    "detector.qe_scale": K("מקדם QE", "מכפיל את עקומת ה-QE כדי להתאים ל-QE המדוד.", "משנה את האות. משמעותי במערכות "
                           "מוגבלות-רעש (לילה).", 1, "חשוב בלילה", ["1."], "QE מדוד מדף הנתונים.", check=_check_qe_scale),
    "detector.qe_custom": K("עקומת QE משלכם", "שורה לכל נקודה: 'אורך גל [µm] QE [%]'.", "מחליפה את העקומה המובנית.",
                            1, "רדיומטריה", source="דף הנתונים של הגלאי."),
    "detector.qe_unit": K("יחידות ה-QE", "האם הערכים באחוזים או בשברים.", "בחירה שגויה משנה את האות פי 100.", 1,
                          "שגיאה גסה אם טועים", ["auto."], "הקובץ שלכם."),
    "detector.qe_basis": K("ה-QE מתייחס ל-", "Active area: QE פנימי. Pixel area: QE כולל (EMVA 1288) שכבר כולל את "
                           "מקדם המילוי.", "בחירה שגויה סופרת את מקדם המילוי פעמיים או לא סופרת אותו.", 1, "ספירה כפולה",
                           ["דף נתונים לפי EMVA 1288: pixel_area."], "דף הנתונים."),
    "detector.netd_TB_K": K("טמפרטורת בדיקת NETD", "טמפרטורת גוף-השחור שבה נמדד ה-NETD.", "NETD משתנה עם טמפרטורת "
                            "הסצנה: בסצנה קרה הוא גרוע יותר. הפרש מעל 10 K מהרקע מסומן.", 1, "עקביות",
                            ["בדרך כלל 300 K (27 °C)."], "דף הנתונים.", check=_kelvin(230, 400, "טמפרטורת הבדיקה")),
    "detector.t_th_ms": K("קבוע זמן תרמי", "קבוע הזמן של המיקרובולומטר - מתנהג כמו זמן אינטגרציה.", "בתנועה הוא "
                          "גורם למריחה. קבוע זמן ארוך = טשטוש בסריקה.", 1, "רק בתנועה", ["5-15 ms."], "דף הנתונים.",
                          check=_check_t_th),
    "detector.netd_F": K("F בבדיקת NETD", "ה-F-number שבו נמדד ה-NETD של המצלמה (0 = לא תועד).", "NETD תלוי ב-F²: "
                         "NETD שנמדד ב-F/1 גרוע פי 2 ב-F/1.4. אי-התאמה מסומנת ולא מומרת בשקט.", 2, "שגיאה של עד x2",
                         ["F של העדשה שאיתה נמדד."], "דף הנתונים (test conditions).", check=_check_netd_F),
    "detector.netd_tint_ms": K("זמן אינטגרציה בבדיקת NETD", "זמן האינטגרציה שבו נמדד ה-NETD.", "הרעש יחסי ל-1/√t: "
                               "אי-התאמה לתרחיש משנה את ה-NETD האפקטיבי.", 1, "עקביות", source="דף הנתונים.",
                               check=_check_netd_tint),
    "detector.netd_frames": K("פריימים ממוצעים בבדיקה", "כמה פריימים מוצעו במדידת ה-NETD.", "NETD ממוצע כבר כולל "
                              "הפחתת רעש. המודל מוסיף אינטגרציה משלו - הרעש יופחת פעמיים. צריך NETD של פריים בודד.",
                              1, "ספירה כפולה", ["1."], "דוח הבדיקה.", check=_check_netd_frames),
    "detector.noise_port": K("נקודת המדידה", "איפה נמדד ה-NETD: RAW, אחרי NUC, או ביציאת הווידאו המעובדת.", "NETD "
                             "מהיציאה המעובדת כבר כולל סינון זמני - המודל יספור אותו פעמיים והטווח יהיה אופטימי.", 1,
                             "ספירה כפולה", ["raw / post_nuc."], "דוח הבדיקה.", check=_check_noise_port),
    "detector.meas_F": K("F במדידת NETD של הגלאי", "ה-F שבו נמדד ה-NETD של הגלאי, להמרה לאופטיקה של הפרויקט (0 = "
                         "כמו בפרויקט).", "ההמרה לפי F² - ערך שגוי משנה את הרגישות.", 1, "המרת NETD", ["F/1."],
                         "דף הנתונים של הגלאי.", check=_nonneg("F", "")),
    "detector.meas_tau": K("העברה במדידת NETD", "העברת האופטיקה במדידה (0 = כמו בפרויקט).", "חלק מהמרת ה-NETD.", 1,
                           "המרת NETD", ["0."], "דף הנתונים.", check=_fraction("ההעברה במדידה")),
    "detector.meas_TB_K": K("טמפרטורת גוף-שחור במדידה", "טמפרטורת הסצנה במדידת ה-NETD (0 = כמו בפרויקט).", "חלק "
                            "מהמרת ה-NETD.", 1, "המרת NETD", ["300 K."], "דף הנתונים.",
                            check=_kelvin(230, 400, "טמפרטורת המדידה")),
    "detector.readout_mK": K("רעש קריאה ב-mK", "חלק הרעש שלא תלוי ב-F (רעש אלקטרוני), ב-mK.", "החלק הזה לא משתנה "
                             "בהמרת F - חשוב כשה-F של העדשה שונה מה-F של המדידה.", 1, "המרת NETD", ["0 אם לא ידוע."],
                             "יצרן הגלאי.", check=_nonneg("רעש קריאה", "mK")),
    "detector.tint_mode": K("איך נקבע זמן האינטגרציה", "Direct: ערך ישיר. Duty: שבר מזמן הפריים. Wellfill: לפי מילוי "
                            "באר רצוי מהרקע.", "Wellfill היא הדרך הטבעית למקורר IR: המצלמה בוחרת זמן לפי הסצנה.", 1,
                            "צורת קלט", ["מקורר IR: wellfill.", "SWIR / יום: direct."], "אופן עבודת המצלמה."),
    "detector.duty": K("מחזור עבודה", "זמן האינטגרציה כשבר (0-1) מזמן הפריים.", "יותר זמן = יותר אות, עד שהבאר "
                       "מתמלאת.", 1, "רמת האות", ["0.3-0.9."], "הגדרות המצלמה.", check=_check_duty),
    "detector.wellfill_pct": K("מילוי באר", "זמן האינטגרציה נבחר כך שהרקע ממלא את הבאר לאחוז הזה.", "מילוי גבוה = "
                               "אות גבוה ורעש יחסי נמוך, אבל סכנת רוויה במטרה חמה. מקובל 40%-70%.", 1, "רעש מול רוויה",
                               ["50%."], "הגדרות המצלמה.", check=_check_wellfill),
    "detector.storage_e": K("קיבולת הבאר", "מספר הנשאים המקסימלי בפיקסל (full well).", "מגבילה את זמן האינטגרציה. במקורר "
                            "ביום הבאר היא שמגבילה את יחס האות-לרעש.", 1, "גבול האות",
                            ["IR מקורר: 1e6-2e7.", "InGaAs: 1e5-1e6.", "CMOS: 5e3-5e4."], "דף הנתונים (Full well).",
                            check=_check_storage),
    "detector.cap_node": K("הקיבולת מתייחסת ל-", "באיזו נקודה נמדדה הקיבולת: פיקסל, ROIC או יציאת המצלמה.", "רק קיבולת "
                           "של יציאת המצלמה מאמתת את מילוי הבאר בפועל.", 0, "תקציב חשיפה", ["unknown אם לא ידוע."],
                           "דף הנתונים."),
    "detector.sat_e": K("קיבולת רוויה של המצלמה", "קיבולת הרוויה ביציאת המצלמה, בנשאים (0 = לא ידוע).", "אם ידוע, "
                        "הקטן מבין הבאר, הערך הזה וה-ADC הוא הקיבולת השמישה.", 1, "גבול האות", ["0."], "מדידת EMVA 1288.",
                        check=_nonneg("קיבולת", "e-")),
    "detector.fill_limit_pct": K("מילוי מותר (מרווח תכנון)", "המילוי הגבוה ביותר שמקבלים לפיקסל הבהיר ביותר.", "בתקציב "
                                 "החשיפה בלבד - מגן מרוויה.", 0, "תקציב חשיפה", ["70%-80%."], "דרישות התכנון.",
                                 check=_check_fill_limit),
    "detector.bright_refl": K("ההחזרות הבהירה בסצנה", "החזרות האובייקט הבהיר ביותר הסביר בסצנה.", "קובעת את גבול "
                              "הרוויה בתקציב החשיפה, לא את האות של המטרה.", 0, "תקציב חשיפה",
                              ["0.9 (שלג, בטון לבן)."], "התרחיש.", check=_check_bright_refl),
    "detector.bright_dT_K": K("האובייקט החם ביותר", "כמה מעלות מעל הרקע האובייקט החם ביותר הסביר.", "קובע את גבול "
                              "הרוויה בתרמי.", 0, "תקציב חשיפה", ["30 K."], "התרחיש.", check=_nonneg("ΔT", "K")),
    "detector.snr_req": K("SNR נדרש לפיקסל", "יחס האות-לרעש לפיקסל שהמשימה דורשת (0 = לא נבדק).", "תקציב החשיפה מדווח "
                          "אם הוא מושג. לא משנה את הטווח.", 0, "תקציב חשיפה", ["0, או 10-40 למדידה."], "דרישות.",
                          check=_check_snr_req),
    "detector.electron_gain": K("הגבר אלקטרונים", "הגבר פנימי של הגלאי (APD, EMCCD). 1 לגלאי רגיל.", "מגביר את האות "
                                "מעל רעש הקריאה - חשוב בלילה. מגיע עם רעש עודף (noise figure).", 1, "רק APD / EMCCD",
                                ["1."], "דף הנתונים.", check=_check_gain),
    "detector.dark_mode": K("זרם אפל: ערך או טבלה", "ערך אחד, או טבלה לפי טמפרטורת החיישן.", "טבלה מדויקת יותר "
                            "כשהחיישן עובד בטמפרטורות שונות.", 1, "דיוק", ["value."], "דף הנתונים."),
    "detector.dark_A": K("זרם אפל", "זרם לפיקסל גם בלי אור, באמפר.", "יוצר רעש ירייה וממלא את הבאר. משמעותי ב-SWIR "
                         "ובזמני אינטגרציה ארוכים (לילה).", 1, "חשוב בלילה",
                         ["IR מקורר: 1e-14-1e-12 A.", "InGaAs: 1e-15-1e-13 A."], "דף הנתונים (Dark current).",
                         ["להזין בצפיפות (A/cm²) במקום לפיקסל."], _check_dark),
    "detector.dark_table": K("טבלת זרם אפל", "'טמפרטורה [K] זרם [A]' בכל שורה, לפחות שתי שורות.", "הזרם מחושב "
                             "בטמפרטורת העבודה של החיישן.", 1, "דיוק", source="מדידת כיול."),
    "detector.T_sensor_K": K("טמפרטורת החיישן", "טמפרטורת העבודה של הגלאי, לחיפוש בטבלת הזרם האפל.", "זרם אפל גדל "
                             "פי 2 בערך כל 6-8 K (InGaAs).", 1, "דרך הזרם האפל",
                             ["IR מקורר: 77-150 K.", "InGaAs TEC: 250-290 K."], "דף הנתונים.",
                             check=_kelvin(40, 350, "טמפרטורת החיישן")),
    "detector.noise_figure": K("מקדם רעש (noise figure)", "רעש עודף של תהליך ההגבר (1 = ללא רעש עודף).", "מגדיל את "
                               "הרעש. רלוונטי רק עם הגבר.", 1, "רק עם הגבר", ["1, APD: 2-5."], "דף הנתונים.",
                               check=_range(1, 10, "", None)),
    "detector.adc_mode": K("רעש קוונטיזציה של ה-ADC", "None: לא ממודל. Carriers: LSB בנשאים. mK: LSB ב-mK.", "ADC גס "
                           "מוסיף רעש. בדרך כלל זניח ב-14 ביטים.", 1, "בדרך כלל זניח", ["carriers."], "דף הנתונים."),
    "detector.lsb_e": K("LSB בנשאים", "גודל צעד אחד של הממיר, בנשאים.", "רעש הקוונטיזציה הוא LSB/√12. אם הוא גדול "
                        "מרעש הקריאה הוא מוסיף רעש.", 1, "בדרך כלל זניח", ["קיבולת / 2^ביטים."], "דף הנתונים.",
                        check=_check_lsb_e),
    "detector.lsb_mK": K("LSB ב-mK", "גודל צעד אחד של הממיר, ב-mK.", "כמו LSB בנשאים.", 1, "בדרך כלל זניח",
                         source="דף הנתונים.", check=_nonneg("LSB", "mK")),
    "detector.adc_bits": K("ביטים של ה-ADC", "עומק הביטים של הממיר (0 = ללא בדיקת חיתוך).", "יחד עם ה-LSB נותן את "
                           "האות המקסימלי; המודל מזהיר מחיתוך.", 0, "בדיקת רוויה", ["14."], "דף הנתונים.",
                           check=_check_adc_bits),
    "detector.T_off_dev_K": K("הפרש טמפרטורה: גוף המצלמה", "טמפרטורת בית המצלמה ביחס לרקע.", "קרינה מבית חם מוסיפה "
                              "פוטוני רקע ורעש (בעיקר במקורר LWIR).", 1, "משני", ["0."], "תנאי ההפעלה.",
                              check=_range(-50, 80, "K", None)),
    "detector.T_off_opt_K": K("הפרש טמפרטורה: האופטיקה", "טמפרטורת העדשה ביחס לרקע.", "פליטת העדשה מוסיפה רקע ורעש.",
                              1, "משני", ["0."], "תנאי ההפעלה.", check=_range(-50, 80, "K", None)),
    "detector.T_cs_K": K("טמפרטורת המגן הקר", "טמפרטורת המגן הקר סביב הגלאי.", "מגן חם פולט ומוסיף רקע. בקירור "
                         "רגיל זה זניח.", 1, "זניח כשקר", ["77-150 K."], "דף הנתונים.", check=_check_Tcs),
    "detector.cs_mode": K("הגדרת המגן הקר", "לפי יעילות, או לפי ה-F האפקטיבי של הפתח.", "צורת קלט.", 1, "צורת קלט",
                          ["efficiency."], "דף הנתונים."),
    "detector.cs_eff": K("יעילות המגן הקר", "היחס בין F של האופטיקה ל-F של המגן (1 = מותאם).", "מגן לא מותאם "
                         "(יעילות < 1) רואה קרינה חמה מבית המצלמה - רעש נוסף.", 1, "רעש רקע", ["0.9-1."],
                         "דף הנתונים.", check=_fraction("יעילות המגן הקר", "מותאם: 1", allow_zero=False)),
    "detector.cs_F": K("F של המגן הקר", "ה-F האפקטיבי של פתח המגן הקר.", "צריך להתאים ל-F של העדשה. F גדול מהעדשה - "
                       "ויגנטינג ואובדן אות; קטן מדי - קרינה חמה.", 1, "התאמת עדשה", ["F/2, F/4, F/5.5."],
                       "דף הנתונים של הגלאי (Dewar).", check=_check_cs_F),
    "detector.nps_file": K("ספקטרום הספק הרעש (NPS)", "NPS מדוד - בדיקת איכות בלבד.", "מראה אם הנחת הרעש הלבן "
                           "מתקיימת. לא משמש בטווחים.", 0, "בדיקת איכות", source="מדידה."),
    "detector.nps_unit": K("יחידת התדר של ה-NPS", "יחידת התדר בקובץ ה-NPS.", "יחידה שגויה מזיזה את הבדיקה.", 0,
                           "בדיקת איכות", source="הקובץ."),
    "detector.nps_stage": K("שלב מדידת ה-NPS", "לפני עיבוד (RAW) או על התמונה המעובדת.", "לתיעוד ופירוש הבדיקה.", 0,
                            "בדיקת איכות", source="דוח המדידה."),
    "detector.fpn_mode": K("רעש תבנית קבוע (FPN)", "רעש מרחבי שנשאר אחרי תיקון אי-אחידות (NUC): none, measured או "
                           "estimate.", "FPN לא מתמצע בזמן - העין לא מנקה אותו. במצלמה תרמית עם NUC ישן הוא יכול להיות "
                           "משמעותי.", 1, "משני, חשוב ב-NUC ישן", ["estimate (חצי מהרעש הזמני)."], "מדידה / יצרן."),
    "detector.ietd_mK": K("IETD", "רעש מרחבי (FPN) של מצלמה תרמית, ב-mK.", "מוסיף רעש שלא נעלם במיצוע.", 1, "משני",
                          ["10-30 mK אחרי NUC טוב."], "מדידה.", check=_nonneg("IETD", "mK")),
    "detector.prnu_pct": K("PRNU", "שונות ההגבר בין פיקסלים, באחוזים מהאות.", "ביום, עם אות גבוה, PRNU יכול להיות "
                           "הרעש הדומיננטי.", 1, "חשוב באות גבוה", ["0.2%-1%."], "דף הנתונים (EMVA 1288).",
                           check=_range(0, 10, "%", None)),
    "detector.dsnu_A": K("DSNU", "שונות הזרם האפל בין פיקסלים, באמפר.", "רעש מרחבי באות נמוך.", 1, "משני",
                         source="דף הנתונים.", check=_nonneg("DSNU", "A")),
    "detector.fpn_fraction": K("FPN כשבר מהרעש הזמני", "רעש התבנית הקבוע כשבר מה-NETD / NES.", "הערכה כשאין מדידה.",
                               1, "משני", ["0.3-0.5."], "הערכה.", check=_range(0, 2, "", None)),

    # ------------------------------------------------------------------ Signal processing
    "dsp.frames_on": K("מיצוע פריימים", "מיצוע של כמה פריימים להפחתת רעש זמני.", "הרעש יורד פי √N - משמעותי במערכת "
                       "מוגבלת-רעש (לילה, ניגוד נמוך). בסצנה נעה זה מטשטש.", 1, "רק במוגבלת-רעש",
                       ["כבוי, אלא אם המצלמה ממצעת."], "תצורת העיבוד."),
    "dsp.n_frames": K("מספר פריימים ממוצעים", "כמה פריימים ממוצעים.", "הרעש יורד פי √N, אבל המודל מניח סצנה סטטית.",
                      1, "רק במוגבלת-רעש", ["2-8."], "תצורת העיבוד.", check=_check_n_frames),
    "dsp.iir_on": K("מסנן IIR זמני", "מיצוע רקורסיבי של פריימים.", "כמו מיצוע פריימים, עם השהיה.", 1, "רק במוגבלת-רעש",
                    source="תצורת העיבוד."),
    "dsp.iir_alpha": K("α של מסנן IIR", "משקל הפריים החדש (0-1). קטן = הפחתת רעש חזקה + השהיה.", "שקול למיצוע של "
                       "(2-α)/α פריימים.", 1, "רק במוגבלת-רעש", ["0.1-0.5."], "תצורת העיבוד.", check=_check_iir),
    "dsp.filter_on": K("מסנן דיגיטלי", "מסנן FIR - חידוד או החלקה.", "משנה את ה-MTF ואת הרעש. חידוד לא נזקף לטווח "
                       "אלא אם מסמנים Credit sharpening.", 1, "משני", ["כבוי."], "תצורת העיבוד."),
    "dsp.filter_dir": K("כיוון המסנן", "באיזה כיוון מופעל המסנן.", "משפיע על ה-MTF באותו כיוון.", 1, "משני", ["both."],
                        "תצורת העיבוד."),
    "dsp.h_type": K("סוג המסנן האופקי", "Odd: עם מקדם מרכזי. Even: בלי.", "סוג המסנן.", 1, "משני", ["odd."],
                    "תצורת העיבוד."),
    "dsp.h_coef": K("מקדמי המסנן האופקי", "c0..c4 (c0 = מרכז), מופרדים בפסיקים.", "קובעים את צורת ה-MTF של המסנן. "
                    "סכום לא מנורמל משנה את הבהירות.", 1, "משני", ["החלקה: 0.5, 0.25.", "חידוד: 1.6, -0.3."],
                    "תצורת העיבוד.", check=_check_coef_axis("h")),
    "dsp.v_type": K("סוג המסנן האנכי", "Odd: עם מקדם מרכזי. Even: בלי.", "סוג המסנן.", 1, "משני", ["odd."],
                    "תצורת העיבוד."),
    "dsp.v_coef": K("מקדמי המסנן האנכי", "c0..c4 בכיוון האנכי.", "כמו המקדמים האופקיים.", 1, "משני",
                    source="תצורת העיבוד.", check=_check_coef_axis("v")),
    "dsp.credit_boost": K("לזקוף חידוד לטווח", "האם לכלול חידוד (MTF > 1) בחישוב הטווח.", "חידוד נראה טוב אבל לא "
                          "מוסיף מידע ומגביר רעש. בלי כיול, השארת הסימון כבוי שמרנית ונכונה.", 1, "שמרני כשכבוי",
                          ["כבוי."], "מדיניות הניתוח.", check=_check_credit),
    "dsp.zoom": K("זום אלקטרוני", "פקטור הגדלה דיגיטלי (1 = ללא).", "מגדיל את התמונה במסך בלי מידע חדש. יכול לעזור "
                  "כשהעין מגבילה (מסך קטן / רחוק), אחרת לא משנה.", 1, "רק כשהעין מגבילה", ["1-2."], "תצורת התצוגה.",
                  check=_check_zoom),
    "dsp.zoom_type": K("סוג הזום", "Pixel: שכפול פיקסלים. Bilinear: אינטרפולציה.", "משפיע על MTF השחזור.", 1, "משני",
                       ["bilinear."], "תצורת התצוגה."),
    "dsp.lrep": K("שכפול שורות", "כל שורה מוצגת כמה פעמים (1 = ללא).", "כמו זום אנכי - לא מוסיף מידע.", 1, "משני",
                  ["1."], "תצורת התצוגה.", check=_positive_int("פקטור השכפול")),
    "dsp.lrep_type": K("סוג שכפול השורות", "Pixel או linear.", "משפיע על MTF השחזור.", 1, "משני", ["pixel."],
                       "תצורת התצוגה."),
    "dsp.crep": K("שכפול עמודות", "כל עמודה מוצגת כמה פעמים (1 = ללא).", "כמו זום אופקי.", 1, "משני", ["1."],
                  "תצורת התצוגה.", check=_positive_int("פקטור השכפול")),
    "dsp.crep_type": K("סוג שכפול העמודות", "Pixel או linear.", "משפיע על MTF השחזור.", 1, "משני", ["pixel."],
                       "תצורת התצוגה."),
    "dsp.pl_compression": K("דחיסה", "דחיסת וידאו: none, lossless או lossy.", "דחיסה מאבדת (lossy) מטשטשת פרטים "
                            "עדינים. היא משפיעה על הטווח רק דרך הטשטוש השקול שלמטה.", 1, "דרך הטשטוש השקול",
                            ["וידאו מוזרם: lossy."], "תצורת התקשורת."),
    "dsp.comp_blur_px": K("טשטוש שקול לדחיסה", "דחיסה מאבדת כטשטוש גאוסי, σ בפיקסלים (0 = לא ממודל).", "מוריד את "
                          "ה-MTF בתדרים גבוהים: פוגע בעיקר בזיהוי. בקצב סיביות נמוך ההשפעה משמעותית.", 2,
                          "בעיקר על זיהוי", ["H.264 בקצב טוב: 0.2-0.4.", "קצב נמוך: 0.5-1."], "התאמה לקודק ולקצב.",
                          check=_check_comp_blur),
    "dsp.tone_mode": K("עקומת טון / AGC", "מיפוי האות לזרם פלט מקוונטט (למשל וידאו 8 ביט): linear, gamma או log.",
                       "האות והרעש עוברים אותה עקומה, אבל העיגול לרמות הפלט מוסיף רעש - במיוחד ב-AGC תרמי רחב.", 1,
                       "רעש עיגול", ["RAW: none.", "וידאו תרמי 8 ביט: linear."], "תצורת הפלט."),
    "dsp.tone_bits": K("עומק ביטים בפלט", "כמה ביטים בזרם הפלט.", "פחות ביטים = מדרגות גסות יותר = רעש עיגול.", 1,
                       "רעש עיגול", ["8."], "תצורת הפלט.", check=_check_tone_bits),
    "dsp.tone_gamma": K("מעריך גמא", "out = (x/x_max)^γ.", "גמא דוחס את האזורים הבהירים - שם רעש העיגול גדל.", 1,
                        "משני", ["0.45 (וידאו)."], "תצורת הפלט.", check=_range(0.1, 3, "", None)),
    "dsp.tone_k": K("מקדם דחיסה לוגריתמי", "k בעקומה הלוגריתמית; גדול = דוחס יותר את הבהירים.", "משנה איפה רעש העיגול "
                    "גדל.", 1, "משני", ["10-1000."], "תצורת הפלט.", check=_range(0.1, 1e5, "", None)),
    "dsp.tone_span_K": K("טווח AGC תרמי", "טווח הטמפרטורות שממופה ליניארית לרמות הפלט.", "טווח רחב על 8 ביטים נותן "
                         "מדרגות גסות: 20 K על 8 ביטים = 23 mK רעש עיגול. אם זה קרוב ל-NETD - ניגודים קטנים נבלעים.",
                         1, "רעש עיגול", ["10-40 K."], "הגדרות ה-AGC.", check=_check_tone_span),

    # ------------------------------------------------------------------ Display & observer
    "display.observer": K("סוג הצופה", "Legacy: הצופה התקני של TRM4. Human: אותו מודל עין עם התצוגה שלכם. "
                          "Algorithm: אלגוריתם קורא את הפריימים - בלי תצוגה ועין.", "צופה אלגוריתמי בלי כיול נותן "
                          "הערכה לא מכוילת, לרוב ארוכה בהרבה מצופה אנושי.", 2, "משנה את כל מודל הצופה",
                          ["השוואה ל-TRM4: legacy.", "מערכת עם מסך ידוע: human."], "מטרת הניתוח.",
                          check=_check_obs_algo),
    "display.algo_calib": K("סט כיול של האלגוריתם", "מזהה סט הכיול (ריק = לא מכויל).", "בלי כיול התוצאה מסומנת "
                            "כהערכה.", 0, "תיעוד", source="כיול האלגוריתם."),
    "display.algo_criterion": K("קריטריון המשימה לאלגוריתם", "LP: זוגות קווים בלי עין. POT: פיקסלים על המטרה + CNR "
                                "מינימלי.", "קובע את חישוב הטווח של הצופה האלגוריתמי.", 2, "רק לאלגוריתם", ["lp."],
                                "מאפייני האלגוריתם."),
    "display.algo_cnr_min": K("CNR מינימלי לפיקסל", "יחס ניגוד-לרעש מינימלי לפיקסל שהאלגוריתם צריך.", "ערך גבוה "
                              "מקצר את הטווח במערכת מוגבלת-רעש.", 2, "רק לאלגוריתם", ["3 (הנחה כללית)."],
                              "כיול האלגוריתם.", check=_check_algo_cnr),
    "display.f_eyepiece_mm": K("מוקד העינית", "אורך המוקד של העינית.", "קובע את ההגדלה הזוויתית: מוקד קצר = הגדלה "
                               "גדולה = פרטים גדולים יותר לעין.", 2, "מנוף תצוגה", ["15-30 mm."], "דף הנתונים.",
                               check=_check_eyepiece),
    "display.n_h": K("פיקסלים בתצוגה (אופקי)", "מספר הפיקסלים האופקי של המסך.", "תצוגה עם פחות פיקסלים מהגלאי מאבדת "
                     "רזולוציה.", 1, "רק אם קטן מהגלאי", ["1280, 1920."], "דף הנתונים של המסך.",
                     check=_positive_int("מספר הפיקסלים", 16)),
    "display.n_v": K("פיקסלים בתצוגה (אנכי)", "מספר הפיקסלים האנכי של המסך.", "כמו האופקי.", 1, "רק אם קטן מהגלאי",
                     ["1024, 1080."], "דף הנתונים של המסך.", check=_positive_int("מספר הפיקסלים", 16)),
    "display.pitch_h_mm": K("גודל פיקסל בתצוגה (אופקי)", "גודל פיקסל אחד במסך, במ\"מ.", "יחד עם מרחק הצפייה קובע כמה "
                            "גדולה התמונה לעין. פיקסל גדול / קרוב = הגדלה גדולה.", 2, "מנוף תצוגה",
                            ["מסך FHD 24\": 0.28 mm.", "מיקרו-תצוגה: 0.008 mm."], "דף הנתונים של המסך.",
                            check=_check_disp_pitch),
    "display.pitch_v_mm": K("גודל פיקסל בתצוגה (אנכי)", "גודל פיקסל אחד במסך, אנכי.", "כמו האופקי.", 2, "מנוף תצוגה",
                            source="דף הנתונים של המסך.", check=_check_disp_pitch),
    "display.luminance": K("בהירות התצוגה", "בהירות ממוצעת של המסך, ב-cd/m².", "רגישות העין לניגוד תלויה בה: מסך "
                           "חשוך מקצר את הטווח. מעל ~50 cd/m² ההשפעה קטנה.", 1, "רק במסך חשוך",
                           ["מסך משרדי: 100-300.", "תצפית לילה (מעומעם): 5-20."], "דף הנתונים / מדידה.",
                           check=_check_luminance),
    "display.t_eye_s": K("זמן אינטגרציה של העין", "הזמן שבו העין משלבת פריימים, בשניות.", "קבוע כיול של מודל הצופה: "
                         "ערך ארוך = יותר מיצוע רעש בווידאו.", 1, "קבוע כיול", ["0.1 s (TRM4)."],
                         "ברירת המחדל.", ["להזין ב-ms."], _check_eye_t),
    "display.neglect_eye": K("התעלמות מה-MTF של העין", "מניח עין מושלמת.", "אפשרות למעבדה. בשדה זה נותן טווח "
                             "אופטימי.", 1, "אופטימי בשדה", ["לא מסומן."], "מטרת הניתוח.", check=_check_neglect_eye),

    # ------------------------------------------------------------------ Stabilization & MTFs
    "stab.jitter_mode": K("מקור תנועת התמונה", "None: אין תנועה. Model: מודלי רטט. Measured: סדרת זמן מדודה. PSD: "
                          "ספקטרום הספק מדוד.", "נתוני מדידה מדויקים יותר ממודל. 'none' בשדה צר אופטימי.", 2,
                          "חשוב בשדה צר", ["אין מדידה: model עם 70 µrad.", "יש מדידה: measured / psd."],
                          "מדידת ייצוב.", check=_check_jitter_mode),
    "stab.psd_file": K("קובץ PSD", "PSD זוויתי חד-צדדי של קו הראייה השיורי: תדר [Hz] ו-PSD.", "מתפצל לטשטוש בתוך "
                       "פריים וריצוד בין פריימים לפי זמן האינטגרציה.", 2, "חשוב בשדה צר", source="מדידת ייצוב."),
    "stab.psd_unit": K("יחידת ה-PSD", "יחידת ה-PSD (זווית בריבוע ל-Hz).", "יחידה שגויה = ריצוד שגוי בסדרי גודל.", 2,
                       "שגיאה גסה אם טועים", ["urad²/Hz."], "הקובץ."),
    "stab.residual_los": K("נתונים שיוריים", "האם הנתונים הם התנועה שנשארה אחרי הייצוב.", "תנועת פלטפורמה (לפני ייצוב) "
                           "מגזימה בטשטוש כשיש ייצוב.", 1, "הערכת יתר", ["מסומן אם נמדד אחרי הגימבל."], "מקור המדידה."),
    "stab.jitter_file": K("קובץ ריצוד", "סדרת זמן של תנועת התמונה: 't h v' או 'h v'.", "מחליף את מודלי הרטט.", 2,
                          "חשוב בשדה צר", source="מדידת ייצוב (ג'יירו / מעקב)."),
    "stab.jitter_unit": K("יחידת התנועה בקובץ", "µrad, mrad או פיקסלים.", "יחידה שגויה = ריצוד שגוי פי 1000.", 2,
                          "שגיאה גסה אם טועים", ["urad."], "הקובץ."),
    "stab.jitter_rate_hz": K("קצב דגימה", "קצב הדגימה של קובץ בלי עמודת זמן.", "צריך לפחות שתי דגימות לזמן אינטגרציה "
                             "כדי לזהות טשטוש בתוך פריים.", 1, "דיוק", source="מערכת המדידה.",
                             check=_nonneg("קצב הדגימה", "Hz")),
    "stab.random_on": K("רטט אקראי", "כולל ריצוד אקראי של קו הראייה.", "בלי ריצוד, מערכת עם שדה צר מקבלת תחזית "
                        "אופטימית מדי.", 2, "חשוב בשדה צר", ["מסומן, עם 70 µrad אם אין מדידה."], "מדידת ייצוב."),
    "stab.rand_v_mrad": K("ריצוד אקראי אנכי (rms)", "עוצמת הריצוד האקראי האנכי, ב-mrad rms.", "מה שקובע הוא היחס "
                          "ל-IFOV. ריצוד גדול מה-IFOV מטשטש מעל פיקסל.", 3, "ביחס ל-IFOV",
                          ["כמו האופקי: 0.005-0.07 mrad."], "מדידת ייצוב.", ["להזין ב-µrad בשדה של mrad."],
                          _check_jitter_v),
    "stab.lin_on": K("תנועה ליניארית", "תנועה קבועה של התמונה בזמן האינטגרציה (מריחה).", "חשוב בסריקה או במעקב אחרי "
                     "מטרה נעה.", 1, "רק בתנועה", ["כבוי בתצפית נייחת."], "התרחיש."),
    "stab.lin_h": K("מהירות זוויתית אופקית", "מהירות התמונה בזמן האינטגרציה, ב-mrad/s.", "המריחה = מהירות x זמן "
                    "אינטגרציה. מעל פיקסל היא מטשטשת את הפרטים.", 1, "רק בתנועה", source="התרחיש.", check=_check_lin),
    "stab.lin_v": K("מהירות זוויתית אנכית", "מהירות התמונה האנכית בזמן האינטגרציה.", "כמו האופקית.", 1, "רק בתנועה",
                    source="התרחיש.", check=_check_lin),
    "stab.smear_allow_px": K("מריחה מותרת לחשיפה", "כמה מריחה בחשיפה המשימה סובלת, בפיקסלים.", "בתקציב החשיפה "
                             "מגביל את זמן האינטגרציה בתנועה.", 0, "תקציב חשיפה", ["0.5."], "דרישות.",
                             check=_check_smear),
    "stab.sin_on": K("רטט סינוסי", "רטט בתדר גבוה של קו הראייה.", "מוסיף טשטוש.", 1, "משני", source="מדידת רטט."),
    "stab.sin_h": K("משרעת רטט אופקית", "משרעת הרטט הסינוסי האופקי, ב-mrad.", "משרעת גדולה מה-IFOV - טשטוש חזק.", 1,
                    "ביחס ל-IFOV", source="מדידת רטט.", check=_check_sin),
    "stab.sin_v": K("משרעת רטט אנכית", "משרעת הרטט הסינוסי האנכי.", "כמו האופקית.", 1, "ביחס ל-IFOV",
                    source="מדידת רטט.", check=_check_sin),
    "stab.neglect": K("התעלמות מ-MTF הייצוב", "מניח פלטפורמה יציבה לגמרי.", "בשדה צר זה אופטימי מאוד.", 2,
                      "אופטימי בשדה צר", ["לא מסומן."], "מטרת הניתוח.", check=_check_neglect_stab),
    "additional.type": K("MTF נוסף", "רכיב MTF שהמודל לא מכסה (למשל ממדידה). Prefilter: לפני הדגימה (משפיע על "
                         "התחזות). Postfilter: אחרי.", "מוסיף טשטוש - בעיקר על הזיהוי.", 1, "משני",
                         ["none."], "מדידה."),
    "additional.par": K("פרמטר ה-MTF הנוסף", "האפס הראשון (sinc / מלבני) או סטיית התקן (גאוסי), ב-1/mrad.", "קובע כמה "
                        "חזק הטשטוש הנוסף.", 1, "משני", source="התאמה למדידה.", check=_nonneg("פרמטר", "1/mrad")),

    # ------------------------------------------------------------------ Target & scenario
    "target.t_refl_mode": K("החזרות המטרה: ערך או חומר", "Effective: ערך אחד. Spectral: עקומה של חומר מהספרייה.",
                            "עקומה ספקטרלית נכונה יותר כשהתחום רחב.", 1, "צורת קלט",
                            ["ערך ידוע: effective.", "חומר מוכר: spectral."], "מקור הנתונים."),
    "target.b_refl_mode": K("החזרות הרקע: ערך או חומר", "Effective: ערך אחד. Spectral: עקומה של חומר מהספרייה.",
                            "כמו החזרות המטרה.", 1, "צורת קלט", source="מקור הנתונים."),
    "target.t_emis_mode": K("פליטות המטרה", "Blackbody (1), grey (ערך קבוע) או spectral (חומר).", "ב-General / MWIR "
                            "ביום, פליטות < 1 פירושה גם החזרה של הסביבה - זה משנה את הניגוד.", 1, "ניגוד ב-General",
                            ["blackbody, אלא אם ידוע."], "ספריית חומרים."),
    "target.t_emis": K("פליטות המטרה (ערך)", "פליטות קבועה של המטרה (0-1).", "משנה את הניגוד האפקטיבי.", 1,
                       "ניגוד ב-General", ["צבע / פלדה מחומצנת: 0.85-0.95."], "ספריית חומרים.", check=_check_emis),
    "target.t_emis_preset": K("חומר המטרה (פליטות)", "חומר שעקומת הפליטות שלו משמשת למטרה.", "משנה את הניגוד.", 1,
                              "ניגוד ב-General", source="ספריית החומרים."),
    "target.b_emis_mode": K("פליטות הרקע", "Blackbody, grey או spectral.", "כמו פליטות המטרה.", 1, "ניגוד ב-General",
                            source="ספריית חומרים."),
    "target.b_emis": K("פליטות הרקע (ערך)", "פליטות קבועה של הרקע (0-1).", "משנה את הניגוד.", 1, "ניגוד ב-General",
                       ["צמחייה / אדמה: 0.9-0.98."], "ספריית חומרים.", check=_check_emis),
    "target.b_emis_preset": K("חומר הרקע (פליטות)", "חומר שעקומת הפליטות שלו משמשת לרקע.", "משנה את הניגוד.", 1,
                              "ניגוד ב-General", source="ספריית החומרים."),
    "target.alt_m": K("גובה המטרה מעל הקרקע", "גובה המטרה, לחישוב פרופיל ה-Cn² לאורך הנתיב.", "טורבולנציה חזקה ליד "
                      "הקרקע: נתיב גבוה יותר עובר בטורבולנציה חלשה יותר.", 1, "רק עם טורבולנציה", ["1 מ'."],
                      "התרחיש.", check=_nonneg("גובה", "m")),
    "target.flight": K("מסלול המצלמה", "Altitude: גובה קבוע (זווית הצפייה משתנה עם הטווח). Angle: זווית צפייה "
                       "קבועה.", "קובע את הגאומטריה האלכסונית - והאם רואים את גג המטרה.", 1, "רק באלכסון",
                       ["קרקעי: altitude עם 0."], "התרחיש."),
    "target.altitude_m": K("גובה המצלמה מעל המטרה", "גובה המצלמה ביחס למטרה, במטרים.", "קובע את הטווח האלכסוני ואת "
                           "זווית הצפייה. מלמעלה רואים גם את עומק המטרה (שטח גדול יותר), והנתיב עובר בטורבולנציה "
                           "חלשה.", 2, "חשוב במוטס", ["קרקעי: 0.", "תורן: 10-30 מ'.", "מוטס: 500-5000 מ'."],
                           "התרחיש.", ["להזין ברגל."], _check_altitude),
    "target.angle_deg": K("זווית צפייה", "זווית קבועה כלפי מטה (חיובית = מבט למטה).", "כמו הגובה: משנה את השטח "
                          "הנראה והנתיב.", 2, "חשוב במוטס", ["0 (אופקי)."], "התרחיש.", check=_check_angle),
    "target.tasks.N.on": K("משימה פעילה", "האם לחשב טווח למשימה הזו.", "משימה כבויה לא מחושבת.", 0, "בחירת פלט",
                           ["שלוש המשימות פעילות."], "מטרת הניתוח."),
    "target.tasks.N.name": K("שם המשימה", "שם המשימה בגרפים ובטבלאות.", "לא משתתף בחישוב.", 0, "תיעוד בלבד",
                             ["Detection / Recognition / Identification."], "בחירה שלכם."),
    "target.tasks.N.pot": K("פיקסלים על המטרה (אלגוריתם)", "כמה פיקסלים צריך על שטח המטרה למשימה, בצופה אלגוריתמי.",
                            "יותר פיקסלים = טווח קצר יותר.", 2, "רק לאלגוריתם",
                            ["גילוי ~60, הכרה ~250, זיהוי ~350 (Holst & Mahalanobis 2023)."], "כיול האלגוריתם.",
                            check=_check_pot),
    "target.tasks.N.v50": K("V50 של מדד TTP", "מספר המחזורים על המטרה ל-50% הצלחה במדד TTP.", "משמש רק לטווחי TTP "
                            "הנוספים. הערכים חייבים כיול - הם לא חליפים ל-NV-IPM.", 1, "רק לטווחי TTP",
                            ["2.7 / 14.5 / 20.8."], "כיול לסט המטרות."),
    "target.prob_levels": K("טווחי P80 / P90", "מדווח גם טווחים בהסתברות 80% ו-90%.", "TRM4 נותן 50%. ל-P90 הטווח "
                            "בערך 0.57 מ-P50 - חשוב לשימושים בטיחותיים.", 0, "פלט נוסף", ["מסומן."], "מטרת הניתוח."),
    "target.ttp": K("טווחי TTP / V50", "מדווח גם טווחים לפי מדד TTP (Vollmerhausen 2004).", "השוואה נוספת; לא משנה את "
                    "טווחי ה-TRM4.", 0, "פלט נוסף", ["כבוי."], "מטרת הניתוח."),
    "target.geo_limit": K("טווח גאומטרי לייחוס", "טווח שבו זוגות הקווים נכנסים לממד הקריטי (נייקוויסט / עקיפה), בלי "
                          "רעש, ניגוד ואטמוספרה.", "ייחוס לגודל המערכת - לא גבול עליון.", 0, "פלט נוסף", ["מסומן."],
                          "מטרת הניתוח."),
    "target.clutter": K("עומס הרקע (clutter)", "רמת העומס ברקע: low עד high.", "TRM4 מניח רקע אחיד. העומס משפיע רק "
                        "עם מודל העומס שלמטה; עומס גבוה יכול לדרוש פי 6 יותר מחזורים לגילוי.", 1, "רק עם מודל העומס",
                        ["שטח פתוח: low.", "עירוני / יער: medium-high."], "התרחיש."),
    "target.clutter_model": K("מודל העומס (ACQUIRE-LC)", "מכפיל את קריטריון הגילוי לפי רמת העומס.", "בעומס גבוה "
                              "טווח הגילוי מתקצר מאוד. ההכרה והזיהוי לא משתנים.", 2, "רק על גילוי",
                              ["כבוי להשוואה ל-TRM4."], "מטרת הניתוח.", check=_check_clutter_model),

    # ------------------------------------------------------------------ Irradiance
    "irradiance.mode": K("הארה", "האם הסצנה מוארת במקור (שמש, ירח, פנס). חובה בחיישן מחזיר.", "בלי הארה בתחום "
                         "הנראה / SWIR אין אות - אין טווח.", 3, "בלי הארה אין אות",
                         ["Visible / SWIR: single.", "General (פליטה בלבד): none."], "התרחיש."),
    "irradiance.type": K("סוג המקור", "גוף שחור, מקור רחב-סרט, או מונוכרומטי (לייזר).", "קובע את ספקטרום ההארה.", 1,
                         "צורת קלט", ["טבעי: broadband."], "התרחיש."),
    "irradiance.T_bb_K": K("טמפרטורת הגוף השחור", "טמפרטורת הגוף השחור שמאיר את הסצנה.", "קובעת את העוצמה ואת "
                           "הספקטרום.", 2, "רמת האות", ["שמש: ~5800-6000 K."], "התרחיש.",
                           check=_range(300, 10000, "K", None)),
    "irradiance.spectrum": K("אפיון הספקטרום", "ערך אפקטיבי, טמפרטורת צבע, או מקור טבעי מוכן.", "מקור טבעי מוכן הוא "
                             "הדרך הפשוטה והעקבית ביותר.", 1, "צורת קלט", ["preset."], "התרחיש."),
    "irradiance.E_eff": K("הארה אפקטיבית", "עוצמת ההארה על הסצנה בתוך התחום הספקטרלי, ב-W/m².", "האות ביחס ישר אליה. "
                          "בלילה זה מה שקובע אם המערכת מוגבלת-רעש.", 3, "קובע את רמת האות",
                          ["שמש ישירה (נראה): ~500 W/m².", "ירח מלא: ~0.001 W/m²."], "מדידה / מודל.",
                          check=_check_E("W/m²")),
    "irradiance.T_colour_K": K("טמפרטורת צבע", "הטמפרטורה שמתארת את צורת הספקטרום של המקור.", "משנה את חלוקת האור "
                               "בין אורכי הגל.", 1, "צורת הספקטרום", ["שמש: 5800 K.", "להט: 2850 K."], "התרחיש.",
                               check=_check_T_colour),
    "irradiance.E_peak": K("הארה ספקטרלית בשיא", "ההארה הספקטרלית בשיא הספקטרום, על המטרה.", "מכפילה את כל הספקטרום "
                           "- האות ביחס ישר אליה.", 3, "קובע את רמת האות",
                           ["שמש: ~1240 W/(m² µm).", "ירח מלא: ~0.003."], "ה-preset, או מדידה.",
                           check=_check_E("W/(m² µm)")),
    "irradiance.lambda_um": K("אורך גל המקור", "אורך הגל של מקור מונוכרומטי (לייזר).", "חייב להיות בתחום הגלאי, אחרת "
                              "אין אות.", 2, "חייב להיות בתחום", ["0.808, 0.85, 1.064, 1.55 µm."], "דף הנתונים של "
                              "המאיר.", ["להזין בננומטר."], _check_lambda_mono),
    "irradiance.E_mono": K("הארת המקור המונוכרומטי", "עוצמת ההארה של הלייזר על הסצנה, ב-W/m².", "האות ביחס ישר "
                           "אליה.", 3, "קובע את רמת האות", source="חישוב: הספק / שטח האלומה בטווח.",
                           check=_check_E("W/m²")),
    "irradiance.geometry": K("גאומטריית המקור", "Extended: מפוזר מכל הכיוונים. Fixed in space: מקור נקודתי (שמש) "
                             "שיוצר הצללה.", "בהצללה, החזית יכולה להיות בצל - ניגוד שונה.", 1, "משני",
                             ["extended."], "התרחיש."),
    "irradiance.beta_h_deg": K("זווית המקור (אופקית)", "הזווית בין כיוון המקור לחזית המטרה, אופקית.", "קובעת כמה "
                               "מוארת החזית.", 1, "משני", ["0."], "התרחיש.", check=_check_beta),
    "irradiance.beta_v_deg": K("זווית המקור (אנכית)", "הזווית בין כיוון המקור לחזית המטרה, אנכית.", "קובעת כמה "
                               "מוארת החזית.", 1, "משני", ["45°."], "התרחיש.", check=_check_beta),

    # ------------------------------------------------------------------ Atmosphere
    "atmosphere.mode": K("איך מוגדרת ההעברה", "Extinction: מקדם הנחתה (Beer). Visibility: טווח ראות (נראה בלבד). "
                         "Weather: ראות + לחות + טמפרטורה. Spectral: קובץ (MODTRAN).", "MODTRAN מדויק ביותר. טווח ראות "
                         "אינו מקדם הנחתה תקף באינפרא-אדום.", 2, "דיוק האטמוספרה",
                         ["מהיר: extinction.", "יש MODTRAN: spectral."], "נתוני מזג אוויר / MODTRAN.",
                         check=_check_atm_mode),
    "atmosphere.spec_file": K("קובץ העברה ספקטרלית", "העברה לפי אורך גל (ולפי טווח), למשל מ-MODTRAN.", "מחליף את "
                              "מקדם ההנחתה - שולט בגילוי.", 3, "שולט בגילוי", source="MODTRAN / LOWTRAN."),
    "atmosphere.spec_L_km": K("אורך הנתיב של הנתונים", "אורך הנתיב שעמודת העברה בודדת מתייחסת אליו.", "ממנו מחושבת "
                              "ההנחתה בכל טווח. ערך שגוי = הנחתה שגויה.", 2, "שגיאה בהנחתה", source="הגדרות ה-MODTRAN.",
                              check=_check_spec_L),
    "atmosphere.atm.N.T_air_K": K("טמפרטורת האוויר", "טמפרטורת האוויר לאורך הנתיב.", "האוויר פולט קרינת נתיב בטמפרטורה "
                                  "הזו, ובמצב weather היא קובעת את אדי המים.", 1, "קרינת נתיב",
                                  ["288 K (15 °C).", "קיץ במדבר: 305-315 K."], "תנאי התרחיש.", ["להזין בצלזיוס."],
                                  _kelvin(220, 330, "טמפרטורת האוויר")),
    "atmosphere.atm.N.F_PR": K("מקדם קרינת נתיב", "כמה אור מפוזר (או חום) מתווסף לאורך קו הראייה.", "קרינת נתיב "
                               "מורידה את הניגוד בטווח - כמו ערפל לבן. בתחום הנראה ביום זה משמעותי.", 2,
                               "מוריד ניגוד בטווח", ["0.1-0.2."], "MODTRAN / הנחה.", check=_check_F_PR),
    "atmosphere.atm.N.on": K("אטמוספרה פעילה", "האם לחשב טווחים לאטמוספרה הזו (עד שלוש להשוואה).", "השוואה של "
                             "מזג אוויר טוב / ממוצע / גרוע מראה כמה הטווח רגיש לאטמוספרה.", 0, "בחירת פלט",
                             ["דוח לדרישה: שלוש."], "מטרת הניתוח."),
    "atmosphere.atm.N.rh_pct": K("לחות יחסית", "לחות האוויר - יחד עם הטמפרטורה קובעת את אדי המים (בליעה ב-8-14 "
                                 "µm).", "ב-LWIR לחות גבוהה ביום חם מקצרת משמעותית את הגילוי.", 2, "חשובה ב-LWIR",
                                 ["מדבר: 15%-40%.", "חוף: 60%-85%."], "תחנה מטאורולוגית.", check=_check_rh),
    "atmosphere.atm.N.tau0": K("העברה התחלתית", "העברה בטווח אפס - הפסדים שלא תלויים בטווח. בדרך כלל 1.", "מכפילה את "
                               "האות בכל טווח.", 1, "בדרך כלל 1", ["1."], "MODTRAN / הנחה.", check=_check_tau0),
    "atmosphere.path_mode": K("קרינת נתיב: מודל או קובץ", "מודל, או קובץ נפרד של קרינת נתיב.", "קרינת הנתיב לעולם לא "
                              "נגזרת מקובץ ההעברה.", 1, "דיוק", ["model."], "MODTRAN."),
    "atmosphere.path_file": K("קובץ קרינת נתיב", "קרינת נתיב ספקטרלית ב-W/(m² sr µm).", "מורידה את הניגוד בטווח.", 1,
                              "ניגוד בטווח", source="MODTRAN."),
    "atmosphere.path_L_km": K("אורך הנתיב של קרינת הנתיב", "אורך הנתיב שעמודה בודדת מתייחסת אליו.", "ממנו מחושבת "
                              "הקרינה בכל טווח.", 1, "ניגוד בטווח", source="הגדרות ה-MODTRAN.", check=_check_spec_L),

    # ------------------------------------------------------------------ Turbulence
    "turbulence.thermal": K("טורבולנציה בתרמי", "TRM4 מתעלם מטורבולנציה בתרמי. סימון מפעיל אותה (הרחבה).", "בטורבולנציה "
                            "חזקה (צהריים, נתיב קרקעי ארוך) λ/r0 מגיע ל-IFOV גם ב-MWIR / LWIR - ובעיקר בשדה צר.", 2,
                            "חשוב בשדה צר ביום", ["MWIR עם שדה צר, נתיב קרקעי ביום: לסמן."], "התרחיש.",
                            check=_check_turb_thermal),
    "turbulence.exposure": K("סוג MTF הטורבולנציה", "Short: בלי נדידת תמונה. Long: כולל נדידה. Time: לפי זמן החשיפה "
                             "(הרחבה).", "Long שמרני יותר (טשטוש חזק). לצופה וידאו 'time' מדויק יותר.", 2,
                             "שמרני מול אופטימי", ["short (TRM4), או time."], "TRM4 פרק 4.", check=_check_exposure),
    "turbulence.wind_ms": K("רוח צולבת", "מהירות הטורבולנציה לרוחב קו הראייה.", "רוח מהירה מחליפה טורבולנציה בזמן "
                            "החשיפה ומגדילה את הטשטוש ב-MTF תלוי-זמן.", 1, "רק במצב time", ["1-5 m/s ליד הקרקע."],
                            "תחנה מטאורולוגית.", ["להזין בקמ\"ש."], _check_wind),
    "turbulence.se_factor": K("איבר החשיפה הקצרה", "Far: 1/2 (TRM4). Near: 1. Auto: לפי D/√(λL).", "בשדה קרוב (מפתח "
                              "גדול, טווח קצר) Near מדויק יותר ונותן כ-8% יותר טווח הכרה.", 1, "משני",
                              ["far (TRM4), או auto."], "Tofsted 2011."),
    "turbulence.cn2_mode": K("איך מוגדר ה-Cn²", "Fixed: קבוע לאורך הנתיב. Height: תלוי גובה. פרופילים (HV, SLC, "
                             "Greenwood), מזג אוויר, או r0 מדוד.", "ליד הקרקע Cn² גדול בסדר גודל מאשר בגובה - בנתיב "
                             "אלכסוני / מוטס פרופיל גובה הכרחי.", 2, "חשוב בנתיב אלכסוני",
                             ["קרקעי: fixed / height.", "מוטס: hv."], "התרחיש."),
    "turbulence.hv_wind_ms": K("רוח בגובה (HV)", "רוח rms בגובה רב בפרופיל Hufnagel-Valley.", "קובעת את איבר "
                               "הטורבולנציה בטרופופאוזה - רלוונטי רק בנתיב גבוה.", 1, "רק בנתיב גבוה", ["21 m/s (HV 5/7)."],
                               "HV 5/7.", check=_check_wind),
    "turbulence.wx_T_K": K("טמפרטורה (Cn² ממזג אוויר)", "טמפרטורת האוויר לרגרסיה של Sadot & Kopeika.", "ה-Cn² עולה "
                           "חזק עם הטמפרטורה. מחוץ ל-9-35 °C הרגרסיה לא תקפה.", 2, "דרך ה-Cn²", ["298 K (25 °C)."],
                           "תחנה מטאורולוגית.", ["להזין בצלזיוס."], _check_wx_T),
    "turbulence.wx_rh_pct": K("לחות (Cn² ממזג אוויר)", "לחות יחסית לרגרסיה.", "תחום ההתאמה: 14%-92%.", 1, "דרך ה-Cn²",
                              ["40%."], "תחנה מטאורולוגית.", check=_check_rh),
    "turbulence.wx_wind_ms": K("רוח (Cn² ממזג אוויר)", "מהירות רוח לרגרסיה.", "תחום ההתאמה: 0-10 m/s.", 1, "דרך ה-Cn²",
                               ["3 m/s."], "תחנה מטאורולוגית.", check=_check_wind),
    "turbulence.wx_hour": K("שעה זמנית (W)", "שעה ביחס לזריחה, שקובעת את המשקל W ואת מעריך הגובה.", "בצהריים "
                            "הטורבולנציה חזקה פי ~10 מאשר בלילה.", 2, "דרך ה-Cn²", ["צהריים: h5_6."], "שעת התרחיש."),
    "turbulence.wx_W": K("משקל השעה W", "המשקל של השעה ברגרסיה (0.1 בלילה, 1 בצהריים).", "Cn² עולה כמעט ליניארית "
                         "עם W.", 2, "דרך ה-Cn²", ["0.1-1."], "Sadot & Kopeika 1992.", check=_check_wx_W),
    "turbulence.wx_calib": K("מקדם כיול מקומי", "יחס בין Cn² מדוד (סינטילומטר) לחזוי באתר.", "הרגרסיה הותאמה בנגב; "
                             "באתרים אחרים היא עלולה לטעות בסדר גודל. כיול מקומי הוא הדרך היחידה לסמוך עליה.", 2,
                             "דרך ה-Cn²", ["1 = לא מכויל."], "מדידת סינטילומטר.", check=_check_cn2_calib),
    "turbulence.r0_cm": K("פרמטר Fried r0", "קוטר הקוהרנטיות של האטמוספרה. תקף רק עם אורך הגל והנתיב שלו.", "D/r0 "
                          "קובע את הטשטוש: D/r0 > 3 - הטורבולנציה מגבילה את הזיהוי.", 3, "חשוב ב-VIS/SWIR",
                          ["נתיב קרקעי ביום: 1-5 cm (0.55 µm, 1 ק\"מ)."], "מדידה מווידאו / DIMM.", ["להזין במ\"מ."],
                          _check_r0),
    "turbulence.r0_lambda_um": K("אורך הגל של r0", "אורך הגל שבו נמדד r0.", "r0 גדל כמו λ^(6/5): ערך שגוי משנה את "
                                 "הטורבולנציה בתחום שלכם.", 2, "המרת r0", ["0.55 µm."], "המדידה.",
                                 check=_range(0.3, 12, "µm", None)),
    "turbulence.r0_L_km": K("אורך הנתיב של r0", "אורך הנתיב שעליו נמדד r0.", "r0 קטן כמו L^(-3/5).", 2, "המרת r0",
                            ["אורך נתיב המדידה."], "המדידה.", check=_check_spec_L),
    "turbulence.h_ref_m": K("גובה ה-Cn²", "הגובה מעל הקרקע שבו ניתן ערך ה-Cn².", "Cn² יורד עם הגובה: אותו ערך "
                            "ב-2 מ' וב-15 מ' מתאר טורבולנציות שונות מאוד.", 2, "פרשנות ה-Cn²", ["2 מ' (טבלה C.2)."],
                            "המדידה / הטבלה.", check=_check_h_ref),
    "turbulence.time": K("יום / לילה", "פרופיל הגובה של הטורבולנציה: h^-4/3 ביום, h^-2/3 בלילה.", "ביום הטורבולנציה "
                         "יורדת מהר יותר עם הגובה.", 1, "פרופיל הגובה", ["לפי התרחיש."], "התרחיש."),
    "turbulence.L0_m": K("סקאלה חיצונית L0", "סקאלה חיצונית של הטורבולנציה (0 = קולמוגורוב).", "L0 סופי מחליש מעט את "
                         "הטשטוש במפתח גדול.", 1, "משני", ["0, או 1-100 מ' ליד הקרקע."], "ספרות / מדידה.",
                         check=_check_L0),
    "turbulence.mit_model": K("מודל עיבוד נגד טורבולנציה", "Gain: r0 אפקטיבי x גבר. Physical: רישום פריימים ובחירת "
                              "'פריים מזל'.", "עיבוד נגד טורבולנציה מוסיף 10%-25% לטווח ההכרה במערכות שפורסמו.", 1,
                              "רק עם עיבוד", ["gain."], "יצרן העיבוד."),
    "turbulence.mitigation": K("גבר r0 של העיבוד", "פקטור הגדלה של r0 בעיבוד (1 = ללא).", "גבר 2-4 נותן בערך "
                               "+12%-19% בהכרה. ערכים גבוהים יותר אופטימיים.", 2, "רק עם עיבוד", ["1 (ללא)."],
                               "יצרן העיבוד / ספרות.", check=_check_mitig),
    "turbulence.mit_alpha": K("שבר ההטיה שהוסר", "איזה חלק מהטיית התמונה (tilt) הרישום מסיר (0-1).", "השארית מטשטשת את "
                              "הפריימים הממוצעים.", 1, "רק במודל פיזיקלי", ["0.5-0.6."], "Hardie 2021.",
                              check=_fraction("שבר ההטיה")),
    "turbulence.mit_select": K("בחירת 'פריים מזל'", "בוחר בין פריימי המיצוע פריים עם שגיאת פאזה קטנה.", "יעיל ב-D/r0 "
                               "של 3.5-7; מעבר לזה פריימים כאלה נדירים.", 1, "רק במודל פיזיקלי", source="Fried 1978."),
    "turbulence.aniso": K("אבחון אניזופלנטיות", "מציג את הזווית האיזופלנטית ומזהיר כשחלקי המטרה זזים בנפרד.", "לא משנה "
                          "את הטווח - מזהיר על עיוות בתוך המטרה, שפוגע בעיקר בזיהוי.", 0, "אבחון בלבד",
                          ["מסומן בנתיב קרקעי ארוך."], "מטרת הניתוח."),
    "turbulence.scint": K("אבחון סינטילציה", "מציג את תנודות העוצמה של מטרה נקודתית / הארה אקטיבית.", "לא משנה את "
                          "הטווח. חשוב למטרות קטנות מפיקסל ולהארת לייזר.", 0, "אבחון בלבד",
                          ["מסומן עם הארת לייזר."], "מטרת הניתוח."),

    # ------------------------------------------------------------------ Metadata
    "optics.mtf_meta": DOC("תיאור ה-MTF המיובא", "שקלול ספקטרלי או אורך גל, מיקום בשדה, מצב זום ומיקוד."),
    "optics.mtf_band": DOC("תחום הגל של ה-MTF", "תחום הגל שבו חושב או נמדד ה-MTF - צריך להתאים לתחום המצלמה."),
    "optics.mtf_focus": DOC("מצב המיקוד", "מיקוד מיטבי, through-focus או מיקוד מבצעי."),
    "optics.mtf_temp": DOC("טמפרטורת העדשה", "עדשות תרמיות מאבדות מיקוד עם הטמפרטורה."),
    "optics.mtf_uncert": DOC("אי-ודאות ה-MTF", "אי-הוודאות המוצהרת של העקומה המיובאת."),
    "atmosphere.meta.geometry": DOC("גאומטריית הנתיב", "אופקי או אלכסוני, גבהים וטווח של הנתונים האטמוספריים."),
    "atmosphere.meta.source": DOC("מקור הנתונים", "המודל או המקור, למשל גרסת MODTRAN והגדרותיה."),
    "atmosphere.meta.conditions": DOC("תנאי מזג האוויר", "לחות, טמפרטורה, לחץ, ראות ותאריך."),
    "atmosphere.meta.database": DOC("מסד הנתונים הספקטרוסקופי", "למשל HITRAN2024 - נדרש לשחזור."),
    "atmosphere.meta.rt_code": DOC("קוד מעבר הקרינה", "הקוד והגרסה, למשל MODTRAN 6.0."),
    "atmosphere.meta.profile": DOC("פרופיל T-p-h", "פרופיל טמפרטורה-לחץ-לחות וריכוזי גזים."),
    "atmosphere.meta.aerosol": DOC("מודל אירוסול", "מודל האירוסול והראות."),
    "atmosphere.meta.resolution": DOC("רזולוציה ספקטרלית", "רזולוציית הפלט של הספקטרום."),
    "detector.op_mode": DOC("מצב עבודה של החיישן", "הגבר, conversion gain, מצב קריאה וטמפרטורה של ערכי הרעש."),
    "detector.netd_nuc": DOC("מצב העיבוד בבדיקת NETD", "הגבר, NUC ומצב העיבוד. בלי זה נתוני הרעש מסומנים כחלקיים."),
    "basic.roi": DOC("מצב ROI / חלון", "מצב החלון של החיישן. הפורמט בחישוב נלקח ממספר הפיקסלים."),
    "dsp.pl_denoise": DOC("ניקוי רעש פעיל", "ניקוי רעש לא ממודל - מתועד כדי לסמן שהתחזית לא מכסה אותו."),
    "dsp.pl_order": DOC("סדר שלבי העיבוד", "למשל NUC > ניקוי רעש > חידוד > זום."),
    "dsp.pl_version": DOC("גרסת האלגוריתם", "גרסת הקרנל / האלגוריתם של העיבוד."),
    "display.algo_id": DOC("מזהה האלגוריתם", "מזהה / גרסה של אלגוריתם הגילוי."),
    "display.algo_roc": DOC("הגדרת ROC", "איך מוגדר גילוי לאלגוריתם: נקודת ROC, קצב התרעות שווא."),
    "target.scene_id": DOC("מזהה הסצנה", "מזהה הסצנה או מדידת העומס."),

    # ------------------------------------------------------------------ Validation data
    "measured.fom_file": K("עקומת ביצועים מדודה", "MTDP / MRTD / MCP מדודה: 'תדר ערך' או 'תדר h v'.", "Compare: מוצגת "
                           "ליד התחזית. Replace: מחליפה את ה-MTDP המחושב בחישוב הטווח (תרמי).", 1,
                           "רק ב-Replace", source="מדידת מעבדה (STANAG 4349)."),
    "measured.fom_kind": K("סוג העקומה", "MTDP / MRTD (תרמי) או MCP (נראה).", "MRTD שווה ל-MTDP רק במערכת דגומה "
                           "היטב.", 0, "פירוש ההשוואה", source="דוח המדידה."),
    "measured.fom_unit": K("יחידת התדר", "cycles/mrad, cycles/mm או cycles/pixel.", "יחידה שגויה מזיזה את העקומה "
                           "ומבטלת את ההשוואה.", 1, "שגיאה גסה אם טועים", ["cycles/mrad."], "דוח המדידה."),
    "measured.fom_vunit": K("יחידת הטמפרטורה", "K או mK.", "יחידה שגויה = עקומה שגויה פי 1000.", 1,
                            "שגיאה גסה אם טועים", source="דוח המדידה."),
    "measured.fom_use": K("שימוש בעקומה", "Compare: השוואה בלבד. Replace: העקומה המדודה מחליפה את המחושבת.",
                          "Replace משנה את הטווחים לפי המדידה.", 2, "Replace משנה טווחים", ["compare."], "מטרת הניתוח."),
    "measured.sfr_file": K("MTF / SFR מדוד", "MTF ממדידת slanted-edge או bar target.", "להשוואה עם ה-MTF החזוי.", 0,
                           "השוואה", source="ISO 12233."),
    "measured.sfr_kind": K("מה המדידה מכסה", "Device: אופטיקה + גלאי. System: כולל עיבוד ותצוגה.", "קובע מול מה "
                           "משווים.", 0, "השוואה", source="דוח המדידה."),
    "measured.sfr_unit": K("יחידת התדר של ה-SFR", "cycles/pixel מקובל ב-ISO 12233.", "יחידה שגויה מבטלת את ההשוואה.",
                           0, "השוואה", ["cycles/pixel."], "דוח המדידה."),
    "measured.netd_mK": K("NETD מדוד", "NETD שנמדד במעבדה, להשוואה עם ה-NETD של המודל (0 = אין).", "הפרש גדול מצביע "
                          "על נתוני גלאי שגויים במודל.", 0, "השוואה", source="מדידת מעבדה.", check=_check_meas_netd),
    "measured.netd_TB_K": K("טמפרטורת הבדיקה", "טמפרטורת גוף-השחור במדידת ה-NETD.", "צריכה להתאים לטמפרטורת הרקע "
                            "להשוואה הוגנת.", 0, "השוואה", ["300 K."], "דוח המדידה.",
                            check=_kelvin(230, 400, "טמפרטורת הבדיקה")),
    "measured.meta.instrument": DOC("מכשיר / ספסל בדיקה", "המכשיר שבו נמדד."),
    "measured.meta.date": DOC("תאריך", "תאריך המדידה."),
    "measured.meta.method": DOC("שיטה / תקן", "למשל ISO 12233 או STANAG 4349."),
    "measured.meta.focus": DOC("מיקוד", "מצב המיקוד והזום במדידה."),
    "measured.meta.temperature": DOC("טמפרטורה", "טמפרטורת הסביבה והחיישן במדידה."),
    "measured.meta.processing": DOC("עיבוד", "NUC, מסננים, AGC ומיצוע במדידה."),
    "measured.meta.uncertainty": DOC("אי-ודאות", "אי-ודאות המדידה המוצהרת."),
    "measured.meta.config_id": DOC("מזהה תצורה", "מספר סידורי, קושחה ועדשה. אם הוא שונה מהפרופיל - מוצגת אזהרה."),
    "measured.meta.firmware": DOC("קושחה", "קושחת המצלמה במדידה."),
    "measured.meta.op_mode": DOC("מצב הגבר / קריאה", "מצב ההגבר והקריאה במדידה."),
    "measured.meta.frame_rate": DOC("קצב פריימים", "קצב הפריימים במדידה."),
    "measured.meta.roi": DOC("חלון", "חלון / ROI במדידה."),
    "measured.meta.exposure": DOC("חשיפה", "זמן החשיפה / האינטגרציה במדידה."),
    "measured.meta.f_number": DOC("F-number", "ה-F של העדשה במדידה - NETD ו-MRTD תלויים בו."),
    "measured.meta.raw_files": DOC("קובצי RAW", "הפניות לקובצי ה-RAW של המדידה."),
    "measured.meta.calib_id": DOC("מזהי כיול", "מקורות הכיול (גוף שחור, קולימטור) הניתנים למעקב."),
}
