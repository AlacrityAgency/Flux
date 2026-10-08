"""Evidence-bound verifier. Receives source/public tests, never private gold."""
import ast
from dataclasses import asdict
from fractions import Fraction
import json
import math
from pathlib import Path
import subprocess
import sys
from contracts import Verification, dumps, digest
from memory_v5 import typed, TRUSTED_ROLES

def exact(left, right, kind, membership=False):
    if not typed(left, kind) or not typed(right, kind):
        if kind == 'literal_set' and membership:
            return type(left) in (str, int, float, bool) and any(type(left) is type(x) and left == x for x in right)
        return False
    if kind == 'literal_set':
        return {dumps([type(x).__name__, x]) for x in left} == {dumps([type(x).__name__, x]) for x in right}
    if kind == 'quantity':
        return left['unit'] == right['unit'] and exact(left['amount'], right['amount'], 'number')
    return left == right

def calculate(expression):
    """Bounded rational arithmetic; no names, calls, powers or eval."""
    if len(expression) > 512:
        raise ValueError('expression too long')
    tree = ast.parse(expression, mode='eval')
    if sum(1 for _ in ast.walk(tree)) > 100:
        raise ValueError('expression too complex')
    def walk(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = Fraction(str(node.value))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = walk(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)):
            a, b = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Add): value = a + b
            elif isinstance(node.op, ast.Sub): value = a - b
            elif isinstance(node.op, ast.Mult): value = a * b
            elif isinstance(node.op, ast.Div): value = a / b
            elif isinstance(node.op, ast.FloorDiv): value = Fraction(a // b)
            else: value = a % b
        else:
            raise ValueError('Unsupported public arithmetic')
        if value.numerator.bit_length() + value.denominator.bit_length() > 4096:
            raise ValueError('Arithmetic magnitude cap')
        return value
    return walk(tree.body)

def run_code(code, tests):
    if type(code) is not str or len(code) > 20000:
        return {'passed': [False], 'errors': ['Invalid/oversize code']}
    try:
        result = subprocess.run([sys.executable, '-I', '-S', str(Path(__file__).with_name('code_worker.py'))],
                                input=dumps({'code': code, 'tests': tests}), text=True, encoding='utf-8',
                                capture_output=True, timeout=6)
        receipt = json.loads(result.stdout)
        if result.returncode != 0 or len(receipt.get('passed', [])) != len(tests):
            return {'passed': [False], 'errors': ['Incomplete test receipt']}
        return receipt
    except (subprocess.TimeoutExpired, ValueError) as error:
        return {'passed': [False], 'errors': [type(error).__name__]}

def verify(snapshot, request, pack, output):
    results, problems, details = [], [], {}
    try:
        output_hash = digest(output)
    except (ValueError, TypeError):
        return Verification('invalid', [], ['Non-JSON or nonfinite output'], 'schema', digest(repr(output)), snapshot.hash)
    def finish(status, method):
        return Verification(status, results, problems, method, output_hash, snapshot.hash, details)
    if not isinstance(output, dict):
        problems.append('Output must be a JSON object')
        return finish('invalid', 'schema')
    if pack.payload.get('snapshot') != snapshot.hash:
        problems.append('Snapshot changed')
        return finish('invalid', 'snapshot')
    if request.needs:
        claims = output.get('claims')
        if not isinstance(claims, list) or any(not isinstance(c, dict) for c in claims):
            problems.append('claims array required')
            return finish('invalid', 'typed-source-binding')
        ids = [c.get('need_id') for c in claims]
        if any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids) or any(i not in {n.need_id for n in request.needs} for i in ids):
            problems.append('Duplicate or unknown need_id')
            return finish('invalid', 'typed-source-binding')
        current = {u['unit_id']: u for u in pack.payload['units'] if snapshot.is_current_unit(u)}
        for need in request.needs:
            claim = next((c for c in claims if c.get('need_id') == need.need_id), None)
            state = 'missing'
            binding = pack.payload['bindings'].get(need.need_id)
            if claim is not None and claim.get('value') is None:
                state = 'abstained'
            elif claim is not None:
                refs = claim.get('evidence_refs')
                if not binding or not isinstance(refs, list) or not refs:
                    state = 'invalid'
                elif any(key not in claim or claim[key] != binding[target] for key, target in
                         [('entity_ref', 'entity'), ('field_ref', 'field'), ('namespace', 'namespace'),
                          ('value_type', 'value_type'), ('proof_kind', 'proof_kind')]):
                    state = 'contradicted'
                elif any(not isinstance(r, str) or r not in current or r not in binding['evidence_refs'] for r in refs):
                    state = 'invalid'
                else:
                    supports = [current[r] for r in refs]
                    resolved_need = need
                    if need.via_field:
                        from dataclasses import replace
                        links, link_status = snapshot.resolve(replace(need, field=need.via_field, value_type='entity_ref',
                                                                       proof_kind='typed_fact', via_field=''))
                        if link_status != 'resolved' or not all(i in current for i in binding.get('bridge_refs', [])):
                            state = 'invalid'
                            results.append({'need_id': need.need_id, 'status': state, 'required': need.required})
                            problems.append(need.need_id + ':' + state)
                            continue
                        resolved_need = replace(need, entity=links[0].value, via_field='')
                    canonical, canonical_status = snapshot.resolve(resolved_need)
                    canonical_ids = {u.unit_id for u in canonical}
                    state = 'verified' if (canonical_status == 'resolved' and
                        all(u['unit_id'] in canonical_ids and
                            u['entity'] == binding['entity'] and u['field'] == binding['field'] and
                            u['namespace'] == binding['namespace'] and
                            exact(claim.get('value'), u['value'], u['value_type'], need.membership)
                            for u in supports)) else 'contradicted'
            results.append({'need_id': need.need_id, 'status': state, 'required': need.required})
            if need.required and state != 'verified':
                problems.append(need.need_id + ':' + state)
    if request.task_kind in ('math', 'mixed'):
        if not request.expression:
            results.append({'need_id': 'math', 'status': 'unverified', 'required': True})
        else:
            try:
                expected = calculate(request.expression)
            except (ValueError, SyntaxError, ZeroDivisionError, OverflowError):
                results.append({'need_id': 'math', 'status': 'unverified', 'required': True})
            else:
                value = output.get('answer')
                valid = type(value) in (int, float) and math.isfinite(value) and Fraction(str(value)) == expected
                results.append({'need_id': 'math', 'status': 'verified' if valid else 'contradicted', 'required': True})
                if not valid: problems.append('Public arithmetic check failed')
    if request.task_kind in ('code', 'mixed'):
        if not request.public_tests:
            results.append({'need_id': 'code', 'status': 'unverified', 'required': True})
        else:
            details['code'] = run_code(output.get('code'), request.public_tests)
            valid = bool(details['code']['passed']) and all(details['code']['passed'])
            results.append({'need_id': 'code', 'status': 'verified' if valid else 'contradicted', 'required': True})
            if not valid: problems.append('Public code tests failed')
    required = [r['status'] for r in results if r['required']]
    if not required:
        return finish('unverified' if output else 'invalid', 'no-semantic-checker')
    if 'invalid' in required:
        state = 'invalid'
    elif 'contradicted' in required:
        state = 'contradicted'
    elif all(s == 'verified' for s in required):
        state = 'verified'
    elif all(s in ('missing', 'abstained') for s in required):
        state = 'abstained' if 'abstained' in required else 'partial'
    elif any(s in ('missing', 'abstained') for s in required):
        state = 'partial'
    else:
        state = 'unverified'
    return finish(state, 'typed-source/public-checkers')
