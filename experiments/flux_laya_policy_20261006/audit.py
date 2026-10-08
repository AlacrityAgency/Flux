"""Post-run integrity and re-execution audit; cannot change frozen policy."""
import json
from pathlib import Path
import benchmark as E

HERE=Path(__file__).resolve().parent
E.verify()
r=json.loads((HERE/'results.json').read_text(encoding='utf-8'))
assert r['status']=='complete'
assert E.sha(HERE/'plan.json')==r['plan_hash']
for path,digest in r['receipt_hashes'].items():assert E.sha(HERE/path)==digest,path
tasks={t['id']:t for t in json.loads((HERE/'tasks.json').read_text(encoding='utf-8'))}
adapter=E.FluxAdapter()
rechecked=[]
for file in sorted((HERE/'trials').glob('*.json')):
    trial=json.loads(file.read_text(encoding='utf-8'));task=tasks[trial['task']]
    for label in trial['labels']:
        receipt=json.loads((HERE/'receipts'/(label+'.json')).read_text(encoding='utf-8'))
        done=[e for e in receipt['raw_events'] if e.get('type')=='turn.completed']
        assert receipt['usage']==(done[-1].get('usage',{}) if done else {})
        assert receipt['completed']==(bool(done) and receipt['exit_code']==0)
        assert receipt['tool_events']==0
    final=json.loads((HERE/'receipts'/(trial['labels'][-1]+'.json')).read_text(encoding='utf-8'))
    effective,program=adapter.interpret(task,final,trial['programs'][-1]['method'])
    verdict=E.B.check(task,effective,'full')
    assert verdict['pass']==trial['audit']['pass'],file
    rechecked.append({'trial':file.stem,'correct':verdict['pass'],'program_reexecuted':program['method']=='program'})
    for label in trial['local_labels']:
        local=json.loads((HERE/'laya_receipts'/(label+'.json')).read_text(encoding='utf-8'))
        assert local['checkpoint_revision']=='7b928d828b7b0e022f929d9bd2e44165aa270148'
        assert local['output']['usage']['output_tokens']==0
        assert not local['output']['usage'].get('truncated')
        assert not local['output']['usage'].get('truncated_questions')
        assert local['output']['usage'].get('state_tokens_dropped',0)==0

facts={'passed':True,'trials_reaudited':len(rechecked),'hashes_verified':len(r['receipt_hashes']),
    'rechecks':rechecked,'uncached_api_equivalent':{},'model_breakdown':{}}
for arm in E.ARMS:
    ts=[json.loads(p.read_text(encoding='utf-8')) for p in (HERE/'trials').glob('*__'+arm+'.json')]
    rs=[json.loads((HERE/'receipts'/(label+'.json')).read_text(encoding='utf-8')) for t in ts for label in t['labels']]
    known=all(E.B.cost(x) is not None for x in rs)
    facts['uncached_api_equivalent'][arm]=sum(E.B.cost(x,uncached=True) for x in rs) if known else None
    facts['model_breakdown'][arm]={m:{'calls':sum(x['model']==m for x in rs),
        'known_api_equivalent_usd':sum(E.B.cost(x) or 0 for x in rs if x['model']==m)} for m in E.B.MODELS}
E.write(HERE/'audit-results.json',facts)
text=['# ممیزی نهایی','',f"تمام {len(rechecked)} اجرای نهایی دوباره بررسی و برنامه‌های پاسخ نهایی دوباره محلی اجرا شدند. {len(r['receipt_hashes'])} هش رسید و نتیجه تطبیق دارند. رویداد مصرف خام با جمع ثبت‌شده برابر است؛ استفاده از ابزار صفر است. خروجی Laya صفر توکن تولیدی و بدون حذف متن/پرسش بوده است.",'',
    'هزینهٔ فرضی بدون تخفیف کش (برای بررسی حساسیت؛ صورت‌حساب واقعی نیست):','',
    '|مسیر|دلار فرضی بدون کش|','|---|---:|']
for arm,cost in facts['uncached_api_equivalent'].items():text.append(f'|{arm}|{cost}|')
text+=['','انتخاب مدل‌های GOAT با Laya:','']
for t in sorted((HERE/'trials').glob('*__goat_flux_laya.json')):
    x=json.loads(t.read_text(encoding='utf-8'));text.append(f"- {x['task']}: {x['route']['model']} / {x['route']['effort']}; {x['retries']} ارتقا.")
text+=['','تعداد کمتر توکن به‌تنهایی هزینهٔ کمتر را ثابت نمی‌کند: تعرفهٔ مدل و نسبت کش مهم‌اند. احتمال‌های Laya در این آزمایش برای هزینه/موفقیت سه مدل آموزش یا کالیبره نشده‌اند. نتایج مسیر GOAT خام می‌تواند نشان دهد که باید سیاست قیمت و آستانه‌های ارتقا روی مجموعهٔ آموزش جداگانه تنظیم شوند.','',
       'گزارش اصلی در REPORT.fa.md و مقادیر دقیق در results.json هستند. الگوریتم و نتایج در پوشهٔ مستقل experiments قرار دارند.']
(HERE/'AUDIT.fa.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
print(json.dumps(facts,ensure_ascii=False,indent=2))
