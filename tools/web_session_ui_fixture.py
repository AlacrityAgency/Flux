"""Isolated UI fixture: temporary encrypted store, no account or model calls."""
import argparse
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from flux.api.app import create_app
from flux.engine.orchestrator import FluxEngine
from flux.providers.fake import FakeProvider
from flux.storage.database import init_db
from flux.storage.repository import Repository
from flux.local_agents.web_session import inspect, SITES
import uvicorn

parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8068);args=parser.parse_args()
directory=Path(tempfile.mkdtemp(prefix='flux-web-ui-'))
os.environ['FLUX_WEB_SESSION_DIR']=str(directory/'sessions')
app=create_app(FluxEngine(Repository(init_db(':memory:')),FakeProvider()))
runtime=app.state.local_runtime
async def status(refresh=False):
    names=['codex','claude','gemini-api','gemini-web','deepseek-web','gemini','gapcode','antigravity','notebooklm']
    values=[inspect(p) if p in SITES else {'id':p,'installed':True,'authenticated':False,'version':'Fixture','detail':'UI fixture; no account calls'} for p in names]
    return {'providers':values,'models':{p:[] for p in names},'default_cwd':str(directory),'catalog_is_entitlement':False}
runtime.status=status
uvicorn.run(app,host='127.0.0.1',port=args.port,log_level='error')
