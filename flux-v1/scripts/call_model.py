"""Native Codex/GapCode adapter. Reads prompts, never reads credentials."""
import argparse,datetime,json,os,re,shutil,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def normalize(text):
    value=text.strip()
    if value.startswith('```json\n') and value.endswith('\n```'):value=value[8:-4]
    elif value.startswith('```\n') and value.endswith('\n```'):value=value[4:-4]
    def unique(pairs):
        out={}
        for k,v in pairs:
            if k in out:raise ValueError('Duplicate JSON key: '+k)
            out[k]=v
        return out
    return json.loads(value,object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Non-finite JSON')))

def binary(provider):
    if provider=='gapcode':
        root=Path.home()/'.gapcode/packages/standalone/releases'
        for f in sorted(root.glob('*/codex-package.json'),key=lambda p:p.stat().st_mtime,reverse=True):
            path=(f.parent/json.loads(f.read_text(encoding='utf-8'))['entrypoint']).resolve()
            if path.is_relative_to(root.resolve()) and path.is_file():return str(path)
    else:
        p=shutil.which('codex')
        if p and Path(p).suffix.lower() not in ['.cmd','.bat','.ps1']:return p
        local=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))
        candidates=[Path.home()/'.local/bin/codex.exe']+sorted((local/'OpenAI/Codex/bin').glob('*/codex.exe'),key=lambda p:p.stat().st_mtime,reverse=True)
        for p in candidates:
            if p.is_file():return str(p)
    raise FileNotFoundError(provider+' native binary not found')

def invoke(provider,model,effort,prompt,receipt,timeout=90,contract='direct'):
    receipt=Path(receipt).resolve()
    if receipt.exists():raise FileExistsError('Use a new receipt per real call; no silent replay')
    registry=json.loads((ROOT/'references/models.json').read_text(encoding='utf-8'))
    key=provider+'/'+model
    info=registry['models'].get(key)
    if not info or not info['enabled']:raise ValueError('Endpoint is not enabled: '+key)
    if contract=='compact' and not info['compact_qualified']:raise ValueError('Endpoint not qualified for compact contract: '+key)
    if effort not in info['supported_efforts']:raise ValueError('Unsupported requested effort')
    receipt.parent.mkdir(parents=True,exist_ok=True)
    sandbox=receipt.parent/'model_sandbox';sandbox.mkdir(exist_ok=True)
    env=dict(os.environ)
    for k in ['OPENAI_API_KEY','CODEX_API_KEY','CODEX_ACCESS_TOKEN','OPENAI_BASE_URL']:env.pop(k,None)
    if provider=='gapcode':env['GAPCODE_HOME']=str(Path.home()/'.gapcode')
    env.update(PYTHONUTF8='1',NO_COLOR='1')
    cmd=[binary(provider),'exec','--ignore-user-config','--ephemeral','--json','--skip-git-repo-check',
         '--sandbox','read-only','-C',str(sandbox),'-m',model]
    settings=['approval_policy="never"','model_reasoning_effort='+json.dumps(effort),
      'model_instructions_file='+json.dumps(str(ROOT/'scripts/instructions.txt').replace('\\','/')),
      'personality="none"','project_doc_max_bytes=0','web_search="disabled"',
      'features.shell_tool=false','features.apps=false','features.memories=false','features.multi_agent=false',
      'features.skill_search=false','features.skip_host_skill_discovery=true',
      'model_providers.gapgpt.request_max_retries=0','model_providers.gapgpt.stream_max_retries=0'] if provider=='gapcode' else [
      'approval_policy="never"','model_reasoning_effort='+json.dumps(effort),
      'model_instructions_file='+json.dumps(str(ROOT/'scripts/instructions.txt').replace('\\','/')),
      'personality="none"','project_doc_max_bytes=0','web_search="disabled"','features.shell_tool=false',
      'features.apps=false','features.memories=false','features.multi_agent=false','features.skill_search=false',
      'features.skip_host_skill_discovery=true']
    for setting in settings:cmd+=['-c',setting]
    cmd+=['-'];start=time.perf_counter();timed_out=False
    p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),start_new_session=os.name!='nt')
    try:out,err=p.communicate(prompt.encode('utf-8'),timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out=True
        if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
        else:
            import signal
            os.killpg(p.pid,signal.SIGKILL)
        out,err=p.communicate()
    clean=lambda t:re.sub(r'\bsk-[A-Za-z0-9_*-]{8,}','[REDACTED]',t.decode('utf-8','replace'))
    raw,stderr=clean(out),clean(err);events=[]
    for line in raw.splitlines():
        try:
            e=json.loads(line)
            if isinstance(e,dict):events.append(e)
        except ValueError:pass
    done=[e for e in events if e.get('type')=='turn.completed']
    tools=[e for e in events if e.get('item',{}).get('type') in ['command_execution','mcp_tool_call','web_search','file_change']]
    text='\n'.join(e['item'].get('text','') for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message')
    r={'provider':provider,'model_requested':model,'effort_requested':effort,'prompt':prompt,'command':cmd,
      'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'completed':bool(done) and p.returncode==0 and not timed_out,
      'usage':done[-1].get('usage') if done else None,'text':text,'exit_code':p.returncode,'timeout':timed_out,
      'tool_events':len(tools),'latency_s':time.perf_counter()-start,'raw_events':events,'stderr':stderr,
      'billing_route':'gapcode-wallet' if provider=='gapcode' else 'codex-account','actual_billing_usd':None,
      'server_model_identity_independently_verified':False}
    receipt.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    return r

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--provider',choices=['codex','gapcode'],required=True)
    a.add_argument('--model',required=True);a.add_argument('--effort',default='low');a.add_argument('--prompt-file',type=Path,required=True)
    a.add_argument('--receipt',type=Path,required=True);a.add_argument('--timeout',type=int,default=90)
    a.add_argument('--contract',choices=['direct','compact'],default='direct')
    args=a.parse_args();r=invoke(args.provider,args.model,args.effort,args.prompt_file.read_text(encoding='utf-8'),args.receipt,args.timeout,args.contract)
    print(json.dumps({k:r[k] for k in ['provider','model_requested','completed','usage','latency_s','tool_events','timeout']},ensure_ascii=False))
    raise SystemExit(0 if r['completed'] and not r['tool_events'] else 1)
