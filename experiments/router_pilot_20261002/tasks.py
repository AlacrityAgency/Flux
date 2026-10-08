"""Pilot tasks: public part and evaluation-only gold kept apart.

Gold is computed by reference code here and never enters packs or prompts.
"""
from pathlib import Path
from collections import OrderedDict
import heapq
import itertools
import json
import math
import random
import re

HERE = Path(__file__).resolve().parent
V3 = HERE.parent/'request_memory_v3_20261002'


def v3_tasks():
    return json.loads((V3/'evaluation_only/tasks.json').read_text(encoding='utf-8'))


def new_private(corpus, seed=5150):
    """Same task shapes as the v3 pilot, fresh corpus and fresh subjects."""
    facts = {}
    for a in corpus['atoms']:
        m = re.fullmatch(r'(svc\d{5}) (\w+): (.+)\.', a.text)
        if m:
            facts.setdefault(m[1], {})[m[2]] = m[3]
    rng = random.Random(seed)
    subjects = rng.sample(sorted(s for s in facts if int(s[3:]) >= 1000), 6)
    out = []
    for i, s in enumerate(subjects):
        fields = ['owner', 'rare_code'] if i < 2 else ['approval', 'scope', 'forbidden'] if i < 4 else ['depends_on', 'dependency_owner']
        gold = {f: (facts[facts[s]['depends_on']]['owner'] if f == 'dependency_owner' else facts[s][f]) for f in fields}
        query = f'For private service {s}, report '+', '.join(fields)+'. Use current evidence; return null for unknown facts.'
        if i == 1:
            query = f'برای سرویس خصوصی {s} مقدار owner و rare_code را از شاهد فعلی پیدا کن؛ مقدار نامعلوم را null بده.'
        if i >= 4:
            query = f'Find the dependency of {s} and the owner of that dependency; report depends_on and dependency_owner.'
        out.append({'id': f'N{i:02d}', 'family': 'private_knowledge', 'corpus': 'synthetic_new', 'query': query,
                    'criteria': [f'{s} {f}' for f in fields if f != 'dependency_owner']+(['owner'] if i >= 4 else []),
                    'gold': gold})
    return out


REAL_EXTRA = [
    ('HR02', 'In this Flux snapshot, what input and output price per million does get_model_price return for an unknown model? Return answer keys input_per_million and output_per_million.',
     ['get_model_price', 'fallback', 'unknown'], {'input_per_million': 10.0, 'output_per_million': 50.0}),
    ('HR06', 'In this Flux snapshot, what are the default values of max_subtasks, max_concurrent_agents and max_root_calls in Settings? Return answer keys max_subtasks, max_concurrent_agents and max_root_calls.',
     ['Settings', 'max_subtasks', 'max_concurrent_agents', 'max_root_calls'], {'max_subtasks': 5, 'max_concurrent_agents': 2, 'max_root_calls': 20}),
    ('HR08', 'In this Flux snapshot, what is the default max_concurrent of ConcurrencyLimiter? Return answer key max_concurrent.',
     ['ConcurrencyLimiter', 'max_concurrent'], {'max_concurrent': 2}),
    ('HR10', 'In this Flux snapshot, what input and output price per million does the pricing table give gpt-5.6-luna? Return answer keys input_per_million and output_per_million.',
     ['MODEL_PRICES', 'gpt-5.6-luna'], {'input_per_million': 0.2, 'output_per_million': 1.2}),
]


def lattice():
    grid = [[0]*7 for _ in range(9)]
    for x in range(9):
        for y in range(7):
            if (x, y) == (3, 2):
                continue
            grid[x][y] = 1 if x == y == 0 else (grid[x-1][y] if x else 0)+(grid[x][y-1] if y else 0)
    return grid[8][6]


def coins(total, values):
    best = [0]+[math.inf]*total
    for t in range(1, total+1):
        best[t] = min((best[t-v]+1 for v in values if v <= t), default=math.inf)
    return best[total]


def lis(xs):
    tails = []
    for x in xs:
        i = next((k for k, t in enumerate(tails) if t >= x), len(tails))
        tails[i:i+1] = [x]
    return len(tails)


def spanning_k34():
    from fractions import Fraction
    n = 7
    lap = [[Fraction(0)]*n for _ in range(n)]
    for a in range(3):
        for b in range(3, 7):
            lap[a][b] = lap[b][a] = Fraction(-1)
            lap[a][a] += 1
            lap[b][b] += 1
    m = [row[1:] for row in lap[1:]]
    det = Fraction(1)
    for c in range(len(m)):
        p = next(r for r in range(c, len(m)) if m[r][c] != 0)
        if p != c:
            m[c], m[p] = m[p], m[c]
            det = -det
        det *= m[c][c]
        for r in range(c+1, len(m)):
            f = m[r][c]/m[c][c]
            m[r] = [x-f*y for x, y in zip(m[r], m[c])]
    return int(det)


