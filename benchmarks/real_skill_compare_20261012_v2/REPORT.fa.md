# بنچمارک واقعی Flux v1، SUPER و حالت عادی

تاریخ قرارداد: ۲۰۲۶-۱۰-۱۲، منطقهٔ کاربر Asia/Tehran. آخرین تحلیل UTC: `2026-10-12T20:28:06.462375+00:00`.

وضعیت: **ناتمام**؛ 20 از 114 آزمایش. داده از فراخوانی‌های واقعی CLI، Laya محلی و تست‌های مستقل است.

**مرز تفسیر:** این بازسازی گردش‌کار در harness است. نشست‌های مدل ابزار ندارند؛ تست و گیت واقعی بیرون نشست اجرا می‌شود. این آزمون جای بنچمارک کامل SUPER در ساخت اپ، UI، تحقیق یا محیط تعاملی عادی را نمی‌گیرد.

## نتایج واقعی به تفکیک نوع کار

### محاسبات: ۱۲ تسک مستقل، هرکدام دو تکرار

| بازو | پاسخ نهایی پذیرفته و صحیح | کاندیدای صحیح در audit | پذیرش غلط | توکن معلوم input+output | usage نامعلوم | فراخوانی | تعمیر اضافی | میانگین ثانیه | p50 / p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| عادی · Sol medium | 6/8 | 6/8 | 0 | 62,619 | 2 | 8 | 0 | 46.58 | 34.83 / 90.56 |
| SUPER · Sol medium | 3/4 | 3/4 | 0 | 56,899 | 3 | 6 | 2 | 92.13 | 36.70 / 271.38 |
| Flux · مسیر اصلی | 3/3 | 3/3 | 0 | 33,066 | 0 | 3 | 0 | 52.63 | 58.66 / 84.02 |
| Flux · Sol medium ثابت | 2/2 | 2/2 | 0 | 22,158 | 0 | 2 | 0 | 37.65 | 37.65 / 37.85 |

| مقایسه با عادی | کاهش توکن مشاهده‌شده | فاصلهٔ bootstrap ۹۵٪ | تفاوت دقت (واحد درصد) | کاهش میانگین زمان مشاهده‌شده | برابری کیفیت بی‌خطای مشاهده‌شده |
|---|---:|---:|---:|---:|---|
| SUPER · Sol medium | دادهٔ جفتی ناتمام | — | — | — | — |
| Flux · مسیر اصلی | دادهٔ جفتی ناتمام | — | — | — | — |
| Flux · Sol medium ثابت | دادهٔ جفتی ناتمام | — | — | — | — |

عدد منفی در ستون کاهش یعنی مصرف/زمان بیشتر. اگر مصرف یکی از فراخوانی‌ها معلوم نباشد درصد کاهش حساب نمی‌شود. صرفه‌جویی توکن معادل صرفه‌جویی پول یا سهمیهٔ اشتراک نیست.

### رفع باگ: ۶ تسک مستقل، یک تکرار

| بازو | پاسخ نهایی پذیرفته و صحیح | کاندیدای صحیح در audit | پذیرش غلط | توکن معلوم input+output | usage نامعلوم | فراخوانی | تعمیر اضافی | میانگین ثانیه | p50 / p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| عادی · Sol medium | 2/2 | 2/2 | 0 | 20,812 | 0 | 2 | 0 | 26.55 | 26.55 / 27.65 |
| SUPER · Sol medium | 1/1 | 1/1 | 0 | 19,024 | 0 | 1 | 0 | 37.80 | 37.80 / 37.80 |
| Flux · مسیر اصلی | 0/0 | 0/0 | 0 | 0 | 0 | 0 | 0 | نامعلوم | نامعلوم / نامعلوم |

| مقایسه با عادی | کاهش توکن مشاهده‌شده | فاصلهٔ bootstrap ۹۵٪ | تفاوت دقت (واحد درصد) | کاهش میانگین زمان مشاهده‌شده | برابری کیفیت بی‌خطای مشاهده‌شده |
|---|---:|---:|---:|---:|---|
| SUPER · Sol medium | دادهٔ جفتی ناتمام | — | — | — | — |
| Flux · مسیر اصلی | دادهٔ جفتی ناتمام | — | — | — | — |

