"""Real Laya + installed skill adapter + worker + independent oracle."""
import hashlib,json,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=Path('C:/Users/xio/.codex/skills/senior-v2')
PROFILE='mixed' if '--mixed' in sys.argv else 'fable'
sys.path.insert(0,str(HERE));from compatibility import FACTS,TASK,oracle,COMPACT
sys.path.insert(0,str(ROOT/'scripts'))
from call_model import invoke,normalize
from validate_program import validate
from laya_decision import predict,guard
import laya,torch

checkpoint=HERE.parent/'flux_laya_policy_20261006/checkpoint'
start=time.perf_counter();agent=laya.load(str(checkpoint),subfolder='multilingual',device='cuda',backend='eager');torch.cuda.synchronize()
load_s=time.perf_counter()-start
front=predict(agent,{'task':TASK,'facts':FACTS[0],'risk_floor':'high'},'front',HERE/'laya_receipts'/('skill_'+PROFILE+'_front.json'))
prompt=COMPACT+'TASK:\n'+TASK+'\nFACTS:\n'+json.dumps(FACTS[0],separators=(',',':'))
plan=([('codex','gpt-6-luna','low'),('gapcode','gpt-6.1-sol','high'),('gapcode','gpt-6-astra','high')]
 if PROFILE=='mixed' else [('gapcode','claude-fable-5','low'),('gapcode','gpt-6.1-sol','high'),('codex','gpt-6-astra','high')])
attempts=[]
for attempt,(provider,model,effort) in enumerate(plan):
    receipt=invoke(provider,model,effort,prompt,HERE/'receipts'/('skill_'+PROFILE+'_e2e_'+str(attempt)+'.json'),90,'compact')
    local={'pass':False,'reason':'Provider incomplete or tools used'}
    if receipt['completed'] and not receipt['tool_events']:
        try:local=validate(normalize(receipt['text']),FACTS[0])
        except ValueError as e:local={'pass':False,'reason':str(e)}
    independent=local['pass'] and local['answer']==oracle(FACTS[0])
    end=predict(agent,{'task':TASK,'provider_completed':receipt['completed'],'candidate':receipt['text'],
        'local_check':{'pass':independent,'reason':local.get('reason','')},'attempt':attempt,'remaining_attempts':2-attempt},
        'end',HERE/'laya_receipts'/('skill_'+PROFILE+'_end'+str(attempt)+'.json'))
    choice=end['output']['answers']['action']['choice'];action=guard(choice,independent,attempt)
    attempts.append({'provider':provider,'model':model,'effort':effort,'worker_pass':local['pass'],
        'independent_pass':independent,'proposed_action':choice,'applied_action':action,'answer':local.get('answer'),
        'receipt':'receipts/skill_'+PROFILE+'_e2e_'+str(attempt)+'.json'})
    if action in ['accept','stop']:break
    prompt+='\nRepair after local failure: '+local.get('reason','Independent invoice check failed')[:240]
result={'passed':action=='accept' and independent,'real_laya':True,'laya_load_s':load_s,'attempts':attempts,
        'profile':PROFILE,'scope':'one arithmetic request with real front/end, installed provider helper and independent Decimal oracle; not a cost benchmark',
        'actual_billing_usd':None}
(HERE/('skill-'+PROFILE+'-smoke.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
