"""Test 10: restart باعث گم‌شدن Run یا رزرو نشود (Persistence across restarts)."""

import os
import tempfile
import pytest
from flux.storage.database import init_db
from flux.storage.repository import Repository
from flux.engine.orchestrator import FluxEngine
from flux.providers.fake import FakeProvider


@pytest.mark.asyncio
async def test_restart_preserves_runs_counters_and_reservations(sample_task_data):
    """Verifies that closing and reopening the SQLite database does not lose
    runs, subtasks, events, counters, or budget reservations.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Phase 1: Initialize, submit and run
        conn1 = init_db(db_path)
        repo1 = Repository(conn1)
        provider1 = FakeProvider()
        engine1 = FluxEngine(repo=repo1, provider=provider1)

        run_id, _ = engine1.submit_run(sample_task_data, idempotency_key="restart_key_1")
        result1 = await engine1.execute_run(run_id)
        assert result1.status == "ACCEPT_CANDIDATE"

        usage1 = repo1.get_usage_summary(run_id)
        events1 = repo1.get_events(run_id)
        subtasks1 = repo1.get_subtasks(run_id)

        # Close database connection (simulating process restart)
        conn1.close()

        # Phase 2: Reopen from same file with new connection and repo
        conn2 = init_db(db_path)
        repo2 = Repository(conn2)

        run_rec = repo2.get_run(run_id)
        assert run_rec is not None
        assert run_rec["status"] == "ACCEPT_CANDIDATE"
        assert run_rec["total_calls"] == len(provider1.recorded_calls)

        usage2 = repo2.get_usage_summary(run_id)
        assert usage2["spent_cost_usd"] == usage1["spent_cost_usd"]
        assert usage2["total_calls"] == usage1["total_calls"]

        events2 = repo2.get_events(run_id)
        assert len(events2) == len(events1)

        subtasks2 = repo2.get_subtasks(run_id)
        assert len(subtasks2) == len(subtasks1)

        conn2.close()
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass
