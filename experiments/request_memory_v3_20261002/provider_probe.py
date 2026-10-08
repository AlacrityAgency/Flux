"""Account-backed CLI bench adapter; no user DB, auth file access or shared chats."""
from pathlib import Path
import json
import hashlib
import os
import shutil
import subprocess
import time

HERE=Path(__file__).resolve().parent
MODELS=['gpt-6-luna','gpt-6.1-sol']


def invoke(model,prompt,label,timeout=180):
    root=HERE/'model_runs';root.mkdir(exist_ok=True)
    work=HERE/'model_sandbox';work.mkdir(exist_ok=True)
    env=dict(os.environ)
    for name in ['OPENAI_API_KEY','CODEX_API_KEY','OPENAI_BASE_URL','CODEX_ACCESS_TOKEN']:
        env.pop(name,None)
    env.update(PYTHONUTF8='1',NO_COLOR='1')
    cmd=[shutil.which('codex'),'exec','--ignore-user-config','--ephemeral','--json',
         '--skip-git-repo-check','--sandbox','read-only','-C',str(work),
         '-c','approval_policy="never"','-c','model_reasoning_effort="low"',
         '-m',model,'-']
    start=time.perf_counter()
    try:
        p=subprocess.run(cmd,input=prompt,text=True,encoding='utf-8',capture_output=True,env=env,timeout=timeout)
        raw=p.stdout;error=p.stderr[-6000:];code=p.returncode;timed=False
    except subprocess.TimeoutExpired as e:
        raw=e.stdout or '';error=e.stderr or '';code=None;timed=True
        if isinstance(raw,bytes):raw=raw.decode('utf-8','replace')
        if isinstance(error,bytes):error=error.decode('utf-8','replace')
    events=[]
    for line in raw.splitlines():
        try:events.append(json.loads(line))
        except ValueError:pass
    texts=[e.get('item',{}).get('text','') for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
    complete=[e for e in events if e.get('type')=='turn.completed']
    tools=[e for e in events if e.get('item',{}).get('type') in ['command_execution','mcp_tool_call','web_search']]
    result={'model_requested':model,'label':label,'exit_code':code,'timed_out':timed,
            'prompt_sha256':hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
            'provider_completed':bool(complete) and code==0,'text':'\n'.join(texts),
            'usage':complete[-1].get('usage',{}) if complete else {},'tool_events':len(tools),
            'latency_seconds':time.perf_counter()-start,'stderr':error,
            'events':events,'billing_usd':None,'account_route':'ChatGPT login','reasoning_effort':'low'}
    (root/f'{label}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def main():
    results=[]
    for model in MODELS:
        r=invoke(model,'This is a model access probe. Do not use any tools or inspect any files. Reply with only: PROBE_OK',f'probe_{model}')
        results.append(r)
        print(json.dumps({k:r[k] for k in ['model_requested','provider_completed','text','usage','latency_seconds','tool_events','stderr']},ensure_ascii=False),flush=True)
    (HERE/'provider-probes.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
