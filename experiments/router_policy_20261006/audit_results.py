"""Post-run audit. Does not modify frozen policy code, tasks, or receipts.

Unknown timeout usage stays unknown. Known costs are lower bounds, not totals.
Transport failures are distinguished from solver/verifier failures.
"""
import hashlib,json
from pathlib import Path
import benchmark as B

HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    B.verify_frozen()
    base=read(HERE/'results.json')
    summaries={}
    for arm in B.ARMS:
        ts=[read(p) for p in sorted((HERE/'trials').glob('*__'+arm+'.json'))]
        pairs=[(label,read(HERE/'receipts'/(label+'.json'))) for t in ts for label in t['labels']]
        costs=[B.cost(r) for _,r in pairs]
        result=base['summary'][arm].copy()
        result.update(known_usage_cost_lower_bound_usd=sum(x for x in costs if x is not None),
           unknown_usage_call_count=sum(x is None for x in costs),
           unknown_usage_labels=[label for label,r in pairs if B.cost(r) is None],
           provider_failure_labels=[label for label,r in pairs if not r['completed']],
           known_usage_no_cache_lower_bound_usd=sum(B.cost(r,True) for _,r in pairs if B.cost(r,True) is not None),
           solver_check_failures=sum(not c['pass'] and not c['reason'].startswith('ValueError: Provider incomplete') for t in ts for c in t['checks']),
           provider_check_failures=sum(not c['pass'] and c['reason'].startswith('ValueError: Provider incomplete') for t in ts for c in t['checks']),
           all_labels=[label for label,_ in pairs])
        for _,r in pairs:
            if r['usage']:
                u=r['usage']
                assert 0<=u['cached_input_tokens']<=u['input_tokens']
                assert u.get('reasoning_output_tokens',0)<=u['output_tokens']
        summaries[arm]=result
    junior,goat=summaries['junior'],summaries['goat']
    ratio_upper=(junior['api_equivalent_usd']/goat['known_usage_cost_lower_bound_usd']
                 if junior['api_equivalent_usd'] is not None and goat['known_usage_cost_lower_bound_usd']>0 else None)
    verdict=('supported_on_this_pilot' if base['15x_supported_on_this_pilot'] else
             'refuted_on_cost_bound' if ratio_upper is not None and ratio_upper<15 else
             'inconclusive' if junior['unknown_usage_call_count'] or goat['unknown_usage_call_count'] or not base['equal_quality_complete'] else
             'not_observed_on_this_pilot')
    comparable=[]
    for tid in ['T1','T2','T3','T4','T5','T6']:
        jp,gp=[HERE/'trials'/(tid+'__'+arm+'.json') for arm in ['junior','goat']]
        if not jp.exists() or not gp.exists():continue
        jt,gt=read(jp),read(gp)
        jr,gr=[[read(HERE/'receipts'/(label+'.json')) for label in t['labels']] for t in [jt,gt]]
        if jt['audit']['pass'] and gt['audit']['pass'] and all(B.cost(r) is not None for r in jr+gr):
            comparable.append({'task':tid,'junior_usd':sum(B.cost(r) for r in jr),'goat_usd':sum(B.cost(r) for r in gr)})
    comparable_ratio=(sum(t['junior_usd'] for t in comparable)/sum(t['goat_usd'] for t in comparable)) if comparable else None
    receipts={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((HERE/'receipts').glob('*.json'))}
    result={'summary':summaries,'claim_verdict':verdict,'equal_quality_complete':base['equal_quality_complete'],
       'junior_goat_exact_api_equivalent_ratio':base['junior_over_goat_api_equivalent_ratio'],
       'junior_goat_cost_ratio_upper_bound':ratio_upper,'actual_paid_usd':None,
       'complete_24_trials':base['completed_trial_count']==24,'receipt_hashes':receipts,
       'frozen_hashes_verified':True,'limits':'One sample per task/policy. Unknown usage is not zero. Dollar costs are API-equivalent estimates, not paid invoices. No tools allowed in model calls.'}
    result['exploratory_known_usage_equal_correctness_subset']={'tasks':comparable,'cost_ratio':comparable_ratio,
       'selection':'Post-run excludes any task with unknown usage in Junior or GOAT or incorrect final answer. Not the full six-task result; may be biased.'}
    B.write(HERE/'audited-results.json',result)
    report=['# نتیجهٔ ممیزی benchmark محلی — ۶ اکتبر ۲۰۲۶','',
       'چهار سیاست، شش تسک یکسان، یک اجرا در هر سلول. تمام تماس‌های Router و retry در سیاست مربوط حساب شده‌اند.',
       'دلار معادل API با تعرفهٔ Standard است؛ اجرا با حساب Codex بوده و مبلغ پرداخت‌شده معلوم نیست.','',
       '| روش | صحیح در ممیزی | retry | تماس | خطای اجرای سرویس | حداقل دلار از usage معلوم | تماس با usage نامعلوم |',
       '|---|---:|---:|---:|---:|---:|---:|']
    for arm,s in summaries.items():
        report.append(f"| {arm} | {s['correct']}/{s['tasks']} | {s['retries']} | {s['calls']} | {s['provider_failures']} | {s['known_usage_cost_lower_bound_usd']:.6f} | {s['unknown_usage_call_count']} |")
    report += ['',f'حکم ادعای حداقل ۱۵ برابر: `{verdict}`',
       f'نسبت دقیق Junior به GOAT: {result["junior_goat_exact_api_equivalent_ratio"]}',
       f'سقف قابل اثبات نسبت با هزینهٔ معلوم Junior و حداقل هزینهٔ GOAT: {ratio_upper}',
       f'پایان هر ۲۴ اجرای تسک: {result["complete_24_trials"]}',
       '', 'هزینهٔ معلوم در سطر دارای usage نامعلوم فقط کران پایین است؛ تقسیم دو کران پایین، نسبت هزینهٔ کل را ثابت نمی‌کند.',
       'خطای شبکه/timeout از جواب نادرست مدل جداست. اگر Junior به علت عدم تکمیل سرویس ۶/۶ نشود، فرض کیفیت برابر برقرار نیست.',
       'این Router از Luna استفاده می‌کند و Laya در این آزمایش اجرا نشده است.',
       'تسک‌ها مصنوعی و ابزارهای مدل خاموش‌اند؛ نتیجه به ترافیک واقعی یا benchmark عامل کدنویسی با ابزار تعمیم داده نمی‌شود.',
       '', '## مقایسهٔ فرعی فقط با دادهٔ کامل','',
       'پس از اجرا، فقط تسک‌هایی انتخاب شده‌اند که هم Junior و هم GOAT درست پاسخ داده‌اند و تمام usage آنها معلوم است. این انتخاب پس از مشاهدهٔ نتایج است و می‌تواند سوگیری داشته باشد؛ جایگزین نتیجهٔ شش‌تسک نیست.',
       'تسک‌های این زیرمجموعه: '+', '.join(t['task'] for t in comparable),
       f'نسبت هزینهٔ Junior به GOAT در این زیرمجموعه: {comparable_ratio}',
       '', '## خطاها','']
    for p in sorted((HERE/'trials').glob('*.json')):
        t=read(p)
        failures=[c['reason'] for c in t['checks'] if not c['pass']]
        if failures:report.append(f"- {t['task']} / {t['arm']}: "+'؛ '.join(failures))
    (HERE/'AUDIT.fa.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['claim_verdict','complete_24_trials','junior_goat_exact_api_equivalent_ratio','junior_goat_cost_ratio_upper_bound']},ensure_ascii=False))

if __name__=='__main__':main()
