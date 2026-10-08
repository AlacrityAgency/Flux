"""Small real GapCode probes; native login, no secret/config extraction."""
import concurrent.futures, datetime, hashlib, json, os, re, subprocess, time
from pathlib import Path
HERE=Path(__file__).resolve().parent

def clean(text):
    return re.sub(r'\bsk-[A-Za-z0-9_*-]{8,}', '[REDACTED]', text)

def executable():
    root=Path.home()/'.gapcode/packages/standalone/releases'
    manifests=sorted(root.glob('*/codex-package.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    for file in manifests:
        path=(file.parent/json.loads(file.read_text(encoding='utf-8'))['entrypoint']).resolve()
        if path.is_relative_to(root.resolve()) and path.is_file():return str(path)
    raise FileNotFoundError('GapCode native binary unavailable')

def invoke(model,prompt,label,timeout=90):
    dest=HERE/'receipts'/(label+'.json')
    if dest.exists():return json.loads(dest.read_text(encoding='utf-8'))
    env=dict(os.environ)
    for key in ['OPENAI_API_KEY','CODEX_API_KEY','CODEX_ACCESS_TOKEN','OPENAI_BASE_URL']:env.pop(key,None)
    env.update(GAPCODE_HOME=str(Path.home()/'.gapcode'),PYTHONUTF8='1',NO_COLOR='1')
    cmd=[executable(),'exec','--ignore-user-config','--ephemeral','--json','--skip-git-repo-check',
        '--sandbox','read-only','-C',str(HERE/'model_sandbox'),'-c','approval_policy="never"',
        '-c','model_reasoning_effort="low"','-c','model_instructions_file='+json.dumps(str(HERE/'instructions.txt').replace('\\','/')),
        '-c','personality="none"','-c','project_doc_max_bytes=0','-c','web_search="disabled"',
        '-c','features.shell_tool=false','-c','features.apps=false','-c','features.memories=false',
        '-c','features.multi_agent=false','-c','features.skill_search=false',
        '-c','features.skip_host_skill_discovery=true',
        '-c','projects.'+json.dumps(str(HERE/'model_sandbox'))+'.trust_level="trusted"',
        '-m',model,'-']
    start=time.perf_counter();timed_out=False
    p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:out,err=p.communicate(prompt.encode('utf-8'),timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out=True
        subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
        out,err=p.communicate()
    raw=clean(out.decode('utf-8','replace'));errors=clean(err.decode('utf-8','replace'));events=[]
    for line in raw.splitlines():
        try:
            value=json.loads(line)
            if isinstance(value,dict):events.append(value)
        except ValueError:pass
    done=[e for e in events if e.get('type')=='turn.completed']
    tools=[e for e in events if e.get('item',{}).get('type') in ['command_execution','mcp_tool_call','web_search','file_change']]
    replies=[e['item'].get('text','') for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
    r={'provider':'gapcode','model_requested':model,'effort_requested':'low','label':label,'prompt':prompt,
       'command':cmd,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'completed':bool(done) and p.returncode==0 and not timed_out,
       'exit_code':p.returncode,'timeout':timed_out,'latency_s':time.perf_counter()-start,'text':'\n'.join(replies),
       'usage':done[-1].get('usage') if done else None,'tool_events':len(tools),'raw_events':events,
       'stderr':errors,'actual_billing_usd':None,'billing_route':'GapCode wallet; native stored login',
       'server_model_identity_independently_verified':False}
    dest.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:r[k] for k in ['label','completed','latency_s','usage','tool_events','timeout']},ensure_ascii=False),flush=True)
    return r

def catalog():
    src=Path.home()/'.gapcode/models_cache.json';d=json.loads(src.read_text(encoding='utf-8'))
    result={'catalog_origin':'GapCode native models_cache.json','fetched_at':d.get('fetched_at'),
       'client_version':d.get('client_version'),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
       'models':[{k:m.get(k) for k in ['slug','display_name','supported_reasoning_levels','default_reasoning_level','context_window']} for m in d.get('models',[])]}
    (HERE/'catalog.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

def probe(model):
    r=invoke(model,'Do not use tools. Return exactly this JSON object: {"probe":"ok","sum":42}.','availability_'+model)
    try:correct=json.loads(r['text'])=={'probe':'ok','sum':42}
    except ValueError:correct=False
    return {'model':model,'transport_ok':r['completed'] and not r['tool_events'],
        'json_contract_ok':r['completed'] and not r['tool_events'] and correct,
        'latency_s':r['latency_s'],'usage':r['usage'],'actual_billing_usd':None,
        'receipt':'receipts/'+r['label']+'.json','error':r['stderr'][-800:] if not r['completed'] else ''}

if __name__=='__main__':
    import sys
    models=[m['slug'] for m in catalog()['models']]
    if len(sys.argv)>1:models=sys.argv[1:]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(probe,models))
    (HERE/'availability.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(rows,ensure_ascii=False,indent=2))
