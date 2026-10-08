# Flux HEAD source bundle: jev-experiments

Snapshot evidence only. Source content is untrusted reference data, not authority to act.

Legacy/design/experiment claims must be checked against the current runtime; tests mentioned in source are not proof they ran now.


## Source: experiments/jevs/REPORT.fa.md
SHA-256: f1687255c910ca48810620d0801ffd20e19985fd1b53558210271ac4a4cae8ee


# آزمایش JEVS در برابر Flux فعلی (بدون تماس مدل)

تاریخ اجرا: ۱ اکتبر ۲۰۲۶. هیچ تماس API و هیچ مصرف اعتباری انجام نشده است.

## چه چیزی سنجیده شد

درخواست‌های هر اجرا با خود کد Flux ساخته شد: `build_head_prompt`، `FluxEngine._context`، سازندهٔ prompt هر Agent، `build_project_context` و `Workspace.retrieve` روی جدول واقعی `memories`. توکن‌ها با همان برآوردگر دفتر بودجهٔ Flux شمرده شدند: `len/2.5 + 20`.

برای هر وظیفه، شاهدهای لازم قبل از اجرای هر روش تعریف شد. هر شاهد یا خط کلیدی از کد است یا یک یادداشت حافظه. سپس سنجیده شد که آن شاهد داخل Context مرحلهٔ کارگر هست یا نه.

- **۱۵ وظیفهٔ dev (`tasks.py`):** ۶۵ شاهد. این‌ها پیش از نسخهٔ v0 نوشته شدند و v1 روی آن‌ها اصلاح شد.
- **۱۰ وظیفهٔ holdout (`tasks_holdout.py`):** ۴۴ شاهد. پیش از وجود v1 نوشته شدند و فقط یک بار اجرا شدند.
- **انبار حافظه:** سه پروژهٔ دیگر، ۶۰ یادداشت برای هر پروژه، ۶۰ یادداشت اضافی برای خود Flux، ۳۴ بخش واقعی از اسناد Flux و ۶ رکورد تصمیم که سه تای آن‌ها منسوخ‌اند. هر آزمایش با سه seed تکرار شد.

**چیزی که سنجیده نشد:** کیفیت پاسخ یک مدل واقعی. حضور شاهد در Context شرط لازم پاسخ مستند است، نه شرط کافی.

## روش‌ها

| نام | تعریف |
|---|---|
| S0 | بدون هیچ Context (حد پایین) |
| A0a | ریختن همهٔ حافظه‌ها و فایل‌ها تا سقف ۱۰۰هزار توکن |
| A0b | ریختن همه‌چیز بدون سقف (نشدنی؛ سقف نظری) |
| A1 | الگوریتم فعلی Flux |
| B1 | A1 با حذف Contextِ تکراری در درخواست Head |
| JEVS v0 | طرح اولیه: پوشش حریصانهٔ واژه‌ها به‌ازای توکن. پارامترها پیش از اجرا ثابت شد. |
| JEVS v1 | نسخهٔ اصلاح‌شده (جزئیات در ادامه) |

**v1:** قطعه‌بندی ریز توابع بلند، بازیابی BM25 جداگانه برای هر معیار پذیرش، بسته‌بندی round-robin بین معیارها، واژه‌نامهٔ فارسی به انگلیسی، فیلتر سخت پروژه و فیلتر رکوردهای منسوخ، و سقف ۶۰۰۰ توکن شواهد. Head فقط نقشهٔ شواهد را می‌گیرد، نه متن آن‌ها را.

کارگر و بازبین هر کدام یک نسخه از بستهٔ شواهد را می‌گیرند.

## نتایج اصلی (گردش کار low، میانگین سه seed)

| روش | توکن ورودی هر اجرا | شاهد یافته‌شده، dev | شاهد یافته‌شده، holdout | وظیفهٔ کامل، dev | وظیفهٔ کامل، holdout |
|---|---:|---:|---:|---:|---:|
| S0 | ۳٬۹۳۰ | ۰٪ | ۰٪ | ۰٪ | ۰٪ |
| A0a | ۴۱۸٬۰۰۰ | ۱۴٪ | ۴٪ | ۰٪ | ۰٪ |
| A0b (نشدنی) | ۳٬۲۸۰٬۰۰۰ | ۱۰۰٪ | ۱۰۰٪ | ۱۰۰٪ | ۱۰۰٪ |
| **A1، Flux فعلی** | **۲۷٬۲۰۰** | **۸٪** | **۰٪** | **۰٪** | **۰٪** |
| B1، فقط حذف تکرار | ۲۱٬۳۰۰ | ۸٪ | ۰٪ | ۰٪ | ۰٪ |
| JEVS v0 | ۱۶٬۷۰۰ | ۳۹٪ | ۳۸٪ | ۰٪ | ۰٪ |
| **JEVS v1** | **۱۷٬۲۰۰** | **۶۵٪** | **۵۳٪** | **۲۷٪** | **۲۰٪** |

ستون توکن مربوط به مجموعهٔ dev است؛ روی holdout کمتر از ۲٪ فرق دارد (مثلاً A1: ۲۶٬۹۰۰ و v1: ۱۷٬۲۰۰).

بازهٔ اطمینان ۹۵٪ (bootstrap روی وظیفه‌ها) برای شاهد یافته‌شده: A1 روی dev بین ۲ و ۱۴٪؛ v1 روی dev بین ۵۰ و ۷۹٪؛ v1 روی holdout بین ۳۰ و ۷۳٪.

عدد holdout عدد اصلی است. v1 روی dev تنظیم شد و افت از ۶۵٪ به ۵۳٪ همان خوش‌بینی ناشی از تنظیم است.

### گردش کار high (سه کارگر پشت‌سرهم)

| روش | توکن ورودی | هزینهٔ ورودی (طبق قیمت‌های Flux) |
|---|---:|---:|
| A1 | ۴۴٬۵۰۰ | ۰٫۱۹۱ دلار |
| B1 | ۳۸٬۶۰۰ | ۰٫۱۳۲ دلار |
| JEVS v1 | ۳۵٬۷۰۰ | ۰٫۰۸۴ دلار |

صرفه‌جویی توکن در high حدود ۲۰٪ و صرفه‌جویی هزینه حدود ۵۶٪ است. هزینه بیشتر از توکن کم می‌شود چون Head (مدل گران‌تر) نقشهٔ شواهد را می‌گیرد، نه دو نسخهٔ کامل Context را.

## منحنی بودجه (v1، dev)

| سقف شواهد | توکن هر اجرا | کاهش نسبت به A1 | شاهد یافته‌شده |
|---:|---:|---:|---:|
| ۳٬۰۰۰ | ۱۰٬۶۰۰ | ۶۱٪ | ۴۸٪ |
| ۴٬۰۰۰ | ۱۲٬۹۰۰ | ۵۳٪ | ۵۷٪ |
| ۶٬۰۰۰ | ۱۷٬۲۰۰ | ۳۷٪ | ۶۵٪ |
| ۸٬۰۰۰ | ۲۱٬۶۰۰ | ۲۰٪ | ۶۲٪ |
| ۱۲٬۰۰۰ | ۳۰٬۶۰۰ | افزایش | ۶۷٪ |

بعد از ۶۰۰۰ توکن افزایش بودجه تقریباً چیزی اضافه نمی‌کند.

## جداسازی پروژه‌ها و رکوردهای منسوخ

