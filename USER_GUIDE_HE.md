<div dir="rtl">

# TRM_HADMAAv1 – מדריך התקנה ושימוש

תוכנה לחישוב טווחי גילוי, זיהוי והזדהות (DRI) של מערכות הדמאה – תרמיות, נראות ו־SWIR – לפי המודל TRM4.v3 של Fraunhofer IOSB.

## 1. התקנה

**דרישות:** Windows 10 או 11, ‏64 ביט. אין צורך ב־Python ואין צורך בהרשאות מנהל.

1. מעתיקים את קובץ ההתקנה (למשל `TRM_HADMAAv1_Setup_2.11.exe`) למחשב ולוחצים עליו לחיצה כפולה.
2. אם מופיעה ההודעה **"Windows protected your PC"** (הקובץ אינו חתום דיגיטלית): לוחצים **More info** ואז **Run anyway**.
3. בוחרים שפה, מסמנים אם רוצים קיצור דרך בשולחן העבודה, ולוחצים **Install**.
4. בסיום, אפשר לסמן **Launch** כדי לפתוח את התוכנה מיד.

התוכנה מותקנת בתיקייה `%LOCALAPPDATA%\Programs\TRM_HADMAAv1`. ההגדרות האישיות (קבצים אחרונים, הודעות שנקראו) נשמרות ב־`%APPDATA%\TRM4`.

**הסרה:** הגדרות Windows ← אפליקציות ← TRM_HADMAAv1 ← הסר. אפשר גם דרך תפריט התחל ← TRM_HADMAAv1 ← Uninstall.

## 2. פתיחת התוכנה

תפריט **התחל** ← **TRM_HADMAAv1**, או הקיצור בשולחן העבודה.

## 3. החישוב הראשון – חמש דקות

1. **File ← New from template** ובוחרים תבנית קרובה למערכת שלכם, למשל *Thermal - LWIR cooled staring 640x512*.
2. בסרגל השמאלי בוחרים **זרימת עבודה**:
   - **Quick Prediction** – מעט שדות, להערכה מהירה.
   - **Engineering Analysis** – כל הפרמטרים לפי עמודים.
   - **Laboratory & Image Evaluation** – כולל נתוני מדידה ואימות.
3. מעדכנים את פרטי המערכת: מוקד ואפרטורה (**Optics**), גלאי (**Detector geometry / sensitivity**), מטרה (**Target & scenario**) ואטמוספרה (**Atmosphere & turbulence**). לכל שדה יש הסבר במעבר עכבר.
4. לוחצים **Calculate** (או **F5**).
5. בעמוד **Summary** מוצגים טווחי הגילוי, הזיהוי וההזדהות. בעמודים **Range**, **MTF** ו־**System data** מוצגים הפרטים, ובעמוד **Messages** האזהרות וההנחות.

> מספר לא נכון אינו "מגן": כל טווח מוצג עם ההנחות שלו. כדאי לקרוא את העמוד **Messages** לפני שמשתמשים בתוצאה.

## 4. פעולות נפוצות

