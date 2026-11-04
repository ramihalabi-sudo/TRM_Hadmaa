"""The narrator as a teacher: what the guide says out loud, written to be heard, not read.

The screen shows reference text; the narrator teaches it.  For the core fields LESSON holds a short spoken lesson in
each language: an opening that says why we stop at this field ("intro"), an intuitive explanation or analogy
("idea") and the one thing to remember ("bottom").  guide_voice.field_script puts them round the reference material
(why it matters, typical values, the mistakes people make), the check of the user's own value and the computed effect
on the ranges.  Every other field gets the same structure from FRAME: openings, transitions and closings that depend
on how strongly the field moves the range, varied from field to field so that the narration does not sound like a
template.
"""
import hashlib

LESSON = {
    "category": {
        "he": ("נתחיל מההחלטה הכי בסיסית בפרויקט: איזה סוג חיישן יש לנו.",
               "תחשבו על זה ככה: מצלמה תרמית רואה חום, כמו שאתם מרגישים חום של כביש בקיץ גם בלילה. מצלמת יום או "
               "SWIR רואה אור שחוזר מהעצמים, בדיוק כמו העין שלנו. המודל צריך לדעת באיזה עולם אנחנו, כי בכל עולם "
               "הניגוד נוצר אחרת.",
               "אז הכלל פשוט: רואה חום, Thermal. רואה אור מוחזר, Visible."),
        "en": ("Let's start with the most basic decision of the project: what kind of sensor we have.",
               "Think of it this way: a thermal camera sees heat, the way you can feel the heat of a road on a summer "
               "night. A day camera or a SWIR camera sees light bouncing off things, just like your eye. The model "
               "has to know which world it is in, because in each world the contrast is created differently.",
               "So the rule is simple: if it sees heat, it is Thermal. If it sees reflected light, it is Visible."),
    },
    "imager_type": {
        "he": ("עכשיו, באותה מצלמה תרמית, יש שתי משפחות שונות מאוד של גלאים.",
               "גלאי מקורר הוא כמו מצלמה מקצועית עם מקרר קטן מאחור: הוא רגיש מאוד, אבל כבד ויקר. גלאי לא-מקורר, "
               "מיקרובולומטר, הוא כמו מדחום זעיר בכל פיקסל: פשוט, קל וזול, אבל איטי ורגיש פחות.",
               "אם יש למצלמה מקרר סטירלינג, היא מקוררת. אם היא קלה ופועלת מיד, היא כמעט בטוח לא-מקוררת."),
        "en": ("Now, within thermal cameras there are two very different families of detectors.",
               "A cooled detector is like a professional camera with a small refrigerator behind it: very "
               "sensitive, but heavy and expensive. An uncooled detector, a microbolometer, is like a tiny "
               "thermometer in every pixel: simple, light and cheap, but slower and less sensitive.",
               "If the camera has a Stirling cooler, it is cooled. If it is light and works right away, it is almost "
               "certainly uncooled."),
    },
    "mode.environment": {
        "he": ("השדה הזה קובע איפה אנחנו מודדים את המערכת: בשטח או על שולחן המעבדה.",
               "במעבדה מסתכלים על המצלמה בלי אוויר באמצע, כאילו המטרה צמודה לעדשה. בשטח יש קילומטרים של אוויר, "
               "אובך וטורבולנציה בין המצלמה למטרה, ורק שם יש משמעות לטווח.",
               "רוצים טווחים בקילומטרים? בוחרים Field. תמיד."),
        "en": ("This field sets where we evaluate the system: in the field, or on the laboratory bench.",
               "In the lab we look at the camera with no air in between, as if the target were right at the lens. "
               "In the field there are kilometers of air, haze and turbulence between the camera and the target, "
               "and only there does a range mean anything.",
               "Do you want ranges in kilometers? Choose Field. Always."),
    },
    "mode.stream": {
        "he": ("שאלה קטנה, אבל עם היגיון יפה: האם הצופה רואה וידאו או תמונה אחת.",
               "כשאתם רואים וידאו, המוח שלכם ממצע כמה פריימים אחד אחרי השני, והרעש שמהבהב פשוט נעלם. בתמונה בודדת "
               "אין לו את העזרה הזו.",
               "צפייה חיה, Video. ניתוח של צילום, Still. וההבדל מורגש בעיקר כשהתמונה רועשת."),
        "en": ("A small question, but with a nice logic behind it: does the observer watch video, or a single image?",
               "When you watch video, your brain averages several frames in a row, and the flickering noise simply "
               "fades away. In a single image it does not get that help.",
               "Live viewing is Video. Analyzing a picture is Still. And the difference shows mostly when the image "
               "is noisy."),
    },
    "optics.f_mm": {
        "he": ("הגענו לאחד המנופים הכי חזקים שיש לכם על הטווח: אורך המוקד.",
               "תחשבו על משקפת. ככל שהיא מגדילה יותר, כל פיקסל בגלאי רואה פרוסה צרה יותר של העולם, ולכן נכנסים "
               "יותר פיקסלים על המטרה. ויותר פיקסלים על המטרה זה בדיוק מה שמאפשר לזהות אותה מרחוק.",
               "בשורה התחתונה: מוקד ארוך יותר, טווח ארוך יותר, אבל שדה ראייה צר יותר. זו תמיד העסקה."),
        "en": ("We have reached one of the strongest levers you have on the range: the focal length.",
               "Think of binoculars. The more they magnify, the narrower the slice of the world each pixel of the "
               "detector sees, so more pixels land on the target. And more pixels on the target is exactly what "
               "lets you identify it from far away.",
               "The bottom line: a longer focal length gives a longer range, but a narrower field of view. That is "
               "always the deal."),
    },
    "optics.aperture": {
        "he": ("כאן אתם רק בוחרים איך לתאר את פתח העדשה. זה לא ערך, זו צורת קלט.",
               "אפשר לתת את הקוטר עצמו, ואפשר לתת רק את ה-F-number. הקוטר הוא המידע המדויק יותר, כי הוא באמת "
               "קובע כמה אור נכנס ועד כמה התמונה חדה.",
               "אם הקוטר כתוב בדף הנתונים, תשתמשו בו."),
        "en": ("Here you only choose how to describe the lens opening. It is not a value, it is a form of input.",
               "You can give the diameter itself, or only the F-number. The diameter is the more exact information, "
               "because it is what really sets how much light comes in and how sharp the image can be.",
               "If the diameter is in the datasheet, use it."),
    },
    "optics.D_mm": {
        "he": ("עכשיו קוטר העדשה, ופה יש סיפור שחשוב להבין.",
               "תדמיינו דלי שעומד בגשם. דלי רחב יותר אוסף יותר מים, ועדשה רחבה יותר אוספת יותר אור. אבל יש עוד "
               "משהו: בגלל טבע הגלים, עדשה קטנה מטשטשת את התמונה. זו העקיפה. עדשה רחבה יותר גם חדה יותר.",
               "אז במערכות שהאופטיקה מגבילה אותן, כמו MWIR מקורר או מצלמות לילה, הקוטר הוא המנוף המרכזי."),
        "en": ("Now the lens diameter, and there is a story here worth understanding.",
               "Picture a bucket standing in the rain. A wider bucket collects more water, and a wider lens collects "
               "more light. But there is more: because light is a wave, a small lens blurs the image. That is "
               "diffraction. A wider lens is also a sharper one.",
               "So in systems limited by the optics, such as cooled MWIR or night cameras, the diameter is the main "
               "lever."),
    },
    "optics.F_general": {
        "he": ("ה-F-number הוא דרך מקוצרת לומר כמה העדשה פתוחה ביחס לאורך שלה.",
               "מספר קטן, כמו F/1, זו עדשה פתוחה ומהירה שמכניסה הרבה אור. מספר גדול, כמו F/8, זה כמו להסתכל דרך "
               "צינור צר.",
               "זכרו: F קטן, יותר אור ופחות טשטוש."),
        "en": ("The F-number is a short way of saying how open the lens is compared to its length.",
               "A small number, like F/1, is a wide open, fast lens that lets in a lot of light. A large number, "
               "like F/8, is like looking through a narrow tube.",
               "Remember: a small F-number means more light and less blur."),
    },
    "optics.tau_opt": {
        "he": ("השדה הזה אומר כמה מהאור באמת מגיע לגלאי, אחרי שהוא עובר את כל העדשות.",
               "כל עדשה וכל חלון בולעים או מחזירים קצת אור, כמו זכוכית של חלון שמחזירה לכם את ההשתקפות. "
               "שמונים וחמישה אחוז זה אומר שחמישה עשר אחוז הלכו לאיבוד בדרך.",
               "ביום ובמצלמה תרמית רגילה זה כמעט לא משנה. בלילה, כשכל פוטון חשוב, זה כבר כן."),
        "en": ("This field says how much of the light really reaches the detector, after passing all the lenses.",
               "Every lens and every window absorbs or reflects a little light, like a window pane that shows you "
               "your own reflection. Eighty-five percent means fifteen percent was lost on the way.",
               "By day, or in an ordinary thermal camera, it hardly matters. At night, when every photon counts, it "
               "does."),
    },
    "detector.n_h": {
        "he": ("מספר הפיקסלים. רוב האנשים בטוחים שזה הפרמטר הכי חשוב, ופה יש הפתעה.",
               "מספר הפיקסלים קובע כמה רחב השדה שאתם רואים, לא כמה רחוק. גלאי רחב יותר הוא כמו חלון רחב יותר, אבל "
               "הוא לא מקרב את הנוף.",
               "אז אם המטרה היא טווח, המוקד והפסיעה חשובים יותר. מספר הפיקסלים קונה לכם כיסוי."),
        "en": ("The number of pixels. Most people are sure this is the most important parameter, and here comes a "
               "surprise.",
               "The number of pixels sets how wide a field you see, not how far. A wider detector is like a wider "
               "window, but it does not bring the view any closer.",
               "So if your goal is range, the focal length and the pitch matter more. The pixel count buys you "
               "coverage."),
    },
    "detector.pitch_h_um": {
        "he": ("פסיעת הפיקסלים, כלומר כמה קטן כל פיקסל.",
               "פיקסל קטן יותר, עם אותה עדשה, רואה פרוסה צרה יותר של העולם, ממש כמו להאריך את המוקד. אבל יש תנאי: "
               "העדשה צריכה להיות חדה מספיק. אם התמונה כבר מטושטשת מהאופטיקה, לחלק אותה לפיקסלים קטנים יותר לא "
               "יוסיף פרטים.",
               "בשורה התחתונה: פיקסל קטן עוזר רק כשהאופטיקה עומדת בקצב. את זה בודק היחס אף למדא חלקי די."),
        "en": ("The pixel pitch, in other words how small each pixel is.",
               "A smaller pixel with the same lens sees a narrower slice of the world, just like a longer focal "
               "length. But there is a condition: the lens has to be sharp enough. If the image is already blurred "
               "by the optics, cutting it into smaller pixels adds no detail.",
               "The bottom line: a small pixel helps only when the optics keep up. That is what the F lambda over d "
               "ratio checks."),
    },
    "detector.noise_mode": {
        "he": ("כאן אתם בוחרים מאיפה המודל יקבל את הרעש של המצלמה.",
               "אפשר לתת למודל לחשב את הרעש מהפיזיקה של הגלאי, ואפשר לתת לו מספר שמישהו מדד על המצלמה האמיתית. "
               "מדידה אמיתית תמיד מנצחת חישוב.",
               "יש NETD מדוד של המצלמה כולה? תבחרו Measured."),
        "en": ("Here you choose where the model takes the camera noise from.",
               "The model can calculate the noise from the physics of the detector, or you can give it a number "
               "someone measured on the real camera. A real measurement always beats a calculation.",
               "Do you have a measured NETD of the whole camera? Choose Measured."),
    },
    "detector.netd_mK": {
        "he": ("ה-NETD, הרגישות התרמית. זה המספר שכולם מסתכלים עליו בדף הנתונים.",
               "הוא אומר מה הפרש הטמפרטורה הכי קטן שהמצלמה עוד מבחינה בו מתוך הרעש. חמישים מילי-קלווין זה חמש "
               "מאיות מעלה, באמת מעט מאוד.",
               "וההפתעה: ברוב המצבים הוא משפיע על הטווח פחות ממה שחושבים. הוא נהיה חשוב כשהניגוד קטן, או כשמזג "
               "האוויר גרוע."),
        "en": ("The NETD, the thermal sensitivity. This is the number everyone looks at in the datasheet.",
               "It says the smallest temperature difference the camera can still pick out of the noise. Fifty "
               "millikelvin is five hundredths of a degree, really very little.",
               "And the surprise: in most cases it affects the range less than people think. It becomes important "
               "when the contrast is small, or when the weather is bad."),
    },
    "detector.tint_ms": {
        "he": ("זמן האינטגרציה הוא כמה זמן הגלאי \"פותח את העיניים\" בכל פריים.",
               "זה כמו לאסוף מי גשם: ככל שמשאירים את הכוס בחוץ יותר זמן, אוספים יותר. אבל הכוס מתמלאת בסוף, ואז "
               "אין טעם להחזיק אותה עוד.",
               "בלילה, כשיש מעט אור, זמן ארוך עוזר מאוד. ביום הבאר מתמלאת מהר, והזמן כבר לא הבעיה."),
        "en": ("The integration time is how long the detector keeps its eyes open in each frame.",
               "It is like collecting rain water: the longer you leave the cup outside, the more you collect. But "
               "the cup fills up eventually, and then there is no point in holding it out any longer.",
               "At night, when there is little light, a long time helps a lot. By day the well fills quickly, and "
               "time is no longer the problem."),
    },
    "detector.noise_floor_e": {
        "he": ("רעש הקריאה. במצלמות לילה זה אחד הפרמטרים הכי חשובים שיש.",
               "תחשבו על מישהו שלוחש לכם בחדר שקט מול חדר עם מזגן רועש. רעש הקריאה הוא המזגן: הוא תמיד שם, ולא "
               "משנה כמה חלש האות.",
               "ביום האות חזק ומכסה עליו. בלילה, כשהאות לוחש, רעש קריאה נמוך הוא ההבדל בין לראות ולא לראות."),
        "en": ("The read noise. In night cameras it is one of the most important parameters there is.",
               "Think of someone whispering to you in a quiet room, compared with a room with a noisy air "
               "conditioner. The read noise is the air conditioner: it is always there, no matter how weak the "
               "signal.",
               "By day the signal is strong and drowns it out. At night, when the signal whispers, a low read noise "
               "is the difference between seeing and not seeing."),
    },
    "basic.frame_rate": {
        "he": ("קצב הפריימים, כמה תמונות בשנייה.",
               "הוא משפיע בעקיפין: הוא מגביל כמה זמן אפשר לאסוף אור בכל פריים, וכמה פריימים העין ממצעת.",
               "בתחום הרגיל, עשרים וחמש עד שישים הרץ, אפשר לסמוך על דף הנתונים ולהמשיך."),
        "en": ("The frame rate, how many images per second.",
               "It acts indirectly: it limits how long light can be collected in each frame, and how many frames the "
               "eye averages.",
               "In the usual range, twenty-five to sixty hertz, you can trust the datasheet and move on."),
    },
    "display.observation": {
        "he": ("איך הצופה מסתכל על התמונה: על מסך, או דרך עינית.",
               "זה נשמע כמו פרט קטן, אבל העין לא רואה פיקסלים, היא רואה זוויות. אותה תמונה נראית גדולה מאוד בעינית "
               "צמודה לעין, וקטנה במסך שנמצא מטר מכם.",
               "תגדירו את זה כמו שהמערכת באמת עובדת. טעות כאן היא אחת הנפוצות."),
        "en": ("How the observer looks at the image: on a monitor, or through an eyepiece.",
               "It sounds like a small detail, but the eye does not see pixels, it sees angles. The same image looks "
               "very large in an eyepiece right at your eye, and small on a monitor a meter away.",
               "Set it the way the system really works. A mistake here is one of the most common ones."),
    },
    "display.distance_cm": {
        "he": ("כמה רחוק הצופה יושב מהמסך.",
               "תנסו את זה בעצמכם: תתקרבו למסך, והפרטים נהיים גדולים יותר לעין. המודל יודע את זה, ולכן מרחק "
               "הצפייה משנה את הטווח.",
               "תזינו את המרחק האמיתי בעמדה, לא מרחק אידיאלי."),
        "en": ("How far the observer sits from the monitor.",
               "Try it yourself: lean closer to the screen, and the details get bigger to your eye. The model knows "
               "this, which is why the viewing distance changes the range.",
               "Enter the real distance at the workstation, not an ideal one."),
    },
    "display.snr_th": {
        "he": ("סף ה-SNR של הצופה. כאן אני ממליץ דווקא לא לגעת.",
               "זה קבוע כיול שמתאר כמה בטוח הצופה צריך להיות לפני שהוא אומר \"ראיתי\". הוא נמדד על הרבה צופים "
               "אמיתיים.",
               "להוריד אותו כדי לקבל טווח יפה יותר זה לרמות את עצמכם. תשאירו את ברירת המחדל."),
        "en": ("The observer SNR threshold. Here I actually recommend not touching it.",
               "It is a calibration constant that describes how sure the observer has to be before saying \"I saw "
               "it\". It was measured on many real observers.",
               "Lowering it to get a nicer range is fooling yourself. Keep the default."),
    },
    "stab.jitter_preset": {
        "he": ("ריצוד קו הראייה, כלומר כמה המצלמה רועדת בזמן הצילום.",
               "תנסו לצלם עם זום חזק ביד: כל רעידה קטנה מטשטשת. בשדה ראייה רחב לא מרגישים את זה, אבל בשדה צר "
               "כל מיקרו-רעידה מורחת את המטרה על כמה פיקסלים.",
               "אם אין לכם מדידה של הייצוב, תשאירו את הערך הטיפוסי. בלי ריצוד בכלל, התחזית תהיה אופטימית מדי."),
        "en": ("The line of sight jitter, in other words how much the camera shakes while it images.",
               "Try taking a photo with a strong zoom in your hand: every small shake blurs it. In a wide field of "
               "view you do not notice it, but in a narrow field every tiny shake smears the target over several "
               "pixels.",
               "If you have no measurement of the stabilization, keep the typical value. With no jitter at all, the "
               "prediction will be too optimistic."),
    },
    "stab.rand_h_mrad": {
        "he": ("עכשיו עוצמת הריצוד עצמה, וחשוב להבין ביחס למה מודדים אותה.",
               "אותה רעידה נראית זניחה במצלמה עם פיקסל גדול, והרסנית במצלמה עם פיקסל זעיר. מה שקובע זה היחס בין "
               "הרעידה לזווית של פיקסל אחד.",
               "ושימו לב ליחידות: השדה במילירדיאן. שבעים מיקרורדיאן זה אפס נקודה אפס שבע, לא שבעים."),
        "en": ("Now the jitter magnitude itself, and it is important to understand what it is compared with.",
               "The same shake looks negligible in a camera with a large pixel, and destructive in a camera with a "
               "tiny pixel. What counts is the ratio between the shake and the angle of a single pixel.",
               "And watch the units: the field is in milliradians. Seventy microradians is zero point zero seven, not "
               "seventy."),
    },
    "target.preset": {
        "he": ("בחירת המטרה. זה המקום שבו אנחנו מחליטים מה בעצם מחפשים.",
               "מטרה תקנית ממלאת בבת אחת את הגודל, את הניגוד ואת הקריטריונים. זה כמו סרגל משותף: כשכולם מודדים מול "
               "אותה מטרה, אפשר להשוות מערכות בצורה הוגנת.",
               "לרכב, STANAG. לאדם, Persons. ואחר כך אפשר לדייק לפי הדרישה שלכם."),
        "en": ("Choosing the target. This is where we decide what we are actually looking for.",
               "A standard target fills in the size, the contrast and the criteria at once. It is like a shared "
               "ruler: when everyone measures against the same target, systems can be compared fairly.",
               "For a vehicle, STANAG. For a person, Persons. Then you can refine it to your requirement."),
    },
    "target.W_m": {
        "he": ("רוחב המטרה. זה אולי הפרמטר הכי אינטואיטיבי, והוא גם מהחזקים.",
               "מטרה גדולה פי שתיים נראית מאותו מרחק כמו מטרה רגילה ממרחק כפול. לכן גודל המטרה מתורגם כמעט ישירות "
               "לטווח.",
               "ושימו לב: מטרים, לא סנטימטרים. ולעולם לא אפס."),
        "en": ("The target width. It may be the most intuitive parameter, and it is also one of the strongest.",
               "A target twice as large looks, from the same distance, like a normal target from half the distance. "
               "That is why target size translates almost directly into range.",
               "And note: meters, not centimeters. And never zero."),
    },
    "target.H_m": {
        "he": ("גובה המטרה, השותף של הרוחב.",
               "המודל לא מסתכל על הרוחב או הגובה לבד, אלא על הגודל האפקטיבי של שניהם יחד, השורש של השטח.",
               "אז הגובה חשוב בדיוק כמו הרוחב. תזינו את שניהם מתוך הדרישה."),
        "en": ("The target height, the partner of the width.",
               "The model does not look at the width or the height alone, but at the effective size of both "
               "together, the square root of the area.",
               "So the height matters exactly as much as the width. Enter both from the requirement."),
    },
    "target.D_m": {
        "he": ("עומק המטרה, האורך שלה.",
               "מלפנים רכב נראה כמו קופסה קטנה, ומהצד הוא פתאום ארוך. העומק נכנס לחישוב רק כשמסתכלים מהצד או "
               "באלכסון.",
               "בצפייה מלפנים אפשר להשאיר אפס."),
        "en": ("The target depth, its length.",
               "From the front a vehicle looks like a small box, and from the side it is suddenly long. The depth "
               "enters the calculation only when you look from the side or at an angle.",
               "For a front view you can leave it at zero."),
    },
    "target.aspect": {
        "he": ("מאיזה כיוון רואים את המטרה.",
               "אותו רכב נראה גדול יותר מהצד ממה שהוא נראה מלפנים, ולכן הוא מזוהה מרחוק יותר מהצד.",
               "אם אתם לא בטוחים, תתכננו למקרה הקשה: חזית."),
        "en": ("From which direction the target is seen.",
               "The same vehicle looks larger from the side than from the front, so from the side it can be "
               "identified from further away.",
               "If you are not sure, design for the hard case: the front."),
    },
    "target.dT_K": {
        "he": ("הניגוד התרמי, דלתא טי. במצלמה תרמית זה מה שבעצם רואים.",
               "המצלמה לא רואה את הטמפרטורה של הרכב, היא רואה כמה הוא חם או קר יותר מהרקע. בשחר ובשקיעה יש רגע "
               "שבו הכול באותה טמפרטורה, והמטרה כמעט נעלמת.",
               "ההמלצה שלי: תחשבו עם שתי מעלות, ותבדקו גם מה קורה עם מעלה אחת. בשטח הניגוד משתנה הרבה."),
        "en": ("The thermal contrast, delta T. In a thermal camera, this is what you actually see.",
               "The camera does not see the temperature of the vehicle; it sees how much warmer or colder it is than "
               "the background. At dawn and dusk there is a moment when everything has the same temperature, and the "
               "target almost disappears.",
               "My recommendation: calculate with two kelvin, and also check what happens with one. In the field the "
               "contrast changes a lot."),
    },
    "target.T_bg_K": {
        "he": ("טמפרטורת הרקע, מה שנמצא מאחורי המטרה.",
               "היא קובעת כמה קרינה מגיעה מכל הסצנה, וזה משפיע על הרעש של הגלאי. במצלמות MWIR מסוימות, ביום חורף "
               "קר, ההשפעה גדולה מאוד.",
               "ורגע של זהירות: הערך בקלווין. חמש עשרה מעלות צלזיוס זה מאתיים שמונים ושמונה."),
        "en": ("The background temperature, what lies behind the target.",
               "It sets how much radiation comes from the whole scene, and that affects the detector noise. In some "
               "MWIR cameras, on a cold winter day, the effect is very large.",
               "And a word of caution: the value is in kelvin. Fifteen degrees Celsius is two hundred eighty-eight."),
    },
    "target.t_refl": {
        "he": ("כמה אור המטרה מחזירה. במצלמת יום, ככה נוצר הניגוד.",
               "רכב ירוק כהה על רקע חול בהיר בולט מיד. אותו רכב על רקע יער כמעט נעלם. מה שקובע זה ההפרש בין "
               "ההחזרות של המטרה והרקע.",
               "ותזכרו: מספר בין אפס לאחד, לא אחוזים."),
        "en": ("How much light the target reflects. In a day camera, this is how contrast is created.",
               "A dark green vehicle against bright sand stands out right away. The same vehicle against a forest "
               "almost disappears. What counts is the difference between the target and background reflectances.",
               "And remember: a number between zero and one, not a percentage."),
    },
    "target.b_refl": {
        "he": ("והצד השני של אותו מטבע: כמה אור הרקע מחזיר.",
               "המטרה לבד לא אומרת כלום. רק ההפרש בינה לבין הרקע יוצר משהו שהעין יכולה לראות.",
               "תבחרו את הרקע של התרחיש האמיתי שלכם."),
        "en": ("And the other side of the same coin: how much light the background reflects.",
               "The target alone means nothing. Only the difference between it and the background creates something "
               "the eye can see.",
               "Choose the background of your real scenario."),
    },
    "target.t_refl_preset": {
        "he": ("כאן המטרה מוגדרת כחומר אמיתי, עם עקומת החזרות לאורך הספקטרום.",
               "דשא, למשל, נראה ירוק כהה לעין אבל בוהק מאוד באינפרא-אדום הקרוב. לכן אותם שני חומרים יכולים להיות "
               "דומים במצלמה אחת ושונים מאוד באחרת.",
               "רק אל תבחרו לרקע ולמטרה את אותו חומר, כי אז אין ניגוד בכלל."),
        "en": ("Here the target is defined as a real material, with a reflectance curve across the spectrum.",
               "Grass, for example, looks dark green to the eye but very bright in the near infrared. That is why "
               "the same two materials can look alike in one camera and very different in another.",
               "Just do not choose the same material for the target and the background, because then there is no "
               "contrast at all."),
    },
    "target.b_refl_preset": {
        "he": ("וכאן חומר הרקע שמאחורי המטרה.",
               "הניגוד הוא תמיד ההפרש בין שני החומרים, בתחום הגל שהמצלמה רואה.",
               "תבחרו את מה שבאמת יהיה מאחורי המטרה: שדה, אספלט או חול."),
        "en": ("And here, the material of the background behind the target.",
               "The contrast is always the difference between the two materials, in the band the camera sees.",
               "Choose what will really be behind the target: a field, asphalt or sand."),
    },
    "target.task_preset": {
        "he": ("ועכשיו הפרמטר הכי חזק בכל המודל. כן, יותר מכל החומרה.",
               "הקריטריונים אומרים כמה פרטים צריך לראות על המטרה כדי להחליט. לגלות שיש משהו מספיק פס אחד. להגיד "
               "שזה רכב צריך שלושה. להגיד איזה רכב צריך שישה. ככל שדורשים יותר פרטים, צריך להתקרב.",
               "לכן, כשמשווים שתי מערכות, תוודאו שהן חושבו עם אותם קריטריונים. אחרת ההשוואה לא שווה כלום."),
        "en": ("And now the strongest parameter in the whole model. Yes, stronger than all the hardware.",
               "The criteria say how much detail must be seen on the target to make a decision. To detect that "
               "something is there, one line pair is enough. To say it is a vehicle takes three. To say which "
               "vehicle takes six. The more detail you demand, the closer you have to be.",
               "So when you compare two systems, make sure they were calculated with the same criteria. Otherwise the "
               "comparison is worthless."),
    },
    "target.tasks.N.lp": {
        "he": ("זה המספר עצמו של זוגות הקווים לכל משימה.",
               "זוג קווים זה כמו פס שחור ופס לבן. ככל שהמשימה דורשת יותר פסים על המטרה, המטרה צריכה להיראות גדולה "
               "יותר, כלומר קרובה יותר.",
               "גילוי אחד, הכרה שלושה עד ארבעה, זיהוי שישה עד שמונה. אלה המספרים שכדאי לזכור."),
        "en": ("This is the number of line pairs itself, for each task.",
               "A line pair is like one black stripe and one white stripe. The more stripes a task needs on the "
               "target, the larger the target has to look, which means the closer it has to be.",
               "Detection one, recognition three to four, identification six to eight. Those are the numbers worth "
               "remembering."),
    },
    "irradiance.preset": {
        "he": ("מקור האור. במצלמת יום, בלי אור אין תמונה.",
               "ביום השמש מספקת הרבה יותר אור ממה שצריך. בלילה, תחת ירח או כוכבים, כל פוטון נספר, ופתאום הקוטר, "
               "זמן האינטגרציה ורעש הקריאה הם שמכריעים.",
               "תבחרו את מצב ההארה הקשה ביותר שהמערכת צריכה לעבוד בו."),
        "en": ("The light source. In a day camera, without light there is no image.",
               "By day the sun gives far more light than needed. At night, under the moon or the stars, every photon "
               "counts, and suddenly the diameter, the integration time and the read noise are what decide.",
               "Choose the hardest lighting the system has to work in."),
    },
    "atmosphere.preset": {
        "he": ("האטמוספרה. בין המצלמה למטרה יש קילומטרים של אוויר.",
               "כמו לנסוע בערפל: הדברים הרחוקים נבלעים קודם. לכן האטמוספרה פוגעת בעיקר בגילוי, שהוא הטווח הארוך, "
               "וכמעט לא בזיהוי, שקורה מקרוב.",
               "לדוח, ההמלצה שלי היא Compare: ככה רואים את התוצאה בשלושה מצבי מזג אוויר."),
        "en": ("The atmosphere. Between the camera and the target there are kilometers of air.",
               "It is like driving in fog: distant things are swallowed first. That is why the atmosphere hurts "
               "mostly detection, the long range, and hardly identification, which happens up close.",
               "For a report, my recommendation is Compare: that way you see the result in three weather "
               "conditions."),
    },
    "atmosphere.atm.N.sigma": {
        "he": ("מקדם ההנחתה, סיגמה, הוא המספר שמתאר כמה האוויר בולע.",
               "על כל קילומטר, חלק קבוע מהאות נעלם. סיגמה קטנה זה יום צלול, סיגמה גדולה זה אובך או ערפל.",
               "ושימו לב ליחידות: לקילומטר, לא למטר."),
        "en": ("The extinction coefficient, sigma, is the number that describes how much the air absorbs.",
               "For every kilometer, a fixed share of the signal disappears. A small sigma is a clear day; a large "
               "sigma is haze or fog.",
               "And watch the units: per kilometer, not per meter."),
    },
    "atmosphere.atm.N.V_km": {
        "he": ("טווח הראות, המספר שתחנות מטאורולוגיות מפרסמות.",
               "זה המרחק שבו העין עוד רואה עצם כהה על רקע השמיים. המודל ממיר אותו להנחתה.",
               "ביום צלול עשרים ושלושה קילומטר ומעלה. בערפל, פחות מקילומטר."),
        "en": ("The visual range, the number weather stations publish.",
               "It is the distance at which the eye can still see a dark object against the sky. The model converts "
               "it to an attenuation.",
               "On a clear day, twenty-three kilometers and more. In fog, less than one kilometer."),
    },
    "turbulence.on": {
        "he": ("טורבולנציה. ראיתם פעם את האוויר רועד מעל כביש חם? זה בדיוק זה.",
               "האוויר החם מעוות את קרני האור, והתמונה של עצם רחוק רוקדת ומיטשטשת. זה חזק במיוחד ביום, קרוב לקרקע, "
               "ובמצלמות של התחום הנראה.",
               "בנתיב אופקי של יותר משני קילומטר ביום, תפעילו את זה."),
        "en": ("Turbulence. Have you ever seen the air shimmer above a hot road? That is exactly it.",
               "Hot air bends the light rays, and the image of a distant object dances and blurs. It is strongest by "
               "day, close to the ground, and in visible band cameras.",
               "On a horizontal path longer than two kilometers by day, turn it on."),
    },
    "turbulence.cn2_preset": {
        "he": ("כאן בוחרים כמה חזקה הטורבולנציה, לפי האקלים והשעה.",
               "מעל מדבר בצהריים האוויר רותח, ובלילה הוא רגוע. ההבדל בטווח יכול להגיע לפי שלושה.",
               "בנגב תבחרו Arid, בצפון ובמרכז Moderate."),
        "en": ("Here you choose how strong the turbulence is, by climate and time of day.",
               "Over a desert at noon the air is boiling, and at night it is calm. The difference in range can reach "
               "a factor of three.",
               "In a desert climate choose Arid; in a temperate one, Moderate."),
    },
    "turbulence.cn2": {
        "he": ("זה המספר הפיזיקלי של עוצמת הטורבולנציה.",
               "המספרים קטנים מאוד, ולכן מדברים בחזקות של עשר. כל צעד של חזקה אחת הוא הבדל גדול מאוד.",
               "ושימו לב לכתיבה: אחד e מינוס ארבע עשרה, לא ארבע עשרה."),
        "en": ("This is the physical number for the strength of the turbulence.",
               "The numbers are very small, so we talk in powers of ten. Every step of one power is a very large "
               "difference.",
               "And watch the notation: one e minus fourteen, not fourteen."),
    },
}