عدد منفی در ستون کاهش یعنی مصرف/زمان بیشتر. اگر مصرف یکی از فراخوانی‌ها معلوم نباشد درصد کاهش حساب نمی‌شود. صرفه‌جویی توکن معادل صرفه‌جویی پول یا سهمیهٔ اشتراک نیست.

## الگوریتم‌ها و کنترل عوامل

| ویژگی | عادی | Flux native | Flux matched | SUPER در harness |
|---|---|---|---|---|
| مدل اولیه | Codex Sol medium | Codex Luna low | Codex Sol medium | Codex Sol medium |
| ارتقا/تعمیر | یک پاسخ مستقیم | GapCode Sol high، سپس Codex Astra high | همان Sol medium، حداکثر سه بار | همان Sol medium، حداکثر سه بار |
| برنامهٔ پارامتری | فقط در رفع باگ | refs + solve + check | refs + solve + check | فقط در رفع باگ؛ بدون refs اجباری |
| کنترل محلی | فقط audit نهایی | AST/worker/معیار مستقل + guard | همان Flux | معیار مستقل + گیت عمومی واقعی در رفع باگ |
| Laya | ندارد | FRONT و END واقعی | FRONT و END واقعی | ندارد |
| بررسی هدف/قرارداد | دستور مستقیم | قیدها و facts ثابت | همان Flux | متن کامل اسکیل و framing/reasoning/debug/testing |
| ابزار داخل نشست | غیرفعال | غیرفعال | غیرفعال | غیرفعال |

مقایسهٔ SUPER و عادی، مدل/effort/محیط مشترک دارد؛ تعداد مجاز تلاش و محتوای اسکیل متفاوت است. مقایسهٔ Flux matched با عادی، اثر متفاوت بودن مدل اولیه را حذف می‌کند، اما compact/checker/Laya/retry را جدا از یکدیگر شناسایی نمی‌کند. Flux native مقایسهٔ کل گردش‌کار است؛ اثر Luna، effort و provider هم داخل نتیجه است.

SUPER فقط دستور ورود نیست: متن اسکیل، framing، reasoning، debug و testing به مدل داده شده و هماهنگ‌کننده گیت و review واقعی را اجرا کرده است. با این حال debug case کامل، تحقیق وب و اجرای خودمختار ابزار توسط مدل بازسازی نشده‌اند؛ در اینجا فقط انطباق قرارداد و صحت پاسخ/تعمیر سنجیده شده است.

## وضعیت واقعی گیت‌های SUPER و ایراد ویندوز

```json
{
  "review_verdicts": {
    "STALE": 2
  },
  "raw_gate_statuses": {
    "testing.smells:PASS": 2,
    "testing.run:FAIL": 1,
    "backend.behavior:FAIL": 1,
    "delivery.build:NOT-TESTED": 2,
    "testing.api:NOT-TESTED": 2,
    "testing.run:PASS": 1,
    "backend.behavior:PASS": 1
  }
}
```