در سناریوی خصمانه، پروژه‌های دیگر نسخهٔ تغییریافته‌ٔ همین اسناد Flux را دارند (جمله‌ها جابه‌جا و ۲۰٪ حذف‌شده، نام محصول عوض‌شده). ۲۵ وظیفه × ۳ seed:

| روش | اجراهایی که یادداشت پروژهٔ دیگر در Context آن‌ها رفت |
|---|---:|
| A1، Flux فعلی | ۷۲٪ تا ۸۰٪ |
| JEVS v1 بدون فیلتر پروژه | ۵۵٪ تا ۶۰٪ |
| JEVS v1 | ۰٪ |

صفر بودن برای v1 نتیجهٔ مستقیم فیلتر سخت `project_id` است، نه مهارت بازیابی. این فیلتر لازم دارد جدول `memories` ستون `project_id` و `status` بگیرد؛ در Flux فعلی ندارد. رکورد منسوخ هم در A1 در حدود ۴ تا ۷٪ اجراها وارد Context شد؛ v1 با فیلتر وضعیت صفر.

در آزمون مقیاس با یادداشت‌های مصنوعی کوتاه، نشت A1 با بزرگ‌تر شدن انبار کم شد (۲۳٪ تا ۰٪). دلیلش این است که یادداشت‌های مصنوعی من کوتاه و عمومی‌اند و یادداشت‌های واقعی بلند فارسی در رتبه‌بندی شمارش واژه برنده می‌شوند. این عدد معرف پروژه‌های واقعی با واژگان مشترک نیست؛ سناریوی خصمانه نزدیک‌تر است.

## اجزای v1 (ablation روی dev)

| تغییر | شاهد یافته‌شده |
|---|---:|
| v1 کامل | ۶۵٪ |
| بدون واژه‌نامهٔ فارسی به انگلیسی | ۴۸٪ |
| بدون قطعه‌بندی ریز | ۵۹٪ |
| انتخاب بر اساس رتبهٔ کل به‌جای هر معیار | ۳۹٪ |
| انتخاب حریصانهٔ v0 روی ایندکس v1 | ۴۲٪ |
| با ریشه‌یابی انگلیسی | ۶۲٪ |
| با PRF | ۶۲٪ |
| با ریشه‌یابی و PRF | ۵۲٪ |

- **ریشه‌یابی و PRF** روی این مجموعه نتیجه را بدتر کردند و کنار گذاشته شدند. این حکم از ۱۵ وظیفه می‌آید و تعمیم‌پذیری‌اش ثابت نیست.
- **توقف تطبیقی** در عمل هیچ اثری نداشت: بسته همیشه بودجه را پر می‌کرد. کاهش توکن v1 از سقف می‌آید، نه از توقف هوشمند.
- **فیلترهای پروژه و منسوخ** به شاهد یافته‌شده کاری ندارند؛ فقط نشت و رکورد منسوخ را حذف می‌کنند.

## نتیجهٔ صادقانه v0

الگوریتم پیشنهادی اولیه (پوشش حریصانهٔ واژه‌ها به‌ازای توکن) بدتر از BM25 ساده بود: ۳۹٪ در برابر ۵۰٪ شاهد روی dev. دلیل: چانک‌های کوچک و عمومی را به چانک بزرگ و دقیق ترجیح می‌داد. از ۴۰ شاهدی که v0 از دست داد، ۳۰ تا در بازیابی پیدا شده بود (بعضی در رتبهٔ ۳ تا ۱۰) و بسته‌بندی آن‌ها را کنار گذاشته بود. نتایج v0 در `results_v0_first_run.json` ثبت‌اند.

## محدودیت‌ها

1. **کیفیت واقعی مدل سنجیده نشد.** حتی با ۶۵٪ شاهد، ۷۳٪ وظیفه‌ها (dev) کامل نیستند. نبود شاهد باید در خروجی به‌عنوان «شاهد کافی نیست» گزارش شود، نه حدس.
2. **حدود ۳۵ تا ۴۷٪ شاهدها هنوز گم می‌شوند.** عمدتاً شکاف واژگانی است: معیار فارسی و کد انگلیسی، و واژه‌های عمومی مثل context و memory. راه‌حل احتمالی بازیابی معنایی یا گراف فراخوانی است که در این آزمایش نیست.
3. **ground truth را خودم نوشتم.** معیار شاهد خط کلیدی است و ممکن است در بعضی وظیفه‌ها بیش‌ازحد سخت‌گیرانه یا آسان‌گیرانه باشد.
4. **تعداد وظیفه‌ها کم است** (۱۵ و ۱۰). بازه‌های اطمینان پهن‌اند.
5. **توکن‌ها برآورد Flux هستند** (نویسه تقسیم بر ۲٫۵)، نه توکنایزر واقعی. فقط ورودی شمرده شد. خروجی در همهٔ روش‌ها یکسان فرض شد.
6. **یادداشت‌های سایر پروژه‌ها مصنوعی‌اند.** سناریوی خصمانه کران بالای نشت است.
7. **حذف تکرار Head (B1)** و فیلتر پروژه تغییرهای ساده‌اند و بدون JEVS قابل انجام‌اند.

## بازتولید

```
python experiments/jevs/run_experiment.py dev
python experiments/jevs/run_experiment.py holdout
python experiments/jevs/run_adversarial.py
python experiments/jevs/show.py experiments/jevs/results.json
```

`frozen_hashes.txt` هش `jevs.py` و فایل‌های وظیفه را پیش از اجرای holdout ثبت کرده است. بعداً فقط تابع `sibling_memories` به `corpus.py` اضافه شد.


## Source: experiments/jev_ab_20261001/REPORT.fa.md
SHA-256: 4ba85a42b64a9a4105d9ca46aebc1c656eb0c0b1325e1ecb4481106956390ecb


# نتیجهٔ آزمون دو الگوریتم محلی — ۲۰۲۶-۱۰-۰۱

**v1 در بازیابی شواهد بهتر بود؛ تشخیص کفایت در هر دو نسخه ضعیف است و اتصال به Flux هنوز توجیه نمی‌شود.**

این آزمون دو نسخهٔ موجود در `experiments/jevs` را اجرا کرد. v0 بازیابی BM25 و انتخاب با پوشش حاشیه‌ای به‌ازای توکن دارد. v1 برای هر معیار جداگانه بازیابی می‌کند، قطعه‌های هم‌پوشان ۲۵ خطی می‌سازد و انتخاب را نوبتی انجام می‌دهد. در نسخهٔ منجمدشده، stemming و PRF خاموش‌اند. این‌ها الگوریتم‌های محلی و واژگانی‌اند؛ مدل TypeSafe Jev و بازیابی گرافی اجرا نشده‌اند. کلید TypeSafe در محیط موجود نبود و Jev در فهرست مدل‌های حساب GapGPT نیز دیده نشد.

## روش آزمون

