"""Test 2: Task خارج از شرکت Reject شود (Task outside company rejected)."""

import pytest


@pytest.mark.asyncio
async def test_task_outside_company_rejected(engine, fake_provider, sample_task_data):
    """When Head Agent detects company_relevance == 'invalid',
    run must transition to REJECTED and NO specialized agents (Opus, Sol, Luna, Qwen) must run.
    """
    fake_provider.scenario = "out_of_company"

    run_id, _ = engine.submit_run(sample_task_data)
    result = await engine.execute_run(run_id)

    assert result.status == "REJECTED"
    # Exactly 1 provider call (Head Agent only)
    assert fake_provider.call_count == 1
    recorded = fake_provider.recorded_calls
    assert len(recorded) == 1
    assert recorded[0]["model_id"] == "claude-fable-5"
