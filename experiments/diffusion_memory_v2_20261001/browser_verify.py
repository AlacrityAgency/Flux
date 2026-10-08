"""Headless rendering check for this self-contained local artifact only."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE=Path(__file__).resolve().parent
EDGE=Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
def main():
    errors=[];results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=str(EDGE),headless=True)
        page=browser.new_page(viewport={'width':1280,'height':1000})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto((HERE/'graph-explorer.html').as_uri())
        for i in range(6):
            page.select_option('#corpus',str(i))
            count=page.locator('#edge option').count()
            assert count>0
            page.select_option('#edge',str(min(2,count-1)))
            assert page.locator('#left').inner_text().strip()
            assert page.locator('#right').inner_text().strip()
            assert page.locator('#matrix tr').count()==6
            before=page.locator('#leftScore').inner_text()
            page.locator('#w0').evaluate("e=>{e.value=100;e.dispatchEvent(new Event('input'))}")
            after=page.locator('#leftScore').inner_text()
            assert before!=after or i>0 # Slider may already be at 100 after first loop.
            results.append({'view':i,'sample_edges':count,'matrix_rows':6})
        page.select_option('#corpus','1')
        page.screenshot(path=str(HERE/'graph-explorer-preview.png'),full_page=True)
        for width in [1280,390]:
            page.set_viewport_size({'width':width,'height':900})
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        browser.close()
    assert not errors
    (HERE/'browser-verification.json').write_text(json.dumps({'views':results,'javascript_errors':errors,'horizontal_overflow':False,'widths':[1280,390]},ensure_ascii=False),encoding='utf-8')
    print('6 graph views, matrix/slider/source previews and mobile overflow: passed')
if __name__=='__main__':main()
