"""Build a standalone Persian visual history from immutable experiment receipts."""
import base64
from html import escape
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
EXP=ROOT/'experiments'
OUT=HERE/'Flux_Memory_Research_FA.html'
LIVE=EXP/'luna_v4_v5_live_20261002'
V5=EXP/'request_memory_v5_20261002'
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
live=load(LIVE/'results.json');offline=load(V5/'runs/final/holdout-results.json')
old4=load(EXP/'request_memory_v4_20261002/holdout-results.json')
old3=load(EXP/'request_memory_v3_20261002/results.json')
reg=load(V5/'regression-results.json')
manifest=load(V5/'runs/final/frozen-manifest.json')
assert all(hashlib.sha256((EXP/p).read_bytes()).hexdigest()==h for p,h in manifest['sha256'].items())
assert live['runtime_hashes_unchanged'] and live['actual_calls']==54

font_css=re.search(r'@font-face.*?}',(ROOT/'docs/Flux_Whitepaper_FA.html').read_text(encoding='utf-8'),re.S)[0]
def e(value):return escape(str(value))
def fa(value):return str(value).translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹'))
def number(value,digits=1):return fa(f'{value:,.{digits}f}')
def badge(text,kind='neutral'):return f'<span class="badge {kind}">{e(text)}</span>'
def note(text,kind=''):return f'<div class="note {kind}">{text}</div>'
def table(headers,rows,cls=''):
    return '<div class="table-wrap"><table class="'+cls+'"><thead><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def flow(items):
    return '<div class="flow">'+''.join(f'<div class="step"><b>{fa(i+1)}</b><strong>{a}</strong><span>{b}</span></div>' for i,(a,b) in enumerate(items))+'</div>'
def svg_start(title,width,height):
    return f'<svg role="img" aria-label="{e(title)}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg"><title>{e(title)}</title>'
def bars(title,rows,unit,max_value=None,digits=0,width=680,height=None):
    # rows: label,value,semantic color. Original observations drive the domain.
    height=height or 58+len(rows)*45
    left=180 if width>500 else 110;right=82;fw=width-left-right;maximum=max_value or max(v for _,v,_ in rows)*1.08
    chunks=[svg_start(title,width,height)]
    for i,(label,value,color) in enumerate(rows):
        y=18+i*45;w=fw*value/maximum
        chunks += [f'<text x="{left-15}" y="{y+22}" text-anchor="end" class="svg-label">{e(label)}</text>',
                   f'<rect x="{left}" y="{y}" width="{fw}" height="29" rx="4" fill="#eeeeea"/>',
                   f'<rect x="{left}" y="{y}" width="{w}" height="29" rx="4" fill="{color}"/>',
                   f'<text x="{left+w+9}" y="{y+22}" class="svg-value">{e(number(value,digits))}</text>']
    y=height-25
    chunks += [f'<line x1="{left}" y1="{y-10}" x2="{left+fw}" y2="{y-10}" stroke="#bbbbaf"/>',
               f'<text x="{left}" y="{y+12}" class="svg-small">۰</text>',
               f'<text x="{left+fw/2}" y="{y+12}" text-anchor="middle" class="svg-small">{e(unit)}</text>',
               f'<text x="{left+fw}" y="{y+12}" text-anchor="end" class="svg-small">{e(number(maximum,digits))}</text>','</svg>']
    return '<figure><figcaption>'+title+'</figcaption>'+''.join(chunks)+'</figure>'

GREEN='#17835c';DARK='#262a28';ORANGE='#bb7335';GRAY='#818782';RED='#a94844'

def grouped(title,categories,sets,denominators):
    width=680;height=265;left=64;top=25;bottom=190;fw=width-left-20;group=fw/len(categories)
    parts=[svg_start(title,width,height)]
    for tick in (0,.5,1):
        y=bottom-(bottom-top)*tick
        parts += [f'<line x1="{left}" y1="{y}" x2="{width-20}" y2="{y}" stroke="#deded4"/>',f'<text x="{left-8}" y="{y+5}" text-anchor="end" class="svg-small">{fa(int(tick*100))}٪</text>']
    for i,label in enumerate(categories):
        center=left+group*(i+.5)
        for j,(name,values,color) in enumerate(sets):
            val=values[i];fraction=val/denominators[i];h=(bottom-top)*fraction;x=center-44+j*45
            parts += [f'<rect x="{x}" y="{bottom-h}" width="35" height="{h}" rx="3" fill="{color}"/>',f'<text x="{x+17.5}" y="{bottom-h-7}" text-anchor="middle" class="svg-small">{fa(val)}/{fa(denominators[i])}</text>']
        parts.append(f'<text x="{center}" y="{bottom+25}" text-anchor="middle" class="svg-label">{e(label)}</text>')
    for j,(name,_,color) in enumerate(sets):
        x=190+j*150;parts += [f'<rect x="{x}" y="241" width="15" height="10" fill="{color}"/>',f'<text x="{x+23}" y="252" class="svg-small">{e(name)}</text>']
    parts.append('</svg>')
    return '<figure><figcaption>'+title+'</figcaption>'+''.join(parts)+'</figure>'

def diagram(title,nodes,edges,width=680,height=270):
    # node=(id,x,y,w,h,title,subtitle,color); visible labels are document data.
    parts=[svg_start(title,width,height),'<defs><marker id="arrow-'+str(len(pages))+'" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="none" stroke="#87948b" stroke-width="1.2"/></marker></defs>']
    lookup={n[0]:n for n in nodes}
    for a,b in edges:
        n,m=lookup[a],lookup[b];x1,y1=n[1]+n[3]/2,n[2]+n[4];x2,y2=m[1]+m[3]/2,m[2]
        if y2<y1:x1,y1=n[1]+n[3],n[2]+n[4]/2;x2,y2=m[1],m[2]+m[4]/2
        parts.append(f'<path d="M{x1} {y1} C{x1} {(y1+y2)/2},{x2} {(y1+y2)/2},{x2} {y2}" fill="none" stroke="#87948b" stroke-width="1.5" marker-end="url(#arrow-{len(pages)})"/>')
    for _,x,y,w,h,label,sub,color in nodes:
        parts += [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{color}"/>',
                  f'<text x="{x+w/2}" y="{y+25}" text-anchor="middle" class="svg-label">{e(label)}</text>',
                  f'<text x="{x+w/2}" y="{y+46}" text-anchor="middle" class="svg-small">{e(sub)}</text>']
    parts.append('</svg>')
    return '<figure><figcaption>'+title+'</figcaption>'+''.join(parts)+'</figure>'

pages=[]
def page(key,kicker,title,body):
    pages.append({'id':key,'kicker':kicker,'title':title,'body':body})

def stat(label,value,detail):return f'<div class="stat"><span>{label}</span><b>{value}</b><small>{detail}</small></div>'

a,b=live['summary']['v5'],live['summary']['v4'];oa,ob=offline['summary']['v5'],offline['summary']['v4']

