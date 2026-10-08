"""Exact, restricted runner for model-written programs: solve() -> answer.

Reads {"code": str} on stdin, prints one JSON receipt. No files, network or eval.
Not an OS sandbox; production needs process isolation with hard memory limits.
"""
import ast
import builtins
import json
import math
import sys
from fractions import Fraction

MODULES = {'math', 'fractions', 'itertools', 'functools', 'collections', 'heapq', 'bisect',
           'decimal', 'operator', 'statistics', 'string'}
DENIED = {'eval', 'exec', 'open', 'compile', 'input', 'globals', 'locals', 'getattr', 'setattr', 'delattr',
          'vars', 'dir', 'breakpoint', 'help', '__import__', 'memoryview', 'type', 'object', 'super'}
ALLOWED = ['abs', 'all', 'any', 'bool', 'chr', 'dict', 'divmod', 'enumerate', 'filter', 'float', 'frozenset',
           'int', 'isinstance', 'iter', 'len', 'list', 'map', 'max', 'min', 'next', 'ord', 'pow', 'range',
           'reversed', 'round', 'set', 'slice', 'sorted', 'str', 'sum', 'tuple', 'zip', 'hash',
           'Exception', 'ValueError', 'KeyError', 'IndexError', 'ZeroDivisionError', 'StopIteration',
           'ArithmeticError', 'RecursionError', 'True', 'False', 'None']


def check(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [x.name.split('.')[0] for x in node.names] if isinstance(node, ast.Import) else [(node.module or '').split('.')[0]]
            if node.__class__ is ast.ImportFrom and node.level:
                raise ValueError('Relative import')
            if any(n not in MODULES for n in names):
                raise ValueError('Disallowed import: '+','.join(names))
        if isinstance(node, ast.Attribute) and node.attr.startswith('_'):
            raise ValueError('Private attribute')
        if isinstance(node, ast.Name) and (node.id in DENIED or node.id.startswith('__')):
            raise ValueError('Disallowed name: '+node.id)
        if isinstance(node, ast.ClassDef):
            raise ValueError('Classes are not needed for solve()')


def encode(value):
    """Canonical tagged value so different numeric types compare exactly."""
    if isinstance(value, bool):
        return {'type': 'bool', 'value': value}
    if isinstance(value, int):
        return {'type': 'fraction', 'value': [value, 1]}
    if isinstance(value, Fraction):
        return {'type': 'fraction', 'value': [value.numerator, value.denominator]}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('Non-finite result')
        f = Fraction(repr(value))
        return {'type': 'decimal', 'value': [f.numerator, f.denominator], 'repr': repr(value)}
    if type(value).__name__ == 'Decimal':
        f = Fraction(str(value))
        return {'type': 'decimal', 'value': [f.numerator, f.denominator], 'repr': str(value)}
    if isinstance(value, str):
        return {'type': 'string', 'value': value}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [encode(x) for x in value]
        if isinstance(value, (set, frozenset)):
            items = sorted(items, key=lambda x: json.dumps(x, sort_keys=True))
        return {'type': 'sequence', 'value': items}
    raise ValueError('Unsupported result type: '+type(value).__name__)


def main():
    job = json.loads(sys.stdin.read())
    code = job['code']
    if not isinstance(code, str) or len(code) > 20000:
        raise ValueError('Invalid or oversize code')
    tree = ast.parse(code)
    check(tree)
    safe = {k: getattr(builtins, k) for k in ALLOWED if hasattr(builtins, k)}
    safe['print'] = lambda *a, **k: None

    def limited_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.split('.')[0] not in MODULES or level:
            raise ValueError('Disallowed module')
        return builtins.__import__(name, globals, locals, fromlist, level)
    safe['__import__'] = limited_import
    scope = {'__builtins__': safe, '__name__': 'solution'}
    sys.setrecursionlimit(6000)
    exec(compile(tree, '<program>', 'exec'), scope)
    fn = scope.get('solve')
    if not callable(fn):
        raise ValueError('solve() not defined')
    facts = job.get('facts')
    value = fn(facts) if facts is not None else fn()
    print(json.dumps({'status': 'ok', 'result': encode(value)}))


if __name__ == '__main__':
    try:
        main()
    except RecursionError:
        print(json.dumps({'status': 'error', 'error': 'RecursionError'}))
    except Exception as e:
        print(json.dumps({'status': 'error', 'error': type(e).__name__+': '+str(e)[:200]}))
