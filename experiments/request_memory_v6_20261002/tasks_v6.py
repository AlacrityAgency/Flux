"""Fresh computable reasoning tasks (seeded generators + independent reference solvers) and regression tasks.

Gold is computed here and written only to evaluation_only/; it never enters prompts.
"""
from fractions import Fraction
from functools import lru_cache
from itertools import combinations, product
from pathlib import Path
import heapq
import json
import math
import random
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
SEED = 61002
FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def fa(text):
    return text.translate(FA)


def bayes(rng, i):
    s, f, p = rng.randrange(85, 100)/100, rng.randrange(10, 100)/1000, rng.randrange(2, 60)/1000
    S, F, P = Fraction(str(s)), Fraction(str(f)), Fraction(str(p))
    gold = float(round(P*S/(P*S+(1-P)*F), 6))
    if i == 3:
        q = fa(f'یک آزمایش غربالگری حساسیت {s} و نرخ مثبت کاذب {f} دارد. شیوع بیماری {p} است. '
               f'اگر نتیجهٔ آزمایش مثبت باشد، احتمال ابتلای فرد چقدر است؟ تا شش رقم اعشار گرد کن.')
    else:
        q = (f'A screening test has sensitivity {s} and false-positive rate {f}. The prevalence of the condition is {p}. '
             f'Given a positive result, what is the probability that the person has the condition? Round to six decimals.')
    return q, gold


def crt(rng, i):
    pool = [5, 7, 8, 9, 11, 13, 16, 17, 19, 23, 25, 27]
    while True:
        ms = rng.sample(pool, 3)
        if all(math.gcd(a, b) == 1 for a, b in combinations(ms, 2)):
            break
    rs = [rng.randrange(m) for m in ms]
    gold = next(x for x in range(math.prod(ms)) if all(x % m == r for m, r in zip(ms, rs)))
    if i == 3:
        q = fa(f'کوچک‌ترین عدد صحیح نامنفی x را پیدا کن که باقیماندهٔ تقسیم آن بر {ms[0]} برابر {rs[0]}، '
               f'بر {ms[1]} برابر {rs[1]} و بر {ms[2]} برابر {rs[2]} باشد.')
    else:
        q = f'Find the smallest nonnegative integer x such that x mod {ms[0]} = {rs[0]}, x mod {ms[1]} = {rs[1]}, and x mod {ms[2]} = {rs[2]}.'
    return q, gold


def pattern_expectation(pattern, sides=6):
    """Expected rolls until pattern via KMP automaton and exact linear equations (independent of overlap formula)."""
    k = len(pattern)

    def step(state, face):
        s = list(pattern[:state])+[face]
        while s and s != list(pattern[:len(s)]):
            s = s[1:]
        return len(s)
    # E[state] = 1 + avg E[next]; E[k]=0. Solve by Gaussian elimination over Fractions.
    n = k
    A = [[Fraction(0)]*n for _ in range(n)]
    b = [Fraction(1)]*n
    for st in range(n):
        A[st][st] += 1
        for face in range(1, sides+1):
            nx = step(st, face)
            if nx < k:
                A[st][nx] -= Fraction(1, sides)
    for c in range(n):
        p = next(r for r in range(c, n) if A[r][c] != 0)
        A[c], A[p], b[c], b[p] = A[p], A[c], b[p], b[c]
        for r in range(n):
            if r != c and A[r][c] != 0:
                f = A[r][c]/A[c][c]
                A[r] = [x-f*y for x, y in zip(A[r], A[c])]
                b[r] -= f*b[c]
    return b[0]/A[0][0]


def pattern(rng, i):
    a, b = rng.sample(range(1, 7), 2)
    pat = [[a, b, rng.randrange(1, 7), a], [a, b, a], [a, a, a], [a, a, b]][i]
    gold = pattern_expectation(pat)
    n = len(pat)
    overlap = sum(6**j for j in range(1, n+1) if pat[:j] == pat[n-j:])
    assert gold == overlap
    p = ','.join(map(str, pat))
    if i == 3:
        q = fa(f'یک تاس سالم شش‌وجهی را پشت سر هم می‌اندازیم. امید ریاضی تعداد پرتاب‌ها تا اولین باری که الگوی متوالی {p} '
               f'ظاهر شود چقدر است؟ مقدار دقیق را بده.')
    else:
        q = f'A fair six-sided die is rolled repeatedly. What is the expected number of rolls until the consecutive pattern {p} first appears? Give the exact value.'
    return q, int(gold)