page('overview','گزارش فنی و تصویری · ۲ اکتبر ۲۰۲۶','از ایدهٔ حافظهٔ فشرده تا v5 آزمایش‌شده',
    '<div class="cover-brand">ALACRITY <span>/</span> FLUX</div>'
    + '<p class="lead">هدف این مسیر، بهتر کردن دسترسی Luna به دانش پروژه، انتخاب شواهد زیر بودجه و جلوگیری از تأیید بی‌پشتوانه بود. پنج نسل الگوریتم را طراحی و آزمایش کردیم و در پایان v4 و v5 را با خود Luna روی ۲۰ سؤال مشترک اجرا کردیم.</p>'
    + '<div class="stats">'+stat('پاسخ درست نهایی Luna + v5','۱۶ / ۲۰','v4: ۱۰ / ۲۰')+stat('میانگین زمان هر سؤال','۶٫۹۳ s','v4: ۹٫۸۶ s')+stat('تماس واقعی Luna','۵۴','۲۲ برای v5؛ ۳۲ برای v4')+'</div>'
    + bars('اجرای واقعی آخر: پاسخ درست روی ۲۰ سؤال',[('Luna + v5',16,GREEN),('Luna + v4',10,DARK)],'تعداد پاسخ درست',20)
    + flow([('حافظه','شاهد مرتبط و نسخهٔ معتبر'),('توکن','بستهٔ کامل زیر سقف'),('تصمیم','نوع بررسی، repair یا توقف')])
    + note('نتیجهٔ معتبر این pilot: حافظه و کنترل repair بهتر شدند. هم‌سطح شدن توان استدلال Luna با Sol ثابت نشده است.','strong')
    + '<p class="source">وضعیت محصول: تمام کار در پوشه‌های آزمایش مستقل باقی مانده؛ این الگوریتم‌ها به production Flux اضافه نشده‌اند. [S7, S8]</p>')

page('hypothesis','ایدهٔ اولیه و اولین مشاهده','یک میلیون توکن؛ گرافی زیر صد هزار توکن',
    '<p>ایدهٔ شما این بود که منابع را بزرگ و کامل جمع کنیم، سپس با ارزش‌گذاری و ترکیب ارزش، آن‌ها را بلوک‌بندی و فشرده کنیم؛ بلوک‌های مشترک بین یال‌ها نیز نقش یادآوری داشته باشند. «صد هزار» حجم کل گراف بود، نه تعداد گره.</p>'
    + flow([('منبع ۱M','۱۰۰ بلوک خامِ ۱۰هزار‌توکنی'),('گراف ≤۱۰۰k','نمای مشتق‌شده، همراه reference'),('بستهٔ درخواست','فقط شواهد مرتبط برای مدل')])
    + bars('v1: اندازهٔ واقعی نمایش گراف در چهار سطح',[('سقف ۱۰۰k',92134,GREEN),('سقف ۳۰k',27449,DARK),('سقف ۱۰k',9071,GRAY),('سقف ۳k',2728,ORANGE)],'توکن کل JSON گراف',100000)
    + table(['سطح گراف','شواهد باقی‌مانده','سؤال کامل فقط از گراف'],[['۹۲٬۱۳۴ توکن','۳۰۰۰ از ۱۱٬۳۱۲','۳۴ / ۱۳۶'],['۲۷٬۴۴۹ توکن','۸۷۰ از ۱۱٬۳۱۲','۹ / ۱۳۶'],['۹٬۰۷۱ توکن','۲۹۰ از ۱۱٬۳۱۲','۴ / ۱۳۶'],['۲٬۷۲۸ توکن','۸۷ از ۱۱٬۳۱۲','۰ / ۱۳۶']])
    + note('نتیجه: کوچک شدن گراف، حفظ همهٔ اطلاعات نبود. منبع اصلی باید بماند؛ جبران اطلاعات حذف‌شده از آرشیو بیرونی انجام می‌شود، نه از «فهم» یا آموزش پنهان مدل.')
    + '<p class="source">مقیاس ۱M روی دادهٔ مصنوعی بود. snapshot واقعی Flux: ۱۱۷ فایل و ۲۵۰٬۷۵۲ توکن. diffusion در v1 یک random walk با ۲۴ گام بود، نه مدل diffusion مولد. [S1]</p>')

versions=[('v1','graph + diffusion','یادگیری: آرشیو را حذف نکنیم','۴۷۶۰ اجرای retrieval؛ صفر تماس مدل در مرحلهٔ اولیه'),
          ('v2','value + shared blocks','یادگیری: وزن دلخواه تضمین بهبود نیست','۷۸۸۴ اجرای retrieval؛ صفر تماس مدل'),
          ('v3','request RAG + E5','یادگیری: pruning حجم را کم کرد، استدلال را نه','۱۴۴ تماس واقعی در آزمایش تاریخی'),
          ('v4','snapshot + one pass','یادگیری: سرعت خوب، verifier ناقص','۱۵۶ سؤال offline؛ اجرای مدل در pilot بعدی'),
          ('v5','typed proof + ledger','یادگیری: نوع شاهد و repair اهمیت دارند','۵۰ تست؛ ۲۴۰ offline؛ سپس ۲۲ تماس Luna')]
page('versions','تکامل طراحی','پنج نسخه؛ پنج تصمیم قابل‌ردیابی',
    '<div class="timeline">'+''.join(f'<div><span>{v}</span><strong>{title}</strong><p>{learn}</p><small>{status}</small></div>' for v,title,learn,status in versions)+'</div>'
    + table(['نسخه','حافظه / گراف','توکن / تصمیم'],[['v1','خلاصهٔ extractive، شباهت واژگانی، archive fallback','rank و بازیابی گراف'],['v2','ماتریس ارزش و reference مشترک','ارزش / هزینه؛ شاهد رابطه'],['v3','RAG مخصوص درخواست، embedding واقعی E5، note و bridge','fixed-1M یا adaptive؛ planner/critic دسته‌ای؛ prune'],['v4','index مشترک، lexical، scope با regex، یک hop','یک گذر، router دوحالته، verifier زیررشته‌ای'],['v5','AST/schema، هویت، scope و proof typed','router سه‌حالته، bundle لازم، admission، ledger']])
    + '<div class="interactive"><label>بازرسی نسخه <select id="version-select">'+''.join(f'<option>{v[0]}</option>' for v in versions)+'</select></label><p id="version-detail" aria-live="polite"></p></div>'
    + note('سؤال اصلی از «چقدر بیشتر compact کنیم؟» به «کدام شاهد دقیقاً برای این نیاز لازم است و چه زمانی حق تأیید داریم؟» تغییر کرد.')
    + '<p class="source">در v2، شواهد کامل واقعیِ وزن‌دار ۱۵/۲۰ بود و گراف قبلی ۱۶/۲۰؛ خود وزن‌دهی برتری نداد. در v1 نیز diffusion نسبت به کنترل بدون diffusion مزیت مشخص نداشت. [S1, S2]</p>')

