"""Test 1: Task نامعتبر قبل از API متوقف شود (Invalid Task stopped before API)."""

import pytest


@pytest.mark.asyncio
async def test_invalid_task_stopped_before_api(engine, fake_provider, sample_task_data):
    """Verifies that invalid tasks (empty objective, empty criteria, secret data, or budget <= 0)
    fail before any LLM provider calls are made (call_count == 0).
    """
    invalid_scenarios = [
        ("empty_task_id", {"task_id": ""}),
        ("empty_human_owner", {"human_owner": ""}),
        ("empty_objective", {"objective": ""}),
        ("vague_objective", {"objective": "fix"}),
        ("empty_criteria", {"acceptance_criteria": []}),
        ("zero_budget", {"budget_cap_usd": 0.0}),
        ("negative_budget", {"budget_cap_usd": -0.50}),
        ("secret_data_class", {"data_class": "secret"}),
    ]

    for name, patch in invalid_scenarios:
        bad_task = dict(sample_task_data)
        bad_task.update(patch)

        initial_calls = fake_provider.call_count
        run_id, _ = engine.submit_run(bad_task)
        result = await engine.execute_run(run_id)

        # Invariant: Must fail immediately without calling LLM
        assert result.status == "FAILED", f"Scenario {name} should have failed, got {result.status}"
        assert fake_provider.call_count == initial_calls, f"Scenario {name} called provider {fake_provider.call_count - initial_calls} times! Expected 0."
