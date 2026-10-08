"""Completed archive-backed recall; primary v2 candidate is preserved unchanged."""
from collections import defaultdict
import copy
import re
from time import perf_counter
import numpy as np
from graph_memory import MemoryGraph, Retriever, dumps, sha, tokens, words
from memory import WARNING


class CompletedMemoryGraph(MemoryGraph):
    def __init__(self, records, project='experiment'):
        records = list(records)
        super().__init__(records, project)
        # Acceptance/caches must change on revision even if the excerpt is identical.
        canonical = {}
        for r in records:
            if r.project == project and r.status != 'proposed':
                old = canonical.get(r.atom.ident)
                if old is None or r.revision > old.revision:
                    canonical[r.atom.ident] = r
        stamps = [[a.ident, canonical[a.ident].revision, sha(a.text)] for a in self.atoms]
        self.snapshot_hash = sha(dumps({'project': project, 'stamps': stamps}))


class CompletedRetriever(Retriever):
    def __init__(self, memory, level):
        super().__init__(memory, level)
        if level['payload']['archive_snapshot_hash'] != memory.snapshot_hash:
            raise ValueError('Graph/archive revision mismatch; rebuild required')
        self.link_index = defaultdict(list)
        for r in memory.links:
            self.link_index[r['left']].append(r)
        self.active_keys = {(r['left'],r['right'],r['kind']) for r in self.active_links}

    def retrieve(self, query, budget, criteria=(), mode='graph', shared=True, values=True,
                 context=True, archive_fallback=True):
        start = perf_counter(); m = self.memory; view = copy.copy(self)
        on_demand = []
        if shared and mode != 'graph_only' and archive_fallback:
            scores = m.index.score(query)
            seeds = [m.atoms[int(i)].ident for i in np.argsort(-scores, kind='stable')[:32] if scores[i] > 0]
            query_words = set(words(query)); svc = re.search(r'svc\d{5}',query)
            dependency = 'dependency' in query.lower() or 'depends_on' in query.lower()
            for ident in seeds:
                for r in self.link_index.get(ident,[]):
                    wanted = ((r['kind']=='depends_on' and dependency and svc and r['key']==svc.group())
                              or (r['kind']=='symbol_reference' and r['key'].lower() in query_words))
                    if wanted and (r['left'],r['right'],r['kind']) not in self.active_keys:
                        on_demand.append(r)
                    if len(on_demand)>=24:break
                if len(on_demand)>=24:break
            # Per-query view is immutable to other queries; no persistent graph mutation.
            view.active_links = self.active_links+on_demand
        result = Retriever.retrieve(view,query,budget,criteria,mode,shared,values,context)
        # Relation descriptions compete with evidence in the EXACT final prompt budget.
        considered = m.links if mode=='flat' else view.active_links
        pinned = set()
        if shared:
            for r in considered:
                if r['kind']=='depends_on' and r['right'] in result['expanded_refs']:
                    pinned.update([r['left'],r['right']])
        items = list(result['items'])
        def render():
            ids = {x['id'] for x in items}
            minis = [[r['kind'],r['key'],r['left'],r['right']] for r in considered
                     if shared and r['left'] in ids and r['right'] in ids and r['right'] in result['expanded_refs']][:8]
            return dumps({'warning':WARNING,'evidence':items,'shared_mini_blocks':minis}),minis
        rendered,minis = render()
        while tokens(rendered)>budget:
            removable = [i for i,x in enumerate(items) if x['id'] not in pinned]
            if removable:
                items.pop(removable[-1])
            elif items:
                # Mandatory relation is admitted as a bundle, or is explicitly omitted.
                result['omitted_relation_bundle'] = sorted(pinned)
                items = []; pinned.clear()
            else:
                raise ValueError('Reference envelope exceeds budget')
            rendered,minis = render()
        result.update(items=items,ids=[x['id'] for x in items],rendered=rendered,
                      tokens=tokens(rendered),pack_hash=sha(rendered),
                      shared_mini_blocks=minis,on_demand_relation_candidates=len(on_demand),
                      archive_relation_fallback=bool(on_demand),
                      latency_ms=(perf_counter()-start)*1000)
        return result
