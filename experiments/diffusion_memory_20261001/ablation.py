"""Post-primary diagnostic controls. No fitting; same frozen graphs, tasks and raw atoms."""
import json
from time import perf_counter
from memory import Atom, GraphRetriever, Lexical, dumps, sha, tokens
from evaluate import BUDGETS, HERE, bootstrap_pair, expand_hop, flat_retrieve, grade, summarize


def main():
    plan={'phase':'diagnostic_after_primary','not_a_blind_holdout':True,
          'reason':'Separate lexical early stopping from graph/source selection.',
          'arms':['flat_atoms_full_expand','graph_archive_full','graph_archive_full_no_diffusion'],
          'caps':[100000],'budgets':BUDGETS,'changed_parameters':{'adaptive':False},
          'candidate_hash':sha((HERE/'memory.py').read_text(encoding='utf-8'))}
    (HERE/'ablation-plan.json').write_text(dumps(plan),encoding='utf-8')
    all_results={};all_details={}
    for name in ['synthetic_1m','flux_real']:
        directory=HERE/'snapshots'/name
        atoms=[Atom(**a) for a in json.loads((directory/'atoms.json').read_text(encoding='utf-8'))]
        byid={a.ident:a for a in atoms}
        payload=json.loads((directory/'graph_100000.json').read_text(encoding='utf-8'))
        retained=[byid[c[0]] for n in payload['nodes'] for c in n['atoms']]
        graph=GraphRetriever({'payload':payload,'atoms':retained},atoms)
        idx=Lexical([a.text for a in atoms])
        tasks=json.loads((HERE/'evaluation_only'/f'{name}_tasks.json').read_text(encoding='utf-8'))
        arms={
          'flat_atoms_full_expand':lambda q,b,c:expand_hop(lambda q,b,c:flat_retrieve(atoms,idx,q,b,c),q,b,c),
          'graph_archive_full':lambda q,b,c:expand_hop(lambda q,b,c:graph.retrieve(q,b,c,archive=True,adaptive=False),q,b,c),
          'graph_archive_full_no_diffusion':lambda q,b,c:expand_hop(lambda q,b,c:graph.retrieve(q,b,c,archive=True,diffusion=False,adaptive=False),q,b,c),
        }
        all_results[name]={};all_details[name]={}
        for budget in BUDGETS:
            rows={a:[] for a in arms}
            for no,t in enumerate(tasks):
                q=t['query']+' '+' '.join(t['criteria'])
                for a in (list(arms) if no%2 else list(reversed(arms))):
                    rows[a].append(grade(arms[a](q,budget,t['criteria']),t))
                if no%32==0:print(dumps({'phase':'ablation','corpus':name,'budget':budget,'task':no}),flush=True)
            for a in rows:rows[a].sort(key=lambda x:x['task_id'])
            all_details[name][str(budget)]=rows
            all_results[name][str(budget)]={a:summarize(v) for a,v in rows.items()}
    (HERE/'ablation-results.json').write_text(dumps(all_results),encoding='utf-8')
    (HERE/'evaluation_only/ablation-details.json').write_text(dumps(all_details),encoding='utf-8')


if __name__=='__main__':main()
