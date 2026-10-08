import asyncio
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from flux.api.app import create_app


@pytest.mark.asyncio
async def test_project_crud_and_folder_validation(engine, tmp_path, sample_task_data):
    # Create sample folder with dummy files
    project_dir = tmp_path / "my_demo_project"
    project_dir.mkdir()
    (project_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    (project_dir / "README.md").write_text("# Demo", encoding="utf-8")

    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        # Validate path
        val_res = await client.get("/filesystem/validate-path", params={"path": str(project_dir)})
        assert val_res.status_code == 200
        val_data = val_res.json()
        assert val_data["exists"] is True
        assert val_data["is_dir"] is True
        assert val_data["total_files"] == 2

        # Non-existent path
        bad_val = await client.get("/filesystem/validate-path", params={"path": str(tmp_path / "missing")})
        assert bad_val.json()["exists"] is False

        missing_project_run = await client.post("/runs", json={
            "project_id": "missing_project",
            "task": {**sample_task_data, "task_id": "missing-project-run"},
        })
        assert missing_project_run.status_code == 404

        # Create project
        create_res = await client.post("/projects", json={
            "name": "پروژه تستی",
            "path": str(project_dir),
            "description": "توضیح تستی",
            "default_budget": 0.75
        })
        assert create_res.status_code == 201
        proj = create_res.json()
        proj_id = proj["id"]
        assert proj["name"] == "پروژه تستی"
        assert proj["path"] == str(project_dir)

        # List projects
        list_res = await client.get("/projects")
        assert list_res.status_code == 200
        assert any(p["id"] == proj_id for p in list_res.json())

        # Get project detail
        detail_res = await client.get(f"/projects/{proj_id}")
        assert detail_res.status_code == 200
        d_data = detail_res.json()
        assert d_data["folder"]["exists"] is True
        assert len(d_data["tasks"]) == 0

        # Update project
        update_res = await client.patch(f"/projects/{proj_id}", json={"name": "پروژه ویرایش‌شده"})
        assert update_res.status_code == 200
        assert update_res.json()["name"] == "پروژه ویرایش‌شده"


def test_project_snapshot_prioritizes_source_and_skips_hidden_cache(tmp_path):
    from flux.api.app import build_project_context

    project_dir = tmp_path / "source_project"
    (project_dir / "src").mkdir(parents=True)
    (project_dir / ".pytest_cache").mkdir()
    (project_dir / "src" / "main.py").write_text("print('real source')", encoding="utf-8")
    (project_dir / ".pytest_cache" / "README.md").write_text("cache only", encoding="utf-8")
    snapshot = build_project_context({"name": "Source", "path": str(project_dir)})

    assert snapshot is not None
    assert "src/main.py" in snapshot["content"]
    assert "real source" in snapshot["content"]
    assert "cache only" not in snapshot["content"]


@pytest.mark.asyncio
async def test_project_task_creation_and_execution(engine, fake_provider, tmp_path):
    fake_provider.delay_seconds = 0.01
    project_dir = tmp_path / "workspace_alpha"
    project_dir.mkdir()
    (project_dir / "index.html").write_text("<h1>Alpha</h1>", encoding="utf-8")

    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        # Create project
        proj = (await client.post("/projects", json={
            "name": "Alpha App",
            "path": str(project_dir),
            "description": "پروژه آلفا"
        })).json()

        # Add task to project
        task_res = await client.post(f"/projects/{proj['id']}/tasks", json={
            "title": "پیاده‌سازی بخش ورود",
            "objective": "ساخت صفحهٔ ورود با اعتبارسنجی کاربر",
            "acceptance_criteria": ["فرم ورودی ایمیل و رمزعبور", "بررسی معتبر بودن ورودی‌ها"],
            "budget_cap_usd": 0.5,
            "priority": "P1",
            "workflow": "team"
        })
        assert task_res.status_code == 201
        task_data = task_res.json()
        task_id = task_data["id"]
        assert task_data["status"] == "PENDING"
        assert len(task_data["acceptance_criteria"]) == 2

        # Run task
        run_res = await client.post(f"/projects/{proj['id']}/tasks/{task_id}/run")
        assert run_res.status_code == 200
        run_info = run_res.json()
        assert run_info["task_id"] == task_id
        assert run_info["status"] == "RUNNING"
        run_id = run_info["run_id"]

        # Wait for execution to finish
        for _ in range(100):
            if not app.state.jobs:
                break
            await asyncio.sleep(0.02)

        # Check run detail
        detail = (await client.get(f"/runs/{run_id}")).json()
        assert detail["status"] in ("ACCEPT_CANDIDATE", "COMPLETED")
        assert any("folder:" in c["ref"] for c in detail["task"]["context"])
        folder_context = next(c for c in detail["task"]["context"] if c["ref"].startswith("folder:"))
        assert "index.html" in folder_context["content"]
        assert "<h1>Alpha</h1>" in folder_context["content"]
        assert str(project_dir) in detail["task"]["allowed_paths"]

        # Check task list
        tasks = (await client.get(f"/projects/{proj['id']}/tasks")).json()
        assert len(tasks) == 1
        assert tasks[0]["last_run_id"] == run_id
        assert tasks[0]["status"] == "ACCEPT_CANDIDATE"

        assert (await client.post(f"/runs/{run_id}/accept")).status_code == 200
        tasks = (await client.get(f"/projects/{proj['id']}/tasks")).json()
        assert tasks[0]["status"] == "COMPLETED"

        # Delete task
        del_task = await client.delete(f"/projects/{proj['id']}/tasks/{task_id}")
        assert del_task.status_code == 200

        # Delete project
        del_proj = await client.delete(f"/projects/{proj['id']}")
        assert del_proj.status_code == 200