page('v3','سابقهٔ مدل واقعی؛ قابل ترکیب با pilot جدید نیست','v3: RAG کمک کرد؛ فاصلهٔ reasoning بسته نشد',
    '<p>در v3، E5 واقعی با بردار ۳۸۴بعدی و پنجره‌های پوشش‌دهندهٔ ورودی بلند استفاده شد. planner و critic روی دستهٔ سؤال‌ها اجرا شدند. منبع، نوت، bridge و pruning به بستهٔ درخواست تبدیل شدند.</p>'
    + grouped('v3 تاریخی: دادهٔ کامل در برابر زیرمجموعهٔ اطلاعات یکسان',['کل ۲۰','reasoning/code ۱۲'],[('Luna + v3',[13,6],GREEN),('Sol بدون RAG',[12,12],DARK)],[20,12])
    + table(['مسیر تاریخی','کل ۲۰ سؤال','دانش اختصاصی ۸','reasoning/code ۱۲'],[['Luna بدون RAG','۷','۰','۷'],['Sol بدون RAG','۱۲','۰','۱۲'],['Luna + v3 fixed','۱۳','۷','۶'],['Sol + v3 fixed','۱۹','۷','۱۲']])
    + '<div class="stats two">'+stat('کاهش بستهٔ ۸ سؤال دانشی','۶۱٫۵۴٪','۲۲۶۵٫۳۸ → ۸۷۱٫۲۵ توکن')+stat('کاهش input مرحلهٔ پاسخ','۲٫۷۳٪','scaffold و تماس‌های دیگر مهم‌اند')+'</div>'
    + note('۱۳/۲۰ Luna در برابر ۱۲/۲۰ Sol بدون RAG، به معنی Luna قوی‌تر نیست: دسترسی به دانش اختصاصی برابر نبود. در مسائل با اطلاعات یکسان، Sol هر ۱۲ را حل کرد و Luna+v3 شش مورد را.')
    + '<p class="source">۱۴۰ پاسخ در ۷ arm، دو تماس planner/critic و دو probe؛ جمع ۱۴۴ تماس. ۵ تا ۷ تماس برای هر درخواست، شرح دقیق این اجرای v3 نبود. نتیجه‌های این صفحه به آزمایش تاریخی مربوط‌اند. [S3]</p>')

page('v4','سرعت آماده‌سازی در برابر اعتبار خروجی','v4: حذف کار تکراری، همراه با چند خطای مهم',
    '<p>ایندکس، هزینهٔ واحدها و رابطه‌ها یک بار برای snapshot ساخته شدند. درخواست به یک گذر lexical، انتخاب معیار و یک hop محدود شد. در گزارش ۱۵۶تایی، زمان آماده‌سازی میانه از حدود ۱۹۱۰ ms به ۱٫۱۸ ms رسید؛ این مقایسهٔ offline بود، نه زمان کل تولید جواب.</p>'
    + table(['سنجهٔ گزارش قدیمی ۱۵۶تایی','v3 fixed در harness v4','v4'],[['شواهد کامل','۱۵۵ / ۱۵۶','۱۵۶ / ۱۵۶'],['میانهٔ آماده‌سازی','۱۹۱۰٫۲۷ ms','۱٫۱۸ ms'],['میانگین توکن بسته','۲۵۳۳٫۸۹','۳۲۴٫۲۸'],['کیفیت خروجی مدل','اندازه‌گیری نشد','اندازه‌گیری نشد']])
    + diagram('اشکال verifier زیررشته‌ای',[('s',60,10,245,65,'شاهد: ۲۵۰','alpha01.limit_ms = 250','#e9eee9'),('a',370,10,245,65,'ادعا: ۲۵','value = 25','#f4ebe5'),('v',195,130,280,65,'v4: پذیرش اشتباه','وجود زیررشته، اثبات مقدار نیست','#f3e9e7')],[('s','v'),('a','v')],height=220)
    + table(['ایراد بازتولیدشده','چرا مهم است؟'],[['موجودیت یا field اشتباه','وجود مقدار در شاهد متعلق به نیاز نبود'],['پاسخ خالی / criterion گم‌شده','نبود خطا را موفقیت کامل حساب می‌کرد'],['citation غایب','fallback به کل بسته، اتصال ادعا را از بین می‌برد'],['math صحیح بدون RAG','پاسخ صحیح به‌دلیل نبود در متن رد می‌شد'],['budget=1 / حافظهٔ خالی','بستهٔ ۴۴توکنی یا خطای empty vocabulary']])
    + note('سرعت retrieval به‌تنهایی کیفیت پاسخ را ثابت نمی‌کند. baseline گزارش v4 با نسخهٔ نهایی مدل‌آزمایی‌شدهٔ v3 یکسان نبود؛ encoder و مراحل planner/critic تفاوت داشتند.')
    + '<p class="source">۹ regression شناخته‌شده بعداً در v5 بررسی شد. این‌ها holdout تازه یا درصد بهبود کیفیت عمومی نیستند. [S4, S5, S7]</p>')

page('architecture','معماری نهایی پیاده‌شده','سه الگوریتم جدا؛ یک قرارداد و یک Controller',
    diagram('مسیر اصلی v5',[('r',35,10,280,65,'Request + Need','task kind / memory need','#e9eee9'),('s',365,10,280,65,'Snapshot مشترک','project / epoch / revision / hash','#e9eee9'),('m',35,115,280,65,'Memory / RAG','typed candidates + graph refs','#e6efe8'),('t',365,115,280,65,'Token manager','required bundles + exact budget','#e6efe8'),('c',195,220,290,65,'Decision + Controller','generate / verify / repair / stop','#dee9e0')],[('r','m'),('s','m'),('m','t'),('t','c')],height=320)
    + table(['ماژول','مسئولیت','خروجی'],[['Memory','scope، canonicalization، AST/schema، lexical و relation','واحدهای eligible و gaps'],['Token','حفظ bundle لازم، dedup و trim گروهی optional','Pack یا budget_infeasible'],['Decision','route و انتخاب نوع checker، repair یا توقف','receipt صریح'],['Controller','ترتیب اجرا، ledger و idempotency','حداکثر دو تلاش فیزیکی']])
    + note('رتبهٔ بالا، scope و proof را دور نمی‌زند. اگر یک نیاز ضروری مبهم، فاقد شاهد یا بیش‌ازبودجه باشد، مدل قوی‌تر جای منبع معتبر را نمی‌گیرد.')
    + '<p>درخواست، نوت نیاز است؛ حقیقت تأییدشده نیست. خروجی مدل نیز برای حافظه فقط proposal با reference و hash تولید می‌کند. پذیرش انسانی جدا از وضعیت verifier باقی می‌ماند.</p>'
    + '<p class="source">کد اجرایی: contracts.py، memory_v5.py، engine_v5.py، verifier_v5.py و controller_v5.py؛ هرکدام در آزمایش مستقل. [S6, S7]</p>')