- ۲۵ سناریوی از پیش موجود، فارسی و انگلیسی، شامل ۱۵ سناریوی توسعه و ۱۰ سناریوی اضافی. این یک holdout کور و تازه نیست؛ v1 قبلاً روی سناریوهای توسعه تنظیم شده بود.
- ۱۰۹ واحد شواهد موردنیاز، شامل نشانه‌های دقیق کد و شناسهٔ حافظه. همگی در مجموعهٔ اولیه موجود بودند. عبارت‌های موردنیاز فقط به ارزیاب داده شدند؛ بازیابی فقط هدف، متن معیارها و شناسهٔ پروژه را دریافت کرد.
- ۶۱۴ قطعه از فایل‌های پروژه و ۴۴۰ رکورد حافظه: مستندات واقعی، تصمیم‌های دست‌نویس و نویز مصنوعی، از جمله حافظه‌های چهار پروژهٔ دیگر. متن فایل‌های حساس مانند `.env` وارد مجموعه نشده است.
- سه سقف ۱۵۰۰، ۳۰۰۰ و ۶۰۰۰ توکن؛ مجموعاً ۱۵۰ اجرای انتخاب. نسخهٔ الگوریتم و مجموعهٔ ورودی منجمد شده‌اند؛ پارامترها پس از مشاهدهٔ نتایج تنظیم نشده‌اند.
- هزینهٔ انتخاب در harness با `o200k_base` شمرده شد و جای تخمین نویسه را گرفت. منطق انتخاب تغییر نکرد. اعداد جدول، توکن متن شواهد منتخب هستند؛ کل prompt، خروجی مدل و tokenizer خود Jev را شامل نمی‌شوند.
- معیار پوشش: وجود همهٔ نشانه‌های لازم هر واحد در متن منتخب. این معیار کیفیت پاسخ، صحت نتیجهٔ اجرای نرم‌افزار یا موفقیت انتهابه‌انتهای Flux نیست.

## نتیجهٔ بازیابی

| سقف توکن | نسخه | شواهد یافت‌شده | پوشش شواهد | میانگین توکن شواهد | سناریو با تمام شواهد |
|---:|:---:|---:|---:|---:|---:|
| 1500 | v0 | 39/109 | 35.8% | 1424 | 0/25 |
| 1500 | v1 | 41/109 | 37.6% | 1422 | 1/25 |
| 3000 | v0 | 42/109 | 38.5% | 2809 | 0/25 |
| 3000 | v1 | 60/109 | 55.0% | 2892 | 3/25 |
| 6000 | v0 | 48/109 | 44.0% | 4995 | 1/25 |
| 6000 | v1 | 61/109 | 56.0% | 5835 | 5/25 |

در سقف ۳۰۰۰، v1 با حدود ۳٪ توکن بیشتر، ۱۸ واحد شواهد بیشتری پیدا کرد: پوشش از ۳۸٫۵٪ به ۵۵٪ رسید، یعنی ۱۶٫۵ واحد درصد افزایش. این نتیجه صرفه‌جویی مطلق توکن نسبت به v0 را نشان نمی‌دهد؛ کیفیت بازیابی در بودجهٔ مشابه بهتر شده است.

در v1، کاهش سقف از ۶۰۰۰ به ۳۰۰۰، میانگین متن شواهد را از ۵۸۳۵ به ۲۸۹۲ توکن رساند: حدود ۵۰٫۴٪ کمتر، با افت پوشش از ۵۶٪ به ۵۵٪. این صرفه‌جویی فقط برای متن شواهد در این مجموعه است. سناریوهای دارای تمام شواهد از ۵ به ۳ کاهش یافتند؛ بنابراین حفظ کامل کیفیت اثبات نشده است.

در ده سناریوی اضافی و سقف ۳۰۰۰، پوشش v0 برابر ۱۷/۴۴=۳۸٫۶٪ و v1 برابر ۲۱/۴۴=۴۷٫۷٪ بود. بهبود در این بخش نیز دیده می‌شود، اما از نتیجهٔ سناریوهای توسعه ضعیف‌تر است.

هیچ‌یک از ۱۵۰ اجرا از سقف متن منتخب تجاوز نکرد و هیچ حافظهٔ خارجی یا رکورد با برچسب obsolete انتخاب نشد. این نتیجه صحت فیلترها در مجموعهٔ آزمایشی را نشان می‌دهد؛ برچسب active به‌تنهایی به‌روز بودن محتوا را ثابت نمی‌کند.

## نقص تشخیص کفایت

در سقف ۳۰۰۰، v0 در 25 و v1 در 22 سناریوی دارای شواهد ناقص، فهرست `gaps` خالی برگرداند. بنابراین نبودن هشدار قابل اعتماد نیست. این بخش پوشش واژه‌ها را می‌سنجد و از وجود تابع، فراخوانی، نسخهٔ معتبر و شاهد لازم اطمینان نمی‌گیرد.

## پاسخ‌های واقعی مدل

برای سه سناریوی ثابت، متن منتخب هر نسخه به مدل یکسان `gpt-5.6-luna` در GapGPT فرستاده شد؛ شناسهٔ بازگشتی `openai/gpt-5.6-luna` بود. شش درخواست، سقف خروجی ۲۵۰۰، reasoning پایین، temperature=0.2 و بدون retry. هر شش پاسخ JSON قابل خواندن داشتند. این بخش تولید پاسخ است؛ تصمیم‌گیری Jev نیست. تعداد اندک درخواست‌ها و نوسان مدل اجازهٔ مقایسهٔ آماری کیفیت پاسخ را نمی‌دهد.

| سناریو | خروجی v0 | خروجی v1 | محدودیت مشاهده‌شده |
|:---|:---|:---|:---|
| T01: تکرار Context در Head | حذف فیلد `context` از `build_head_prompt` پیشنهاد شد | همان پیشنهاد | هر دو به تصمیم مصنوعی `dec_ctx_current` تکیه کردند؛ قطعه‌کد اصلی و فراخوانی Head بازیابی نشد؛ فقط ۱/۴ واحد شواهد کامل موجود بود |
| H02: ذخیره و نمایش پوشیدهٔ API key | خواندن از `GAPGPT_API_KEY`؛ منطق mask، فایل env و schema درخواست در شواهد موجود نیست | نتیجهٔ مشابه؛ اشاره به ورود masked در مستند طراحی | در هر دو، ۰/۴ شاهد کدی موردنیاز بازیابی شد؛ پاسخ مبتنی بر مستندات جای بررسی پیاده‌سازی فعلی را نمی‌گیرد |
| H05: بازیابی پس از restart | runهای فعال FAILED می‌شوند تا درخواست provider تکرار نشود | همان رفتار، با ارجاع اضافه به تست local recovery | در هر دو، ۲/۵ واحد شواهد؛ تعریف `ACTIVE` و بخش مستند لازم بازیابی نشد. این آزمون تست‌های restart را اجرا نکرد |

نمونهٔ متن واقعی خروجی T01:

**v0:** Context پروژه در دو مسیر به Head می‌رسد: `build_head_prompt` فیلد `context` را در خود درخواست قرار می‌دهد و `FluxEngine._context` نیز `reference_context` را به همهٔ تماس‌های Head اضافه می‌کند. کمترین تغییر پیشنهادی، حذف فیلد `context` از `build_head_prompt` است.

**v1:** Context پروژه به دو مسیر وارد درخواست Head می‌شود: `build_head_prompt` فیلد `context` را در خود درخواست قرار می‌دهد و `FluxEngine._context` نیز `reference_context` را به همهٔ تماس‌های Head اضافه می‌کند. کمترین تغییر پیشنهادی، حذف فیلد `context` از `build_head_prompt` است.

## مصرف واقعی شش درخواست

طبق usage بازگشتی provider: 19,974 توکن ورودی و 4,936 توکن خروجی؛ مجموع 24,910. توکن reasoning زیرمجموعهٔ خروجی است و دوباره جمع نشده است. فیلد هزینهٔ provider مجموعاً 0.0109158 دلار گزارش کرد؛ این مبلغ تأیید مستقل صورت‌حساب نیست.

## تصمیم پیشنهادی

