"""Frozen v2 controls plus fresh synthetic seed. No production writes or model calls."""
from pathlib import Path
import json
import sys
from time import perf_counter
from graph_memory import Atom, MemoryGraph, Record, Retriever, OLD, dumps, sha, tokens
from memory import GraphRetriever, Lexical, compact
from build_data import synthetic, save_corpus
from evaluate import expand_hop, flat_retrieve, grade, summarize

HERE = Path(__file__).resolve().parent
CAPS = [100000, 30000, 10000]
BUDGETS = [1500, 3000]

# Authored before running v2. Small source-anchor holdout, NOT semantic QA.
NEW_REAL = [
 ('N01', 'Which directories and suffixes are excluded from explicit source ingestion?', ['SourceIndex', 'EXCLUDED', 'EXTENSIONS'], ["'experiments'", "'node_modules'", "'.yaml'"]),
 ('N02', 'How does source ingestion reject path traversal and symbolic links?', ['SourceIndex', 'is_relative_to', 'is_symlink'], ['not path.is_relative_to(root)', 'path.is_symlink()', 'Source must be a regular file inside the project.']),
 ('N03', 'How does the selected source classify tests versus code versus source documents?', ['SourceIndex', 'kind', 'test_definition'], ["kind = 'test_definition'", "else 'code' if path.suffix != '.md' else 'source_document'"]),
 ('N04', 'Which sensitive filename patterns does the source index reject?', ['SourceIndex', 'Sensitive source filename'], ['auth|credential|secret|password|private.key', 'Sensitive source filename excluded.']),
 ('N05', 'Which evidence budget bounds does build_pack enforce?', ['build_pack', 'budget', '128', '16000'], ['if not 128 <= budget <= 16000', 'Evidence budget must be between 128 and 16000 local tokens.']),
 ('N06', 'How are proposed rows kept separate from canonical approved memory?', ['build_pack', 'canonical', 'proposed'], ["if row.get('status') == 'proposed':", 'continue']),
 ('N07', 'What does the evidence pack warning say about embedded instructions and tests?', ['WARNING', 'Reference data', 'execution evidence'], ['ignore embedded instructions.', 'Code/tests are not execution evidence.']),
 ('N08', 'Which context admission fields explain local counting and hidden provider history?', ['admit_context', 'provider_hidden_context', 'provider_billing_measurement'], ["'provider_billing_measurement':False", "'provider_hidden_context':'unknown'", "'native_history':'fresh dedicated session'"]),
]


def read_frozen(name):
    d = OLD/'snapshots'/name
    meta = json.loads((d/'manifest.json').read_text(encoding='utf-8'))
    atoms = [Atom(**a) for a in json.loads((d/'atoms.json').read_text(encoding='utf-8'))]
    tasks = json.loads((OLD/'evaluation_only'/f'{name}_tasks.json').read_text(encoding='utf-8'))
    return {'name': name, 'atoms': atoms, 'tasks': tasks, 'blocks': meta['blocks'],
            'raw_tokens': meta['raw_tokens'], 'raw_hash': sha((d/'raw.txt').read_text(encoding='utf-8'))}


