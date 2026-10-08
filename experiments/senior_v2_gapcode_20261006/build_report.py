"""Reaudit probe usage/contracts; render evidence into installed skill."""
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=Path('C:/Users/xio/.codex/skills/senior-v2')
sys.path.insert(0,str(ROOT/'scripts'));from call_model import normalize
from validate_program import validate
from laya_decision import guard
sys.path.insert(0,str(HERE));from compatibility import FACTS,oracle

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=read(HERE/'availability.json');comp={x['model']:x for x in read(HERE/'compatibility.json')}
records=[(p,read(p)) for p in (HERE/'receipts').glob('*.json')]
known={};unknown=0;provider_counts={};errors=[]
for p,r in records:
    done=[e for e in r['raw_events'] if e.get('type')=='turn.completed']
    assert (bool(done) and r['exit_code']==0 and not r['timeout'])==r['completed'],p
    assert r['usage']==(done[-1].get('usage') if done else None),p
    assert not r['tool_events'],p
    u=r['usage'];provider_counts[r['provider']]=provider_counts.get(r['provider'],0)+1
    if u is None:unknown+=1
    else:
        assert u['input_tokens']>=u.get('cached_input_tokens',0)+u.get('cache_write_input_tokens',0)
        assert u['output_tokens']>=u.get('reasoning_output_tokens',0)
        for k,v in u.items():known[k]=known.get(k,0)+v
for model,c in comp.items():
    if c['compact_contract_pass']:
        data=normalize(read(HERE/c['receipt'])['text'])
        assert all((r:=validate(data,facts))['pass'] and r['answer']==oracle(facts) for facts in FACTS)

