# שיקולי מערכת במדריך: גודל, משקל ועיוותים בתמונה

מסמך רקע למודול `trm4/guide_design_he.py` (גרסה 2.14). המדריך מציג, לצד ההשפעה על הטווח, מה ערכי השדות מחייבים
מהמערכת: גודל ומשקל, וסטיות ועיוותים בתמונה. **שום דבר מכאן לא נכנס לטווחים של TRM4.** הטווח מחושב על הציר עם MTF
אחד לכל השדה. הסטיות נכנסות לטווח רק דרך מודל הסטיות (q / blur) או דרך MTF מיובא. כל המספרים הם הערכות הנדסיות
מסדר ראשון לגודל ראשוני, ותכנון אופטי ודפי נתונים מחליפים אותם.

## 1. סטיות: איך הן גדלות עם F ועם השדה

בתאוריית Seidel, עם גובה קרן y במפתח וגובה תמונה h: כדורית ∝ y³, קומה ∝ y²h, אסטיגמטיזם ועקמומיות שדה ∝ yh²,
עיוות ∝ h³ (Dube, opticallimits). בטשטוש זוויתי, כפונקציה של F ושל חצי השדה θ:

| סטייה | טשטוש זוויתי | מה מגדיל אותה |
|---|---|---|
| כדורית | ∝ 1/F³ | עדשה מהירה (קוטר גדול לאותו מוקד) |
| קומה | ∝ θ/F² | עדשה מהירה + שדה |
| אסטיגמטיזם / עקמומיות שדה | ∝ θ²/F | שדה רחב |
| עיוות גאומטרי | ∝ θ³, לא תלוי ב-F | שדה רחב; לא מטשטש - מזיז את התמונה |

המקור לשורות הטשטוש הזוויתי: arXiv 2608.07784. אלה קירובים לשדה ומפתח קטנים. בעדשות מהירות מאוד או רחבות מאוד
נכנסים גם סדרים גבוהים. במדריך מוצג **מדד קושי**: היחס לעדשה ייחוס F/2 בחצי שדה של 2.5° (נמוך ≤ 1.5, בינוני ≤ 6,
גבוה מעל 6). זה לא ערך טשטוש.

עיוות טיפוסי בפינת השדה (כלל אצבע לפי חצי השדה האלכסוני): עד 5° - 0.1%-0.5%; 5°-15° - 0.5%-2%; 15°-30° - 2%-5%;
30°-45° - 5%-10%; מעבר לזה - עין דג. ההזזה בפיקסלים = אחוז העיוות x חצי האלכסון בפיקסלים.

הארה בפינה ≈ cos⁴θ, בלי ויגנטינג.

## 2. עומק מוקד ותזוזת מוקד עם הטמפרטורה

- **עומק מוקד:** ±2λF² (קריטריון רבע גל, Rayleigh / Maréchal). ב-LWIR ב-F/1 זה כ-±20 µm, וב-MWIR ב-F/4 כ-±130 µm.
- **תזוזת המוקד** של אלמנט דק בבית באורך ~f: Δf ≈ f·(γ + α_H)·ΔT, כאשר γ = (dn/dT)/(n−1) − α הוא הקבוע התרמו-אופטי
  ו-α_H הוא מקדם ההתפשטות של הבית (אלומיניום ≈ 23e-6/K). הנוסחה מדוח Arizona optomechanics; סימני הכיוון משתנים בין
  מקורות.

| חומר | γ [1/K] | צפיפות [g/cm³] | מקור |
|---|---|---|---|
| גרמניום (LWIR) | 126e-6 (dn/dT 396e-6, n ≈ 4, α 5.7e-6) | 5.33 | Umicore |
| כלקוגניד (GASIR) | ~23.5e-6 - קרוב ל-α_H, ולכן מאפשר אתרמליזציה פסיבית | ~4.4 | Umicore / SPIE |
| סיליקון (MWIR) | ~63e-6 (dn/dT ~160e-6, n ≈ 3.43) | 2.33 | הערכה מערכי ספרות |
| זכוכית אופטית (BK7) | ~−1.3e-6 - הבית שולט | ~2.5 | הערכה מערכי ספרות |

המדריך מחשב את התזוזה עבור ΔT = ±40 K ומשווה אותה לעומק המוקד. כשהיא גדולה ממנו, מופיעה הערת תכנון: ודאו שהעדשה
אתרמלית (פסיבית אופטית או מכנית) או עם מיקוד מנועי.

## 3. גודל ומשקל

- **אורך העדשה (track):** עדשה שבירה פשוטה ≈ 1.0-1.3 f; טלפוטו (f > 150 mm) ≈ 0.6-0.9 f; מקופלת / קטדיופטרית
  (f > 500 mm) ≈ 0.3-0.5 f.
