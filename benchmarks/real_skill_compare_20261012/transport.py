"""Native CLI receipts; fresh per invocation, no auth reads, bounded process tree."""
import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SKILL=Path('C:/Users/xio/.codex/skills/flux-v1')
sys.path.insert(0,str(SKILL/'scripts'))
from call_model import binary

def invoke(provider,model,effort,prompt,path,workspace,instructions,tools,timeout):
    if path.exists():raise FileExistsError(path)
    workspace.mkdir(parents=True,exist_ok=True);path.parent.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ)
    for k in ['OPENAI_API_KEY','CODEX_API_KEY','CODEX_ACCESS_TOKEN','OPENAI_BASE_URL']:env.pop(k,None)
    if provider=='gapcode':env['GAPCODE_HOME']=str(Path.home()/'.gapcode')
    env.update(PYTHONUTF8='1',NO_COLOR='1',USE_TF='0',USE_FLAX='0')
    cmd=[binary(provider),'exec','--ignore-user-config','--ephemeral','--json','--skip-git-repo-check',
         '--sandbox','workspace-write' if tools else 'read-only','-C',str(workspace),'-m',model]
    settings=['approval_policy="never"','model_reasoning_effort='+json.dumps(effort),
      'model_instructions_file='+json.dumps(str(instructions).replace('\\','/')),
      'personality="none"','project_doc_max_bytes=0','web_search="disabled"',
      'features.shell_tool='+('true' if tools else 'false'),'features.apps=false','features.memories=false',
      'features.multi_agent=false','features.skill_search=false','features.skip_host_skill_discovery=true']
    if provider=='gapcode':settings+=['model_providers.gapgpt.request_max_retries=0','model_providers.gapgpt.stream_max_retries=0']
    for setting in settings:cmd+=['-c',setting]
    cmd+=['-'];start=time.perf_counter();timed=False
    p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:out,err=p.communicate(prompt.encode('utf-8'),timeout=timeout)
    except subprocess.TimeoutExpired:
        timed=True;subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True);out,err=p.communicate()
    clean=lambda b:re.sub(r'\bsk-[A-Za-z0-9_*-]{8,}','[REDACTED]',b.decode('utf-8','replace'))
    events=[]
    for line in clean(out).splitlines():
        try:
            e=json.loads(line)
            if isinstance(e,dict):events.append(e)
        except ValueError:pass
    done=[e for e in events if e.get('type')=='turn.completed']
    observed=[e for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type') in ['command_execution','mcp_tool_call','web_search','file_change']]
    messages=[e['item'].get('text','') for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
    r={'provider':provider,'model_requested':model,'effort_requested':effort,'prompt':prompt,'command':cmd,
      'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'completed':bool(done) and p.returncode==0 and not timed,
      'usage':done[-1].get('usage') if done else None,'text':messages[-1] if messages else '',
      'all_agent_messages':messages,'exit_code':p.returncode,'timeout':timed,'tool_events':len(observed),
      'latency_s':time.perf_counter()-start,'raw_events':events,'stderr':clean(err),
      'cli_retry_notices':sum(e.get('type')=='error' for e in events),'actual_billing_usd':None,
      'server_model_identity_independently_verified':False,'tools_enabled':tools}
    path.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');return r
