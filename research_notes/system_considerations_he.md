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
