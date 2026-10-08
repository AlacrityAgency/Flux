# اجرای واقعی Luna + v5 در برابر Luna + v4

۲ اکتبر ۲۰۲۶؛ ۲۰ سؤال مشترک، مدل `gpt-6-luna`، reasoning=low، CLI حساب موجود، دو worker، حداکثر یک repair برای هر arm. Sol استفاده نشد.

| سنجه | Luna + v5 | Luna + v4 |
|---|---:|---:|
| پاسخ درست با evaluator مستقل | 16/20 | 10/20 |
| پاسخ درست در تولید اول | 14/20 | 11/20 |
| تماس واقعی / کامل | 22 / 22 | 32 / 32 |
| repair واقعی | 2 | 12 |
| میانگین زمان end-to-end، ثانیه | 6.934 | 9.861 |
| میانگین توکن evidence نهایی | 196.30 | 571.80 |
| مجموع provider input tokens، شامل repair/scaffold | 379452 | 559264 |
| مجموع provider output tokens | 1462 | 1674 |

## خروجی سؤال به سؤال

| سؤال | Luna + v5 | Luna + v4 | پاسخ مرجع |
|---|---|---|---|
| حقیقت string | ✅ "group_759" | ✅ "group_759" | "group_759" |
| حقیقت integer | ✅ 350 | ✅ 350 | 350 |
| مجموعهٔ literalها | ✅ ["enabled_2","disabled_2"] | ❌ null | ["enabled_2", "disabled_2"] |
| عدد همراه واحد | ✅ {"amount":253,"unit":"ms"} | ❌ null | {"amount": 253, "unit": "ms"} |
| سؤال طبیعی انگلیسی | ✅ "setting_value_796598" | ❌ null | "setting_value_796598" |
| سؤال طبیعی فارسی | ✅ "setting_value_583388" | ✅ "setting_value_583388" | "setting_value_583388" |
| مالک dependency، مورد ۱ | ✅ "team_0" | ❌ null | "team_0" |
| مالک dependency، مورد ۲ | ✅ "team_1" | ❌ null | "team_1" |
| Flux: max_concurrency | ✅ 2 | ✅ 2 | 2 |
| Flux: allowed human_owner | ✅ ["local-user"] | ✅ ["local-user"] | ["local-user"] |
| احتمال شرطی | ❌ 0.16864 | ❌ 0.168816 | 0.168722 |
| عضویت دقیقاً در یک مجموعه | ✅ 222 | ❌ 295 | 222 |
| رشتهٔ باینری بدون ۱ مجاور | ✅ 792 | ✅ 792 | 792 |
| باقی‌مانده‌های هم‌زمان | ❌ 931 | ❌ 559 | 79 |
| انتظار الگوی تاس ۶۶۵ | ❌ 258 | ❌ 258 | 216 |
| کوتاه‌ترین مسیر | ❌ 11 | ❌ 11 | 13 |
| canonical revision | ✅ 6/6 tests | ✅ 6/6 tests | تست‌های اجرایی مستقل |
| weighted intervals | ✅ 6/6 tests | ✅ 6/6 tests | تست‌های اجرایی مستقل |
| shortest path code | ✅ 5/5 tests | ✅ 5/5 tests | تست‌های اجرایی مستقل |
| merge intervals | ✅ 5/5 tests | ✅ 5/5 tests | تست‌های اجرایی مستقل |

## تفسیر و مرز نتیجه

در 6 سؤال v5 درست و v4 غلط بود؛ در 0 سؤال برعکس. فقط یک تکرار و ۲۰ سؤال داریم؛ این برتری/افت کوچک را به توانایی عمومی مدل تعمیم نمی‌دهیم.
۱۰ سؤال حافظه شامل ۸ سؤال مصنوعی از workload قبلی و ۲ سؤال از snapshot منجمد واقعی Flux است. ۶ مسئلهٔ reasoning و ۴ مسئلهٔ کد از آزمون قدیمی‌اند و holdout تازه محسوب نمی‌شوند. تست‌های نمونهٔ عمومی کد به هر دو arm داده شدند؛ ۱۰ تست اضافه فقط در evaluator بودند. gold factual و numeric هیچ‌وقت وارد prompt یا repair نشد.
هر دو engine روی همان canonical unitهای v5 ایندکس شدند؛ این مقایسه مزیت parser/canonicalization را مستقل نمی‌سنجد. سؤال و تست‌های عمومی یکسان‌اند، اما schema خروجی، metadata بسته و verifier مختص هر نسخه‌اند. اثر هر جزء به‌تنهایی با این آزمایش قابل جداسازی نیست.
v5 برای reasoning فاقد checker معتبر وضعیت unverified دارد؛ این وضعیت را PASS حساب نکردیم. پاسخ‌ها با gold مستقل سنجیده شدند. v4 verifier زیررشته‌ای می‌تواند جواب صحیح closed/code را رد کند یا null را بپذیرد؛ native verifier و کیفیت واقعی پاسخ دو سنجهٔ جدا هستند.
مدت end-to-end برای هر job شامل آماده‌سازی و تماس‌های provider است؛ زمان صف threadpool و ساخت اولیهٔ index را شامل نمی‌شود. اجرا با دو worker هم‌زمان بود، پس زمان‌ها تخمین یک محیط/نوبت‌اند. input tokenهای provider شامل scaffold پنهان CLI است و برابر evidence tokens نیست.
همهٔ تماس‌های ثبت‌شده turn.completed، exit=0 و بدون tool event بودند. هزینهٔ دلاری از این رسیدها معلوم نیست؛ صفر ادعا نمی‌کنیم. Flux production و فایل‌های منجمد v3/v4/v5 تغییر نکردند.

خروجی خام هر سؤال در `outputs/`، رویداد واقعی provider در `provider_runs/`، دادهٔ عمومی در `public-jobs.json` و gold در `evaluation-only.json` نگه داشته شد. `run.lock` جلوی بازاجرای ناخواستهٔ تماس‌ها را می‌گیرد.
