"""Test 12: پاسخ JSON نامعتبر مدیریت و ثبت شود (Invalid JSON handled gracefully)."""

import pytest


@pytest.mark.asyncio
async def test_invalid_json_from_model_handled_and_logged(engine, fake_provider, sample_task_data):
    """When LLM returns corrupted or non-JSON output, engine does not crash unhandled;
    it logs an event, handles the error, and transitions run to FAILED.
    """
    fake_provider.simulate_invalid_json = True

    run_id, _ = engine.submit_run(sample_task_data)
    result = await engine.execute_run(run_id)

    assert result.status == "FAILED"
    assert "Invalid" in result.summary or "JSON" in result.summary

    # Verify event was recorded in DB
    events = engine.repo.get_events(run_id)
    fail_event = next((e for e in events if e["to_state"] == "FAILED"), None)
    assert fail_event is not None
    assert "JSON" in fail_event["reason"]
