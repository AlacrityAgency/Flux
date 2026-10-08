import json, os, shutil, subprocess, time
from pathlib import Path

HERE=Path(__file__).resolve().parent
def invoke(model, effort, prompt, label, timeout=240, minimal=False):
    path=HERE/'receipts'/(label+'.json')
    if path.exists():
        r=json.loads(path.read_text(encoding='utf-8'))
        assert (r['model'],r['effort'],r['prompt'],r['minimal'])==(model,effort,prompt,minimal)
        return r
    env=dict(os.environ)
    for key in ['OPENAI_API_KEY','CODEX_API_KEY','OPENAI_BASE_URL','CODEX_ACCESS_TOKEN']:
        env.pop(key,None)
    env.update(PYTHONUTF8='1',NO_COLOR='1')
    cmd=[shutil.which('codex'),'exec','--ignore-user-config','--ephemeral','--json',
        '--skip-git-repo-check','--sandbox','read-only','-C',str(HERE/'model_sandbox'),
        '-c','approval_policy="never"','-c',f'model_reasoning_effort="{effort}"','-m',model,'-']
    if minimal:
        config = [
            'model_instructions_file='+json.dumps(str(HERE/'instructions.txt').replace('\\','/')),
            'personality="none"','project_doc_max_bytes=0','web_search="disabled"',
            'features.shell_tool=false','features.apps=false','features.memories=false',
            'features.multi_agent=false','features.skill_search=false','features.skip_host_skill_discovery=true']
        extra=[]
        for item in config:extra.extend(['-c',item])
        cmd[-1:-1]=extra
    start=time.perf_counter()
    try:
        p=subprocess.run(cmd,input=prompt,encoding='utf-8',capture_output=True,env=env,timeout=timeout)
        raw,err,code=p.stdout,p.stderr,p.returncode
    except subprocess.TimeoutExpired as e:
        raw,err,code=e.stdout or '',e.stderr or '',None
        if isinstance(raw,bytes):raw=raw.decode('utf-8','replace')
        if isinstance(err,bytes):err=err.decode('utf-8','replace')
    events=[]
    for line in raw.splitlines():
        try: events.append(json.loads(line))
        except ValueError: pass
    done=[e for e in events if e.get('type')=='turn.completed']
    tools=[e for e in events if e.get('item',{}).get('type') in ['command_execution','mcp_tool_call','web_search']]
    texts=[e['item'].get('text','') for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
    r=dict(model=model,effort=effort,prompt=prompt,label=label,minimal=minimal,command=cmd,text='\n'.join(texts),
        completed=bool(done) and code==0,usage=done[-1].get('usage',{}) if done else {},
        latency_s=time.perf_counter()-start,tool_events=len(tools),exit_code=code,
        stderr=err,raw_events=events,actual_billing_usd=None,account_route='ChatGPT account via Codex CLI')
    path.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:r[k] for k in ['label','model','effort','completed','usage','latency_s','tool_events']},ensure_ascii=False),flush=True)
    return r

if __name__=='__main__':
    for model,effort in [('gpt-6-luna','low'),('gpt-6.1-sol','high'),('gpt-6-astra','max')]:
        invoke(model,effort,'Do not use tools or read files. Reply only PROBE_OK.','probe_'+model)
