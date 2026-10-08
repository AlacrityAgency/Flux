"""Current navigation and shared project/memory data regression checks, offline."""
from html.parser import HTMLParser

import pytest
from httpx import ASGITransport, AsyncClient

from flux.api.app import create_app


class Navigation(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = {}
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.elements[attributes["id"]] = (tag, attributes)
        if tag == "script":
            self.scripts.append(attributes.get("src"))


@pytest.mark.asyncio
async def test_current_workspace_navigation_keeps_legacy_explicit(engine):
    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        current = await client.get("/chat")
        navigation = Navigation()
        navigation.feed(current.text)
        tag, attrs = navigation.elements["project-memory-button"]
        assert tag == "button" and "href" not in attrs
        assert attrs["aria-controls"] == "project-memory-dialog"
        assert navigation.elements["project-memory-dialog"][0] == "dialog"
        assert "/static/project-memory.js" in navigation.scripts
        assert (await client.get("/static/project-memory.js")).status_code == 200
        legacy = await client.get("/legacy")
        assert legacy.status_code == 200 and "/static/app.js" in legacy.text


@pytest.mark.asyncio
async def test_current_project_edits_preserve_existing_tasks_and_budget(engine, tmp_path):
    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        project = (await client.post("/projects", json={
            "name": "پروژهٔ قبلی", "path": str(tmp_path),
            "default_budget": 1.25, "default_criteria": "معیار قدیمی حفظ شود",
        })).json()
        task = (await client.post(f"/projects/{project['id']}/tasks", json={
            "title": "تسک قبلی", "objective": "تسک قبلی باید حفظ شود",
        })).json()
        edited = await client.patch(f"/projects/{project['id']}", json={
            "name": "نام تازه", "path": str(tmp_path), "description": "توضیح تازه",
        })
        assert edited.status_code == 200
        assert edited.json()["default_budget"] == 1.25
        assert edited.json()["default_criteria"] == "معیار قدیمی حفظ شود"
        await client.patch(f"/projects/{project['id']}", json={"archived": True})
        assert (await client.get("/projects")).json() == []
        archived = (await client.get("/projects?archived=true")).json()
        assert archived[0]["id"] == project["id"] and archived[0]["archived"] == 1
        await client.patch(f"/projects/{project['id']}", json={"archived": False})
        restored = (await client.get(f"/projects/{project['id']}")).json()
        assert restored["tasks"][0]["id"] == task["id"]
        assert restored["name"] == "نام تازه"


@pytest.mark.asyncio
async def test_memory_panel_changes_take_effect_in_existing_retrieval(engine):
    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        memory = (await client.post("/memories", json={
            "title": "قاعدهٔ پروژه", "content": "حافظه تستی مشترک پروژه", "enabled": False,
        })).json()
        assert app.state.workspace.retrieve("حافظه تستی") == []
        enabled = await client.put(f"/memories/{memory['id']}", json={
            "title": "قاعدهٔ تازه", "content": "حافظه تستی به روز شد", "enabled": True,
        })
        assert enabled.status_code == 200 and enabled.json()["revision"] == 2
        refs = app.state.workspace.retrieve("حافظه تستی")
        assert refs[0]["ref"] == memory["id"] and refs[0]["revision"] == 2
        assert len((await client.get("/memories", params={"q": "تستي"})).json()) == 1
        assert (await client.delete(f"/memories/{memory['id']}")).status_code == 200
        assert app.state.workspace.retrieve("حافظه تستی") == []
        assert (await client.get("/memories")).json() == []
