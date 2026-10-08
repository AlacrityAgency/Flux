"""Session import boundaries, stale-response rejection and Flux turn integration."""
import asyncio
import json
import os
import time
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from flux.api.app import create_app
from flux.engine.orchestrator import FluxEngine
from flux.providers.fake import FakeProvider
from flux.storage.database import init_db
from flux.storage.repository import Repository
from flux.local_agents import web_session as web
from flux.local_agents.runtime import ChatSpec, TurnSpec


def cookie(domain='chat.deepseek.com',value='fixture-private-session'):
    return {'name':'fixture_session','value':value,'domain':domain,'path':'/','expirationDate':time.time()+3600}


def test_scoping_expiry_and_playwright_storage_formats():
    state=web.normalize_state('deepseek-web',{'cookies':[cookie(),cookie('evil.deepseek.com'),cookie('google.com')],
        'origins':[{'origin':'https://chat.deepseek.com','localStorage':[{'name':'fixture','value':'private'}]},
                   {'origin':'https://evil.deepseek.com','localStorage':[{'name':'bad','value':'private'}]}]})
    assert len(state['cookies'])==1 and len(state['origins'])==1
    assert state['cookies'][0]['expires']>time.time()
    expired=cookie();expired['expirationDate']=time.time()-1
    with pytest.raises(ValueError):web.normalize_state('deepseek-web',[expired])
    with pytest.raises(ValueError):web.normalize_state('deepseek-web',[cookie('deepseek.com.evil.example')])
    invalid=cookie();invalid['value']={'token':'wrong shape'}
    with pytest.raises(ValueError):web.normalize_state('deepseek-web',[invalid])


@pytest.mark.skipif(os.name!='nt',reason='Windows encrypted session store')
def test_import_encrypted_no_auth_claim_and_no_raw_values(tmp_path,monkeypatch):
    monkeypatch.setenv('FLUX_WEB_SESSION_DIR',str(tmp_path/'encrypted'))
    source=tmp_path/'export.json';source.write_text(json.dumps([cookie()]),encoding='utf-8')
    original=source.read_bytes()
    result=web.import_session('deepseek-web',str(source))
    assert result['saved'] and not result['credential_validated'] and not result['transport_verified']
    assert 'fixture-private-session' not in web.state_path('deepseek-web').read_text()
    assert web.load_state('deepseek-web')['state']['cookies'][0]['value']=='fixture-private-session'
    status=web.inspect('deepseek-web')
    assert status['configured'] and not status['authenticated'] and 'fixture-private-session' not in json.dumps(status)
    assert source.read_bytes()==original


@pytest.mark.parametrize('provider,url,expected',[
    ('gemini-web','https://gemini.google.com/app/abc123',True),
    ('deepseek-web','https://chat.deepseek.com/a/chat/s/abc-123',True),
    ('deepseek-web','https://chat.deepseek.com.evil.example/a/chat/s/abc',False),
    ('deepseek-web','https://user@chat.deepseek.com/a/chat/s/abc',False),
    ('gemini-web','https://gemini.google.com/app/abc?token=secret',False),
    ('gemini-web','http://gemini.google.com/app/abc',False),
])
def test_exact_session_url_allowlist(provider,url,expected):
    assert web.valid_session_url(provider,url)==expected


class PageFixture:
    """An older reply is already complete; the new reply streams before controls arrive."""
    def __init__(self):self.url='https://chat.deepseek.com/a/chat/s/fixture';self.step=0;self.sends=0
    def locator(self,selector):return FixtureLocator(self,'composer' if selector=='textarea' else 'response')
    def get_by_role(self,role,**kwargs):return FixtureLocator(self,'terminal')


class FixtureLocator:
    def __init__(self,page,kind):self.page=page;self.kind=kind
    @property
    def last(self):return self
    async def wait_for(self,**kwargs):pass
    async def fill(self,text):self.page.prompt=text
    async def press(self,key):self.page.step=1;self.page.sends+=1
    async def count(self):
        if self.kind=='response':return 1 if not self.page.step else 2
        if self.kind=='terminal':return 1 if self.page.step<3 else 2
        return 1
    async def inner_text(self):return 'partial' if self.page.step<2 else 'complete answer'
    async def is_visible(self):return True


@pytest.mark.asyncio
async def test_new_reply_cannot_complete_on_old_message_controls(monkeypatch):
    page=PageFixture()
    async def tick(seconds):page.step+=1
    monkeypatch.setattr(web.asyncio,'sleep',tick)
    assert await web.drive_page('deepseek-web',page,'user request')=='complete answer'
    assert page.step==4 and page.sends==1


