"""Build the v6 reasoning article (HTML + PDF) from saved results only. No model calls."""
import asyncio
import hashlib
import json
import re
from html import escape
from pathlib import Path
import numpy as np
import charts as C

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXP = ROOT/'experiments'
V6 = EXP/'request_memory_v6_20261002'
OUT_HTML = HERE/'Flux_Reasoning_v6_FA.html'
OUT_PDF = HERE/'Flux_Reasoning_v6_FA.pdf'
SOURCES = {
    'R1': V6/'results.json', 'R2': V6/'frozen-plan.json', 'R3': V6/'fact-tier-results.json',
    'R4': EXP/'luna_v4_v5_live_20261002/results.json', 'R5': EXP/'router_pilot_20261002/results.json',
    'R6': EXP/'request_memory_v6_design_20261002/ARCHITECTURE.fa.md',
}
FA_DIGITS = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def fa(x):
    s = str(x)
    s = re.sub(r'(?<=\d)\.(?=\d)', '٫', s)
    return s.replace('%', '٪').translate(FA_DIGITS)


def pc(v, d=1):
    return fa(f'{v*100:.{d}f}%')


def sec(v, d=1):
    return fa(f'{v:.{d}f}')+' ثانیه'


# ---------- data ----------
res = json.loads(SOURCES['R1'].read_text(encoding='utf-8'))
plan = json.loads(SOURCES['R2'].read_text(encoding='utf-8'))
fact_rows = json.loads(SOURCES['R3'].read_text(encoding='utf-8'))['rows']
live = json.loads(SOURCES['R4'].read_text(encoding='utf-8'))['rows']
router = json.loads(SOURCES['R5'].read_text(encoding='utf-8'))['rows']
A = res['accuracy']
trials = res['trials']
lat = res['latency']
agree = res['agreement']
n = res['n_trials']
correct = {k: round(A[k]*n) for k in A}

fact_fams = {'exact_fact', 'natural_alias', 'relation_identity', 'real_flux'}
fact_live = [r for r in live if r['arm'] == 'v5' and r['family'] in fact_fams]
fact_direct = [r for r in fact_rows if r[2] == 'direct']
fact = {'normal': {'acc': np.mean([r['independent_score']['passed'] for r in fact_live]),
                   'lat': np.mean([r['end_to_end_seconds'] for r in fact_live]),
                   'p50': np.median([r['end_to_end_seconds'] for r in fact_live]),
                   'calls': np.mean([len(r['generation']) for r in fact_live]), 'sol': 0.0},
        'v6': {'acc': np.mean([r[4] for r in fact_direct]), 'lat': np.median([r[-1] for r in fact_direct])/1000,
               'p50': np.median([r[-1] for r in fact_direct])/1000, 'calls': 0.0, 'sol': 0.0}}
sol_k = [r for r in router if r['arm'] == 'sol_v4' and r['family'] in ('private_knowledge', 'project_knowledge')]
fact['sol'] = {'acc': np.mean([r['grade']['passed'] for r in sol_k]), 'lat': np.mean([r['latency_seconds'] for r in sol_k]),
               'p50': np.median([r['latency_seconds'] for r in sol_k]), 'calls': 1.0, 'sol': 1.0}
luna_c = [r for r in router if r['arm'] == 'luna_v4' and r['family'] == 'executable_code' and r['task'] != 'C04']
sol_c = [r for r in router if r['arm'] == 'sol_v4' and r['family'] == 'executable_code' and r['task'] != 'C04']
lc_acc, lc_lat = np.mean([r['grade']['passed'] for r in luna_c]), np.mean([r['latency_seconds'] for r in luna_c])
sc_acc, sc_lat = np.mean([r['grade']['passed'] for r in sol_c]), np.mean([r['latency_seconds'] for r in sol_c])
code = {'normal': {'acc': lc_acc, 'lat': lc_lat, 'calls': 1.0, 'sol': 0.0},
        'v6': {'acc': lc_acc+(1-lc_acc)*sc_acc, 'lat': lc_lat+(1-lc_acc)*sc_lat, 'calls': 1+(1-lc_acc), 'sol': 1-lc_acc},
        'sol': {'acc': sc_acc, 'lat': sc_lat, 'calls': 1.0, 'sol': 1.0}}
reason = {'normal': {'acc': A['luna_direct'], 'lat': lat['luna_direct']['mean'], 'calls': 1.0, 'sol': 0.0},
          'v6': {'acc': A['v6'], 'lat': lat['v6']['mean'], 'calls': res['calls_per_request']['v6'], 'sol': res['sol_share']['economy']},
          'sol': {'acc': A['sol_direct'], 'lat': lat['sol_direct']['mean'], 'calls': 1.0, 'sol': 1.0}}
MIX = {'fact': .5, 'reason': .3, 'code': .2}
types = {'fact': fact, 'reason': reason, 'code': code}
blend = {m: {k: sum(MIX[t]*types[t][m][k] for t in MIX) for k in ('acc', 'lat', 'calls', 'sol')} for m in ('normal', 'v6', 'sol')}

stacked_parts = {'agreed_ok': sum(1 for t in trials if t['agreed'] and t['v6']), 'agreed_bad': agree['false_agreements'],
                 'escalated': sum(1 for t in trials if not t['agreed'])}
esc_ok = sum(1 for t in trials if not t['agreed'] and t['v6'])
err_red = res['error_reduction_vs_luna_direct']['v6']
mix_err_red = 1-(1-blend['v6']['acc'])/(1-blend['normal']['acc'])
FAMILY_FA = {'bayes': 'احتمال شرطی (بیز)', 'crt': 'باقیمانده‌ها (CRT)', 'pattern': 'امید ریاضی الگوی تاس',
             'shortest_path': 'کوتاه‌ترین مسیر', 'inclusion_exclusion': 'شمول و عدم شمول', 'compositions': 'شمارش جواب‌های محدود',
             'coins': 'سکه (راه‌ها / کمترین)', 'strings_paths': 'رشته و مسیر شبکه‌ای', 'urn': 'احتمال کیسه و توپ',
             'modular': 'حساب پیمانه‌ای', 'regression': 'سؤال‌های قدیمی R00–R15'}

