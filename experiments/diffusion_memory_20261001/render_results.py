"""Research artifacts from saved measurements; never alters candidates or source."""
import csv
import html
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from memory import Atom, ENC, GraphRetriever, dumps, sha, tokens

HERE=Path(__file__).resolve().parent


def main():
    full=json.loads((HERE/'results.json').read_text(encoding='utf-8'))
    ablation=json.loads((HERE/'ablation-results.json').read_text(encoding='utf-8'))
    results={r['corpus']:r for r in full['results']}
    records=[]
    for corpus,r in results.items():
        for budget,arms in r['summary'].items():
            for arm,metric in {**arms,**ablation[corpus][budget]}.items():
                records.append({'corpus':corpus,'budget':budget,'arm':arm,**metric})
    with (HERE/'metrics.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    colors=['#bd4242','#277c58']
    for ax,(name,title) in zip(axes, [('synthetic_1m','Controlled 1M-token corpus'),('flux_real','Flux source-anchor checks (12 tasks)')]):
        r=results[name]
        for prefix,label,color in [('graph_only','Compressed graph only',colors[0]),('graph_archive','Graph + source index; early stop',colors[1])]:
            caps=[3000,10000,30000,100000]
            xs=[r['levels'][str(c)]['graph_tokens'] for c in caps]
            ys=[r['summary']['3000'][f'{prefix}_{c}']['complete_rate']*100 for c in caps]
            ax.plot(xs,ys,'o-',label=label,color=color,linewidth=2)
        flat=r['summary']['3000']['flat_atoms_expand']['complete_rate']*100
        ax.axhline(flat,label='Flat atom + same adaptive policy',color='#606975',linestyle='--')
        ax.scatter([r['levels']['100000']['graph_tokens']],
                   [ablation[name]['3000']['graph_archive_full']['complete_rate']*100],
                   marker='^',s=95,color='#1e5489',label='Graph + source; fixed-budget control',zorder=5)
        if name=='flux_real':ax.axhline(r['summary']['3000']['flux_current_selector']['complete_rate']*100,label='Frozen Flux selector',color='#3e5f9b',linestyle=':')
        ax.set_xscale('log');ax.set_ylim(-3,105);ax.set_title(title)
        ax.set_xlabel('Entire active graph: local tokens');ax.set_ylabel('Tasks with all required evidence (%)')
        ax.grid(alpha=.2);ax.legend(fontsize=8,loc='upper left')
    fig.suptitle('Repeated compression loses detail; retrieval to original sources is separate storage',fontsize=12)
    fig.savefig(HERE/'compression-results.png',dpi=180);fig.savefig(HERE/'compression-results.svg')
    plt.close(fig)
    # Exactly 100 input slices of 10,000 encoded tokens; no content padding.
    raw=(HERE/'snapshots/synthetic_1m/raw.txt').read_text(encoding='utf-8')
    tids=ENC.encode(raw,disallowed_special=());blockdir=HERE/'snapshots/synthetic_1m/input_blocks';blockdir.mkdir(exist_ok=True)
    sizes=[];blocks=[]
    for i in range(100):
        text=ENC.decode(tids[i*10000:(i+1)*10000]);sizes.append(tokens(text));blocks.append(text)
        (blockdir/f'block_{i:03d}.txt').write_text(text,encoding='utf-8')
    if ''.join(blocks)!=raw or any(s!=10000 for s in sizes):raise AssertionError('Input block round trip failed')
    integrity={'input_tokens':tokens(raw),'blocks':100,'each_input_block_tokens':10000,
               'input_sha256':sha(raw),'input_block_round_trip':True,
               'primary_runs':sum(v['tasks'] for r in results.values() for arms in r['summary'].values() for v in arms.values()),
               'diagnostic_runs':sum(v['tasks'] for corp in ablation.values() for arms in corp.values() for v in arms.values()),
               'budget_violations':sum(r['budget_violations'] for r in records),
               'gold_outside_graphs':True,'model_calls':0,'main_flux_edited':False}
    plan=json.loads((HERE/'frozen-plan.json').read_text(encoding='utf-8'))
    integrity['candidate_hashes_still_match']={n:sha((HERE/n).read_text(encoding='utf-8'))==h for n,h in plan['candidate_hashes'].items()}
    (HERE/'verification.json').write_text(dumps(integrity),encoding='utf-8')
    # Optional interactive graph: precomputed personalized diffusion for several queries.
    directory=HERE/'snapshots/synthetic_1m'
    atoms=[Atom(**a) for a in json.loads((directory/'atoms.json').read_text(encoding='utf-8'))];byid={a.ident:a for a in atoms}
    graph_payload=json.loads((directory/'graph_100000.json').read_text(encoding='utf-8'))
    retained=[byid[c[0]] for n in graph_payload['nodes'] for c in n['atoms']]
    graph=GraphRetriever({'payload':graph_payload,'atoms':retained},atoms)
    tasks=json.loads((HERE/'evaluation_only/synthetic_1m_tasks.json').read_text(encoding='utf-8'))
    samples=[tasks[i] for i in [0,1,3,80,112]]
    data={'tokens':results['synthetic_1m']['levels']['100000']['graph_tokens'],
          'nodes':[{'id':n['id'],'blocks':n['blocks'],'count':len(n['atoms']),
                    'route':n['route'],'preview':[c[3] for c in n['atoms'][:4]]} for n in graph_payload['nodes']],
          'edges':graph_payload['edges'],
          'samples':[{'query':t['query'],'weights':graph.ranks(t['query']+' '+' '.join(t['criteria'])).tolist()} for t in samples]}
    template='''<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>آزمایش گراف حافظه Flux</title><style>body{margin:0;background:#0b1115;color:#eaf0ed;font:16px Tahoma,Arial}main{max-width:1200px;margin:auto;padding:24px}h1{font-size:24px}p{line-height:1.9;color:#b7c6c0}select,button{padding:12px;background:#18252b;color:white;border:1px solid #486058;border-radius:8px;max-width:100%}.grid{display:grid;grid-template-columns:2fr 1fr;gap:18px}canvas{width:100%;background:#101c23;border-radius:14px}aside{padding:18px;background:#17242a;border-radius:14px;white-space:pre-wrap;line-height:1.8;font-size:13px}.note{font-size:13px}@media(max-width:700px){.grid{grid-template-columns:1fr}main{padding:12px}}</style><main><h1>نقشهٔ حافظهٔ آزمایشی Flux</h1><p>۱۰۰ شاخه از منبع کنترل‌شدهٔ یک‌میلیون‌توکنی. اندازهٔ کل نمایش گراف: <b id="size"></b> توکن. روی شاخه کلیک کن تا نمونهٔ متن و منشأ آن را ببینی.</p><select id="q"></select><p class="note">رنگ و اندازه، ارتباط با سؤالِ انتخاب‌شده را از انتشار وزن روی گراف نشان می‌دهند؛ اهمیت سازمانی و صحت تصمیم از این وزن اثبات نمی‌شود. یال‌ها شباهت واژگانی‌اند. منبع اصلی و ایندکس کامل خارج از این گراف نگهداری می‌شوند.</p><div class="grid"><canvas id="graph" width="900" height="620"></canvas><aside id="detail">برای دیدن شاخه، یک گره را انتخاب کن.</aside></div></main><script>const DATA=__DATA__;const c=document.getElementById('graph'),ctx=c.getContext('2d'),select=document.getElementById('q');document.getElementById('size').textContent=DATA.tokens.toLocaleString('fa-IR');DATA.samples.forEach((s,i)=>{const o=document.createElement('option');o.value=i;o.textContent=s.query;select.append(o)});const pos=DATA.nodes.map((n,i)=>({x:50+(i%10)*87,y:45+Math.floor(i/10)*58}));function draw(){const ws=DATA.samples[Number(select.value)].weights,m=Math.max(...ws,0.00001);ctx.clearRect(0,0,900,620);ctx.strokeStyle='#2b424a';DATA.edges.forEach(([a,b,w])=>{ctx.beginPath();ctx.moveTo(pos[a].x,pos[a].y);ctx.lineTo(pos[b].x,pos[b].y);ctx.globalAlpha=.2+.4*w;ctx.stroke()});ctx.globalAlpha=1;DATA.nodes.forEach((n,i)=>{const t=ws[i]/m,r=9+16*Math.sqrt(t);ctx.fillStyle=`rgb(${40+100*t},${90+150*t},${100+90*t})`;ctx.beginPath();ctx.arc(pos[i].x,pos[i].y,r,0,Math.PI*2);ctx.fill();ctx.fillStyle='#eff';ctx.font='10px Arial';ctx.textAlign='center';ctx.fillText(n.id,pos[i].x,pos[i].y+3)})}select.addEventListener('change',draw);c.addEventListener('click',e=>{const rect=c.getBoundingClientRect(),x=(e.clientX-rect.left)*900/rect.width,y=(e.clientY-rect.top)*620/rect.height;let best=-1,d=25;pos.forEach((p,i)=>{const n=Math.hypot(p.x-x,p.y-y);if(n<d){best=i;d=n}});if(best>=0){const n=DATA.nodes[best];document.getElementById('detail').textContent='شاخه '+n.id+'\\nبلوک‌های منبع: '+n.blocks.join(', ')+'\\nقطعات باقی‌مانده: '+n.count+'\\nنمونه‌های واقعیِ باقی‌مانده در گراف:\\n'+n.preview.join('\\n\\n')}});draw();</script></html>'''
    (HERE/'graph-explorer.html').write_text(template.replace('__DATA__',dumps(data).replace('<','\\u003c')),encoding='utf-8')
    print(dumps(integrity))


if __name__=='__main__':main()