page('memory','حافظهٔ درخواست‌محور و بلوک مشترک','مینی‌بلوک مشترک: یک منبع، چند reference',
    '<p>Snapshot قبل از index با project، epoch، revision و status پالایش می‌شود. متن Python معتبر با AST، JSON با schema و رکورد متنی با grammar ثبت‌شده استخراج می‌شود. اطلاعات نامفهوم به‌صورت متن می‌ماند؛ با حدس به fact تبدیل نمی‌شود.</p>'
    + diagram('مثال شماتیکِ یک hop ثبت‌شده',[('a',30,10,285,65,'alpha.link = beta','شاهد پل: Source A','#e9eee9'),('b',365,10,285,65,'beta.owner = team9','شاهد مقدار: Source B','#e9eee9'),('n',200,125,280,65,'نیاز: مالک dependency','reference به هر دو شاهد','#e1ece4'),('p',200,230,280,65,'bundle درخواست','بدون کپی یا حقیقت بی‌منبع','#e9eee9')],[('a','n'),('b','n'),('n','p')],height=320)
    + '<h3>ماتریس ارزش v5؛ پس از عبور از gateها</h3>'
    + table(['مولفه','قاعده / وزن','آیا آموخته‌شده است؟'],[['هویت','entity + namespace صحیح؛ وزن ۸','خیر'],['field','فیلد نیاز با شاهد یکسان؛ وزن ۴','خیر'],['اعتبار','role و proof معتبر؛ وزن ۲','خیر'],['هزینه','جریمهٔ ثابت ۰٫۰۰۱ × cost','خیر'],['context اختیاری','امتیاز lexical برای قطعات محدود','خیر']])
    + note('این ماتریس در trace ثبت می‌شود؛ وزن‌ها ثابت‌اند. فشرده‌سازی و reference مشترک، آموزش پارامتری یا یادگیری وزن از بازخورد نیست.')
    + '<p class="source">یال‌ها: containment، adjacency، explicit entity reference و bare-name call حل‌شده در همان فایل. default یک hop از via_field است؛ زنجیرهٔ دلخواهِ چند field و note معنایی بین همهٔ یال‌ها پیاده نشده‌اند. [S6, S7]</p>')

page('tokens','مدیریت توکن، مستقل از رتبه‌بندی','شاهد لازم را برای جا شدن قربانی نمی‌کنیم',
    flow([('واحد کامل','هزینهٔ هر واحد پیشاپیش'),('bundle لازم','مقدار + پل + بدنهٔ موردنیاز'),('بسته exact','حداکثر دو شمارش serialization'),('prompt admission','قرارداد + سؤال + pack')])
    + diagram('مثال شماتیک بودجه: required بزرگ‌تر از سقف',[('a',35,10,285,65,'required = ۲۴۰ توکن','شاهد اصلی + رابطه + metadata','#e9eee9'),('b',360,10,285,65,'budget = ۲۱۰ توکن','سقف عمومی درخواست','#f3ece3'),('v',195,130,290,65,'budget_infeasible','توقف؛ بدون تماس مدل','#f2e8e6')],[('a','v'),('b','v')],height=215)
    + '<div class="split"><div><h3>کار مجاز</h3><ul><li>dedup referenceها و واحدها</li><li>یک حذف گروهی از context اختیاری</li><li>حفظ دو سر یال و تمام requiredها</li><li>رد prompt بزرگ پیش از provider</li></ul></div><div><h3>کار غیرمجاز</h3><ul><li>بریدن بی‌صدای شاهد لازم</li><li>حذف پل و نگه‌داشتن مقدار بی‌منبع</li><li>پر کردن آرشیو تا ۱M برای هر سؤال</li><li>یکی دانستن pack با input مدل</li></ul></div></div>'
    + table(['لایهٔ شمارش','تعریف'],[['آرشیو / snapshot','فضای نگه‌داری؛ کل آن به مدل فرستاده نمی‌شود'],['pack','JSON شواهد، واحدها، binding و relation'],['prompt محلی','دستور + Request + pack؛ admission مستقل'],['provider input','مصرف واقعی ثبت‌شده؛ شامل scaffold CLI و تماس repair']])
    + note('در pilot واقعی، input کل v5 برابر ۳۷۹٬۴۵۲ بود؛ این عدد از ۲۲ تماس می‌آید. میانگین pack نهایی ۱۹۶٫۳ توکن است و با context کل provider برابر نیست.')
    + '<p class="source">توکن‌های محلی: o200k_base. هزینهٔ دلاری از receipt اشتراک معلوم نبود؛ «صفر» یا صرفه‌جویی دلاری ادعا نشده است. [S7, S8]</p>')

page('decision','router، verifier و سقف repair','تصمیم از نوع مسئله و نوع proof می‌آید',
    '<div class="branches"><div><b>project_grounded</b><span>وجود نیاز منبع یا اشارهٔ مثبت به پروژه → بازیابی</span></div><div><b>self_contained</b><span>قرارداد بستهٔ ریاضی یا کد → بدون شواهد خارجی</span></div><div><b>uncertain</b><span>تشخیص ناکافی → probe کوچک؛ بدون فرضِ خودبسنده بودن</span></div></div>'
    + table(['پاسخ','روش بررسی','مرز verified'],[['fact typed','entity / field / namespace / نوع / value / citation','همان ادعا و همان snapshot'],['literal-set','تطابق مجموعهٔ کامل؛ membership فقط اگر صریح باشد','همان constraint'],['ریاضی ساده','حساب محدود روی expression عمومی','فقط عملگرها و ورودی‌های پشتیبانی‌شده'],['کد','اجرای تست عمومی در worker محدود','فقط caseهای اجراشده'],['reasoning پیچیده / متن آزاد','بدون checker معتبر: unverified','درستی معنایی ادعا نمی‌شود']])
    + flow([('تولید اول','Luna، receipt کامل'),('بررسی','شکست معتبر یا وضعیت صریح'),('یک repair','diagnostics عمومی، بدون gold'),('توقف نهایی','هیچ تولید سوم پنهانی نداریم')])
    + '<h3>مثال واقعی: repair نامناسب v4</h3>'
    + '<div class="repair-example"><code>["enabled_2","disabled_2"]</code><span>پاسخ اولیهٔ صحیح</span><b>↓</b><span>verifier زیررشته‌ای رد کرد</span><b>↓</b><code>null</code><span>پاسخ نهایی غلط، اما v4 پذیرفت</span></div>'
    + note('در اجرای نهایی، v4 دو پاسخ factual صحیح را پس از repair از دست داد. در v5 دو repair، دو سؤال natural-alias را به پاسخ درست رساندند.')
    + '<p class="source">Luna-only policy در pilot؛ Sol و escalation استفاده نشد. حالت provider ناقص/اثر نامعلوم خودکار retry نمی‌شود. worker کد sandbox سخت‌شدهٔ OS یا سقف قطعی RAM نیست. [S7, S8]</p>')