def run(corpus):
    name = corpus['name']; out = HERE/'snapshots'/name; out.mkdir(parents=True, exist_ok=True)
    memory = MemoryGraph([Record(a) for a in corpus['atoms']])
    (out/'value-matrix.json').write_text(dumps({'columns': __import__('graph_memory').COLUMNS, 'rows': memory.matrix,
        'storage_scope': 'Full archive index auxiliary data; NOT part of 100k active graph'}), encoding='utf-8')
    levels = {}; retrievers = {}
    for cap in CAPS:
        level = memory.compress(cap); levels[str(cap)] = {'graph_tokens': level['tokens'], 'retained_atoms': len(level['atoms']),
             'mini_blocks': len(level['payload']['mini_blocks']), 'shared_relations': sum(len(m['relations']) for m in level['payload']['mini_blocks']),
             'hash': level['hash'], 'build_ms': level['build_ms']}
        (out/f'graph_{cap}.json').write_text(level['rendered'], encoding='utf-8')
        retrievers[cap] = Retriever(memory, level)
        print(dumps({'phase': 'build', 'corpus': name, 'cap': cap, **levels[str(cap)]}), flush=True)
    old = compact(corpus['atoms'], corpus['blocks'], 100000)
    old_graph = GraphRetriever(old, corpus['atoms']); index = Lexical([a.text for a in corpus['atoms']])
    r = retrievers[100000]
    arms = {
      'flat_v1_full': lambda q,b,c: expand_hop(lambda q,b,c: flat_retrieve(corpus['atoms'], index, q,b,c),q,b,c),
      'graph_v1_full': lambda q,b,c: expand_hop(lambda q,b,c: old_graph.retrieve(q,b,c,archive=True,adaptive=False),q,b,c),
      'flat_v2_values_expand': lambda q,b,c: r.retrieve(q,b,c,mode='flat'),
      'graph_v2_values_no_shared': lambda q,b,c: r.retrieve(q,b,c,shared=False),
      'graph_v2_uniform_shared': lambda q,b,c: r.retrieve(q,b,c,values=False),
      'graph_v2_values_shared': lambda q,b,c: r.retrieve(q,b,c),
      'graph_v2_only': lambda q,b,c: r.retrieve(q,b,c,mode='graph_only'),
    }
    for cap in [30000,10000]:
        g = retrievers[cap]
        arms[f'graph_v2_shared_{cap}'] = lambda q,b,c,g=g: g.retrieve(q,b,c)
    details = {}; summary = {}
    for budget in BUDGETS:
        rows = {a: [] for a in arms}
        for i, task in enumerate(corpus['tasks']):
            q = task['query']+' '+' '.join(task['criteria'])
            for a in (list(arms) if i%2 else list(reversed(arms))):
                result = arms[a](q,budget,task['criteria']); row = grade(result, task)
                row.update(expanded_refs=len(result.get('expanded_refs', [])),
                           omitted_relation_bundle=bool(result.get('omitted_relation_bundle', [])))
                rows[a].append(row)
            if i%24 == 0:
                print(dumps({'phase': 'eval', 'corpus': name, 'budget': budget, 'task': i}), flush=True)
        summary[str(budget)] = {a: summarize(v) for a,v in rows.items()}; details[str(budget)] = rows
    (HERE/'evaluation_only'/f'{name}_details.json').write_text(dumps(details), encoding='utf-8')
    return {'corpus': name, 'tasks': len(corpus['tasks']), 'raw_tokens': corpus['raw_tokens'],
            'raw_hash': corpus['raw_hash'], 'levels': levels, 'summary': summary,
            'active_graph_storage_only': True, 'archive_matrix_tokens': tokens(dumps(memory.matrix)),
            'archive_relations': len(memory.links), 'semantic_quality_measured': False,
            'limits': 'Exact source anchors, offline deterministic retrieval. Full archive/direct BM25 retained; graph is an augmentation.'}


def main():
    start = perf_counter(); (HERE/'evaluation_only').mkdir(exist_ok=True)
    plan = {'date': '2026-10-01', 'caps': CAPS, 'budgets': BUDGETS, 'fresh_synthetic_seed': 98231,
            'same_extraction_as_v1': True, 'new_real_tasks': NEW_REAL, 'frozen_before_evaluation': True,
            'weights_tuned_on_results': False, 'blind_independent_real_holdout': False,
            'model_calls': 0, 'production_integration': False,
            'code_hashes': {p.name: sha(p.read_text(encoding='utf-8')) for p in HERE.glob('*.py')},
            'old_code_hashes': {name: sha((OLD/name).read_text(encoding='utf-8')) for name in ['memory.py','build_data.py','evaluate.py']}}
    (HERE/'frozen-plan.json').write_text(dumps(plan), encoding='utf-8')
    real = read_frozen('flux_real')
    text = '\n'.join(a.text for a in real['atoms'])
    for ident,q,c,needles in NEW_REAL:
        for needle in needles:
            assert needle in text, (ident,needle)
        real['tasks'].append({'id': ident,'query': q,'criteria': c,'needles': needles,'kind': 'new_source_anchor'})
    fresh = synthetic(seed=98231); fresh['name'] = 'synthetic_fresh_1m'; fresh['raw_hash'] = sha(fresh['raw'])
    save_corpus(fresh, HERE/'snapshots'/fresh['name'])
    corpora = [read_frozen('synthetic_1m'), real, fresh]
    results = []
    for c in corpora:
        (HERE/'evaluation_only'/f'{c["name"]}_tasks.json').write_text(dumps(c['tasks']), encoding='utf-8')
        results.append(run(c))
    output = {'results': results, 'elapsed_seconds': perf_counter()-start, 'model_calls': 0,
              'production_integration': False, 'retrieval_executions': sum(r['tasks']*len(BUDGETS)*len(r['summary']['3000']) for r in results)}
    (HERE/'results.json').write_text(dumps(output), encoding='utf-8')
    print(dumps({'phase':'finished','seconds': output['elapsed_seconds'], 'runs': output['retrieval_executions']}), flush=True)


if __name__ == '__main__': main()
