"""Audit and summarize saved results, without rerunning retrieval or calling a model."""
import hashlib,json,statistics
from pathlib import Path
HERE=Path(__file__).resolve().parent
e=json.loads((HERE/"evaluation.json").read_text(encoding="utf-8"))
frozen=json.loads((HERE/"frozen_candidate.json").read_text(encoding="utf-8"))
assert all(hashlib.sha256((HERE/k).read_bytes()).hexdigest()==v for k,v in frozen.items())
skill=json.loads((HERE/"skill_manifest.json").read_text(encoding="utf-8"))
assert all(hashlib.sha256((Path(skill["directory"])/k).read_bytes()).hexdigest()==v for k,v in skill["files"].items())
labels={"v1":"v1 قبلی","prior_v2":"v2 قبلی","rewrite":"v2 بازنویسی‌شده"}
flat=[r for split in e.values() for budget in split.values() for result in budget.values() for r in result["rows"]]
assert len(flat)==333
assert all(r["tokens"]<=r["budget"] and r["foreign"]==r["obsolete"]==0 for r in flat)
aggregate={}
for budget in (1500,3000,6000):
    aggregate[budget]={}
    for label in labels:
        rows=[r for r in flat if r["budget"]==budget and r["algorithm"]==label]
        aggregate[budget][label]={"tasks":len(rows),"hits":sum(r["hits"] for r in rows),
                "needs":sum(r["total"] for r in rows),"complete_tasks":sum(r["complete"] for r in rows),
                "mean_tokens":statistics.mean(r["tokens"] for r in rows),
                "median_select_ms":statistics.median(r["select_ms"] for r in rows)}
live3=json.loads((HERE/"live_results.json").read_text(encoding="utf-8"))
live6=json.loads((HERE/"live_results_6000.json").read_text(encoding="utf-8"))
assert len(live3)==6 and len(live6)==3 and all(r["success"] for r in live3+live6)
def totals(rows):
    return {k:sum(r["usage"].get(k,0) for r in rows) for k in ("prompt_tokens","completion_tokens","total_tokens","cost")}
newlive=totals([r for r in live3 if r["algorithm"]=="rewrite"])
oldlive=totals(live6)
live_savings={k:100*(1-newlive[k]/oldlive[k]) for k in ("prompt_tokens","total_tokens","cost")}
summary={"aggregate":aggregate,"fresh_additional_3000":{k:v["summary"] for k,v in e["additional"]["3000"].items()},
         "live_new_3000":newlive,"live_prior_v2_6000":oldlive,"live_savings_pct":live_savings,
         "all_live_requests":9,"all_live_usage":totals(live3+live6),"behavior_tests_passed":16,
         "packaged_cli_tests_passed":2,"invariant_runs":len(flat),"native_jev_tested":False,
         "frozen_candidate_verified":True,"skill_path":skill["directory"]}
(HERE/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")

text="""# بازنویسی JEVS v2 — گزارش آزمون ۱ اکتبر ۲۰۲۶

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
"""
for label,value in e["additional"]["3000"].items():
    s=value["summary"]
    text+=f"| {labels[label]} | {s['hits']}/{s['needs']} | {s['micro_recall']:.1%} | {s['mean_context_tokens']:.0f} | {s['complete_tasks']}/{s['tasks']} |\n"
text+="""
بازنویسی نسبت به v2 قبلی ۱۰ شاهد بیشتر پیدا کرد: پوشش از ۴۴٫۲٪ به ۶۷٫۴٪ رسید؛ ۲۳٫۳ واحد درصد افزایش و ۵۲٫۶٪ افزایش نسبی. تعداد سناریوهای دارای تمام شواهد در هر دو نسخه ۴ از ۱۲ است؛ بهبود پوشش را نباید به افزایش ثابت‌شدهٔ کیفیت پاسخ کامل تعبیر کرد.

در همین مجموعه، نسخهٔ جدید با سقف ۳۰۰۰ در برابر v2 قبلی با سقف ۶۰۰۰، حدود ۵۰٫۶٪ توکن متن کارگر کمتر دارد و ۲۹ شاهد در برابر ۲۳ شاهد پیدا می‌کند. این بهبود مربوط به متن شواهد است؛ بودجهٔ کل prompt و خروجی مدل جداست.

## کل ۳۷ سناریو

این جدول سناریوهای توسعه را نیز شامل می‌شود؛ شاهد اصلی تعمیم، جدول ۱۲ سناریوی اضافی است.

| سقف | نسخه | شاهد یافته‌شده | پوشش | میانگین توکن متن کارگر | سناریو با تمام شواهد |
|---:|:---|---:|---:|---:|---:|
"""
for budget,ss in aggregate.items():
    for label,s in ss.items():
        text+=f"| {budget} | {labels[label]} | {s['hits']}/{s['needs']} | {s['hits']/s['needs']:.1%} | {s['mean_tokens']:.0f} | {s['complete_tasks']}/{s['tasks']} |\n"
text+="""
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
"""
text+=f"| v2 قبلی، سقف شواهد ۶۰۰۰ | {oldlive['prompt_tokens']:,} | {oldlive['completion_tokens']:,} | {oldlive['total_tokens']:,} |\n"
text+=f"| بازنویسی، سقف شواهد ۳۰۰۰ | {newlive['prompt_tokens']:,} | {newlive['completion_tokens']:,} | {newlive['total_tokens']:,} |\n"
text+=f"\nدر همین سه نمونه، ورودی {live_savings['prompt_tokens']:.1f}٪ و مجموع ورودی/خروجی {live_savings['total_tokens']:.1f}٪ کمتر شد. فیلد هزینهٔ provider از {oldlive['cost']:.7f} به {newlive['cost']:.7f} دلار رسید؛ {live_savings['cost']:.1f}٪ کمتر. این هزینه گزارش provider است، نه بررسی مستقل صورت‌حساب. reasoning زیرمجموعهٔ خروجی است و دوباره جمع نشده است.\n"
text+="""
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
"""
(HERE/"REPORT.fa.md").write_text(text,encoding="utf-8")
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.is_file() and p.name!="delivery_manifest.json"}
(HERE/"delivery_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print(json.dumps({"additional":summary["fresh_additional_3000"],"live_savings_pct":live_savings,
                  "all_live_usage":summary["all_live_usage"],"invariant_runs":len(flat)},ensure_ascii=False,indent=2))