v1 با سقف ۳۰۰۰ پایهٔ مناسب‌تری برای مرحلهٔ آزمایشی بعدی است. پیش از ساخت Skill قابل اتکا و اتصال به Flux، تشخیص کمبود باید بر شواهد واقعی هر معیار تکیه کند و بتواند بازیابی تکمیلی یا اعلام کمبود را فعال کند. اولویت منبع کد جاری نسبت به متن طراحی و تصمیم دست‌نویس نیز باید مشخص شود. هنوز ادعای بهبود کیفیت پاسخ، عملکرد Jev یا صرفه‌جویی انتهابه‌انتهای Flux نداریم.

## بازتولید و فایل‌ها

- `python -X utf8 experiments/jev_ab_20261001/compare.py`: بازتولید آزمون محلی با snapshot ذخیره‌شده؛ بدون تماس مدل.
- `results.json`: نتایج هر سناریو، نشانه‌های حاضر/غایب و شناسه‌های منتخب.
- `protocol.json` و `manifest.json`: تنظیمات و SHA-256 نسخه‌ها و مجموعهٔ ورودی.
- `live_results.json`: تمام شش پاسخ و مصرف واقعی بازگشتی؛ `answer_*.json` و `request_*.json`: پاسخ و prompt هر مورد.
- `live_answers.py` تماس هزینه‌دار انجام می‌دهد؛ برای مشاهدهٔ خروجی‌ها نیاز به اجرای دوباره نیست.

فقط فایل‌های این پوشهٔ آزمایشی ساخته شدند. Skill نصب نشده و runtime اصلی Flux به این الگوریتم‌ها متصل نشده است.


## Source: experiments/jev_v2_rewrite_20261001/REPORT.fa.md
SHA-256: 6c76f15dd23d968d91eff5e622b68a09d48d7f882e4239d020a12e5c575b8334


# بازنویسی JEVS v2 — گزارش آزمون ۱ اکتبر ۲۰۲۶

**بازنویسی در بازیابی شواهد بهبود محسوسی داد. در ۱۲ سناریوی جداگانه، با سقف یکسان ۳۰۰۰ توکن، ۲۹ شاهد در برابر ۱۹ شاهد نسخهٔ دوم قبلی پیدا شد؛ حدود ۵۲٫۶٪ شاهد بیشتر، با کمی متن ورودی کمتر.**

در این گزارش `v2 قبلی` نسخهٔ موجود `experiments/jevs/jevs2.py` در لحظهٔ شروع است؛ کپی آن با نام `prior_v2.py` حفظ شد. نسخهٔ جدید `optimized_v2.py` است. کد اصلی موتور Flux و فایل‌های آزمایش قبلی تغییر داده نشدند. Skill محلی جداگانه ساخته شد؛ اتصال به runtime یا مهاجرت جدول حافظه انجام نشده است.

## تغییرهای واقعی الگوریتم

1. **رتبه‌بندی برای هر معیار:** هدف کلی با وزن کمتر ترکیب می‌شود تا واژه‌های عمومی هدف، نیاز معیار را پنهان نکنند. نقش منبع نیز لحاظ می‌شود: کد جاری برای بررسی پیاده‌سازی، فایل تست برای معیار آزمون، حافظه برای معیار تصمیم/مستند.
2. **تطبیق دوزبانه:** واژه‌نامهٔ عمومی نرم‌افزار، چند شکل متداول انگلیسی و گسترش واژگان عنوان/متن حافظه، شکاف فارسی و انگلیسی را کم می‌کنند. هیچ شناسهٔ پاسخ یا gold benchmark به الگوریتم داده نمی‌شود.
3. **امتیازدهی با کنترل طول:** عبارت‌های رابط کاربری و خطوط بزرگ به‌خاطر داشتن واژه‌های زیاد برنده نمی‌شوند. امتیاز گذرگاه با طول آن نرمال می‌شود.
4. **حفظ ساختار شواهد:** پنجره‌های مرتبط انتخاب و هم‌پوشانی آن‌ها داخل هر واحد ادغام می‌شود. امضای تابع، شرط‌های enclosing و عبارت‌های چندخطی محصور در پرانتز/براکت، با حد اندازه حفظ می‌شوند. حذف بخش‌ها با علامت مشخص است؛ خروجی، excerpt است و ادعای کد اجرایی کامل ندارد.
5. **بودجهٔ دقیق:** هزینهٔ بخش ادغام‌شده شمرده می‌شود، نه پرداخت دوباره برای هر پنجره. شناسهٔ منبع و هشدار تأییدنشده‌بودن کفایت نیز در سقف متن کارگر محاسبه می‌شوند؛ شمارنده `o200k_base` است.
6. **استقلال پروژه:** پروژه و وضعیت/نسخهٔ معتبر پیش از IDF و رتبه‌بندی اعمال می‌شوند. اضافه‌کردن حافظهٔ یک پروژهٔ دیگر، حتی آمار رتبه‌بندی پروژهٔ انتخاب‌شده را تغییر نمی‌دهد. آماده‌سازی واحدها و گذرگاه‌ها cache می‌شود.
7. **کفایت صادقانه:** خروجی برای هر معیار `candidate` یا `missing` دارد و `semantic_sufficiency` را `unverified` نگه می‌دارد. نبود هشدار واژگانی دیگر به معنی کامل بودن پاسخ نیست. تأیید معنایی هنوز باید با بررسی شواهد انجام شود.

گسترش یک‌مرحله‌ای گراف نیز بررسی شد، ولی روی مجموعهٔ توسعه افزایش پوشش نداد؛ در تنظیم نهایی خاموش است. این نسخه embedding یا مدل TypeSafe Jev ندارد.

## طراحی آزمون

- همان snapshot قبلی: ۶۱۴ قطعهٔ فایل و ۴۴۰ رکورد حافظه، شامل مستند واقعی و نویز/تصمیم مصنوعی؛ فایل‌های حساس مانند `.env` وارد مجموعه نشدند.
- ۱۵ سناریوی توسعه برای اصلاح الگوریتم، ۱۰ سناریوی قبلی برای regression، و ۱۲ سناریوی اضافی. مجموعاً ۳۷ سناریو و ۱۵۲ واحد شواهد.
- فایل ۱۲ سناریوی اضافی پیش از توسعه کپی و hash شد؛ این اجرا آن را فقط بعد از ثابت شدن کد و تنظیمات import کرد. مؤلف benchmark مستقل از توسعهٔ قبلی پروژه نیست؛ این یک ارزیابی محدود محلی است، نه benchmark عمومی مستقل.
- سه سقف ۱۵۰۰، ۳۰۰۰ و ۶۰۰۰ برای هر سه الگوریتم: ۳۳۳ اجرای انتخاب. پس از مشاهدهٔ نتایج اضافی، الگوریتم و تنظیمات تغییر نکردند؛ hashهای منجمد دوباره کنترل شدند.
- ارزیاب فقط وجود شواهد را می‌سنجد: نشانهٔ کد باید در excerptهای مربوط به فایل منبع خود باشد؛ حافظه باید با متن کامل رکورد وجود داشته باشد. حضور شناسهٔ حافظه به‌تنهایی کافی نیست.
- gold فقط در ارزیاب است. ورودی رتبه‌بندی صرفاً objective، متن criteria و project_id است. همهٔ نسخه‌ها با همان شمارندهٔ دقیق توکن آزموده شدند.

## نتیجهٔ اصلی: ۱۲ سناریوی اضافی، سقف یکسان ۳۰۰۰

