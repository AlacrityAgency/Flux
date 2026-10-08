"""v6 reasoning engine: deterministic classifier, program-of-thought pair, exact agreement, cascade.

No model calls here; providers are passed in. Everything is replayable from receipts.
"""
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
import json
import math
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
NUMBER = re.compile(r'(?<![A-Za-z_])\d+(?:\.\d+)?')
CODE_REQUEST = re.compile(r'\b(write|implement)\b[^.]*\b(function|class|code|program)\b|\bdef\s+\w+\s*\(|'
                          r'(تابع|کد|برنامه)[^.]*بنویس|بنویس[^.]*(تابع|کد|برنامه)', re.I)
COMPUTE_EN = re.compile(r'\b(how many|number of|count|compute|calculate|probability|expected|expectation|minimum|maximum|'
                        r'smallest|largest|shortest|longest|sum|product|remainder|mod|rounded|solutions?|digits?|'
                        r'what is|find|determine|distance|ways)\b', re.I)
COMPUTE_FA = re.compile(r'چند|چقدر|احتمال|امید ریاضی|کمترین|بیشترین|حداقل|حداکثر|کوتاه‌ترین|کوتاه ترین|باقیمانده|باقی‌مانده|'
                        r'مجموع|تعداد|رقم|محاسبه|حساب کن|گرد')
OPEN_CUES = re.compile(r'\b(why|explain|describe|compare|discuss|should|pros and cons|trade-?offs?|opinion|recommend)\b|'
                       r'چرا|توضیح|مقایسه|بررسی کن|پیشنهاد|نظر', re.I)
WORD_NUM = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
FA_NUM = {'یک': 1, 'دو': 2, 'سه': 3, 'چهار': 4, 'پنج': 5, 'شش': 6, 'هفت': 7, 'هشت': 8, 'نه': 9, 'ده': 10}
FA_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


@dataclass(frozen=True)
class AnswerSpec:
    kind: str = 'number'          # integer | probability | number
    places: int | None = None     # decimal places when rounding is requested


@dataclass(frozen=True)
class Classified:
    kind: str                     # fact | computable | project_computable | code | open | uncertain
    spec: AnswerSpec
    reason: str


def answer_spec(query):
    q = query.translate(FA_DIGITS).lower()
    places = None
    m = re.search(r'(\w+)\s+decimal', q) or re.search(r'(\S+)\s*رقم\s*(?:اعشار|بعد از ممیز)', q)
    if m:
        tok = m.group(1)
        places = int(tok) if tok.isdigit() else WORD_NUM.get(tok, FA_NUM.get(tok))
    if re.search(r'\bprobability\b|احتمال', q):
        return AnswerSpec('probability', places)
    if places is not None:
        return AnswerSpec('number', places)
    if re.search(r'\b(how many|number of|count|smallest|largest|minimum number|integer|digits|remainder)\b|'
                 r'چند (?:عدد|رشته|راه|مسیر|جواب|سکه|عضو)|تعداد|کوچک‌ترین عدد|باقی‌?مانده|رقم', q):
        return AnswerSpec('integer', None)
    return AnswerSpec('number', None)


def classify(query, public_tests=(), project_needs=()):
    """Deterministic route. project_needs: typed needs v5 resolved for this request (may be empty)."""
    q = query.translate(FA_DIGITS)
    numbers = len(NUMBER.findall(q))
    computes = bool(COMPUTE_EN.search(q) or COMPUTE_FA.search(q))
    spec = answer_spec(query)
    if public_tests or CODE_REQUEST.search(q):
        return Classified('code', spec, 'code request')
    if project_needs:
        return Classified('project_computable' if computes and numbers >= 1 and not OPEN_CUES.search(q) else 'fact',
                          spec, 'typed project need')
    if OPEN_CUES.search(q) and numbers < 2:
        return Classified('open', spec, 'explanation or judgment')
    if numbers >= 2 and computes:
        return Classified('computable', spec, 'inline data + compute cue')
    if numbers >= 2 or computes:
        return Classified('uncertain', spec, 'partial compute signal')
    return Classified('open', spec, 'no checker available')


PROGRAM_CONTRACT = (
    'Do not use tools, files, browsing or commands. Write a Python program that computes the answer to the task.\n'
    'Return only JSON: {"code": "<python source>"}.\n'
    'The source must define solve() with no parameters that returns the final answer as int, fractions.Fraction or float.\n'
    'Use exact int / Fraction arithmetic; use float only for the final rounding the task asks for.\n'
    'No randomness, no simulation, no input/output, no classes. Imports only from: math, fractions, itertools, functools, '
    'collections, heapq, bisect. It must finish within 2 seconds.\n')
METHODS = {
    'A': 'Method: solve it analytically with the standard formula, theorem or textbook algorithm for this problem type.',
    'B': ('Method: solve it independently by direct construction of the stated objects: exhaustive enumeration, '
          'dynamic programming, or exactly solving the state equations. Do not rely on a closed-form formula for the final value.'),
}
DIRECT_CONTRACT = ('Solve the task using only the prompt. Do not call tools, inspect files, browse, or run commands. '
                   'Return exactly one JSON object. Use keys "answer" (a single number) and "citations" (empty array). ')


