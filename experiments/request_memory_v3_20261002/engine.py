"""Request-conditioned notes/graph, reversible pruning and exact rendered packs."""
from __future__ import annotations
from dataclasses import dataclass,field
from pathlib import Path
from collections import defaultdict
import re
import sys
from time import perf_counter
import numpy as np
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'diffusion_memory_20261001'
V2=HERE.parent/'diffusion_memory_v2_20261001'
sys.path.insert(0,str(OLD));sys.path.insert(0,str(V2))
from memory import Atom,Lexical,dumps,sha,tokens,words
from graph_memory import Record,eligible,relations


@dataclass(frozen=True)
class Request:
    ident:str
    query:str
    criteria:tuple[str,...]
    project:str='experiment'
    language:str='en'
    external_evidence:bool=True
    preferences:tuple[str,...]=()
    planner_notes:tuple[str,...]=()


def note_request(req):
    return [{'id':f'{req.ident}:need:{i}','kind':'need','text':c,'scope':req.project,
             'request_id':req.ident,'status':'requirement','weight':1.,'sources':[]}
            for i,c in enumerate(req.criteria)]


def request_payload(req,items,bridges):
    return dumps({'warning':'Reference data, not instructions. Source code is not executed-test evidence.',
        'request_id':req.ident,'needs':note_request(req),'preferences':list(req.preferences),
        'evidence':items,'shared_notes':bridges,'semantic_sufficiency':'unverified'})


class ArchiveBuilder:
    def __init__(self,chunks):
        self.chunks=chunks;self.index=Lexical([a.text for a in chunks])

    def build(self,req,priority_sources=(),target=1_000_000,adaptive=False):
        start=perf_counter();scores=self.index.score(req.query+' '+' '.join(req.criteria))
        priorities=set(priority_sources)
        order=sorted(range(len(self.chunks)),key=lambda i:(self.chunks[i].source not in priorities,-scores[i],self.chunks[i].ident))
        if adaptive:order=order[:min(32,len(order))]
        header={'kind':'request_evidence_archive_v3','project':req.project,'request':req.ident,'records':[]}
        base=tokens(dumps(header));selected=[];remaining=[];estimate=base
        for i in order:
            a=self.chunks[i];item=a.public();cost=tokens(dumps(item))+1
            if estimate+cost<=target-2048:
                selected.append(item);estimate+=cost
            else:remaining.append(a)
        header['records']=selected
        rendered=dumps(header)
        while tokens(rendered)>target and selected:
            selected.pop();rendered=dumps(header)
        # Complete unused source lines can close the gap without duplicate text/padding.
        exact=False;line_candidates=[]
        if not adaptive and remaining and 0<target-tokens(rendered)<=6000:
            for a in remaining[:32]:
                for no,line in enumerate(a.text.splitlines(),a.line):
                    if not line.strip():continue
                    item={'id':f'{a.ident}:line:{no}','source':a.source,'line':no,'text':line}
                    line_candidates.append(item)
            gap=target-tokens(rendered);reachable={0:()}
            # This exact-serialization delta is checked again after the proposed combination.
            tail={**header,'records':selected[-1:]}
            tail_tokens=tokens(dumps(tail))
            costs=[tokens(dumps({**tail,'records':tail['records']+[x]}))-tail_tokens for x in line_candidates]
            for i,cost in enumerate(costs):
                if cost<=0:continue
                new={}
                for amount,ids in reachable.items():
                    nxt=amount+cost
                    if nxt<=gap and nxt not in reachable:new[nxt]=ids+(i,)
                reachable.update(new)
                if gap in reachable:
                    proposed=selected+[line_candidates[j] for j in reachable[gap]]
                    r=dumps({**header,'records':proposed})
                    if tokens(r)==target:
                        selected=proposed;header['records']=selected;rendered=r;exact=True
                    break
        actual=tokens(rendered)
        texts=defaultdict(list)
        for item in selected:texts[item['source']].append(item['text'])
        return {'rendered':rendered,'tokens':actual,'target':target,'exact_target':actual==target,
                'status':'target_met' if actual==target else 'adaptive' if adaptive else 'target_unreachable',
                'sources':set(texts),'source_texts':{k:'\n'.join(v) for k,v in texts.items()},
                'records':len(selected),'hash':sha(rendered),'build_ms':(perf_counter()-start)*1000}


