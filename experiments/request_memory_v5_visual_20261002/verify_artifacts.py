"""Validate the final frozen run and visual against measured sources."""
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from playwright.async_api import async_playwright

HERE=Path(__file__).resolve().parent
EXP=HERE.parent
V5=EXP/'request_memory_v5_20261002'
FRAGMENT=Path('C:/Users/xio/.codex/visualizations/2026/10/01/01a0f8ae-157d-7e02-8126-2e0c9007a93d/flux-v5-results.html')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_sources():
    manifest=json.loads((V5/'runs/final/frozen-manifest.json').read_text(encoding='utf-8'))
    assert all(sha(EXP/path)==value for path,value in manifest['sha256'].items())
    archived=json.loads((V5/'frozen_runs/r1/frozen-manifest.json').read_text(encoding='utf-8'))
    for path,value in archived['sha256'].items():
        original=EXP/path
        local=V5/'frozen_runs/r1'/original.name if original.parent==V5 else original
        assert sha(local)==value,(path,'archive mismatch')
    frozen_result=V5/'runs/final/holdout-results.json';before=sha(frozen_result)
    refusal=subprocess.run([sys.executable,'-X','utf8',str(V5/'benchmark_v5.py'),'holdout'],capture_output=True,text=True,encoding='utf-8')
    assert refusal.returncode!=0 and 'FileExistsError' in refusal.stderr and sha(frozen_result)==before
    data=json.loads(frozen_result.read_text(encoding='utf-8'));content=FRAGMENT.read_text(encoding='utf-8')
    for arm in ('v4','v5'):
        assert all(str(data['summary'][arm][key]) in content for key in ('median_ms','p95_ms','mean_tokens'))
    assert data['summary']['v4']['evidence_complete']==140 and data['summary']['v5']['evidence_complete']==150
    assert data['summary']['v4']['route_correct']==198 and data['summary']['v5']['route_correct']==240
    assert data['actual_model_calls']==0 and data['summary']['fixture_status_correct']==240
    assert len(content.encode())<1000000 and '<html' not in content.lower() and '\\"' not in content
    old=json.loads((EXP/'request_memory_v3_20261002/results.json').read_text(encoding='utf-8'))
    assert [old['summary'][k]['passed'] for k in ('luna_v3_fixed','sol_no_rag','sol_v3_fixed')]==[13,12,19]
    return {'final_frozen_files_match':len(manifest['sha256']),'r1_archive_matches':True,
            'holdout_rerun_refused_without_overwrite':True,'source_metrics_match':True,'actual_model_calls':0}

async def inspect():
    results=[];errors=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless=True)
        page=await browser.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto((HERE/'preview.html').as_uri())
        frame=page.frame_locator('iframe');await frame.locator('.v5-chart text').first.wait_for()
        child=next(f for f in page.frames if f!=page.main_frame)
        for theme in ('light','dark'):
            await page.emulate_media(color_scheme=theme)
            for width in (736,390,320):
                await page.set_viewport_size({'width':width,'height':1700});await page.wait_for_timeout(150)
                check=await child.evaluate('''() => {
                  const root=document.getElementById('flux-v5-results-20261002'),overlaps=[],clipped=[];
                  for(const svg of root.querySelectorAll('.v5-chart')) {
                    const bounds=svg.getBoundingClientRect();
                    const labels=[...svg.querySelectorAll('text')].map(t=>({text:t.textContent,b:t.getBoundingClientRect()}));
                    for(const t of labels) if(t.b.left<bounds.left-1||t.b.right>bounds.right+1)clipped.push(t.text);
                    for(let i=0;i<labels.length;i++)for(let j=i+1;j<labels.length;j++){
                      const a=labels[i],b=labels[j];if(Math.min(a.b.right,b.b.right)-Math.max(a.b.left,b.b.left)>1&&Math.min(a.b.bottom,b.b.bottom)-Math.max(a.b.top,b.b.top)>1)overlaps.push([a.text,b.text]);
                    }
                  }
                  return {width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,overlaps,clipped,charts:root.querySelectorAll('.v5-chart').length};
                }''')
                for key in ('entity','field','number','empty','partial','citation','math','budget','memory'):
                    await frame.locator('#v5-case-select').select_option(key)
                    assert await frame.locator('#v5-case-state').inner_text()
                await frame.locator('#v5-case-select').select_option('entity')
                assert await frame.locator('#v5-case-state').inner_text()=='contradicted'
                assert check['charts']==6 and not check['overflow'] and not check['overlaps'] and not check['clipped'],check
                results.append({'theme':theme,'viewport':width,**check})
            await page.set_viewport_size({'width':736,'height':1900});await page.wait_for_timeout(100)
            await page.screenshot(path=str(HERE/f'preview-{theme}.png'),full_page=True)
        assert not errors,errors
        await browser.close()
    return {'checks':results,'javascript_errors':errors,'all_nine_cases_update':True}

if __name__=='__main__':
    result={**verify_sources(),**asyncio.run(inspect())}
    (HERE/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))
