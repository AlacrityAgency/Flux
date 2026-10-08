"""Tests for all 7 required FastAPI internal endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from flux.api.app import create_app
from flux.engine.orchestrator import FluxEngine
from flux.providers.fake import FakeProvider
from flux.storage.database import init_db
from flux.storage.repository import Repository


@pytest.fixture
def app_and_engine():
    conn = init_db(":memory:")
    repo = Repository(conn)
    provider = FakeProvider()
    engine = FluxEngine(repo=repo, provider=provider)
    app = create_app(engine=engine)
    return app, engine, provider


@pytest.mark.asyncio
async def test_all_api_endpoints(app_and_engine, sample_task_data):
    app, engine, provider = app_and_engine

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. GET /models/status
        res_models = await client.get("/models/status")
        assert res_models.status_code == 200
        models_data = res_models.json()
        assert "models" in models_data
        assert "claude-fable-5" in models_data["models"]
        assert "claude-opus-5" in models_data["models"]
        assert "gpt-5.6-sol" in models_data["models"]
        assert "gpt-5.6-luna" in models_data["models"]
        assert "gapgpt-qwen-3.6-thinking" in models_data["models"]

        # 2. POST /runs
        res_submit = await client.post(
            "/runs",
            json={"task": sample_task_data, "idempotency_key": "api_test_01"}
        )
        assert res_submit.status_code == 201
        run_info = res_submit.json()
        assert "run_id" in run_info
        run_id = run_info["run_id"]
        assert run_info["is_new"] is True
        assert run_info["status"] == "ACCEPT_CANDIDATE"

        # 3. GET /runs/:id
        res_get = await client.get(f"/runs/{run_id}")
        assert res_get.status_code == 200
        run_detail = res_get.json()
        assert run_detail["run_id"] == run_id
        assert run_detail["status"] == "ACCEPT_CANDIDATE"
        assert len(run_detail["subtasks"]) > 0

        # 4. GET /runs/:id/events
        res_events = await client.get(f"/runs/{run_id}/events")
        assert res_events.status_code == 200
        events_data = res_events.json()
        assert "events" in events_data
        assert len(events_data["events"]) >= 5

        # 5. GET /runs/:id/usage
        res_usage = await client.get(f"/runs/{run_id}/usage")
        assert res_usage.status_code == 200
        usage_data = res_usage.json()
        assert "spent_cost_usd" in usage_data
        assert usage_data["spent_cost_usd"] > 0.0

        # 6. POST /runs with same idempotency_key
        res_dup = await client.post(
            "/runs",
            json={"task": sample_task_data, "idempotency_key": "api_test_01"}
        )
        assert res_dup.status_code == 201
        dup_data = res_dup.json()
        assert dup_data["run_id"] == run_id
        assert dup_data["is_new"] is False

        # 7. Cancel on a new run
        run_id_2, _ = engine.submit_run(sample_task_data, idempotency_key="api_cancel_test")
        res_cancel = await client.post(f"/runs/{run_id_2}/cancel")
        assert res_cancel.status_code == 200
        assert res_cancel.json()["status"] == "CANCELLED"

        # 8. GET / (Claude/Codex Web UI)
        res_ui = await client.get("/legacy")
        assert res_ui.status_code == 200
        assert 'id="composer"' in res_ui.text
        assert '/static/app.js' in res_ui.text
        assert (await client.get('/static/app.js')).status_code == 200
        assert (await client.get('/static/app.css')).status_code == 200

        # 9. GET /runs (Sidebar history list)
        res_list = await client.get("/runs")
        assert res_list.status_code == 200
        runs_list = res_list.json()
        assert isinstance(runs_list, list)
        assert len(runs_list) >= 2


@pytest.mark.asyncio
async def test_prompt_path_auto_detection(app_and_engine, sample_task_data, tmp_path):
    app, engine, provider = app_and_engine
    # Create a small directory with a source file
    test_dir = tmp_path / "my_project"
    test_dir.mkdir()
    (test_dir / "main.py").write_text("print('hello')", encoding="utf-8")

    sample_task_data["objective"] = f"Check this project at {test_dir}"
    sample_task_data["task_id"] = "auto_detect_task"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/runs",
            json={"task": sample_task_data, "idempotency_key": "auto_detect_key"}
        )
        assert res.status_code == 201
        run_id = res.json()["run_id"]
        run_detail = (await client.get(f"/runs/{run_id}")).json()
        task_data = run_detail.get("task") or {}
        context_refs = [c.get("ref", "") for c in task_data.get("context", [])]
        assert any(ref.startswith("folder:") for ref in context_refs)