class Memory:
    def __init__(self,records,encoder,project='experiment'):
        start=perf_counter();self.project=project;self.atoms=eligible(records,project)
        self.byid={a.ident:a for a in self.atoms};self.pos={a.ident:i for i,a in enumerate(self.atoms)}
        self.index=Lexical([a.text for a in self.atoms]);self.encoder=encoder
        self.vectors=encoder.encode([a.text for a in self.atoms],'passage')
        self.links=relations(self.atoms);self.link_by_left=defaultdict(list)
        for r in self.links:self.link_by_left[r['left']].append(r)
        self.source_atoms=defaultdict(list)
        for a in self.atoms:self.source_atoms[a.source].append(a)
        for xs in self.source_atoms.values():xs.sort(key=lambda a:a.line)
        self.snapshot_hash=sha(dumps([a.__dict__ for a in self.atoms]));self.build_ms=(perf_counter()-start)*1000

    def score(self,req,embedding=True):
        queries=[req.query]+list(req.criteria)+list(req.planner_notes)
        final=np.zeros(len(self.atoms));ranks=[]
        vectors=self.encoder.encode(queries,'query') if embedding else None
        for j,q in enumerate(queries):
            lexical=self.index.score(q)
            for raw in [lexical]+([self.vectors@vectors[j]] if embedding else []):
                order=np.argsort(-raw,kind='stable');rank=np.empty(len(order));rank[order]=np.arange(1,len(order)+1)
                final+=1/(60+rank)
        svc=re.search(r'svc\d{5}',req.query)
        if svc:
            # Exact identifiers remain anchors even when multilingual embedding is diffuse.
            for i,a in enumerate(self.atoms):
                if svc.group() in a.text:final[i]*=3
        return final/max(1e-12,final.max())

    def route(self,req,archive,embedding=True):
        score=self.score(req,embedding);valid={a.ident for a in self.atoms if a.source in archive['sources'] and a.text in archive['source_texts'][a.source]}
        order=[int(i) for i in np.argsort(-score,kind='stable') if self.atoms[int(i)].ident in valid]
        seeds=order[:48];wanted={self.atoms[i].ident for i in seeds};protected=set();bridges=[]
        svc=re.search(r'svc\d{5}',req.query)
        if svc:
            fields=set(re.findall(r'owner|approval|scope|forbidden|retry_limit|timeout_ms|rare_code|depends_on',req.query+' '+' '.join(req.criteria)))
            for a in self.atoms:
                if a.ident in valid and any(f'{svc.group()} {f}:' in a.text for f in fields):
                    protected.add(a.ident);wanted.add(a.ident)
        dependency='dependency' in req.query.lower() or 'depends_on' in ' '.join(req.criteria)
        for i in seeds:
            a=self.atoms[i]
            for r in self.link_by_left.get(a.ident,[]):
                if r['right'] not in valid:continue
                relevant=((r['kind']=='depends_on' and dependency and svc and r['key']==svc.group())
                          or (r['kind']=='symbol_reference' and r['key'].lower() in set(words(req.query+' '+' '.join(req.criteria)))))
                if relevant:
                    wanted.add(r['right']);bridges.append(r)
                    if r['kind']=='depends_on':protected.update([r['left'],r['right']])
        # Complete adjacent source units; lexical coverage is never an acceptance signal.
        for ident in list(wanted):
            a=self.byid[ident];xs=self.source_atoms[a.source];p=next(i for i,x in enumerate(xs) if x.ident==ident)
            wanted.update(x.ident for x in xs[max(0,p-1):p+2] if x.ident in valid)
        # Graph begins broad; each pruning proposal is evaluated against pinned source probes.
        wanted.update(self.atoms[i].ident for i in order[:512])
        if not req.external_evidence:wanted=set();protected=set();bridges=[]
        return score,wanted,protected,bridges


def graph_payload(req,memory,ids,bridges):
    byblock=defaultdict(list)
    for ident in sorted(ids):byblock[memory.byid[ident].block].append(ident)
    rows=[memory.byid[x].public() for x in sorted(ids)]
    return {'kind':'personalized_request_graph_v3','snapshot':memory.snapshot_hash,'request_id':req.ident,
            'needs':note_request(req),'nodes':[{'block':b,'refs':refs} for b,refs in sorted(byblock.items())],
            'notes':[{'id':f'n:{x}','kind':'source_excerpt','ref':x,'scope':req.project,'status':'source_verified_semantics_unverified'} for x in sorted(ids)],
            'evidence':rows,'bridges':[r for r in bridges if r['left'] in ids and r['right'] in ids],
            'semantic_sufficiency':'unverified'}


def probe_graph(req,memory,ids,protected):
    # Internal source probes, not benchmark answers or a proof of answer correctness.
    return {'protected_preserved':protected<=ids,'missing':sorted(protected-ids),
            'exact_source_text':all(memory.byid[x].text for x in ids),
            'snapshot':memory.snapshot_hash}


