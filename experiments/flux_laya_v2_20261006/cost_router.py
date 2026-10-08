"""Cost of a bounded cascade, from prior development receipts, never holdout gold."""
import json, math, statistics
from pathlib import Path
from suite import B
from optimizer import tokens, facts_for
HERE=Path(__file__).resolve().parent
V1=HERE.parent/'flux_laya_policy_20261006'

def cascade_scores(costs,success):
    tail=0.;scores=[0.,0.,0.]
    for i in [2,1,0]:
        tail=costs[i]+(1-success[i])*tail;scores[i]=tail
    return scores

def build_statistics():
    seen=set();observations=[]
    for arm in ['senior_flux_laya','goat_flux_laya']:
        for p in sorted((V1/'trials').glob('*__'+arm+'.json')):
            t=json.loads(p.read_text(encoding='utf-8'))
            for label,check in zip(t['labels'],t['checks']):
                r=json.loads((V1/'receipts'/(label+'.json')).read_text(encoding='utf-8'))
                key=(t['task'],r['model'],r['effort'])
                if key in seen:continue
                seen.add(key)
                observations.append({'task':t['task'],'family':t['family'],'model':r['model'],'effort':r['effort'],
                    'pass':check['pass'],'output_tokens':r['usage'].get('output_tokens'), 'receipt_hash':B.sha(V1/'receipts'/(label+'.json'))})
    success={}
    for m in B.MODELS:
        rows=[x for x in observations if x['model']==m];k=sum(x['pass'] for x in rows)
        success[m]={'n':len(rows),'passed':k,'beta_1_1_mean':(k+1)/(len(rows)+2)}
    probe_offsets={}
    for m in B.MODELS:
        rs=[json.loads(p.read_text(encoding='utf-8')) for p in (HERE/'receipts').glob('dev_minimal_*.json')]
        rs=[r for r in rs if r['model']==m and r['completed'] and r['usage']]
        if not rs:raise ValueError('Missing configuration probe '+m)
        probe_offsets[m]=statistics.median(r['usage']['input_tokens']-tokens(r['prompt']) for r in rs)
    return {'success':success,'input_offsets':probe_offsets,'observations':observations,
       'estimated_output':{f:statistics.median(x['output_tokens'] for x in observations if x['family']==f and x['output_tokens'] is not None) for f in sorted({x['family'] for x in observations})},
       'output_scale_compact':0.5,'cache_assumption':'uncached, conservative for primary-selection cost',
       'calibration':'Small development empirical statistics with Beta(1,1) smoothing; not calibrated success probabilities, not trained Laya weights.'}

def route(task,front,prompt,statistics_data):
    d=front['output']['answers']
    estimate_out=statistics_data['estimated_output'].get(task['family'],800)
    if task['family'] in ['arithmetic','logic_count','scheduling']:estimate_out*=statistics_data['output_scale_compact']
    costs=[((tokens(prompt)+statistics_data['input_offsets'][m])*B.RATES[m][0]+estimate_out*B.RATES[m][3])/1e6 for m in B.MODELS]
    success=[statistics_data['success'][m]['beta_1_1_mean'] for m in B.MODELS]
    scores=cascade_scores(costs,success);index=min(range(3),key=lambda i:scores[i])
    # Effort adaptation is an explicit heuristic, not a fitted performance claim.
    large_domain=task['family']=='scheduling' and math.factorial(len(task['data']))>=40320
    effort='medium' if large_domain and d['effort']['choice']=='high' else 'low'
    return {'model':B.MODELS[index],'effort':effort,'verify':d['verify']['choice'],
      'raw_laya_model':d['model']['choice'],'raw_laya_effort':d['effort']['choice'],
      'predicted_costs':dict(zip(B.MODELS,costs)),'predicted_cascade_costs':dict(zip(B.MODELS,scores)),
      'smoothed_success_estimates':dict(zip(B.MODELS,success)),
      'raw_model_overridden':d['model']['choice']!=['luna','sol','astra'][index],
      'reason':'minimum estimated cost of remaining bounded cascade; full verification and risk floors retained'}
