"""Render measured result section into the detailed algorithm MD after audit."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'results.json').read_text(encoding='utf-8'))
a=json.loads((HERE/'audit-results.json').read_text(encoding='utf-8'))
assert r['status']=='complete' and a['passed']
lines=['## نتیجهٔ آزمون تازه و ممیزی‌شده','',
    f"{a['trials_reaudited']} اجرای نهایی دوباره بررسی شد و {a['hashes_verified']} hash رسید تطبیق دارد. نتیجهٔ اصلی روی ۱۲ تسک تازه است؛ نتیجهٔ فرعی روی شش تسک ازپیش‌تعیین‌شده گزارش می‌شود.",'',
    '| مسیر | درست | توکن ورودی | کش ورودی | خروجی شامل استدلال | مجموع توکن معلوم | دلار معادل معلوم | ارتقا | usage نامعلوم | میانهٔ زمان تسک |',
    '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for arm in ['senior_v1','senior_v2','goat_v1','goat_v2','senior_compact_default']:
    s=r['summary'][arm];u=s['usage_known_sum']
    lines.append(f"|{arm}|{s['correct']}/{s['tasks']}|{u['input_tokens']:,}|{u['cached_input_tokens']:,}|{u['output_tokens']:,}|{s['provider_total_tokens_known']:,}|${s['cost_known_lower_bound']:.6f}|{s['retries']}|{s['unknown_usage_calls']}|{s['trial_p50_s']:.2f}s|")
lines += ['','اگر usage نامعلوم وجود داشته باشد، دلار/توکن معلوم فقط حد پایین است. costs معادل نرخ ثابت API و کش مشاهده‌شده‌اند؛ صورت‌حساب واقعی حساب ChatGPT نیستند.','',
    '| مقایسهٔ اصلی v1 → v2 | کیفیت برابر روی همهٔ ۱۲ | کاهش توکن | کاهش هزینه | کاهش خروجی | نسبت سرعت میانه |',
    '|---|---|---:|---:|---:|---:|']
def fmt(value):return 'نامعلوم/مقایسه نامعتبر' if value is None else f'{value:.2f}'
for name,c in r['comparisons'].items():
    lines.append(f"|{name}|{c['quality_equal']}|{fmt(c['token_reduction_percent'])}٪|{fmt(c['cost_reduction_percent'])}٪|{fmt(c['output_reduction_percent'])}٪|{fmt(c['p50_speedup'])}|")
lines += ['','اعداد منفی در کاهش هزینه یا خروجی، افزایش را نشان می‌دهند. صفر false_accept شرط لازم برای ادعای حفظ کیفیت بوده است.','',
    '### آزمون تفکیک قالب و مسیر اجرا','',
    '| مقایسه روی H01..H06 | درست | مجموع توکن معلوم | خروجی | دلار معادل معلوم | ارتقا |',
    '|---|---:|---:|---:|---:|---:|']
sec=r['secondary_ablation']
for arm,s in sec['summaries'].items():lines.append(f"|{arm}|{s['correct']}/{s['tasks']}|{s['provider_total_tokens_known']:,}|{s['usage_known_sum']['output_tokens']:,}|${s['cost_known_lower_bound']:.6f}|{s['retries']}|")
for name,label in [('compact_effect','اثر قالب با مسیر اجرای پیش‌فرض'),('transport_effect','اثر مسیر اجرا با قالب پارامتری')]:
    c=sec[name];lines += ['',f"{label}: کاهش توکن {fmt(c['token_reduction_percent'])}٪، کاهش خروجی {fmt(c['output_reduction_percent'])}٪، کاهش هزینه {fmt(c['cost_reduction_percent'])}٪. این مقایسه شش‌تسکی و با یک نمونه است؛ تفاوت پاسخ stochastic، ارتقا و کش هم اثر می‌گذارند."]
lines += ['','### زمان و مصرف محلی Laya','',
    '| مسیر | تصمیم‌های واقعی Laya | مجموع زمان تصمیم‌ها | ورودی encoder | موفقیت برنامه/تلاش برنامه | توزیع فراخوانی مدل |',
    '|---|---:|---:|---:|---:|---|']
for arm,s in r['summary'].items():lines.append(f"|{arm}|{s['laya_calls']}|{s['laya_seconds']:.3f}s|{s['laya_encoder_input_tokens']:,}|{s['program_passes']}/{s['program_attempts']}|{s['models']}|")
runtime=json.loads((HERE/'runtime.json').read_text(encoding='utf-8'))
locals_=[json.loads(p.read_text(encoding='utf-8')) for p in (HERE/'laya_receipts').glob('*.json')]
peak=max(x['peak_allocated_bytes'] for x in locals_)/1024**3
lines += ['',f"بارگذاری Laya: {runtime['laya_load_s']:.2f}s؛ بیشترین حافظهٔ اختصاص‌یافتهٔ CUDA: {peak:.3f} GiB. ورودی/پرسش Laya حذف نشده و خروجی تولیدی آن صفر توکن است. مصرف محلی Laya در توکن ارائه‌دهنده جمع نشده؛ هزینهٔ سخت‌افزار/برق قیمت‌گذاری نشده است.",'',
    '### حساسیت به کش','', '| مسیر | دلار فرضی بدون تخفیف کش |','|---|---:|']
for arm,s in r['summary'].items():lines.append(f"|{arm}|{fmt(s['uncached_equivalent_usd']) if s['uncached_equivalent_usd'] is None else format(s['uncached_equivalent_usd'],'.6f')}|")
lines += ['','این جدول محاسبهٔ فرضی با همان مصرف است، نه اجرای دوم یا صورتحساب بدون کش.','',
    '### شکست‌های تلاش اولیه و ارتقا','']
descriptions={
 'H02__goat_v2':'پاسخ فاکتور غلط بود و checker تولیدی آن را تأیید کرد؛ ارزیاب مستقل آن را رد کرد و Sol پاسخ درست داد.',
 'H05__senior_compact_default':'کد نام ممنوع __import__ داشت؛ ناسازگاری با قرارداد worker.',
 'H05__senior_v1':'کد از builtin در دسترس‌نبودۀ bin استفاده کرد؛ ناسازگاری با worker.',
 'H06__senior_compact_default':'کد نام خصوصی ممنوع __import_placeholder داشت؛ ناسازگاری با worker.',
 'H08__goat_v2':'بازاجرای تشخیصی نشان داد solve پاسخ درست داده ولی check=False است؛ رد اشتباهِ checker باعث ارتقای اضافی شد.',
 'H08__senior_v1':'بازاجرای تشخیصی نشان داد tax=1639 به‌جای 3277 محاسبه شده و checker نیز پاسخ را رد کرده است.',
 'H09__goat_v1':'خروجی کد با قرارداد «فقط تعریف تابع» worker سازگار نبود.',
 'H11__senior_v1':'خروجی JSON دادهٔ اضافی داشت و parser آن را رد کرد.'}
for fail in a['failures']:lines.append(f"- {fail['trial']}، تلاش {fail['attempt']}: {descriptions.get(fail['trial'],fail['reason'])}")
if not a['failures']:lines.append('شکستی در تلاش‌ها ثبت نشد.')
lines += ['','خطاهای خام در audit-results.json نگهداری شده‌اند. سه بازاجرای تشخیصی در failure-diagnostics.json، با hash رسید اصلی، ثبت شده‌اند. نمایش fraction در encoding داخلی علت رد دو تلاش H08 نبود؛ علت check=False بود. تشخیص پس از آزمون هیچ سیاست یا prompt قفل‌شده‌ای را تغییر نداده است.']
lines += ['',f"سیاست هزینه در {len(a['cost_router_overrides'])} درخواست، انتخاب خام مدل Laya را تغییر داده است. این تغییرها در audit-results.json ثبت شده‌اند.",'',
    f"اجرای تازه شامل {sum(s['calls'] for s in r['summary'].values())} فراخوانی حل‌کننده و {sum(s['laya_calls'] for s in r['summary'].values())} تصمیم واقعی Laya بود. هزینهٔ معادلِ همین اجرای تازه، با همهٔ مسیرها و ارتقاها، ${sum(s['cost_known_lower_bound'] for s in r['summary'].values()):.6f} است. شش probe مقدماتیِ کپی‌شده، ${a['development_probe_api_equivalent_usd']:.6f} هزینهٔ تاریخی جدا دارند؛ آنها در تکرار دوباره فراخوانی نشده‌اند. مجموع با احتساب آن دادهٔ توسعه ${a['total_experiment_api_equivalent_known_lower_bound']:.6f} است. هزینهٔ اجرای ناقص قبلی در این عدد جمع نشده است.",'',
    '### تفسیر','',
    'ترکیب کامل در هر دو مسیر مصرف را کاهش داد و تمام پاسخ‌های نهایی درست بودند. Senior v2 هر ۱۲ مسئله را در تلاش اول با Luna حل کرد؛ در Senior v1 سه ارتقا به Sol رخ داد. کاهش بزرگ هزینهٔ Senior علاوه بر تغییر کانتکست و قالب، به حذف همین ارتقاها وابسته است و نباید تمام آن را به کوتاه‌شدن prompt نسبت داد.',
    '',
    'در GOAT v2 سیاست هزینه برای هر ۱۲ درخواست مدل اولیهٔ Luna را انتخاب کرد و در ۱۰ مورد انتخاب خام Laya را تغییر داد. دو ارتقا به Sol باقی ماند؛ GOAT v1 چهار فراخوانی Astra داشت. روی این مجموعه، تنوع مدل اولیهٔ GOAT v2 عملاً به انتخاب Luna فروکاسته است؛ انعطاف مسیریاب در خانواده‌های دیگر هنوز اثبات نشده است.',
    '',
    'در آزمون شش‌تسکیِ تفکیکی، قالب پارامتری با مسیر اجرای پیش‌فرض، خروجی را ۱۳٫۵٪ کم کرد ولی توکن کل را ۱۳٫۲٪ و هزینه را ۵۰٫۸٪ بالا برد؛ دو ناسازگاری worker به ارتقا انجامید. بنابراین مزیت مستقل قالب فشرده ثابت نشده است. پاسخ‌های تصادفی و کش کنترل‌نشده، تفکیک علی را محدود می‌کنند.',
    '',
    'هزینهٔ معادل هر تسک در Senior از $0.007381 به $0.000528 و در GOAT از $0.043647 به $0.004856 رسید. این تقریباً ۱۴٫۰ برابر و ۹٫۰ برابر کاهش در مقایسهٔ v1→v2 است. ادعای اولیهٔ «۱۵ برابر ارزان‌تر از Junior» در این آزمون سنجیده نشده، چون مسیر Junior در مجموعهٔ تازه اجرا نشده است.',
    '',
    'نرخ موفقیت یا بهینه‌بودن عمومی از ۱۲ مسئله نتیجه نمی‌شود. این آزمایش RAG، آموزش وزن Laya یا عملکرد production را تأیید نمی‌کند. بهینه‌سازی بعدی باید ناسازگاری قرارداد worker و رد اشتباه checker را روی دادهٔ توسعهٔ جدا هدف بگیرد؛ گیت ارزیاب مستقل باید حفظ شود.']

doc=HERE/'ALGORITHM.fa.md';text=doc.read_text(encoding='utf-8')
start='<!-- RESULTS_START -->';end='<!-- RESULTS_END -->'
before,tail=text.split(start,1);_,after=tail.split(end,1)
doc.write_text(before+start+'\n'+'\n'.join(lines)+'\n'+end+after,encoding='utf-8')
print('Detailed algorithm MD updated with audited results:',doc)
