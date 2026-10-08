"""Launch official user OAuth flows without reading/copying credentials."""
import argparse
import os
from pathlib import Path
import json
import subprocess
import tempfile

parser=argparse.ArgumentParser()
parser.add_argument('provider',choices=['gemini','gapcode'])
args=parser.parse_args()
root=Path.home()/'.flux/integrations'
env=dict(os.environ)
folder=Path(tempfile.mkdtemp(prefix='flux-account-connect-'))
if args.provider=='gemini':
    profile=root/'gemini-account';profile.mkdir(parents=True,exist_ok=True)
    settings=profile/'.gemini/settings.json'
    settings.parent.mkdir(parents=True,exist_ok=True)
    if not settings.exists():settings.write_text(json.dumps({'security':{'auth':{'selectedType':'oauth-personal'}},'general':{'enableAutoUpdate':False}}),encoding='utf-8')
    env['GEMINI_CLI_HOME']=str(profile)
    for key in ['GEMINI_API_KEY','GOOGLE_API_KEY','GOOGLE_GENAI_USE_VERTEXAI','GOOGLE_GENAI_USE_GCA']:
        env.pop(key,None)
    import shutil
    node=shutil.which('node')
    command=[node,str(root/'gemini/node_modules/@google/gemini-cli/bundle/gemini.js'),'--skip-trust','--approval-mode','plan','--output-format','stream-json','-p','Connection test only. Reply exactly FLUX_GEMINI_OK. No tools or file changes.']
else:
    home=Path.home()/'.gapcode'
    releases=home/'packages/standalone/releases'
    manifests=list(releases.glob('*/codex-package.json'))
    manifest=max(manifests,key=lambda p:p.stat().st_mtime)
    info=json.loads(manifest.read_text(encoding='utf-8'))
    executable=(manifest.parent/info['entrypoint']).resolve()
    if not executable.is_relative_to(releases.resolve()):raise ValueError('Unexpected GapCode entrypoint.')
    env['GAPCODE_HOME']=str(home)
    command=[str(executable),'login']
    for key in ['OPENAI_API_KEY','CODEX_API_KEY','CODEX_ACCESS_TOKEN','OPENAI_BASE_URL']:
        env.pop(key,None)
print('Official browser sign-in may open. Credentials stay with the CLI.',flush=True)
result=subprocess.run(command,cwd=folder,env=env)
raise SystemExit(result.returncode)
