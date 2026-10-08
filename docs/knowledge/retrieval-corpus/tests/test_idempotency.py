"""Test 8: idempotency از اجرای دوباره جلوگیری کند (Idempotency prevents duplicate execution)."""

import pytest


@pytest.mark.asyncio
async def test_idempotency_prevents_duplicate_runs(engine, fake_provider, sample_task_data):
    """Submitting the same task with the same idempotency key
    returns the existing run_id and is_new=False without executing duplicate calls.
    """
    key = "idem_key_12345"

    run_id_1, is_new_1 = engine.submit_run(sample_task_data, idempotency_key=key)
    assert is_new_1 is True

    # Execute first run
    res_1 = await engine.execute_run(run_id_1)
    assert res_1.status == "ACCEPT_CANDIDATE"
    first_call_count = fake_provider.call_count

    # Submit again with same key
    run_id_2, is_new_2 = engine.submit_run(sample_task_data, idempotency_key=key)
    assert is_new_2 is False
    assert run_id_2 == run_id_1

    # Call count should not have increased
    assert fake_provider.call_count == first_call_count