def shortest(rng, i):
    nodes = 'ABCDEFG'
    while True:
        edges = {}
        for _ in range(13):
            u, v = rng.sample(nodes, 2)
            edges[(u, v)] = rng.randrange(1, 16)
        dist = {n: math.inf for n in nodes}
        dist['A'] = 0
        pq = [(0, 'A')]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            for (x, y), w in edges.items():
                if x == u and d+w < dist[y]:
                    dist[y] = d+w
                    heapq.heappush(pq, (d+w, y))
        # Independent Bellman-Ford check.
        bf = {n: math.inf for n in nodes}
        bf['A'] = 0
        for _ in range(len(nodes)):
            for (x, y), w in edges.items():
                bf[y] = min(bf[y], bf[x]+w)
        if dist['G'] < math.inf and dist['G'] == bf['G'] and ('A', 'G') not in edges:
            break
    listing = ', '.join(f'{u}->{v}:{w}' for (u, v), w in sorted(edges.items()))
    if i == 3:
        q = fa(f'یک گراف جهت‌دار وزن‌دار این یال‌ها را دارد (یال X->Y:w یعنی از X به Y با وزن w): {listing}. '
               f'کوتاه‌ترین فاصله از A تا G چقدر است؟')
    else:
        q = f'A weighted directed graph has edges {listing} (X->Y:w is an edge from X to Y with weight w). What is the shortest-path distance from A to G?'
    return q, int(dist['G'])


def venn(rng, i):
    r = {k: rng.randrange(3, 40) for k in ('a', 'b', 'c', 'ab', 'ac', 'bc', 'abc', 'none')}
    A = r['a']+r['ab']+r['ac']+r['abc']
    B = r['b']+r['ab']+r['bc']+r['abc']
    C = r['c']+r['ac']+r['bc']+r['abc']
    AB, AC, BC, ABC = r['ab']+r['abc'], r['ac']+r['abc'], r['bc']+r['abc'], r['abc']
    N = sum(r.values())
    ask = ['exactly one', 'exactly two', 'none', 'exactly one'][i]
    gold = {'exactly one': r['a']+r['b']+r['c'], 'exactly two': r['ab']+r['ac']+r['bc'], 'none': r['none']}[ask]
    assert gold == {'exactly one': A+B+C-2*(AB+AC+BC)+3*ABC, 'exactly two': AB+AC+BC-3*ABC,
                    'none': N-(A+B+C-AB-AC-BC+ABC)}[ask]
    if i == 3:
        q = fa(f'از {N} دانشجو، {A} نفر هنر، {B} نفر زیست و {C} نفر شیمی می‌گیرند؛ {AB} نفر هنر و زیست، {AC} نفر هنر و شیمی، '
               f'{BC} نفر زیست و شیمی، و {ABC} نفر هر سه را می‌گیرند. تعداد دانشجویانی که دقیقاً یکی از این درس‌ها را می‌گیرند چند است؟')
    else:
        what = {'exactly one': 'exactly one of these subjects', 'exactly two': 'exactly two of these subjects',
                'none': 'none of these subjects'}[ask]
        q = (f'Among {N} students, {A} take art, {B} take biology and {C} take chemistry; {AB} take both art and biology, '
             f'{AC} take art and chemistry, {BC} take biology and chemistry, and {ABC} take all three. How many students take {what}?')
    return q, gold


def compositions(rng, i):
    k, c = rng.choice([3, 4, 5]), rng.randrange(5, 10)
    n = rng.randrange(c+1, k*c-c)

    @lru_cache(None)
    def ways(j, left):
        if j == 0:
            return int(left == 0)
        return sum(ways(j-1, left-x) for x in range(0, min(c, left)+1))
    gold = ways(k, n)
    assert gold == sum((-1)**j*math.comb(k, j)*math.comb(n-j*(c+1)+k-1, k-1) for j in range(k+1) if n-j*(c+1) >= 0)
    if i == 3:
        q = fa(f'تعداد {k}تایی‌های مرتب از اعداد صحیح (x1,...,x{k}) که مجموعشان {n} است و هر xi بین 0 و {c} (با خود این دو) است چند است؟')
    else:
        q = f'How many ordered tuples of {k} integers (x1,...,x{k}) satisfy x1+...+x{k} = {n} with 0 <= xi <= {c} for every i?'
    return q, gold


