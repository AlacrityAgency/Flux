import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

from flux.api.app import create_app
from flux.providers.fake import FakeProvider
from flux.providers.base import ProviderError
from flux.storage.workspace import Workspace
from flux.storage.database import init_db
from flux.storage.repository import Repository


@pytest.mark.asyncio
async def test_background_chat_exposes_live_state_and_persists_output(engine, fake_provider, sample_task_data):
    fake_provider.delay_seconds = .02
    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        chat = (await client.post('/conversations', json={"title": "First workspace"})).json()
        task = {**sample_task_data, "workflow": "team"}
        response = await client.post('/runs?background=true', json={"task": task, "conversation_id": chat['id'], "idempotency_key": "background"})
        assert response.status_code == 202
        run_id = response.json()['run_id']
        assert (await client.get('/runs/'+run_id)).json()['status'] != 'ACCEPT_CANDIDATE'
        for _ in range(100):
            if not app.state.jobs:
                break
            await asyncio.sleep(.01)
        conversation = (await client.get('/conversations/'+chat['id'])).json()
        run = conversation['runs'][0]
        assert run['status'] == 'ACCEPT_CANDIDATE'
        assert len(run['calls']) == 5
        assert [s['assigned_agent'] for s in run['subtasks']] == ['opus', 'sol', 'luna']
        assert run['subtasks'][-1]['output']['content']
        assert run['task']['acceptance_criteria'] == sample_task_data['acceptance_criteria']
        assert (await client.post('/runs/'+run_id+'/accept')).status_code == 200
        assert (await client.get('/runs/'+run_id)).json()['acceptance']['content_hash']


@pytest.mark.asyncio
async def test_memory_crud_retrieval_and_deleted_memory_not_reused(engine, sample_task_data):
    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        memory = (await client.post('/memories', json={"title": "Flux architecture", "content": "Flux uses local memory."})).json()
        task = {**sample_task_data, "task_id": "memory-task"}
        run = (await client.post('/runs', json={"task": task})).json()
        detail = (await client.get('/runs/'+run['run_id'])).json()
        assert any(c['ref'] == memory['id'] for c in detail['task']['context'])
        edited = await client.put('/memories/'+memory['id'], json={"title": "Flux architecture", "content": "Updated local memory.", "enabled": False})
        assert edited.json()['revision'] == 2
        assert app.state.workspace.retrieve(task['objective']) == []
        assert (await client.delete('/memories/'+memory['id'])).status_code == 200
        assert (await client.get('/memories')).json() == []
        assert app.state.workspace.retrieve(task['objective']) == []


def test_memory_and_preferences_survive_restart(tmp_path):
    path = str(tmp_path/'workspace.db')
    conn = init_db(path)
    workspace = Workspace(Repository(conn))
    item = workspace.save_memory('Local facts', 'Persistent content')
    workspace.save_preferences({'daily_budget': 1.25})
    conn.close()
    conn = init_db(path)
    workspace = Workspace(Repository(conn))
    assert workspace.memories()[0]['id'] == item['id']
    assert workspace.preferences()['daily_budget'] == 1.25
    conn.close()


@pytest.mark.asyncio
async def test_validation_idempotency_and_origin_guard(engine, sample_task_data):
    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert (await client.post('/runs', json={"task": {}})).status_code == 422
        response = await client.post('/runs', json={"task": sample_task_data, "idempotency_key": "same"})
        assert response.status_code == 201
        changed = {**sample_task_data, 'objective': 'A different objective'}
        assert (await client.post('/runs', json={"task": changed, "idempotency_key": "same"})).status_code == 409
        assert (await client.post('/memories', headers={'Origin': 'https://untrusted.example'}, json={'title': 'x', 'content': 'y'})).status_code == 403
        # Synthetic sentinel, not a usable API credential.
        secret = 'sk-' + 'x'*24
        response = await client.post('/memories', json={'title': 'secret', 'content': secret})
        assert response.status_code == 422
        assert secret not in response.text


