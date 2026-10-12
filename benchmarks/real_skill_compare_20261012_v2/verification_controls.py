"""Real deterministic negative controls. No claimed provider/model safety score."""
import json
import benchmark as B

def main():
    B.verify();task=next(t for t in B.build() if t['family']=='count');facts=task['facts']
    wrong=B.oracle(task)['count']+1
    correlated={'refs':list(facts),'code':f'''def solve(facts):
    return {{"count":{wrong},"digit_sum_total":facts["length"]}}
def check(answer,facts):
    return answer["count"]=={wrong} and answer["digit_sum_total"]==facts["length"]
'''}
    check=B.validate(correlated,facts)
    assert check['pass'],'self-consistent generated checker control should pass internal worker'
    assert not B.equal(check['answer'],B.oracle(task)),'full external audit must reject wrong correlated answer'
    result=[{'control':'correlated_wrong_solver_checker','internal_checker_pass':True,'independent_full_audit_pass':False}]
    badcodes={
      'forbidden_import':'import os\ndef solve(facts): return facts\ndef check(answer,facts): return answer==facts',
      'forbidden_eval':'def solve(facts): return eval(str(facts["length"]))\ndef check(answer,facts): return answer==facts["length"]',
      'private_attribute':'def solve(facts): return facts.__class__\ndef check(answer,facts): return answer==facts',
      'constant_checker':'def solve(facts): return facts\ndef check(answer,facts): return True',
      'checker_calls_solve':'def solve(facts): return facts\ndef check(answer,facts): return answer==solve(facts)'}
    for name,code in badcodes.items():
        r=B.validate({'refs':list(facts),'code':code},facts);assert not r['pass'],name
        result.append({'control':name,'rejected':True,'reason':r.get('reason')})
    for name,refs in [('missing_ref',list(facts)[1:]),('duplicate_ref',list(facts)+[next(iter(facts))])]:
        r=B.validate(dict(correlated,refs=refs),facts);assert not r['pass'];result.append({'control':name,'rejected':True})
    result.append({'control':'guard_exhaustive_failed_verification','cases':9,'pass':True})
    for choice in ['accept','escalate','stop']:
        for attempt in range(3):assert B.guard(choice,False,attempt)==('escalate' if attempt<2 else 'stop')
    B.write(B.HERE/'verification-controls.json',{'provider_calls':0,'scope':'deterministic runner/guard controls only, not model security or OS isolation','controls':result})
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
