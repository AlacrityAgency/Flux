"""Profile routing and provider budget regression coverage (no network)."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport

from flux.api.app import create_app
from flux.contracts.task import TaskInput
from flux.providers.gapgpt import GapGPTAdapter
from flux.providers.base import ProviderError


@pytest.mark.parametrize("level, expected_calls", [("low", 3), ("medium", 3), ("high", 5)])
async def test_profile_roundtrip(engine, fake_provider, sample_task_data, level, expected_calls):
    app = create_app(engine=engine)
    task = {**sample_task_data, "workflow": level, "budget_cap_usd": 2}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/runs", json={"task": task})
        assert response.status_code == 201
        result = response.json()
        assert result["status"] == "ACCEPT_CANDIDATE"
        detail = (await client.get('/runs/' + result['run_id'])).json()
        assert detail['task']['workflow'] == level
        assert detail['total_calls'] == expected_calls
        if level == 'low':
            assert {c['model_id'] for c in detail['calls']} == {'gpt-5.6-luna'}
            assert all(c['max_output_tokens'] <= 8000 for c in fake_provider.recorded_calls)
        assert detail['spent_cost_usd'] > 0
        assert detail['reserved_cost_usd'] == 0


def test_default_is_low(sample_task_data):
    sample_task_data.pop('workflow')
    assert TaskInput(**sample_task_data).workflow == 'low'


@pytest.mark.parametrize('finish, content', [('stop', '{}'), ('length', ''), ('content_filter', '')])
async def test_provider_never_inflates_or_retries(monkeypatch, finish, content):
    response = SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish,
        message=SimpleNamespace(content=content, refusal=None))], usage=None)
    create = AsyncMock(return_value=response)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)), close=AsyncMock())
    adapter = GapGPTAdapter(api_key='test-only')
    monkeypatch.setattr(adapter, '_get_client', lambda: client)
    if content:
        await adapter.generate('gpt-5.6-sol', [], 1600)
    else:
        with pytest.raises(ProviderError) as exc:
            await adapter.generate('gpt-5.6-sol', [], 1600)
        assert not exc.value.is_transient
    create.assert_awaited_once()
    assert create.call_args.kwargs['max_tokens'] == 1600
    assert create.call_args.kwargs['model'] == 'gpt-5.6-sol'
    client.close.assert_awaited_once()
