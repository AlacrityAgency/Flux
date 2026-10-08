"""One explicitly requested, isolated read-only native CLI connection test."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from flux.local_agents.runtime import find_cli,command_for,cli_environment,EventParser,kill_tree

parser=argparse.ArgumentParser();parser.add_argument('--provider',choices=['gapcode','gemini'],required=True);args=parser.parse_args()
chat={'provider':args.provider,'access':'read','model':'','session_id':None}
report={'provider':args.provider,'model_calls_requested':1,'database':'none','files_modified_by_request':False,'actual_cost_usd':None}
with tempfile.TemporaryDirectory(prefix='flux-account-smoke-') as cwd:
    process=subprocess.Popen(command_for(chat,find_cli(args.provider)),cwd=cwd,env=cli_environment(args.provider),
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    try:out,err=process.communicate(b'Reply exactly FLUX_CONNECTION_OK. Do not use tools or modify files.',timeout=90)
    except subprocess.TimeoutExpired:
        kill_tree(process);out,err=process.communicate();report['timeout']=True
    events=EventParser(args.provider);tool_events=0
    for line in out.decode('utf-8',errors='replace').splitlines():
        try:
            event=json.loads(line)
            if isinstance(event,dict):tool_events+=sum(k=='tool' for k,v in events.feed(event))
        except ValueError:pass
    report.update(exit_code=process.returncode,completed=events.complete,response=events.text,
        successful=process.returncode==0 and events.complete and events.text.strip()=='FLUX_CONNECTION_OK',
        tool_events=tool_events,usage=events.usage)
    if not report['successful']:report['failure']='Connection probe did not complete; no automatic resend.'
dest=Path(__file__).resolve().parents[1]/'docs/knowledge';dest.mkdir(parents=True,exist_ok=True)
(dest/(args.provider+'-connection-check.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
