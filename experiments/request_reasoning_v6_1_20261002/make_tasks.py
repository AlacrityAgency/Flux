"""Evaluator-side fresh generators. Never imported by the inference engine."""
from itertools import product, permutations
from pathlib import Path
import json
import random
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'request_memory_v6_20261002'))
import tasks_v6 as OLD


def build():
    rng = random.Random(610120261002)
    result = []
    def add(family, query, gold, lang='en'):
        result.append({'id': f'{family}_{sum(t["family"] == family for t in result)}',
                       'family': family, 'lang': lang, 'query': query, 'gold': gold})
    for j, (name, gen) in enumerate(OLD.FAMILIES):
        idx = 3 if j % 2 else (1 if name == 'coins' else 0)
        q, g = gen(rng, idx)
        add(name, q, g, 'fa' if idx == 3 else 'en')
    for name, gen in [('coins', OLD.coins), ('pattern', OLD.pattern)]:
        q, g = gen(rng, 2)
        add(name, q, g)
    # CNF: independent complete enumeration, with implication and cardinality.
    for i in range(3):
        clauses = []
        for _ in range(7+i):
            variables = rng.sample(range(5), 3)
            clauses.append([(v, rng.choice([True, False])) for v in variables])
        k = 2+i%2
        gold = sum(sum(bits) == k and all(any(bits[v] == sign for v, sign in c) for c in clauses)
                   for bits in product([False, True], repeat=5))
        texts = ['('+' OR '.join(('' if sign else 'NOT ')+chr(65+v) for v, sign in c)+')' for c in clauses]
        q = 'Boolean variables A,B,C,D,E satisfy all these clauses: '+' AND '.join(texts)+f'. Exactly {k} variables are true. How many satisfying assignments exist?'
        if i == 2:
            q = 'متغیرهای بولی A,B,C,D,E باید همهٔ این بندها را ارضا کنند: '+' AND '.join(texts)+f'. دقیقاً {k} متغیر درست باشد. تعداد انتساب‌های مجاز چند است؟ OR یعنی یا و NOT یعنی نقیض.'
        add('logic_sat', q, gold, 'fa' if i == 2 else 'en')
    # Knights/knaves: statement truth iff the speaker is a knight.
    for i in range(3):
        refs = [rng.sample(range(5), 2) for _ in range(5)]
        ops = [rng.choice(['same', 'different', 'both', 'neither', 'exactly_one']) for _ in range(5)]
        def statement(bits, pair, op):
            a, b = (bits[x] for x in pair)
            return {'same': a == b, 'different': a != b, 'both': a and b,
                    'neither': not (a or b), 'exactly_one': a != b}[op]
        gold = sum(all(bits[j] == statement(bits, refs[j], ops[j]) for j in range(5))
                   for bits in product([False, True], repeat=5))
        phrases = {'same': 'have the same type', 'different': 'have different types',
                   'both': 'are both knights', 'neither': 'are both knaves', 'exactly_one': 'include exactly one knight'}
        statements = [f'{chr(65+j)} says: {chr(65+p[0])} and {chr(65+p[1])} {phrases[op]}' for j, (p, op) in enumerate(zip(refs, ops))]
        q = 'Each of A,B,C,D,E is either a knight (every statement true) or a knave (every statement false). '+ '; '.join(statements)+'. How many assignments of types satisfy all statements?'
        add('logic_knights', q, gold)
    # Orders: enumerate every permutation; do not use solver's graph algorithm.
    for i in range(3):
        hidden = list('ABCDEF')
        rng.shuffle(hidden)
        pairs = rng.sample([(hidden[a], hidden[b]) for a in range(6) for b in range(a+1, 6)], 6)
        x, y = rng.sample(list('ABCDEF'), 2)
        gold = 0
        for order in permutations('ABCDEF'):
            pos = {v: j for j, v in enumerate(order)}
            gold += all(pos[a] < pos[b] for a,b in pairs) and abs(pos[x]-pos[y]) != 1
        q = 'Arrange A,B,C,D,E,F in a single row, each exactly once. Constraints: '+ '; '.join(f'{a} before {b}' for a,b in pairs)+f'; {x} and {y} must NOT be adjacent. How many arrangements are possible?'
        add('logic_order', q, gold)
    # Finite assignments with distinctness and one disequality relation.
    for i in range(3):
        values = [1,2,3,4,5]
        forbidden = [rng.choice(values) for _ in range(4)]
        total = rng.randrange(9,16)
        delta = rng.choice([1,2])
        gold = sum(sum(xs)==total and all(x != f for x,f in zip(xs,forbidden)) and abs(xs[0]-xs[2]) != delta
                   for xs in permutations(values,4))
        q = f'Assign four pairwise distinct integers A,B,C,D from {{1,2,3,4,5}}. Their sum is {total}. '+', '.join(f'{v} != {f}' for v,f in zip('ABCD',forbidden))+f'. Also |A-C| != {delta}. How many ordered assignments satisfy every condition?'
        if i == 2:
            q = f'چهار عدد صحیح متمایز A,B,C,D را از مجموعه {{1,2,3,4,5}} انتخاب کن. مجموع آن‌ها {total} باشد. '+', '.join(f'{v} != {f}' for v,f in zip('ABCD',forbidden))+f'. همچنین |A-C| != {delta}. تعداد انتساب‌های مرتب مجاز چند است؟'
        add('logic_assignment', q, gold, 'fa' if i == 2 else 'en')
    return result


if __name__ == '__main__':
    ts = build()
    (HERE/'evaluation_only').mkdir(exist_ok=True)
    (HERE/'tasks.json').write_text(json.dumps([{k:v for k,v in t.items() if k!='gold'} for t in ts], ensure_ascii=False, indent=2), encoding='utf-8')
    (HERE/'evaluation_only/gold.json').write_text(json.dumps({t['id']:t['gold'] for t in ts}, indent=2), encoding='utf-8')
    print(json.dumps({'tasks':len(ts),'logic_tasks':12}))
