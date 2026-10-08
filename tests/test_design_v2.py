import pytest
from httpx import ASGITransport, AsyncClient

from flux.api.app import create_app

PAGES = ["01-shell-home.html", "02-request-contract.html", "02-request-contract.js",
         "03-10-workspace.html", "03-10-workspace.js"]


@pytest.mark.asyncio
async def test_root_opens_workspace_and_design_pages_are_served(engine):
    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        root = await client.get("/", follow_redirects=False)
        assert root.status_code == 307 and root.headers["location"] == "/design-v2/01-shell-home.html"
        for page in PAGES:
            response = await client.get(f"/design-v2/{page}")
            assert response.status_code == 200, page
            assert "script-src 'self' 'unsafe-inline'" in response.headers["content-security-policy"]
        assert (await client.get("/design-v2/not-listed.html")).status_code == 404
        assert (await client.get("/design-v2/..%2Fapp.py")).status_code in (404, 422)


@pytest.mark.asyncio
async def test_every_page_loads_native_windows_behaviour(engine):
    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        for path in ("/chat", "/legacy", "/head", "/design-v2/01-shell-home.html",
                     "/design-v2/02-request-contract.html", "/design-v2/03-10-workspace.html"):
            response = await client.get(path)
            assert response.status_code == 200 and "/static/native.js" in response.text, path
        assert (await client.get("/static/native.js")).status_code == 200
        assert "fx-menu" in (await client.get("/static/native.css")).text


@pytest.mark.asyncio
async def test_head_uses_connected_frozen_provider_without_a_cli_spend_cap(engine, tmp_path):
    app = create_app(engine=engine)
    project = app.state.workspace.create_project('HEAD fixture', str(tmp_path))
    connected = False

    async def account_status(refresh=False):
        return {'providers': [{'id': 'codex', 'authenticated': connected}]}

    app.state.local_runtime.status = account_status
    payload = {
        'project_id': project['id'], 'request_key': 'head-provider-fixture',
        'objective': 'Prepare a short technical report', 'execution_provider': 'codex',
        'acceptance_criteria': [{'criterion_id': 'C1', 'text': 'Explain the design'}],
    }
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        head = (await client.get('/head')).text
        assert 'head-budget' not in head and 'head-reserve' not in head
        assert 'head-request-provider' in head
        rejected = await client.post('/api/core/tasks', json=payload)
        assert rejected.status_code == 409
        connected = True
        created = await client.post('/api/core/tasks', json=payload)
        assert created.status_code == 201
        task = created.json()
        assert task['contract']['execution_provider'] == 'codex'
        mismatch = await client.post(f"/api/core/tasks/{task['id']}/execute", json={
            'operation_key': 'mismatched-provider-fixture', 'provider': 'claude',
        })
        assert mismatch.status_code == 409


@pytest.mark.asyncio
async def test_no_gapgpt_api_connection_remains(engine):
    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert (await client.put("/api/local/connections/gapgpt-api", json={"api_key": "x" * 20})).status_code in (404, 405)
        assert (await client.post("/settings/api-key", json={"api_key": "x" * 20})).status_code in (404, 405)
        status = (await client.get("/api/local/status")).json()
        assert "gapgpt-api" not in [p["id"] for p in status["providers"]]
        assert any(p["id"] == "gapcode" for p in status["providers"])  # the GapCode account stays
        models = (await client.get("/models/status")).json()
        assert models["has_api_key"] is False and models["demo"] is True


@pytest.mark.asyncio
async def test_role_model_assignments_persist_and_validate(engine):
    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert (await client.get("/roles/models")).json() == {"roles": {}}
        roles = {"central": {"provider": "claude", "model": "opus"}, "developer": {"provider": "gapcode", "model": ""}}
        saved = await client.put("/roles/models", json={"roles": roles})
        assert saved.status_code == 200 and saved.json() == {"roles": roles}
        assert (await client.get("/roles/models")).json() == {"roles": roles}
        for bad in ({"x": {"provider": "gapgpt-api", "model": ""}},        # removed paid API
                    {"x": {"provider": "codex", "model": "a b;c"}},         # unsafe model id
                    {"X Y": {"provider": "codex", "model": ""}},            # bad role id
                    {"x": {"provider": "codex", "model": "m" * 101}}):
            assert (await client.put("/roles/models", json={"roles": bad})).status_code == 422
        assert (await client.get("/roles/models")).json() == {"roles": roles}  # rejected writes changed nothing


