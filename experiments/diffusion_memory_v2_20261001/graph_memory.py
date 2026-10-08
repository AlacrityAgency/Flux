"""Isolated value-matrix/shared-mini-block memory. No training or Flux imports."""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import math
import re
import sys
from time import perf_counter
import numpy as np

OLD = Path(__file__).resolve().parent.parent / 'diffusion_memory_20261001'
sys.path.insert(0, str(OLD))
from memory import Atom, Lexical, dumps, envelope, sha, tokens, words

COLUMNS = ['source_role_prior', 'rarity', 'constraint_cue', 'bridge_utility', 'freshness_gate', 'token_cost']
STATIC_WEIGHTS = [.20, .30, .30, .20]
QUERY_WEIGHTS = {'relevance': .62, 'criterion_gain': .14, 'constraint': .10, 'rarity': .08, 'role': .06}


@dataclass(frozen=True)
class Record:
    atom: Atom
    project: str = 'experiment'
    revision: int = 1
    status: str = 'verified'
    enabled: bool = True


def eligible(records, project):
    """Project BEFORE indexing; canonical revision BEFORE status; proposed is separate."""
    canonical = {}
    for r in records:
        if r.project != project or r.status == 'proposed':
            continue
        key = r.atom.ident
        old = canonical.get(key)
        if old is None or r.revision > old.revision:
            canonical[key] = r
        elif r.revision == old.revision and r != old:
            raise ValueError('Conflicting canonical memory revision')
    return [r.atom for _, r in sorted(canonical.items()) if r.status == 'verified' and r.enabled]


def relations(atoms):
    """Extract explicit fields and symbol references. A mention is NOT a call edge."""
    owners = {}
    definitions = defaultdict(list)
    for a in atoms:
        for s in re.findall(r'(svc\d{5}) owner:', a.text):
            owners.setdefault(s, a)
        for symbol in re.findall(r'(?:def|class)\s+(\w+)\s*[:(]', a.text):
            if len(symbol) >= 4 and not symbol.startswith('_'):
                definitions[symbol].append(a)
    out = []
    seen = set()
    for a in atoms:
        for source, target in re.findall(r'(svc\d{5}) depends_on: (svc\d{5})', a.text):
            b = owners.get(target)
            if b:
                out.append({'left': a.ident, 'right': b.ident, 'kind': 'depends_on',
                            'key': source, 'target': target})
        # Tokens must correspond to a declared symbol. Ambiguous definitions are skipped.
        for symbol in set(re.findall(r'\b[A-Za-z_]\w*\b', a.text)) & definitions.keys():
            defs = definitions[symbol]
            if len(defs) != 1:
                continue
            b = defs[0]
            key = (a.ident, b.ident, symbol)
            if a.source != b.source and key not in seen:
                out.append({'left': a.ident, 'right': b.ident, 'kind': 'symbol_reference',
                            'key': symbol, 'target': symbol})
                seen.add(key)
    return sorted(out, key=lambda x: (x['kind'], x['key'], x['left'], x['right']))


def value_matrix(atoms, links):
    sets = [set(words(a.text)) for a in atoms]
    df = Counter(w for s in sets for w in s)
    degree = Counter(x[k] for x in links for k in ['left', 'right'])
    matrix = {}
    for a, ws in zip(atoms, sets):
        # Role is a retrieval prior, NEVER semantic authority or execution proof.
        role = .9 if a.source.startswith('src/') else .8 if a.source.startswith('tests/') else .6
        rarity = sum(math.log1p(len(atoms)/df[w]) for w in ws) / max(1, len(ws))
        rarity = min(1., rarity/max(1., math.log1p(len(atoms))))
        critical = float(bool(re.search(r'approval|forbidden|scope|raise|assert|guard|budget|revision|unknown|accept', a.text, re.I)))
        bridge = min(1., math.log1p(degree[a.ident])/math.log(5))
        matrix[a.ident] = [round(role, 4), round(rarity, 4), critical, round(bridge, 4), 1., tokens(dumps(a.public()))]
    return matrix


def static_value(row):
    return sum(w*x for w, x in zip(STATIC_WEIGHTS, row[:4]))


