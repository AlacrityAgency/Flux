import json
import subprocess
import sys

import pytest
from pydantic import ValidationError
from httpx import ASGITransport, AsyncClient

from flux.local_agents import google_tools, quota, runtime as module
from flux.local_agents.runtime import ChatSpec, EventParser, command_for, cli_environment
from test_local_agents import local_app, finish


def test_google_provider_constraints_and_exact_resume(tmp_path):
    with pytest.raises(ValidationError):
        ChatSpec(cwd=str(tmp_path), provider='notebooklm')
    spec=ChatSpec(cwd=str(tmp_path), provider='notebooklm', notebook_id='notebook-123')
    assert spec.access == 'read'
    with pytest.raises(ValidationError):
        ChatSpec(cwd=str(tmp_path), provider='antigravity', access='read')
    args=command_for({**spec.model_dump(),'session_id':'conversation-456'}, 'notebooklm.exe')
    assert '--new' not in args and '--yes' not in args and 'notebook-123' in args
    assert args[args.index('--conversation-id')+1] == 'conversation-456'
    args=command_for({'provider':'antigravity','model':'known-model','session_id':'exact-id'}, 'agy.exe')
    assert args[args.index('--conversation')+1] == 'exact-id'
    assert '--continue' not in args and '--dangerously-skip-permissions' not in args
    assert '--input-format' in args


def test_antigravity_stream_success_error_and_waiting():
    parser=EventParser('antigravity')
    parser.feed({'event':'step_update','step_update':{'conversation_id':'id','step_type':'agent_response','text_delta':'سلام'}})
    output=parser.feed({'event':'step_update','step_update':{'step_type':'tool','state':'DONE','tool_name':'run_command','tool_info':{'parameters':{'CommandLine':'test'},'output':'passed'}}})
    assert output[0][1]['output']=='passed'
    parser.feed({'event':'result','result':{'status':'SUCCESS','response':'سلام؛ کامل','conversation_id':'id','usage':{'output_tokens':9}}})
    assert parser.complete and parser.text=='سلام؛ کامل' and parser.session_id=='id'
    for status in ('ERROR','WAITING','CANCELED','RUNNING'):
        parser=EventParser('antigravity')
        parser.feed({'event':'result','result':{'status':status,'error':'reason'}})
        assert not parser.complete
        assert parser.blocked == (status=='WAITING')


def test_notebooklm_references_and_error_are_not_synthetic_success():
    parser=EventParser('notebooklm')
    parser.feed({'answer':'پاسخ [1]', 'conversation_id':'real-id', 'references':[{'source_id':'source-id','citation_number':1}]})
    assert parser.complete and parser.session_id=='real-id' and parser.usage['references'][0]['source_id']=='source-id'
    parser=EventParser('notebooklm')
    parser.feed({'error':{'message':'private auth details'},'status':'error'})
    assert not parser.complete and 'private' not in parser.error


def test_google_environment_uses_saved_accounts(monkeypatch):
    for name in ('GEMINI_API_KEY','GOOGLE_API_KEY','GOOGLE_GEMINI_BASE_URL','NOTEBOOKLM_AUTH_JSON'):
        monkeypatch.setenv(name,'secret')
    for provider in ('antigravity','notebooklm'):
        env=cli_environment(provider)
        assert env['PYTHONUTF8']=='1'
        assert not any(k in env for k in ('GEMINI_API_KEY','GOOGLE_API_KEY','NOTEBOOKLM_AUTH_JSON'))


def test_google_cli_prefers_managed_install_over_older_path(tmp_path, monkeypatch):
    monkeypatch.setattr(module.Path, 'home', lambda:tmp_path/'home')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.delenv('FLUX_ANTIGRAVITY_PATH', raising=False)
    monkeypatch.delenv('FLUX_NOTEBOOKLM_PATH', raising=False)
    monkeypatch.setattr(module.shutil, 'which', lambda name: str(tmp_path/'old.exe'))
    for provider, relative in [('antigravity','agy/bin/agy.exe'),('notebooklm','Flux/integrations/notebooklm/Scripts/notebooklm.exe')]:
        exe=tmp_path/relative
        exe.parent.mkdir(parents=True,exist_ok=True)
        exe.touch()
        assert module.find_cli(provider)==str(exe)


