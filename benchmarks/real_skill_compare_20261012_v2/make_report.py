"""Measured report and offline interactive viewer. Never invent missing telemetry."""
import csv
import html
import json
import statistics
from pathlib import Path
import benchmark as B

LABELS={'normal':'عادی · Sol medium','super':'SUPER · Sol medium','flux_native':'Flux · مسیر اصلی','flux_matched':'Flux · Sol medium ثابت'}

def fmt(x,d=2):return 'نامعلوم' if x is None else f'{x:,.{d}f}'
def usage(trial):
    rs=[B.read(B.HERE/'receipts'/(x+'.json')) for x in trial['calls']]
    if any(not r.get('usage') or any(k not in r['usage'] for k in ['input_tokens','output_tokens']) for r in rs):return None
    return sum(r['usage']['input_tokens']+r['usage']['output_tokens'] for r in rs)
def gate_statuses(trials):
    verdicts={};raw={}
    for t in trials:
        for name in t.get('review_receipts',[]):
            r=B.read(B.HERE/'gate_receipts'/(name+'.json'));report=r.get('report') or {}
            overall=(report.get('verdict') or {}).get('overall','UNKNOWN');verdicts[overall]=verdicts.get(overall,0)+1
        for x in t['gate_records']:
            k=x['gate']+':'+str(x.get('status'));raw[k]=raw.get(k,0)+1
    return {'review_verdicts':verdicts,'raw_gate_statuses':raw}