page('offline','آزمون نهایی offline؛ پیش از اجرای Luna','۲۴۰ درخواست؛ شواهد بیشتر با metadata بزرگ‌تر',
    '<p>۱۱۲۶۰ واحد، شش خانوادهٔ ۴۰تایی، دو warmup و پنج تکرار جفت‌شده با ترتیب تصادفی. canonical unitهای یکسان به هر دو موتور داده شد. نتیجهٔ صحیح checker از fixture آماده سنجیده شد؛ این ۲۴۰ خروجیِ تولیدی LLM نبود.</p>'
    + '<div class="chart-grid">'+bars('میانهٔ آماده‌سازی',[('v5',oa['median_ms'],GREEN),('v4',ob['median_ms'],DARK)],'ms',digits=3,width=330)+bars('میانگین توکن بسته',[('v5',oa['mean_tokens'],GREEN),('v4',ob['mean_tokens'],DARK)],'tokens',digits=1,width=330)+'</div>'
    + '<div class="stats two">'+stat('شواهد کامل','۱۵۰ / ۱۵۰','v4: ۱۴۰ / ۱۵۰')+stat('route مطابق قرارداد','۲۴۰ / ۲۴۰','v4: ۱۹۸ / ۲۴۰')+'</div>'
    + table(['خانواده','v4 شواهد کامل','v5 شواهد کامل'],[['حقیقت دقیق','۴۰ / ۴۰','۴۰ / ۴۰'],['alias عمومی','۴۰ / ۴۰','۴۰ / ۴۰'],['رابطه','۱۰ / ۲۰','۲۰ / ۲۰'],['freshness / scope','۳۰ / ۳۰','۳۰ / ۳۰'],['کد وابسته به منبع','۲۰ / ۲۰','۲۰ / ۲۰']])
    + note('بده‌بستان واقعی offline: ۳۳٫۱۵٪ زمان میانهٔ کمتر، اما ۱۱۸٫۷۱٪ بستهٔ بزرگ‌تر. metadata نوع و استناد رایگان نیست. زمان ساخت v5 حدود ۵۵۹ ms و v4 از واحد آماده حدود ۴۷۰ ms بود.')
    + '<p class="source">۲۰ ambiguous، ۱۰ missing و ۶۰ مسئلهٔ مستقل جدا از ۱۵۰ شاهد مثبت بودند. ۵۰ تست پاس و ۸۰ case عمومی کد اجرا شد. r1 پس از خطای parser واقعی کنار گذاشته و source آن حفظ شد؛ اجرای نهایی با seed 981315 منجمد شد. [S7]</p>')

page('protocol','اجرای واقعی Luna + v4 در برابر Luna + v5','از «شاهد کامل» به «جواب واقعی درست»',
    '<p>بعد از درخواست شما، ۲۰ سؤال مشترک برای هر دو نسخه آماده شد. مدل یکسان <code>gpt-6-luna</code> با <code>reasoning=low</code> و حساب موجود Codex اجرا شد. schema و verifier مختص نسخه بودند؛ ارزیابی مستقل، gold را بعد از تولید استفاده کرد.</p>'
    + bars('ترکیب ۲۰ سؤال pilot',[('حافظه و Flux',10,GREEN),('reasoning مستقل',6,DARK),('کدنویسی',4,GRAY)],'تعداد سؤال',10)
    + flow([('Freeze','کد، source، jobs و gold'),('Generate','دو worker؛ حداکثر یک repair'),('Receipt','turn.completed، exit=0، بدون ابزار'),('Evaluate','gold جدا و تست‌های withheld')])
    + table(['کنترل آزمایش','چیزی که واقعاً انجام شد'],[['منابع مشترک','canonical unitهای v5 برای هر دو engine'],['حافظه','۸ سؤال مصنوعی + ۲ سؤال قرارداد واقعی Flux'],['reasoning/code','۶ + ۴ سؤال از آزمایش تاریخی؛ regression هستند'],['تست کد','نمونه‌های عمومی یکسان؛ ۱۰ تست اضافه فقط برای evaluator'],['حجم اجرای واقعی','۲۲ تماس v5 + ۳۲ تماس v4 = ۵۴ تماس'],['تکرار','یک پاسخ اولیه در هر arm؛ فقط repair مجاز اضافه شد']])
    + note('همهٔ ۵۴ تماس واقعی تکمیل شدند و tool event نداشتند. Sol در این pilot استفاده نشد. این طراحی اثر prompt، بسته و verifier را با هم می‌سنجد؛ اثر جداگانهٔ هر جزء را تعیین نمی‌کند.')
    + '<p class="source">runtimeهای v3/v4/v5 و برنامهٔ pilot پس از انجماد hash یکسان داشتند. public-jobs، evaluation-only، outputs و provider_runs جدا نگه داشته شدند. [S8, S9]</p>')

page('quality','نتیجهٔ اجرای واقعی','v5 در حافظه بهتر بود؛ reasoning هنوز مسئله دارد',
    grouped('درستی پاسخ نهایی به تفکیک نوع کار',['حافظه / Flux','reasoning','کد'],[('Luna + v5',[10,2,4],GREEN),('Luna + v4',[5,1,4],DARK)],[10,6,4])
    + '<div class="chart-grid">'+bars('درستی در تولید اول',[('v5',14,GREEN),('v4',11,DARK)],'درست از ۲۰',20,width=330)+bars('درستی پس از repair',[('v5',16,GREEN),('v4',10,DARK)],'درست از ۲۰',20,width=330)+'</div>'
    + table(['کیفیت مستقل از verifier','Luna + v5','Luna + v4'],[['پاسخ درست نهایی','۱۶ / ۲۰ = ۸۰٪','۱۰ / ۲۰ = ۵۰٪'],['تولید اول','۱۴ / ۲۰ = ۷۰٪','۱۱ / ۲۰ = ۵۵٪'],['سؤال‌هایی که فقط این arm درست بود','۶','۰'],['native verifier در reasoning','۶ مورد unverified','می‌تواند correct را رد کند']])
    + note('۳۰ واحد درصد بهبود در این pilot مشاهده شد؛ «۳۰٪ افزایش هوش عمومی» نیست. تمام ۴ پاسخ کدِ هر arm تست‌ها را پاس کردند، ولی در reasoning فقط ۲/۶ و ۱/۶ درست بود.','strong')
    + '<p>چهار شکست مشترک v5: احتمال شرطی، CRT، انتظار الگوی تاس و کوتاه‌ترین مسیر. این خطاها با RAG بهتر به‌خودی‌خود حل نشدند؛ دادهٔ مسئله از ابتدا در سؤال موجود بود.</p>'
    + '<p class="source">نتایج score از raw output دوباره محاسبه شدند. «verified» بومیِ نسخه و «جواب درست» evaluator یکی نیستند. ۲۰ سؤال و یک نوبت، ادعای برتری عمومی یا هم‌سطح شدن با Sol را پشتیبانی نمی‌کند. [S8, S9]</p>')

