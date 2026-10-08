"""Plot measured metrics and inspect the interactive comparison in headless Edge."""
from pathlib import Path
import json
import asyncio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from playwright.async_api import async_playwright

HERE=Path(__file__).resolve().parent
FRAGMENT=Path('C:/Users/xio/.codex/visualizations/2026/10/01/01a0f8ae-157d-7e02-8126-2e0c9007a93d/flux-v3-comparison.html')


def plot():
    v=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
    names=['luna_no_rag','sol_no_rag','luna_flat','luna_v1','luna_v3_fixed','luna_v3_adaptive','sol_v3_fixed']
    labels=['Luna / no RAG','Sol / no RAG','Luna / flat RAG','Luna / v1','Luna / v3 fixed','Luna / v3 adaptive','Sol / v3 fixed']
    rows={r['arm']:r for r in v['metrics']}; colors=['#999999','#555555','#999999','#999999','#087f5b','#999999','#555555']
    fig,axes=plt.subplots(1,2,figsize=(12,5.4),sharey=True,layout='constrained')
    for ax,col,total,title in zip(axes,['passed','closed_passed'],[20,12],['Mixed tasks (n=20)','Same-information reasoning + code (n=12)']):
        vals=[rows[n][col]/total*100 for n in names]
        ax.barh(range(7),vals,color=colors,height=.6)
        ax.set_xlim(0,110);ax.set_xticks([0,25,50,75,100]);ax.set_xlabel('Complete tasks (%)');ax.set_title(title)
        ax.set_yticks(range(7),labels);ax.spines[['top','right']].set_visible(False)
        for i,n in enumerate(names):ax.text(vals[i]+1.5,i,f"{rows[n][col]}/{total}",va='center',fontsize=10)
    axes[0].invert_yaxis()
    fig.suptitle('Flux request-memory v3: actual model pilot, one completion per arm/task',fontsize=13)
    fig.savefig(HERE/'comparison.png',dpi=180);fig.savefig(HERE/'comparison.svg');plt.close(fig)


async def inspect():
    results=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless=True)
        page=await browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto((HERE/'visualization-preview.html').as_uri())
        frame=page.frame_locator('iframe')
        await frame.locator('#flux-v3-actual-20261002 .flux-chart rect').first.wait_for()
        child=next(f for f in page.frames if f!=page.main_frame)
        for width in [736,390,320]:
            await page.set_viewport_size({'width':width,'height':1500})
            await page.wait_for_timeout(150)
            r=await child.evaluate("""() => {
              const root=document.getElementById('flux-v3-actual-20261002');
              const overlaps=[],clipped=[];
              for(const svg of root.querySelectorAll('.flux-chart')) {
                const bounds=svg.getBoundingClientRect();
                const labels=[...svg.querySelectorAll('text')].map(t=>({text:t.textContent,b:t.getBoundingClientRect()}));
                for(const t of labels)if(t.b.left<bounds.left-1||t.b.right>bounds.right+1)clipped.push(t.text);
                for(let i=0;i<labels.length;i++)for(let j=i+1;j<labels.length;j++) {
                  const a=labels[i],b=labels[j];if(Math.min(a.b.right,b.b.right)-Math.max(a.b.left,b.b.left)>1 && Math.min(a.b.bottom,b.b.bottom)-Math.max(a.b.top,b.b.top)>1)overlaps.push([a.text,b.text]);
                }
              }
              return {width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,chartLabelOverlaps:overlaps,clippedLabels:clipped,buttons:root.querySelectorAll('button').length};
            }""")
            await frame.get_by_role('button',name='مسئلهٔ K00',exact=True).click()
            assert 'ناقص' in await frame.locator('.flux-task-detail').inner_text()
            await frame.get_by_role('button',name='مسئلهٔ C00',exact=True).click()
            assert 'ناقص' not in await frame.locator('.flux-task-detail').inner_text()
            assert not r['overflow'] and not r['chartLabelOverlaps'] and not r['clippedLabels'] and r['buttons']==20,r
            results.append(r)
        assert not errors,errors
        await page.set_viewport_size({'width':736,'height':1600})
        await page.wait_for_timeout(150);await page.screenshot(path=str(HERE/'visualization-preview.png'),full_page=True)
        await browser.close()
    literal=FRAGMENT.read_text(encoding='utf-8')
    assert len(literal.encode('utf-8'))<1000000 and '\\"' not in literal and '<html' not in literal.lower()
    (HERE/'visualization-checks.json').write_text(json.dumps({'viewports':results,'javascript_errors':errors,'interaction_passed':True,'fragment_bytes':len(literal.encode('utf-8'))},indent=2),encoding='utf-8')
    print(json.dumps({'visualization_passed':True,'viewports':results}))


if __name__=='__main__':plot();asyncio.run(inspect())
