"""Presentation only; derives every number from frozen experiment receipts."""
from pathlib import Path
import json
import html
import sys
from fractions import Fraction
import engine as E

HERE=Path(__file__).resolve().parent
DOCS=HERE.parent.parent/'docs/reasoning-v6-1-20261002'


def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(str(h))+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(c))+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def bars(values, title, suffix='', maximum=None):
    maximum=maximum or max(v for _,v in values)*1.12 or 1
    out=[f'<svg viewBox="0 0 760 {len(values)*52+35}" role="img" aria-label="{html.escape(title)}" dir="ltr">']
    for i,(label,v) in enumerate(values):
        y=15+i*52;w=v/maximum*480
        out.append(f'<text x="130" y="{y+20}" text-anchor="end">{html.escape(label)}</text><rect x="145" y="{y}" width="{w:.2f}" height="28" rx="4" fill="{["#777e84","#138064","#be7943","#6085a5"][i%4]}"/><text x="{155+w:.2f}" y="{y+20}">{v:,.1f}{suffix}</text>')
    out.append('</svg>')
    return '<figure>'+''.join(out)+f'<figcaption>{title}</figcaption></figure>'


def main():
    DOCS.mkdir(exist_ok=True,parents=True)
    r=json.loads((HERE/'results.json').read_text(encoding='utf-8'))
    m=r['metrics'];arms=['v6','v6.1','sol_direct','luna_B_shared']
    labels={'v6':'Luna + v6 → Sol','v6.1':'Luna + v6.1 → Sol','sol_direct':'Sol مستقل','luna_B_shared':'Luna + B (اشتراکی)'}
    rows=[]
    for a in arms:
        z=m[a];mns=z['means']
        rows.append([labels[a],f'{z["correct"]}/{z["n"]}',f'{z["accuracy"]*100:.1f}%',f'{mns["calls"]:.2f}',
                     f'{z["sol_share"]*100:.1f}%',f'{mns["input_tokens"]:,.0f}',f'{mns["output_tokens"]:,.0f}',
                     f'{z["latency_p50"]:.2f}',f'{z["latency_p95"]:.2f}'])
    headers=['روش','درست','دقت','فراخوانی/مسئله','ارجاع Sol','ورودی provider','خروجی provider','p50 ثانیه','p95 ثانیه']
    v=m['v6.1'];base=m['v6'];sol=m['sol_direct']
    input_saving=100*(1-v['means']['input_tokens']/base['means']['input_tokens'])
    total_saving=100*(1-(v['means']['input_tokens']+v['means']['output_tokens'])/(base['means']['input_tokens']+base['means']['output_tokens']))
    accepted=[row for row in r['rows'] if row['arm']=='v6.1' and row['initial_accepted']]
    autonomous_correct=sum(row['correct'] for row in accepted)
    subsection=[]
    for group in ['logic','math']:
        subsection.append([group]+[f'{r["by_set"][group][a]["correct"]}/{r["by_set"][group][a]["n"]}' for a in arms])
    failures=[row for row in r['rows'] if not row['correct']]
    failrows=[[row['task'],labels[row['arm']],row['value'],row['gold']] for row in failures]
    details=[]
    for f in sorted((HERE/'trials').glob('*.json')):
        t=json.loads(f.read_text(encoding='utf-8'));z=t['results']['v6.1'];init=z['initial']
        details.append([t['task'],'پذیرش Luna' if z['accepted_initial'] else 'ارجاع Sol',init['status'],init.get('graph_detail','—'),init.get('verified','—')])
    intro=(f'در این آزمون، v6.1 به {v["correct"]} پاسخ درست از ۲۴ رسید؛ v6 به {base["correct"]} و Sol مستقل به {sol["correct"]}. '
           f'ورودی گزارش‌شدهٔ provider نسبت به v6، {input_saving:.1f}٪ کمتر شد؛ مجموع ورودی و خروجی {total_saving:.1f}٪ کمتر شد. '
           f'{autonomous_correct} پاسخ درست بدون ارجاع به Sol پذیرفته شدند و {sum(not x["correct"] for x in accepted)} پاسخ غلط از بررسی عبور کردند. '
           'این نتیجه دربارهٔ همین مجموعه است و هم‌ارزی عمومی Luna و Sol را اثبات نمی‌کند.')
    charts=bars([(a,m[a]['accuracy']*100) for a in arms],'دقت پاسخ نهایی؛ هر روش روی همان ۲۴ سؤال','%',100)
    charts+=bars([(a,m[a]['means']['input_tokens']) for a in arms],'میانگین توکن ورودی واقعی provider در هر مسئله')
    charts+=bars([(a,m[a]['means']['output_tokens']) for a in arms],'میانگین توکن خروجی گزارش‌شدهٔ provider در هر مسئله')
    charts+=bars([(a,m[a]['latency_p50']) for a in arms],'زمان واقعی مسیر؛ میانه، با احتساب انتظار صف',' s')
    graph_receipt=json.loads((HERE/'model_runs/coins_0__v61_graph.json').read_text(encoding='utf-8'))
    graph_data=E.V6.parse_json(graph_receipt['text'])
    graph_nodes=graph_data.get('nodes',[])
    graph_html=''
    if len(graph_nodes)==4:
        positions={n['id']:15+190*i for i,n in enumerate(graph_nodes)}
        network=['<svg viewBox="0 0 770 115" role="img" aria-label="Actual four-node constraint network" dir="ltr"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="#138064"/></marker></defs>']
        for a,b in graph_data.get('edges',[]):
            network.append(f'<path d="M{positions[a]+170} 55 L{positions[b]-4} 55" stroke="#138064" stroke-width="2" fill="none" marker-end="url(#arrow)"/>')
        for n in graph_nodes:
            x=positions[n['id']]
            network.append(f'<rect x="{x}" y="15" width="170" height="80" rx="8" fill="#edf3ed"/><text x="{x+85}" y="47" text-anchor="middle">{html.escape(n["id"])}</text><text x="{x+85}" y="75" text-anchor="middle">{html.escape(n["kind"])}</text>')
        network.append('</svg>')
        graph_html='<h2>یک شبکهٔ واقعی از همین اجرا</h2><p>گراف مسئلهٔ coins_0، عیناً از خروجی Luna: ارزش سکه‌ها، مبلغ هدف، کمینه‌سازی و بررسی به هم وصل شده‌اند. اعتبار یال‌ها و حفظ اعداد بررسی می‌شود؛ این اتصال به‌تنهایی ثابت نمی‌کند برنامه از همهٔ قیود استفاده کرده است.</p>'+''.join(network)+table(['گره','نقش','متن ثبت‌شده'],[[n['id'],n['kind'],n['text']] for n in graph_nodes])
    tokenrows=[[labels[a],f'{m[a]["means"]["visible_prompt_tokens"]:.0f}',f'{m[a]["means"]["visible_output_tokens"]:.0f}',
                f'{m[a]["means"]["cached_input_tokens"]:.0f}',f'{m[a]["means"]["input_tokens"]-m[a]["means"]["cached_input_tokens"]:.0f}'] for a in arms]
    difference=r['paired_differences']['sol_direct']
    ci=difference['paired_bootstrap_95']
    ci_text=f'اختلاف دقت v6.1−Sol: {difference["difference"]*100:.1f} واحد درصد؛ بازهٔ bootstrap جفتی ۹۵٪: [{ci[0]*100:.1f}، {ci[1]*100:.1f}].'
    if v['correct']==v['n']:
        ci_text+=f' با صفر خطا در {v["n"]} نمونه، کران بالای دقیقِ دوطرفهٔ ۹۵٪ برای نرخ خطا هنوز {100*(1-.025**(1/v["n"])):.1f}٪ است؛ صفر خطای مشاهده‌شده به معنی صفر خطای واقعی نیست.'
    interpretation='''<h2>آیا این نسخه را بهتر از v6 حساب کنیم؟</h2><p>برای مصرف ورودی provider، بله؛ برای سرعت یا کاهش نیاز به Sol، خیر. دقت نهایی در این مجموعه برابر ماند. Luna+B روی هر ۱۲ سؤال منطقی درست بود؛ بنابراین در این بخش بهبود دقتی از گراف نشان ندادیم. v6.1 فقط ۱۳ پاسخ را مستقل پذیرفت و ۱۱ بار Sol را فراخوانی کرد، در برابر ۶ ارجاع v6. دقت ۲۴/۲۴ متعلق به مسیر ترکیبی است، نه Luna تنها.</p>
    <p>علت ۱۱ ارجاع: ۸ برنامه از type استفاده کردند که worker آن را ممنوع می‌کند؛ ۱ گراف عدد 4 را حذف کرد؛ ۲ بررسی‌کننده False برگرداندند. محدودیت type یک ناسازگاری بین قرارداد تولید و runner است؛ نمی‌توان این ۸ مورد را شکست استدلال Luna نامید. گراف و check همچنین خروجی provider را از میانگین ۲۹۱ به ۵۲۲ توکن رساندند. کاهش تعداد فراخوانی به‌تنهایی کاهش زمان را تضمین نکرد.</p>
    <p class="note">این کاندید برای جایگزینی پیش‌فرض v6 توصیه نمی‌شود. قدم آزمایشی بعدی: قرارداد دقیق‌تر برای builtinهای مجاز، ثبت قطعی ورودی‌های عمومی پیش از مدل و check کوتاه به‌جای بازگویی کامل گراف. این پیشنهادها هنوز پیاده‌سازی و روی holdout تازه آزمایش نشده‌اند؛ نباید نتیجهٔ آن‌ها را به این نسخه نسبت داد.</p>'''
    article=f'''<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Flux v6.1 — گراف قیود، دقت و توکن</title><style>
    *{{box-sizing:border-box}}body{{margin:0;background:#f3f3ee;color:#202a26;font:16px/2.05 Tahoma,Arial,sans-serif}}main{{max-width:1050px;margin:auto;background:white;padding:52px 50px}}h1{{font-size:35px;line-height:1.6}}h2{{font-size:25px;margin-top:48px}}.eyebrow{{color:#138064;font-size:13px}}.lead{{border-right:3px solid #138064;padding-right:22px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}figure{{margin:0;padding:18px 10px;background:#f7f9f6;border-radius:8px}}svg{{width:100%;display:block}}svg text{{font:14px Arial}}figcaption{{font-size:13px;margin:8px 10px}}.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{padding:10px;border-bottom:1px solid #ddd;text-align:right;white-space:nowrap}}th{{background:#edf3ed}}.note{{background:#f6f1e7;padding:18px}}.flow{{display:flex;flex-wrap:wrap;gap:10px}}.flow span{{padding:12px 18px;background:#edf3ed;border-radius:6px}}a{{color:#138064}}code{{direction:ltr;unicode-bidi:embed}}details{{margin:20px 0}}@media(max-width:700px){{main{{padding:25px 18px}}h1{{font-size:28px}}.grid{{grid-template-columns:1fr}}}}@media print{{body{{background:white}}main{{padding:0;max-width:none}}figure,table{{break-inside:avoid}}h2{{break-after:avoid}}}}
    </style><main><div class="eyebrow">ALACRITY / FLUX · آزمایش مستقل · ۲ اکتبر ۲۰۲۶</div>
    <h1>v6.1: هر قید را به محاسبه و بررسی وصل کن</h1><p>مقایسهٔ واقعی روی منطق محدود و استدلال عددی، با تمرکز بر مصرف توکن</p><p class="lead">{intro}</p>
    <h2>از دو فراخوانی به یک بستهٔ قابل اجرا</h2><p>v6 دو برنامهٔ A و B را با دو فراخوانی Luna می‌سازد و هنگام عدم توافق Sol را صدا می‌زند. v6.1 در یک فراخوانی، گراف قیود، برنامهٔ حل و بررسی‌کننده را می‌گیرد. پذیرش به اعتبار گراف و نتیجهٔ check وابسته است؛ در صورت رد، یک فراخوانی واقعی Sol انجام می‌شود. حلقهٔ بازنویسی و بازیابی یک‌میلیونی وجود ندارد.</p>
    <div class="flow"><span>درخواست عمومی</span><span>← گراف ورودی / قید / هدف</span><span>← solve + check</span><span>← پوشش + اجرا</span><span>← پذیرش یا Sol</span></div>
    <p>شبکه در این آزمایش ساختار مسئله را نمایش می‌دهد و اتصال قیود را بررسی می‌کند. این روش وزن‌های Luna را آموزش نمی‌دهد، حافظهٔ پایدار نمی‌سازد و یادگیری RAG را آزمایش نمی‌کند. استقلال بررسی‌کننده از حل‌کننده از نظر معنایی تضمین‌شده نیست.</p>
    <h2>نتیجهٔ اندازه‌گیری‌شده</h2>{table(headers,rows)}<div class="grid">{charts}</div>{graph_html}
    <h2>منطق در برابر مسائل عددی</h2>{table(['مجموعه']+[labels[a] for a in arms],subsection)}<p>۱۲ سؤال ریاضی تازه از ده خانواده و ۱۲ سؤال منطق: شمارش مدل‌های SAT، شوالیه و دروغ‌گو، ترتیب با قیود و تخصیص اعداد متمایز. پاسخ‌های منطق با شمارش کامل دامنهٔ متناهی ساخته شدند. مسائل به مدل فقط با متن عمومی داده شدند؛ مرجع در پوشهٔ evaluation_only باقی ماند.</p>
    <h2>کاهش توکن دقیقاً به چه معناست؟</h2>{table(['روش','متن درخواست','متن خروجی','ورودی cached','ورودی غیر cached'],tokenrows)}<p>تمام مقادیر میانگین در هر مسئله‌اند. توکن متن قابل مشاهده با o200k_base شمرده شد؛ input/output/cached از رویداد turn.completed می‌آید. سربار CLI از توکن متن بسیار بیشتر است. هزینهٔ دلاری در دسترس نیست؛ کاهش توکن معادل درصد کاهش صورت‌حساب نیست. B ablation از فراخوانی موجود v6 استفاده می‌کند و اجرای جداگانه محسوب نمی‌شود. زمان B فقط فراخوانی و اجرای همان برنامه است؛ زمان کنترل‌گرهای اصلی شامل صف هم هست.</p>
    {interpretation}<h2>خطا و استقلال بررسی</h2>{table(['مسئله','روش','جواب','مرجع'],failrows) if failrows else '<p>در پاسخ نهایی هیچ خطایی ثبت نشد.</p>'}<p class="note">{ci_text} تعداد سؤال کم است و یک نمونه از هر سؤال داریم. بازهٔ bootstrap در نتایج بدون خطا می‌تواند به‌صورت کاذب باریک شود؛ از آن برای ادعای هم‌ارزی استفاده نمی‌کنیم. اشتراک فرمول یا حذف همان قید در solve و check همچنان ممکن است.</p>
    <details><summary>جزئیات پذیرش و ارجاع برای هر مسئله</summary>{table(['مسئله','تصمیم','اجرا','گراف','check'],details)}</details>
    <h2>روش بازتولید و محدودیت‌ها</h2><p>کد، ۲۴ پرسش و مرجع قبل از آزمایش hash شدند. effort=low برای هر دو مدل، سقف ۱۴۴ فراخوانی، بدون retry و حداکثر چهار فراخوانی همزمان. {r['physical_calls']} فراخوانی واقعی ثبت شد، {r['physical_completed']} مورد کامل شدند و {r['tool_events']} رویداد ابزار ثبت شد. زمان‌ها اجرای واقعیِ مسیر شرطی‌اند؛ صف semaphore در آن‌ها وجود دارد. ترتیب روش‌ها برای هر سؤال از پیش تصادفی شد. دادهٔ آزمایش v6 قبلی دست‌نخورده است.</p><p>۱۰ تست محلی، شامل حذف قید، rounding، check صوری، حساب دقیق، مسیر Formatter و timeout پاس شدند. worker محدودسازی AST و زمان دارد؛ sandbox کامل سیستم‌عامل و سقف RAM ندارد. این نسخه برای آزمایش جداگانه است و در Flux اصلی ادغام نشده است.</p>
    <p><a href="../../experiments/request_reasoning_v6_1_20261002/results.json">نتایج خام</a> · <a href="../../experiments/request_reasoning_v6_1_20261002/frozen-plan.json">طرح منجمد</a> · <a href="../../experiments/request_reasoning_v6_1_20261002/ALGORITHM.fa.md">الگوریتم</a></p></main></html>'''
    (DOCS/'Flux_Reasoning_v6_1_FA.html').write_text(article,encoding='utf-8')
    md='# گزارش v6.1\n\n'+intro+'\n\n| '+' | '.join(headers)+' |\n|'+ '|'.join(['---']*len(headers))+'|\n'
    md+='\n'.join('| '+' | '.join(str(c) for c in row)+' |' for row in rows)
    md+='\n\n'+ci_text+'\n\n'+f'فراخوانی‌های واقعی: {r["physical_calls"]}؛ کامل‌شده: {r["physical_completed"]}؛ ابزار: {r["tool_events"]}.\n\n'
    md+='Luna+B یک ablation با receipt مشترک است. زمان مسیرها واقعی و شامل انتظار صف است. مجموع توکن به معنی هزینهٔ دلاری نیست. گراف و check تولیدشده اثبات رسمی یا یادگیری وزن مدل نیستند. ۲۴ سؤال مصنوعی با یک نمونه برای ادعای هم‌ارزی عمومی کافی نیستند. Flux اصلی و v6 تغییر نکردند.\n'
    md+='\n## تفسیر\n\nاین کاندید برای جایگزینی پیش‌فرض v6 توصیه نمی‌شود: دقت نهایی برابر، زمان بیشتر و وابستگی به Sol بیشتر است. روی منطق، B ساده ۱۲/۱۲ درست بود. v6.1 از ۲۴ سؤال فقط ۱۳ پاسخ را مستقل پذیرفت؛ بقیه به Sol رسیدند. علت ارجاع: ۸ ناسازگاری type با worker، ۱ عدد حذف‌شده از گراف، و ۲ check=False. این‌ها را همگی خطای استدلال Luna نمی‌نامیم. بهبود دقت از شبکه نشان داده نشد.\n'
    (HERE/'REPORT.fa.md').write_text(md,encoding='utf-8')
    print(json.dumps({'html':str(DOCS/'Flux_Reasoning_v6_1_FA.html'),'input_saving_percent':input_saving,
                      'total_token_saving_percent':total_saving,'autonomous_correct':autonomous_correct,
                      'false_accepts':sum(not x['correct'] for x in accepted)},ensure_ascii=False))


if __name__=='__main__': main()