page('efficiency','زمان و توکن واقعی از receiptها','repair کمتر، تماس کمتر، input کمتر',
    '<div class="chart-grid">'+bars('میانگین end-to-end هر سؤال',[('v5',a['mean_end_to_end_seconds'],GREEN),('v4',b['mean_end_to_end_seconds'],DARK)],'seconds',digits=2,width=330)+bars('تعداد تماس واقعی',[('v5',22,GREEN),('v4',32,DARK)],'calls',digits=0,width=330)+'</div>'
    + '<div class="chart-grid">'+bars('input کل provider',[('v5',a['input_tokens_total'],GREEN),('v4',b['input_tokens_total'],DARK)],'tokens',digits=0,width=330)+bars('repairهای واقعی',[('v5',2,GREEN),('v4',12,DARK)],'repairs',digits=0,width=330)+'</div>'
    + table(['سنجهٔ همین اجرای واقعی','v5','v4'],[['میانهٔ زمان سؤال','۶٫۲۵ s','۹٫۹۱ s'],['میانگین evidence نهایی','۱۹۶٫۳ tokens','۵۷۱٫۸ tokens'],['output کل provider','۱۴۶۲ tokens','۱۶۷۴ tokens'],['سهم scaffold / cache','در receipt ثبت شده؛ pack نیست','در receipt ثبت شده؛ pack نیست']])
    + note('در این pilot: میانگین زمان ۲۹٫۶۹٪ کمتر، input کل ۳۲٫۱۵٪ کمتر و تعداد تماس ۳۱٫۲۵٪ کمتر بود. زمان صف و ساخت اولیهٔ index در end-to-end هر job نیست؛ اجرا دو worker هم‌زمان داشت.')
    + '<p class="source">بستهٔ v5 در workload offline بزرگ‌تر بود، اما در pilot مدل کوچک‌تر شد؛ مجموعهٔ سؤال، route و رشد بستهٔ repair v4 متفاوت بودند. این دو مقایسه را ادغام نمی‌کنیم. هزینهٔ دلاری نامعلوم است. [S7, S8]</p>')

public=load(LIVE/'public-jobs.json');gold=load(LIVE/'evaluation-only.json')
labels={'holdfinal-f0':'حقیقت string','holdfinal-f1':'حقیقت integer','holdfinal-f2':'مجموعهٔ literal','holdfinal-f3':'عدد همراه واحد','holdfinal-q0':'alias انگلیسی','holdfinal-q1':'alias فارسی','holdfinal-h0':'مالک dependency ۱','holdfinal-h1':'مالک dependency ۲','Flux-limit':'Flux: max_concurrency','Flux-owner':'Flux: allowed owner','R00':'احتمال شرطی','R01':'عضویت در یک مجموعه','R02':'رشتهٔ باینری','R03':'CRT','R04':'انتظار الگوی ۶۶۵','R06':'کوتاه‌ترین مسیر','C00':'canonical revision','C01':'weighted intervals','C02':'shortest path code','C03':'merge intervals'}
def result_row(case):
    rows={arm:next(r for r in live['rows'] if r['id']==case['id'] and r['arm']==arm) for arm in ('v5','v4')}
    expected=next(g for g in gold if g['id']==case['id'])
    def value(arm):
        score=rows[arm]['independent_score'];text=score.get('display',str(score.get('value')))
        return f'<span class="verdict {"pass" if score["passed"] else "fail"}">{"درست" if score["passed"] else "غلط"}</span><code class="answer">{e(text)}</code>'
    ref='تست اجرایی مستقل' if expected['kind']=='code' else json.dumps(expected['value'],ensure_ascii=False)
    return [f'<b>{labels[case["id"]]}</b><small class="case-id">{case["id"]}</small>',value('v5'),value('v4'),f'<code class="answer">{e(ref)}</code>']

page('answers-memory','خروجی واقعی؛ سؤال‌های ۱ تا ۱۰','حافظه و قرارداد واقعی Flux',
    '<p>در این ۱۰ سؤال، v5 تمام پاسخ‌ها را درست داد و v4 پنج پاسخ درست داشت. مقدارها عین خروجی نهایی‌اند؛ «null» پاسخ نامعلوم است، نه جواب صحیح برای منبعی که مقدار مشخص دارد.</p>'
    + table(['سؤال','Luna + v5','Luna + v4','مرجع'],[result_row(c) for c in public['cases'][:10]],'answer-table')
    + note('درخواست‌های مربوط به allowed owner، مجموعهٔ مجاز <code>Literal</code> را می‌پرسیدند؛ این پاسخ اثبات مالک واقعی یا وضعیت runtime امروز نیست.')
    + '<p class="source">JSON کامل با citation، binding، status، رسید و متن provider در outputs/ و results.json ذخیره شده است. مقدارهای مصنوعی، حقایق اختصاصی benchmark هستند. [S8]</p>')

page('answers-reason','خروجی واقعی؛ سؤال‌های ۱۱ تا ۲۰','reasoning و کدنویسی با شواهد یکسان',
    '<p>در reasoning تمام دادهٔ لازم در سؤال بود. چهار پاسخ کد با نمونه‌های عمومی و caseهای اضافهٔ withheld اجرا شدند. تعداد تست پاس، به معنی اثبات کل رفتار ممکن برنامه نیست.</p>'
    + table(['سؤال','Luna + v5','Luna + v4','مرجع'],[result_row(c) for c in public['cases'][10:]],'answer-table')
    + note('برای CRT، پاسخ مرجع ۷۹ است؛ مدل‌ها ۹۳۱ و ۵۵۹ دادند. انتظار الگوی ۶۶۵ برابر ۲۱۶ است؛ هر دو ۲۵۸ دادند. این خطاها مرز توان reasoning را نشان می‌دهند.')
    + '<p class="source">چهار جواب کد در هر arm تمام ۲۲ case عمومی/withheld متناظر را پاس کردند. این ۲۲، شمار caseها برای چهار سؤال است؛ نه ۲۲ مسئلهٔ مستقل. [S8, S9]</p>')

page('implementation','چیزی که ساخته شد و چیزی که باقی ماند','مزیت رقابتی بالقوه؛ هنوز یک candidate مستقل',
    table(['پیاده‌شده و آزموده‌شده','پیاده‌نشده / اثبات‌نشده'],[['AST / JSON / schema و source binding','معنای آزاد کامل یا parser INI/YAML'],['یک hop ثبت‌شده و reference مشترک','note معنایی بین تمام یال‌ها؛ زنجیرهٔ دلخواه چند field'],['حذف محدود optionalها و پذیرش exact','optimizer خودآموز یا وزن کالیبره‌شده'],['router سه‌حالته، verifier typed، ledger','توان reasoning هم‌سطح Sol'],['adapter حساب موجود و اجرای واقعی Luna','اجرای production یا integration حافظهٔ اصلی'],['۵۰ تست و hash freeze و آرشیو شکست','benchmark خارجی بزرگ و تکرارشونده'],['proposal دارای hash/reference','تغییر پارامتر مدل یا ارتقای خودکار حافظه']])
    + flow([('مزیت امروز','شاهد متصل به ادعا؛ trace قابل ممیزی'),('آزمون بعدی','دادهٔ مستقل، چند تکرار، paraphrase بدون alias'),('reasoning','checker عمومی معتبر و بررسی مدل قوی‌تر'),('ادغام بعدی','پذیرش candidate، سپس integration جدا')])
    + '<h3>نقشهٔ فایل‌های اجرا</h3>'
    + table(['فایل','وظیفه'],[['contracts.py / memory_v5.py','قرارداد و snapshot / extraction / graph'],['engine_v5.py','router، ماتریس، retrieval و بودجه'],['verifier_v5.py / code_worker.py','proof و تست اجرایی محدود'],['controller_v5.py / provider_v5.py','ledger، repair و receipt واقعی'],['cli.py / test_v5.py','demo و ۵۰ آزمون'],['benchmark_v5.py / run_pilot.py','offline منجمد / آزمایش واقعی جفت‌شده']])
    + note('آنچه می‌تواند Edge رقابتی Flux بسازد: حافظهٔ اختصاصی درست، هزینهٔ تماس کمتر و پاسخ قابل‌ردیابی. آنچه هنوز نداریم: اثبات برتری عمومی reasoning یا موفقیت محصول در استفادهٔ واقعی.','strong')
    + '<p class="source">هیچ مدل تازه‌ای آموزش داده نشد. «خودتخریبی RAG» در این مسیر، حذف از نمای مشتق‌شده بود و به معنی پاک کردن اصل دانش نبود. [S6, S7, S8]</p>')

