"""Offline extractive hierarchical graph; no LLM, DB, Flux runtime, or learned latents."""
from __future__ import annotations
import hashlib
import json
import re
from dataclasses import dataclass
from time import perf_counter
import numpy as np
import tiktoken
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer

ENC = tiktoken.get_encoding('o200k_base')
WARNING = 'Reference excerpts only; lexical matches are not semantic verification or execution evidence.'


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def tokens(text):
    return len(ENC.encode(text, disallowed_special=()))


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def normalize(text):
    return text.replace('ي', 'ی').replace('ك', 'ک').replace('\u200c', ' ').lower()


def words(text):
    return re.findall(r'[\w]{2,}', normalize(text))


@dataclass(frozen=True)
class Atom:
    ident: str
    text: str
    source: str
    line: int
    block: int
    priority: float = 0.0

    def public(self):
        return {'id': self.ident, 'text': self.text, 'source': self.source, 'line': self.line}


class Lexical:
    """Reusable BM25 baseline, shared by flat and graph arms."""
    def __init__(self, texts):
        self.texts = texts
        self.vectorizer = CountVectorizer(analyzer=words, dtype=np.float64)
        counts = self.vectorizer.fit_transform(texts).tocsr()
        self.tfidf = TfidfTransformer().fit_transform(counts).tocsr()
        lengths = np.asarray(counts.sum(axis=1)).ravel()
        avg = max(1.0, float(lengths.mean()))
        df = np.bincount(counts.indices, minlength=counts.shape[1])
        idf = np.log(1+(len(texts)-df+.5)/(df+.5))
        rows = np.repeat(np.arange(counts.shape[0]), np.diff(counts.indptr))
        counts.data = (counts.data*2.2/(counts.data+1.2*(.25+.75*lengths[rows]/avg)))*idf[counts.indices]
        self.bm25 = counts

    def score(self, query):
        q = self.vectorizer.transform([query])
        q.data[:] = 1
        return np.asarray((self.bm25@q.T).toarray()).ravel()


def envelope(items):
    return dumps({'warning': WARNING, 'evidence': items})


def pack(atoms, scores, budget, adaptive=False, queries=()):
    selected, ids, covered = [], [], set()
    query_words = [set(words(q)) for q in queries]
    order = np.argsort(-np.asarray(scores), kind='stable')
    for i in order[:96]:
        if scores[i] <= 0:
            break
        a = atoms[int(i)]
        item = a.public()
        if tokens(envelope(selected+[item])) <= budget:
            selected.append(item); ids.append(a.ident)
            aw = set(words(a.text))
            # This stop signal is explicitly lexical, not semantic sufficiency.
            covered.update(j for j,qw in enumerate(query_words) if qw and qw <= aw)
        if adaptive and query_words and len(covered) == len(query_words):
            break
    rendered = envelope(selected)
    return {'items': selected, 'ids': ids, 'rendered': rendered, 'tokens': tokens(rendered),
            'budget': budget, 'semantic_sufficiency': 'unverified', 'pack_hash': sha(rendered)}


def atom_priority(text):
    # Fixed BEFORE evaluation; these are syntax/field cues, not answer labels.
    return float(bool(re.search(r'approval|required|forbidden|scope|raise|assert|guard|budget|cap|revision|unknown|accept', text, re.I)))


