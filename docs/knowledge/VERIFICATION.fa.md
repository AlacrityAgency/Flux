# گزارش تحویل HEAD، RAG و اصلاح رابط Flux

> گزارش تاریخی نسخهٔ ۰٫۴؛ نتیجهٔ نصب، پیاده‌سازی و بررسی ۰٫۵ در [گزارش جاری](../algorithms/05-implementation-v0.5.fa.md) آمده است. اعداد و hashهای زیر شواهد همان تحویل قبلی‌اند.

تاریخ: ۱ اکتبر ۲۰۲۶. این گزارش نتیجهٔ همین نوبت است؛ گزارش‌های benchmark/اتصال قبلی فقط به‌عنوان منبع تاریخی استفاده شدند.

## سند و گفتگوها

وایت‌پیپر فارسی ۲۰ صفحه، نسخهٔ ۱٫۰، ۱۳ سپتامبر ۲۰۲۶ کامل استخراج و خوانده شد. متن قابل خواندن در `tmp/pdfs/whitepaper-readable.md` با اصلاح ترتیب RTL استخراج شد؛ PDF اصل تغییر نکرد. جلد بصری بررسی شد. منابع داخلی README، قراردادها، موتور قدیمی، runtime فعلی، storage و گزارش JEV بررسی شدند. سه گفتگوی «تدوین white paper دقیق Flux»، «طراحی الگوریتم RAG بهینه» و «اتصال کامل سیستم به Claude و ChatGPT» به‌صورت snapshot منتخب خوانده شدند؛ export کامل تمام گفتگوهای حساب انجام نشد.

## RAG واقعی NotebookLM