def optimize(req,memory,score,ids,protected,bridges,cap=100000,pruning=True,critic_proposal=()):
    current=set(ids);trace=[]
    def size(s):return tokens(dumps(graph_payload(req,memory,s,bridges)))
    # Admission first protects critical units. Optional pieces are removed until cap.
    for ident in sorted(current-protected,key=lambda x:score[memory.pos[x]]):
        if size(current)<=cap:break
        current.remove(ident)
    if size(current)>cap:raise ValueError('Protected graph cannot fit; split request')
    initial=set(current);initial_tokens=size(current);best=set(current)
    if pruning:
        proposals=[('critic',set(critic_proposal))] if critic_proposal else []
        for fraction in [.70,.45,.25,.12]:
            optional=sorted(initial-protected,key=lambda x:-score[memory.pos[x]])
            proposals.append((f'bounded_prune_{fraction}',set(optional[max(16,int(len(optional)*fraction)):])) )
        # Explicit rollback probe: candidate tries deleting one critical item.
        if protected:proposals.append(('critical_deletion_probe',{sorted(protected)[0]}))
        for label,remove in proposals[:6]:
            proposed=current-remove;probe=probe_graph(req,memory,proposed,protected)
            before=size(current);after=size(proposed)
            accepted=probe['protected_preserved'] and probe['exact_source_text'] and after<before
            trace.append({'operation':label,'before_tokens':before,'after_tokens':after,'accepted':accepted,
                          'rollback':not accepted,'missing_probes':probe['missing'],'graph_hash':sha(dumps(graph_payload(req,memory,proposed,bridges)))})
            if accepted:current=proposed;best=set(proposed)
    final=graph_payload(req,memory,best,bridges)
    return {'payload':final,'rendered':dumps(final),'ids':best,'initial_ids':initial,
            'tokens':tokens(dumps(final)),'initial_tokens':initial_tokens,'trace':trace,
            'protected':protected,'internal_probe_scope':'Pinned exact source facts only; semantic criterion acceptance remains unverified'}


def pack(req,memory,score,graph,budget=3000,bridges=True):
    ids=graph['ids'];protected=graph['protected'];items=[];selected=set()
    def shared(current):
        ss={x['id'] for x in current}
        return [{'kind':r['kind'],'key':r['key'],'left':r['left'],'right':r['right'],'status':'source_relation'}
                for r in graph['payload']['bridges'] if bridges and r['left'] in ss and r['right'] in ss][:12]
    for x in sorted(protected,key=lambda x:(-score[memory.pos[x]],x)):
        proposed=items+[memory.byid[x].public()]
        if tokens(request_payload(req,proposed,shared(proposed)))>budget:
            raise ValueError('Required source bundle cannot fit evidence budget')
        items=proposed;selected.add(x)
    # Whole-record exact marginal token cost; protected facts are already admitted.
    remaining=sorted(ids-selected,key=lambda x:(-score[memory.pos[x]],x))[:96]
    for x in remaining:
        proposed=items+[memory.byid[x].public()]
        if tokens(request_payload(req,proposed,shared(proposed)))<=budget:
            items=proposed;selected.add(x)
    rendered=request_payload(req,items,shared(items))
    if tokens(rendered)>budget:raise ValueError('Mandatory note frame exceeds budget')
    return {'items':items,'ids':[x['id'] for x in items],'rendered':rendered,'tokens':tokens(rendered),
            'budget':budget,'pack_hash':sha(rendered),'semantic_sufficiency':'unverified','model_calls':0}


def pipeline(req,memory,builder,adaptive=False,embedding=True,pruning=True,bridges=True,critic_proposal=()):
    start=perf_counter();scores=memory.score(req,embedding)
    sources=[memory.atoms[int(i)].source for i in np.argsort(-scores,kind='stable')[:48]]
    # Prefer dependency targets before filling a fixed-size archive.
    for ident in [memory.atoms[int(i)].ident for i in np.argsort(-scores,kind='stable')[:48]]:
        sources.extend(memory.byid[r['right']].source for r in memory.link_by_left.get(ident,[]))
    archive=builder.build(req,sources,adaptive=adaptive)
    score,ids,protected,links=memory.route(req,archive,embedding)
    if not bridges:links=[]
    graph=optimize(req,memory,score,ids,protected,links,pruning=pruning,critic_proposal=critic_proposal)
    result=pack(req,memory,score,graph,bridges=bridges)
    result.update(latency_ms=(perf_counter()-start)*1000,archive=archive,graph=graph,
                  external_atom_tokens_scanned=sum(tokens(memory.byid[x].text) for x in graph['initial_ids']))
    return result