در preflight سالم، گیت‌های testing.run، testing.smells و backend.behavior واقعاً PASS شدند، اما verdict بومی SUPER به علت ناسازگاری مسیر report با کلید digests در Windows، STALE بود. `ledger.intact()` قبل از سنجش هش، عضویت رشتهٔ مسیر را بررسی می‌کند: report دارای `/` ولی کلید digests دارای `\` است. هش‌ها و fingerprint واقعاً برابر بودند. اسکیل اصلاح نشده و verdict اصلی با تمام شکاف‌ها نگه داشته شده است.

پذیرش harness بر اساس تست مستقل قرارداد و PASS خام سناریوی مربوط است؛ این پذیرش به معنای PASSED بودن verdict بومی SUPER یا آمادگی انتشار نیست. delivery.build و testing.api برای fixture تابع stdlib پیکربندی نشده‌اند؛ NOT-TESTED را PASS حساب نکرده‌ایم.

## کیفیت ارزیاب و نمونه‌گیری

فاکتور با Decimal و Fraction مستقل کنترل شد؛ شمارش با enumeration و dynamic programming مستقل؛ زمان‌بندی با permutation و DFS مستقل. شش کنترل سالمِ رفع باگ پاس شدند و هر شش نسخهٔ باگ‌دار رد شدند. مقایسهٔ JSON نوع‌دار است: True، 1 و 1.0 قابل جایگزینی نیستند. تغییر ورودی، کلید تکراری JSON، NaN، کد دارای IO و checker ثابت نیز کنترل شده‌اند.

رفع باگ شامل مرز tenant/owner/admin، بازهٔ نیمه‌باز/adjacency، replay/idempotency/conflict، HALF UP، مهاجرت/duplicate/precedence و version-specific field است. ۱۸ کیس عمومی و ۱۳۶ کیس افزودهٔ پنهان وجود دارد؛ مجموع ۱۵۴ مورد در هر audit کامل این شش تسک. تعداد کیس‌ها با تعداد دامنه‌ها اشتباه گرفته نشده است.

Oracle و کد تست پنهان در prompt حل‌کننده یا Laya نیست. Flux و SUPER برای تعمیر فقط بازخورد محدود تست عمومی دریافت می‌کنند. audit پنهان فقط پس از پاسخ نهایی اجرا می‌شود؛ خطای پنهان به solver بازگردانده نمی‌شود. ترتیب با seed قفل‌شده و تصادفی است، تمام شکست‌ها در جدول باقی می‌مانند.

## عدم‌قطعیت آماری

| نوع کار / بازو | تسک مستقل که تمام تکرارهایش موفق است | Wilson ۹۵٪ برای همان معیار |
|---|---:|---:|
| reasoning / عادی · Sol medium | 5/7 | 35.89 تا 91.78٪ |
| reasoning / SUPER · Sol medium | 3/4 | 30.06 تا 95.44٪ |
| reasoning / Flux · مسیر اصلی | 3/3 | 43.85 تا 100.00٪ |
| reasoning / Flux · Sol medium ثابت | 2/2 | 34.24 تا 100.00٪ |
| engineering / عادی · Sol medium | 2/2 | 34.24 تا 100.00٪ |
| engineering / SUPER · Sol medium | 1/1 | 20.65 تا 100.00٪ |
| engineering / Flux · مسیر اصلی | 0/0 | نامعلوم |

bootstrap مصرف/زمان با ۱۰٬۰۰۰ بازنمونه روی **خوشهٔ تسک** است؛ دو تکرار داخل همان تسک میانگین می‌شوند. ۲۴ پاسخ در محاسبات، ۲۴ دامنهٔ مستقل نیستند. دقت ۱۰۰٪ در نمونهٔ کوچک اثبات دقت عمومی ۱۰۰٪ نیست؛ بازهٔ صفرِ تفاوت bootstrap در حالت همه‌موفق نیز عدم‌قطعیت تعمیم را حذف نمی‌کند. p آزمون دقیق جفتی و تعداد برد/باخت در results.json ثبت شده است. این آزمون equivalence با حاشیهٔ ازپیش‌تعیین‌شده نیست.

## مصرف، زمان و محدودیت‌ها

| نوع کار / بازو | input | cached subset | output | reasoning subset | Laya calls / ثانیه | provider failures / timeout |
|---|---:|---:|---:|---:|---:|---:|
| reasoning / عادی · Sol medium | 60,659 | 3,840 | 1,960 | 1,710 | 0 / 0.00 | 2 / 2 |
| reasoning / SUPER · Sol medium | 56,132 | 9,728 | 767 | 656 | 0 / 0.00 | 3 / 3 |
| reasoning / Flux · مسیر اصلی | 30,704 | 14,592 | 2,362 | 0 | 6 / 1.79 | 0 / 0 |
| reasoning / Flux · Sol medium ثابت | 20,387 | 4,864 | 1,771 | 568 | 4 / 2.36 | 0 / 0 |
| engineering / عادی · Sol medium | 20,463 | 0 | 349 | 52 | 0 / 0.00 | 0 / 0 |
| engineering / SUPER · Sol medium | 18,836 | 0 | 188 | 43 | 0 / 0.00 | 0 / 0 |
| engineering / Flux · مسیر اصلی | 0 | 0 | 0 | 0 | 0 / 0.00 | 0 / 0 |

لود سرد Laya در فرایند مشترک:

```json
{
  "load_sessions": [
    {
      "utc": "2026-10-12T20:19:10.379640+00:00",
      "laya_load_s": 10.097777899998619,
      "python": "D:\\project\\Alacrity\\Flux\\experiments\\flux_laya_policy_20261006\\.venv\\Scripts\\python.exe"
    }
  ]
}
```

زمان هر trial شامل تماس مدل، انتظار محلی، تست و audit است. دو trial هم‌زمان اجرا شده‌اند و Laya قفل مشترک دارد؛ شبکه، کش و بار CPU/GPU کنترل نشده‌اند. بارگذاری اولیهٔ Laya جدا ثبت شده و داخل زمان گرم هر trial نیست. از این نمونه ادعای برتری سرعت سرد، مصرف برق یا سرعت production نمی‌کنیم.

input+output مصرف گزارش‌شدهٔ provider است؛ cached و reasoning زیرمجموعه‌اند و دوباره جمع نشده‌اند. هزینهٔ کیف پول، وزن سهمیهٔ اشتراک، توکن این چت هماهنگ‌کننده و برق محلی اندازه‌گیری نشده‌اند. usage نامعلوم صفر نشده است. هویت مدل فقط نام درخواست‌شدهٔ client است و مستقلاً در server تأیید نشده است. CLI ممکن است retry داخلی داشته باشد؛ یک invocation را یک wire request قطعی سمت سرور حساب نکرده‌ایم.

## پروندهٔ اجرای اولیه و تغییرات روش

بنچمارک قدیمی والد از عدد تصادفی و oracle استفاده می‌کرد و به‌عنوان شبیه‌سازی برچسب خورد. pilot واقعی اول با ۱۱ trial متوقف شد چون ابزارها در CLI با policy رد می‌شدند؛ تمام رسیدها در ../real_skill_compare_20261012 حفظ شده و در این نتایج وارد نشده‌اند. preflightهای ابزار و یک timeout نیز جدا هستند. این اجرا با seed تازه و قرارداد تازه، قبل از دیدن خروجی آن، قفل شده است. هر دو اسکیل اصلی بدون تغییر مانده‌اند.

پیش از trialهای نهایی، GapCode Astra با محدودیت مصرف رد شد؛ Codex Astra همان مدل در probe موفق شد و provider آخر برنامه به Codex تغییر یافت. آمارهای قدیمی حافظه در نتیجهٔ جدید استفاده نشده‌اند.

برای بررسی نحوهٔ اجرای CLI، مستندات رسمی [حالت غیرتعاملی](https://learn.chatgpt.com/docs/non-interactive-mode) و [پروفایل مجوز](https://learn.chatgpt.com/docs/permissions) خوانده شد. رفتار واقعی محیط با preflight اندازه‌گیری شد؛ مستندات را به‌جای شاهد اجرای ابزار استفاده نکردیم.

## تمام trialها

| شناسه | بازو | تکرار | صحیح پذیرفته | audit کاندیدا | false accept | calls | توکن | ثانیه |
|---|---|---:|---|---|---|---:|---:|---:|
| C1 | flux_matched | 2 | True | True | False | 1 | 10,916 | 37.85 |
| C3 | normal | 2 | False | False | False | 1 | نامعلوم | 90.43 |
| C3 | super | 2 | False | False | False | 3 | نامعلوم | 271.38 |
| C4 | normal | 1 | False | False | False | 1 | نامعلوم | 90.56 |
| E3 | normal | 1 | True | True | False | 1 | 10,423 | 25.45 |
| E5 | normal | 1 | True | True | False | 1 | 10,389 | 27.65 |
| E5 | super | 1 | True | True | False | 1 | 19,024 | 37.80 |
| I1 | normal | 2 | True | True | False | 1 | 10,040 | 17.50 |
| I1 | super | 2 | True | True | False | 1 | 18,683 | 23.75 |
| I2 | super | 2 | True | True | False | 1 | 18,867 | 31.61 |
| I4 | normal | 2 | True | True | False | 1 | 10,547 | 35.31 |
| S1 | flux_native | 2 | True | True | False | 1 | 10,932 | 58.66 |
| S1 | normal | 1 | True | True | False | 1 | 10,272 | 31.37 |
| S1 | normal | 2 | True | True | False | 1 | 10,272 | 25.90 |
| S2 | flux_native | 2 | True | True | False | 1 | 11,185 | 84.02 |
| S3 | normal | 1 | True | True | False | 1 | 10,771 | 47.24 |
| S4 | flux_matched | 1 | True | True | False | 1 | 11,242 | 37.44 |
| S4 | flux_native | 2 | True | True | False | 1 | 10,949 | 15.21 |
| S4 | normal | 1 | True | True | False | 1 | 10,717 | 34.36 |
| S4 | super | 1 | True | True | False | 1 | 19,349 | 41.79 |

## شکست‌ها و تلاش‌های اضافی

```json
[
  {
    "label": "C3__normal__r1",
    "failure": "",
    "online_checks": [
      {
        "pass": false,
        "reason": "Provider incomplete or tool event"
      }
    ],
    "audit": {
      "pass": false,
      "executed": 1,
      "failures": [
        {
          "reason": "answer differs from exact reference"
        }
      ]
    },
    "actions": []
  },
  {
    "label": "C3__super__r1",
    "failure": "Provider incomplete or tool event",
    "online_checks": [
      {
        "pass": false,
        "reason": "Provider incomplete or tool event"
      },
      {
        "pass": false,
        "reason": "Provider incomplete or tool event"
      },
      {
        "pass": false,
        "reason": "Provider incomplete or tool event"
      }
    ],
    "audit": {
      "pass": false,
      "executed": 1,
      "failures": [
        {
          "reason": "answer differs from exact reference"
        }
      ]
    },
    "actions": []
  },
  {
    "label": "C4__normal__r0",
    "failure": "",
    "online_checks": [
      {
        "pass": false,
        "reason": "Provider incomplete or tool event"
      }
    ],
    "audit": {
      "pass": false,
      "executed": 1,
      "failures": [
        {
          "reason": "answer differs from exact reference"
        }
      ]
    },
    "actions": []
  }
]
```

## بازتولید و شواهد

`plan.json` هش کد، checkpoint، دو اسکیل، تسک‌ها، schedule و دستورها را نگه می‌دارد. `results.json` همهٔ trialها و هش رسیدهای واقعی را دارد؛ `harness-audit.json` نتیجهٔ کنترل سالم/باگ‌دار و صحت فایل‌هاست. `environment.json` نسخه و هش CLIها و runtime را ثبت می‌کند. `gate_receipts/` و ledger داخل workspaceهای SUPER شواهد گیت را حفظ می‌کنند.

برای ادامهٔ **همان اجرای ثابت**: `run.ps1 -Mode live`. برای بازتحلیل بدون فراخوانی: `run.ps1 -Mode analyze`. برای تست harness: `run.ps1 -Mode audit`. رسید موجود تنها با provider/model/effort/prompt یکسان قابل resume است؛ برای نمونهٔ تازه باید پوشهٔ جدید و freeze مستقل بسازید. اجرای مجدد prepare در پوشهٔ قفل‌شده رد می‌شود.

هش طرح: `296a44d48aa20468ceeddb480e7d41bad58715b1bc1f2792671adb1135829f46`.
