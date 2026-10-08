"""Test 7: retry بیشتر از حد تعریف‌شده انجام نشود (Retry limit enforced)."""

import pytest
from flux.providers.base import ProviderError


@pytest.mark.asyncio
async def test_transient_error_retries_at_most_twice(engine, fake_provider, sample_task_data):
    """When a transient error (429) occurs, engine retries at most 2 times.
    Head has its stricter two-send cap; one retry may succeed.
    """
    fake_provider.transient_error_countdown = 1

    run_id, _ = engine.submit_run(sample_task_data)
    result = await engine.execute_run(run_id)

    assert result.status == "ACCEPT_CANDIDATE"
    # The Head call had one failure and one success, both accounted for.
    assert fake_provider.call_count == 4
    assert result.total_calls == 4
    assert result.unknown_cost_usd > 0


@pytest.mark.asyncio
async def test_transient_error_fails_if_exceeding_two_retries(engine, fake_provider, sample_task_data):
    """If transient error occurs 3 times (more than 2 retries allowed),
    it fails without doing infinite or excess retries.
    """
    fake_provider.transient_error_countdown = 3  # Needs 3 retries, but max is 2

    run_id, _ = engine.submit_run(sample_task_data)
    result = await engine.execute_run(run_id)

    assert result.status == "FAILED"
    # Head is capped at two sends, even though ordinary agents allow three.
    assert fake_provider.call_count == 2


@pytest.mark.asyncio
async def test_permanent_error_not_retried(engine, fake_provider, sample_task_data):
    """Permanent error (401 auth error) is never retried (0 retries)."""
    fake_provider.permanent_error = True

    run_id, _ = engine.submit_run(sample_task_data)
    result = await engine.execute_run(run_id)

    assert result.status == "FAILED"
    # Exactly 1 call was attempted (0 retries)
    assert fake_provider.call_count == 1
