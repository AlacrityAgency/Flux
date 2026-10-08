"""Read subscription quota; expose only normalized percentages and reset times."""
import asyncio
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import threading
import time

import httpx
from flux.local_agents.google_tools import run


def window(ident, label, used, reset, minutes=None):
    if isinstance(used, bool) or not isinstance(used, (int, float)) or not math.isfinite(used):
        return None
    if isinstance(reset, str):
        try:
            reset = datetime.fromisoformat(reset.replace('Z', '+00:00')).timestamp()
        except ValueError:
            reset = None
    if isinstance(reset, bool) or not isinstance(reset, (int, float)) or not math.isfinite(reset):
        reset = None
    remaining = max(0, min(100, 100 - used))
    return {'id': ident, 'label': label, 'remaining_percent': round(remaining, 1),
            'resets_at': reset, 'window_minutes': minutes}


def codex_windows(data):
    buckets = data.get('rateLimitsByLimitId')
    if not isinstance(buckets, dict) or not buckets:
        legacy = data.get('rateLimits') or {}
        buckets = {legacy.get('limitId') or 'codex': legacy}
    results = []
    for ident, bucket in buckets.items():
        if not isinstance(bucket, dict):
            continue
        for key in ('primary', 'secondary'):
            part = bucket.get(key)
            if not isinstance(part, dict):
                continue
            minutes = part.get('windowDurationMins')
            label = '۵ ساعته' if minutes == 300 else 'هفتگی' if minutes == 10080 else (
                f'{minutes} دقیقه' if isinstance(minutes, (int, float)) else 'سهمیه')
            group = bucket.get('limitName') or (ident if ident != 'codex' else '')
            item = window(f'{ident}:{key}', f'{group} · {label}' if group else label,
                          part.get('usedPercent'), part.get('resetsAt'), minutes)
            if item:
                results.append(item)
    return results


def claude_windows(data):
    results = []
    for key, label, minutes in [('five_hour', '۵ ساعته', 300), ('seven_day', 'هفتگی', 10080),
                                ('seven_day_sonnet', 'Sonnet · هفتگی', 10080),
                                ('seven_day_opus', 'Opus · هفتگی', 10080)]:
        part = data.get(key)
        if not isinstance(part, dict):
            continue
        item = window(key, label, part.get('utilization'), part.get('resets_at'), minutes)
        if item:
            results.append(item)
    return results


def read_codex(executable, env):
    """A short-lived official app-server connection; no thread or model turn starts."""
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    process = subprocess.Popen([executable, 'app-server', '--stdio'], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, **flags)
    messages = queue.Queue()
    def reader():
        for line in process.stdout:
            try:
                messages.put(json.loads(line))
            except ValueError:
                continue
        messages.put(None)
    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    def send(message):
        process.stdin.write((json.dumps(message) + '\n').encode('utf-8'))
        process.stdin.flush()
    def receive(ident):
        while True:
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                raise TimeoutError
            data = messages.get(timeout=timeout)
            if data is None:
                raise RuntimeError('Quota transport closed')
            if data.get('id') == ident:
                if 'error' in data:
                    raise RuntimeError('Quota request failed')
                return data.get('result') or {}
    try:
        send({'method': 'initialize', 'id': 1, 'params': {
            'clientInfo': {'name': 'flux', 'title': 'Flux', 'version': '0.4.0'}}})
        receive(1)
        send({'method': 'initialized', 'params': {}})
        send({'method': 'account/rateLimits/read', 'id': 2})
        return codex_windows(receive(2))
    finally:
        process.stdin.close()
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        thread.join(timeout=3)
        process.stdout.close()


def read_claude():
    """Read the same usage endpoint as Claude Code. Credentials stay in memory only.

    Windows Claude Code stores OAuth login in this file. Keychain-only installations
    deliberately report unavailable rather than extracting their credentials.
    """
    config = Path(os.environ.get('CLAUDE_CONFIG_DIR', Path.home() / '.claude'))
    path = config / '.credentials.json'
    if path.stat().st_size > 128000:
        raise ValueError('Unexpected credential file')
    oauth = json.loads(path.read_text(encoding='utf-8')).get('claudeAiOauth') or {}
    token = oauth.get('accessToken')
    if not isinstance(token, str) or not token:
        raise ValueError('No OAuth login')
    # Fixed HTTPS destination, no redirect or credential in URL/logs/returned data.
    with httpx.Client(timeout=10, follow_redirects=False) as client:
        response = client.get('https://api.anthropic.com/api/oauth/usage', headers={
            'Authorization': 'Bearer ' + token, 'anthropic-beta': 'oauth-2025-04-20',
            'User-Agent': 'Flux/0.4.0'})
        response.raise_for_status()
        return claude_windows(response.json())


def read_notebooklm(executable, env):
    response = run(executable, ['usage', '--json'], env, 30)
    if response.returncode:
        raise RuntimeError('NotebookLM quota unavailable')
    data = json.loads(response.stdout)
    results = []
    for part in data.get('windows') or []:
        kind = part.get('kind')
        label = '۵ ساعته' if kind == 'five_hour' else 'هفتگی' if kind == 'weekly' else 'سهمیه'
        item = window(str(kind), label, part.get('used_percent'), part.get('resets_at'), 300 if kind == 'five_hour' else 10080 if kind == 'weekly' else None)
        if item:
            results.append(item)
    return results


class QuotaMonitor:
    def __init__(self):
        self.cache = {}
        self.times = {}
        self.lock = asyncio.Lock()

    async def read(self, providers, find_cli, environment, refresh=False):
        async with self.lock:
            async def inspect(provider):
                ident = provider['id']
                age = time.monotonic() - self.times.get(ident, -1000)
                # Even explicit refresh is throttled; prevent quota endpoint polling.
                if provider.get('authenticated') and ident in self.cache and age < (30 if refresh else 60):
                    return self.cache[ident]
                result = {'id': ident, 'windows': [], 'available': False, 'stale': False,
                          'checked_at': datetime.now(timezone.utc).isoformat(),
                          'detail': provider.get('detail') or 'برای دیدن سهمیه، وارد حساب شوید.'}
                if provider.get('authenticated'):
                    try:
                        if ident == 'codex':
                            items = await asyncio.to_thread(read_codex, find_cli(ident), environment(ident))
                        elif ident == 'claude':
                            items = await asyncio.to_thread(read_claude)
                        elif ident == 'notebooklm':
                            items = await asyncio.to_thread(read_notebooklm, find_cli(ident), environment(ident))
                        else:
                            items = []
                        result.update(windows=items, available=bool(items), detail='' if items else 'سهمیه از سرویس گزارش نشده است.')
                    except Exception:
                        old = self.cache.get(ident) or {}
                        if old.get('windows'):
                            result.update(windows=old['windows'], available=True, stale=True,
                                          checked_at=old['checked_at'])
                        result['detail'] = 'به‌روزرسانی سهمیه ممکن نشد؛ دوباره بررسی کنید.'
                self.cache[ident] = result
                self.times[ident] = time.monotonic()
                return result
            return {'providers': await asyncio.gather(*(inspect(p) for p in providers))}