@pytest.mark.asyncio
async def test_cancel_before_terminal_never_returns_partial_or_resends(monkeypatch):
    page=PageFixture()
    async def stop(seconds):raise asyncio.CancelledError()
    monkeypatch.setattr(web.asyncio,'sleep',stop)
    with pytest.raises(asyncio.CancelledError):await web.drive_page('deepseek-web',page,'request')
    assert page.sends==1


@pytest.mark.asyncio
async def test_gemini_guest_composer_does_not_prove_account_login():
    page=PageFixture();page.url='https://gemini.google.com/app'
    class GuestLocator(FixtureLocator):
        async def count(self):return 0
    page.get_by_role=lambda role,**kw:GuestLocator(page,'account') if role=='link' else FixtureLocator(page,'composer')
    with pytest.raises(web.SessionError,match='مهمان'):await web.require_login('gemini-web',page)
    assert page.sends==0


@pytest.mark.asyncio
async def test_browser_launch_failure_is_redacted_and_not_retried(tmp_path,monkeypatch):
    from playwright import async_api
    monkeypatch.setenv('FLUX_WEB_SESSION_DIR',str(tmp_path/'encrypted'))
    web.save_state('deepseek-web',{'cookies':[cookie()]},verified=True)
    launches=[]
    class Engine:
        async def __aenter__(self):return SimpleNamespace(chromium=self)
        async def __aexit__(self,*args):pass
        async def launch(self,**kwargs):
            launches.append(kwargs)
            raise RuntimeError('fixture-private-session must never enter a turn error')
    monkeypatch.setattr(async_api,'async_playwright',Engine)
    with pytest.raises(web.SessionError) as error:await web.generate('deepseek-web','request')
    assert 'fixture-private-session' not in str(error.value)
    assert launches==[{'channel':'msedge','headless':False}]
    assert not web.load_state('deepseek-web')['verified']


@pytest.fixture
def web_app(tmp_path,monkeypatch):
    monkeypatch.setenv('FLUX_WEB_SESSION_DIR',str(tmp_path/'encrypted'))
    repo=Repository(init_db(':memory:'));app=create_app(FluxEngine(repo,FakeProvider()))
    return app,app.state.local_runtime


@pytest.mark.asyncio
async def test_flux_web_turn_resume_idempotency_and_no_cli(web_app,tmp_path,monkeypatch):
    app,runtime=web_app;calls=[]
    async def status(refresh=False):return {'providers':[{'id':'deepseek-web','authenticated':True}]}
    async def generate(provider,prompt,session_id=None,**kwargs):
        calls.append((provider,session_id,prompt))
        return 'complete answer',{'physical_requests':1,'usage_available':False},'https://chat.deepseek.com/a/chat/s/fixture'
    monkeypatch.setattr(runtime,'status',status);monkeypatch.setattr(web,'generate',generate)
    chat=runtime.create_chat(ChatSpec(provider='deepseek-web',cwd=str(tmp_path),access='work'))
    assert chat['access']=='read'
    spec=TurnSpec(prompt='first',request_key='one',use_memory=False)
    turn=runtime.submit(chat['id'],spec);await runtime.jobs[turn['id']]
    assert runtime.turn(turn['id'])['state']=='completed'
    assert runtime.submit(chat['id'],spec)['id']==turn['id'] and len(calls)==1
    second=runtime.submit(chat['id'],TurnSpec(prompt='second',request_key='two',use_memory=False))
    await runtime.jobs[second['id']]
    assert calls[0][1] is None and calls[1][1]=='https://chat.deepseek.com/a/chat/s/fixture'
    runtime.web_connecting=True
    with pytest.raises(RuntimeError):runtime.submit(chat['id'],TurnSpec(prompt='third',request_key='three'))
    with pytest.raises(ValueError):ChatSpec(provider='gemini-web',cwd=str(tmp_path),model='fake-model')


@pytest.mark.asyncio
async def test_import_api_resets_old_account_sessions_and_requires_verification(web_app,tmp_path,monkeypatch):
    app,runtime=web_app
    source=tmp_path/'session.json';source.write_text(json.dumps([cookie()]),encoding='utf-8')
    chat=runtime.create_chat(ChatSpec(provider='deepseek-web',cwd=str(tmp_path)))
    with runtime.conn:runtime.conn.execute('UPDATE local_chats SET session_id=? WHERE id=?',('old-account',chat['id']))
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        result=await client.put('/api/local/connections/web/deepseek-web',json={'path':str(source)})
        assert result.status_code==200 and not result.json()['transport_verified']
        assert runtime.chat(chat['id'])['session_id'] is None
        runtime.web_connecting=True
        assert (await client.put('/api/local/connections/web/deepseek-web',json={'path':str(source)})).status_code==409
        assert (await client.post('/api/local/connections/web/deepseek-web/verify')).status_code==409
        runtime.web_connecting=False
        assert (await client.put('/api/local/connections/web/other',json={'path':str(source)})).status_code==404