SEQ = [5, 2, 8, 6, 3, 6, 9, 7, 4, 10, 1, 11, 5, 12]
NEW_REASONING = [
    ('R08', 'How many lattice paths from (0,0) to (8,6) using unit steps right or up avoid the point (3,2)?', lattice()),
    ('R09', 'How many integer solutions does x1+x2+x3+x4=20 have with 0<=xi<=7 for every i?',
     sum(1 for xs in itertools.product(range(8), repeat=4) if sum(xs) == 20)),
    ('R10', 'What are the last three digits of 7^2026? Give them as an integer.', pow(7, 2026, 1000)),
    ('R11', 'How many derangements (permutations with no fixed point) of 9 distinct objects are there?',
     sum((-1)**k*math.factorial(9)//math.factorial(k) for k in range(10))),
    ('R12', 'Using unlimited coins of values 1, 7, 23 and 41, what is the minimum number of coins that sum to exactly 289?', coins(289, [1, 7, 23, 41])),
    ('R13', 'A 5-card hand is dealt from a standard 52-card deck. What is the probability of exactly two pairs (not a full house), rounded to six decimals?',
     round(math.comb(13, 2)*math.comb(4, 2)**2*44/math.comb(52, 5), 6)),
    ('R14', f'What is the length of the longest strictly increasing subsequence of {SEQ}?', lis(SEQ)),
    ('R15', 'How many spanning trees does the complete bipartite graph K_{3,4} have?', spanning_k34()),
]


def ref_c04(s):
    toks, i = [], 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
        elif c.isdigit():
            j = i
            while j < len(s) and s[j].isdigit():
                j += 1
            toks.append(int(s[i:j]))
            i = j
        else:
            toks.append(c)
            i += 1
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else None

    def expr():
        nonlocal pos
        v = term()
        while peek() in ('+', '-'):
            op = toks[pos]
            pos += 1
            r = term()
            v = v+r if op == '+' else v-r
        return v

    def term():
        nonlocal pos
        v = unary()
        while peek() in ('*', '/'):
            op = toks[pos]
            pos += 1
            r = unary()
            if op == '*':
                v *= r
            else:
                q = abs(v)//abs(r)
                v = q if (v >= 0) == (r > 0) else -q
        return v

    def unary():
        nonlocal pos
        if peek() == '-':
            pos += 1
            return -unary()
        if peek() == '+':
            pos += 1
            return unary()
        t = toks[pos]
        pos += 1
        if t == '(':
            v = expr()
            pos += 1
            return v
        return t
    return expr()


def ref_c05(data):
    dur, deps = data['durations'], data['deps']
    if any(a not in dur or b not in dur for a, b in deps):
        return None
    indeg = {t: 0 for t in dur}
    adj = {t: [] for t in dur}
    for a, b in deps:
        adj[a].append(b)
        indeg[b] += 1
    start = {t: 0 for t in dur}
    finish = {}
    q = [t for t in dur if indeg[t] == 0]
    while q:
        t = q.pop()
        finish[t] = start[t]+dur[t]
        for n in adj[t]:
            start[n] = max(start[n], finish[t])
            indeg[n] -= 1
            if indeg[n] == 0:
                q.append(n)
    if len(finish) < len(dur):
        return None
    return max(finish.values(), default=0)


def ref_c06(ops):
    cap, d, out = ops[0][1], OrderedDict(), []
    for op in ops[1:]:
        if op[0] == 'get':
            if op[1] in d:
                d.move_to_end(op[1])
                out.append(d[op[1]])
            else:
                out.append(-1)
        elif cap > 0:
            if op[1] in d:
                d.move_to_end(op[1])
            d[op[1]] = op[2]
            if len(d) > cap:
                d.popitem(last=False)
    return out


def ref_c07(words):
    letters = sorted({c for w in words for c in w})
    adj = {c: set() for c in letters}
    indeg = {c: 0 for c in letters}
    for w1, w2 in zip(words, words[1:]):
        for a, b in zip(w1, w2):
            if a != b:
                if b not in adj[a]:
                    adj[a].add(b)
                    indeg[b] += 1
                break
        else:
            if len(w1) > len(w2):
                return ''
    h = [c for c in letters if indeg[c] == 0]
    heapq.heapify(h)
    out = []
    while h:
        c = heapq.heappop(h)
        out.append(c)
        for n in sorted(adj[c]):
            indeg[n] -= 1
            if indeg[n] == 0:
                heapq.heappush(h, n)
    return ''.join(out) if len(out) == len(letters) else ''


NEW_CODE = [
    ('C04', 'Write Python function solve(s) that evaluates an arithmetic expression string containing non-negative integers, + - * /, parentheses and unary minus or plus, with optional whitespace. * and / bind tighter than + and -; unary operators bind tighter than * and /. Division truncates toward zero. Return an int. Do not use eval.',
     ref_c04, ['3+2*2', ' 3/2 ', '-(2+3)*-4', '7-(-3)', '-7/2', '2*(3+(4-1))/4', '10/(-3)', '14-3*(2-5)/2', '1 - -1']),
    ('C05', "Write Python function solve(data). data has 'durations' (dict task->non-negative int) and 'deps' (list of [before, after] pairs). A task starts when all its prerequisites finish; independent tasks run in parallel. Return the minimum time to finish all tasks, 0 when there are no tasks, or None if deps contain a cycle or name an unknown task. Duplicate deps are allowed. Do not mutate input.",
     ref_c05, [{'durations': {'a': 3, 'b': 2, 'c': 4, 'd': 1}, 'deps': [['a', 'c'], ['b', 'c'], ['c', 'd']]},
               {'durations': {'a': 1, 'b': 1}, 'deps': [['a', 'b'], ['b', 'a']]},
               {'durations': {}, 'deps': []},
               {'durations': {'a': 2}, 'deps': [['a', 'z']]},
               {'durations': {'x': 0, 'y': 5, 'z': 0}, 'deps': [['x', 'y'], ['x', 'y'], ['y', 'z']]}]),
    ('C06', "Write Python function solve(ops) that simulates an LRU cache. ops[0] is ['init', capacity]; each later op is ['put', key, value] or ['get', key]. Return the list of get results (the value, or -1 if missing). get and put both make the key most recently used; put on an existing key updates its value; when size exceeds capacity evict the least recently used key; capacity 0 stores nothing. Do not mutate input.",
     ref_c06, [[['init', 2], ['put', 1, 1], ['put', 2, 2], ['get', 1], ['put', 3, 3], ['get', 2], ['put', 4, 4], ['get', 1], ['get', 3], ['get', 4]],
               [['init', 0], ['put', 1, 1], ['get', 1]],
               [['init', 2], ['put', 'a', 1], ['put', 'b', 2], ['put', 'a', 9], ['put', 'c', 3], ['get', 'b'], ['get', 'a'], ['get', 'c']],
               [['init', 1], ['put', 1, 1], ['get', 1], ['put', 2, 2], ['get', 1], ['get', 2]]]),
    ('C07', "Write Python function solve(words). words is a list of lowercase words sorted in an unknown alphabet's order. Return a string with every letter that appears, in an order consistent with the list; if several orders are valid return the lexicographically smallest one (by normal a-z order). Return '' if no order is valid, including when a word comes before its own proper prefix. Do not mutate input.",
     ref_c07, [['wrt', 'wrf', 'er', 'ett', 'rftt'], ['z', 'x', 'z'], ['abc', 'ab'], ['ba', 'bc', 'ac', 'cab'], ['cb', 'cb'], ['za', 'zb', 'ca', 'cb']]),
]


def all_tasks(new_corpus):
    old = v3_tasks()
    tasks = []
    for t in old:
        tasks.append({k: t[k] for k in ('id', 'family', 'corpus', 'query', 'criteria', 'gold', 'tests') if k in t})
    tasks += new_private(new_corpus)
    for ident, query, criteria, gold in REAL_EXTRA:
        tasks.append({'id': ident, 'family': 'project_knowledge', 'corpus': 'real', 'query': query, 'criteria': criteria, 'gold': gold})
    for ident, query, gold in NEW_REASONING:
        tasks.append({'id': ident, 'family': 'closed_reasoning', 'corpus': 'synthetic', 'query': query,
                      'criteria': ['Return the correct numeric answer'], 'gold': gold})
    for ident, query, ref, inputs in NEW_CODE:
        tests = [{'input': x, 'expected': ref(json.loads(json.dumps(x)))} for x in inputs]
        tasks.append({'id': ident, 'family': 'executable_code', 'corpus': 'synthetic', 'query': query,
                      'criteria': ['Implement solve with all stated edge cases'], 'gold': None, 'tests': tests})
    return tasks
