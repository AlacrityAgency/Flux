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
for fail in a['failures']:lines.append(f"- {fail['trial']}، تلاش {fail['attempt']}: {fail['reason']}")
if not a['failures']:lines.append('شکستی در تلاش‌ها ثبت نشد.')
lines += ['',f"سیاست هزینه در {len(a['cost_router_overrides'])} درخواست، انتخاب خام مدل Laya را تغییر داده است. این تغییرها در audit-results.json ثبت شده‌اند.",'',
    f"شش probe مقدماتی جدا از holdout، مجموعاً ${a['development_probe_api_equivalent_usd']:.6f} معادل هزینه داشتند. کل هزینهٔ معادلِ معلوم آزمایش با احتساب تمام مسیرها، ارتقاها و probeها: ${a['total_experiment_api_equivalent_known_lower_bound']:.6f}. این مجموع، هزینهٔ اجرای benchmark است و با هزینهٔ یک سیاست در جدول اصلی تفاوت دارد.",'',
    '### تفسیر','',
    'مزیت اقتصادی باید از جمع واقعی مصرف و تعرفهٔ مدل خوانده شود؛ کاهش prompt یا خروجی به‌تنهایی کافی نیست. مقدار کاهش هزینهٔ GOAT، ظرفیت اصلاح انتخاب مدل را می‌سنجد؛ نتیجهٔ Senior نشان می‌دهد ترکیب کوتاه‌کردن برنامه و تغییر کانتکست اجرا چه اثری داشته است. نرخ موفقیت یا بهینه‌بودن عمومی از ۱۲ مسئله نتیجه نمی‌شود. این آزمایش RAG، آموزش وزن Laya یا عملکرد production را تأیید نمی‌کند.']
doc=HERE/'ALGORITHM.fa.md';text=doc.read_text(encoding='utf-8')
start='<!-- RESULTS_START -->';end='<!-- RESULTS_END -->'
before,tail=text.split(start,1);_,after=tail.split(end,1)
doc.write_text(before+start+'\n'+'\n'.join(lines)+'\n'+end+after,encoding='utf-8')
print('Detailed algorithm MD updated with audited results:',doc)
