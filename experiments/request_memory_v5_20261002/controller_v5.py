"""Idempotent controller and durable two-attempt ledger, confined to this experiment."""
from dataclasses import asdict
from pathlib import Path
import json
import sqlite3
import time
import threading
from contracts import Policy, digest, dumps
from engine_v5 import normalize_request, retrieve, prompt_for
from verifier_v5 import verify

class Ledger:
    def __init__(self, path=':memory:'):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.RLock()
        self.db.execute('CREATE TABLE IF NOT EXISTS requests '
                        '(id TEXT PRIMARY KEY, hash TEXT, calls INTEGER, repair INTEGER, '
                        'deadline REAL, state TEXT, result TEXT)')
        self.db.commit()

    def begin(self, request_id, fingerprint, deadline_seconds):
        with self.lock, self.db:
            self.db.execute('INSERT OR IGNORE INTO requests VALUES (?,?,0,0,?,"new",NULL)',
                            (request_id, fingerprint, time.time() + deadline_seconds))
            row = self.db.execute('SELECT hash,state,result FROM requests WHERE id=?', (request_id,)).fetchone()
            if row[0] != fingerprint:
                raise ValueError('Request ID reused with different request/snapshot/policy')
            changed = self.db.execute('UPDATE requests SET state="running" WHERE id=? AND state="new"', (request_id,)).rowcount
            return ('started', None) if changed else (row[1], json.loads(row[2]) if row[2] else None)

    def reserve(self, request_id, cap, repair=False):
        with self.lock, self.db:
            # Compare-and-update also enforces the limit across independent SQLite connections.
            changed = self.db.execute('UPDATE requests SET calls=calls+1,repair=repair+? '
                    'WHERE id=? AND state="running" AND calls<? AND deadline>? AND (?=0 OR repair=0)',
                    (int(repair), request_id, cap, time.time(), int(repair))).rowcount
            if not changed:
                raise RuntimeError('Call/repair/deadline limit')

    def stats(self, request_id):
        with self.lock:
            row = self.db.execute('SELECT calls,repair,deadline,state FROM requests WHERE id=?', (request_id,)).fetchone()
        return dict(zip(('physical_attempts', 'repair_used', 'deadline', 'state'), row))

    def finish(self, request_id, result):
        with self.lock, self.db:
            self.db.execute('UPDATE requests SET state="complete",result=? WHERE id=?', (dumps(result), request_id))

    def close(self):
        self.db.close()

class Controller:
    def __init__(self, snapshot, provider, ledger=None):
        self.snapshot, self.provider = snapshot, provider
        self.ledger = ledger or Ledger()

    def run(self, request, policy=Policy()):
        request = normalize_request(request, self.snapshot)
        fingerprint = digest({'request': asdict(request), 'snapshot': self.snapshot.hash, 'policy': asdict(policy)})
        state, saved = self.ledger.begin(request.request_id, fingerprint, policy.deadline_seconds)
        if state != 'started':
            return saved if saved is not None else {'status': 'in_progress_or_interrupted', 'generation': [],
                                                   'ledger': self.ledger.stats(request.request_id)}
        receipts = []
        pack = retrieve(self.snapshot, request, policy)
        result = {'status': pack.status, 'request': asdict(request), 'pack': pack.public(), 'generation': receipts,
                  'verification': None, 'output': None, 'human_accepted': False}

        def finish(status):
            result['status'] = status
            result['ledger'] = self.ledger.stats(request.request_id)
            result['ledger']['state'] = 'complete'
            result['memory_proposal'] = {'status': 'proposed', 'auto_promoted': False,
                'request_hash': fingerprint, 'snapshot_hash': self.snapshot.hash,
                'evidence_refs': list(pack.required_ids), 'output_hash': digest(result['output'])}
            stable = json.loads(dumps(result))
            self.ledger.finish(request.request_id, stable)
            return stable

        if pack.status != 'ready':
            return finish(pack.status)
        if pack.route == 'project_grounded' and not request.needs and not pack.payload['units']:
            return finish('missing')
        model = policy.primary_model
        diagnostics = None
        for attempt in range(2):
            admission = prompt_for(request, pack, policy, diagnostics)
            result['prompt_admission'] = {k: v for k, v in admission.items() if k != 'prompt'}
            if not admission['accepted']:
                return finish('prompt_too_large')
            try:
                self.ledger.reserve(request.request_id, policy.max_calls, repair=attempt > 0)
            except RuntimeError:
                return finish('call_or_deadline_limit')
            remaining = max(.01, self.ledger.stats(request.request_id)['deadline'] - time.time())
            try:
                provider_receipt = self.provider.generate(model, admission['prompt'], request.request_id + '-' + str(attempt), remaining)
            except Exception as error:
                # Unknown external effect consumes this attempt; never retry it silently.
                receipts.append({'model_requested': model, 'provider_completed': False, 'error': type(error).__name__})
                return finish('provider_incomplete')
            receipts.append(provider_receipt)
            if not provider_receipt.get('provider_completed') or provider_receipt.get('tool_events', 0):
                return finish('provider_incomplete')
            try:
                def reject_constant(name):
                    raise ValueError('Nonfinite JSON constant: ' + name)
                output = json.loads(provider_receipt['text'], parse_constant=reject_constant)
            except (ValueError, KeyError):
                output = provider_receipt.get('text', '')
            receipt = verify(self.snapshot, request, pack, output)
            result['output'], result['verification'] = output, asdict(receipt)
            if not receipt.blocking:
                return finish(receipt.status)
            if attempt or pack.gaps:
                return finish(receipt.status)
            diagnostics = {'previous_output': output, 'problems': receipt.problems, 'per_need': receipt.per_need,
                           'public_checker_details': receipt.details}
            if policy.allow_escalation and request.task_kind in ('math', 'code', 'mixed') and receipt.status == 'contradicted':
                model = policy.fallback_model
        raise AssertionError('Unreachable third generation')

class ScriptedProvider:
    """TEST DOUBLE ONLY: model outputs supplied by a test, no actual model calls."""
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def generate(self, model, prompt, label, timeout):
        self.calls.append({'model': model, 'prompt': prompt, 'timeout': timeout})
        value = self.outputs.pop(0)
        if isinstance(value, Exception):
            raise value
        return {'model_requested': model, 'provider_completed': True, 'tool_events': 0,
                'text': dumps(value) if isinstance(value, (dict, list)) else value,
                'usage': None, 'billing_usd': None, 'test_double': True}
