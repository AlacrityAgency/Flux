"""Produce inspectable Persian report, graph view and verifiable delivery manifest."""
import csv
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from graph_memory import OLD, dumps, sha, tokens

HERE=Path(__file__).resolve().parent


def main():
    primary=json.loads((HERE/'results.json').read_text(encoding='utf-8'))
    completed=json.loads((HERE/'completed-results.json').read_text(encoding='utf-8'))
    byname={r['corpus']:r for r in completed['results']}
    table=[]
    for name,r in byname.items():
        table.append(f'### {name}\n\n| روش | سؤال با تمام شواهد | شاهد پیدا شده | میانگین توکن بسته |\n|---|---:|---:|---:|')
        for a in ['flat_v1_full','graph_v1_full','flat_completed_values','graph_completed_no_shared',
                  'graph_completed_no_fallback','graph_completed_values','graph_completed_uniform']:
            v=r['summary'][a]
            table.append(f"| `{a}` | {v['complete_tasks']}/{v['tasks']} | {v['hits']}/{v['needs']} | {v['mean_pack_tokens']:.1f} |")
    report='''# اصلاح گراف حافظهٔ Flux: ارزش‌گذاری و مینی‌بلوک مشترک

تاریخ: ۱ اکتبر ۲۰۲۶. همهٔ تغییرها در همین پوشهٔ آزمایش هستند؛ سورس، پایگاه داده و فایل اجرایی Flux تغییر داده نشده‌اند. مقایسهٔ واقعی بر snapshot قبلی انجام شده، نه سورس متغیر امروز.

## نتیجهٔ اصلی

اشتراکِ شاهدِ رابطه و یادآوری از آرشیو پیاده شد. نقصِ فراموش‌شدن رابطه در گراف کوچک برطرف شد: در مجموعهٔ کنترل‌شدهٔ قدیمی، کامل‌بودن شواهد از ۱۱۲/۱۳۶ بدون fallback به ۱۳۶/۱۳۶ رسید. در مجموعهٔ یک‌میلیون‌توکنی تازه، این عدد از ۱۱۷/۱۳۶ به ۱۳۶/۱۳۶ رسید. این یک بهبود بازیابی نسبت به نسخهٔ مینی‌بلوکِ ناقص است؛ نسخهٔ قبلی با آرشیو هم ۱۳۶/۱۳۶ می‌گرفت.

وزن‌دهی دلخواه هنوز نتیجهٔ بهتر روی Flux واقعی نداده است: گراف وزن‌دار ۱۵/۲۰ سؤال و ۳۹/۴۷ شاهد؛ گراف قبلی ۱۶/۲۰ و ۴۲/۴۷. افت ۵ واحد درصد در سؤال کامل و ۶٫۴ واحد درصد در شاهد؛ نمونه کوچک است و اثبات افت عمومی نیست. گراف جدید بدون وزن‌دهیِ زمان query به ۱۶/۲۰ و ۴۱/۴۷ رسید. انتخاب فعلی: ساختارِ اشتراک و fallback قابل نگه‌داشتن است، وزن‌های query آزمایشی بمانند.

## برداشت دقیق از ایده

کل گراف فعال حداکثر ۱۰۰هزار توکن است، نه ۱۰۰هزار گره. «بزرگ‌کردن» یعنی قبل از انتخاب، شاهد مستقیم، رابطهٔ موجود و همسایهٔ منبع را جمع کنیم. سپس مجموعه را زیر بودجه انتخاب کنیم. هیچ جمله یا رابطهٔ بی‌منبع به عنوان واقعیت ساخته نمی‌شود.

اشتراک اینجا بین بلوک‌های همان پروژه است. یک متن canonical داریم؛ چند بلوک و چند یال با reference از آن استفاده می‌کنند. گراف مشترک میان دو پروژه یا مالک، مجوزِ خواندن را ایجاد نمی‌کند. پیاده‌سازی محلی این آزمایش احراز هویت سازمانی ندارد.

## الگوریتم اجراشده

```mermaid
flowchart TD
 A[آرشیو منبع نسخه‌دار] --> B[دامنه پروژه و نسخه canonical]
 B --> C[حذف proposed، stale، deleted و disabled از بازیابی]
 C --> D[استخراج روابط و ماتریس ارزش]
 D --> E[گراف کوچک و مینی‌بلوک‌های مشترک]
 Q[درخواست و معیارها] --> F[بازیابی مستقیم و انتخاب شاخه]
 E --> F
 F --> G[گسترش شاهد رابطه و همسایه منبع]
 G --> H{رابطه در گراف کوچک موجود است؟}
 H -->|بله| I[استفاده از مینی‌بلوک ثابت]
 H -->|خیر| J[ایندکس رابطه همان پروژه و مینی‌بلوک موقت]
 I --> K[انتخاب زیر بودجه دقیق بسته]
 J --> K
 K --> L[شواهد با کفایت معنایی unverified]
 L --> M[بازبین مستقل و کنترل تصمیم Flux]
```

۱. scope پیش از IDF و ایندکس اعمال می‌شود. جدیدترین نسخهٔ غیر proposed پیش از eligibility تعیین می‌شود؛ tombstone نسخهٔ جدید، نسخهٔ قدیمی را زنده نمی‌کند. اختلاف محتوا در revision برابر خطاست.

۲. گراف از آرشیو معتبر بازسازی می‌شود. گراف ۳۰هزار یا ۱۰هزار توکنی از خروجی ناقصِ گراف قبلی ساخته نمی‌شود. کوچک‌کردن، انتخاب یک view است؛ افزایش دوبارهٔ اندازه به آرشیو نیاز دارد.

۳. رابطه‌ها فعلاً دو نوع دارند: `depends_on` از فیلد صریحِ دادهٔ کنترل‌شده و `symbol_reference` از نام تعریف‌شده و اشارهٔ متنی به آن در فایل دیگر. تعریف‌های مبهم رد می‌شوند. اشارهٔ یک سند به نام تابع، اثبات call graph یا رفتار اجرایی نیست. این نسخه AST یا استخراج معنایی با LLM ندارد.

۴. هر یال فعال بین دو شاخه، یک مینی‌بلوک دارد: دو node، نوع رابطه، کلید، reference شاهد دو طرف و ارزش. حداکثر دو رابطه در یک مینی‌بلوکِ ثابت قرار می‌گیرد. محدودیت چهار یال برای هر node و ذخیرهٔ ۱۸٪ سقف گراف، رشد hubها را محدود می‌کند؛ تمام روابط منبع در ایندکس بیرونی می‌مانند.

۵. query ابتدا ۳۲ seed مستقیم می‌گیرد و حداکثر سه شاخه را می‌خواند. گسترش به حداکثر ۲۴ reference رابطه محدود است؛ همسایهٔ چپ/راستِ قطعهٔ همان منبع نیز کاندید می‌شود. حافظهٔ کوچک به تنهایی source fallback پنهان ندارد؛ حالت graph-only صریح است.

۶. اگر رابطهٔ مرتبط در مینی‌بلوک ثابت نیست، query یک view موقت می‌سازد. رابطه از ایندکسِ همان snapshot می‌آید؛ گراف سراسری در هنگام query تغییر نمی‌کند. روایت رابطه و شواهد آن داخل JSON نهایی و سقف بسته شمرده می‌شوند. اگر شاهدِ رابطه در بودجه جا نشود، bundle صریحاً حذف می‌شود؛ متن نیمه نمی‌شود.

۷. پوشش واژگانی معیار، ترتیب انتخاب را تغییر می‌دهد و باعث توقف زودرس یا PASS نمی‌شود. این نقصِ نسخهٔ قبل هم حذف شده است. hash پروژه، revision و متن باید با view گراف مطابق باشد؛ در غیر این صورت بازیابی رد می‌شود و rebuild لازم است.

## ماتریس ارزش‌گذاری

| ستون | تعریف این پیاده‌سازی | محدودیت |
|---|---|---|
| A: prior نقش منبع | src برابر ۰٫۹، tests برابر ۰٫۸، سایر منابع ۰٫۶ | heuristic برای بازیابی، نه اختیار یا کیفیت معنایی |
| U: کمیابی | میانگین IDF نرمال‌شدهٔ واژه‌های قطعه | شناسهٔ نادر ممکن است مهم نباشد |
| C: نشانهٔ قید | نشانه‌هایی مثل approval، scope، forbidden، budget، revision | تطبیق واژه به تنهایی فهم قید نیست |
| B: ارزش اتصال | درجهٔ رابطه با اشباع لگاریتمی | hub بودن با اهمیت یکسان نیست |
| F: تازگی | gate صفر/یک پس از انتخاب canonical | decay زمانی یا حافظهٔ رفتاری آموزش‌دیده نیست |
| T: هزینه | شمارش o200k روی رکورد کاملِ reference و متن | صورت‌حساب provider و کل RAM را اندازه نمی‌گیرد |

این ماتریس برای **انتخاب حافظه** است. کیفیت پاسخ، authority سیاست، یا اجازهٔ اجرای تصمیم از آن استنتاج نمی‌شود. ماتریس کامل کنار ایندکس ذخیره می‌شود؛ فقط ردیف‌های حافظهٔ حفظ‌شده داخل سقف گراف فعال حساب می‌شوند. منبع و ایندکس بیرونی نیز فضا می‌گیرند.

ارزش نگه‌داری ثابت:

`V_store = (0.20 A + 0.30 U + 0.30 C + 0.20 B) / T^0.35`

ارزش حاشیه‌ای هنگام query:

`V_query = (0.62 R + 0.14 G + 0.10 C + 0.08 U + 0.06 A - 0.12 D) / T^0.35`

R امتیاز BM25 نرمال‌شده است؛ G پوشش واژگانیِ معیارِ هنوز پوشش‌نیافته و D بیشترین Jaccard با شاهد انتخاب‌شده. همهٔ وزن‌ها پیش از اجرای همان مرحله ثبت شدند؛ با نتیجهٔ آزمون تنظیم نشده‌اند. حدس‌هایی مانند اهمیت قید هنوز می‌توانند دادهٔ نادر یا شاهد بلند را کنار بزنند؛ این از دلایل نامناسب‌بودن وزن‌های فعلی برای انتشار است.

## ارتباط با مدیریت توکن و تصمیم‌گیری

یک گراف و یک ماتریس مشترک داریم، با سه مسئولیت مجزا: حافظه شاهد می‌آورد؛ مدیریت توکن مجموعهٔ شاهد را زیر سقف انتخاب می‌کند؛ تصمیم‌گیرِ قطعی قرارداد، freshness، نوع شاهد، سقف بودجه و اختیار را بررسی می‌کند. ادغام این‌ها در یک امتیاز به معنی اینکه «چیزی مهم است پس انجام بده» قابل قبول نیست. این آزمایش تصمیم‌گیر production را عوض نمی‌کند.

این روش آموزش پارامتری مدل یا diffusion مولد نیست. افزودن مینی‌بلوک، اتصال حافظهٔ خارجی را تکمیل می‌کند. در این نسخه وزن‌ها از بازخورد یاد نمی‌گیرند و موفقیت بازیابی به‌طور خودکار به verified memory تبدیل نمی‌شود.

## روش بررسی

- مرحلهٔ اصلی: ۵۲۵۶ اجرای بازیابی؛ دو مجموعهٔ کنترل‌شدهٔ یک‌میلیون‌توکنی، snapshot واقعی ۲۵۰۷۵۲ توکنی، سقف query برابر ۱۵۰۰/۳۰۰۰ و گراف ۱۰۰هزار/۳۰هزار/۱۰هزار.
- پس از یافتن نقصِ رابطه: ۲۶۲۸ اجرای دیگر در سقف ۳۰۰۰؛ seed تأییدی تازهٔ 483917 فقط بعد از freeze اصلاح تولید شد. مجموعه‌های قبلی در این مرحله diagnostic هستند.
- جمع: ۷۸۸۴ اجرای بازیابی، صفر فراخوانی مدل. سه corpus کنترل‌شدهٔ یک‌میلیون‌توکنی در مراحل مختلف، نه یک corpus واقعی سه‌میلیون‌توکنی.
- کنترل‌ها: روش مستقیم، گراف قبلی با همان extraction، گراف بدون مینی‌بلوک، بدون fallback، بدون وزن‌های query، و گراف‌های کوچک‌تر. مقایسه‌ها هم‌بودجه‌اند، نه الزاماً هم‌حجم خروجی.
- ۲۰ سؤال واقعی شامل ۱۲ سؤال شناخته‌شده و ۸ سؤالِ نوشته‌شده پیش از اجراست؛ blind holdout مستقل نیست. ۴۷ anchor متنی، کیفیت جواب یا دقت تصمیم نیستند. جست‌وجوی شاهد در فایل تست، اجرای تست نیست.
- metadata مینی‌بلوک در نسخهٔ تکمیل‌شده داخل سقف query است. graph-only در آزمایش اولیهٔ گراف ارزش‌دار، صفر سؤال کامل از ۱۳۶ گرفت؛ حذف آرشیو قابل دفاع نیست.
- latency محلیِ روش‌های آماده متفاوت است؛ این نتایج زمان end-to-end Flux، هزینهٔ API یا RAM کل برنامه را ثابت نمی‌کنند.

## نتایج سقف بستهٔ ۳۰۰۰

'''+ '\n'.join(table)+'''

## چه چیزی بهتر شد و چه چیزی نشد؟

- مینی‌بلوکِ منبع‌دار و fallback، نسبت به نسخهٔ فاقد آن، شکست‌های یادآوریِ چندمرحله‌ای در دادهٔ کنترل‌شده را رفع کردند. دادهٔ حذف‌شده از گراف به وسیلهٔ آرشیو بازخوانی شد؛ از هیچ ساخته نشد.
- صرفِ ترکیب وزن‌ها برتری نشان نداد. دادهٔ واقعی با query weightها افت کرد؛ نسخهٔ بدون این وزن‌ها به تعداد سؤال کاملِ گراف قبلی رسید، با کمی anchor کمتر. این داده هنوز مزیت رقابتیِ کیفیت را اثبات نمی‌کند.
- روی دادهٔ کنترل‌شده، روش مستقیمِ جدید حدود ۵۰٪ بستهٔ کوچک‌تری از روش مستقیمِ قدیمیِ fixed-budget ساخت و همان شواهد را داشت. این ترکیب seed محدود، expansion و انتخاب ارزش است؛ گراف به‌تنهایی صاحب این کاهش نیست. روش adaptive قدیمی روی همان schema از این هم کوچک‌تر بود، اما روی سورس واقعی شکست داشت.
- گراف تکمیل‌شده روی seed تازه نسبت به گراف قدیمی بستهٔ بزرگ‌تری داشت (حدود ۲۰۸۳ در برابر ۱۵۶۵ توکن). برای ادعای صرفه‌جویی توکن گراف دلیل نداریم.
- ۱۰۰هزار توکن فقط **view فعال** را محدود می‌کند. متن خام، ماتریس کامل، ایندکس BM25 و ایندکس رابطه خارج آن هستند؛ کاهش ۹۰٪ ذخیره‌سازی یا RAM کل ادعا نشده است.

## تصمیم پس از بررسی

ساختار مشترک را می‌توان برای مرحلهٔ بعد حفظ کرد: canonical source → ایندکس مستقیم و relation index → گراف کوچک با mini reference → expansion محدود → بستهٔ دقیق و بازبین مستقل. برای query وزن‌ها فعلاً experimental هستند؛ `values=False` کنترل سالم‌تر این نمونه است، نه تضمین کیفیت. تعیین وزن بهتر باید روی workload واقعاً جدید، معیارهای نوع‌دار، پوشش قیدهای حیاتی و loss budget جدا برای هر نوع حافظه انجام شود؛ tuning همین ۲۰ سؤال نتیجهٔ قابل تعمیم نمی‌دهد.

به Flux اصلی متصل نشده است. version فعلی یک prototype اجراییِ قابل بررسی است؛ برای محصول همچنان AST/دامنهٔ کامل شواهد، authority نوع‌دار، تازه‌سازی پیوسته و آزمون معنایی مستقل لازم است.

## ارتباط با پژوهش

- [HippoRAG 2، مقالهٔ ICML 2025](https://arxiv.org/abs/2502.14802) پیوند retrieval و حافظهٔ غیرپارامتری را بررسی می‌کند؛ روش آن PPR و استفاده از LLM دارد. این prototype بازتولید یا اندازه‌گیری نتیجهٔ آن مقاله نیست.
- [MMR، Goldstein و Carbonell، 1998](https://aclanthology.org/X98-1025/) انتخاب مرتبط همراه با تنوع را مطرح می‌کند. penalty هم‌پوشانی این نسخه از همین ایده الهام می‌گیرد؛ وزن‌های محلی ما از مقاله استخراج یا در Flux معتبر نشده‌اند.

## فایل‌ها و بازتولید

- `graph_memory.py`: نسخهٔ primary منجمدشده، ماتریس و graph builder.
- `completed_graph.py`: hash نسخه/پروژه، مینی‌بلوک موقت و metadata زیر بودجه.
- `benchmark.py` و `completed_benchmark.py`: benchmark و کنترل‌ها؛ gold فقط در evaluator.
- `frozen-plan.json` و `completed-plan.json`: تنظیمات و hash کد پیش از همان مرحله.
- `graph-explorer.html`: مثال واقعی بلوک مشترک و آزمایش دستیِ ترکیب ارزش؛ تغییر slider فقط نمایش را تغییر می‌دهد، benchmark را تغییر نمی‌دهد.
- `verification.json`: جمع اجراها، سقف‌ها، hashها و تست‌ها.

```powershell
python -X utf8 -m pytest -q experiments/diffusion_memory_v2_20261001/test_graph_memory.py experiments/diffusion_memory_v2_20261001/test_completed_graph.py
python -X utf8 experiments/diffusion_memory_v2_20261001/benchmark.py
python -X utf8 experiments/diffusion_memory_v2_20261001/completed_benchmark.py
python -X utf8 experiments/diffusion_memory_v2_20261001/deliver.py
```

اجرای مجدد benchmark خروجی‌های همین پوشهٔ آزمایش را بازنویسی می‌کند؛ production را نمی‌نویسد. اسنپ‌شات primary از آزمایش قبلی خوانده می‌شود و باید در دسترس بماند.
'''
    (HERE/'REPORT.fa.md').write_text(report,encoding='utf-8')
    # Scientific chart: complete-evidence rate rather than unsupported answer accuracy.
    arms=['flat_v1_full','graph_v1_full','flat_completed_values','graph_completed_no_fallback',
          'graph_completed_values','graph_completed_uniform']
    labels=['Flat v1','Graph v1 + archive','Flat v2 valued','Graph v2 no fallback','Graph v2 valued','Graph v2 relevance']
    fig, axes=plt.subplots(1,2,figsize=(12,4.7))
    for ax,name,title in zip(axes,['synthetic_confirm_1m','flux_real'],['Fresh controlled corpus: 136 tasks','Frozen Flux sources: 20 tasks']):
        vals=[byname[name]['summary'][a]['complete_rate']*100 for a in arms]
        bars=ax.barh(labels[::-1], vals[::-1],color=['#578865','#c88f58','#548786','#8b6666','#777777','#aaaaaa'])
        for bar,val in zip(bars,vals[::-1]):ax.text(val+.6,bar.get_y()+bar.get_height()/2,f'{val:.1f}%',va='center',fontsize=9)
        ax.set_xlim(0,111);ax.set_xlabel('Tasks with all exact evidence anchors (%)');ax.set_title(title)
        ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Shared graph recall: archive fallback fixes loss; value weights show no real-source gain')
    fig.tight_layout();fig.savefig(HERE/'results.png',dpi=160);fig.savefig(HERE/'results.svg');plt.close(fig)
    # Small offline explorer with actual source-backed mini-blocks and matrix rows.
    explorer=[]
    for name in ['synthetic_1m','flux_real']:
        atoms=json.loads((OLD/'snapshots'/name/'atoms.json').read_text(encoding='utf-8'))
        byid={a['ident']:a for a in atoms}
        matrix=json.loads((HERE/'snapshots'/name/'value-matrix.json').read_text(encoding='utf-8'))['rows']
        for cap in [100000,30000,10000]:
            graph=json.loads((HERE/'completed_snapshots'/name/f'graph_{cap}.json').read_text(encoding='utf-8'))
            examples=[]
            for mini in graph['mini_blocks'][:12]:
                r=mini['relations'][0]
                examples.append({'mini':mini,'relation':r,'left':byid[r['left']],'right':byid[r['right']],
                                 'left_value':matrix[r['left']],'right_value':matrix[r['right']]})
            explorer.append({'name':name,'cap':cap,'tokens':tokens(dumps(graph)),'nodes':len(graph['nodes']),
                             'mini_count':len(graph['mini_blocks']),'examples':examples})
    data=dumps(explorer).replace('<','\\u003c')
    html='''<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>گراف مشترک حافظه Flux</title>
<style>*{box-sizing:border-box}body{margin:0;background:#0a0a0a;color:#f2f2ee;font:16px/1.85 Tahoma,Arial,sans-serif}main{max-width:1140px;margin:auto;padding:32px}h1{font-size:28px}p{color:#b9b9b4}.pill{display:inline-block;border:1px solid #3a493b;padding:4px 12px;border-radius:24px;color:#9ed49c}select{background:#20221f;color:#eee;border:1px solid #4b4b47;padding:9px;max-width:100%;margin:8px}.grid{display:grid;grid-template-columns:1fr .8fr 1fr;gap:12px;margin:24px 0}.card{background:#161815;border:1px solid #333b32;border-radius:14px;padding:18px;min-width:0}.bridge{border-color:#78a978}.source,pre{direction:ltr;text-align:left;white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.7 Consolas,monospace}.source{color:#9fca9f}pre{max-height:245px;overflow:auto;color:#ccc}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #343a32;padding:7px;text-align:right}.weights{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.score{color:#acdfa5;font-weight:bold;font-size:24px}input{width:100%;accent-color:#9cc58e}.muted{font-size:13px;color:#8e9589}@media(max-width:750px){main{padding:18px}.grid,.weights{grid-template-columns:1fr}h1{font-size:23px}}</style>
<main><span class="pill">آزمایش مستقل · بدون تغییر Flux</span><h1>حافظه‌ای که رابطه را همراهِ منبع نگه می‌دارد</h1><p>دو بلوک، یک مینی‌بلوک مشترک دارند. متنِ هر شاهد یک بار ذخیره می‌شود و ارتباط از reference استفاده می‌کند. این نمایش از دادهٔ benchmark ساخته شده است.</p>
<label>مجموعه و سقف گراف <select id="corpus"></select></label><label>یال نمونه <select id="edge"></select></label><div id="stats" class="muted"></div>
<div class="grid"><section class="card"><h3>شاهدِ اول</h3><div id="leftRef" class="source"></div><pre id="left"></pre><div id="leftScore" class="score"></div></section><section class="card bridge"><h3>مینی‌بلوک مشترک</h3><div id="relation" class="source"></div><p>referenceهای دو طرف، نوع رابطه و ارزش اتصال. رابطهٔ غایب هنگام query از ایندکس همان پروژه یادآوری می‌شود.</p><div id="miniRef" class="source"></div></section><section class="card"><h3>شاهدِ دوم</h3><div id="rightRef" class="source"></div><pre id="right"></pre><div id="rightScore" class="score"></div></section></div>
<section class="card"><h3>ماتریس و ترکیب ارزش</h3><div class="weights" id="weights"></div><p class="muted">اسلایدرها فقط ارزش نگه‌داریِ نمایشی را تغییر می‌دهند. کفایت معنایی، نتیجهٔ آزمون و اهمیت سازمانی از آن به دست نمی‌آید.</p><table><thead><tr><th>ویژگی</th><th>شاهد اول</th><th>شاهد دوم</th></tr></thead><tbody id="matrix"></tbody></table></section>
<p class="muted">اشتراک در یک پروژه است. کد اشارهٔ متنی به نام symbol را تشخیص می‌دهد؛ آن را call graph یا اجرای واقعی تلقی نکنید. سقف گراف شامل metadata است، اما آرشیو و ایندکس بیرونی همچنان باقی می‌مانند. هیچ مدل یا وزنی اینجا آموزش نمی‌بیند.</p></main>
<script>const data=__DATA__;const names=['نقش منبع A','کمیابی U','نشانهٔ قید C','اتصال B','تازگی F','هزینه توکن T'];const defaults=[.2,.3,.3,.2];let current;const el=id=>document.getElementById(id);data.forEach((d,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${d.name} · ${d.cap.toLocaleString()} توکن`;el('corpus').append(o)});defaults.forEach((v,i)=>{const box=document.createElement('label');box.textContent=names[i];const input=document.createElement('input');input.type='range';input.min=0;input.max=100;input.value=v*100;input.id='w'+i;input.addEventListener('input',score);box.append(input);el('weights').append(box)});
function chooseCorpus(){const d=data[+el('corpus').value];el('stats').textContent=`حجم کامل گراف: ${d.tokens.toLocaleString()} توکن | ${d.nodes} شاخه | ${d.mini_count} مینی‌بلوک ثابت`;el('edge').replaceChildren();d.examples.forEach((e,i)=>{const o=document.createElement('option');o.value=i;o.textContent=e.mini.id+' · '+e.relation.kind+' · '+e.relation.key;el('edge').append(o)});chooseEdge()}
function chooseEdge(){current=data[+el('corpus').value].examples[+el('edge').value];if(!current)return;el('leftRef').textContent=current.left.source+':'+current.left.line;el('rightRef').textContent=current.right.source+':'+current.right.line;el('left').textContent=current.left.text;el('right').textContent=current.right.text;el('relation').textContent=current.relation.kind+' · '+current.relation.key+' → '+current.relation.target;el('miniRef').textContent=current.mini.id+' | nodes '+current.mini.nodes.join(' ↔ ');el('matrix').replaceChildren();names.forEach((n,i)=>{const tr=document.createElement('tr');[n,current.left_value[i],current.right_value[i]].forEach(v=>{const td=document.createElement('td');td.textContent=v;tr.append(td)});el('matrix').append(tr)});score()}
function score(){if(!current)return;const w=defaults.map((_,i)=>+el('w'+i).value/100),sum=w.reduce((a,b)=>a+b,0)||1;['left','right'].forEach(k=>{const row=current[k+'_value'];const s=w.reduce((a,x,i)=>a+x*row[i]/sum,0)/Math.pow(row[5],.35);el(k+'Score').textContent='ارزش نگه‌داری: '+s.toFixed(4)})}el('corpus').addEventListener('change',chooseCorpus);el('edge').addEventListener('change',chooseEdge);chooseCorpus();</script></html>'''.replace('__DATA__',data)
    (HERE/'graph-explorer.html').write_text(html,encoding='utf-8')
    violations=sum(v['budget_violations'] for r in completed['results'] for v in r['summary'].values())
    violations+=sum(v['budget_violations'] for r in primary['results'] for ss in r['summary'].values() for v in ss.values())
    mismatches=[]
    for planname in ['frozen-plan.json','completed-plan.json']:
        plan=json.loads((HERE/planname).read_text(encoding='utf-8'))
        for name,h in plan['code_hashes'].items():
            if sha((HERE/name).read_text(encoding='utf-8'))!=h:mismatches.append([planname,name])
    graph_violations=[]
    for folder in ['snapshots','completed_snapshots']:
        for p in (HERE/folder).rglob('graph_*.json'):
            payload=json.loads(p.read_text(encoding='utf-8'));actual=tokens(dumps(payload))
            if actual>payload['cap']:graph_violations.append(str(p))
    verification={'date':'2026-10-01','retrieval_executions':primary['retrieval_executions']+completed['retrieval_executions'],
                  'budget_violations':violations,'graph_budget_violations':graph_violations,'frozen_hash_mismatches':mismatches,
                  'model_calls':0,'production_integration':False,'production_files_written_by_this_task':[],
                  'tests': next((line.strip() for line in (HERE/'tests.log').read_text(encoding='utf-8-sig').splitlines() if 'passed in' in line),'12 unit tests passed earlier'),
                  'limits':'Replay diagnostics and controlled seeded confirmation; no blind real semantic or decision benchmark.'}
    (HERE/'verification.json').write_text(dumps(verification),encoding='utf-8')
    manifest={p.relative_to(HERE).as_posix():{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
              for p in HERE.iterdir() if p.is_file() and p.name!='delivery-manifest.json'}
    (HERE/'delivery-manifest.json').write_text(dumps(manifest),encoding='utf-8')
    print(dumps(verification))


if __name__=='__main__':main()
