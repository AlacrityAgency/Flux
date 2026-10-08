"""Test 5: سقف بودجه قابل عبور نباشد (Budget cap cannot be exceeded)."""

import pytest
from flux.budget.ledger import BudgetLedger, BudgetExceededError


@pytest.mark.asyncio
async def test_budget_cap_stops_call_when_insufficient(engine, sample_task_data):
    """When budget is insufficient to reserve for Head Agent call,
    engine stops and transitions to PAUSED_BUDGET.
    """
    # Head Agent call with max_output 2000 tokens at $50/M requires at least ~$0.10.
    # Set cap to tiny amount $0.005
    tiny_budget_task = dict(sample_task_data)
    tiny_budget_task["budget_cap_usd"] = 0.005

    run_id, _ = engine.submit_run(tiny_budget_task)
    result = await engine.execute_run(run_id)

    assert result.status == "PAUSED_BUDGET"
    usage = engine.repo.get_usage_summary(run_id)
    # Invariant: spent + reserved + unknown <= cap
    total_committed = usage["spent_cost_usd"] + usage["reserved_cost_usd"] + usage["unknown_cost_usd"]
    assert total_committed <= tiny_budget_task["budget_cap_usd"]


@pytest.mark.asyncio
async def test_missing_usage_keeps_reserved_as_unknown(engine, fake_provider, sample_task_data):
    """When usage information is missing, reservation is not released,
    and is held as unknown_cost_usd to prevent budget overrun.
    """
    fake_provider.simulate_missing_usage = True

    run_id, _ = engine.submit_run(sample_task_data)
    result = await engine.execute_run(run_id)

    usage = engine.repo.get_usage_summary(run_id)
    assert usage["unknown_cost_usd"] > 0.0
    total_committed = usage["spent_cost_usd"] + usage["reserved_cost_usd"] + usage["unknown_cost_usd"]
    assert total_committed <= sample_task_data["budget_cap_usd"]