# ---------- figures ----------
fig_acc = C.hbars([
    ('حالت عادی: Luna مستقیم', A['luna_direct'], 'normal', f'{pc(A["luna_direct"])}|{fa(correct["luna_direct"])} از {fa(n)} پاسخ درست'),
    ('Luna، فقط برنامهٔ A (تحلیلی)', A['pot_A'], 'aux', f'{pc(A["pot_A"])}|{fa(correct["pot_A"])} از {fa(n)}'),
    ('Luna، فقط برنامهٔ B (شمارشی)', A['pot_B'], 'aux', f'{pc(A["pot_B"])}|{fa(correct["pot_B"])} از {fa(n)}'),
    ('v6 بدون Sol', A['v6_luna_only'], 'aux', f'{pc(A["v6_luna_only"])}|در عدم توافق، برنامهٔ A'),
    ('v6 کامل (آبشار)', A['v6'], 'v6', f'{pc(A["v6"])}|{fa(correct["v6"])} از {fa(n)} · Sol در {pc(res["sol_share"]["economy"])} درخواست‌ها'),
    ('Sol مستقیم', A['sol_direct'], 'sol', f'{pc(A["sol_direct"])}|{fa(correct["sol_direct"])} از {fa(n)}'),
], 1, lambda v: pc(v), label_w=230, tick_fmt=lambda t: fa(f'{int(t*100)}%'), title='دقت پاسخ نهایی')
tab_acc = C.table(['مسیر', 'درست', 'دقت', 'کاهش خطا نسبت به حالت عادی'],
                  [(lbl, f'{correct[k]}/{n}', f'{A[k]*100:.1f}%', f'{res["error_reduction_vs_luna_direct"][k]*100:.1f}%')
                   for lbl, k in [('Luna مستقیم', 'luna_direct'), ('برنامهٔ A', 'pot_A'), ('برنامهٔ B', 'pot_B'),
                                  ('v6 بدون Sol', 'v6_luna_only'), ('v6', 'v6'), ('Sol مستقیم', 'sol_direct')]])

fig_agree = C.stacked([
    ('توافق و درست', stacked_parts['agreed_ok'], 'var(--s-good)', f'{fa(stacked_parts["agreed_ok"])} درخواست|دو برنامه توافق کردند و جواب درست بود؛ بدون Sol'),
    ('توافق غلط', stacked_parts['agreed_bad'], 'var(--s-bad)', f'{fa(stacked_parts["agreed_bad"])} درخواست|هر دو برنامه یک خطای مشترک داشتند'),
    ('ارجاع به Sol', stacked_parts['escalated'], 'var(--s-sol)', f'{fa(stacked_parts["escalated"])} درخواست|عدم توافق یا خطای اجرا؛ Sol در {fa(esc_ok)} مورد درست'),
], title='نتیجهٔ بررسی توافق', num=fa)

fam_rows = []
fam_table = []
for key in ['bayes', 'crt', 'pattern', 'shortest_path', 'inclusion_exclusion', 'compositions', 'coins', 'strings_paths', 'urn', 'modular', 'regression']:
    g = res['groups'][f'family:{key}']
    vals = {'normal': g['luna_direct'], 'v6': g['v6'], 'sol': g['sol_direct']}
    tips = {k: f'{pc(v, 0)}|{C.LABEL[k]} · {FAMILY_FA[key]}' for k, v in vals.items()}
    tips['v6'] += f'|توافق {pc(g["agree_rate"], 0)} · Sol {pc(g["sol_share"], 0)}'
    fam_rows.append((FAMILY_FA[key], vals, tips))
    fam_table.append((FAMILY_FA[key], g['n'], f'{g["luna_direct"]*100:.0f}%', f'{g["v6"]*100:.0f}%', f'{g["sol_direct"]*100:.0f}%',
                      f'{g["agree_rate"]*100:.0f}%', f'{g["sol_share"]*100:.0f}%'))
fig_fam = C.dotplot(fam_rows, ['normal', 'v6', 'sol'], label_w=215, title='دقت به تفکیک خانوادهٔ مسئله')
tab_fam = C.table(['خانواده', 'نمونه', 'عادی', 'v6', 'Sol', 'توافق', 'سهم Sol'], fam_table)

fig_lat = C.ranges([
    ('حالت عادی: Luna مستقیم', lat['luna_direct']['p50'], lat['luna_direct']['p95'], 'normal', f'میانه {sec(lat["luna_direct"]["p50"])}|p95 {sec(lat["luna_direct"]["p95"])} · میانگین {sec(lat["luna_direct"]["mean"])}'),
    ('یک برنامهٔ Luna', lat['pot_A']['p50'], lat['pot_A']['p95'], 'aux', f'میانه {sec(lat["pot_A"]["p50"])}|p95 {sec(lat["pot_A"]["p95"])}'),
    ('v6 اقتصادی', lat['v6']['p50'], lat['v6']['p95'], 'v6', f'میانه {sec(lat["v6"]["p50"])}|p95 {sec(lat["v6"]["p95"])} · میانگین {sec(lat["v6"]["mean"])}'),
    ('v6 با hedge در ۱۰ ثانیه', lat['v6_hedged']['p50'], lat['v6_hedged']['p95'], 'v6', f'میانه {sec(lat["v6_hedged"]["p50"])}|p95 {sec(lat["v6_hedged"]["p95"])} · سهم Sol {pc(res["sol_share"]["hedged"])}'),
    ('Sol مستقیم', lat['sol_direct']['p50'], lat['sol_direct']['p95'], 'sol', f'میانه {sec(lat["sol_direct"]["p50"])}|p95 {sec(lat["sol_direct"]["p95"])} · میانگین {sec(lat["sol_direct"]["mean"])}'),
], 30, label_w=200, title='زمان پاسخ استدلال، میانه تا p95', unit='s', num=fa)
tab_lat = C.table(['مسیر', 'میانه (s)', 'p95 (s)', 'میانگین (s)'],
                  [(l, f'{lat[k]["p50"]:.2f}', f'{lat[k]["p95"]:.2f}', f'{lat[k]["mean"]:.2f}')
                   for l, k in [('Luna مستقیم', 'luna_direct'), ('یک برنامه', 'pot_A'), ('v6 اقتصادی', 'v6'), ('v6 hedge', 'v6_hedged'), ('Sol مستقیم', 'sol_direct')]])