- **העדשה הקדמית:** ≈ 1.1 D כשהאישון בחזית. עם cold stop בגלאי (מקורר, 100% יעילות מגן) האישון מאחור, והעדשה הקדמית
  ≈ D + 2·L·tanθ.
- **משקל:** כמה אלמנטים (2-3 ב-IR, ועוד אחד בשדה רחב, ועוד 3 בנראה / SWIR לתיקון כרומטי), עובי ≈ 8% מהקוטר. משקל
  הזכוכית × 1.6-2.5 עבור הבית. התוצאה גדלה בערך כמו D² עד D³.
- **פסיעה:** לאותו IFOV ולאותו F, המוקד והקוטר יחסיים לפסיעה, ולכן משקל העדשה ∝ פסיעה³ (17 → 12 µm: כשליש).
- **ליבה:** מכלול Dewar-cooler מקורר כ-200-600 g, עם הספק של וואטים בודדים בעבודה ויותר בקירור הראשוני. ליבה
  לא-מקוררת 640 בפסיעה 12 µm: כ-25 g ומעלה (Xenics MicroCube 640: פחות מ-25 g). ערכי הספק של ליבות לא-מקוררות לא
  נמצאו במקורות שנבדקו; כאן הם הערכה כללית.
- **ייצוב:** כדי שהריצוד לא יגביל, ריצוד שיורי של עד 0.3 IFOV. מעל 100 µrad - חצובה; 20-100 µrad - ייצוב רכב / גימבל
  בינוני; פחות מ-20 µrad - גימבל איכותי.
- **טורבולנציה:** r0 = (0.423 k² Cn² L)^(-3/5) לגל מישורי ול-Cn² קבוע. מעבר ל-D ≈ 3 r0 הגדלת הקוטר כמעט לא משפרת
  רזולוציה ביום.

## 4א. ייצור ועלות (נוסף בגרסה 2.17)

המדריך מציג לשדות המשפיעים גם "ייצור ועלות". אלה כיווני מגמה ולא מחירים: מחירים אמיתיים מגיעים מהצעות מחיר.