def main():
    B.verify();r=B.read(B.HERE/'results.json');ts=r['trials'];plan=B.read(B.HERE/'plan.json')
    lines=['# بنچمارک واقعی Flux v1، SUPER و حالت عادی',
      '',f'تاریخ قرارداد: ۲۰۲۶-۱۰-۱۲، منطقهٔ کاربر Asia/Tehran. آخرین تحلیل UTC: `{r["analyzed_utc"]}`.',
      '',f'وضعیت: **{"کامل" if r["complete"] else "ناتمام"}**؛ {r["completed_trials"]} از {r["scheduled_trials"]} آزمایش. داده از فراخوانی‌های واقعی CLI، Laya محلی و تست‌های مستقل است.',
      '', '**مرز تفسیر:** این بازسازی گردش‌کار در harness است. نشست‌های مدل ابزار ندارند؛ تست و گیت واقعی بیرون نشست اجرا می‌شود. این آزمون جای بنچمارک کامل SUPER در ساخت اپ، UI، تحقیق یا محیط تعاملی عادی را نمی‌گیرد.',
      '', '## نتایج واقعی به تفکیک نوع کار']
    for track,title in [('reasoning','محاسبات: ۱۲ تسک مستقل، هرکدام دو تکرار'),('engineering','رفع باگ: ۶ تسک مستقل، یک تکرار')]:
        lines += ['',f'### {title}','','| بازو | پاسخ نهایی پذیرفته و صحیح | کاندیدای صحیح در audit | پذیرش غلط | توکن معلوم input+output | usage نامعلوم | فراخوانی | تعمیر اضافی | میانگین ثانیه | p50 / p95 |',
          '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for arm,s in r['tracks'][track].items():
            lines.append(f'| {LABELS[arm]} | {s["correct"]}/{s["trials"]} | {s["candidate_correct"]}/{s["trials"]} | {s["false_accepts"]} | {s["total_tokens_known"]:,} | {s["unknown_usage_calls"]} | {s["provider_calls"]} | {s["extra_attempts"]} | {fmt(s["latency_mean_s"])} | {fmt(s["latency_p50_s"])} / {fmt(s["latency_p95_s"])} |')
        lines += ['', '| مقایسه با عادی | کاهش توکن مشاهده‌شده | فاصلهٔ bootstrap ۹۵٪ | تفاوت دقت (واحد درصد) | کاهش میانگین زمان مشاهده‌شده | برابری کیفیت بی‌خطای مشاهده‌شده |',
          '|---|---:|---:|---:|---:|---|']
        for arm,c in r['comparisons'][track].items():
            if not c.get('complete'):lines.append(f'| {LABELS[arm]} | دادهٔ جفتی ناتمام | — | — | — | — |');continue
            interval=c['bootstrap95']['token_reduction_percent']
            ci='نامعلوم' if interval is None else ' تا '.join(fmt(x) for x in interval)
            lines.append(f'| {LABELS[arm]} | {fmt(c["token_reduction_percent"])}٪ | {ci}٪ | {fmt(c["accuracy_difference_pp"])} | {fmt(c["mean_latency_reduction_percent"])}٪ | {"بله، فقط همین نمونه" if c["maintained_perfect_observed_quality"] else "خیر"} |')
        lines += ['', 'عدد منفی در ستون کاهش یعنی مصرف/زمان بیشتر. اگر مصرف یکی از فراخوانی‌ها معلوم نباشد درصد کاهش حساب نمی‌شود. صرفه‌جویی توکن معادل صرفه‌جویی پول یا سهمیهٔ اشتراک نیست.']
    lines += ['', '## الگوریتم‌ها و کنترل عوامل',
      '', '| ویژگی | عادی | Flux native | Flux matched | SUPER در harness |',
      '|---|---|---|---|---|',
      '| مدل اولیه | Codex Sol medium | Codex Luna low | Codex Sol medium | Codex Sol medium |',
      '| ارتقا/تعمیر | یک پاسخ مستقیم | GapCode Sol high، سپس Codex Astra high | همان Sol medium، حداکثر سه بار | همان Sol medium، حداکثر سه بار |',
      '| برنامهٔ پارامتری | فقط در رفع باگ | refs + solve + check | refs + solve + check | فقط در رفع باگ؛ بدون refs اجباری |',
      '| کنترل محلی | فقط audit نهایی | AST/worker/معیار مستقل + guard | همان Flux | معیار مستقل + گیت عمومی واقعی در رفع باگ |',
      '| Laya | ندارد | FRONT و END واقعی | FRONT و END واقعی | ندارد |',
      '| بررسی هدف/قرارداد | دستور مستقیم | قیدها و facts ثابت | همان Flux | متن کامل اسکیل و framing/reasoning/debug/testing |',
      '| ابزار داخل نشست | غیرفعال | غیرفعال | غیرفعال | غیرفعال |',
      '', 'مقایسهٔ SUPER و عادی، مدل/effort/محیط مشترک دارد؛ تعداد مجاز تلاش و محتوای اسکیل متفاوت است. مقایسهٔ Flux matched با عادی، اثر متفاوت بودن مدل اولیه را حذف می‌کند، اما compact/checker/Laya/retry را جدا از یکدیگر شناسایی نمی‌کند. Flux native مقایسهٔ کل گردش‌کار است؛ اثر Luna، effort و provider هم داخل نتیجه است.',
      '', 'SUPER فقط دستور ورود نیست: متن اسکیل، framing، reasoning، debug و testing به مدل داده شده و هماهنگ‌کننده گیت و review واقعی را اجرا کرده است. با این حال debug case کامل، تحقیق وب و اجرای خودمختار ابزار توسط مدل بازسازی نشده‌اند؛ در اینجا فقط انطباق قرارداد و صحت پاسخ/تعمیر سنجیده شده است.',
      '', '## وضعیت واقعی گیت‌های SUPER و ایراد ویندوز']
    gates=gate_statuses(ts);B.write(B.HERE/'gate-summary.json',gates)
    lines+=['','```json',json.dumps(gates,ensure_ascii=False,indent=2),'```',
      '', 'در preflight سالم، گیت‌های testing.run، testing.smells و backend.behavior واقعاً PASS شدند، اما verdict بومی SUPER به علت ناسازگاری مسیر report با کلید digests در Windows، STALE بود. `ledger.intact()` قبل از سنجش هش، عضویت رشتهٔ مسیر را بررسی می‌کند: report دارای `/` ولی کلید digests دارای `\\` است. هش‌ها و fingerprint واقعاً برابر بودند. اسکیل اصلاح نشده و verdict اصلی با تمام شکاف‌ها نگه داشته شده است.',
      '', 'پذیرش harness بر اساس تست مستقل قرارداد و PASS خام سناریوی مربوط است؛ این پذیرش به معنای PASSED بودن verdict بومی SUPER یا آمادگی انتشار نیست. delivery.build و testing.api برای fixture تابع stdlib پیکربندی نشده‌اند؛ NOT-TESTED را PASS حساب نکرده‌ایم.',
      '', '## کیفیت ارزیاب و نمونه‌گیری',
      '', 'فاکتور با Decimal و Fraction مستقل کنترل شد؛ شمارش با enumeration و dynamic programming مستقل؛ زمان‌بندی با permutation و DFS مستقل. شش کنترل سالمِ رفع باگ پاس شدند و هر شش نسخهٔ باگ‌دار رد شدند. مقایسهٔ JSON نوع‌دار است: True، 1 و 1.0 قابل جایگزینی نیستند. تغییر ورودی، کلید تکراری JSON، NaN، کد دارای IO و checker ثابت نیز کنترل شده‌اند.',
      '', 'رفع باگ شامل مرز tenant/owner/admin، بازهٔ نیمه‌باز/adjacency، replay/idempotency/conflict، HALF UP، مهاجرت/duplicate/precedence و version-specific field است. ۱۸ کیس عمومی و ۱۳۶ کیس افزودهٔ پنهان وجود دارد؛ مجموع ۱۵۴ مورد در هر audit کامل این شش تسک. تعداد کیس‌ها با تعداد دامنه‌ها اشتباه گرفته نشده است.',
      '', 'Oracle و کد تست پنهان در prompt حل‌کننده یا Laya نیست. Flux و SUPER برای تعمیر فقط بازخورد محدود تست عمومی دریافت می‌کنند. audit پنهان فقط پس از پاسخ نهایی اجرا می‌شود؛ خطای پنهان به solver بازگردانده نمی‌شود. ترتیب با seed قفل‌شده و تصادفی است، تمام شکست‌ها در جدول باقی می‌مانند.',
      '', '## عدم‌قطعیت آماری',
      '', '| نوع کار / بازو | تسک مستقل که تمام تکرارهایش موفق است | Wilson ۹۵٪ برای همان معیار |',
      '|---|---:|---:|']
    for track,arms in r['tracks'].items():
        for arm,s in arms.items():
            ci=s['task_accuracy_wilson95'];txt='نامعلوم' if ci is None else ' تا '.join(fmt(100*x) for x in ci)+'٪'
            lines.append(f'| {track} / {LABELS[arm]} | {s["all_repeats_correct_tasks"]}/{s["distinct_tasks"]} | {txt} |')
    lines += ['', 'bootstrap مصرف/زمان با ۱۰٬۰۰۰ بازنمونه روی **خوشهٔ تسک** است؛ دو تکرار داخل همان تسک میانگین می‌شوند. ۲۴ پاسخ در محاسبات، ۲۴ دامنهٔ مستقل نیستند. دقت ۱۰۰٪ در نمونهٔ کوچک اثبات دقت عمومی ۱۰۰٪ نیست؛ بازهٔ صفرِ تفاوت bootstrap در حالت همه‌موفق نیز عدم‌قطعیت تعمیم را حذف نمی‌کند. p آزمون دقیق جفتی و تعداد برد/باخت در results.json ثبت شده است. این آزمون equivalence با حاشیهٔ ازپیش‌تعیین‌شده نیست.',
      '', '## مصرف، زمان و محدودیت‌ها',
      '', '| نوع کار / بازو | input | cached subset | output | reasoning subset | Laya calls / ثانیه | provider failures / timeout |',
      '|---|---:|---:|---:|---:|---:|---:|']
    for track,arms in r['tracks'].items():
        for arm,s in arms.items():
            u=s['usage_known_sum'];lines.append(f'| {track} / {LABELS[arm]} | {u["input_tokens"]:,} | {u["cached_input_tokens"]:,} | {u["output_tokens"]:,} | {u["reasoning_output_tokens"]:,} | {s["local_laya_calls"]} / {fmt(s["local_laya_s"])} | {s["provider_failures"]} / {s["timeouts"]} |')
    runtime=B.read(B.HERE/'runtime.json') if (B.HERE/'runtime.json').exists() else None
    lines += ['', 'لود سرد Laya در فرایند مشترک:', '', '```json',json.dumps(runtime,ensure_ascii=False,indent=2),'```',
      '', 'زمان هر trial شامل تماس مدل، انتظار محلی، تست و audit است. دو trial هم‌زمان اجرا شده‌اند و Laya قفل مشترک دارد؛ شبکه، کش و بار CPU/GPU کنترل نشده‌اند. بارگذاری اولیهٔ Laya جدا ثبت شده و داخل زمان گرم هر trial نیست. از این نمونه ادعای برتری سرعت سرد، مصرف برق یا سرعت production نمی‌کنیم.',
      '', 'input+output مصرف گزارش‌شدهٔ provider است؛ cached و reasoning زیرمجموعه‌اند و دوباره جمع نشده‌اند. هزینهٔ کیف پول، وزن سهمیهٔ اشتراک، توکن این چت هماهنگ‌کننده و برق محلی اندازه‌گیری نشده‌اند. usage نامعلوم صفر نشده است. هویت مدل فقط نام درخواست‌شدهٔ client است و مستقلاً در server تأیید نشده است. CLI ممکن است retry داخلی داشته باشد؛ یک invocation را یک wire request قطعی سمت سرور حساب نکرده‌ایم.',
      '', '## پروندهٔ اجرای اولیه و تغییرات روش',
      '', 'بنچمارک قدیمی والد از عدد تصادفی و oracle استفاده می‌کرد و به‌عنوان شبیه‌سازی برچسب خورد. pilot واقعی اول با ۱۱ trial متوقف شد چون ابزارها در CLI با policy رد می‌شدند؛ تمام رسیدها در ../real_skill_compare_20261012 حفظ شده و در این نتایج وارد نشده‌اند. preflightهای ابزار و یک timeout نیز جدا هستند. این اجرا با seed تازه و قرارداد تازه، قبل از دیدن خروجی آن، قفل شده است. هر دو اسکیل اصلی بدون تغییر مانده‌اند.',
      '', 'پیش از trialهای نهایی، GapCode Astra با محدودیت مصرف رد شد؛ Codex Astra همان مدل در probe موفق شد و provider آخر برنامه به Codex تغییر یافت. آمارهای قدیمی حافظه در نتیجهٔ جدید استفاده نشده‌اند.',
      '', 'برای بررسی نحوهٔ اجرای CLI، مستندات رسمی [حالت غیرتعاملی](https://learn.chatgpt.com/docs/non-interactive-mode) و [پروفایل مجوز](https://learn.chatgpt.com/docs/permissions) خوانده شد. رفتار واقعی محیط با preflight اندازه‌گیری شد؛ مستندات را به‌جای شاهد اجرای ابزار استفاده نکردیم.',
      '', '## تمام trialها',
      '', '| شناسه | بازو | تکرار | صحیح پذیرفته | audit کاندیدا | false accept | calls | توکن | ثانیه |',
      '|---|---|---:|---|---|---|---:|---:|---:|']
    for t in ts:lines.append(f'| {t["task_id"]} | {t["arm"]} | {t["rep"]+1} | {t["correct"]} | {t["candidate_correct"]} | {t["false_accept"]} | {len(t["calls"])} | {fmt(usage(t),0)} | {fmt(t["latency_s"])} |')
    failures=[t for t in ts if not t['correct'] or len(t['calls'])>1]
    lines += ['', '## شکست‌ها و تلاش‌های اضافی', '', '```json', json.dumps([{'label':t['label'],'failure':t['failure'],'online_checks':t['online_checks'],'audit':t['audit'],'actions':t['actions']} for t in failures],ensure_ascii=False,indent=2),'```',
      '', '## بازتولید و شواهد',
      '', '`plan.json` هش کد، checkpoint، دو اسکیل، تسک‌ها، schedule و دستورها را نگه می‌دارد. `results.json` همهٔ trialها و هش رسیدهای واقعی را دارد؛ `harness-audit.json` نتیجهٔ کنترل سالم/باگ‌دار و صحت فایل‌هاست. `environment.json` نسخه و هش CLIها و runtime را ثبت می‌کند. `gate_receipts/` و ledger داخل workspaceهای SUPER شواهد گیت را حفظ می‌کنند.',
      '', 'برای ادامهٔ **همان اجرای ثابت**: `run.ps1 -Mode live`. برای بازتحلیل بدون فراخوانی: `run.ps1 -Mode analyze`. برای تست harness: `run.ps1 -Mode audit`. رسید موجود تنها با provider/model/effort/prompt یکسان قابل resume است؛ برای نمونهٔ تازه باید پوشهٔ جدید و freeze مستقل بسازید. اجرای مجدد prepare در پوشهٔ قفل‌شده رد می‌شود.',
      '', f'هش طرح: `{B.sha(B.HERE/"plan.json")}`.', '']
    (B.HERE/'REPORT.fa.md').write_text('\n'.join(lines),encoding='utf-8')
    with (B.HERE/'trials.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['task_id','track','family','arm','rep','correct','candidate_correct','policy_accepted','false_accept','false_reject','calls','total_tokens','latency_s'])
        writer.writeheader()
        for t in ts:writer.writerow({k:(len(t['calls']) if k=='calls' else usage(t) if k=='total_tokens' else t[k]) for k in writer.fieldnames})
    render_html(r)
    print('Wrote measured REPORT.fa.md, report.html, trials.csv and gate-summary.json')

def render_html(r):
    data=json.dumps(r,ensure_ascii=False).replace('</','<\\/')
    page='''<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>بنچمارک واقعی اسکیل‌ها</title>
<style>body{font:16px/1.8 Tahoma,Arial,sans-serif;background:#f3f5f8;color:#17212f;margin:0}main{max-width:1180px;margin:auto;padding:30px}h1{font-size:28px}section{background:white;border:1px solid #dde4ec;border-radius:14px;padding:22px;margin:18px 0}select,input{padding:10px;font:inherit;border:1px solid #aebacb;border-radius:7px}table{width:100%;border-collapse:collapse;font-size:14px}td,th{border-bottom:1px solid #e3e9f1;padding:9px;text-align:right}th{background:#f5f8fb}a{color:#2159ad}.scroll{overflow:auto}.bar{height:19px;border-radius:5px;background:#4374d4}.barrow{display:grid;grid-template-columns:200px 1fr 130px;gap:14px;align-items:center;margin:14px 0}.muted{color:#58697b}.bad{color:#b3261e}.ok{color:#166a38}button{padding:8px;border:1px solid #abc;background:#fff;border-radius:6px;cursor:pointer}@media(max-width:650px){main{padding:14px}.barrow{grid-template-columns:130px 1fr 80px}h1{font-size:22px}}</style>
<main><h1>Flux v1 · SUPER · حالت عادی</h1><p>دادهٔ واقعی از CLI و Laya محلی؛ بازسازی گردش‌کار در harness. تمام نشست‌های مدل بدون ابزار هستند.</p><p class="muted" id="status"></p><section><label>نوع کار <select id="track"><option value="reasoning">محاسبات · ۱۲ تسک × دو تکرار</option><option value="engineering">رفع باگ · ۶ تسک × یک تکرار</option></select></label><p>توکن گزارش‌شدهٔ provider؛ input + output، بدون جمع دوبارهٔ cache.</p><div id="bars"></div><div class="scroll"><table id="summary"></table></div></section><section><h2>تمام اجراها</h2><label>فیلتر <input id="filter" placeholder="مثلاً I1 یا super"></label><button id="errors">فقط شکست/تلاش اضافی</button><div class="scroll"><table id="trials"></table></div></section><section><h2>حدود نتیجه</h2><p>نمونه کوچک و مصنوعی است؛ دقت نمونه با برتری عمومی، مصرف توکن با هزینهٔ پولی و تست مستقل با verdict بومی SUPER یکی نیست. verdict ویندوز SUPER ممکن است STALE باشد؛ تمام وضعیت‌ها در گزارش کامل حفظ شده‌اند. کش، شبکه و بار میزبان کنترل نشده‌اند.</p><p><a href="REPORT.fa.md">گزارش دقیق و روش‌شناسی</a> · <a href="results.json">نتایج و هش‌ها</a> · <a href="plan.json">طرح قفل‌شده</a> · <a href="trials.csv">CSV اجراها</a></p></section></main>
<script>const R=DATA;const L={normal:'عادی · Sol medium',super:'SUPER · Sol medium',flux_native:'Flux · مسیر اصلی',flux_matched:'Flux · Sol medium ثابت'};let onlyErrors=false;const num=n=>n==null?'نامعلوم':n.toLocaleString('en-US',{maximumFractionDigits:2});document.querySelector('#status').textContent=(R.complete?'اجرای کامل':'اجرای ناتمام')+' · '+R.completed_trials+' / '+R.scheduled_trials+' آزمایش';function paint(){let track=document.querySelector('#track').value,S=R.tracks[track],max=Math.max(...Object.values(S).map(s=>s.total_tokens_known),1);document.querySelector('#bars').innerHTML=Object.entries(S).map(([a,s])=>`<div class="barrow"><span>${L[a]}</span><div><div class="bar" style="width:${100*s.total_tokens_known/max}%"></div></div><span dir="ltr">${num(s.total_tokens_known)}</span></div>`).join('');document.querySelector('#summary').innerHTML='<tr><th>بازو</th><th>صحیح پذیرفته</th><th>کاندیدای صحیح</th><th>پذیرش غلط</th><th>فراخوانی</th><th>usage نامعلوم</th><th>میانگین ثانیه</th></tr>'+Object.entries(S).map(([a,s])=>`<tr><td>${L[a]}</td><td>${s.correct}/${s.trials}</td><td>${s.candidate_correct}/${s.trials}</td><td>${s.false_accepts}</td><td>${s.provider_calls}</td><td>${s.unknown_usage_calls}</td><td>${num(s.latency_mean_s)}</td></tr>`).join('');let q=document.querySelector('#filter').value.trim().toLowerCase();document.querySelector('#trials').innerHTML='<tr><th>تسک</th><th>بازو</th><th>تکرار</th><th>صحیح</th><th>Audit</th><th>تلاش</th><th>ثانیه</th><th>رسید</th></tr>'+R.trials.filter(t=>t.track===track&&(!q||t.label.toLowerCase().includes(q))&&(!onlyErrors||!t.correct||t.calls.length>1)).map(t=>`<tr><td>${t.task_id}</td><td>${L[t.arm]}</td><td>${t.rep+1}</td><td class="${t.correct?'ok':'bad'}">${t.correct?'موفق':'ناموفق'}</td><td>${t.candidate_correct?'صحیح':'غلط/ناقص'}</td><td>${t.calls.length}</td><td>${num(t.latency_s)}</td><td><a href="receipts/${t.calls[0]}.json">JSON</a></td></tr>`).join('')}document.querySelector('#track').onchange=paint;document.querySelector('#filter').oninput=paint;document.querySelector('#errors').onclick=()=>{onlyErrors=!onlyErrors;paint()};paint();</script></html>'''
    (B.HERE/'report.html').write_text(page.replace('DATA',data),encoding='utf-8')

if __name__=='__main__':main()