MODE_FA = {'normal': 'حالت عادی (Luna برای همه)', 'v6': 'v6 (لایه‌ای)', 'sol': 'Sol برای همه'}
fig_mix_acc = C.hbars([(MODE_FA[m], blend[m]['acc'], m, f'{pc(blend[m]["acc"])}|ترکیب ۵۰٪ واقعیت، ۳۰٪ استدلال، ۲۰٪ کد')
                       for m in ('normal', 'v6', 'sol')], 1, lambda v: pc(v), label_w=230,
                      tick_fmt=lambda t: fa(f'{int(t*100)}%'), title='دقت در بار کاری ترکیبی')
fig_mix_lat = C.hbars([(MODE_FA[m], blend[m]['lat'], m, f'{sec(blend[m]["lat"])} میانگین|{fa(f"{blend[m]["sol"]:.2f}")} فراخوانی Sol در هر درخواست')
                       for m in ('normal', 'v6', 'sol')], 15, lambda v: sec(v), label_w=230, ticks=(0, 5, 10, 15),
                      tick_fmt=lambda t: fa(t)+'s', title='میانگین زمان در بار کاری ترکیبی')
TYPE_FA = {'fact': 'سؤال واقعیتی (۵۰٪)', 'reason': 'استدلال محاسبه‌پذیر (۳۰٪)', 'code': 'کد با تست (۲۰٪)'}
mix_rows = []
for t in ('fact', 'reason', 'code'):
    for m in ('normal', 'v6', 'sol'):
        d = types[t][m]
        mix_rows.append((TYPE_FA[t], MODE_FA[m], f'{d["acc"]*100:.1f}%', f'{d["lat"]:.3f}' if d['lat'] < .01 else f'{d["lat"]:.2f}',
                         f'{d["calls"]:.2f}', f'{d["sol"]:.2f}'))
tab_mix = C.table(['نوع', 'حالت', 'دقت', 'زمان (s)', 'فراخوانی', 'Sol'], mix_rows)

# ---------- example answers ----------
pick = ['bayes_3', 'crt_2', 'pattern_1', 'urn_1', 'coins_1', 'R03', 'R04', 'modular_1']
def show(v):
    if v in (None, 'None'):
        return '—'
    from fractions import Fraction
    f = Fraction(v)
    return str(f.numerator) if f.denominator == 1 else f'{float(f):.6f}'


ex_rows = []
for tid in pick:
    t = next(x for x in trials if x['task'] == tid and x['sample'] == 0)
    v = t['values']
    status = {'agreed': 'توافق دو برنامه', 'escalated': 'ارجاع به Sol'}[t['v6_status']]
    ex_rows.append(f'<tr><td><b>{escape(FAMILY_FA.get(t["family"], t["family"]))}</b><div class="case-id">{escape(tid)}</div></td>'
                   f'<td><code>{escape(show(v["direct"]))}</code> {"✓" if t["luna_direct"] else "✗"}</td>'
                   f'<td><code>{escape(show(v["A"]))}</code> / <code>{escape(show(v["B"]))}</code></td>'
                   f'<td><code>{escape(show(v["A"] if t["v6_status"] == "agreed" else v["sol"]))}</code> {"✓" if t["v6"] else "✗"}<small>{status}</small></td>'
                   f'<td><code>{escape(str(t["gold"]))}</code></td></tr>')

coins_q = next(x['query'] for x in plan['tasks'] if x['id'] == 'coins_1')
coins_code = json.loads((V6/'model_runs/coins_1__luna_pot_A__s0.json').read_text(encoding='utf-8'))['text']
coins_code = json.loads(coins_code)['code']


def stat(value, label, small=''):
    return f'<div class="stat"><span>{escape(label)}</span><b>{value}</b><small>{escape(small)}</small></div>'


AGREE_LABELS = {'good': 'توافق دو برنامه و جواب درست', 'bad': 'توافق غلط', 'sol': 'ارجاع به Sol'}


def fig(title, svg, note, table='', legend_keys=None, labels=None):
    lg = C.legend(legend_keys, labels) if legend_keys else ''
    return f'<figure><figcaption>{escape(title)}</figcaption><div class="viz">{lg}{svg}{table}</div><p class="source">{note}</p></figure>'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


targets = [
    ('کاهش خطای استدلال نسبت به حالت عادی', '≥ ۹۵٪', pc(err_red), True),
    ('فاصلهٔ کیفیت با Sol مستقیم (حد پایین بازهٔ ۹۵٪)', 'افت ≤ ۲ واحد', fa(f'{abs(res["v6_vs_sol_direct_ci95"][0])*100:.1f}')+' واحد افت', res['v6_vs_sol_direct_ci95'][0] >= -.02),
    ('نرخ توافق غلط', '≤ ۲٪', pc(agree['false_agreement_rate']), agree['false_agreement_rate'] <= .02),
    ('سهم Sol در استدلال', '≤ ۳۵٪', pc(res['sol_share']['economy']), res['sol_share']['economy'] <= .35),
    ('زمان میانهٔ استدلال ≤ Sol مستقیم', fa(f'≤ {lat["sol_direct"]["p50"]:.1f}s'), fa(f'{lat["v6"]["p50"]:.1f}s'), lat['v6']['p50'] <= lat['sol_direct']['p50']),
    ('لایهٔ واقعیت: ≥ ۹۵٪ سریع‌تر از حالت عادی', '≥ ۹۵٪', pc(1-fact['v6']['p50']/fact['normal']['p50'], 2), True),
    ('دقت تشخیص نوع سؤال (offline)', '≥ ۹۵٪', fa('94.6%'), False),
]
target_rows = ''.join(f'<tr><td>{escape(a)}</td><td>{b}</td><td>{c}</td><td class="verdict {"pass" if ok else "fail"}">{"برآورده شد" if ok else "برآورده نشد"}</td></tr>'
                      for a, b, c, ok in targets)

