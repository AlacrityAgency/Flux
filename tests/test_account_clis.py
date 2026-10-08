"""Provider isolation, terminal protocols, encrypted secrets and one-send API behavior."""
import json
import os
import pytest
import httpx
from flux.local_agents.runtime import command_for,cli_environment,EventParser,ChatSpec
from flux.local_agents import gemini_api


def test_gapcode_scope_does_not_override_account_provider():
    args=command_for({'provider':'gapcode','access':'read','model':'','session_id':'known'},'gapcode.exe')
    assert args[:4]==['gapcode.exe','exec','resume','known']
    assert 'sandbox_mode="read-only"' in args and 'model_provider="openai"' not in args
    parser=EventParser('gapcode');parser.feed({'type':'thread.started','thread_id':'known'})
    parser.feed({'type':'item.completed','item':{'type':'agent_message','text':'response'}})
    parser.feed({'type':'turn.completed','usage':{'input_tokens':12}})
    assert parser.complete and parser.usage['billing']=='gapcode-wallet'


def test_gemini_protocol_and_environment(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','inherited-secret');monkeypatch.setenv('GOOGLE_GENAI_USE_VERTEXAI','1')
    env=cli_environment('gemini');assert 'GEMINI_API_KEY' not in env and 'GOOGLE_GENAI_USE_VERTEXAI' not in env
    args=command_for({'provider':'gemini','access':'read','model':'','session_id':'exact'},'gemini.js')
    assert args[args.index('--approval-mode')+1]=='plan' and args[args.index('--resume')+1]=='exact'
    parser=EventParser('gemini');parser.feed({'type':'init','session_id':'g1'})
    parser.feed({'type':'message','role':'assistant','content':'reply','delta':True})
    assert not parser.complete
    parser.feed({'type':'result','status':'success','stats':{'input_tokens':20}})
    assert parser.complete and parser.text=='reply' and parser.usage['billing']=='google-account'


@pytest.mark.skipif(os.name!='nt',reason='Windows DPAPI')
def test_dpapi_storage_does_not_store_plaintext(tmp_path,monkeypatch):
    path=tmp_path/'keys.json';monkeypatch.setenv('FLUX_KEYS_PATH',str(path))
    gemini_api.save_key('unit_test_secret_1234567890')
    assert 'unit_test_secret' not in path.read_text() and gemini_api.get_key()=='unit_test_secret_1234567890'
    gemini_api.save_key('');assert not gemini_api.get_key()


@pytest.mark.asyncio
async def test_gemini_rest_one_send_and_no_secret_in_url(monkeypatch,tmp_path):
    monkeypatch.setattr(gemini_api,'get_key',lambda:'fixture-key')
    seen=[]
    def respond(request):
        seen.append(request)
        assert str(request.url).endswith('/models/gemini-fixture:generateContent')
        assert 'fixture-key' not in str(request.url)
        assert request.headers['x-goog-api-key']=='fixture-key'
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'actual answer'}]}}],'usageMetadata':{'promptTokenCount':3,'candidatesTokenCount':4}})
    original=httpx.AsyncClient
    monkeypatch.setattr(gemini_api.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    text,usage=await gemini_api.generate('gemini-fixture','prompt')
    assert text=='actual answer' and len(seen)==1 and usage['input_tokens']==3
    assert ChatSpec(provider='gemini-api',cwd=str(tmp_path),access='work').access=='read'


@pytest.mark.asyncio
async def test_gemini_rejected_response_never_retried(monkeypatch):
    monkeypatch.setattr(gemini_api,'get_key',lambda:'fixture-key');seen=[]
    def respond(request):seen.append(request);return httpx.Response(429,json={'error':'quota'})
    original=httpx.AsyncClient
    monkeypatch.setattr(gemini_api.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    with pytest.raises(ValueError,match='429'):await gemini_api.generate('gemini-fixture','prompt')
    assert len(seen)==1
