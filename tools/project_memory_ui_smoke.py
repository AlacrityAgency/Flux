"""Offline browser regression for the current project/memory panel.

Run with .venv-ui/Scripts/python.exe -X utf8 tools/project_memory_ui_smoke.py.
Only a loopback fixture server and fixture data are used; no model or user DB.
"""
import argparse
import json
import mimetypes
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright, expect


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/flux/static"
PROJECT_PATH = str(ROOT)
projects = [{"id": "prior-project", "name": "پروژه قبلی", "path": PROJECT_PATH,
             "description": "<img src=x onerror=alert(1)>", "archived": 0,
             "default_budget": 1.25, "default_criteria": "preserved", "task_count": 2}]
memories = [{"id": "prior-memory", "title": "حافظه تستی", "content": "<img src=x onerror=alert(1)>",
             "enabled": 1, "revision": 1}]
requests = []
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--screenshots", type=Path)
args = parser.parse_args()
if args.screenshots:
    args.screenshots.mkdir(parents=True, exist_ok=True)


class FixtureServer(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, content, code=200, content_type="application/json"):
        body = json.dumps(content, ensure_ascii=False).encode() if content_type == "application/json" else content
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/":
            return self.reply((STATIC / "local.html").read_bytes(), content_type="text/html; charset=utf-8")
        if path.startswith("/static/"):
            target = (STATIC / path.removeprefix("/static/")).resolve()
            if target.is_relative_to(STATIC) and target.is_file():
                return self.reply(target.read_bytes(), content_type=mimetypes.guess_type(target)[0] or "application/octet-stream")
        if path == "/api/local/status":
            return self.reply({"default_cwd": PROJECT_PATH, "models": {"codex": [], "claude": []},
                               "providers": [{"id": item, "authenticated": True, "installed": True,
                                              "version": "fixture", "detail": "ready"}
                                             for item in ("codex", "claude", "antigravity", "notebooklm")]})
        if path == "/api/local/usage":
            return self.reply({"providers": []})
        if path == "/api/local/chats":
            return self.reply([])
        if path == "/api/local/notebooks":
            return self.reply({"notebooks": [{"id": "fixture-book", "title": "دفتر آزمایش"}]})
        if path == "/projects":
            return self.reply(projects)
        if path == "/memories":
            return self.reply(memories)
        if path == "/filesystem/validate-path":
            supplied = parse_qs(parsed.query).get("path", [""])[0]
            return self.reply({"exists": supplied == PROJECT_PATH, "is_dir": supplied == PROJECT_PATH})
        self.reply({"detail": "Unknown fixture route"}, 404)

    def mutate(self):
        path = urlsplit(self.path).path
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        requests.append((self.command, path, payload))
        collection = projects if path.startswith("/projects") else memories if path.startswith("/memories") else None
        if collection is None:
            return self.reply({"detail": "No model calls are allowed in this check"}, 400)
        if self.command == "POST":
            item = {**payload, "id": f"fixture-{len(requests)}", "archived": 0, "revision": 1}
            collection.append(item)
            return self.reply(item, 201)
        item = next((row for row in collection if row["id"] == path.rsplit("/", 1)[-1]), None)
        if item is None:
            return self.reply({"detail": "Not found"}, 404)
        if self.command == "DELETE":
            collection.remove(item)
            return self.reply({"deleted": True})
        item.update(payload)
        if collection is memories:
            item["revision"] += 1
        self.reply(item)

    do_POST = mutate
    do_PATCH = mutate
    do_PUT = mutate
    do_DELETE = mutate


