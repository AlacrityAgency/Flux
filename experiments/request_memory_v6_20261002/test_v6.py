from fractions import Fraction
import pytest
import reasoning_v6 as R
import tasks_v6 as T

CRT = '''
from math import prod
def solve():
    ms, rs = [23, 9, 5], [22, 5, 2]
    x, m = 0, 1
    for mi, ri in zip(ms, rs):
        while x % mi != ri:
            x += m
        m *= mi
    return x
'''
PATTERN = '''
from fractions import Fraction
from functools import lru_cache
def solve():
    pat = (2, 3, 2)
    def nxt(state, face):
        s = list(pat[:state]) + [face]
        while s and tuple(s) != pat[:len(s)]:
            s = s[1:]
        return len(s)
    n = len(pat)
    A = [[Fraction(0)] * n for _ in range(n)]
    b = [Fraction(1)] * n
    for st in range(n):
        A[st][st] += 1
        for f in range(1, 7):
            t = nxt(st, f)
            if t < n:
                A[st][t] -= Fraction(1, 6)
    for c in range(n):
        p = next(r for r in range(c, n) if A[r][c] != 0)
        A[c], A[p] = A[p], A[c]
        b[c], b[p] = b[p], b[c]
        for r in range(n):
            if r != c and A[r][c] != 0:
                f = A[r][c] / A[c][c]
                A[r] = [x - f * y for x, y in zip(A[r], A[c])]
                b[r] -= f * b[c]
    return b[0] / A[0][0]
'''
NONLOCAL = '''
def solve():
    total = 0
    def add(k):
        nonlocal total
        total += pow(k, 2, 1000)
    for k in range(5):
        add(k)
    return divmod(total, 7)[1] + round(0.25, 1)
'''


def run(code):
    return R.run_program(code, timeout=5)


def test_worker_supports_exact_math_constructs():
    assert R.to_fraction(run(CRT)['result']) == 482
    assert R.to_fraction(run(PATTERN)['result']) == 222
    r = run(NONLOCAL)
    assert r['status'] == 'ok' and R.to_fraction(r['result']) == Fraction(2) + Fraction('0.2')


@pytest.mark.parametrize('code', ['import os\ndef solve(): return 1', 'def solve(): return eval("1")',
                                  'def solve(): return open("x").read()', 'def solve(): return (1).__class__',
                                  'class A: pass\ndef solve(): return 1', 'def solve(): return __import__("os")'])
def test_worker_rejects_unsafe_code(code):
    assert run(code)['status'] == 'error'


def test_worker_timeout():
    r = R.run_program('def solve():\n    while True:\n        pass', timeout=1)
    assert r['status'] == 'timeout'


def test_answer_spec_and_classifier():
    assert R.answer_spec('What is the probability ... Round to six decimals.') == R.AnswerSpec('probability', 6)
    assert R.answer_spec('احتمال ابتلا چقدر است؟ تا شش رقم اعشار گرد کن.') == R.AnswerSpec('probability', 6)
    assert R.answer_spec('How many binary strings of length 16 ...').kind == 'integer'
    assert R.classify('Write Python function solve(rows) that returns x.').kind == 'code'
    assert R.classify('Explain why ledgers matter.').kind == 'open'
    assert R.classify('باقیماندهٔ تقسیم ۸۸۷^۷۰۱۴ بر ۶۵۲ چند است؟').kind == 'computable'
    assert R.classify('What is owner?', project_needs=('n0',)).kind == 'fact'


def test_agreement_rules():
    p6 = R.AnswerSpec('probability', 6)
    assert R.close(Fraction('0.323747'), Fraction(3237466, 10**7), p6)
    assert not R.close(Fraction('0.3237'), Fraction('0.3247'), p6)
    assert R.close(Fraction(216), Fraction(216), R.AnswerSpec('integer'))
    assert not R.sanity(Fraction(3, 2), p6) and not R.sanity(Fraction(1, 2), R.AnswerSpec('integer'))
    assert R.grade(Fraction('0.3237474'), 0.323747, p6) and not R.grade(Fraction('0.32376'), 0.323747, p6)


def trial(va, vb, sol, ea='ok', eb='ok', la=6, lb=8, ls=11, spec=R.AnswerSpec('integer')):
    return R.Trial({'value': va, 'exec': ea, 'latency': la, 'exec_ms': 100},
                   {'value': vb, 'exec': eb, 'latency': lb, 'exec_ms': 100},
                   {'value': sol, 'latency': ls}, spec)


def test_cascade_agree_disagree_and_hedge():
    e, h = R.cascade(trial(Fraction(5), Fraction(5), Fraction(7)), hedge_after=7)
    assert e['status'] == 'agreed' and e['value'] == 5 and e['sol'] == 0 and abs(e['latency']-8.1) < 1e-9
    assert h['status'] == 'agreed' and h['sol'] == 1          # pair finished after hedge, Sol already sent
    e, h = R.cascade(trial(Fraction(5), Fraction(6), Fraction(7)), hedge_after=7)
    assert e['status'] == 'escalated' and e['value'] == 7 and abs(e['latency']-19.1) < 1e-9
    assert abs(h['latency']-18) < 1e-9                        # Sol started at 7 s
    e, _ = R.cascade(trial(Fraction(5), None, Fraction(7), eb='error'))
    assert e['status'] == 'escalated'
    e, h = R.cascade(trial(Fraction(5), Fraction(5), Fraction(7), la=3, lb=4), hedge_after=7)
    assert h['sol'] == 0 and h['latency'] == e['latency']


def test_tasks_are_deterministic_and_complete():
    a, b = T.fresh_tasks(), T.fresh_tasks()
    assert a == b and len(a) == 40 and len({t['id'] for t in a}) == 40
    assert len(T.regression_tasks()) == 16
    assert sum(t['lang'] == 'fa' for t in a) == 10