helper_tests=[]
for name in ['helper_codex_luna_low','helper_gapcode_sol_high','helper_gapcode_astra_high']:
    path=HERE/'receipts'/(name+'.json')
    if not path.exists():continue
    receipt=read(path);tests=[]
    if receipt['completed']:
        try:tests=[validate(normalize(receipt['text']),f) for f in FACTS]
        except ValueError:pass
    passed=len(tests)==3 and all(t['pass'] and t['answer']==oracle(f) for t,f in zip(tests,FACTS))
    helper_tests.append({'label':name,'passed':passed,'cases':tests,'receipt':'receipts/'+name+'.json'})
    if passed and receipt['provider']=='gapcode':
        registry=read(ROOT/'references/models.json');info=registry['models']['gapcode/'+receipt['model_requested']]
        info['tested_efforts']=sorted(set(info['tested_efforts']+[receipt['effort_requested']]))
        (ROOT/'references/models.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2),encoding='utf-8')
mixed=read(HERE/'skill-mixed-smoke.json');fable=read(HERE/'skill-smoke.json')
assert mixed['passed'] and fable['passed']
for job in [mixed,fable]:
    for n,t in enumerate(job['attempts']):
        receipt=read(HERE/t['receipt'])
        result=validate(normalize(receipt['text']),FACTS[0])
        passed=result['pass'] and result['answer']==oracle(FACTS[0])
        assert passed==t['independent_pass']
        assert guard(t['proposed_action'],passed,n)==t['applied_action']
for p in (HERE/'laya_receipts').glob('*.json'):
    r=read(p);u=r['output']['usage']
    assert u['output_tokens']==0 and not u.get('truncated') and not u.get('truncated_questions') and not u.get('state_tokens_dropped',0)

descriptions={'kimi-3':'پیش از تماس مدل: workspace trust در مسیر native Claude',
 'glm-5.3':'پیش از تماس مدل: workspace trust در مسیر native Claude',
 'deepseek-v4.1-flash':'402 Insufficient credits؛ retry داخلی CLI ثبت شده',
 'grok-4.6':'upstream stream error و timeout ۹۰ ثانیه'}
compact_reasons={'gpt-6-luna':'refs شامل کلیدهای تو در تو بود؛ رد قرارداد',
 'gapgpt-qwen-3.6':'خروجی Python به‌جای JSON؛ حدود ۸۹ ثانیه',
 'claude-opus-5-5':'timeout ۹۰ ثانیه در تولید برنامه',
 'claude-sonnet-5-5':'timeout ۹۰ ثانیه در تولید برنامه'}
lines=['# تست واقعی مدل‌های GapCode برای Senior V2','',
 'تاریخ: ۲۰۲۶-۱۰-۰۶؛ native GapCode 0.153.4، حساب متصل فعلی. هر مدل کاتالوگ تازه یک ping واقعی گرفت. هر مدل پاسخ‌گو یک درخواست تولید برنامهٔ فاکتور گرفت؛ همان برنامه روی سه facts متفاوت با Decimal مستقل سنجیده شد. پاسخ‌ها بین مدل‌ها replay نشدند.','',
 'ابتدا cache قدیمی ۱۲ نام داشت؛ اولین فراخوانی آن را از سرویس به‌روز کرد. snapshot تازه ۱۱ مدل دارد؛ نام‌های Claude Opus/Sonnet به شناسه‌های 5-5 تغییر کرده‌اند و GPT-5.6 Terra در فهرست تازه نیست. نتیجه بر مبنای ۱۱ شناسهٔ snapshot تازه است، نه حدس نام‌های قدیمی.','',
 '| شناسهٔ دقیق GapCode | پاسخ به ping | قرارداد compact | نتیجه/فعال‌سازی |','|---|---|---|---|']
for r in rows:
    model=r['model'];c=comp.get(model)
    if r['transport_ok']:
        normalized=normalize(read(HERE/r['receipt'])['text'])=={'probe':'ok','sum':42}
        assert normalized
        ping='بله؛ JSON نرمال‌شده' if not r['json_contract_ok'] else 'بله؛ JSON'
        qualified=c['compact_contract_pass']
        desc='compact و پاسخ مستقیم فعال؛ ۳/۳ ورودی درست' if qualified else 'فقط پاسخ مستقیم؛ '+compact_reasons[model]
        lines.append(f"|`{model}`|{ping}|{'پاس' if qualified else 'رد/تکمیل‌نشده'}|{desc}|")
    else:lines.append(f"|`{model}`|تکمیل نشد|آزموده نشد|غیرفعال؛ {descriptions[model]}|")
lines += ['','Fable در ping و نمونهٔ برنامه یک حصار کامل JSON داشت؛ محتوا بدون تغییر unwrap شد. مدل Qwen حصار Python داشت و با parser حدسی به JSON تبدیل نشد. رد refs در Luna یا timeout یک نمونه اثبات ضعف عمومی آن مدل نیست؛ eligibility فعلی محافظه‌کارانه و مخصوص همین قرارداد است.','',
 '## تست helper نصب‌شده','', '| فراخوانی واقعی | برنامه روی سه facts |','|---|---|']
for t in helper_tests:lines.append(f"|`{t['label']}`|{'۳/۳ درست' if t['passed'] else 'رد قرارداد؛ در فایل ممیزی ثبت شده'}|")
lines += ['','## تست یکپارچه با Laya واقعی','',
 'پروفایل Fable-first: Laya ابتدا، GapCode/Fable low، AST و worker، oracle مستقل Decimal، Laya پایان و guard؛ در تلاش اول پاسخ درست پذیرفته شد. این پروفایل انتخاب پیکربندی‌شدهٔ تست بود، نه ترتیب قیمت اثبات‌شده.','',
 'پروفایل پیش‌فرض mixed: Laya ابتدا، Codex/Luna low. برنامه در بررسی محلی رد شد؛ Laya خام accept پیشنهاد داد، ولی guard آن را به escalate تبدیل کرد. تلاش دوم GapCode/Sol high با feedback کوتاه، worker و oracle را پاس کرد و پذیرفته شد. بنابراین مسیر واقعی Codex → GapCode و جلوگیری از پذیرش غلط مشاهده شد. این یک مسئله است، نه benchmark مقایسهٔ هزینه.','',
 '## ممیزی و مصرف','',
 f"{len(records)} رسید CLI بررسی شد؛ تعداد به تفکیک provider: {provider_counts}. {len(records)-unknown} رسید usage کامل دارند و {unknown} رسید usage نامعلوم. مجموعِ معلوم input={known.get('input_tokens',0):,}، output={known.get('output_tokens',0):,}، cached={known.get('cached_input_tokens',0):,} و reasoning={known.get('reasoning_output_tokens',0):,} است. مجموع توکنِ معلوم {known.get('input_tokens',0)+known.get('output_tokens',0):,} است؛ مصرف کل با وجود usage نامعلوم تعیین نشده.",'',
 'اعتبار/صورتحساب واقعی کیف پول خوانده یا اندازه‌گیری نشده است؛ actual_billing_usd=null. قیمت صفحهٔ عمومی نیز در خروجی قابل‌استخراج نبود؛ نرخ API مدل‌ها جای قیمت کیف پول قرار نگرفت. مدل‌های blocked پیش از تکمیل usage ندارند؛ این به معنی صفر فرض‌کردن هزینه نیست.','',
 'چهار مدل غیرپاسخ‌گو در registry فعال نیستند. trust با override همان process برای Kimi/GLM دو بار بررسی شد ولی گیت native باقی ماند؛ اعتماد عمومی workspace یا credential تغییر داده نشد. DeepSeek با کمبود اعتبار مجدداً فراخوانی نشد و timeoutهای Opus/Sonnet/Grok تکرار نشدند.','',
 'تست‌ها اتصال، schema و سازگاری محدود را ثابت می‌کنند. قابلیت همهٔ خانواده‌ها، هزینهٔ کمتر، تلاش‌های max، هم‌ارزی مدل سمت server یا عملکرد production سنجیده نشده‌اند. هویت مدل فقط در سطح نام درخواست‌شده ثبت شده است.','',
 'دادهٔ خام: `D:/project/Alacrity/Flux/experiments/senior_v2_gapcode_20261006`. manifest ممیزی، hash رسیدها، source helpers و اسکیل را دارد.','',
 'منبع رسمی: [GapCode و کیف پول آن](https://aigap.app/gapcode)، [مدل‌ها و مقایسهٔ کدنویسی](https://aigap.app/programming). فهرست دقیق slugها از catalog.json سرویس نصب‌شده و موفقیت از رویدادهای واقعی CLI گرفته شده است.']
(ROOT/'references/model-tests.fa.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
result={'passed':True,'receipt_count':len(records),'provider_counts':provider_counts,'usage_unknown':unknown,
 'usage_known_sum':known,'actual_billing_usd':None,'qualified_compact_models':[m for m,c in comp.items() if c['compact_contract_pass']],
 'helper_tests':helper_tests,'mixed_smoke_passed':mixed['passed'],'fable_smoke_passed':fable['passed'],
 'hashes':{str(p.relative_to(HERE)):sha(p) for p,_ in records},
 'skill_hashes':{str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in str(p)}}
(HERE/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['hashes','skill_hashes','helper_tests']},ensure_ascii=False,indent=2))