server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureServer)
worker = Thread(target=server.serve_forever, daemon=True)
worker.start()
errors = []
try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.emulate_media(reduced_motion="reduce")
        page.on("pageerror", lambda error: errors.append(str(error)))
        base = f"http://127.0.0.1:{server.server_port}/"
        page.goto(base)
        expect(page.locator("#folder-label")).to_have_text("Flux")
        page.locator("#project-memory-button").click()
        expect(page.locator("#project-memory-dialog")).to_be_visible()
        assert page.url == base
        expect(page.locator("#project-list .workspace-card")).to_have_count(1)
        assert page.locator("#project-list img").count() == 0
        assert page.locator(".workspace-legacy-link").get_attribute("href") == "/legacy"
        page.get_by_role("button", name="ویرایش پروژه", exact=True).click()
        page.locator("#project-name").fill("پروژه تازه")
        page.locator("#project-path").fill("missing-fixture-folder")
        page.locator("#project-form button[type=submit]").click()
        expect(page.locator("#project-edit-error")).to_be_visible()
        page.locator("#project-path").fill(PROJECT_PATH)
        page.locator("#project-form button[type=submit]").click()
        expect(page.locator("#project-editor")).not_to_be_visible()
        expect(page.locator("#project-list")).to_contain_text("پروژه تازه")
        assert projects[0]["default_budget"] == 1.25 and projects[0]["task_count"] == 2
        assert set(next(body for method, path, body in requests if method == "PATCH")) == {"name", "path", "description"}
        page.get_by_role("button", name="بایگانی پروژه", exact=True).click()
        expect(page.locator("#project-list .workspace-card")).to_have_count(0)
        page.locator("#include-archived-projects").check()
        page.get_by_role("button", name="بازگرداندن پروژه", exact=True).click()
        expect(page.locator("#project-list")).to_contain_text("فعال")
        page.locator("#add-project").click()
        page.locator("#project-name").fill("پروژه دوم")
        page.locator("#project-form button[type=submit]").click()
        expect(page.locator("#project-list .workspace-card")).to_have_count(2)
        page.locator("#workspace-search").fill("دوم")
        expect(page.locator("#project-list .workspace-card")).to_have_count(1)
        page.locator("#workspace-search").fill("")
        page.locator("#memories-tab").click()
        expect(page.locator("#memories-panel")).to_be_visible()
        assert page.locator("#memory-list img").count() == 0
        page.locator("#workspace-search").fill("تستي")
        expect(page.locator("#memory-list .workspace-card")).to_have_count(1)
        page.locator("#workspace-search").fill("")
        page.locator("#add-memory").click()
        page.locator("#memory-title").fill("قاعده جدید")
        page.locator("#memory-content").fill("یادداشت دقیق جدید")
        page.locator("#memory-enabled").uncheck()
        page.locator("#memory-form button[type=submit]").click()
        expect(page.locator("#memory-list .workspace-card")).to_have_count(2)
        new_card = page.locator("#memory-list .workspace-card").filter(has_text="قاعده جدید")
        expect(new_card).to_contain_text("غیرفعال")
        new_card.get_by_role("button", name="ویرایش یادداشت", exact=True).click()
        page.locator("#memory-content").fill("یادداشت اصلاح شده")
        page.locator("#memory-enabled").check()
        page.locator("#memory-form button[type=submit]").click()
        expect(new_card).to_contain_text("یادداشت اصلاح شده")
        expect(new_card).to_contain_text("نسخهٔ ۲")
        new_card.get_by_role("button", name="حذف یادداشت", exact=True).click()
        page.locator('[data-close="workspace-confirm"]').click()
        expect(page.locator("#memory-list .workspace-card")).to_have_count(2)
        new_card.get_by_role("button", name="حذف یادداشت", exact=True).click()
        page.locator("#workspace-confirm-form button[type=submit]").click()
        expect(page.locator("#memory-list .workspace-card")).to_have_count(1)
        page.locator("#projects-tab").click()
        page.evaluate("state.chat={id:'running-fixture',turns:[{state:'running'}]};renderWorkspace()")
        expect(page.get_by_role("button", name="گفتگوی تازه در این پروژه", exact=True).first).to_be_disabled()
        page.evaluate("state.chat=null;renderWorkspace()")
        page.locator('[data-close="project-memory-dialog"]').click()
        page.locator("#prompt").fill("پیش نویس حفظ شود")
        page.locator("#provider-toggle").click()
        page.locator('[data-provider="notebooklm"]').click()
        page.locator("#project-memory-button").click()
        page.get_by_role("button", name="گفتگوی تازه در این پروژه", exact=True).first.click()
        expect(page.locator("#project-memory-dialog")).not_to_be_visible()
        expect(page.locator("#prompt")).to_have_value("پیش نویس حفظ شود")
        expect(page.locator("#provider-label")).to_have_text("Codex")
        expect(page.locator("#folder-label")).to_have_text("Flux")
        assert page.url == base
        for width in (375, 768, 1024, 1440):
            page.set_viewport_size({"width": width, "height": 900})
            if width <= 850:
                page.locator("#menu-button").click()
            page.locator("#project-memory-button").click()
            expect(page.locator("#project-memory-dialog")).to_be_visible()
            page.locator("#projects-tab").click()
            expect(page.locator("#projects-panel")).to_be_visible()
            box = page.locator("#project-memory-dialog").bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= width, (width, box)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
            if args.screenshots and width in (375, 1440):
                page.screenshot(path=str(args.screenshots / f"projects-{width}.png"), full_page=True)
            page.locator("#memories-tab").click()
            expect(page.locator("#memories-panel")).to_be_visible()
            if args.screenshots and width in (375, 1440):
                page.screenshot(path=str(args.screenshots / f"memories-{width}.png"), full_page=True)
            page.locator("#add-memory").click()
            page.keyboard.press("Escape")
            expect(page.locator("#memory-editor")).not_to_be_visible()
            expect(page.locator("#project-memory-dialog")).to_be_visible()
            page.keyboard.press("Escape")
            expect(page.locator("#project-memory-dialog")).not_to_be_visible()
        assert not errors, errors
        browser.close()
finally:
    server.shutdown()
    server.server_close()
print(json.dumps({"page_errors": errors, "responsive_widths": [375, 768, 1024, 1440],
                  "crud_requests": len(requests), "model_calls": 0, "user_database_access": False}, ensure_ascii=False))
