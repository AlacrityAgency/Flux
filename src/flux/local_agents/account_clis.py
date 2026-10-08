"""Check official CLI readiness without exposing credentials or sending a model prompt."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def inspect_gemini(executable, env):
    result={'id':'gemini','installed':bool(executable),'authenticated':False,'path':executable,
            'version':'','billing':'google-account','detail':'Gemini CLI نصب نیست.'}
    if not executable:return result
    kwargs={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    try:
        result['version']=subprocess.run([shutil.which('node'),executable,'--version'],env=env,
            capture_output=True,timeout=15,**kwargs).stdout.decode('utf-8',errors='replace').strip()
        # A missing cache must never trigger browser login during a status request.
        if not (Path(env['GEMINI_CLI_HOME'])/'.gemini/oauth_creds.json').is_file():
            result['detail']='ورود Google را از پنجرهٔ اتصال Gemini انجام دهید.'
            return result
        from flux.local_agents.runtime import kill_tree
        with tempfile.TemporaryDirectory(prefix='flux-gemini-status-') as cwd:
            process=subprocess.Popen([shutil.which('node'),executable,'--list-sessions'],cwd=cwd,
                env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kwargs)
            try:out,err=process.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                kill_tree(process);process.communicate()
                result['detail']='اعتبار ورود Gemini تأیید نشد؛ اجرای آزمایشی لازم است.'
                return result
            summary=(out+err).decode('utf-8',errors='replace')
            result['authenticated']=process.returncode==0 and 'Do you want to continue?' not in summary
            if 'IneligibleTierError' in summary or 'This client is no longer supported' in summary:
                result['authenticated']=False;result['auth_error']='ineligible_tier'
                result['detail']='Google این حساب را برای Gemini CLI نمی‌پذیرد؛ مسیر دیگر Gemini لازم است.'
            else:result['detail']='ورود Google آماده است؛ دسترسی مدل با اجرا مشخص می‌شود.' if result['authenticated'] else 'ورود Gemini یا دسترسی حساب تأیید نشد.'
    except (OSError,ValueError,subprocess.SubprocessError):result['detail']='بررسی ورود Gemini ممکن نشد.'
    return result