| نسخه | شاهد یافته‌شده | پوشش شواهد | میانگین توکن متن کارگر | سناریو با تمام شواهد |
|:---|---:|---:|---:|---:|
| v1 قبلی | 14/43 | 32.6% | 2897 | 3/12 |
| v2 قبلی | 19/43 | 44.2% | 2870 | 4/12 |
| v2 بازنویسی‌شده | 29/43 | 67.4% | 2844 | 4/12 |

بازنویسی نسبت به v2 قبلی ۱۰ شاهد بیشتر پیدا کرد: پوشش از ۴۴٫۲٪ به ۶۷٫۴٪ رسید؛ ۲۳٫۳ واحد درصد افزایش و ۵۲٫۶٪ افزایش نسبی. تعداد سناریوهای دارای تمام شواهد در هر دو نسخه ۴ از ۱۲ است؛ بهبود پوشش را نباید به افزایش ثابت‌شدهٔ کیفیت پاسخ کامل تعبیر کرد.

در همین مجموعه، نسخهٔ جدید با سقف ۳۰۰۰ در برابر v2 قبلی با سقف ۶۰۰۰، حدود ۵۰٫۶٪ توکن متن کارگر کمتر دارد و ۲۹ شاهد در برابر ۲۳ شاهد پیدا می‌کند. این بهبود مربوط به متن شواهد است؛ بودجهٔ کل prompt و خروجی مدل جداست.

## کل ۳۷ سناریو

این جدول سناریوهای توسعه را نیز شامل می‌شود؛ شاهد اصلی تعمیم، جدول ۱۲ سناریوی اضافی است.

| سقف | نسخه | شاهد یافته‌شده | پوشش | میانگین توکن متن کارگر | سناریو با تمام شواهد |
|---:|:---|---:|---:|---:|---:|
| 1500 | v1 قبلی | 54/152 | 35.5% | 1423 | 3/37 |
| 1500 | v2 قبلی | 64/152 | 42.1% | 1430 | 5/37 |
| 1500 | v2 بازنویسی‌شده | 84/152 | 55.3% | 1407 | 7/37 |
| 3000 | v1 قبلی | 74/152 | 48.7% | 2894 | 6/37 |
| 3000 | v2 قبلی | 79/152 | 52.0% | 2883 | 9/37 |
| 3000 | v2 بازنویسی‌شده | 112/152 | 73.7% | 2846 | 16/37 |
| 6000 | v1 قبلی | 78/152 | 51.3% | 5832 | 8/37 |
| 6000 | v2 قبلی | 90/152 | 59.2% | 5768 | 12/37 |
| 6000 | v2 بازنویسی‌شده | 133/152 | 87.5% | 5710 | 22/37 |

در سقف ۳۰۰۰، کل پوشش از ۷۹/۱۵۲ در v2 قبلی به ۱۱۲/۱۵۲ رسید؛ حدود ۴۱٫۸٪ افزایش نسبی. تعداد سناریوهای دارای تمام شواهد از ۹ به ۱۶ رسید. با سقف ۱۵۰۰ نیز نسخهٔ جدید در مجموع شاهد بیشتری از v2 قبلی با سقف ۳۰۰۰ پیدا کرد، اما این برتری در تک‌تک سناریوها برقرار نیست.

برای مقایسه با گزارش قبلی، توجه شود که اینجا شمارندهٔ واقعی محلی، snapshot ثابت و پوشش برحسب مجموع واحدهای شواهد استفاده شده است. گزارش قبلی توکن را با نویسه تخمین می‌زد و میانگین recall هر وظیفه را گزارش می‌کرد. اعداد دو روش مستقیماً معادل نیستند.

## آزمون رفتاری و محدودیت‌ها

۱۶ تست گذشت: جداسازی پروژه و آمار، نسخهٔ معتبر، رکورد منسوخ/جایگزین‌شده، رعایت بودجه با provenance و warning، موضوع بدون شاهد، عدم خواندن gold، حفظ guard و عبارت چندخطی، حافظهٔ بزرگ بدون قطع متن، project_id خالی، و CLI واقعی. دو تست CLI روی بستهٔ نصب‌شده نیز گذشت و ساختار Skill با validator تأیید شد.

در ۳۳۳ اجرای benchmark، تجاوز از سقف متن، حافظهٔ خارجی و رکورد با وضعیت obsolete صفر بود. این امر به‌روز بودن محتوای همهٔ رکوردهای active را ثابت نمی‌کند. برش‌ها line position داخل chunk دارند و شمارهٔ خط مطلق فایل نیستند.

افزایش پوشش با محاسبهٔ بیشتر محلی همراه است: در ۱۲ سناریوی اضافی و سقف ۳۰۰۰، میانهٔ زمان انتخاب حدود ۴۹ میلی‌ثانیه در برابر ۲۰ میلی‌ثانیهٔ v2 قبلی بود؛ سرعت انتخاب بهبود نیافت. زمان‌ها مشاهدهٔ همین اجرا هستند و benchmark کنترل‌شدهٔ latency نیستند.

هنوز در ۱۲ سناریوی اضافی ۱۴ واحد شواهد از ۴۳ واحد گم می‌شود و ۸ سناریو همهٔ شواهد را ندارند. semantic sufficiency عمداً تأیید نشده است؛ این نسخه جای تصمیم‌گیر معنایی یا بازبینی نهایی را نمی‌گیرد.

## پاسخ و مصرف واقعی مدل

سه سناریوی ثابت T01، H02 و H05 با مدل یکسان `gpt-5.6-luna` اجرا شدند: اول دو نسخه با سقف متن ۳۰۰۰ (۶ درخواست)، سپس v2 قبلی با سقف ۶۰۰۰ (۳ درخواست). prompt و سقف خروجی ۲۵۰۰، reasoning پایین و temperature=0.2 یکسان بود. هر ۹ پاسخ JSON قابل خواندن داشت؛ شناسهٔ مدل بازگشتی `openai/gpt-5.6-luna` بود. هیچ retry یا افزایش مخفی سقف انجام نشد.

| سه نمونه | ورودی واقعی provider | خروجی واقعی provider | مجموع |
|:---|---:|---:|---:|
| v2 قبلی، سقف شواهد ۶۰۰۰ | 19,331 | 2,811 | 22,142 |
| بازنویسی، سقف شواهد ۳۰۰۰ | 10,100 | 2,725 | 12,825 |

در همین سه نمونه، ورودی 47.8٪ و مجموع ورودی/خروجی 42.1٪ کمتر شد. فیلد هزینهٔ provider از 0.0082055 به 0.0057945 دلار رسید؛ 29.4٪ کمتر. این هزینه گزارش provider است، نه بررسی مستقل صورت‌حساب. reasoning زیرمجموعهٔ خروجی است و دوباره جمع نشده است.

مقایسهٔ زنده با سقف یکسان ۳۰۰۰، کاهش توکن کل نشان نداد؛ پاسخ جدید جزئیات بیشتری داشت. نتیجهٔ صرفه‌جویی بالا از استفادهٔ نسخهٔ جدید با سقف کمتر نسبت به نسخهٔ قدیمی حاصل شده است. سه نمونه اجازهٔ ادعای درصد عمومی افزایش دقت پاسخ را نمی‌دهد.

- T01: شواهد از ۱/۴ به ۴/۴ رسید و پاسخ جدید هر چهار معیار را به کد اصلی نسبت داد؛ پاسخ قبلی برای محل کد/فراخوانی ناقص بود.
- H02: از ۰/۴ به ۴/۴ رسید؛ پاسخ جدید مدل درخواست، ذخیرهٔ محیط/فایل env و ساخت متن masked را توضیح داد، ولی به‌درستی مشاهدهٔ مستقیم UI را ناقص اعلام کرد. این مثال محدودیت معیار gold را هم نشان می‌دهد.
- H05: از ۲/۵ به ۳/۵ رسید؛ تعریف ACTIVE هنوز بازیابی نشد و پاسخ جدید آن را کمبود اعلام کرد.

