"""Inspect HTML print layout, export the same source to PDF, render every PDF page."""
import asyncio
import hashlib
import json
from pathlib import Path
import pypdfium2 as pdfium
from pypdf import PdfReader
from PIL import Image,ImageDraw
from playwright.async_api import async_playwright

HERE=Path(__file__).resolve().parent
HTML=HERE/'Flux_Memory_Research_FA.html'
PDF=HERE/'Flux_Memory_Research_FA.pdf'
QA=HERE/'qa'
QA.mkdir(exist_ok=True)

async def render():
    errors=[];checks=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless=True)
        page=await browser.new_page(viewport={'width':1180,'height':1350},device_scale_factor=1)
        page.on('pageerror',lambda error:errors.append(str(error)))
        await page.goto(HTML.as_uri());await page.evaluate('document.fonts.ready')
        assert await page.locator('.sheet').count()==17
        for version in ('v1','v2','v3','v4','v5'):
            await page.locator('#version-select').select_option(version)
            assert await page.locator('#version-detail').inner_text()
        for width in (1180,736,390,320):
            await page.set_viewport_size({'width':width,'height':1350});await page.wait_for_timeout(80)
            check=await page.evaluate('''() => ({width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,fontLoaded:document.fonts.check('14px Vazir')})''')
            assert not check['overflow'] and check['fontLoaded'],check
            checks.append(check)
        await page.set_viewport_size({'width':1180,'height':1350})
        await page.emulate_media(media='print');await page.evaluate('document.fonts.ready')
        layout=await page.evaluate('''() => [...document.querySelectorAll('.sheet')].map(sheet=>{
          const body=sheet.querySelector('.page-body').getBoundingClientRect(),foot=sheet.querySelector('.page-foot').getBoundingClientRect();
          const sb=sheet.getBoundingClientRect();const clipped=[];const svgOverlaps=[];
          for(const svg of sheet.querySelectorAll('svg')){
            const box=svg.getBoundingClientRect(),labels=[...svg.querySelectorAll('text')].map(t=>({text:t.textContent,b:t.getBoundingClientRect()}));
            for(const t of labels)if(t.b.left<box.left-1||t.b.right>box.right+1||t.b.top<box.top-1||t.b.bottom>box.bottom+1)clipped.push(t.text);
            for(let i=0;i<labels.length;i++)for(let j=i+1;j<labels.length;j++){
              const a=labels[i],b=labels[j];if(Math.min(a.b.right,b.b.right)-Math.max(a.b.left,b.b.left)>1&&Math.min(a.b.bottom,b.b.bottom)-Math.max(a.b.top,b.b.top)>1)svgOverlaps.push([a.text,b.text]);
            }
          }
          return {id:sheet.id,page:Number(sheet.dataset.page),height:sb.height,bodyBottom:body.bottom-sb.top,footerTop:foot.top-sb.top,footerGap:foot.top-body.bottom,clipped,svgOverlaps};
        })''')
        (QA/'layout-initial.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding='utf-8')
        failures=[r for r in layout if r['footerGap']<10 or r['clipped'] or r['svgOverlaps']]
        if failures:
            print(json.dumps({'layout_failures':failures},ensure_ascii=False,indent=2))
            await page.screenshot(path=str(QA/'print-layout.png'),full_page=True)
            await browser.close()
            raise RuntimeError('Fix layout before PDF export')
        await page.pdf(path=str(PDF),format='A4',print_background=True,prefer_css_page_size=True,
                       margin={'top':'0','right':'0','bottom':'0','left':'0'},display_header_footer=False,
                       tagged=True,outline=True)
        assert not errors,errors
        await browser.close()
    return checks,layout,errors

def inspect_pdf():
    reader=PdfReader(PDF)
    assert len(reader.pages)==17,len(reader.pages)
    counts=[]
    for i,page in enumerate(reader.pages):
        text=page.extract_text() or ''
        assert len(text)>200,(i+1,len(text))
        assert '\ufffd' not in text,(i+1,'missing glyph')
        counts.append(len(text))
    doc=pdfium.PdfDocument(str(PDF));tiles=[]
    for i in range(len(doc)):
        image=doc[i].render(scale=1.25).to_pil().convert('RGB')
        image.save(QA/f'page-{i+1:02d}.png')
        thumb=image.copy();thumb.thumbnail((240,340))
        tile=Image.new('RGB',(258,375),'#e5e9e2');tile.paste(thumb,((258-thumb.width)//2,12));ImageDraw.Draw(tile).text((12,355),f'Page {i+1:02d}',fill='#203126')
        tiles.append(tile)
    for batch in range(3):
        sub=tiles[batch*6:(batch+1)*6]
        contact=Image.new('RGB',(258*3,375*2),'#e5e9e2')
        for j,tile in enumerate(sub):contact.paste(tile,((j%3)*258,(j//3)*375))
        contact.save(QA/f'contact-{batch+1}.png')
    return {'pages':len(reader.pages),'text_chars_per_page':counts,'all_pages_rendered':True}

if __name__=='__main__':
    checks,layout,errors=asyncio.run(render())
    pdf=inspect_pdf()
    result={'html_checks':checks,'print_layout':layout,'javascript_errors':errors,'pdf':pdf,
            'html_sha256':hashlib.sha256(HTML.read_bytes()).hexdigest(),'pdf_sha256':hashlib.sha256(PDF.read_bytes()).hexdigest(),
            'pdf_bytes':PDF.stat().st_size,'svg_figures':HTML.read_text(encoding='utf-8').count('<svg'),
            'actual_new_model_calls':0}
    (HERE/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='print_layout'},ensure_ascii=False,indent=2))
