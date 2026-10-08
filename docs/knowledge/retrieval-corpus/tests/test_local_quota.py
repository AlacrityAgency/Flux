import asyncio
import json
import subprocess
import sys

import pytest

from flux.local_agents import quota


def test_missing_quota_is_unknown_zero_is_known_and_values_are_clamped():
    assert quota.window('a', 'x', None, None) is None
    assert quota.window('a', 'x', float('nan'), None) is None
    assert quota.window('a', 'x', True, None) is None
    assert quota.window('a', 'x', 0, None)['remaining_percent'] == 100
    assert quota.window('a', 'x', 100, None)['remaining_percent'] == 0
    assert quota.window('a', 'x', 125, None)['remaining_percent'] == 0
    assert quota.window('a', 'x', -5, None)['remaining_percent'] == 100


def test_codex_prefers_all_named_buckets_and_never_invents_missing_windows():
    data = {'rateLimits': {'primary': {'usedPercent': 98}}, 'rateLimitsByLimitId': {
        'codex': {'primary': {'usedPercent': 25, 'windowDurationMins': 10080, 'resetsAt': 1700000000}},
        'review': {'limitName': 'Review', 'secondary': {'usedPercent': 50, 'windowDurationMins': 300}}}}
    items = quota.codex_windows(data)
    assert len(items) == 2
    assert items[0]['remaining_percent'] == 75 and items[0]['label'] == 'هفتگی'
    assert items[1]['label'] == 'Review · ۵ ساعته'
    assert quota.codex_windows({}) == []
    assert len(quota.codex_windows({'rateLimits': {'primary': {'usedPercent': 0}}})) == 1


def test_claude_normalization_whitelists_fields_and_reset_timestamps():
    items = quota.claude_windows({'five_hour': {'utilization': 79, 'resets_at': '2026-10-01T12:00:00Z'},
        'seven_day': None, 'accessToken': 'never returned', 'seven_day_sonnet': {'utilization': 10, 'resets_at': 'invalid'}})
    assert len(items) == 2 and items[0]['remaining_percent'] == 21
    assert items[0]['resets_at'] == 1790856000
    assert items[1]['resets_at'] is None
    assert 'never returned' not in json.dumps(items)


@pytest.mark.asyncio
async def test_cache_refresh_throttle_stale_fallback_and_logout(monkeypatch):
    clock = [1000]
    monkeypatch.setattr(quota.time, 'monotonic', lambda: clock[0])
    calls = []
    def read():
        calls.append(1)
        if len(calls) > 1:
            raise RuntimeError('secret exception must not escape')
        return [quota.window('five_hour', '۵ ساعته', 40, 1700000000)]
    monkeypatch.setattr(quota, 'read_claude', read)
    monitor = quota.QuotaMonitor()
    providers = [{'id': 'claude', 'authenticated': True}]
    first = await monitor.read(providers, None, None)
    again = await monitor.read(providers, None, None, refresh=True)
    assert first == again and len(calls) == 1
    clock[0] += 31
    stale = (await monitor.read(providers, None, None, refresh=True))['providers'][0]
    assert stale['stale'] and stale['windows'][0]['remaining_percent'] == 60
    assert stale['checked_at'] == first['providers'][0]['checked_at']
    assert 'secret' not in json.dumps(stale)
    logged_out = await monitor.read([{'id': 'claude', 'authenticated': False}], None, None)
    assert not logged_out['providers'][0]['windows'] and len(calls) == 2


@pytest.mark.asyncio
async def test_concurrent_reads_share_one_snapshot(monkeypatch):
    calls = []
    def read():
        calls.append(1)
        return []
    monkeypatch.setattr(quota, 'read_claude', read)
    monitor = quota.QuotaMonitor()
    await asyncio.gather(*(monitor.read([{'id':'claude','authenticated':True}], None, None) for _ in range(3)))
    assert calls == [1]


def test_codex_stdio_handshake_ignores_notifications_and_closes_owned_process(monkeypatch, tmp_path):
    script = tmp_path / 'quota_cli.py'
    script.write_text('''import json,sys
for line in sys.stdin:
    message=json.loads(line)
    if message['method']=='initialize':
        print(json.dumps({'id':message['id'],'result':{}}),flush=True)
    elif message['method']=='account/rateLimits/read':
        print(json.dumps({'method':'some/notification','params':{}}),flush=True)
        print(json.dumps({'id':message['id'],'result':{'rateLimits':{'primary':{'usedPercent':42,'windowDurationMins':300}}}}),flush=True)
''', encoding='utf-8')
    original = subprocess.Popen
    processes = []
    def launch(args, **kwargs):
        assert args[1:] == ['app-server', '--stdio']
        process = original([sys.executable, '-u', str(script)], **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(quota.subprocess, 'Popen', launch)
    assert quota.read_codex('codex.exe', {})[0]['remaining_percent'] == 58
    assert processes[0].poll() is not None


def test_claude_auth_only_goes_to_fixed_https_and_response_is_sanitized(monkeypatch, tmp_path):
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', str(tmp_path))
    (tmp_path / '.credentials.json').write_text(json.dumps({'claudeAiOauth': {'accessToken': 'test-only-secret'}}))
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'five_hour': {'utilization': 0}, 'token':'test-only-secret'}
    class Client:
        def __init__(self, **kwargs): assert kwargs['follow_redirects'] is False
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, headers):
            assert url == 'https://api.anthropic.com/api/oauth/usage'
            assert headers['Authorization'] == 'Bearer test-only-secret'
            return Response()
    monkeypatch.setattr(quota.httpx, 'Client', Client)
    result = quota.read_claude()
    assert result[0]['remaining_percent'] == 100
    assert 'test-only-secret' not in json.dumps(result)