sources=[
 ('S1','v1: graph / diffusion',EXP/'diffusion_memory_20261001/REPORT.fa.md'),
 ('S2','v2: ارزش و shared mini-block',EXP/'diffusion_memory_v2_20261001/REPORT.fa.md'),
 ('S3','v3: نتیجهٔ واقعی Luna/Sol',EXP/'request_memory_v3_20261002/results.json'),
 ('S4','v4: holdout اصلی ۱۵۶تایی',EXP/'request_memory_v4_20261002/holdout-results.json'),
 ('S5','بازبینی مستقل v4',EXP/'request_memory_v4_review_20261002/review-results.json'),
 ('S6','طراحی مصوب v5',EXP/'request_memory_v5_design_20261002/ALGORITHM.fa.md'),
 ('S7','v5: holdout نهایی offline',V5/'runs/final/holdout-results.json'),
 ('S8','اجرای واقعی Luna + v4/v5',LIVE/'results.json'),
 ('S9','بازسنجی و receipt verification',LIVE/'verification.json')]
source_registry=[{'id':ident,'title':title,'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for ident,title,path in sources]
page('evidence','منابع، معیارها و قابلیت بازتولید','هر ادعا به یک اجرای مشخص وصل است',
    table(['شناسه','منبع / اجرای مرتبط','SHA-256 کوتاه'],[[ident,title,f'<code>{hashlib.sha256(path.read_bytes()).hexdigest()[:16]}</code>'] for ident,title,path in sources])
    + '<ol class="evidence-paths">'+''.join(f'<li><b>{ident}</b><code>{e(str(path.relative_to(ROOT)))}</code></li>' for ident,_,path in sources)+'</ol>'
    + '<h3>چهار سطح ادعا</h3>'
    + '<div class="evidence-levels"><div><b>طراحی</b><span>هدف و قرارداد پیشنهادی</span></div><div><b>offline</b><span>retrieval، budget و checker</span></div><div><b>مدل واقعی</b><span>جواب و receipt تکمیل</span></div><div><b>production</b><span>هنوز اجرا نشده</span></div></div>'
    + note('فایل <code>evidence-manifest.json</code> کنار HTML شامل hash کامل منابع است. سند از نتیجه‌های ذخیره‌شده ساخته شد؛ برای تهیهٔ این گزارش هیچ تماس تازهٔ مدل یا تغییر runtime انجام نشد.')
    + '<p class="source">محدودیت‌های اصلی: دادهٔ مصنوعی و alias معلوم، فقط دو سؤال واقعی در pilot آخر، مجموعهٔ کوچک، یک تکرار، تفاوت schema/prompt، منابع canonical مشترک، دو worker هم‌زمان و هزینهٔ دلاری نامعلوم.</p>')

css=font_css+'''
:root{--ink:#161b18;--muted:#687369;--green:#17835c;--soft:#edf3ec;--line:#dce2d9;--paper:#fff;--bg:#e9ece6}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font-family:Vazir,Arial,sans-serif;font-size:14px;line-height:1.75;direction:rtl}a{color:#16724f;text-decoration:none}p{margin:10px 0}h1,h2,h3{line-height:1.5;margin:0 0 10px}h1{font-size:29px;font-weight:750}h2{font-size:23px}h3{font-size:16px;margin-top:14px}code{font-family:Consolas,monospace;font-size:12px;direction:ltr;unicode-bidi:isolate;overflow-wrap:anywhere}small{font-size:11px}ul{padding-right:22px;margin:8px 0}.toolbar{position:sticky;top:0;z-index:5;background:#17221b;color:#fff;display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding:12px 24px}.toolbar a{color:#dcece0}.toolbar label{display:flex;gap:9px;align-items:center;min-width:0;max-width:100%}.toolbar select{min-width:0;max-width:100%;flex:1}.evidence-paths code{min-width:0}.toolbar select,.toolbar button{font:inherit;padding:5px 12px;border:1px solid #5e7263;border-radius:5px;background:#263d2d;color:#fff}.toolbar .brand{font-weight:700;letter-spacing:2px;direction:ltr}.sheets{padding:28px 0}.sheet{width:210mm;min-height:297mm;background:var(--paper);margin:0 auto 24px;padding:15mm 16mm 21mm;position:relative;box-shadow:0 8px 30px #2a332117}.page-head{border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:16px}.eyebrow{color:var(--green);font-size:11px;margin-bottom:6px;font-weight:650}.page-head h1{margin-bottom:0}.page-foot{position:absolute;left:16mm;right:16mm;bottom:11mm;border-top:1px solid var(--line);padding-top:7px;display:flex;justify-content:space-between;font-size:10px;color:var(--muted)}.page-body{overflow-wrap:break-word}.lead{font-size:17px;line-height:1.9}.cover-brand{font-family:Consolas,monospace;font-size:34px;font-weight:700;letter-spacing:2px;direction:ltr;margin:25px 0;color:#202b23}.cover-brand span{color:var(--green)}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}.stats.two{grid-template-columns:repeat(2,1fr)}.stat{background:var(--soft);padding:14px 16px;border-radius:9px;display:flex;flex-direction:column}.stat span{font-size:12px}.stat b{font-size:28px;line-height:1.65;font-weight:750}.stat small{color:var(--muted)}.note{background:#f0f3eb;border-right:4px solid var(--green);padding:12px 15px;margin:15px 0;border-radius:4px;font-size:13px}.note.strong{background:#e4efe6;font-size:14px;font-weight:600}.source{color:var(--muted);font-size:11px;line-height:1.7}figure{margin:14px 0 17px}figcaption{font-size:13px;font-weight:650;margin-bottom:7px}svg{display:block;width:100%;height:auto;overflow:visible;direction:ltr;font-family:Vazir,Arial,sans-serif}.svg-label{font-size:16px;fill:#202720}.svg-value{font-size:16px;font-weight:650;fill:#202720}.svg-small{font-size:13px;fill:#626e62}.flow{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:16px 0}.flow .step{background:#f6f7f3;border-top:3px solid #95b09b;border-radius:6px;padding:13px 11px;display:flex;flex-direction:column;gap:6px;position:relative}.flow .step b{font-family:Vazir;font-size:16px;color:var(--green)}.flow .step strong{font-size:13px}.flow .step span{font-size:11px;line-height:1.7}.table-wrap{width:100%}table{width:100%;border-collapse:collapse;margin:12px 0;font-size:12px;table-layout:fixed}thead{background:#eaf0e8}th,td{text-align:right;border-bottom:1px solid var(--line);padding:9px 9px;vertical-align:top;overflow-wrap:anywhere}th{font-weight:650}tr{break-inside:avoid}td small{display:block;color:var(--muted)}.timeline{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:18px 0}.timeline div{border-top:3px solid var(--green);padding:11px 8px;background:#f5f7f0}.timeline span{font-family:Consolas;font-size:25px;font-weight:700}.timeline strong{display:block;font-size:11px;direction:ltr;text-align:left}.timeline p{font-size:12px;line-height:1.65}.timeline small{font-size:10px;line-height:1.65;display:block;color:var(--muted)}.interactive{border:1px solid #d8e2d6;padding:12px;border-radius:7px;margin:15px 0}.interactive select{font:inherit;margin-right:9px;padding:4px 10px;background:#fff;border:1px solid #9fb19f;border-radius:4px}.interactive p{font-size:12px}.split,.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.split li{font-size:13px}.branches{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:12px 0 20px}.branches div{background:#edf3eb;border-radius:7px;padding:14px}.branches b{display:block;font-size:12px;direction:ltr;text-align:left}.branches span{display:block;margin-top:8px;font-size:12px}.repair-example{display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:#f6f1ec;padding:15px}.repair-example span{font-size:11px}.repair-example b{font-size:20px;color:#925d3c}.answer-table th:first-child{width:22%}.answer-table td{padding:12px 8px}.answer-table code.answer{display:block;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.65;margin-top:5px;font-size:11px}.verdict{font-size:11px;font-weight:700}.verdict.pass{color:#14784b}.verdict.fail{color:#a5433c}.case-id{font-family:Consolas;direction:ltr;text-align:right;font-size:10px;margin-top:5px}.evidence-paths{list-style:none;padding:0;margin:12px 0}.evidence-paths li{display:flex;gap:9px;margin-bottom:6px;align-items:start}.evidence-paths b{font-family:Consolas;font-size:11px}.evidence-paths code{font-size:10px;line-height:1.6;text-align:left;direction:ltr}.evidence-levels{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:12px 0}.evidence-levels div{padding:10px;background:#f1f4ed;border-radius:5px}.evidence-levels b{display:block;font-size:13px}.evidence-levels span{font-size:11px}.badge{display:inline-block;border-radius:4px;padding:2px 8px;font-size:11px;background:#eef0e8}
@media(max-width:820px){.toolbar{position:static;padding:12px}.sheet{width:calc(100% - 20px);min-height:0;padding:24px 22px 65px}.page-foot{left:22px;right:22px;bottom:18px}.page-head h1{font-size:24px}.cover-brand{font-size:28px}.lead{font-size:15px}.timeline{grid-template-columns:repeat(2,1fr)}.flow{grid-template-columns:repeat(2,1fr)}.sheets{padding:15px 0}.table-wrap{overflow-x:auto}.answer-table{min-width:620px}.svg-label,.svg-value{font-size:16px}}
@media(max-width:500px){body{font-size:13px}.stats,.stats.two,.split,.chart-grid,.branches{grid-template-columns:1fr}.evidence-levels{grid-template-columns:repeat(2,1fr)}.stat b{font-size:25px}.sheet{padding:22px 16px 64px}.page-foot{left:16px;right:16px}.page-head h1{font-size:22px}.timeline{grid-template-columns:1fr 1fr}}
@page{size:A4;margin:0}
@media print{#v4 .page-body,#quality .page-body,#implementation .page-body,#evidence .page-body{font-size:13px;line-height:1.65}#v4 td,#v4 th,#quality td,#quality th,#implementation td,#implementation th,#evidence td,#evidence th{padding:7px 9px}#answers-memory .answer-table td,#answers-reason .answer-table td{padding:9px 8px}html{scroll-behavior:auto}body{background:#fff;font-size:14px;-webkit-print-color-adjust:exact;print-color-adjust:exact}.toolbar,.interactive{display:none!important}.sheets{padding:0}.sheet{width:210mm;height:297mm;min-height:0;margin:0;padding:15mm 16mm 21mm;box-shadow:none;break-after:page;overflow:hidden}.sheet:last-child{break-after:auto}.table-wrap{overflow:visible}.answer-table{min-width:0}.page-foot{left:16mm;right:16mm;bottom:11mm}.timeline{grid-template-columns:repeat(5,1fr)}.flow{grid-template-columns:repeat(4,1fr)}.stats{grid-template-columns:repeat(3,1fr)}.stats.two,.split,.chart-grid{grid-template-columns:1fr 1fr}.branches{grid-template-columns:repeat(3,1fr)}.evidence-levels{grid-template-columns:repeat(4,1fr)}}
'''
nav=''.join(f'<option value="{p["id"]}">{fa(i+1)} · {p["title"]}</option>' for i,p in enumerate(pages))
sections=''.join(f'<section class="sheet" id="{p["id"]}" data-page="{i+1}"><header class="page-head"><div class="eyebrow">{p["kicker"]}</div><h1>{p["title"]}</h1></header><div class="page-body">{p["body"]}</div><footer class="page-foot"><span>Flux · Memory Research · 2026-10-02</span><span>{fa(i+1)} / {fa(len(pages))}</span></footer></section>' for i,p in enumerate(pages))
script='''
document.getElementById('chapter-select').addEventListener('change',e=>document.getElementById(e.target.value).scrollIntoView({behavior:'smooth'}));
document.getElementById('print-button').addEventListener('click',()=>window.print());
const versionDetails={v1:'انتشار وزن روی گراف برتری مشخص نداد؛ نگه‌داری source و fallback مؤثر بود.',v2:'بلوک مشترک و reference حفظ شد؛ وزن‌های دلخواه روی کد واقعی نتیجهٔ بهتر ندادند.',v3:'E5 و prune پیاده شدند؛ بسته کوچک‌تر شد، ولی فاصلهٔ reasoning Luna/Sol بسته نشد.',v4:'snapshot مشترک مسیر hot را سریع کرد؛ verifier substring و router دوحالته نقص داشتند.',v5:'proof typed، bundle لازم و ledger اضافه شد؛ pilot واقعی ۱۶/۲۰ در برابر ۱۰/۲۰ گرفت.'};
const picker=document.getElementById('version-select');function showVersion(){document.getElementById('version-detail').textContent=versionDetails[picker.value]}picker.addEventListener('change',showVersion);showVersion();
'''
html='<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Flux | گزارش تصویری حافظه و تصمیم‌گیری v1-v5</title><style>'+css+'</style></head><body><nav class="toolbar" aria-label="فهرست گزارش"><span class="brand">ALACRITY / FLUX</span><label>فصل <select id="chapter-select">'+nav+'</select></label><button id="print-button" type="button">چاپ / PDF</button></nav><main class="sheets">'+sections+'</main><script>'+script+'</script></body></html>'
OUT.write_text(html,encoding='utf-8')
(HERE/'evidence-manifest.json').write_text(json.dumps({'sources':source_registry,'pages':len(pages),'embedded_font':True,
    'html_sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),'actual_new_model_calls_for_document':0,
    'metrics':{'live':live['summary'],'offline':offline['summary']}},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'html':str(OUT),'pages':len(pages),'svg_figures':html.count('<svg'),'bytes':OUT.stat().st_size},ensure_ascii=False))
