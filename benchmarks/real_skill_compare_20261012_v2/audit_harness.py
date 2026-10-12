"""Independent verification controls and artifact-integrity audit, no provider calls."""
import json
import sys
from pathlib import Path
import benchmark as B

GOOD = {
 'access': '''def solve(facts):
    a=facts['actor'];r=facts['resource']
    if not a['active'] or a['tenant']!=r['tenant']:return {'allowed':False}
    return {'allowed':a['id']==r['owner'] or a.get('role')=='admin'}
''',
 'intervals': '''def solve(facts):
    if any(x[0]>x[1] for x in facts['intervals']):return {'error':'reversed'}
    parts=[list(x) for x in facts['intervals'] if x[0]!=x[1]]
    changed=True
    while changed:
        changed=False
        for i in range(len(parts)):
            for j in range(i+1,len(parts)):
                if max(parts[i][0],parts[j][0])<min(parts[i][1],parts[j][1]):
                    parts[i]=[min(parts[i][0],parts[j][0]),max(parts[i][1],parts[j][1])]
                    parts.pop(j);changed=True;break
            if changed:break
    return {'intervals':sorted(parts)}
''',
 'replay': '''def solve(facts):
    ev=facts['events']
    for i,e in enumerate(ev):
        for prior in ev[:i]:
            if e['id']==prior['id'] and (e['kind'],e['amount'])!=(prior['kind'],prior['amount']):return {'error':'conflict'}
    chosen=[e for i,e in enumerate(ev) if not any(p['id']==e['id'] for p in ev[:i])]
    return {'balance':facts['initial']+sum(e['amount'] if e['kind']=='credit' else -e['amount'] for e in chosen),'applied':len(chosen)}
''',
 'rounding': '''from fractions import Fraction
def solve(facts):
    f=Fraction(facts['amount_cents'])*(100-Fraction(facts['percent']))/100
    q,r=divmod(f.numerator,f.denominator)
    return {'cents':q+(2*r>=f.denominator)}
''',
 'migration': '''def solve(facts):
    rows=facts['rows']
    for i,row in enumerate(rows):
        if any(p['id']==row['id'] for p in rows[:i]):return {'error':'duplicate'}
    for row in rows:
        if 'name' not in row:return {'error':'missing_name'}
    return {'rows':[{'id':r['id'],'display_name':r['name']} for r in sorted(rows,key=lambda r:r['id'])]}
''',
 'version': '''def solve(facts):
    v=facts['version'];p=facts['payload']
    if v==1:
        if 'title' not in p:return {'error':'missing'}
        return {'label':p['title']}
    if v==2:
        if 'display_name' not in p:return {'error':'missing'}
        return {'label':p['display_name']}
    return {'error':'version'}
'''
}

def main():
    B.verify();controls=[]
    for t in B.build():
        if t['track']!='engineering':continue
        result=B.program_check(t,GOOD[t['family']],hidden=True)
        assert result['pass'],(t['id'],result)
        assert not B.program_check(t,t['buggy_code'],hidden=True)['pass']
        controls.append({'task_id':t['id'],'healthy_control_pass':True,'seeded_bug_rejected':True,'asserted_cases':result['executed']})
    bad=B.program_check(B.build()[12],"def solve(facts):\n    facts['actor']['active']=False\n    return {'allowed':False}\n",hidden=True)
    assert any(x['reason']=='input mutation' for x in bad['failures'])
    integrity=[]
    if (B.HERE/'results.json').exists():
        r=B.read(B.HERE/'results.json')
        assert r['plan_sha256']==B.sha(B.HERE/'plan.json')
        for rel,digest in r['receipt_hashes'].items():assert B.sha(B.HERE/rel)==digest,rel
        assert len({t['label'] for t in r['trials']})==len(r['trials'])
        schedule={(x['task_id'],x['arm'],x['rep']) for x in B.read(B.HERE/'schedule.json')}
        assert all((t['task_id'],t['arm'],t['rep']) in schedule for t in r['trials'])
        assert all(t['correct']==bool(t['policy_accepted'] and t['audit']['pass'] and t['test_integrity']) for t in r['trials'])
        for t in r['trials']:
            for label in t['calls']:
                receipt=B.read(B.HERE/'receipts'/(label+'.json'))
                assert B.public(next(x for x in B.build() if x['id']==t['task_id'])) in receipt['prompt']
                assert 'hidden' not in receipt['prompt'].lower()
        integrity=['plan/source hashes','all receipt hashes','unique scheduled trials','success/acceptance consistency','unaltered task/facts in all model prompts','no hidden fixture in candidate prompts']
    B.write(B.HERE/'harness-audit.json',{'controls':controls,'mutation_rejected':True,'artifact_checks':integrity,'provider_calls':0})
    print(json.dumps({'controls':controls,'artifact_checks':integrity},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
