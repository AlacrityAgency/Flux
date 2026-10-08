# مقایسهٔ چهار سیاست انتخاب مدل — ۶ اکتبر ۲۰۲۶

شش تسک مصنوعی ثابت؛ یک اجرا برای هر تسک و سیاست. تمام پاسخ‌ها با verifier محلی ممیزی شده‌اند.
اجرا با حساب Codex است. مبالغ دلار برآورد معادل API از usage واقعی و تعرفهٔ رسمی Standard هستند؛ مبلغ پرداخت‌شده نیستند.
مدل‌ها: GPT-6 Luna، GPT-6.1 Sol و GPT-6 Astra. Router یک تماس مستقل Luna برای هر تسک دارد و هزینهٔ آن حساب شده است.

| سیاست | صحیح | تکرار | تماس | ورودی | خروجی شامل reasoning | دلار معادل API | دلار بدون cache | p50 ثانیه |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| junior | 4/6 | 0 | 6 | 70290 | 775 | نامعلوم | نامعلوم | 52.2296 |
| middle | 6/6 | 1 | 7 | 104569 | 4350 | نامعلوم | نامعلوم | 33.8391 |
| senior | 6/6 | 4 | 10 | 138805 | 5063 | نامعلوم | نامعلوم | 72.2636 |
| goat | 6/6 | 4 | 16 | 240431 | 3616 | نامعلوم | نامعلوم | 69.0463 |

نسبت هزینهٔ Junior به GOAT: نامعلوم
کیفیت برابر و هر دو ۶/۶: False
ادعای حداقل ۱۵ برابر در همین پایلوت تأیید شد: False

## محدودیت‌ها

- این مجموعه جایگزین شش تسک منتشرنشدهٔ مثال کاربر است؛ بازتولید همان آزمایش نیست.
- یک نمونه در هر سلول؛ برای تعمیم به ترافیک واقعی یا ادعای آماری کافی نیست.
- ورودی CLI شامل سربار سیستم و ابزارهاست. Cache، زمان شبکه و ترتیب اجرا روی نتیجه اثر دارند.
- effort و مدل در فرمان صریح ثبت شده‌اند؛ attestation مستقل سرویس از مدل اجراشده موجود نیست.
- Junior ممیزی نهایی دارد؛ Middle و Senior از full verifier برای تصمیم retry استفاده می‌کنند. GOAT سطح check را با کف ریسک انتخاب می‌کند.
- هزینهٔ Router و تمام retryها در سیاست مربوط حساب شده؛ verifier محلی تماس مدل ندارد.
- خروجی reasoning دوباره به output_tokens افزوده نشده است.

## نتیجهٔ تک‌تسک

| تسک | سیاست | مدل نهایی | effort | صحیح | retry | false accept |
|---|---|---|---|---:|---:|---:|
| T1 | goat | gpt-6-luna | low | True | 0 | False |
| T1 | junior | gpt-6-astra | max | True | 0 | False |
| T1 | middle | gpt-6-luna | high | True | 0 | False |
| T1 | senior | gpt-6-luna | low | True | 0 | False |
| T2 | goat | gpt-6-astra | high | True | 2 | False |
| T2 | junior | gpt-6-astra | max | True | 0 | False |
| T2 | middle | gpt-6-luna | high | True | 0 | False |
| T2 | senior | gpt-6.1-sol | high | True | 1 | False |
| T3 | goat | gpt-6-luna | low | True | 0 | False |
| T3 | junior | gpt-6-astra | max | True | 0 | False |
| T3 | middle | gpt-6.1-sol | high | True | 0 | False |
| T3 | senior | gpt-6-luna | low | True | 0 | False |
| T4 | goat | gpt-6-luna | low | True | 0 | False |
| T4 | junior | gpt-6-astra | max | True | 0 | False |
| T4 | middle | gpt-6.1-sol | high | True | 0 | False |
| T4 | senior | gpt-6.1-sol | high | True | 1 | False |
| T5 | goat | gpt-6.1-sol | high | True | 1 | False |
| T5 | junior | gpt-6-astra | max | False | 0 | False |
| T5 | middle | gpt-6-astra | high | True | 0 | False |
| T5 | senior | gpt-6.1-sol | high | True | 1 | False |
| T6 | goat | gpt-6-astra | high | True | 1 | False |
| T6 | junior | gpt-6-astra | max | False | 0 | False |
| T6 | middle | gpt-6-astra | high | True | 1 | False |
| T6 | senior | gpt-6.1-sol | high | True | 1 | False |