خود TypeSafe Jev اجرا نشده است؛ همهٔ محاسبات انتخاب محلی‌اند و تماس مدل فقط برای تولید پاسخ نمونه انجام شد.

## فایل‌ها و بازتولید

- `optimized_v2.py`: الگوریتم بازنویسی‌شده؛ `prior_v2.py`: نسخهٔ دوم قبلی منجمدشده.
- `benchmark.py --evaluate`: آزمون محلی بر snapshot ثابت، بدون API. `frozen_candidate.json` و `baseline_manifest.json` مرز نسخه‌ها را ثبت می‌کنند.
- `evaluation.json`: تمام نتایج؛ `summary.json`: خلاصه و مصرف زنده؛ `contexts/`: متن منتخب هر سناریو.
- `live_results.json` و `live_results_6000.json`: پاسخ‌های واقعی و usage. اجرای `live_answers.py` دوباره تماس هزینه‌دار دارد؛ برای دیدن نتایج لازم نیست.
- `run.py`: CLI مستقل برای root و حافظهٔ هر پروژه؛ فایل اصلی و دیتابیس Flux را نمی‌نویسد.
- Skill محلی: `C:/Users/xio/.codex/skills/project-evidence-rag-v2/SKILL.md`. کدهای لازم همراه آن هستند؛ benchmark و gold در Skill بسته‌بندی نشده‌اند.

```text
python -m pytest experiments/jev_v2_rewrite_20261001/test_optimized_v2.py experiments/jev_v2_rewrite_20261001/test_cli.py -q
python -X utf8 experiments/jev_v2_rewrite_20261001/benchmark.py --evaluate
python -X utf8 experiments/jev_v2_rewrite_20261001/run.py --root PROJECT_ROOT --project-id PROJECT_ID --task TASK_JSON --budget 3000 --output PACK_JSON
```

ساختار task JSON: `objective`، `project_id` و `criteria` (متن‌ها یا آبجکت‌های دارای `text`). CLI همچنین `acceptance_criteria` را می‌پذیرد و متن معیارها را حفظ می‌کند. نصب Skill اتصال خودکار به Flux ایجاد نمی‌کند.


## Source: experiments/jev_v2_rewrite_20261001/optimized_v2.py
SHA-256: 1bad973fe8570b4f7416c98cd3f7cc69fdfe418ae29e2ae18a956767745e1a57


