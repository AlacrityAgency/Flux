"""Small, sanitized adapters for the Antigravity and NotebookLM CLIs."""
import json
import os
import re
import subprocess


def run(executable, arguments, env, timeout=30):
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    result = subprocess.run([executable, *arguments], env=env, capture_output=True,
                            timeout=timeout, **flags)
    if len(result.stdout) > 2_000_000:
        raise ValueError('CLI response exceeds limit')
    return result


def inspect_google(provider, executable, env):
    result = {'id': provider, 'installed': bool(executable), 'authenticated': False,
              'version': '', 'path': executable, 'detail': 'ابزار نصب نیست.',
              'integration': 'official' if provider == 'antigravity' else 'community', 'models': []}
    if not executable:
        return result
    try:
        version = run(executable, ['--version'], env, 15)
        result['version'] = version.stdout.decode('utf-8', 'replace').strip()[:100]
        if provider == 'notebooklm':
            auth = run(executable, ['auth', 'check', '--test', '--passive', '--json'], env)
            result['authenticated'] = auth.returncode == 0
            result['detail'] = 'ورود آماده است؛ پاسخ‌ها از منابع دفتر انتخاب‌شده‌اند.' if auth.returncode == 0 else 'برای اتصال NotebookLM، با حساب Google وارد شوید.'
        else:
            models = run(executable, ['models'], env, 15)
            result['models'] = [line.split('\t')[0] for line in models.stdout.decode('utf-8', 'replace').splitlines()
                                if re.fullmatch(r'[A-Za-z0-9_.:/-]+', line.split('\t')[0])]
            auth = run(executable, ['--print', '/usage', '--output-format', 'json', '--print-timeout', '15s'], env, 20)
            data = json.loads(auth.stdout)
            result['authenticated'] = auth.returncode == 0 and data.get('status') == 'SUCCESS'
            error = str(data.get('error') or '')
            if 'not currently available in your location' in error or 'not available in your region' in error:
                result.update(error_code='region_restricted', detail='Google حساب فعلی را به‌دلیل محدودیت منطقه برای Antigravity واجد شرایط نمی‌داند.')
            elif result['authenticated']:
                result['detail'] = 'اتصال CLI رسمی Antigravity آماده است.'
            else:
                result['detail'] = 'ورود یا دسترسی Antigravity آماده نیست؛ CLI رسمی را بررسی کنید.'
    except Exception:
        result['detail'] = 'وضعیت اتصال قابل بررسی نبود؛ دوباره بررسی کنید.'
    return result


def list_notebooks(executable, env):
    response = run(executable, ['list', '--json', '--limit', '500'], env)
    if response.returncode:
        raise RuntimeError('دریافت دفترها ممکن نشد؛ اتصال NotebookLM را بررسی کنید.')
    data = json.loads(response.stdout)
    rows = data.get('notebooks', []) if isinstance(data, dict) else data
    results = []
    for row in rows:
        ident = row.get('id') or row.get('notebook_id')
        if isinstance(ident, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', ident):
            results.append({'id': ident, 'title': str(row.get('title') or 'بدون عنوان')[:300]})
    return {'notebooks': results, 'limit': 500}