class MemoryGraph:
    def __init__(self, records, project='experiment'):
        self.project = project
        self.atoms = eligible(records, project)
        if not self.atoms:
            raise ValueError('No eligible memory')
        self.byid = {a.ident: a for a in self.atoms}
        self.positions = {a.ident: i for i, a in enumerate(self.atoms)}
        self.links = relations(self.atoms)
        self.matrix = value_matrix(self.atoms, self.links)
        self.index = Lexical([a.text for a in self.atoms])
        self.wordsets = [set(words(a.text)) for a in self.atoms]
        self.by_source = defaultdict(list)
        for a in self.atoms:
            self.by_source[a.source].append(a)
        for xs in self.by_source.values():
            xs.sort(key=lambda a: a.line)
        self.neighbors = {}
        for xs in self.by_source.values():
            for i, a in enumerate(xs):
                self.neighbors[a.ident] = [x.ident for x in xs[max(0, i-1):i+2] if x.ident != a.ident]
        self.snapshot_hash = sha(dumps([a.__dict__ for a in self.atoms]))

    def compress(self, cap=100000):
        """Expand relations from eligible archive FIRST; then budget the active view."""
        start = perf_counter()
        blocks = sorted({a.block for a in self.atoms})
        count = min(len(blocks), max(1, cap//1000))
        mapping = {b: min(count-1, i*count//len(blocks)) for i, b in enumerate(blocks)}
        groups = [[] for _ in range(count)]
        for a in self.atoms:
            groups[mapping[a.block]].append(a)
        nodes = []
        for i, group in enumerate(groups):
            entities = sorted({s for a in group for s in re.findall(r'svc\d{5}|(?:def|class)\s+\w+', a.text)})
            # Complete entity strings only; no clipped names masquerading as routes.
            route = []
            for s in entities:
                if tokens(' '.join(route+[s])) <= max(12, cap//count//5):
                    route.append(s)
            nodes.append({'id': i, 'blocks': sorted({a.block for a in group}), 'route': ' '.join(route), 'refs': []})
        payload = {'kind': 'valued_shared_memory_graph_v2', 'project': self.project, 'cap': cap,
                   'archive_snapshot_hash': self.snapshot_hash, 'matrix_columns': COLUMNS,
                   'nodes': nodes, 'memories': [], 'mini_blocks': [],
                   'warning': 'Source excerpts and references; semantic sufficiency unverified. External archive required for absent text.'}
        if tokens(dumps(payload)) > cap:
            raise ValueError('Graph metadata exceeds cap')
        # Every active inter-node edge IS a shared mini-block. No unbacked edges.
        edges = defaultdict(list)
        for link in self.links:
            a, b = self.byid[link['left']], self.byid[link['right']]
            i, j = mapping[a.block], mapping[b.block]
            if i != j:
                edges[tuple(sorted((i, j)))].append(link)
        ranked = []
        for (i, j), links in edges.items():
            links.sort(key=lambda x: (-static_value(self.matrix[x['left']])-static_value(self.matrix[x['right']]), x['key'], x['left']))
            selected = links[:2]
            rank = sum(static_value(self.matrix[x[k]]) for x in selected for k in ['left', 'right']) / len(selected)
            ranked.append((rank, i, j, selected))
        # Round-robin edge slots keeps a prolific hub from spending the whole bridge reserve.
        ranked.sort(key=lambda x: (-x[0], x[1], x[2]))
        degree = Counter(); reserve = int(cap*.18); used = 0
        for rank, i, j, links in ranked:
            if degree[i] >= 4 or degree[j] >= 4:
                continue
            mini = {'id': f'm{i}_{j}', 'nodes': [i, j], 'relations': links,
                    'value': round(rank, 4), 'archive_refs': True}
            cost = tokens(dumps(mini))+2
            if used+cost > reserve:
                continue
            payload['mini_blocks'].append(mini); used += cost; degree[i] += 1; degree[j] += 1
        # One canonical text per record. Nodes and shared blocks reuse its reference.
        base = tokens(dumps(payload))
        per_node = max(0, int((cap-base)*.96)//count)
        selected = []
        for i, group in enumerate(groups):
            group.sort(key=lambda a: (-static_value(self.matrix[a.ident])/max(1, self.matrix[a.ident][-1])**.35, a.ident))
            spent = 0
            for a in group:
                card = [a.ident, a.source, a.line, a.text, self.matrix[a.ident]]
                cost = tokens(dumps(card))+tokens(dumps(a.ident))+4
                if spent+cost <= per_node:
                    payload['memories'].append(card); nodes[i]['refs'].append(a.ident)
                    selected.append(a); spent += cost
        rendered = dumps(payload)
        while tokens(rendered) > cap and selected:
            a = selected.pop(); payload['memories'].pop()
            nodes[mapping[a.block]]['refs'].remove(a.ident); rendered = dumps(payload)
        if tokens(rendered) > cap:
            raise ValueError('Topology alone exceeds cap')
        return {'payload': payload, 'atoms': selected, 'rendered': rendered, 'tokens': tokens(rendered),
                'hash': sha(rendered), 'build_ms': (perf_counter()-start)*1000}


class Retriever:
    def __init__(self, memory, level):
        self.memory, self.level = memory, level
        self.nodes = level['payload']['nodes']
        kept = {a.ident: a for a in level['atoms']}
        self.node_index = Lexical([n['route']+' '+' '.join(kept[x].text for x in n['refs']) or 'empty' for n in self.nodes])
        self.by_block = defaultdict(list)
        for a in memory.atoms:
            self.by_block[a.block].append(a.ident)
        self.active_links = [r for mini in level['payload']['mini_blocks'] for r in mini['relations']]
        self.kept_atoms = level['atoms']
        self.kept_index = Lexical([a.text for a in self.kept_atoms]) if self.kept_atoms else None

    def retrieve(self, query, budget, criteria=(), mode='graph', shared=True, values=True, context=True):
        start = perf_counter(); m = self.memory
        if mode == 'graph_only':
            direct = np.zeros(len(m.atoms))
            if self.kept_index:
                for a, score in zip(self.kept_atoms, self.kept_index.score(query)):
                    direct[m.positions[a.ident]] = score
        else:
            direct = m.index.score(query)
        seeds = np.argsort(-direct, kind='stable')[:32]
        seeds = [int(i) for i in seeds if direct[i] > 0]
        seed_ids = {m.atoms[i].ident for i in seeds}
        visited = []; expanded = set(); pinned = set(); pool = set(seed_ids)
        external = mode != 'graph_only'
        if mode.startswith('graph'):
            route = self.node_index.score(query)
            for node_id in np.argsort(-route, kind='stable')[:3]:
                if route[node_id] <= 0:
                    continue
                node = self.nodes[int(node_id)]; visited.append(int(node_id))
                if external:
                    for b in node['blocks']:
                        pool.update(self.by_block[b])
                else:
                    pool.update(node['refs'])
            if not external:
                available = {a.ident for a in self.level['atoms']}
                pool &= available
        links = m.links if mode == 'flat' else self.active_links
        if shared:
            svc = re.search(r'svc\d{5}', query)
            dependency = 'dependency' in query.lower() or 'depends_on' in query.lower()
            for r in links:
                if r['left'] not in seed_ids:
                    continue
                if r['kind'] == 'depends_on' and dependency and svc and r['key'] == svc.group():
                    expanded.add(r['right']); pinned.update([r['left'], r['right']])
                elif r['kind'] == 'symbol_reference' and r['key'].lower() in set(words(query)):
                    expanded.add(r['right'])
                if len(expanded) >= 24:
                    break
            if not external:
                expanded &= {a.ident for a in self.level['atoms']}
                pinned &= {a.ident for a in self.level['atoms']}
            pool.update(expanded)
        if context:
            for ident in seed_ids | expanded:
                pool.update(m.neighbors.get(ident, []))
            if not external:
                pool &= {a.ident for a in self.level['atoms']}
        # Expanded witnesses inherit bounded route relevance, not a fabricated fact.
        rel = direct/max(1., float(direct.max()))
        for ident in expanded:
            rel[m.positions[ident]] = max(rel[m.positions[ident]], .8)
        candidates = sorted(pool, key=lambda ident: (-rel[m.positions[ident]], ident))[:96]
        criteria_words = [set(words(c)) for c in criteria]
        selected = []; selected_ids = set(); covered = set(); dropped_pins = []
        # Explicit relationship bundles are admitted atomically under the actual envelope budget.
        if pinned:
            bundle = [m.byid[x].public() for x in sorted(pinned)]
            if tokens(envelope(bundle)) <= budget:
                selected += bundle; selected_ids |= pinned
            else:
                dropped_pins = sorted(pinned)
        remaining = [x for x in candidates if x not in selected_ids and rel[m.positions[x]] > 0]
        duplicate_scores = {x: 0. for x in remaining}
        def update_duplicates(chosen):
            chosen_words = m.wordsets[m.positions[chosen]]
            for x in remaining:
                ws = m.wordsets[m.positions[x]]
                overlap = len(ws & chosen_words)/max(1, len(ws | chosen_words))
                duplicate_scores[x] = max(duplicate_scores[x], overlap)
        for x in selected_ids:
            update_duplicates(x)
        # Greedy bounded marginal value, criterion diversity and duplicate penalty.
        while remaining:
            scores = []
            for ident in remaining:
                i = m.positions[ident]; row = m.matrix[ident]; ws = m.wordsets[i]
                gain = sum(len(ws & c)/max(1, len(c)) for j, c in enumerate(criteria_words) if j not in covered)/max(1, len(criteria_words))
                duplicate = duplicate_scores[ident]
                value = (.62*rel[i]+.14*gain+.10*row[2]+.08*row[1]+.06*row[0]-.12*duplicate) if values else rel[i]
                scores.append(value/max(1, row[-1])**(.35 if values else 0))
            pos = int(np.argmax(scores)); ident = remaining.pop(pos); a = m.byid[ident]
            if tokens(envelope(selected+[a.public()])) <= budget:
                selected.append(a.public()); selected_ids.add(ident)
                update_duplicates(ident)
                covered.update(j for j, c in enumerate(criteria_words) if c and c <= m.wordsets[m.positions[ident]])
            # Coverage changes ordering only. It NEVER terminates retrieval or verifies a criterion.
        rendered = envelope(selected)
        if tokens(rendered) > budget:
            raise ValueError('Evidence metadata exceeds requested budget')
        return {'items': selected, 'ids': [x['id'] for x in selected], 'rendered': rendered,
                'tokens': tokens(rendered), 'budget': budget, 'pack_hash': sha(rendered),
                'semantic_sufficiency': 'unverified', 'model_calls': 0,
                'latency_ms': (perf_counter()-start)*1000, 'visited_nodes': visited,
                'expanded_refs': sorted(expanded), 'omitted_relation_bundle': dropped_pins,
                'external_atom_tokens_scanned': sum(m.matrix[x][-1] for x in pool) if external else 0,
                'recall_scope': 'eligible archive plus graph' if external else 'active graph only'}
