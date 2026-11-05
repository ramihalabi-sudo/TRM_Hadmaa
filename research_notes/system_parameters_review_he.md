# בדיקת המחקר "חקר פרמטרי מערכת עם שיקולים מערכתיים"

מסמך רקע לגרסה 2.19: השיעור "שיקולים מערכתיים: משקל, עלות ובדיקות" במדריך (`guide_he.LESSONS`, id `system`),
ניתוח הרגישות החי בכרטיסי השדות (`guide_design_he.sensitivity` / `spoken_sensitivity`) והשיקולים החדשים של NETD, רעש
הקריאה וקצב הפריימים (`guide_design_he.COST`). **שום דבר מכאן לא משנה את הטווחים של TRM4.**

כל טענה במחקר נבדקה מול דפי נתונים של יצרנים, תקנים וספרות. מה שלא נמצא לו מקור לא נכנס למדריך.

## 1. מה שימרנו

| נושא | במחקר | הבדיקה |
|---|---|---|
| קוטר המפתח | D = f/F; 50 mm ב-f/1.4 ≈ 35 mm, ב-f/4 ≈ 12.5 mm | נכון (50/1.4 = 35.7) |
| IMX174 | פיקסל 5.86 µm; 50 fps ב-GigE, 155 fps ב-USB3 | תואם Basler ace (acA1920-50gm / -155um) |
| FLIR Lepton | NETD < 50 mK; 160x120 / 80x60; פסיעה 12 / 17 µm; ~8.6 Hz | תואם דף הנתונים של Lepton 3 / 3.5 |
| טווח דינמי | 20 log(FW / רעש) | נכון (הגדרת EMVA 1288) |
| VOx מול a-Si | VOx רגיש יותר ויקר יותר לייצור; a-Si נוח יותר לייצור | נכון בכיוון: VOx לא תואם לקו CMOS ודורש קו ייעודי |
| Rolling / Global | Global מונע עיוות בתנועה; Rolling זול יותר | נכון (כבר במדריך מגרסה 2.14) |
| בדיקות | NETD מול גוף שחור, MTF בטבלת בדיקה, רעש בחושך | נכון; הוספנו את התקנים (פרק 3) |

## 2. מה שינינו

| נושא | במחקר | הערך הנכון | מקור / חישוב |
|---|---|---|---|
| משקל מול מוקד | +10% מוקד → +15% משקל; +50% → +50% | באותו F הקוטר גדל עם המוקד, ומשקל הזכוכית ∝ D³ (שטח x עובי): +10% → כ-+33%, +50% → פי 3.4 | 1.1³ = 1.33, 1.5³ = 3.38; מודל המשקל של `guide_design_he.estimates` |
| F מ-f/4 ל-f/8 | קוטר -50%, משקל כ-20%- | הקוטר נחצה, משקל הזכוכית יורד לשמינית עד רבע | ∝ D² עד D³ |
| רזולוציה +10% | שטח השבב +10% | +10% בכל ציר = +21% פיקסלים ושטח | 1.1² |
| רעש קריאה IMX174 | ~2.6 e⁻ | כ-7 e⁻; QE כ-70% ב-545 nm; באר כ-32 ke⁻; DR כ-74 dB | Basler EMVA Data Overview |
| "VOx מקורר" | הצעה ל-"VOx מקורר עם f/1.4" ו-"קריוגניקה" להורדת NETD | VOx ו-a-Si הם תמיד לא-מקוררים. גלאים מקוררים: InSb, MCT, T2SL / XBn | ספרות המיקרובולומטרים |
| TCR | ל-VOx TCR גבוה יותר | דומה: VOx כ-2%-3%-/K, a-Si דומה או גבוה יותר. היתרון של VOx הוא רעש 1/f נמוך | MDPI Nanomaterials 2025; SPIE 9070 |
| NETD של a-Si | 50-80 mK | מיושן; ליבות של היום ב-12 µm: פחות מ-50 mK, ו-VOx (Boson+ Industrial) ≤ 20 mK | Boson+ datasheet Rev 114 |
| שיפור NETD | דורש גלאי מקורר, +50%-100% עלות | NETD ∝ F²: מ-F/1.4 ל-F/1.0 חוצה את ה-NETD. לרוב הדרך הזולה היא עדשה מהירה | Teledyne FLIR knowledge base |
| זרם חושך | "עשרות אלפי e⁻/s" ב-CMOS רגיל | יחידות עד עשרות e⁻/s לפיקסל בטמפרטורת החדר; מוכפל כל ~6-8 °C | arXiv 1412.4031; Photometrics |
| עלות קצב פריימים | +10% קצב → +5%-10% עלות; +50% → +20%-30% | אין מקור; הוחלף בקצב הנתונים = פיקסלים x ביטים x קצב | חישוב |
| BOM של Lepton | חיישן $80-100, PCB $30 ועוד | אין מקור; הוסר. נשאר רק המחיר הקמעונאי: כ-$164 ב-GroupGets | GroupGets |

