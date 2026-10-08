"""Independent offline scoring from saved real provider receipts. No model calls."""
import json
from pathlib import Path
import statistics
from run_pilot import score, decode, normalize_request, Snapshot, Source, sha, HERE

def main():
    result=json.loads((HERE/'results.json').read_text(encoding='utf-8'))
    public=json.loads((HERE/'public-jobs.json').read_text(encoding='utf-8'))
    gold=json.loads((HERE/'evaluation-only.json').read_text(encoding='utf-8'))
    snapshot=Snapshot([Source(**s) for s in public['sources']],aliases=public['aliases'])
    independent=[];calls=[]
    for row in result['rows']:
        case=next(c for c in public['cases'] if c['id']==row['id']);expected=next(g for g in gold if g['id']==row['id'])
        request=normalize_request(decode(case['request']),snapshot)
        rescored=score(row['output'],request,expected)
        assert rescored==row['independent_score']
        for generation in row['generation']:
            assert generation['model_requested']=='gpt-6-luna' and generation['test_double'] is False
            assert generation['provider_completed'] and generation['tool_events']==0
            assert generation['usage'] is not None
        assert len(row['generation'])<=2
        independent.append((row['arm'],row['id'],rescored['passed']))
        calls.extend(row['generation'])
    assert len(independent)==40 and len({(a,i) for a,i,_ in independent})==40
    assert len(calls)==result['actual_calls']
    provider_files=list((HERE/'provider_runs').glob('*.json'))
    assert len(provider_files)==len(calls)
    for path in provider_files:
        provider=json.loads(path.read_text(encoding='utf-8'));events=provider['events'];receipt=provider['receipt']
        complete=[e for e in events if e.get('type')=='turn.completed']
        assert complete and receipt['exit_code']==0 and complete[-1]['usage']==receipt['usage']
    frozen=json.loads((HERE/'frozen-plan.json').read_text(encoding='utf-8'))
    assert all(sha(Path(path))==h for path,h in frozen['sha256'].items())
    assert all(sha(HERE/path)==h for path,h in frozen['pilot_sha256'].items())
    paired={}
    for case in public['cases']:
        v5=next(r for r in result['rows'] if r['arm']=='v5' and r['id']==case['id'])
        v4=next(r for r in result['rows'] if r['arm']=='v4' and r['id']==case['id'])
        paired[case['id']]={'v5':v5,'v4':v4}
    wins=sum(p['v5']['independent_score']['passed'] and not p['v4']['independent_score']['passed'] for p in paired.values())
    losses=sum(p['v4']['independent_score']['passed'] and not p['v5']['independent_score']['passed'] for p in paired.values())
    labels={
      'holdfinal-f0':'حقیقت string','holdfinal-f1':'حقیقت integer','holdfinal-f2':'مجموعهٔ literalها','holdfinal-f3':'عدد همراه واحد',
      'holdfinal-q0':'سؤال طبیعی انگلیسی','holdfinal-q1':'سؤال طبیعی فارسی','holdfinal-h0':'مالک dependency، مورد ۱','holdfinal-h1':'مالک dependency، مورد ۲',
      'Flux-limit':'Flux: max_concurrency','Flux-owner':'Flux: allowed human_owner',
      'R00':'احتمال شرطی','R01':'عضویت دقیقاً در یک مجموعه','R02':'رشتهٔ باینری بدون ۱ مجاور','R03':'باقی‌مانده‌های هم‌زمان',
      'R04':'انتظار الگوی تاس ۶۶۵','R06':'کوتاه‌ترین مسیر','C00':'canonical revision','C01':'weighted intervals',
      'C02':'shortest path code','C03':'merge intervals'
    }
    summary=result['summary'];v5,v4=summary['v5'],summary['v4']
    report=['# اجرای واقعی Luna + v5 در برابر Luna + v4','',
            '۲ اکتبر ۲۰۲۶؛ ۲۰ سؤال مشترک، مدل `gpt-6-luna`، reasoning=low، CLI حساب موجود، دو worker، حداکثر یک repair برای هر arm. Sol استفاده نشد.',
            '', '| سنجه | Luna + v5 | Luna + v4 |','|---|---:|---:|',
            f'| پاسخ درست با evaluator مستقل | {v5["passed"]}/20 | {v4["passed"]}/20 |',
            f'| پاسخ درست در تولید اول | {v5["first_passed"]}/20 | {v4["first_passed"]}/20 |',
            f'| تماس واقعی / کامل | {v5["actual_calls"]} / {v5["completed_calls"]} | {v4["actual_calls"]} / {v4["completed_calls"]} |',
            f'| repair واقعی | {v5["repairs"]} | {v4["repairs"]} |',
            f'| میانگین زمان end-to-end، ثانیه | {v5["mean_end_to_end_seconds"]:.3f} | {v4["mean_end_to_end_seconds"]:.3f} |',
            f'| میانگین توکن evidence نهایی | {v5["mean_evidence_tokens"]:.2f} | {v4["mean_evidence_tokens"]:.2f} |',
            f'| مجموع provider input tokens، شامل repair/scaffold | {v5["input_tokens_total"]} | {v4["input_tokens_total"]} |',
            f'| مجموع provider output tokens | {v5["output_tokens_total"]} | {v4["output_tokens_total"]} |',
            '', '## خروجی سؤال به سؤال','',
            '| سؤال | Luna + v5 | Luna + v4 | پاسخ مرجع |','|---|---|---|---|']
    for case in public['cases']:
        p=paired[case['id']];expected=next(g for g in gold if g['id']==case['id'])
        def display(row):
            judged=row['independent_score'];prefix='✅ ' if judged['passed'] else '❌ '
            return prefix+judged.get('display',str(judged.get('value'))).replace('|','\\|')
        reference='تست‌های اجرایی مستقل' if expected['kind']=='code' else json.dumps(expected['value'],ensure_ascii=False)
        report.append('| '+labels[case['id']]+' | '+display(p['v5'])+' | '+display(p['v4'])+' | '+reference+' |')
    report += ['', '## تفسیر و مرز نتیجه','',
       f'در {wins} سؤال v5 درست و v4 غلط بود؛ در {losses} سؤال برعکس. فقط یک تکرار و ۲۰ سؤال داریم؛ این برتری/افت کوچک را به توانایی عمومی مدل تعمیم نمی‌دهیم.',
       '۱۰ سؤال حافظه شامل ۸ سؤال مصنوعی از workload قبلی و ۲ سؤال از snapshot منجمد واقعی Flux است. ۶ مسئلهٔ reasoning و ۴ مسئلهٔ کد از آزمون قدیمی‌اند و holdout تازه محسوب نمی‌شوند. تست‌های نمونهٔ عمومی کد به هر دو arm داده شدند؛ ۱۰ تست اضافه فقط در evaluator بودند. gold factual و numeric هیچ‌وقت وارد prompt یا repair نشد.',
       'هر دو engine روی همان canonical unitهای v5 ایندکس شدند؛ این مقایسه مزیت parser/canonicalization را مستقل نمی‌سنجد. سؤال و تست‌های عمومی یکسان‌اند، اما schema خروجی، metadata بسته و verifier مختص هر نسخه‌اند. اثر هر جزء به‌تنهایی با این آزمایش قابل جداسازی نیست.',
       'v5 برای reasoning فاقد checker معتبر وضعیت unverified دارد؛ این وضعیت را PASS حساب نکردیم. پاسخ‌ها با gold مستقل سنجیده شدند. v4 verifier زیررشته‌ای می‌تواند جواب صحیح closed/code را رد کند یا null را بپذیرد؛ native verifier و کیفیت واقعی پاسخ دو سنجهٔ جدا هستند.',
       'مدت end-to-end برای هر job شامل آماده‌سازی و تماس‌های provider است؛ زمان صف threadpool و ساخت اولیهٔ index را شامل نمی‌شود. اجرا با دو worker هم‌زمان بود، پس زمان‌ها تخمین یک محیط/نوبت‌اند. input tokenهای provider شامل scaffold پنهان CLI است و برابر evidence tokens نیست.',
       'همهٔ تماس‌های ثبت‌شده turn.completed، exit=0 و بدون tool event بودند. هزینهٔ دلاری از این رسیدها معلوم نیست؛ صفر ادعا نمی‌کنیم. Flux production و فایل‌های منجمد v3/v4/v5 تغییر نکردند.',
       '', 'خروجی خام هر سؤال در `outputs/`، رویداد واقعی provider در `provider_runs/`، دادهٔ عمومی در `public-jobs.json` و gold در `evaluation-only.json` نگه داشته شد. `run.lock` جلوی بازاجرای ناخواستهٔ تماس‌ها را می‌گیرد.'
    ]
    (HERE/'REPORT.fa.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    verification={'independent_scores_match':True,'paired_tasks':20,'actual_completed_calls':len(calls),'all_native_luna_no_tools':True,
                  'frozen_runtime_and_pilot_hashes_match':True,'v5_only_wins':wins,'v4_only_wins':losses,'billing_usd':None,
                  'results_sha256':sha(HERE/'results.json'),'source_public_jobs_sha256':sha(HERE/'public-jobs.json')}
    (HERE/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
    print(json.dumps({'summary':summary,'verification':verification},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