دفتر اختصاصی: [Flux HEAD | Whitepaper, Runtime and JEV | 2026-10-01](https://notebooklm.google.com/notebook/cbd54447-058f-445c-a1e3-850f15cc5eb9).

PDF و bundleهای allowlist سورس/گزارش/گفتگو وارد شدند. فایل‌های credential، `.env`، دیتابیس‌های کاربر، backupها و logهای شخصی وارد نشدند. MDهای الگوریتم و تحویل با برچسب طراحی به دفتر افزوده می‌شوند؛ شناسه و وضعیت آخر همهٔ sourceها در `notebooklm-manifest.json` ثبت می‌شود. public sharing فعال نشده است.

پرسش کنترل از PDF، **۶ ارجاع ساخت‌یافته** به متن منبع برگرداند (`notebooklm-grounding-check.json`). memory note نهایی، **۱۶ ارجاع ساخت‌یافته به چهار source** برگرداند (`notebooklm-generated-memory.json`) و Note `dd52cd81-cfe1-40ed-9e53-4fefd49172bb` با عنوان `Flux Project Memory` در دفتر ذخیره شد. خروجی اولیه/کوتاه فارسی نیز محفوظند، اما citationهای عددی فارسی‌شان در آرایهٔ native references قرار نگرفت؛ با پرسش انگلیسی provenance ساخت‌یافته تأیید شد.

`head-memory.fa.md` جمع‌بندی فارسی بازبینی‌شده است؛ ادعای ۱۰۰٪ پاسخ اولیه حذف، چارت داخلی از چارت مشتری جدا، واژگانی‌بودن JEV و تفاوت آزمون قدیم/جدید تصحیح شد. گزارش تغییرات نمونه و شواهد داخلی به معنی تأیید مستقل تمام خروجی‌های مدل نیست.

## RAG محلی برای ادامهٔ کار

Skill مستقل `project-evidence-rag-v2` با پروژهٔ `alacrity-flux`، task سه‌معیاره و هفت رکورد حافظه اجرا شد؛ تماس مدل آن **صفر** است. سقف ۳۰۰۰ توکن برای worker evidence با `o200k_base`، framing/output/history جداست. نتیجه در `head-evidence-pack.json`؛ عدد آخر در همان فایل مرجع است، نه اندازهٔ اولیهٔ pack.

corpus محلی از snapshot allowlist در `retrieval-corpus` ساخته شد. query/task، خروجی‌های مدل، packهای تولیدشده، source bundleهای تکراری و gold آزمایش وارد index آن نشدند تا متن خود سؤال شاهد پاسخ محسوب نشود. `retrieval-corpus-manifest.json` hash هر فایل و ریشهٔ اصلی را برای provenance نگه می‌دارد. assessmentهای سه معیار candidate هستند و semantic sufficiency به‌درستی unverified است؛ تابع تست در pack، اجرای آن نیست. این pack ابزار پژوهش HEAD است و به Workspace/LocalRuntime تزریق نشده است.

## الگوریتم‌ها

چهار مشخصات فارسی با قرارداد داده، pseudocode، ماشین حالت/رزرو/تصمیم/lifecycle، failure handling، مثال و برنامهٔ آزمون نوشته شدند؛ `00-head-brief.fa.md` نقشهٔ خواندن و provenance است. یک بازبینی مستقل، ناسازگاری enum/نوع revision، مسیر تسویهٔ دوباره، بررسی ناقص pack تازه، gate quarantine و نگاشت revision منبع را کشف کرد و در MDها اصلاح شدند. بلوک‌های Python از نظر syntax و JSON مثال‌ها و پیوندهای محلی بررسی می‌شوند؛ این کار اجرای runtime pseudocode یا benchmark الگوریتم هدف نیست.

در بررسی کوچک synthetic بدون مدل و DB، نقص revision آزمایش JEV بازتولید شد: rev1 active می‌تواند پس از rev2 obsolete با همان ID دوباره eligible شود. مشخصات lifecycle مقصد روش canonical revision/tombstone را دارد؛ کد آزمایش در این نوبت تغییر نکرد.

## باگ «پروژه‌ها و حافظه»

علت اولیه `href=/legacy` در `local.html` بود. اکنون دکمه پنل مدیریت همان رابط v0.4 را باز می‌کند؛ پروژه و یادداشت از APIهای موجود مدیریت می‌شوند و legacy پیوند مستقل دارد. انتخاب پروژه از NotebookLM به گفتگوی تازهٔ Codex با پوشهٔ همان پروژه می‌رود. بودجه و تسک قدیمی با edit/archive پروژه حفظ می‌شوند. حافظه همچنان global است و UI آن را بیان می‌کند؛ migration tenant/project/ACL انجام نشده است.

بررسی‌ها:

- `python -m pytest -q`: **۷۳ passed**؛ تماس مدل در تست‌های معمول صفر.
- syntax هر دو فایل `local.js` و `project-memory.js` گذشت.
- smoke مرورگر با fixture مستقل در عرض‌های ۳۷۵،۷۶۸،۱۰۲۴،۱۴۴۰، بدون خطای JavaScript؛ CRUD پروژه/حافظه، حفظ پیش‌نویس، invalid path، متن ناامن، archive و قفل هنگام اجرا بررسی شدند.
- ۲۲ تست هدفمند زیرکار در مجموعهٔ ۷۳تایی نیز پوشش دارند؛ این شمارها با هم جمع نمی‌شوند.
- EXE با PyInstaller 6.22.2 ساخته شد. هش build: `ba29e0309e139128e7ec93e98651abfbd9565f6d929166342b3be2ac48c9cee5`.
- `tools/project_memory_packaged_smoke.py` روی EXE با DB موقت اجرا شد: محتوای سه فایل UI با سورس byte-for-byte برابر، صفحهٔ فعلی و legacy، ایجاد/ویرایش پروژه و ایجاد/خواندن/حذف یادداشت موفق؛ مدل و دیتابیس کاربر استفاده نشدند. نتیجه در `project-memory-packaged-check.json`.
- installer اجرا شد؛ `C:\Users\xio\AppData\Local\Programs\Flux\Flux.exe` با build byte-for-byte برابر است. نسخهٔ قبلی executable توسط installer backup شد. فرایند Flux کاربر هنگام نصب باز نبود و هیچ نشست کاربر متوقف نشد.

source PDF/MDها و یادداشت حافظه باقی‌اند. مدل‌های جدید، مسیریابی خودکار JEV، حافظهٔ سازمانی چندمشتری، policy gate ابزار و دفتر بودجهٔ ancestor هنوز طراحی آینده‌اند؛ رفع باگ رابط آن‌ها را پیاده‌سازی‌شده نمی‌کند.