| מה רוצים | איפה |
|---|---|
| הערכה גסה בלי חישוב מלא | **Run ← Quick geometric estimate** |
| לבחור גלאי מהקטלוג | **Run ← Detector lookup** (‏Ctrl+D) |
| מה מגביל את הטווח | **Run ← Limiting factors** |
| המלצות לשיפור הטווח | **Run ← Improve performance (advisor)** |
| השפעת פרמטר אחד על הטווח | **Run ← Parameter sweep** |
| טווח עם אי־ודאות (RSS / Monte Carlo) | **Run ← Uncertainty study** |
| השוואת כמה תרחישים | **Run ← Scenario comparison** |
| טווחי P80 / P90 או TTP / V50 | עמוד **Target & scenario** ← *Probability and clutter* |
| טורבולנציה בנתיב אווירי | **Atmosphere & turbulence** ← *Cn2 - Hufnagel-Valley altitude profile*, או פרופיל SLC / ‏Greenwood / ‏Brookner (ממעיטים בטורבולנציה ליד הקרקע) |
| Cn2 מנתוני מזג אוויר (טמפרטורה, לחות, רוח ושעה ביום) | **Atmosphere & turbulence** ← *Cn2 from the weather* – זמני (PROVISIONAL), צריך כיול מקומי |
| האם המטרה "מתעוותת" בתוך עצמה (anisoplanatism) | **Atmosphere & turbulence** ← *Anisoplanatism diagnostic*; התוצאות ב־**System data** |
| הבהוב (scintillation) של מטרה נקודתית או תת־פיקסלית, או בתאורה אקטיבית (לייזר) | **Atmosphere & turbulence** ← *Scintillation diagnostic*; התוצאות ב־**System data**. תקף בטורבולנציה חלשה בלבד; מחוץ לתחום מוצג דגל |
| טורבולנציה לצופה בווידאו (זמן שילוב העין ורוח רוחבית) | **Atmosphere & turbulence** ← *Type of MTF: Exposure-time dependent* |
| טווחים לפי שעה ביום ועונה (סטטיסטיקת Cn2) | לשונית **Sensitivity** ← *Cn2 statistics* (אפשר גם h^-2/3 ליום מעונן או חורפי) |
| מודל פיזיקלי לעיבוד נגד טורבולנציה | **Atmosphere & turbulence** ← *Mitigation processing model: Physical* |
| מדידת r0 מווידאו של המצלמה | **Run ← Lab: turbulence r0 from a frame sequence** – סצנה סטטית, לפחות 50 פריימים |
| פלט וידאו 8 ביט / AGC | **Signal processing** ← *Tone mapping / AGC* (פרמטרים מתקדמים) |
| MTF מתמונת קצה אלכסוני | **Run ← Lab: slanted-edge SFR from an image** |
| אפיון מצלמה מפריימים של flat ו־dark | **Run ← Lab: photon transfer (EMVA 1288)** |
| דוח טקסט | **File ← Export report** (‏Ctrl+E) |
| דוח DRI בעברית (PDF) | **File ← Export Hebrew DRI report (PDF)** |
| שמירת הפרויקט | **File ← Save** (‏Ctrl+S) – קובץ ‎.json |

## 5. מקורות הנתונים

לצד כל שדה מופיע סימון של **מקור הנתון**: מדוד, דף נתונים, הנחה וכדומה. לוחצים עליו כדי לשנות. הדוחות מציגים לכל טווח על אילו נתונים הוא נשען. ערך שמסומן *preset* או *assumed* הוא ערך כללי, ועדיף להחליף אותו בנתון של המערכת שלכם.

## 6. הרחבות שאינן חלק מ־TRM4

מדדים כמו P80/P90, ‏TTP/V50, עומס רקע (clutter), דעיכה מנתוני מזג אוויר, פרופילי Cn2 (Hufnagel-Valley, ‏SLC, ‏Greenwood, ‏Brookner), ‏Cn2 ממזג אוויר, אבחוני anisoplanatism ו־scintillation ומיפוי טונים מסומנים בכל מקום כ־**extension**. רובם כבויים כברירת מחדל. כשהם כבויים, הטווחים זהים לאלה של TRM4.

## 7. בעיות נפוצות

| בעיה | פתרון |
|---|---|
| Windows חוסם את ההתקנה | **More info ← Run anyway**. במחשב ארגוני ייתכן שצריך אישור IT. |
| האנטי־וירוס מסמן את הקובץ | זה קורה לפעמים לתוכנות שנארזו עם PyInstaller. בודקים מול מקור הקובץ ומאשרים חריגה. |
| "Calculation error" | ההודעה מציינת איזה ערך לא תקין, למשל אפרטורה 0 או Cn2 שלילי. מתקנים ומחשבים שוב. |
| התוכנה איטית | Visible עם טורבולנציה, ה־advisor וניתוחי אי־ודאות לוקחים זמן. ההתקדמות מוצגת בשורת המצב. |

## 8. עזרה

**Help ← Model documentation (PDF)** (‏F1) פותח את התיעוד המלא של המודל. **Help ← Keyboard shortcuts** מציג את קיצורי המקלדת.

</div>