def coins(rng, i):
    vals = sorted(rng.sample([2, 3, 4, 5, 7, 9, 11, 13, 17], 4))
    T = rng.randrange(40, 90)
    if i in (0, 2):
        ways = [1]+[0]*T
        for v in vals:
            for t in range(v, T+1):
                ways[t] += ways[t-v]
        gold = ways[T]
        brute = sum(1 for a in range(T//vals[0]+1) for b in range(T//vals[1]+1) for c in range(T//vals[2]+1)
                    if (T-a*vals[0]-b*vals[1]-c*vals[2]) >= 0 and (T-a*vals[0]-b*vals[1]-c*vals[2]) % vals[3] == 0)
        assert gold == brute
        q = f'Using unlimited coins of values {", ".join(map(str, vals))}, in how many different ways (order does not matter) can you make exactly {T}?'
        return q, gold
    best = [0]+[math.inf]*T
    for t in range(1, T+1):
        best[t] = min((best[t-v]+1 for v in vals if v <= t), default=math.inf)
    if best[T] == math.inf:
        return coins(rng, i)
    gold = best[T]
    if i == 3:
        q = fa(f'با سکه‌های نامحدود به ارزش‌های {"، ".join(map(str, vals))}، حداقل تعداد سکه برای ساختن دقیقاً مبلغ {T} چند است؟')
    else:
        q = f'Using unlimited coins of values {", ".join(map(str, vals))}, what is the minimum number of coins needed to make exactly {T}?'
    return q, gold


def strings_paths(rng, i):
    if i in (0, 2):
        n, k = rng.randrange(14, 22), rng.randrange(4, 8)
        gold = sum(1 for ones in combinations(range(n), k) if all(b-a > 1 for a, b in zip(ones, ones[1:])))
        assert gold == math.comb(n-k+1, k)
        return f'How many binary strings of length {n} contain exactly {k} ones with no two ones adjacent?', gold
    a, b = rng.randrange(6, 10), rng.randrange(5, 8)
    p, q0 = rng.randrange(1, a), rng.randrange(1, b)
    grid = [[0]*(b+1) for _ in range(a+1)]
    for x in range(a+1):
        for y in range(b+1):
            if (x, y) == (p, q0):
                continue
            grid[x][y] = 1 if x == y == 0 else (grid[x-1][y] if x else 0)+(grid[x][y-1] if y else 0)
    gold = grid[a][b]
    assert gold == math.comb(a+b, a)-math.comb(p+q0, p)*math.comb(a-p+b-q0, a-p)
    if i == 3:
        q = fa(f'تعداد مسیرهای شبکه‌ای از (0,0) تا ({a},{b}) با گام‌های واحد به راست یا بالا که از نقطهٔ ({p},{q0}) عبور نمی‌کنند چند است؟')
    else:
        q = f'How many lattice paths from (0,0) to ({a},{b}) using unit steps right or up avoid the point ({p},{q0})?'
    return q, gold


def urn(rng, i):
    r, b, g, m = rng.randrange(4, 10), rng.randrange(4, 10), rng.randrange(4, 10), rng.randrange(4, 7)
    total = math.comb(r+b+g, m)
    counts = {}
    for x in range(m+1):
        for y in range(m+1-x):
            z = m-x-y
            counts[(x, y, z)] = math.comb(r, x)*math.comb(b, y)*math.comb(g, z)
    two = sum(v for (x, y, z), v in counts.items() if sum(t > 0 for t in (x, y, z)) == 2)
    three = sum(v for (x, y, z), v in counts.items() if min(x, y, z) > 0)
    want = 'two' if i in (0, 2) else 'three'
    gold = float(round(Fraction(two if want == 'two' else three, total), 6))
    if i == 3:
        q = fa(f'در یک کیسه {r} توپ قرمز، {b} توپ آبی و {g} توپ سبز هست. {m} توپ به‌تصادف و بدون جایگذاری بیرون می‌آوریم. '
               f'احتمال اینکه هر سه رنگ در توپ‌های بیرون‌آمده باشند چقدر است؟ تا شش رقم اعشار گرد کن.')
    else:
        phrase = 'exactly two colors appear' if want == 'two' else 'all three colors appear'
        q = (f'A bag contains {r} red, {b} blue and {g} green balls. {m} balls are drawn uniformly at random without replacement. '
             f'What is the probability that {phrase} among the drawn balls? Round to six decimals.')
    return q, gold


def modular(rng, i):
    a, e = rng.randrange(101, 999), rng.randrange(1000, 9999)
    if i in (0, 2):
        gold = pow(a, e, 1000)
        return f'What are the last three digits of {a}^{e}? Give them as an integer (drop leading zeros).', gold
    c, d, m = rng.randrange(11, 99), rng.randrange(100, 999), rng.randrange(37, 997)
    if i == 3:
        gold = pow(a, e, m)
        return fa(f'باقیماندهٔ تقسیم {a}^{e} بر {m} چند است؟'), gold
    gold = (pow(a, e, m)+pow(c, d, m)) % m
    return f'What is the remainder when {a}^{e} + {c}^{d} is divided by {m}?', gold


FAMILIES = [('bayes', bayes), ('crt', crt), ('pattern', pattern), ('shortest_path', shortest), ('inclusion_exclusion', venn),
            ('compositions', compositions), ('coins', coins), ('strings_paths', strings_paths), ('urn', urn), ('modular', modular)]


def fresh_tasks():
    rng = random.Random(SEED)
    out = []
    for name, gen in FAMILIES:
        for i in range(4):
            q, gold = gen(rng, i)
            out.append({'id': f'{name}_{i}', 'family': name, 'set': 'fresh', 'lang': 'fa' if i == 3 else 'en',
                        'query': q, 'gold': gold})
    return out


def regression_tasks():
    old = json.loads((EXP/'request_memory_v3_20261002/evaluation_only/tasks.json').read_text(encoding='utf-8'))
    out = [{'id': t['id'], 'family': 'regression', 'set': 'regression', 'lang': 'en', 'query': t['query'], 'gold': t['gold']}
           for t in old if t['id'].startswith('R')]
    sys.path.insert(0, str(EXP/'router_pilot_20261002'))
    import tasks as router_tasks
    out += [{'id': i, 'family': 'regression', 'set': 'regression', 'lang': 'en', 'query': q, 'gold': g}
            for i, q, g in router_tasks.NEW_REASONING]
    return out


OPEN = [
    'Explain why canonical revisions should be resolved before status filtering in a memory store.',
    'Compare program-of-thought prompting with chain-of-thought prompting for small models.',
    'Should Flux escalate to a stronger model when evidence is missing? Discuss the trade-offs.',
    'Describe the role of a ledger in an idempotent controller.',
    'Why might two independent programs agree on a wrong answer?',
    'چرا پاسخ مستقیم از حافظه سریع‌تر از فراخوانی مدل است؟ توضیح بده.',
    'مسیریابی بر اساس نوع سؤال را با مسیریابی بر اساس اطمینان مدل مقایسه کن.',
    'پیشنهاد تو برای کاهش سربار هر فراخوانی CLI چیست؟',
    'Explain why 3 retries with a 2 second timeout might still be too slow for an interactive request.',
    'Discuss whether 16 tasks are enough to estimate a 2 percent error rate.',
]


def classifier_set():
    """Labelled requests for the deterministic classifier (no model calls)."""
    items = [{'query': t['query'], 'label': 'computable', 'source': t['set']} for t in fresh_tasks()+regression_tasks()]
    sys.path.insert(0, str(EXP/'router_pilot_20261002'))
    import tasks as router_tasks
    old = json.loads((EXP/'request_memory_v3_20261002/evaluation_only/tasks.json').read_text(encoding='utf-8'))
    items += [{'query': t['query'], 'label': 'code', 'source': 'code'} for t in old if t['id'].startswith('C')]
    items += [{'query': q, 'label': 'code', 'source': 'code'} for _, q, _, _ in router_tasks.NEW_CODE]
    items += [{'query': q, 'label': 'open', 'source': 'open'} for q in OPEN]
    return items