@pytest.mark.asyncio
async def test_daily_budget_is_shared_across_runs(engine, sample_task_data):
    app = create_app(engine=engine)
    app.state.workspace.save_preferences({'daily_budget': .12})
    first, _ = engine.submit_run(sample_task_data)
    await engine.execute_run(first)
    second, _ = engine.submit_run({**sample_task_data, 'task_id':'second'})
    result = await engine.execute_run(second)
    assert result.status == 'PAUSED_BUDGET'
    assert app.state.workspace.usage()['spent'] <= .12


@pytest.mark.asyncio
async def test_cancel_during_provider_call_keeps_cost_and_stops_next_agent(engine, fake_provider, sample_task_data):
    fake_provider.delay_seconds = .04
    run_id, _ = engine.submit_run(sample_task_data)
    job = asyncio.create_task(engine.execute_run(run_id))
    await asyncio.sleep(.01)
    assert engine.cancel_run(run_id)
    result = await job
    assert result.status == 'CANCELLED'
    assert fake_provider.call_count == 1
    assert result.spent_cost_usd > 0
    assert engine.repo.get_subtasks(run_id) == []


@pytest.mark.asyncio
async def test_followup_has_prior_output_and_memory_opt_out(engine, sample_task_data):
    app = create_app(engine=engine)
    app.state.workspace.save_memory('Flux architecture', 'A relevant memory')
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        chat = (await client.post('/conversations', json={'title':'Thread'})).json()
        first = (await client.post('/runs', json={'task':sample_task_data,'conversation_id':chat['id'],'use_memory':False})).json()
        second = (await client.post('/runs', json={'task':{**sample_task_data,'task_id':'followup'},'conversation_id':chat['id'],'use_memory':False})).json()
        run = (await client.get('/runs/'+second['run_id'])).json()
        assert len(run['task']['context']) == 1
        assert run['task']['context'][0]['ref'] == first['run_id']


@pytest.mark.asyncio
async def test_ordinary_agent_retries_are_individually_reserved(engine, fake_provider, sample_task_data):
    original = fake_provider.generate
    failed = 0
    async def flaky(model_id, *args, **kwargs):
        nonlocal failed
        if model_id == 'gpt-5.6-luna' and failed < 2:
            failed += 1
            raise ProviderError('temporary', is_transient=True, status_code=503)
        return await original(model_id, *args, **kwargs)
    fake_provider.generate = flaky
    run_id, _ = engine.submit_run(sample_task_data)
    result = await engine.execute_run(run_id)
    assert result.status == 'ACCEPT_CANDIDATE'
    assert result.total_calls == 5
    assert result.unknown_cost_usd > 0
    statuses = [r[0] for r in engine.repo.conn.execute('SELECT status FROM budget_reservations WHERE run_id=?',(run_id,))]
    assert statuses.count('held_unknown') == 2


@pytest.mark.asyncio
async def test_missing_review_criterion_prevents_acceptance(engine, fake_provider, sample_task_data):
    fake_provider.custom_responses['gapgpt-qwen-3.6-thinking'] = json.dumps({
        'decision':'ACCEPT_CANDIDATE','blocking_issues':[], 'passed_criteria':[],
        'failed_criteria':[],'confidence':'high'})
    run_id, _ = engine.submit_run(sample_task_data)
    result = await engine.execute_run(run_id)
    assert result.status == 'REVISE'
    assert len(result.decision.blocking_issues) == len(sample_task_data['acceptance_criteria'])


@pytest.mark.asyncio
async def test_reviewer_paraphrase_is_normalized_to_the_immutable_root_criteria(engine, fake_provider, sample_task_data):
    fake_provider.custom_responses['gapgpt-qwen-3.6-thinking'] = json.dumps({
        'decision': 'ACCEPT_CANDIDATE', 'blocking_issues': [],
        'passed_criteria': ['The documentation is complete', 'The diagram is clear'],
        'failed_criteria': [], 'confidence': 'high'})
    run_id, _ = engine.submit_run(sample_task_data)
    result = await engine.execute_run(run_id)
    assert result.status == 'ACCEPT_CANDIDATE'
    assert result.decision.passed_criteria == sample_task_data['acceptance_criteria']