def program_prompt(query, method):
    return PROGRAM_CONTRACT+METHODS[method]+'\nTASK:\n'+query


def direct_prompt(query):
    return DIRECT_CONTRACT+'\nTASK:\n'+query


def parse_json(text):
    s = (text or '').strip()
    if s.startswith('```'):
        s = re.sub(r'^```(?:json|python)?\s*', '', s)
        s = re.sub(r'\s*```$', '', s)
    try:
        return json.loads(s)
    except ValueError:
        m = re.search(r'\{.*\}', s, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def run_program(code, timeout=2.5, facts=None):
    start = time.perf_counter()
    job = {'code': code} if facts is None else {'code': code, 'facts': facts}
    try:
        p = subprocess.run([sys.executable, '-I', '-S', str(HERE/'worker_v6.py')], input=json.dumps(job),
                           capture_output=True, text=True, encoding='utf-8', timeout=timeout)
        receipt = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {'status': 'error', 'error': 'no output'}
    except subprocess.TimeoutExpired:
        receipt = {'status': 'timeout'}
    except ValueError as e:
        receipt = {'status': 'error', 'error': 'bad receipt: '+str(e)[:80]}
    receipt['exec_ms'] = (time.perf_counter()-start)*1000
    return receipt


def to_fraction(result):
    """Tagged worker result or a plain JSON number -> Fraction, else None."""
    if result is None:
        return None
    if isinstance(result, dict) and result.get('type') in ('fraction', 'decimal'):
        n, d = result['value']
        return Fraction(n, d)
    if isinstance(result, bool):
        return None
    if isinstance(result, (int, float)):
        return Fraction(repr(result)) if isinstance(result, float) and math.isfinite(result) else (Fraction(result) if isinstance(result, int) else None)
    if isinstance(result, str):
        try:
            return Fraction(result.strip())
        except (ValueError, ZeroDivisionError):
            return None
    return None


def close(a, b, spec):
    """Same answer under the requested format. Rounded answers may differ by one unit in the last place."""
    if a is None or b is None:
        return False
    if spec.places is not None:
        return abs(a-b) <= Fraction(1, 10**spec.places)+Fraction(1, 10**12)
    if a.denominator == 1 and b.denominator == 1:
        return a == b
    return abs(a-b) <= max(Fraction(1, 10**9), abs(b)*Fraction(1, 10**9))


def sanity(value, spec):
    if value is None:
        return False
    if spec.kind == 'probability' and not (0 <= value <= 1):
        return False
    if spec.kind == 'integer' and value.denominator != 1:
        return False
    return True


def grade(value, gold, spec):
    """Evaluator only: same rule for every arm."""
    if value is None:
        return False
    g = Fraction(str(gold)) if isinstance(gold, float) else Fraction(gold)
    if spec.places is not None:
        return abs(value-g) <= Fraction(5, 10**(spec.places+1))+Fraction(1, 10**12)
    if g.denominator == 1 and value.denominator == 1:
        return value == g
    return abs(value-g) <= max(Fraction(1, 10**9), abs(g)*Fraction(1, 10**9))


@dataclass
class Trial:
    """One sample of one task: receipts for A, B and the Sol answer (escalation target)."""
    a: dict
    b: dict
    sol: dict
    spec: AnswerSpec
    out: dict = field(default_factory=dict)


def cascade(t, hedge_after=None):
    """Decision + replayed latency. economy: Sol only after A and B finish and disagree.
    hedged: Sol starts at hedge_after seconds if no agreement yet; first acceptable answer wins."""
    va, vb = t.a.get('value'), t.b.get('value')
    agree = (t.a.get('exec') == 'ok' and t.b.get('exec') == 'ok' and close(va, vb, t.spec)
             and sanity(va, t.spec) and sanity(vb, t.spec))
    la, lb, ls = t.a['latency'], t.b['latency'], t.sol['latency']
    exec_s = (t.a.get('exec_ms', 0)+t.b.get('exec_ms', 0))/2000
    pair_done = max(la, lb)+exec_s
    if agree:
        economy = {'value': va, 'status': 'agreed', 'calls': 2, 'sol': 0, 'latency': pair_done}
    else:
        economy = {'value': t.sol.get('value'), 'status': 'escalated', 'calls': 3, 'sol': 1, 'latency': pair_done+ls}
    if hedge_after is None:
        return economy, None
    if agree and pair_done <= hedge_after:
        hedged = dict(economy)
    elif agree:
        sol_done = hedge_after+ls
        hedged = ({'value': va, 'status': 'agreed', 'calls': 3, 'sol': 1, 'latency': pair_done} if pair_done <= sol_done
                  else {'value': t.sol.get('value'), 'status': 'escalated', 'calls': 3, 'sol': 1, 'latency': sol_done})
    else:
        hedged = {'value': t.sol.get('value'), 'status': 'escalated', 'calls': 3, 'sol': 1,
                  'latency': max(hedge_after, 0)+ls if pair_done > hedge_after else pair_done+ls}
    return economy, hedged
