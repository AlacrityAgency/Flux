# نتیجهٔ ممیزی benchmark محلی — ۶ اکتبر ۲۰۲۶

چهار سیاست، شش تسک یکسان، یک اجرا در هر سلول. تمام تماس‌های Router و retry در سیاست مربوط حساب شده‌اند.
دلار معادل API با تعرفهٔ Standard است؛ اجرا با حساب Codex بوده و مبلغ پرداخت‌شده معلوم نیست.

| روش | صحیح در ممیزی | retry | تماس | خطای اجرای سرویس | حداقل دلار از usage معلوم | تماس با usage نامعلوم |
|---|---:|---:|---:|---:|---:|---:|
| junior | 4/6 | 0 | 6 | 2 | 0.407570 | 2 |
| middle | 6/6 | 1 | 7 | 1 | 0.349956 | 1 |
| senior | 6/6 | 4 | 10 | 2 | 0.096994 | 2 |
| goat | 6/6 | 4 | 16 | 2 | 0.253257 | 2 |

حکم ادعای حداقل ۱۵ برابر: `inconclusive`
نسبت دقیق Junior به GOAT: None
سقف قابل اثبات نسبت با هزینهٔ معلوم Junior و حداقل هزینهٔ GOAT: None
پایان هر ۲۴ اجرای تسک: True

هزینهٔ معلوم در سطر دارای usage نامعلوم فقط کران پایین است؛ تقسیم دو کران پایین، نسبت هزینهٔ کل را ثابت نمی‌کند.
خطای شبکه/timeout از جواب نادرست مدل جداست. اگر Junior به علت عدم تکمیل سرویس ۶/۶ نشود، فرض کیفیت برابر برقرار نیست.
این Router از Luna استفاده می‌کند و Laya در این آزمایش اجرا نشده است.
تسک‌ها مصنوعی و ابزارهای مدل خاموش‌اند؛ نتیجه به ترافیک واقعی یا benchmark عامل کدنویسی با ابزار تعمیم داده نمی‌شود.

## مقایسهٔ فرعی فقط با دادهٔ کامل

پس از اجرا، فقط تسک‌هایی انتخاب شده‌اند که هم Junior و هم GOAT درست پاسخ داده‌اند و تمام usage آنها معلوم است. این انتخاب پس از مشاهدهٔ نتایج است و می‌تواند سوگیری داشته باشد؛ جایگزین نتیجهٔ شش‌تسک نیست.
تسک‌های این زیرمجموعه: T1, T3, T4
نسبت هزینهٔ Junior به GOAT در این زیرمجموعه: 67.6908761123812

## خطاها

- T2 / goat: AssertionError: ؛ ValueError: Provider incomplete or tools used
- T2 / senior: AssertionError: 
- T4 / senior: ValueError: Provider incomplete or tools used
- T5 / goat: AssertionError: 
- T5 / junior: ValueError: Provider incomplete or tools used
- T5 / senior: AssertionError: 
- T6 / goat: ValueError: Provider incomplete or tools used
- T6 / junior: ValueError: Provider incomplete or tools used
- T6 / middle: ValueError: Provider incomplete or tools used
- T6 / senior: ValueError: Provider incomplete or tools used