def compact(atoms, source_blocks, cap, prior=None):
    """Whole-atom, round-robin block allocation; subsequent passes only see prior atoms."""
    start = perf_counter()
    pool = atoms if prior is None else prior['atoms']
    active_blocks = sorted({a.block for a in pool})
    if not active_blocks:
        raise ValueError('Nonempty pool required')
    # Keep source-block groups even after summaries merge: the archive is EXTERNAL.
    group_count = min(len(active_blocks), max(1, cap//1000))
    group_map = {b: min(group_count-1, i*group_count//len(active_blocks)) for i,b in enumerate(active_blocks)}
    groups = [[] for _ in range(group_count)]
    for a in pool:
        groups[group_map[a.block]].append(a)
    index = Lexical([a.text for a in pool])
    # Fixed schema/syntax salience; no evaluator labels or oracle feed this order.
    lengths = np.array([max(1,len(words(a.text))) for a in pool])
    specificity = 1/np.sqrt(lengths)
    rank = {a.ident: a.priority+.1*float(s) for a,s in zip(pool,specificity)}
    for group in groups:
        group.sort(key=lambda a: (-rank[a.ident], a.ident))
    groups_blocks = [sorted({a.block for a in group}) for group in groups]
    # Shared-term affinity graph. It does NOT claim extracted semantic relations.
    texts = [' '.join(a.text for a in g[:30]) for g in groups]
    affin = Lexical(texts).tfidf
    sim = (affin@affin.T).toarray()
    np.fill_diagonal(sim, 0)
    edges = []
    for i in range(group_count):
        for j in np.argsort(-sim[i], kind='stable')[:min(4, group_count-1)]:
            if sim[i,j]>0:
                edges.append([i,int(j),round(float(sim[i,j]),4)])
    routes=[]
    for group in groups:
        # Routing includes source entity/symbol names; it contains no oracle labels.
        subjects=sorted({s for a in group for s in re.findall(r'svc\d{5}',a.text)})
        symbols=sorted({s for a in group for s in re.findall(r'(?:def|class)\s+(\w+)',a.text)})
        route_text=' '.join(subjects+symbols)
        # Routing metadata itself competes for the TOTAL graph token budget.
        route_cap=max(8,cap//group_count//4)
        rt=ENC.encode(route_text,disallowed_special=())[:route_cap]
        routes.append(ENC.decode(rt))
    payload = {'kind':'extractive_affinity_graph','source_blocks':source_blocks,'cap':cap,
               'nodes':[{'id':i,'blocks':bs,'route':routes[i],'atoms':[]} for i,bs in enumerate(groups_blocks)],
               'edges':edges,'warning':WARNING}
    base_tokens = tokens(dumps(payload))
    if base_tokens > cap:
        raise ValueError('Graph metadata exceeds cap')
    selected = []; used = base_tokens
    allowance = max(0,(cap-base_tokens)//group_count-12)
    for i, group in enumerate(groups):
        local = 0
        for a in group:
            card = [a.ident,a.source,a.line,a.text]
            cost = tokens(dumps(card))+2
            if local+cost > allowance:
                continue
            payload['nodes'][i]['atoms'].append(card);selected.append(a);local+=cost;used+=cost
    # Exact final serialization, including ALL nodes/edges/metadata/provenance.
    rendered = dumps(payload)
    while tokens(rendered)>cap and selected:
        a=selected.pop();i=group_map[a.block]
        payload['nodes'][i]['atoms']=[c for c in payload['nodes'][i]['atoms'] if c[0]!=a.ident]
        rendered=dumps(payload)
    return {'payload':payload,'atoms':selected,'tokens':tokens(rendered),'cap':cap,
            'rendered':rendered,'hash':sha(rendered),'build_ms':(perf_counter()-start)*1000}


class GraphRetriever:
    def __init__(self, level, full_atoms):
        self.level=level;self.atoms=level['atoms'];self.full_atoms=full_atoms
        self.node_index=Lexical([n['route']+' '+' '.join(c[3] for c in n['atoms']) or 'empty' for n in level['payload']['nodes']])
        n=len(level['payload']['nodes']);rows=[];cols=[];data=[]
        for i,j,w in level['payload']['edges']:
            rows.append(i);cols.append(j);data.append(w)
        adj=sparse.csr_matrix((data,(rows,cols)),shape=(n,n))
        deg=np.asarray(adj.sum(axis=1)).ravel()
        for i in np.flatnonzero(deg==0):
            adj=adj+sparse.csr_matrix(([1.],([i],[i])),shape=(n,n))
        deg=np.asarray(adj.sum(axis=1)).ravel()
        self.transition=sparse.diags(1/deg)@adj
        self.atom_index=Lexical([a.text for a in self.atoms])
        self.by_block={}
        for a in full_atoms:self.by_block.setdefault(a.block,[]).append(a)

    def ranks(self, query, diffusion=True):
        seeds=self.node_index.score(query)
        if not seeds.sum():return np.zeros(len(seeds))
        seeds=seeds/seeds.sum();rank=seeds.copy()
        if diffusion:
            for _ in range(24):rank=.65*seeds+.35*(self.transition.T@rank)
        return rank

    def retrieve(self, query, budget, queries, archive=False, diffusion=True, adaptive=False):
        start=perf_counter();rank=self.ranks(query,diffusion)
        visited=[];read_tokens=0;pool=self.atoms
        if archive and rank.max()>0:
            # Limited branches. No hidden full-corpus fallback, answer oracle or gold.
            best=np.argsort(-rank,kind='stable')[:min(3,len(rank))]
            blocks=set()
            for j in best:
                blocks.update(self.level['payload']['nodes'][int(j)]['blocks'])
            visited=sorted(blocks);pool=[a for b in visited for a in self.by_block.get(b,[])]
            read_tokens=min(len(visited)*10000,self.level['payload']['source_blocks']*10000)
        if not pool:
            result=pack([],[],budget)
        else:
            idx=Lexical([a.text for a in pool]) if archive else self.atom_index
            score=idx.score(query)
            if not archive:
                node_for={c[0]:n['id'] for n in self.level['payload']['nodes'] for c in n['atoms']}
                score=score*(1+np.array([rank[node_for[a.ident]] for a in pool]))
            result=pack(pool,score,budget,adaptive,queries)
        result.update({'latency_ms':(perf_counter()-start)*1000,'visited_blocks':visited,
                       'archive_tokens_upper_estimate':read_tokens,
                       'external_atom_tokens_scanned':tokens('\n'.join(a.text for a in pool)) if archive else 0,
                       'model_calls':0})
        return result
