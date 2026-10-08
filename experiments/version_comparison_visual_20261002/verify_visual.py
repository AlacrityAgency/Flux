"""Check comparison source numbers, responsive layout, theme and version selection."""
import asyncio
import hashlib
import json
from pathlib import Path
from playwright.async_api import async_playwright

HERE=Path(__file__).resolve().parent
EXP=HERE.parent
FRAGMENT=Path('C:/Users/xio/.codex/visualizations/2026/10/01/01a0f8ae-157d-7e02-8126-2e0c9007a93d/flux-memory-versions.html')


def check_sources():
    content=FRAGMENT.read_text(encoding='utf-8')
    r4=json.loads((EXP/'request_memory_v4_20261002/holdout-results.json').read_text(encoding='utf-8'))
    r3=json.loads((EXP/'request_memory_v3_20261002/results.json').read_text(encoding='utf-8'))
    assert all(str(r4['pooled'][arm][key]) in content for arm in ['v3_fixed','v3_adaptive','v4'] for key in ['median_ms','mean_pack_tokens'])
    assert [r3['summary'][a]['passed'] for a in ['luna_v1','luna_v3_fixed','sol_no_rag','sol_v3_fixed']]==[13,13,12,19]
    assert [r3['summary'][a]['by_family']['closed_reasoning']['passed']+r3['summary'][a]['by_family']['executable_code']['passed'] for a in ['luna_v1','luna_v3_fixed','sol_no_rag','sol_v3_fixed']]==[6,6,12,12]
    assert len(content.encode())<1000000 and '<html' not in content.lower() and '\\"' not in content
    names=['diffusion_memory_20261001/REPORT.fa.md','diffusion_memory_v2_20261001/REPORT.fa.md',
           'request_memory_v3_20261002/results.json','request_memory_v4_20261002/holdout-results.json',
           'request_memory_v4_review_20261002/review-results.json','request_memory_v5_design_20261002/ALGORITHM.fa.md']
    (HERE/'sources.json').write_text(json.dumps({n:{'sha256':hashlib.sha256((EXP/n).read_bytes()).hexdigest()} for n in names},indent=2),encoding='utf-8')


async def inspect():
    results=[];errors=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless=True)
        page=await browser.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto((HERE/'preview.html').as_uri())
        frame=page.frame_locator('iframe');await frame.locator('.flux-version-flow li').first.wait_for()
        child=next(f for f in page.frames if f!=page.main_frame)
        for theme in ['light','dark']:
            await page.emulate_media(color_scheme=theme)
            for width in [736,390,320]:
                await page.set_viewport_size({'width':width,'height':1400});await page.wait_for_timeout(120)
                r=await child.evaluate("""() => {
                  const root=document.getElementById('flux-memory-versions-20261002');let overlaps=[],clipped=[];
                  for(const svg of root.querySelectorAll('.flux-version-chart')) {
                    const bounds=svg.getBoundingClientRect(),labels=[...svg.querySelectorAll('text')].map(t=>({text:t.textContent,b:t.getBoundingClientRect()}));
                    for(const t of labels)if(t.b.left<bounds.left-1||t.b.right>bounds.right+1)clipped.push(t.text);
                    for(let i=0;i<labels.length;i++)for(let j=i+1;j<labels.length;j++) {
                      const a=labels[i],b=labels[j];if(Math.min(a.b.right,b.b.right)-Math.max(a.b.left,b.b.left)>1&&Math.min(a.b.bottom,b.b.bottom)-Math.max(a.b.top,b.b.top)>1)overlaps.push([a.text,b.text]);
                    }
                  }
                  return {contentWidth:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,overlaps,clipped};
                }""")
                for version in ['v1','v2','v3','v4','v5']:
                    await frame.locator(f'[data-version="{version}"]').click()
                    assert await frame.locator(f'[data-version="{version}"]').get_attribute('aria-pressed')=='true'
                    assert await frame.locator('.flux-version-flow li').count()==4
                    assert await frame.locator('.flux-version-detail').inner_text()
                assert 'فقط طراحی' in await frame.locator('.flux-version-detail').inner_text()
                assert not r['overflow'] and not r['clipped'] and not r['overlaps'],r
                results.append({'theme':theme,'viewport':width,**r})
            await page.set_viewport_size({'width':736,'height':1600});await page.wait_for_timeout(120)
            await page.screenshot(path=str(HERE/f'preview-{theme}.png'),full_page=True)
        assert not errors,errors
        await browser.close()
    result={'source_numbers_match':True,'version_selection_passed':True,'checks':results,'javascript_errors':errors,'model_calls':0}
    (HERE/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':check_sources();asyncio.run(inspect())
