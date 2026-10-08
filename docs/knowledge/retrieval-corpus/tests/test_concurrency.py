"""Test 6: concurrency بیشتر از دو نشود (Concurrency does not exceed 2)."""

import asyncio
import json
import pytest
from flux.engine.scheduler import ConcurrencyLimiter


@pytest.mark.asyncio
async def test_concurrency_never_exceeds_two(engine, fake_provider, sample_task_data, limiter):
    """Verifies that even with multiple independent subtasks,
    at most 2 agents run concurrently at any given moment.
    """
    # Configure Head agent to create 4 independent parallel subtasks
    fake_provider.custom_responses["claude-fable-5"] = json.dumps({
        "task_type": "operations",
        "company_relevance": "valid",
        "summary": "4 parallel subtasks",
        "ambiguities": [],
        "risk_level": "low",
        "requires_human_input": False,
        "subtasks": [
            {
                "subtask_id": f"sub_{i}",
                "objective": f"Subtask {i}",
                "assigned_agent": "luna",
                "acceptance_criteria": ["Complete"],
                "dependencies": [],
                "max_output_tokens": 1000
            }
            for i in range(1, 5)
        ],
        "final_review_agent": "qwen",
        "reason": "Testing parallel execution"
    })

    # Wrap generate with slight async sleep to ensure concurrency overlaps
    original_gen = fake_provider.generate

    async def slow_generate(*args, **kwargs):
        await asyncio.sleep(0.02)
        return await original_gen(*args, **kwargs)

    fake_provider.generate = slow_generate

    run_id, _ = engine.submit_run(sample_task_data)
    result = await engine.execute_run(run_id)

    assert result.status == "ACCEPT_CANDIDATE"
    assert limiter.max_observed_concurrency <= 2
    assert limiter.active_count == 0