- **גרמניום:** מחיר המתכת באירופה (99.999%) עלה מכ-$3,150 לק"ג בינואר 2025 לכ-$5,380 באוקטובר; הממוצע השנתי
  ב-2025: כ-$4,100 לק"ג למתכת (USGS, Mineral Commodity Summaries 2026). בתחילת 2023 המחיר היה מעט יותר מ-$1,000
  (Fastmarkets). הסיבה: מגבלות ייצוא של סין (רישיון מאוגוסט 2023, איסור לארה"ב מדצמבר 2024). המחיר בסין עצמה נמוך
  יותר (Project Blue) - השוק התפצל.
- **הערכת חומר הגלם:** משקל הזכוכית של העדשה (פרק 3, בלי הבית) כפול 1.5-3 לפחת עיבוד (גלם, השחזה, פסולת), כפול
  $4,100 לק"ג. ב-MWIR רק חצי מהמשקל נספר כגרמניום (חלק מהאלמנטים מסיליקון). זו עלות החומר בלבד - לפני ליטוש, חריטה,
  ציפוי, בית והרכבה, שהם בדרך כלל רוב המחיר.
- **קוטר ו-F:** לפי ספקים, עדשה ב-F/1.0 עולה פי 2-3 מאותה עדשה ב-F/1.5 (יותר חומר ופסולת גבוהה יותר). גידול גביש
  גרמניום בקוטר 100 mm ומעלה הוא אתגר ייצורי (DRDO). ציפוי AR איכותי ל-LWIR: 20%-30% מעלות ייצור העדשה (מקור ספק, לא
  מאומת).
- **כלקוגניד מול גרמניום:** בכבישה (precision molding) ומעל כ-1,000 יחידות, כלקוגניד זול יותר מגרמניום בחריטת יהלום;
  בכמויות קטנות חריטת יהלום זולה יותר (LightPath). ב-GASIR הגרמניום הוא רק כ-20% מהחומר (Umicore).
- **מקורר מול לא-מקורר:** מקרר Stirling: MTTF של כ-8,000-20,000 שעות לפי מדריכי ספקים, ו-27,000 שעות ל-FL-100 של
  Teledyne FLIR (Inside GNSS). בעבודה של 8 שעות ביום: כ-3-9 שנים עד תחזוקה. לא-מקורר: בלי חלקים נעים. מקור בתעשייה
  טוען שמעל מוקד של כ-350 mm עלות עדשת הלא-מקורר עוברת את עלות מערכת מקוררת שלמה (טענה יחידה, לא מאומתת).
- **פסיעה ופורמט:** פיקסל קטן = שבב קטן = יותר שבבים בפרוסה ומחיר נמוך יותר לגלאי (Umicore: מ-50 µm ל-12 µm כ-17
  פי יותר גלאים בפרוסה - גבול עליון תאורטי); אבל 10-12 µm עלולים לחייב עדשת F/1.0 שמבטלת את החיסכון (Tech Briefs).
  שבב גדול = פחות שבבים בפרוסה ותפוקה נמוכה (פטנט US 9410850).
- **SWIR:** גלאי InGaAs יקרים בהרבה מ-CMOS, וגלאי שטח InGaAs כפופים לעיתים ל-ITAR או ל-EAR (6A003.b.4.a).

מגבלות: רוב נתוני העלות מגיעים מספקים או מאתרי שוק; המחירים משתנים מהר. המדריך מציג אותם כ"לפי ספקים" או עם שנת
המקור, ולא כמחירים.

## 4. מה לא נבדק ומגבלות

- מספרי המשקל והאורך הם כללי אצבע ולא מחליפים תכנון.
- ההספק של ליבות מקוררות לפי מקור שיווקי (20-60 W למערכת שלמה); בפועל הערך תלוי מאוד בדגם המקרר. המדריך כותב
  "וואטים בודדים ועד עשרות בקירור הראשוני".
- הערכים של Si ו-BK7 לא אומתו מול טבלת יצרן בחיפוש הזה.

## מקורות

- Umicore, *Designing athermal lenses for LWIR systems*: https://www.umicore.com/en/newsroom/athermal-lenses-for-lwir-systems/
- Umicore, *Using material advances in chalcogenide glasses ...*: https://eom.umicore.com/en/infrared-optics/featured-articles/using-material-advances-in-chalcogenide-glasses-to-improve-imaging-lenses-in-the-8-14-m-waveband-2
- University of Arizona, optomechanics report (thermal focus shift): https://wp.optics.arizona.edu/optomech/wp-content/uploads/sites/53/2016/10/irvin_report_01.pdf
- arXiv 2608.07784 (aberration scaling with N and θ): https://arxiv.org/pdf/2608.07784
- B. Dube, opticallimits.com (Seidel dependencies): https://opticallimits.com/?p=3823
- Umicore, *Evaluate depth of field limits of fixed focus lens arrangements in thermal infrared*: https://www.umicore.com/en/newsroom/evaluate-depth-of-field-limits-of-fixed-focus-lens-arrangements-in-thermal-infrared/
- Wikipedia, *Depth of focus*: https://wikipedia.com/wiki/Depth_of_focus
- Xenics LWIR MicroCube 640 leaflet: https://www.exosens.com/system/files/2024-04/Xenics_LWIR_MicroCube%20640_Leaflet.pdf
- Cooled vs uncooled thermal camera cores (vendor guide): https://irhubs-2026.pages.dev/information/news/cooled-vs-uncooled-thermal-camera-cores/
- Wavelength Electronics, *Replacing Germanium with Chalcogenide Glass*: https://us.wavelength-oe.com/application-notes/infrared-optics/ge-to-chalcogenide
- USGS, *Mineral Commodity Summaries 2026 - Germanium*: https://pubs.usgs.gov/periodicals/mcs2026/mcs2026-germanium.pdf
- Fastmarkets, *China's export curbs on gallium and germanium*: https://www.fastmarkets.com/insights/are-chinas-export-curbs-on-gallium-and-germanium-a-political-symbol-or-a-real-threat/
- Project Blue, *US and EU germanium prices surge*: https://projectblue.com/blue/news-analysis/1303/us-and-eu-germanium-prices-surge-as-material-remains-scarce-
- Inside GNSS, *Understanding cryocooled infrared system reliability*: https://insidegnss.com/?p=189069
- LightPath, *Investigation of As40Se60 chalcogenide glass in precision glass molding*: https://www.lightpath.com/wp-content/uploads/2021/03/Investigation-of-As40Se60-chalcogenide-glass-in-precision-glass.pdf
- Umicore, *GASIR*: https://www.umicore.com/en/markets-products/optics/infrared-optics/gasir/
- Why are infrared lenses so expensive (vendor article): https://irhubs-2026.pages.dev/information/news/why-are-infrared-lenses-so-much-more-expensive-than-standard-lenses/
- DRDO, germanium single-crystal growth: https://drdo.gov.in/drdo/sites/default/files/inline-files/GermaniumSCGfIO12032025.pdf
- Umicore, *The evolution of lens designs for 12 micron uncooled LWIR detectors*: https://www.umicore.com/en/newsroom/the-evolution-of-lens-designs-for-12micron-uncooled-lwir-detectors/
- Tech Briefs, *Trends in thermal imaging*: https://www.techbriefs.com/component/content/article/28511-trends-in-thermal-imaging
- US patent 9410850 (die size and yield): https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9410850
- Princeton Infrared Technologies, ITAR-free SWIR camera (EAR 6A003.b.4.a): https://www.gophotonics.com/news/details/636-princeton-infrared-technologies-launches-first-megapixel-swir-camera-with-no-itar-export-restrictions