## 3. מה הוספנו

- **ניתוח רגישות חי** בכרטיסי השדות (מוקד, קוטר / F, פסיעה, פורמט, קצב): ‎-50% עד +50%, מחושב על המערכת של המשתמש
  עם אותו מודל משקל של `estimates()`. זה מחליף את טבלאות הרגישות של המחקר, שלא היו עקביות (למשל משקל +50% בטבלה
  ו-+150% בטקסט לאותו שינוי).
- **פסיעה באותו IFOV:** משקל העדשה ∝ פסיעה³ - היתרון המערכתי הגדול של פיקסל קטן, שהמחקר לא הזכיר.
- **NETD ∝ F²** וההשוואה רק באותם תנאים (F וטמפרטורת רקע).
- **סף הייצוא של 9 Hz:** מצלמה תרמית לא-מקוררת עד 9 Hz - ECCN 6A993; מעל 9 Hz - 6A003.b.4.b, עם רישיון לרוב היעדים.
  זו הסיבה ש-Lepton עובד ב-8.6-8.7 Hz. רקע הנדסי בלבד; הסיווג משתנה ויש לבדוק אותו מול ה-EAR העדכני.
- **קצב נתונים:** 640x512, 14 ביט, 60 Hz ≈ 275 Mbit/s; 1920x1080, 14 ביט, 50 Hz ≈ 1.45 Gbit/s (מעבר ל-GigE).
- **תקני מדידה:** EMVA 1288 (QE, רעש, באר, זרם חושך, DR); ISO 12233 (MTF בקצה נטוי, כ-5°); ASTM E1543 (NETD -
  practice, גרסת 2014 שאושרה מחדש ב-2022; במקור נכתב למערכות סורקות) ו-ASTM E1213 (MRTD).

## 4. מגבלות

- כללי המשקל הם מסדר ראשון (ראו `system_considerations_he.md`, פרק 3). במעבר בין סוגי עדשות (שבירה / טלפוטו) היחס
  יכול לקפוץ - המודל מציג את הקפיצה כמו שהיא.
- נתוני IMX174 נלקחו מטבלת סיכום של Basler; דוח EMVA מלא של מצלמה ספציפית עדיף.
- המחיר של Lepton הוא מחיר קמעונאי ליחידה ומשתנה.

## מקורות

- Basler, *EMVA Data Overview*: https://cdn.graftek.com/system/files/13429/original/Basler_EMVA_Data_Overview.pdf
- Teledyne FLIR, *Lepton 3 / 3.5 datasheet*: https://www.mouser.com/datasheet/2/227/Lepton3_3_5_Data_Sheet-2580086.pdf
- Teledyne FLIR, Lepton product page (8.6 Hz, exportable): https://oem.flir.com/products/lepton/
- Teledyne FLIR, *Boson+ product datasheet Rev 114*: https://www.acalbfi.com/nl/file/16133/Boson-Plus-Product-Datasheet-Rev-114.pdf
- Teledyne FLIR, *Relationship between lens f-number and NEdT*: https://oem.flir.com/de/support/support-center/knowledge-base/what-is-the-relationship-between-lens-f-number-and-camera-performance-or-nedt/
- *Convergence of thermistor materials and FPAs in uncooled microbolometers* (Nanomaterials 2025): https://www.mdpi.com/2079-4991/15/17/1316
- *Evaluation of 1/f noise in prospective IR imaging thin films* (SPIE 9070): https://spiedigitallibrary.org/conference-proceedings-of-spie/9070/90701P/Evaluation-of-1-f-noise-in-prospective-IR-imaging-thin/10.1117/12.2054652.full
- *Materials for microbolometers: vanadium oxide or silicon derivatives* (SPIE 10209): https://ui.adsabs.harvard.edu/abs/2017SPIE10209E..0MV/abstract
- *High-level numerical simulations of noise in CCD and CMOS photosensors* (arXiv 1412.4031): https://arxiv.org/pdf/1412.4031
- Photometrics, *Dark current*: https://photometrics.com/learn/imaging-topics/dark-current
- Axis, *US export fact sheet* (6A993 / 6A003, 9 Hz): https://www.axis.com/files/conformity/US-export_fact_sheet-EU_sensors_en_1706.pdf
- Federal Register 2024-03661 (6A993.a, 9 Hz): https://www.govinfo.gov/content/pkg/FR-2024-02-23/pdf/2024-03661.pdf
- ASTM E1543: https://store.astm.org/e1543-00.html
- ISO 12233 slanted edge (Burns, PICS 2000): https://www.imaging.org/common/uploaded%20files/pdfs/Papers/2000/PICS-0-81/1621.pdf
- GroupGets, FLIR Lepton 3.5: https://groupgets.com/products/flir-lepton-3-5