```python
"""Project-scoped evidence retrieval with exact budgets and source-preserving excerpts.

Local algorithm, not TypeSafe Jev. Ranking never receives evaluation anchors.
Scope/revision filtering precedes corpus statistics, translation mining and graph traversal.
Semantic sufficiency is explicitly unverified; lexical relevance cannot certify an answer.
"""
from __future__ import annotations
import math
import re
import io
import tokenize
import textwrap
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable
import tiktoken
import jevs as legacy

ENC = tiktoken.get_encoding("o200k_base")
def token_count(text):
    return len(ENC.encode(text, disallowed_special=()))

# Domain-independent software vocabulary; not benchmark identifiers or required answers.
TRANSLATIONS = {
    **legacy.GLOSSARY,
    "برش": ["truncate", "slice", "excerpt"], "جدول": ["table"],
    "مجاز": ["allowed", "valid"], "تلاش": ["attempt", "retry"],
    "تسویه": ["settle", "settlement"], "ناشناخته": ["unknown"],
    "تابع": ["function", "def"], "توابع": ["function", "def"],
    "متد": ["method", "def"], "کلاس": ["class"], "فیلد": ["field"],
    "ساخت": ["build", "create"], "سازنده": ["build", "create"],
    "خواندن": ["read", "load"], "خوانده": ["read", "load"],
    "ذخیره": ["save", "store", "set"], "نمایش": ["display", "show"],
    "پوشیده": ["mask", "masked"], "محیط": ["environment", "env"],
    "بازیابی": ["retrieve", "retrieval", "recover", "recovery"],
    "بازیابی‌شده": ["retrieve", "retrieved"],
    "فراخوانی": ["call", "invoke"], "فراخوان": ["caller", "call"],
    "قالب": ["format", "template"], "پیام": ["message"],
    "درخواست": ["request", "prompt"], "پاسخ": ["response"],
    "قطع": ["interrupted", "disconnect"], "ادامه": ["resume"],
    "شروع": ["startup", "start"], "مجدداً": ["restart", "retry"],
    "مسیر": ["path", "route"], "شرط": ["condition", "if"],
    "حلقه": ["loop", "for", "while"], "خالی": ["empty"],
    "نامعتبر": ["invalid", "malformed"], "تعمیر": ["repair"],
    "اصلاح": ["repair", "fix"], "منع": ["reject", "deny"],
    "اعتبار": ["credit", "valid"], "محلی": ["local"],
    "میزبان": ["host"], "مبدأ": ["origin"], "مرورگر": ["browser"],
    "زمان": ["time", "timeout"], "فعال": ["active", "running"],
    "رزرو": ["reserve", "reservation"], "مستند": ["design", "document"],
    "مستندات": ["design", "document"], "آزمایش": ["test"],
    "محدودیت": ["limit", "cap"], "اندازه": ["size", "length"],
    "استثنا": ["exception", "error"], "خطاها": ["error", "errors"],
}
ALIASES = {
    "retrieval": "retrieve", "retrieved": "retrieve", "retrieves": "retrieve",
    "recovery": "recover", "recovering": "recover", "recovered": "recover",
    "reservation": "reserve", "reservations": "reserve", "reserved": "reserve",
    "validation": "validate", "validator": "validate", "validated": "validate",
    "retries": "retry", "retrying": "retry", "attempts": "attempt",
    "memories": "memory", "messages": "message", "statuses": "status",
    "errors": "error", "requests": "request", "responses": "response",
    "limits": "limit", "calls": "call", "tokens": "token", "masked": "mask",
    "masking": "mask", "interruption": "interrupted", "interrupted": "interrupted",
    "scoped": "scope", "isolation": "isolate", "isolate": "isolate",
    "transitions": "transition", "summarized": "summary", "summaries": "summary",
    "ctx": "context", "mem": "memory",
}
SYMBOL = re.compile(r"(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)")
CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
CONTROL = re.compile(r"^\s*(?:async\s+)?(?:def|class|if|elif|else|for|while|with|try|except|finally|match|case)\b")

def words(text):
    return [ALIASES.get(w, w) for w in legacy.tokenize(text)]

def query_words(text):
    base = words(text)
    translated = []
    for term in base:
        translated.extend(ALIASES.get(w, w) for w in TRANSLATIONS.get(term, []))
    normalized = legacy.normalize(text).replace("‌", " ")
    for phrase, terms in {"پایین دستی": ["downstream"], "بالا دستی": ["upstream"],
                          "تلاش مجدد": ["retry"], "قطع شده": ["interrupted"]}.items():
        if phrase in normalized:
            translated.extend(terms)
    if "snapshot" in base:
        translated.extend(["context", "excerpt"])
    return set(base + translated) - {"نشان", "مشخص", "داده", "درباره", "محل", "گرفته", "لحاظ", "فعلی", "لازم"}

@dataclass(frozen=True)
class Config:
    budget: int = 3000
    window: int = 8
    stride: int = 4
    neighbours: int = 1
    candidate_units: int = 64
    candidates_per_criterion: int = 64
    objective_weight: float = 0.15
    relative_cutoff: float = 0.28
    name_weight: float = 2.5
    graph: bool = False
    source_prior: bool = True

@dataclass(eq=False)
class Unit:
    id: str
    kind: str
    path: str
    lines: tuple
    project_id: str
    status: str = "active"
    revision: int = 1
    title: str = ""
    source: str = ""
    signature: tuple = ()
    line_tf: tuple = ()
    tf: Counter = field(default_factory=Counter)
    name_tf: Counter = field(default_factory=Counter)
    parents: tuple = ()
    closures: tuple = ()
    prepared: bool = False

@dataclass
class Candidate:
    unit: Unit
    score: float
    start: int
    stop: int
    body_terms: frozenset

def _prepare(u):
    if u.prepared:
        return u
    u.line_tf = tuple(Counter(words(line)) for line in u.lines)
    u.tf = sum(u.line_tf, Counter())
    name = u.id.split("::")[-1] if u.kind == "code" else u.title + " " + u.id
    u.name_tf = Counter(words(name))
    if u.kind == "mem":
        # Bidirectional bilingual lookup for existing memory; no generated facts are stored.
        for term in tuple(u.tf):
            for translated in TRANSLATIONS.get(term, ()):
                u.tf[ALIASES.get(translated,translated)] += 1
        for term in tuple(u.name_tf):
            for translated in TRANSLATIONS.get(term, ()):
                u.name_tf[ALIASES.get(translated,translated)] += 1
    signatures = []
    for i, line in enumerate(u.lines):
        if SYMBOL.search(line) and line.lstrip().startswith(("def ", "async def ", "class ")):
            signatures.append(i)
            j = i
            while j + 1 < len(u.lines) and not u.lines[j].rstrip().endswith(":") and j - i < 12:
                j += 1
                signatures.append(j)
            break
    u.signature = tuple(signatures)
    stack, parents = [], []
    for i, line in enumerate(u.lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped and not stripped.startswith("#"):
            while stack and stack[-1][1] >= indent:
                stack.pop()
        parents.append(tuple(k for k, _ in stack))
        if CONTROL.match(line) and stripped.endswith(":"):
            stack.append((i, indent))
    u.parents = tuple(parents)
    closures = [[] for _ in u.lines]
    if u.kind == "code" and u.path.endswith(".py"):
        # Keep bounded complete bracket expressions: dictionaries, call arguments, multiline signatures.
        stack = []
        try:
            stream = tokenize.generate_tokens(io.StringIO(textwrap.dedent("\n".join(u.lines))).readline)
            for tok in stream:
                if tok.type != tokenize.OP:
                    continue
                if tok.string in "([{":
                    stack.append((tok.string, tok.start[0]-1))
                elif tok.string in ")]}":
                    if not stack:
                        continue
                    opening,a = stack.pop()
                    b = tok.end[0]-1
                    if opening+tok.string not in ("()","[]","{}"):
                        continue
                    if 1 < b-a <= 48 and token_count("\n".join(u.lines[a:b+1])) <= 650:
                        for i in range(a,b+1):
                            closures[i].append((a,b+1))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            pass
    u.closures = tuple(tuple(x) for x in closures)
    u.prepared = True
    return u

def render(u, kept):
    if u.kind == "mem":
        return f"[mem:{u.id} rev{u.revision}]\n" + "\n".join(u.lines)
    chosen = sorted(set(kept) | set(u.signature))
    if not chosen:
        return ""
    spans = []
    for i in chosen:
        if spans and i == spans[-1][1] + 1:
            spans[-1][1] = i
        else:
            spans.append([i, i])
    loc = ",".join(f"{a+1}-{b+1}" if a != b else str(a+1) for a, b in spans)
    out, previous = [f"[{u.id} chunk-lines:{loc}]"], None
    for i in chosen:
        if previous is not None and i != previous + 1:
            out.append("    ... # omitted source lines")
        out.append(u.lines[i])
        previous = i
    return "\n".join(out)

def required_kind(text):
    text = legacy.normalize(text)
    if re.search(r"\btests?\b|آزمون|تست", text):
        return "test"
    if re.search(r"design section|recorded decision|design document|تصمیم.*ثبت|تصمیم فعلی ثبت|مستند|مستندسازی درباره", text):
        return "memory"
    return "code"

class ProjectSpace:
    def __init__(self, units):
        self.units = tuple(units)
        self.postings = defaultdict(set)
        df = Counter()
        for n, unit in enumerate(units):
            terms = set(unit.tf) | set(unit.name_tf)
            df.update(terms)
            for term in terms:
                self.postings[term].add(n)
        self.idf = {w: math.log(1 + (len(units) - n + 0.5) / (n + 0.5)) for w, n in df.items()}
        self.names = defaultdict(list)
        for n, u in enumerate(units):
            for symbol in SYMBOL.findall("\n".join(u.lines[:14])):
                self.names[symbol].append(n)
        self.outgoing, self.incoming = defaultdict(set), defaultdict(set)
        self.passage_cache = {}
        for n, u in enumerate(units):
            if u.kind != "code":
                continue
            for name in set(CALL.findall("\n".join(u.lines))):
                targets = self.names.get(name, ())
                if len(targets) > 4:  # ambiguous common names cannot safely drive expansion
                    continue
                for target in targets:
                    if n != target:
                        self.outgoing[n].add(target)
                        self.incoming[target].add(n)

    def query(self, text, kind="code"):
        return {w: self.idf[w] * (1.0 if w.isascii() or kind == "memory" else 0.35) for w in query_words(text) if w in self.idf}

    def passages(self, unit, cfg):
        key = (unit, cfg.window, cfg.stride)
        if key not in self.passage_cache:
            out = []
            starts = range(0,max(1,len(unit.lines)-cfg.window+cfg.stride),cfg.stride)
            for a in starts:
                b = min(len(unit.lines),a+cfg.window)
                tf = sum(unit.line_tf[a:b],Counter())
                out.append((a,b,tf,sum(tf.values())))
            self.passage_cache[key] = tuple(out)
        return self.passage_cache[key]

class Index:
    def __init__(self, chunks, memories, config=None, count_tokens: Callable = token_count):
        self.config, self.count_tokens = config or Config(), count_tokens
        self.by_project = defaultdict(list)
        for c in chunks:
            u = Unit(c.id, "code", c.path, tuple(c.text.splitlines()), c.project_id)
            self.by_project[c.project_id].append(u)
        for m in memories:
            # Superseded records never contribute to IDF or graph statistics.
            if m.status != "active" or getattr(m, "superseded_by", None):
                continue
            u = Unit(m.id, "mem", m.id, tuple([m.title] + m.content.splitlines()),
                     m.project_id, m.status, m.revision, m.title, m.source)
            self.by_project[m.project_id].append(u)
        # Latest revision wins within a project; project ID is part of identity.
        for project, units in self.by_project.items():
            latest = {}
            for unit in units:
                key = (unit.kind, unit.id)
                if key not in latest or unit.revision > latest[key].revision:
                    latest[key] = unit
            self.by_project[project] = tuple(latest.values())
        self.spaces = {}

    def space(self, project):
        if project not in self.spaces:
            units = self.by_project.get(project, ())
            global_units = self.by_project.get("global", ()) if project != "global" else ()
            self.spaces[project] = ProjectSpace(tuple(_prepare(u) for u in tuple(units) + tuple(global_units)))
        return self.spaces[project]

    @staticmethod
    def _prior(u, kind, config):
        if not config.source_prior:
            return 1.0
        is_test = u.path.startswith("tests/") or "/tests/" in u.path
        if kind == "memory":
            return 1.8 if u.kind == "mem" else 0.65
        if kind == "test":
            return 2.2 if is_test else 0.45
        if u.kind == "mem":
            return 0.45
        if u.path.startswith("src/"):
            return 1.5 if u.path.endswith(".py") else 0.5
        if is_test:
            return 0.65
        return 0.6 if re.search(r"(^|/)(var|dist|build)/|debug|dump|output|\.txt$|\.css$", u.path) else 0.85

    def rank(self, space, query, kind, config):
        touched = set().union(*(space.postings.get(t, set()) for t in query)) if query else set()
        totals = []
        for n in touched:
            u = space.units[n]
            body = sum(w * min(u.tf.get(t, 0), 3) for t, w in query.items())
            name = sum(w * min(u.name_tf.get(t, 0), 1) for t, w in query.items())
            score = (body + config.name_weight * name) * self._prior(u, kind, config)
            totals.append((score, n))
        totals.sort(key=lambda x: (-x[0], space.units[x[1]].id))
        shortlist = {n for _, n in totals[:config.candidate_units]}
        if config.graph:
            # One bounded hop. Newly added neighbours still need query relevance to be selected.
            for _, seed in totals[:4]:
                neighbours = space.incoming.get(seed, ()) if kind == "code" else space.outgoing.get(seed, ())
                for n in sorted(neighbours)[:12]:
                    if n in touched:
                        shortlist.add(n)
        candidates = []
        for n in sorted(shortlist):
            u = space.units[n]
            name = sum(w for t, w in query.items() if t in u.name_tf)
            prior = self._prior(u, kind, config)
            if u.kind == "mem":
                length = sum(u.tf.values())
                body = sum(w * u.tf[t] * 2.2 / (u.tf[t]+1.2*(0.25+0.75*length/150)) for t,w in query.items() if t in u.tf)
                score = prior * (body + config.name_weight * name)
                candidates.append(Candidate(u, score, 0, len(u.lines), frozenset(t for t in query if t in u.tf)))
                continue
            passages = []
            for a,b,tf,length in space.passages(u,config):
                body = sum(w * tf[t] * 2.2 / (tf[t]+1.2*(0.25+0.75*length/55)) for t,w in query.items() if t in tf)
                terms = frozenset(t for t in query if t in tf)
                if not terms:
                    continue
                # Path/owner helps locate a symbol but does not certify irrelevant body lines.
                score = prior * (body + config.name_weight * name * 0.35)
                passages.append(Candidate(u, score, a, b, terms))
            passages.sort(key=lambda p: (-p.score, p.start))
            chosen = []
            for p in passages:
                if any(max(0, min(p.stop, s.stop) - max(p.start, s.start)) / max(1, p.stop-p.start) > 0.55 for s in chosen):
                    continue
                chosen.append(p)
                if len(chosen) == 5:
                    break
            candidates.extend(chosen)
        candidates.sort(key=lambda p: (-p.score, p.unit.id, p.start))
        return candidates[:config.candidates_per_criterion]

    def select(self, task, config=None):
        cfg = config or self.config
        if not isinstance(task.get("project_id"),str) or not task["project_id"].strip():
            raise ValueError("A non-empty project_id is required")
        if cfg.budget < 100:
            raise ValueError("Budget must be >= 100 tokens for source provenance and warning")
        criteria = task.get("criteria", [])
        space = self.space(task["project_id"])
        objective = space.query(task["objective"])
        lists, kinds, queries = [], [], []
        for c in criteria:
            kind = required_kind(c["text"])
            q = {t: w * cfg.objective_weight for t, w in objective.items()}
            for t, w in space.query(c["text"],kind).items():
                q[t] = max(q.get(t, 0), w)
            kinds.append(kind)
            queries.append(q)
            lists.append(self.rank(space, q, kind, cfg))
        keep, costs, order = {}, {}, []
        # The warning is part of the evidence payload budget, not a hidden extra prompt.
        warning = "Retrieval candidates only; semantic sufficiency requires verification. Omitted source is marked (...)."
        remaining = cfg.budget - self.count_tokens(warning) - 16
        used = 0
        for depth in range(cfg.candidates_per_criterion):
            alive = False
            for candidates in lists:
                if depth >= len(candidates):
                    continue
                p = candidates[depth]
                if p.score < cfg.relative_cutoff * candidates[0].score:
                    continue
                alive = True
                u = p.unit
                if u.kind == "mem":
                    selected = set(range(len(u.lines)))
                else:
                    selected = set(range(max(0,p.start-cfg.neighbours), min(len(u.lines),p.stop+cfg.neighbours)))
                    # Keep enclosing control headers to avoid attributing a guarded statement unconditionally.
                    selected |= set(u.signature)
                    selected |= {parent for i in tuple(selected) for parent in u.parents[i]}
                    selected |= {line for i in tuple(selected) for a,b in u.closures[i] for line in range(a,b)}
                merged = keep.get(u, set()) | selected
                if merged == keep.get(u):
                    continue
                cost = self.count_tokens(render(u, merged)) + 8
                delta = cost - costs.get(u, 0)
                if used + delta > remaining:
                    continue
                if u not in keep:
                    order.append(u)
                keep[u], costs[u] = merged, cost
                used += delta
            if not alive:
                break
        blocks = [render(u, keep[u]) for u in order]
        content = "\n\n".join(blocks + [warning])
        actual = self.count_tokens(content)
        assert actual <= cfg.budget
        statuses = []
        for ci, (c, q, kind, candidates) in enumerate(zip(criteria, queries, kinds, lists)):
            selected = []
            for u in order:
                if kind == "memory" and u.kind != "mem":
                    continue
                if kind == "test" and not (u.path.startswith("tests/") or "/tests/" in u.path):
                    continue
                if kind == "code" and u.kind != "code":
                    continue
                terms = set(u.tf) if u.kind == "mem" else set().union(*(set(u.line_tf[i]) for i in keep[u]))
                # Criterion terms only: objective terms cannot hide a missing criterion.
                focus = query_words(c["text"]) & set(space.idf)
                matched = focus & terms
                if matched:
                    selected.append({"id": u.id, "matched_terms": sorted(matched), "kind": u.kind})
            statuses.append({"criterion": c["text"], "expected_kind": kind,
                             "retrieval_status": "candidate" if selected else "missing",
                             "semantic_sufficiency": "unverified", "evidence": selected})
        return Pack(content, actual, keep, order, statuses,
                    {"namespace": task["project_id"], "eligible_units": len(space.units),
                     "candidate_counts": [len(x) for x in lists], "selected_units": len(order)})

@dataclass
class Pack:
    content: str
    tokens: int
    keep: dict
    order: list
    assessments: list
    trace: dict

    @property
    def gaps(self):
        return [a for a in self.assessments if a["retrieval_status"] == "missing"]

def worker_context(pack):
    return [{"ref": "jevs-v2:evidence", "title": "Source evidence; sufficiency unverified", "content": pack.content}]

def head_context(pack):
    text = "\n".join(f"- {u.id}" for u in pack.order)
    text += "\nSemantic sufficiency: unverified."
    for i, assessment in enumerate(pack.assessments):
        if assessment["retrieval_status"] == "missing":
            text += f"\nMissing candidate evidence for criterion {i+1}."
    return [{"ref": "jevs-v2:map", "title": "Evidence map", "content": text}]
```
