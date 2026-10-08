# Flux Memory v5 — اجرای مستقل

این نسخه در `experiments` است و به runtime یا دیتابیس Flux وصل نشده است. سه بخش حافظه، بودجهٔ توکن و تصمیم‌گیری با قرارداد typed مشترک و یک Controller هماهنگ می‌شوند.

## فایل‌های اجرایی

| فایل | مسئولیت |
|---|---|
| `contracts.py` | Source، Need، Request، Policy، Pack و رسید بررسی |
| `memory_v5.py` | snapshot canonical، AST/JSON/text، ایندکس sparse و گراف |
| `engine_v5.py` | router سه‌حالته، alias عمومی، ماتریس ارزش، بسته و پذیرش prompt |
| `verifier_v5.py` | اتصال دقیق ادعا به منبع و checker محدود ریاضی/کد |
| `controller_v5.py` | ledger SQLite، idempotency، یک repair و سقف دو تلاش فیزیکی |
| `provider_v5.py` | adapter اختیاری Codex CLI با حساب موجود |
| `code_worker.py` | اجرای محدود تابع `solve` در subprocess با timeout |
| `cli.py` | آماده‌سازی پیش‌فرض و اجرای واقعی فقط با `--live` |
| `test_v5.py` | ۵۰ آزمون regression، مرزهای قرارداد، ledger و checker |
| `benchmark_v5.py` | dev، freeze و holdout جفت‌شده با v4 |
| `regression_probe.py` | بازتولید ۹ ایراد شناخته‌شده و ۳ شاهد قرارداد واقعی Flux |

## اجرای بدون مدل

از پوشهٔ همین نسخه:

```powershell
python -X utf8 -m pytest test_v5.py -q
python -X utf8 cli.py demo-job.json --output demo-result.json
```

فرمت ورودی در `demo-job.json` مشخص است. sourceها باید همراه schema، نقش معتبر، namespace، project، epoch و revision ارائه شوند. متن فاقد parser معتبر شاهد typed نمی‌شود. Aliasها عمومی‌اند و در hash snapshot ثبت می‌شوند.

پاسخ grounded باید `claims`، `need_id`، `entity_ref`، `field_ref`، `namespace`، `value`، `value_type`، `proof_kind` و `evidence_refs` داشته باشد. مرجع واحدها داخل pack آمده است. برای ریاضی `answer` و expression عمومی؛ برای کد `code` و تست‌های عمومی استفاده می‌شوند. متن آزاد semantic-unverified می‌ماند.

## مسیر مدل واقعی، اختیاری

```powershell
python -X utf8 cli.py demo-job.json --live --output live-result.json
```

این دستور واقعاً مدل را اجرا می‌کند و از سهمیهٔ حساب Codex استفاده می‌کند. خود ساخت، تست و benchmark این نسخه هیچ مدل واقعی‌ای را فراخوانی نکردند. اتصال v5 به CLI با اجرای زندهٔ تازه تأیید نشده است؛ receipt کامل، نبود tool event و JSON معتبر شرط پذیرش‌اند. هزینهٔ دلاری در نبود رسید تعرفه `unknown` است.

شناسهٔ درخواست در ledger پایدار است: اجرای مجدد همان درخواست نتیجهٔ ذخیره‌شده را برمی‌گرداند؛ استفادهٔ همان ID برای سؤال، snapshot یا policy متفاوت رد می‌شود. برای درخواست تازه ID تازه بدهید. تلاش با اثر خارجی نامعلوم خودکار تکرار نمی‌شود.

## بازتولید benchmark

نتیجهٔ نهایی فقط در `runs/final/holdout-results.json` است. `runs/final/frozen-manifest.json` کد، داده، وابستگی‌ها، tokenizer و baselineها را hash می‌کند. `holdout-run.lock` بازنویسی یا اجرای مجدد holdout را رد می‌کند. نتایج r1 مربوط به کد قبلی‌اند؛ نسخهٔ آن کد در `frozen_runs/r1` حفظ شده است.

Benchmark وابسته به پوشه‌های آزمایش v3/v4 و snapshot قدیمی در repository است؛ ZIP runtime برای اجرای demo و unit tests مستقل است. اجرای تازهٔ benchmark باید با run directory و دادهٔ تازه و برچسب تازه انجام شود؛ فایل lock را برای بازنویسی نتایج حذف نکنید.

## مرز پیاده‌سازی

Embedding، update افزایشی snapshot، آموزش وزن‌ها، یادداشت معنایی LLM بین یال‌ها و ادغام با حافظهٔ production در این نسخه اجرا نشده‌اند. Snapshot کامل rebuild می‌شود؛ alias، نیاز و dependency بسته را مخصوص درخواست می‌کنند. گراف یک reference حل‌شده و containment/adjacency دارد؛ `via_field` یک hop ثبت‌شده را دنبال می‌کند. برچسب ۱۰۰هزار توکن یا ۱میلیون توکن هدف پر کردن نیست.

Worker کد محدودیت AST، import، builtin و زمان دارد؛ sandbox امنیتی سخت‌شدهٔ سیستم‌عامل یا محدودیت قطعی RAM ندارد. `verified` کد فقط به تست‌های عمومی اجراشده مربوط است. پذیرش انسانی و یادداشت proposed با موفقیت verifier یکی نیستند.
