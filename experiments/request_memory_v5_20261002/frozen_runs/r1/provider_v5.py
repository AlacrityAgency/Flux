"""Opt-in native account-backed CLI adapter. No credential reads, no dollar API."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from contracts import digest, dumps

class CodexProvider:
    def __init__(self, output_directory):
        self.root = Path(output_directory).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.work = self.root / 'sandbox'
        self.work.mkdir(exist_ok=True)

    def generate(self, model, prompt, label, timeout):
        if model not in ('gpt-6-luna', 'gpt-6.1-sol'):
            raise ValueError('Model not allowed by this experimental adapter')
        command = shutil.which('codex')
        if not command:
            raise RuntimeError('Codex CLI unavailable')
        env = dict(os.environ)
        for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL', 'CODEX_ACCESS_TOKEN'):
            env.pop(key, None)
        env.update(PYTHONUTF8='1', NO_COLOR='1')
        args = [command, 'exec', '--ignore-user-config', '--ephemeral', '--json', '--skip-git-repo-check',
                '--sandbox', 'read-only', '-C', str(self.work), '-c', 'approval_policy="never"',
                '-c', 'model_reasoning_effort="low"', '-m', model, '-']
        start = time.perf_counter()
        try:
            proc = subprocess.run(args, input=prompt, text=True, encoding='utf-8', capture_output=True,
                                  env=env, timeout=min(timeout, 180))
            raw, code, error, timed = proc.stdout, proc.returncode, proc.stderr[-4000:], False
        except subprocess.TimeoutExpired as ex:
            raw, error, code, timed = ex.stdout or '', ex.stderr or '', None, True
            if isinstance(raw, bytes): raw = raw.decode('utf-8', 'replace')
            if isinstance(error, bytes): error = error.decode('utf-8', 'replace')
        events = []
        for line in raw.splitlines():
            try: events.append(json.loads(line))
            except ValueError: pass
        completed = [e for e in events if e.get('type') == 'turn.completed']
        tool_events = [e for e in events if e.get('item', {}).get('type') in ('command_execution', 'mcp_tool_call', 'web_search')]
        texts = [e['item'].get('text', '') for e in events if e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'agent_message']
        receipt = {'model_requested': model, 'provider_completed': bool(completed) and code == 0,
                   'text': '\n'.join(texts), 'tool_events': len(tool_events), 'exit_code': code,
                   'timed_out': timed, 'latency_seconds': time.perf_counter() - start,
                   'usage': completed[-1].get('usage') if completed else None, 'stderr': error,
                   'prompt_hash': digest(prompt), 'billing_usd': None, 'route': 'native account CLI',
                   'reasoning_effort': 'low', 'test_double': False}
        # Content-addressed filename prevents request IDs from becoming filesystem paths.
        path = self.root / (digest({'label': label, 'prompt': prompt, 'model': model}) + '.json')
        with path.open('x', encoding='utf-8') as stream:
            stream.write(dumps({'receipt': receipt, 'events': events}))
        return receipt
