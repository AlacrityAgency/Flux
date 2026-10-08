import json
import pytest
from httpx import AsyncClient, ASGITransport
from flux.api.app import create_app
from flux.engine.orchestrator import FluxEngine


def custom(enabled=True):
    return {'id': 'custom_12345678', 'name': 'ویراستار', 'role': 'luna',
            'model_id': 'gpt-5.6-sol', 'instructions': 'متن نهایی را ویرایش و روشن‌تر کن.', 'enabled': enabled}


async def test_saved_models_custom_execution_and_snapshot(engine, fake_provider, sample_task_data):
    async with AsyncClient(transport=ASGITransport(app=create_app(engine=engine)), base_url='http://test') as client:
        config = {'model_overrides': {'head': 'gpt-5.6-luna', 'verification': 'gpt-5.6-sol'}, 'custom_agents': [custom()]}
        assert (await client.put('/settings/agents', json=config)).status_code == 200
        # Configuration survives recreating the engine against the same database.
        assert FluxEngine(engine.repo, fake_provider).get_agent_settings().model_dump() == config
        run_id, _ = engine.submit_run({**sample_task_data, 'workflow': 'low', 'budget_cap_usd': 2})
        await client.put('/settings/agents', json={'model_overrides': {}, 'custom_agents': []})
        result = await engine.execute_run(run_id)
        assert result.status == 'ACCEPT_CANDIDATE'
        detail = (await client.get('/runs/' + run_id)).json()
        assert detail['task']['agent_settings'] == config
        assert [c['agent_role'] for c in detail['calls']] == ['head', 'luna', 'custom_12345678', 'verification']
        assert [c['model_id'] for c in detail['calls']] == ['gpt-5.6-luna', 'gpt-5.6-luna', 'gpt-5.6-sol', 'gpt-5.6-sol']
        prompt = fake_provider.recorded_calls[2]['messages']
        assert custom()['instructions'] in prompt[0]['content']
        assert json.loads(prompt[-1]['content'])['dependency_outputs']
        assert detail['spent_cost_usd'] > 0


async def test_disabled_agent_not_called(engine, sample_task_data):
    task = {**sample_task_data, 'workflow': 'low', 'agent_settings': {'custom_agents': [custom(False)]}}
    run_id, _ = engine.submit_run(task)
    assert (await engine.execute_run(run_id)).total_calls == 3


async def test_custom_agent_still_obeys_budget(engine, fake_provider, sample_task_data):
    task = {**sample_task_data, 'workflow': 'low', 'budget_cap_usd': .01,
            'agent_settings': {'custom_agents': [{**custom(), 'model_id': 'claude-opus-5'}]}}
    run_id, _ = engine.submit_run(task)
    result = await engine.execute_run(run_id)
    assert result.status == 'PAUSED_BUDGET'
    assert all(c['model_id'] == 'gpt-5.6-luna' for c in fake_provider.recorded_calls)
    assert result.spent_cost_usd + result.reserved_cost_usd + result.unknown_cost_usd <= .01


@pytest.mark.parametrize('config', [
    {'model_overrides': {'head': 'nonexistent'}},
    {'model_overrides': {'invented': 'gpt-5.6-luna'}},
    {'custom_agents': [custom(), custom()]},
    {'custom_agents': [{**custom(), 'id': 'head'}]},
    {'custom_agents': [{**custom(), 'model_id': 'nonexistent'}]},
    {'custom_agents': [{**custom(), 'id': f'custom_0000000{i}'} for i in range(6)]},
])
async def test_invalid_team_rejected(engine, config):
    async with AsyncClient(transport=ASGITransport(app=create_app(engine=engine)), base_url='http://test') as client:
        assert (await client.put('/settings/agents', json=config)).status_code == 422
        assert (await client.get('/settings/agents')).json() == {'model_overrides': {}, 'custom_agents': []}