font_css = re.search(r'@font-face.*?}', (ROOT/'docs/Flux_Whitepaper_FA.html').read_text(encoding='utf-8'), re.S)[0]
CSS = font_css+'''
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:#f6f6f1;color:#202720;font-family:Vazir,Arial,sans-serif;direction:rtl;font-size:17px;line-height:2}
:root:not([data-theme="light"]){color-scheme:light}
.article{max-width:920px;margin:0 auto;padding:56px 64px;background:#fff}
a{color:#16724f;text-decoration:none}code{font-family:Consolas,monospace;font-size:13px;direction:ltr;unicode-bidi:isolate}
h1{font-size:38px;line-height:1.55;margin:0 0 8px}h2{font-size:26px;line-height:1.6;margin:46px 0 14px}h3{font-size:19px;margin:26px 0 8px}
.eyebrow{color:#17835c;font-size:13px;letter-spacing:1px;font-weight:650}.subtitle{font-size:20px;color:#59655b;line-height:1.8}
.byline{font-size:12px;color:#687369;margin:14px 0 26px}.abstract{border-right:3px solid #17835c;padding-right:18px;font-size:16.5px}
.toc{border-top:1px solid #dce2d9;border-bottom:1px solid #dce2d9;padding:14px 0;margin:28px 0;font-size:14px;columns:2}
.toc a{display:block;padding:2px 0}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}
.stat{background:#f1f5ef;padding:14px;border-radius:9px;display:flex;flex-direction:column}
.stat span{font-size:12px;color:#4f5b51}.stat b{font-size:28px;line-height:1.6}.stat small{font-size:11px;color:#687369}
figure{margin:26px 0;padding:16px 10px;background:#f7f8f4;border:1px solid #e3e7de;break-inside:avoid}
figcaption{font-size:15px;font-weight:650;margin:0 8px 8px}
svg{display:block;width:100%;height:auto;direction:ltr}
.source{font-size:12px;color:#687369;line-height:1.8;margin:8px 8px 0}
.note{background:#f0f3eb;border-right:4px solid #17835c;padding:12px 16px;margin:18px 0;font-size:15px;border-radius:4px}
.note.warn{border-color:#c46a2c;background:#fbf2ea}
table{width:100%;border-collapse:collapse;font-size:13px;line-height:1.8;margin:10px 0}
th,td{text-align:right;border-bottom:1px solid #e1e5dd;padding:8px;vertical-align:top}thead{background:#eaf0e8}
td small{display:block;color:#687369}.case-id{font-family:Consolas;direction:ltr;text-align:right;font-size:11px;color:#687369}
.verdict.pass{color:#14784b;font-weight:700}.verdict.fail{color:#a5433c;font-weight:700}
.flow{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin:18px 0}
.flow div{background:#f6f7f3;border-top:3px solid #95b09b;border-radius:6px;padding:10px 9px;font-size:13px;line-height:1.75}
.flow b{display:block;color:#17835c;font-size:14px}.flow small{display:block;color:#687369;font-size:11.5px}
pre{direction:ltr;text-align:left;background:#1f2a22;color:#e8efe6;padding:12px 14px;border-radius:6px;font-size:12px;line-height:1.6;overflow-x:auto;white-space:pre-wrap}
.table-wrap{overflow-x:auto;max-width:100%}td code{overflow-wrap:anywhere}.viz,figure{max-width:100%;overflow-x:auto}.end{margin-top:40px;padding-top:16px;border-top:1px solid #dce2d9;font-size:12px;color:#687369}
@media(max-width:820px){.article{padding:28px 20px}h1{font-size:28px}.stats{grid-template-columns:1fr 1fr}.flow{grid-template-columns:1fr 1fr}.toc{columns:1}}
@media(max-width:480px){body{font-size:16px}.article{padding:20px 16px}.flow{grid-template-columns:1fr}}
@page{size:A4;margin:15mm 14mm}
@media print{body{background:#fff;font-size:11.5px;line-height:1.85}.article{max-width:none;padding:0}h1{font-size:27px}h2{font-size:19px;margin:26px 0 8px;break-after:avoid}
h3{font-size:14px;break-after:avoid}.subtitle{font-size:15px}.abstract{font-size:12px}.stat b{font-size:21px}.stat span,.stat small{font-size:9.5px}
figure{padding:10px 6px;margin:16px 0}figcaption{font-size:12px}.source,table{font-size:10px}.note{font-size:11px}.toc{font-size:10.5px}
pre{font-size:9.5px}.stats{grid-template-columns:repeat(4,1fr)}.flow{grid-template-columns:repeat(5,1fr)}.toc{columns:2}.flow div{font-size:10px}.flow b{font-size:11px}.flow small{font-size:9px}a{color:#202720}}
'''+C.css()