@pytest.mark.asyncio
async def test_chat_rename_archive_and_delete(engine, tmp_path):
    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        made = (await client.post("/api/local/chats", json={"title": "اول", "provider": "codex", "cwd": str(tmp_path)})).json()
        cid = made["id"]
        assert [c["id"] for c in (await client.get("/api/local/chats")).json()] == [cid]
        renamed = await client.patch(f"/api/local/chats/{cid}", json={"title": "نام تازه"})
        assert renamed.status_code == 200 and renamed.json()["title"] == "نام تازه"
        assert (await client.patch(f"/api/local/chats/{cid}", json={"title": "  "})).status_code == 422
        assert (await client.patch(f"/api/local/chats/{cid}", json={"archived": True})).json()["archived_at"]
        assert (await client.get("/api/local/chats")).json() == []                       # hidden by default
        assert [c["id"] for c in (await client.get("/api/local/chats?archived=only")).json()] == [cid]
        assert len((await client.get("/api/local/chats?archived=all")).json()) == 1
        assert (await client.get("/api/local/chats?archived=bogus")).status_code == 422
        assert (await client.patch(f"/api/local/chats/{cid}", json={"archived": False})).json()["archived_at"] == ""
        assert (await client.delete(f"/api/local/chats/{cid}")).json() == {"deleted": True, "id": cid}
        assert (await client.get(f"/api/local/chats/{cid}")).status_code == 404
        assert (await client.delete(f"/api/local/chats/{cid}")).status_code == 404


@pytest.mark.asyncio
async def test_workspace_pages_share_real_shell_without_prototype_leftovers(engine):
    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert (await client.get("/static/shell.js")).status_code == 200
        assert ".proj-row" in (await client.get("/static/shell.css")).text
        for page in ("01-shell-home.html", "02-request-contract.html", "03-10-workspace.html"):
            html = (await client.get(f"/design-v2/{page}")).text
            assert "/static/shell.js" in html, page
            assert 'class="proto"' not in html and "notes-dlg" not in html, page
            assert "پروژهٔ نمونه" not in html, page
        for script in ("02-request-contract.js", "03-10-workspace.js"):
            js = (await client.get(f"/design-v2/{script}")).text
            assert "notes-dlg" not in js and "دموی تعاملی" not in js, script
        home = (await client.get("/design-v2/01-shell-home.html")).text
        assert "طراحی می‌شود" not in home
        assert 'href="/head">ثبت درخواست واقعی' in home
        assert "تصمیم‌های آزمایشی نمایش داده نمی‌شوند" in home


@pytest.mark.asyncio
async def test_usage_summary_counts_turns_per_account(engine):
    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert (await client.get("/api/local/usage/summary")).json() == {"accounts": []}
        runtime = app.state.local_runtime if hasattr(app.state, "local_runtime") else None
        if runtime is None:
            return
        conn = runtime.conn
        conn.execute("INSERT INTO local_chats (id,title,provider,model,cwd,access,created_at,updated_at) VALUES ('c1','t','codex','','.', 'read','2026-01-01','2026-01-01')")
        conn.execute("INSERT INTO local_turns (id,chat_id,request_key,prompt,state,usage,created_at,updated_at) VALUES ('t1','c1','k1','p','completed',?, '2026-01-01','2026-01-01')",
                     ('{"input_tokens": 120, "cached_input_tokens": 20, "output_tokens": 30}',))
        conn.commit()
        acc = (await client.get("/api/local/usage/summary")).json()["accounts"][0]
        assert (acc["provider"], acc["turns"], acc["input_tokens"], acc["output_tokens"], acc["cached_tokens"], acc["chats"]) == ("codex", 1, 120, 30, 20, 1)


@pytest.mark.asyncio
async def test_chat_screen_renders_markdown_safely(engine):
    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert "/static/markdown.js" in (await client.get("/design-v2/03-10-workspace.html")).text
        js = (await client.get("/static/markdown.js")).text
        assert "fluxMarkdown" in js and "innerHTML" not in js