def test_google_cli_user_home_install_survives_packaged_host_virtualization(tmp_path, monkeypatch):
    monkeypatch.setattr(module.Path, 'home', lambda:tmp_path)
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'virtual-local'))
    monkeypatch.delenv('FLUX_ANTIGRAVITY_PATH',raising=False)
    monkeypatch.delenv('FLUX_NOTEBOOKLM_PATH',raising=False)
    monkeypatch.setattr(module.shutil, 'which', lambda name:None)
    for provider,relative in [('antigravity','antigravity/agy.exe'),('notebooklm','notebooklm/Scripts/notebooklm.exe')]:
        exe=tmp_path/'.flux/integrations'/relative
        exe.parent.mkdir(parents=True,exist_ok=True)
        exe.touch()
        assert module.find_cli(provider)==str(exe.resolve())


def test_google_probe_keeps_region_rejection_visible_and_auth_output_private(monkeypatch):
    def run(executable, args, env, timeout=30):
        if args==['--version']: data=b'1.2.14'
        elif args==['models']: data=b'known-model\tKnown model\n'
        elif args[0]=='auth': data=b'{"account":"private@example.com","accessToken":"secret"}'
        else: data=json.dumps({'status':'ERROR','error':'not currently available in your location.'}).encode()
        return subprocess.CompletedProcess([], 0 if args[0] in ('models','auth','--version') else 1, data, b'')
    monkeypatch.setattr(google_tools, 'run', run)
    result=google_tools.inspect_google('antigravity','agy',{})
    assert not result['authenticated'] and result['error_code']=='region_restricted'
    result=google_tools.inspect_google('notebooklm','nb',{})
    assert result['authenticated']
    assert 'private@example.com' not in json.dumps(result) and 'secret' not in json.dumps(result)


def test_notebook_quota_normalization(monkeypatch):
    monkeypatch.setattr(quota, 'run', lambda *a:subprocess.CompletedProcess([],0,json.dumps({'windows':[{'kind':'five_hour','used_percent':20,'resets_at':'2026-10-01T12:00:00Z'}]}).encode()))
    item=quota.read_notebooklm('nb',{})[0]
    assert item['remaining_percent']==80 and item['window_minutes']==300 and item['resets_at']==1790856000


@pytest.mark.asyncio
async def test_notebook_cli_multiline_json_stdin_session_and_api(local_app, monkeypatch):
    app, runtime, root=local_app
    async def status(refresh=False):
        return {'providers':[{'id':'notebooklm','authenticated':True}]}
    monkeypatch.setattr(runtime,'status',status)
    script=root/'notebook_mock.py'
    script.write_text('''import sys,json
prompt=sys.stdin.buffer.read().decode('utf-8')
assert 'درخواست فارسی' in prompt
assert 'You are working through Flux' not in prompt
print(json.dumps({'answer':'پاسخ فارسی [1]','conversation_id':'notebook-session','references':[{'source_id':'source1'}]},ensure_ascii=False,indent=2))
''', encoding='utf-8')
    commands=[]
    def command(chat, executable):
        commands.append(dict(chat))
        return [sys.executable,'-u',str(script)]
    monkeypatch.setattr(module,'command_for',command)
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response=await client.post('/api/local/chats',json={'provider':'notebooklm','notebook_id':'book-1','cwd':str(root)})
        chat=response.json()
        assert chat['notebook_id']=='book-1'
        for key in ('first','second'):
            result=await client.post('/api/local/chats/'+chat['id']+'/turns',json={'prompt':'درخواست فارسی','request_key':key})
            turn=await finish(runtime,result.json()['id'])
            assert turn['state']=='completed' and '[1]' in turn['text']
        assert commands[1]['session_id']=='notebook-session'
        assert runtime.chat(chat['id'])['notebook_id']=='book-1'
        monkeypatch.setattr(module,'list_notebooks',lambda *a:{'notebooks':[{'id':'book-1','title':'test'}]})
        assert (await client.get('/api/local/notebooks')).json()['notebooks'][0]['id']=='book-1'