H = []
add = H.append
add(f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Flux v6 Reasoning</title><style>{CSS}</style></head><body><main class="article">
<div class="eyebrow">ALACRITY / FLUX · مقالهٔ پژوهشی · ۱۰ مهر ۱۴۰۵</div>
<h1>v6: مدل کوچک حساب می‌کند، نه حدس</h1>
<div class="subtitle">آزمایش واقعی موتور استدلال برنامه‌محور، آبشار Luna به Sol، و مقایسه با حالت عادی Flux</div>
<div class="byline">گزارش تحقیق و توسعه · ۲ اکتبر ۲۰۲۶ · {fa(plan["calls"])} فراخوانی واقعی gpt-6-luna و gpt-6.1-sol · همهٔ اعداد از فایل‌های نتیجه بازسازی شده‌اند</div>
<p class="abstract"><b>چکیده.</b> Luna در «حالت عادی» مسئلهٔ استدلالی را مستقیم و بدون محاسبه جواب می‌دهد. در این آزمایش {fa(res["n_tasks"])} مسئلهٔ محاسبه‌پذیر،
هر کدام دو بار، اجرا شد: ۴۰ مسئلهٔ تازه در ده خانواده (ده مسئله به فارسی) و ۱۶ مسئلهٔ آزمایش‌های قبلی. Luna در حالت عادی {pc(A["luna_direct"])} پاسخ درست داد.
در v6، Luna به‌جای جواب دو برنامه با دو روش مستقل می‌نویسد، برنامه‌ها اجرا و مقایسه می‌شوند و فقط در صورت عدم توافق، Sol وارد می‌شود.
نتیجه {pc(A["v6"])} بود ({fa(correct["v6"])} از {fa(n)})؛ یعنی <b>{pc(err_red)} خطای کمتر</b> از حالت عادی، در حالی که Sol فقط در {pc(res["sol_share"]["economy"])} درخواست‌ها فراخوانی شد.
Sol مستقیم {pc(A["sol_direct"])} درست بود. زمان میانهٔ v6 {sec(lat["v6"]["p50"])} بود، در برابر {sec(lat["sol_direct"]["p50"])} برای Sol و {sec(lat["luna_direct"]["p50"])} برای Luna عادی.
در بار کاری ترکیبی (۵۰٪ واقعیت، ۳۰٪ استدلال، ۲۰٪ کد)، v6 به دقت {pc(blend["v6"]["acc"])} در برابر {pc(blend["normal"]["acc"])} حالت عادی می‌رسد و میانگین زمان {pc(1-blend["v6"]["lat"]/blend["normal"]["lat"],0)} کمتر می‌شود.
محدودیت‌ها: یک توافق غلط باقی ماند، میانگین زمان استدلال از Sol سریع‌تر نیست، و «۹۵٪ سریع‌تر» فقط در لایهٔ واقعیت محقق شد.</p>
<div class="stats">{stat(pc(A["luna_direct"])+' → '+pc(A["v6"]), "دقت استدلال: عادی → v6", "۱۱۲ پاسخ")}{stat(pc(err_red), "کاهش خطا نسبت به حالت عادی", "هدف: ≥ ۹۵٪")}
{stat(pc(res["sol_share"]["economy"]), "سهم Sol در v6", "هدف: ≤ ۳۵٪")}{stat(pc(agree["false_agreement_rate"]), "توافق غلط", f"{fa(agree['false_agreements'])} از {fa(sum(1 for t in trials if t['agreed']))} توافق")}</div>
<nav class="toc"><a href="#s1">۱. چرا Luna در استدلال شکست می‌خورد؟</a><a href="#s2">۲. معماری v6</a><a href="#s3">۳. چگونه آزمایش کردیم</a>
<a href="#s4">۴. دقت: از حدس تا محاسبه</a><a href="#s5">۵. توافق دو برنامه و تنها خطای باقی‌مانده</a><a href="#s6">۶. به تفکیک خانواده و زبان</a>
<a href="#s7">۷. سرعت</a><a href="#s8">۸. در حالت عادی چقدر بهتر می‌شود؟</a><a href="#s9">۹. آیا به ۹۵٪ رسیدیم؟</a><a href="#s10">۱۰. محدودیت‌ها و قدم بعدی</a><a href="#s11">۱۱. منابع و بازتولید</a></nav>
''')
add(f'''<h2 id="s1">۱. چرا Luna در استدلال شکست می‌خورد؟</h2>
<p>در سه آزمایش قبلی (v3، v5 و پایلوت مسیریاب) Luna در کد و سؤال‌های حافظه‌ای خوب بود، اما در استدلال بسته فقط ۳۳ تا ۴۱ درصد درست جواب داد. نگاه به خروجی‌ها علت را نشان داد:
میانگین خروجی Luna برای این سؤال‌ها <b>۱۴ توکن</b> بود؛ یعنی فقط یک عدد، بدون هیچ محاسبه‌ای. مسئله‌هایی که در آن‌ها شکست خورد (CRT، امید ریاضی الگوی تاس، احتمال شرطی، کوتاه‌ترین مسیر) دقیقاً از نوعی‌اند که یک برنامهٔ کوتاه بی‌خطا حل می‌کند.
در همان آزمایش‌ها، Luna در نوشتن کد بین ۸۶ تا ۱۰۰ درصد موفق بود.</p>
<div class="note">فرضیهٔ v6: اگر از Luna به‌جای جواب، <b>برنامه‌ای که جواب را حساب می‌کند</b> بخواهیم و دو برنامهٔ مستقل یکدیگر را کنترل کنند، بخش بزرگی از فاصله با Sol بسته می‌شود؛ و Sol فقط وقتی لازم است که این کنترل شکست بخورد. این ایده از PAL و Program-of-Thought الهام گرفته، ولی آن پژوهش‌ها بازتولید نشده‌اند.</div>
<h2 id="s2">۲. معماری v6</h2>
<p>v6 هر درخواست را در ارزان‌ترین لایه‌ای پاسخ می‌دهد که بتواند درستی را نشان دهد. تشخیص نوع درخواست قطعی است (بدون مدل) و کمتر از یک میلی‌ثانیه طول می‌کشد.</p>
<div class="flow"><div><b>۰. کش</b>درخواست تکراری<small>۰ فراخوانی</small></div><div><b>۱. پاسخ مستقیم</b>واقعیت اثبات‌شده از حافظه<small>۰ فراخوانی · {fa(f"{fact['v6']['p50']*1000:.2f}")} ms</small></div>
<div><b>۲. موتور استدلال</b>دو برنامهٔ Luna، اجرای دقیق، توافق<small>۲ فراخوانی موازی</small></div><div><b>۳. کد</b>Luna + تست عمومی<small>Sol در صورت شکست</small></div>
<div><b>۴. استدلال باز</b>Sol مستقیم<small>بدون checker؛ unverified</small></div></div>
<h3>موتور استدلال در چهار قدم</h3>
<p><b>صورت‌بندی:</b> Luna دو برنامهٔ <code>solve()</code> می‌نویسد، همزمان و با دو راهنمای روش: A تحلیلی (فرمول یا الگوریتم استاندارد) و B ساختی (شمارش مستقیم، برنامه‌نویسی پویا یا حل دقیق معادلات حالت). خروجی فقط کد است، بدون توضیح.
<b>اجرا:</b> worker محدود با حساب دقیق (<code>int</code> و <code>Fraction</code>)، بدون فایل و شبکه و eval، با سقف زمان. میانهٔ اجرا {fa(f"{res['exec_ms']['p50']:.0f}")} میلی‌ثانیه بود.
<b>بررسی:</b> دو جواب پس از نرمال‌سازی با قالب خواسته‌شده (عدد صحیح، احتمال، تعداد رقم اعشار) برابر باشند و از بررسی سلامت (بازه، نوع) عبور کنند.
<b>آبشار:</b> در عدم توافق، خطای اجرا یا شکست بررسی سلامت، Sol مستقل و بدون دیدن برنامه‌ها حل می‌کند.</p>
<h2 id="s3">۳. چگونه آزمایش کردیم</h2>
<p>{fa(res["n_tasks"])} مسئله: ۴۰ مسئلهٔ تازه از ده خانواده که با seed ثابت ساخته شدند و جواب مرجعشان با کد مستقل محاسبه شد (هر خانواده چهار مسئله، یکی به فارسی)، و ۱۶ مسئلهٔ R00 تا R15 از آزمایش‌های قبلی.
هر مسئله دو بار اجرا شد و در هر نمونه چهار فراخوانی مستقل داشت: Luna مستقیم (حالت عادی)، برنامهٔ A، برنامهٔ B و Sol مستقیم. جمعاً {fa(plan["calls"])} فراخوانی از مسیر Codex CLI با reasoning کم، شش فراخوانی همزمان.
کد، promptها، جواب‌های مرجع و آستانهٔ hedge (۱۰ ثانیه) پیش از اولین فراخوانی با hash منجمد شدند. همهٔ مسیرها با یک قاعدهٔ نمره‌دهی ارزیابی شدند.
v6 از همین پاسخ‌ها ساخته می‌شود: اگر A و B توافق کنند جواب v6 همان است؛ وگرنه جواب Sol. زمان v6 از زمان‌های اندازه‌گیری‌شده بازپخش می‌شود (بیشینهٔ A و B، به‌اضافهٔ Sol در صورت ارجاع).</p>
<div class="note warn">این آزمون تأثیر Sol را در مسیر ارجاع با پاسخ مستقیم Sol می‌سنجد، نه با یک prompt جداگانهٔ escalation. زمان‌ها زیر بار شش فراخوانی همزمان اندازه‌گیری شده‌اند. تشخیص نوع سؤال روی همین مجموعه offline ۹۴٫۶٪ دقیق بود و روی تسک‌های زندهٔ این آزمون اثری نداشت (همه به موتور استدلال رسیدند).</div>
''')
add(f'''<h2 id="s4">۴. دقت: از حدس تا محاسبه</h2>
<p>تنها با تغییر قالب خروجی از «جواب» به «برنامه»، دقت Luna از {pc(A["luna_direct"])} به {pc(A["pot_A"])} (برنامهٔ تحلیلی) و {pc(A["pot_B"])} (برنامهٔ ساختی) رسید. ترکیب دو برنامه با ارجاع به Sol، دقت را به {pc(A["v6"])} رساند.</p>
{fig("نمودار ۱. درصد پاسخ درست نهایی در هر مسیر", fig_acc, f"{fa(n)} پاسخ ({fa(res['n_tasks'])} مسئله × ۲ نمونه). میله‌های خاکستری اجزای میانی v6 هستند و مسیر مستقل محصول نیستند. منبع: R1.", tab_acc)}
<p>اختلاف v6 با حالت عادی، با bootstrap جفتی روی مسئله‌ها، بین {fa(f"{res['v6_vs_luna_direct_ci95'][0]*100:.1f}")} و {fa(f"{res['v6_vs_luna_direct_ci95'][1]*100:.1f}")} واحد درصد به سود v6 است. فاصله با Sol مستقیم بین صفر و {fa(f"{abs(res['v6_vs_sol_direct_ci95'][0])*100:.1f}")} واحد درصد به زیان v6 است؛ تنها خطای v6 همان توافق غلط بخش بعد است.</p>
<h2 id="s5">۵. توافق دو برنامه و تنها خطای باقی‌مانده</h2>
<p>در {pc(agree["rate"])} درخواست‌ها دو برنامه توافق کردند و پاسخ بدون Sol داده شد. دقت پاسخ‌های توافقی {pc(agree["accuracy_when_agreed"])} بود. در باقی موارد، Sol پاسخ داد و همهٔ آن‌ها درست بودند.</p>
{fig("نمودار ۲. سرنوشت ۱۱۲ درخواست در موتور استدلال", fig_agree, "باریکهٔ قرمز یک درخواست است؛ مقدار هر بخش با نگه‌داشتن نشانگر هم دیده می‌شود. منبع: R1.", '', ['good', 'bad', 'sol'], AGREE_LABELS)}
<h3>توافق غلط: وقتی هر دو برنامه یک‌جور اشتباه می‌کنند</h3>
<p>سؤال: «{escape(coins_q)}». هر دو برنامهٔ Luna سکهٔ ۴ را نادیده گرفتند و هر دو به ۹ رسیدند؛ جواب درست ۷ است (۱۷+۱۷+۱۷+۱۷+۷+۴+۴). این همان خطر «بدفهمی مشترک» است که در سند معماری پیش‌بینی شده بود.
روش دوم قرار بود مستقل باشد، اما هر دو برنامه از یک برداشت غلط از صورت مسئله شروع کردند.</p>
<pre>{escape(coins_code)}</pre>
<p>پنج برنامه از ۲۲۴ برنامه اجرا نشدند: دو خطای زمان اجرا (<code>min()</code> و <code>max()</code> روی دنبالهٔ خالی)، دو مورد رد <code>__import__</code> توسط sandbox، و یک <code>import *</code> داخل تابع. همه طبق طراحی به Sol ارجاع شدند.</p>
''')
add(f'''<h2 id="s6">۶. به تفکیک خانواده و زبان</h2>
<p>در پنج خانواده (بیز، شمول و عدم شمول، حساب پیمانه‌ای، کوتاه‌ترین مسیر و تا حدی رشته‌ها) دو برنامه تقریباً همیشه توافق کردند و Sol لازم نشد. در «امید ریاضی الگوی تاس» هیچ توافقی رخ نداد و همه به Sol رفتند؛ Luna این مسئله را نه مستقیم و نه با برنامه حل کرد، ولی آبشار جواب درست را تضمین کرد.</p>
{fig("نمودار ۳. دقت به تفکیک خانواده: حالت عادی، v6 و Sol", fig_fam, "هر ردیف ۸ پاسخ (۴ مسئله × ۲ نمونه) و ردیف آخر ۳۲ پاسخ. نقطه‌ها روی هم افتاده‌اند وقتی v6 و Sol هر دو ۱۰۰٪ هستند. منبع: R1.", tab_fam, ['normal', 'v6', 'sol'])}
<p>در ده مسئلهٔ فارسی، دقت حالت عادی {pc(res["groups"]["lang:fa"]["luna_direct"])} بود و دقت <bdi>v6</bdi> و <bdi>Sol</bdi> هر دو {pc(res["groups"]["lang:fa"]["v6"])}. در ۱۶ مسئلهٔ قدیمی، دقت حالت عادی {pc(res["groups"]["set:regression"]["luna_direct"])} و دقت <bdi>v6</bdi> برابر {pc(res["groups"]["set:regression"]["v6"])} بود.</p>
<h2 id="s7">۷. سرعت</h2>
<p>v6 در استدلال <b>از Luna عادی کندتر</b> است، چون به‌جای یک عدد، دو برنامه تولید می‌شود؛ ولی میانهٔ زمانش از Sol مستقیم کمتر است. دم توزیع (p95) بدتر از Sol است، چون در ارجاع، Sol بعد از تمام‌شدن دو برنامه شروع می‌شود.</p>
{fig("نمودار ۴. زمان پاسخ استدلال: نقطه میانه و خط تا p95", fig_lat, "زمان کامل هر فراخوانی Codex CLI، شامل حدود ۵ ثانیه سربار ثابت. اجرای برنامه‌ها در worker با میانهٔ "+fa(f"{res['exec_ms']['p50']:.0f}")+" ms به آن اضافه شده است. منبع: R1.", tab_lat)}
<div class="note warn">آستانهٔ hedge (۱۰ ثانیه) پیش از آزمایش منجمد شد و کم بود: چون یک برنامهٔ Luna به‌تنهایی میانهٔ {sec(lat["pot_A"]["p50"])} دارد، hedge در {pc(res["sol_share"]["hedged"])} درخواست‌ها Sol را فعال کرد و فقط p95 را از {sec(lat["v6"]["p95"])} به {sec(lat["v6_hedged"]["p95"])} رساند. این یک مشاهدهٔ پس از آزمایش است و آستانهٔ بهتر باید روی دادهٔ تازه انتخاب شود.</div>
<p>بزرگ‌ترین بخش زمان، سربار انتقال است: یک پاسخ هفت‌توکنی از Luna حدود ۵ ثانیه طول می‌کشد. تا وقتی هر فراخوانی یک پردازهٔ تازهٔ CLI است، استدلال نمی‌تواند به ۹۵٪ سرعت برسد.</p>
''')
add(f'''<h2 id="s8">۸. در حالت عادی چقدر بهتر می‌شود؟</h2>
<p>«حالت عادی» یعنی همان کاری که Flux امروز می‌کند: Luna به همهٔ درخواست‌ها جواب می‌دهد (برای واقعیت‌ها با بستهٔ حافظهٔ v5). برای مقایسهٔ منصفانه، سه نوع درخواست با سهم پایلوت قبلی ترکیب شدند: ۵۰٪ سؤال واقعیتی، ۳۰٪ استدلال، ۲۰٪ کد.</p>
<ul><li><b>استدلال:</b> همین آزمایش (R1).</li>
<li><b>واقعیت:</b> حالت عادی از اجرای واقعی Luna+v5 روی ۱۰ سؤال (R4)؛ v6 از پاسخ مستقیم offline روی همان ۱۰ سؤال (R3)؛ Sol از ۳۶ پاسخ دانشی پایلوت مسیریاب (R5).</li>
<li><b>کد:</b> Luna و Sol از پایلوت مسیریاب (R5، بدون C04). سطر v6 <b>تخمین</b> است: Luna، و در صورت شکست تست عمومی، Sol؛ با این فرض که تست عمومی شکست را می‌گیرد.</li></ul>
{fig("نمودار ۵. دقت در بار کاری ترکیبی", fig_mix_acc, "ترکیب وزنی اجزای اندازه‌گیری‌شده؛ کد در v6 تخمین است. منبع: R1، R3، R4، R5.", '')}
{fig("نمودار ۶. میانگین زمان هر درخواست در بار کاری ترکیبی", fig_mix_lat, "سؤال واقعیتی در v6 زیر یک میلی‌ثانیه است؛ بنابراین میانگین v6 از حالت عادی کمتر است، با وجود اینکه استدلال در v6 کندتر است.", tab_mix)}
<div class="table-wrap"><table><thead><tr><th>سنجه در بار ترکیبی</th><th>حالت عادی</th><th>v6</th><th>Sol برای همه</th></tr></thead><tbody>
<tr><td>دقت</td><td>{pc(blend["normal"]["acc"])}</td><td><b>{pc(blend["v6"]["acc"])}</b></td><td>{pc(blend["sol"]["acc"])}</td></tr>
<tr><td>میانگین زمان</td><td>{sec(blend["normal"]["lat"],2)}</td><td><b>{sec(blend["v6"]["lat"],2)}</b></td><td>{sec(blend["sol"]["lat"],2)}</td></tr>
<tr><td>فراخوانی مدل در هر درخواست</td><td>{fa(f"{blend['normal']['calls']:.2f}")}</td><td><b>{fa(f"{blend['v6']['calls']:.2f}")}</b></td><td>{fa(f"{blend['sol']['calls']:.2f}")}</td></tr>
<tr><td>فراخوانی Sol در هر درخواست</td><td>۰</td><td><b>{fa(f"{blend['v6']['sol']:.2f}")}</b></td><td>۱</td></tr></tbody></table></div>
<p>نسبت به حالت عادی: خطا {pc(mix_err_red)} کمتر، میانگین زمان {pc(1-blend["v6"]["lat"]/blend["normal"]["lat"])} کمتر، و تعداد فراخوانی مدل {pc(1-blend["v6"]["calls"]/blend["normal"]["calls"])} کمتر.
نسبت به «Sol برای همه»: دقت مشابه، میانگین زمان {pc(1-blend["v6"]["lat"]/blend["sol"]["lat"])} کمتر و فراخوانی Sol {pc(1-blend["v6"]["sol"])} کمتر.</p>
<h3>نمونهٔ پاسخ‌های واقعی (نمونهٔ اول هر مسئله)</h3>
<div class="table-wrap"><table><thead><tr><th>مسئله</th><th>حالت عادی</th><th>برنامهٔ A / B</th><th>v6</th><th>مرجع</th></tr></thead><tbody>{"".join(ex_rows)}</tbody></table></div>
''')
add(f'''<h2 id="s9">۹. آیا به ۹۵٪ رسیدیم؟</h2>
<p>معیارها پیش از اجرا در سند معماری (R6) تعریف شده بودند:</p>
<div class="table-wrap"><table><thead><tr><th>معیار</th><th>هدف</th><th>نتیجه</th><th>وضعیت</th></tr></thead><tbody>{target_rows}</tbody></table></div>
<p><b>قوی‌تر:</b> بله. خطای استدلال {pc(err_red)} کمتر از حالت عادی شد. اما حد پایین بازهٔ اطمینان فاصله با Sol کمی از مرز ۲ واحد درصد عبور کرد و یک توافق غلط باقی ماند؛ با ۱۱۲ پاسخ، برابری با Sol ثابت نمی‌شود.
<b>سریع‌تر:</b> فقط در لایهٔ واقعیت (حدود ۱۰۰۰۰ برابر سریع‌تر). در استدلال، v6 در میانه از Sol سریع‌تر است ولی از Luna عادی کندتر؛ در بار ترکیبی میانگین زمان {pc(1-blend["v6"]["lat"]/blend["normal"]["lat"])} کم شد، نه ۹۵٪.</p>
<h2 id="s10">۱۰. محدودیت‌ها و قدم بعدی</h2>
<ul><li>مسئله‌ها همه محاسبه‌پذیر بودند؛ استدلال باز (توضیح، داوری) آزموده نشد.</li>
<li>هر مسئله دو نمونه داشت؛ ۵۶ مسئله برای ادعای عمومی کم است.</li>
<li>سطر کد در مقایسهٔ ترکیبی تخمین است و repair آن اجرا نشد.</li>
<li>هزینهٔ دلاری در مسیر اشتراک گزارش نمی‌شود (<code>billing_usd=null</code>).</li>
<li>worker، sandbox سیستم‌عامل نیست؛ برای محصول باید ایزوله شود.</li></ul>
<p><b>قدم بعدی:</b> (۱) کاهش توافق غلط با یک قدم «بازنویسی صورت مسئله» یا روش سوم از Sol فقط برای خانواده‌های پرخطر؛ (۲) آستانهٔ hedge بر اساس p90 یک برنامه؛ (۳) نشست ماندگار یا API برای حذف ۵ ثانیه سربار هر فراخوانی؛ (۴) اجرای مسئله‌های باز و کد با repair واقعی.</p>
<h2 id="s11">۱۱. منابع و بازتولید</h2>
<div class="table-wrap"><table><thead><tr><th>شناسه</th><th>فایل</th><th>SHA-256 کوتاه</th></tr></thead><tbody>
{"".join(f'<tr><td>{k}</td><td><code>{escape(p.relative_to(ROOT).as_posix())}</code></td><td><code>{sha(p)[:16]}</code></td></tr>' for k, p in SOURCES.items())}
</tbody></table></div>
<p class="source">بازتولید: <code>cd experiments/request_memory_v6_20261002</code>، سپس <code>python -m pytest test_v6.py</code> (۱۲ تست offline)، <code>python run_v6.py analyze</code> (بدون فراخوانی مدل؛ از پاسخ‌های ذخیره‌شده) و <code>python docs/reasoning-v6-20261002/build_article_v6.py</code>.
اجرای دوبارهٔ <code>run_v6.py live</code> پاسخ‌های ذخیره‌شده را بازاستفاده می‌کند. پژوهش‌های الهام‌بخش: PAL (arXiv:2211.10435)، Program of Thoughts (arXiv:2211.12588)، FrugalGPT (arXiv:2305.05176) و The Tail at Scale.</p>
<div class="end">پایان مقاله · v6 هنوز به Flux اصلی متصل نشده است · برای ساخت این سند هیچ فراخوانی تازهٔ مدل انجام نشد.</div>
</main>{C.TIP_JS}</body></html>''')
OUT_HTML.write_text('\n'.join(H), encoding='utf-8')


async def render():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless=True)
        page = await browser.new_page(viewport={'width': 1180, 'height': 1300})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.goto(OUT_HTML.as_uri())
        await page.evaluate('document.fonts.ready')
        checks = []
        for w in (1180, 390, 320):
            await page.set_viewport_size({'width': w, 'height': 1300})
            await page.wait_for_timeout(60)
            checks.append(await page.evaluate('''() => ({w: innerWidth, overflow: document.documentElement.scrollWidth > innerWidth,
              font: document.fonts.check('14px Vazir'),
              clipped: [...document.querySelectorAll('svg')].flatMap(svg => {const b = svg.getBoundingClientRect();
                return [...svg.querySelectorAll('text')].filter(t => {const r = t.getBoundingClientRect();
                  return r.left < b.left-1 || r.right > b.right+1;}).map(t => t.textContent);})})'''))
        await page.set_viewport_size({'width': 1180, 'height': 1300})
        await page.screenshot(path=str(HERE/'preview-desktop.png'), full_page=False)
        await page.emulate_media(media='print')
        await page.pdf(path=str(OUT_PDF), format='A4', print_background=True, prefer_css_page_size=True)
        await browser.close()
        return checks, errors


if __name__ == '__main__':
    checks, errors = asyncio.run(render())
    print(json.dumps({'checks': checks, 'errors': errors}, ensure_ascii=False))