# FRAME[lang][part][impact] -> variants; {t} is the field title.  The variant is picked per field (stable).
FRAME = {
    "he": {
        "intro": {
            3: ["עכשיו נעצור על שדה חשוב במיוחד: {t}.", "בואו נדבר על {t}. זה אחד המנופים החזקים על הטווח.",
                "הגענו ל{t}, ופה כדאי להקדיש רגע ולדייק."],
            2: ["השדה הבא הוא {t}. השפעה בינונית, ושווה להבין אותו.", "נעבור ל{t}.",
                "בואו נכיר את {t}."],
            1: ["השדה הבא הוא {t}. הוא משפיע מעט, אז נעבור עליו בקצרה.", "עכשיו {t}, שדה משני.",
                "נעבור מהר על {t}."],
            0: ["השדה הבא הוא {t}. חדשות טובות: הוא לא משפיע על הטווח.",
                "{t} הוא שדה של תיעוד ובדיקה, לא של טווח.", "נעבור על {t}. הוא לא נכנס לחישוב הטווח."],
        },
        "idea": ["במילים פשוטות:", "מה זה אומר?", "קודם כול, מה זה בכלל?"],
        "why": ["ולמה זה חשוב לנו?", "ולמה שזה יעניין אתכם?", "עכשיו, איך זה משפיע?"],
        "typical": ["כדי שתהיה לכם תחושה של המספרים:", "ערכים שתפגשו בדרך כלל:", "לדוגמה:"],
        "source": ["ואיפה מוצאים את הערך?", "ומאיפה לוקחים את המספר?"],
        "mistakes": ["וטיפ מניסיון, טעות שחוזרת הרבה:", "ורגע של זהירות, זו הטעות הנפוצה:"],
        "bottom": {
            3: ["בשורה התחתונה: שדה כזה שווה את הזמן. תזינו נתון אמיתי של המערכת.",
                "אז לסיכום: כאן דיוק של הערך באמת משנה את התוצאה."],
            2: ["לסיכום: ערך סביר מספיק כאן, ונתון אמיתי עדיף.", "אז בקצרה: כדאי לבדוק אותו, אבל בלי לשבור את הראש."],
            1: ["בשורה התחתונה: אם אין נתון טוב יותר, אפשר להשאיר את ברירת המחדל.",
                "לסיכום: זה לא המקום להשקיע את רוב הזמן."],
            0: ["אז אפשר למלא אותו לצורך התיעוד ולהמשיך הלאה.", "בשורה התחתונה: הוא לא ישנה את הטווח."],
        },
        "ok": ["בדקתי את הערך שהזנתם, {v}, והוא נראה תקין.", "אצלכם הוזן {v}. זה ערך סביר.",
               "הערך שלכם, {v}, עובר את הבדיקה."],
        "warn": ["פה אני רוצה לעצור רגע. הזנתם {v}, ומשהו בו נראה חשוד.",
                 "רגע, כדאי להסתכל על הערך שלכם, {v}.", "שימו לב, הערך {v} מעורר אצלי שאלה."],
        "suggest": ["הייתי מנסה {s}. הכפתור 'החל את הערך המוצע' עושה את זה בשבילכם, ו'בטל' מחזיר.",
                    "ההצעה שלי היא {s}. אפשר להחיל אותה בכפתור, ולבטל אם תתחרטו."],
        "impact": ["ועכשיו החלק המעניין: מה זה עושה לטווחים שלכם.",
                   "בואו נראה מה המספרים אומרים על המערכת שלכם."],
        "next": ["כשתהיו מוכנים, 'הבא' ממשיך לשלב הבא.", "אם הכול ברור, ממשיכים ב'הבא'."],
    },
    "en": {
        "intro": {
            3: ["Now let's stop at a particularly important field: {t}.",
                "Let's talk about {t}. It is one of the strong levers on the range.",
                "We have reached {t}, and this one is worth a moment to get right."],
            2: ["The next field is {t}. It has a medium effect, and it is worth understanding.", "Let's move on to {t}.",
                "Let's get to know {t}."],
            1: ["The next field is {t}. It has a small effect, so we will go over it quickly.",
                "Now {t}, a secondary field.", "A quick look at {t}."],
            0: ["The next field is {t}. Good news: it does not affect the range.",
                "{t} is a field for documentation and checks, not for the range.",
                "Let's look at {t}. It does not enter the range calculation."],
        },
        "idea": ["In simple words:", "What does it mean?", "First of all, what is it?"],
        "why": ["And why does it matter to us?", "So why should you care?", "Now, how does it affect things?"],
        "typical": ["To give you a feel for the numbers:", "Values you will usually meet:", "For example:"],
        "source": ["And where do you find the value?", "And where does the number come from?"],
        "mistakes": ["And a tip from experience, a mistake that comes up a lot:",
                     "And a word of caution, this is the common mistake:"],
        "bottom": {
            3: ["The bottom line: a field like this is worth your time. Enter real data of your system.",
                "So to sum up: here the accuracy of the value really changes the result."],
            2: ["To sum up: a reasonable value is enough here, and real data is better.",
                "So in short: check it, but do not lose sleep over it."],
            1: ["The bottom line: if there is no better data, you can keep the default.",
                "To sum up: this is not where to spend most of your time."],
            0: ["So you can fill it in for the record, and move on.", "The bottom line: it will not change the range."],
        },
        "ok": ["I checked the value you entered, {v}, and it looks fine.", "You entered {v}. That is a reasonable value.",
               "Your value, {v}, passes the check."],
        "warn": ["I want to stop here for a moment. You entered {v}, and something about it looks suspicious.",
                 "Wait, it is worth looking at your value, {v}.", "Note that the value {v} raises a question for me."],
        "warn_more": ["The note on the screen explains exactly what looks wrong."],
        "suggest": ["I would try {s}. The apply button does it for you, and undo brings your value back.",
                    "My suggestion is {s}. You can apply it with the button, and undo it if you change your mind."],
        "impact": ["And now the interesting part: what this does to your ranges.",
                   "Let's see what the numbers say about your system."],
        "next": ["When you are ready, Next moves on.", "If everything is clear, continue with Next."],
    },
}


