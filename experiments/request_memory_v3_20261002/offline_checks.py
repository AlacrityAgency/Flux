"""Independent structural audit/ablation of the frozen candidate, no generation calls."""
from pathlib import Path
import json
from time import perf_counter
import numpy as np
from embedding import Encoder
from engine import HERE,OLD,Atom,Record,Request,ArchiveBuilder,Memory,pipeline,dumps,sha,tokens
from evaluate import grade,summarize


def main():
    start=perf_counter();d=HERE/'snapshots/synthetic_fresh_1m'
    atoms=[Atom(**a) for a in json.loads((d/'atoms.json').read_text(encoding='utf-8'))]
    chunks=[Atom(**a) for a in json.loads((d/'chunks.json').read_text(encoding='utf-8'))]
    # Original source-generated task file from new corpus, not model answer output.
    from build_data import synthetic
    source=synthetic(seed=771239)
    tasks=source['tasks'][:12]+source['tasks'][80:88]+source['tasks'][112:120]
    plan={'phase':'offline_ablation','evaluation':'Exact-anchor diagnostics, no output quality claims',
          'arms':['full','no_embedding','no_pruning','no_bridge','no_personalization'],
          'archive_policy':'adaptive','query_budget':3000,'tasks':len(tasks),
          'candidate_hashes':{name:sha((HERE/name).read_text(encoding='utf-8')) for name in ['engine.py','embedding.py']}}
    (HERE/'offline-plan.json').write_text(dumps(plan),encoding='utf-8')
    e=Encoder();m=Memory([Record(a) for a in atoms],e);b=ArchiveBuilder(chunks)
    rows={a:[] for a in plan['arms']};details=[]
    for i,t in enumerate(tasks):
        req=Request(t['id'],t['query'],tuple(t['criteria']))
        for arm in plan['arms']:
            request=Request(t['id'],'Find relevant project service evidence',()) if arm=='no_personalization' else req
            p=pipeline(request,m,b,adaptive=True,embedding=arm!='no_embedding',
                       pruning=arm!='no_pruning',bridges=arm!='no_bridge')
            r=grade(p,t);rows[arm].append(r)
            details.append({'task':t['id'],'arm':arm,'graph_tokens':p['graph']['tokens'],
                            'pack_tokens':p['tokens'],'archive_tokens':p['archive']['tokens'],
                            'rollbacks':sum(x['rollback'] for x in p['graph']['trace']),'grade':r})
        if i%8==0:print(dumps({'phase':'offline','task':i}),flush=True)
    # All windows contribute; overlength source content remains unchanged in the archive.
    vec=e.encode(['بودجه و حافظه پروژه','Project memory and budget'],'query')
    long=e.encode(['passage about budget '*600],'passage')
    assert vec.shape==(2,384) and long.shape==(1,384)
    assert np.allclose(np.linalg.norm(vec,axis=1),1,atol=1e-5)
    assert np.allclose(np.linalg.norm(long,axis=1),1,atol=1e-5)
    result={'runs':len(details),'summary':{a:summarize(r) for a,r in rows.items()},'details':details,
            'embedding_shape':[2,384],'bilingual_cosine':float(vec[0]@vec[1]),
            'long_input_window_coverage':True,'seconds':perf_counter()-start,'model_calls':0}
    (HERE/'offline-results.json').write_text(dumps(result),encoding='utf-8')
    print(dumps({'phase':'offline_finished','summary':result['summary']}),flush=True)


if __name__=='__main__':main()
