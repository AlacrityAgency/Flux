"""Actual compact-program responses, three independent invoice facts per model."""
import concurrent.futures, json, sys
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'flux_laya_v2_repeat_20261006'))
from optimizer import COMPACT,compact_audit,execute_compact
sys.path.insert(0,str(HERE))
from probe_models import invoke

def parse(text):
    text=text.strip()
    if text.startswith('```json\n') and text.endswith('\n```'):text=text[8:-4]
    elif text.startswith('```\n') and text.endswith('\n```'):text=text[4:-4]
    return json.loads(text)

FACTS=[{'lines':[{'qty':3,'unit_cents':1299,'discount_percent':17},{'qty':2,'unit_cents':701,'discount_percent':5}], 'shipping':475,'tax_percent':8.25},
       {'lines':[{'qty':1,'unit_cents':101,'discount_percent':50}], 'shipping':0,'tax_percent':7.25},
       {'lines':[{'qty':7,'unit_cents':2294,'discount_percent':5},{'qty':7,'unit_cents':1713,'discount_percent':17},{'qty':5,'unit_cents':2991,'discount_percent':0},{'qty':4,'unit_cents':2521,'discount_percent':50}], 'shipping':738,'tax_percent':7.25}]
TASK='Calculate invoice in integer cents. Round each qty*unit_cents*(1-discount_percent/100) HALF UP before summing subtotal. Tax is tax_percent percent of subtotal, HALF UP. Shipping is untaxed. Return subtotal_cents, tax_cents, total_cents. Read all numeric data from facts.'

def oracle(facts):
    rounded=lambda x:int(x.quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    subtotal=sum(rounded(Decimal(l['qty'])*l['unit_cents']*(1-Decimal(l['discount_percent'])/100)) for l in facts['lines'])
    tax=rounded(Decimal(subtotal)*Decimal(str(facts['tax_percent']))/100)
    return {'subtotal_cents':subtotal,'tax_cents':tax,'total_cents':subtotal+tax+facts['shipping']}

def test(model):
    prompt=COMPACT+'TASK:\n'+TASK+'\nFACTS:\n'+json.dumps(FACTS[0],separators=(',',':'))
    receipt=invoke(model,prompt,'compact_'+model,90);tests=[];failure='';normalized=False
    try:
        if not receipt['completed'] or receipt['tool_events']:raise ValueError('Provider incomplete or tools used')
        data=parse(receipt['text']);normalized=receipt['text'].strip().startswith('```')
        compact_audit(data,FACTS[0])
        for facts in FACTS:
            result=execute_compact(data['code'],facts)
            tests.append({'worker_pass':result['pass'],'oracle_pass':result.get('answer')==oracle(facts),'worker_reason':result.get('reason','')})
    except Exception as e:failure=str(e)[:600]
    return {'model':model,'compact_contract_pass':len(tests)==3 and all(t['worker_pass'] and t['oracle_pass'] for t in tests),
        'normalization_used':normalized,'cases':tests,'failure':failure,'usage':receipt['usage'],
        'receipt':'receipts/'+receipt['label']+'.json','actual_billing_usd':None}

if __name__=='__main__':
    rows=json.loads((HERE/'availability.json').read_text(encoding='utf-8'))
    models=[r['model'] for r in rows if r['transport_ok']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(test,models))
    (HERE/'compatibility.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