def pick(lang, part, key, *sub):
    """A variant of a frame phrase, stable for `key` (the field path) so the same card always sounds the same."""
    opts = FRAME[lang][part]
    for s in sub:
        opts = opts[s]
    h = int(hashlib.md5(("%s|%s" % (part, key)).encode("utf-8")).hexdigest()[:6], 16)
    return opts[h % len(opts)]


# (lesson id, Hebrew step title) -> spoken explanation of the step, in Hebrew (the English one is in guide_voice_en)
HE_STEPS = {
    ("first", "ברוכים הבאים"): [
        "שלום, ברוכים הבאים. אני אלווה אתכם בחישוב טווחים מלא, צעד אחר צעד.",
        "בכל שלב אסמן לכם את השדה בטופס, אסביר מה הוא אומר, ואבדוק שהערך שהזנתם הגיוני.",
        "לפני שמתחילים, שלושה כללים שיחסכו לכם הרבה זמן.",
        "אחד: מתחילים מתבנית שקרובה למערכת שלכם, ומחליפים רק את מה שבאמת ידוע לכם.",
        "שתיים: קודם הפרמטרים שמשפיעים, המשימה, המטרה, האופטיקה והאטמוספרה. הרעש מגיע אחר כך.",
        "ושלוש: ערך שמסומן preset או assumed הוא ניחוש. כדאי להחליף אותו בנתון אמיתי.",
        "אפשר לעצור ולסגור את המדריך בכל רגע, וכשתחזרו נמשיך מאותו מקום. מוכנים? ממשיכים ב'הבא'."],
    ("first", "בחרו תבנית"): [
        "הצעד הראשון הוא לבחור תבנית.",
        "תבנית ממלאת בבת אחת מאות פרמטרים בערכים שמתאימים אחד לשני, כך שאתם לא מתחילים מדף ריק.",
        "פותחים File, New from template, או לוחצים New בסרגל הכלים.",
        "יש לכם מצלמה תרמית לא-מקוררת? תבחרו LWIR uncooled. מקוררת? MWIR או LWIR cooled. מצלמת יום, CMOS. "
        "מצלמת לילה, SWIR InGaAs.",
        "ואם כבר שמרתם פרופיל של המצלמה שלכם, הוא מחכה לכם בראש העמוד Quick setup."],
    ("first", "המטרה"): [
        "עכשיו נגדיר מה אנחנו מחפשים. מטרה תקנית ממלאת מידות, ניגוד וקריטריונים בבת אחת."],
    ("first", "קריטריון הזיהוי"): [
        "בתחתית העמוד יש שלוש משימות: גילוי, הכרה וזיהוי. אני מסמן לכם את הזיהוי, המשימה הכי קשה מבין השלוש."],
    ("first", "מחשבים"): [
        "הגיע הזמן לחשב. לוחצים Calculate בסרגל הכלים, או F5, או פשוט 'חשב עכשיו' כאן למטה.",
        "זה לוקח כמה שניות.",
        "ואם קופצת הודעת שגיאה, אל דאגה: היא אומרת בדיוק איזה ערך לא תקין. מתקנים ומחשבים שוב."],
    ("first", "קוראים את התוצאה"): [
        "יש לנו תוצאה. בעמוד Summary תראו שלושה טווחים בקילומטרים.",
        "גילוי זה הרגע שבו אתם רואים שיש שם משהו. הכרה זה כשאתם יודעים שזה רכב ולא אדם. וזיהוי, איזה רכב בדיוק.",
        "כל טווח כזה הוא בהסתברות של חמישים אחוז, לפי הקריטריונים שבחרתם.",
        "ועקומת הטווח מראה לכם איך הביצועים יורדים ככל שמתרחקים."],
    ("first", "לפני שמשתמשים במספר"): [
        "רגע לפני שאתם לוקחים את המספר הזה לישיבה, תעברו על עמוד Messages.",
        "שם מופיעות כל האזהרות וכל ההנחות שעליהן החישוב נשען.",
        "זה חשוב: מספר שנראה טוב הוא לא בהכרח מספר נכון. טווח בלי ההנחות שלו לא שווה הרבה.",
        "וזהו, סיימתם את השיעור הראשון. בשיעור הבא נזין מערכת אמיתית, ברמה ההנדסית."],
    ("engineering", "סדר העבודה"): [
        "בשיעור הזה נעבוד כמו מהנדסים. במצב Engineering כל העמודים פתוחים, וזה יכול להרגיש הרבה.",
        "הסוד הוא לא למלא הכול, אלא למלא לפי הסדר של מה שבאמת משפיע.",
        "בראש הרשימה: קריטריון המשימה, מידות המטרה, המוקד, הקוטר והאטמוספרה.",
        "אחריהם טורבולנציה, ריצוד ותצוגה. ורק בסוף, ה-NETD והרעש.",
        "ונתון שמפתיע אנשים: מתוך כמאה פרמטרים, כשבעים כמעט לא משפיעים. אל תבזבזו עליהם זמן."],
    ("engineering", "Fλ/d - מי מגביל?"): [
        "עכשיו מושג אחד שאם תבינו אותו, תבינו את רוב המערכת: היחס Fλ/d.",
        "הוא עונה על שאלה פשוטה: מי מגביל את החדות, הגלאי או העדשה?",
        "אם היחס קטן מאחד, הגלאי מגביל. אז מוקד ארוך יותר או פיקסל קטן יותר יעזרו מאוד.",
        "אם הוא גדול מאחד וחצי, העדשה מגבילה, בגלל העקיפה. אז רק קוטר גדול יותר יעזור, ופיקסל קטן כמעט לא ישנה.",
        "את הערך שלכם תמצאו בפאנל הערכים המחושבים, בתחתית עמוד Optics."],
    ("engineering", "פסיעת הפיקסלים"): [
        "טיפ שחוסך הקלדה: Run, Detector lookup, או Ctrl+D, ממלא את נתוני הגלאי ישר מהקטלוג."],
    ("engineering", "מקדם ההנחתה"): [
        "כאן מזינים את האטמוספרה הראשונה. אפשר להפעיל עד שלוש, ולהשוות ביניהן."],
    ("engineering", "תג המקור של כל ערך"): [
        "שמתם לב לתג הקטן ליד כל שדה? preset, datasheet, measured, assumed.",
        "הוא אומר מאיפה הגיע הערך, ולוחצים עליו כדי לשנות.",
        "זה לא סתם קישוט: הדוחות מראים לכל טווח על אילו נתונים הוא נשען. ערך שנשאר preset הוא ניחוש כללי.",
        "והנה הסיכום: הזנתם את כל מה שבאמת קובע את הטווח. תחשבו עם F5, ונעבור לשיעור השלישי."],
    ("results", "המסך Summary"): [
        "בשיעור הזה נלמד לקרוא את התוצאות, ולהבין מה כדאי לשפר.",
        "המסך Summary מראה את טווחי הגילוי, ההכרה והזיהוי לכל אטמוספרה, את רמת הביטחון, ואת הסיבה העיקרית לכל טווח.",
        "אם עוד לא חישבתם, לחצו 'חשב עכשיו'."],
    ("results", "System data"): [
        "System data הוא המקום לבדוק את עצמכם.",
        "יש שם את כל הערכים המחושבים: IFOV, שדה הראייה, Fλ/d, NETD אפקטיבי ומילוי הבאר.",
        "תשאלו שתי שאלות: ה-IFOV ושדה הראייה תואמים לדף הנתונים? והבאר מתמלאת למשהו סביר, לא אפס ולא מאה אחוז?",
        "אם כן, המערכת שהזנתם היא באמת המערכת שהתכוונתם אליה."],
    ("results", "מה מגביל את הטווח"): [
        "עכשיו השאלה הכי שימושית: מה מגביל את הטווח?",
        "Run, Limiting factors, מראה לכל משימה מה עוצר אותה: אטמוספרה, עקיפה, דגימה, רעש או ריצוד.",
        "ולמה זה כל כך חשוב? כי שדרוג של משהו שלא מגביל לא ישנה כלום. קודם מוצאים את צוואר הבקבוק."],
    ("results", "יועץ השיפור"): [
        "ויש לכם גם יועץ. Run, Improve performance, מדרג שינויים אפשריים לפי כמה טווח כל אחד מוסיף.",
        "הוא רק מייעץ, הוא לא משנה לכם את הפרויקט.",
        "ושימו לב לסימון Measure first: אלה פרמטרים שכדאי למדוד לפני שמוציאים כסף על חומרה."],
    ("results", "סריקת פרמטר ואי-ודאות"): [
        "שלושה כלים לשאלות של מה אם.",
        "Parameter sweep מראה איך פרמטר אחד משנה את הטווח, בעקומה ובטבלה.",
        "Uncertainty study נותן טווח עם אי-ודאות. שם מזינים פלוס מינוס לפרמטרים הלא בטוחים, כמו ΔT, σ וקריטריון "
        "המשימה.",
        "ו-Scenario comparison שם כמה תרחישים זה לצד זה."],
    ("results", "דוח ושמירה"): [
        "ולסיום, איך לוקחים את העבודה הלאה.",
        "File, Export Hebrew DRI report, נותן דוח מלא בעברית. Export report נותן דוח טקסט עם כל ההנחות. ו-Save שומר "
        "את הפרויקט עם תגי המקור.",
        "סיימתם את כל השיעורים, כל הכבוד!",
        "אפשר להשאיר את המדריך פתוח: כל לחיצה על שדה תציג לכם את ההסבר שלו."],
    ("tour", "איך עובד הסיור"): [
        "בסיור הזה נעבור יחד על כל עמודי הטופס, קבוצה אחר קבוצה.",
        "בכל שלב אגיד לכם מה השדות בקבוצה, מה הערך שלכם, וכמה כל אחד משפיע על הטווח.",
        "שדה שצריך בדיקה מסומן במשולש אזהרה. לחיצה עליו פותחת הסבר מלא, עם חישוב חי של ההשפעה.",
        "וטיפ: לא צריך לשנות כל שדה. שדה עם כוכב אחד או בלי כוכב אפשר להשאיר בברירת המחדל."],
    ("tour", "בדיקת כל הערכים"): [
        "סיימנו את הסיור. עכשיו אני מציג לכם את כל ההערות על הערכים שלכם, מהמשפיעה ביותר לפחות משפיעה.",
        "לחיצה על שורה פותחת את השדה."],
}
