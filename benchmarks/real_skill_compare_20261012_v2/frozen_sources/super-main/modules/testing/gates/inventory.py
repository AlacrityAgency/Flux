#!/usr/bin/env python3
"""testing.inventory (informational): what the project is made of and how it is tested today.

Detects layers (frontend / backend), frameworks, test runners, test files, coverage and API
specs, then recommends a test-portfolio shape (pyramid, trophy or honeycomb) for step T2 of
the evaluation algorithm. Writes <project>/.superagent/testing/inventory.json.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testlib  # noqa: E402
from gatekit import base_parser, emit, make_finding, project_root, report, work_dir  # noqa: E402


GATE = "testing.inventory"
FRONTEND_DEPS = {"react", "vue", "svelte", "@angular/core", "next", "nuxt", "solid-js", "preact", "@sveltejs/kit", "astro", "electron", "lit", "alpinejs", "htmx.org"}
LOGIC_EXT = {".py", ".go", ".rs", ".java", ".kt", ".cs", ".rb", ".php"}
BACKEND_JS_DEPS = {"express", "fastify", "koa", "@nestjs/core", "hapi", "@hapi/hapi", "hono", "apollo-server", "@trpc/server"}
BACKEND_PY = ("django", "flask", "fastapi", "starlette", "aiohttp", "tornado", "sanic", "litestar")
DB_HINTS = ("prisma", "typeorm", "sequelize", "mongoose", "knex", "drizzle", "sqlalchemy", "psycopg", "pymongo", "redis", "django")
OPENAPI_NAMES = re.compile(r"^(openapi|swagger)[\w.-]*\.(json|ya?ml)$", re.I)


def detect(project: Path) -> dict:
    pkg = testlib.package_json(project)
    deps = testlib.js_deps(pkg)
    pyreq = testlib.python_requirements(project)
    for manifest in testlib.iter_project_files(project, {".json", ".toml", ".txt", ".cfg"}):
        if len(manifest.relative_to(project).parts) > 5:
            continue
        if manifest.name == "package.json":
            deps.update(testlib.js_deps(testlib.read_json(manifest)))
        elif manifest.name in {"pyproject.toml", "requirements.txt", "setup.cfg"} and manifest.parent != project:
            pyreq += "\n" + testlib.python_requirements(manifest.parent)
    sources = testlib.source_files(project)
    tests = testlib.test_files(project)
    languages = Counter(p.suffix for p in sources)

    frontend = sorted(d for d in deps if d in FRONTEND_DEPS)
    backend = sorted(d for d in deps if d in BACKEND_JS_DEPS) + [b for b in BACKEND_PY if re.search(rf"\b{b}\b", pyreq)]
    if (project / "go.mod").is_file():
        backend.append("go")
    databases = sorted({h for h in DB_HINTS if h in deps or h in pyreq})

    compose_services = 0
    for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
        path = project / name
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            block = re.search(r"^services:\s*\n((?:[ \t]+.*\n?)*)", text, re.M)
            if block:
                compose_services = len(re.findall(r"^[ \t]{2}[\w.-]+:\s*$", block.group(1), re.M))
    service_manifests = [p for p in project.glob("*/package.json")] + [p for p in project.glob("services/*/package.json")]

    openapi = [str(p.relative_to(project)) for p in testlib.iter_project_files(project, {".json", ".yaml", ".yml"}) if OPENAPI_NAMES.match(p.name)]
    runners = testlib.detect_suites(project)
    e2e = testlib.e2e_runner(project)
    coverage = [str(p.relative_to(project)) for p in testlib.find_coverage_reports(project)]

    # UI without a framework dependency: Electron apps and plain HTML pages with their own scripts.
    package_manifests = [project / "package.json"] + list(project.glob("*/package.json"))
    electron = any("electron" in testlib.js_deps(testlib.read_json(m)) for m in package_manifests if m.is_file())
    html_pages = [p for p in testlib.iter_project_files(project, {".html", ".htm"}) if not testlib.is_test_file(p.relative_to(project))]
    plain_web_ui = len(html_pages) >= 1 and (languages.get(".js", 0) + languages.get(".mjs", 0) + languages.get(".ts", 0)) > 0
    logic_files = sum(count for ext, count in languages.items() if ext in LOGIC_EXT)

    layers = []
    if frontend or electron or plain_web_ui or any(s in languages for s in (".jsx", ".tsx", ".vue", ".svelte")):
        layers.append("frontend")
    if backend or databases:
        layers.append("backend")
    if logic_files and "backend" not in layers:
        layers.append("core-logic")
    if not layers and sources:
        layers.append("library")

    microservices = compose_services >= 3 or len(service_manifests) >= 3
    if microservices:
        shape = "honeycomb"
        why = "Several deployable services: most risk sits in service interactions, so favour integration and contract tests over isolated unit tests."
    elif "frontend" in layers and ("backend" in layers or "core-logic" in layers):
        shape = "pyramid+trophy"
        why = ("UI plus substantial non-UI code: use a pyramid for the core/backend logic (many unit tests, fewer integration tests) "
               "and a trophy for the UI (component integration tests, accessibility and interaction gates, few E2E on critical flows).")
    elif "frontend" in layers:
        shape = "trophy"
        why = "UI-centric app: static analysis plus integration-level component tests give the best confidence per cost; few E2E tests on critical flows."
    else:
        shape = "pyramid"
        why = "Backend or library code: many fast unit tests on logic, fewer integration tests on real I/O (DB, HTTP), a thin E2E layer."

    return {
        "layers": layers,
        "languages": dict(languages.most_common()),
        "frontend_frameworks": frontend,
        "backend_frameworks": backend,
        "databases": databases,
        "services": {"compose_services": compose_services, "package_manifests": len(service_manifests), "microservices": microservices},
        "ui": {"electron": electron, "html_pages": len(html_pages), "framework": frontend},
        "test_runners": runners,
        "e2e_runner": e2e,
        "test_file_count": len(tests),
        "source_file_count": len(sources),
        "test_to_source_ratio": round(len(tests) / len(sources), 2) if sources else None,
        "coverage_reports": coverage,
        "openapi_specs": openapi,
        "ci": sorted(str(p.relative_to(project)) for p in (project / ".github" / "workflows").glob("*.y*ml")) if (project / ".github" / "workflows").is_dir() else [],
        "recommended_shape": {"shape": shape, "reason": why},
    }


def main():
    args = base_parser("Inventory the project's stack and current tests").parse_args()
    project = project_root(args.project)
    inventory = detect(project)
    out = work_dir(project, "testing") / "inventory.json"
    out.write_text(json.dumps(inventory, indent=2), encoding="utf-8")

    findings = []
    if inventory["source_file_count"] and not inventory["test_file_count"]:
        findings.append(make_finding(1, "testing", GATE, "no-automated-tests", "P1",
                                     f"{inventory['source_file_count']} source files, 0 test files",
                                     {"layers": inventory["layers"]}, "Regressions can ship unnoticed.",
                                     "Start with tests for the highest-risk modules from testing.risk.", confidence="suspected"))
    if "backend" in inventory["layers"] and inventory["openapi_specs"] == [] and inventory["backend_frameworks"]:
        findings.append(make_finding(len(findings) + 1, "testing", GATE, "no-api-contract", "P3",
                                     "backend framework detected but no OpenAPI/Swagger spec",
                                     {"backend": inventory["backend_frameworks"]},
                                     "API behaviour cannot be checked against a contract (testing.api).",
                                     "Generate or write an OpenAPI spec for the public API.", confidence="suspected"))
    metrics = {
        "layers": ", ".join(inventory["layers"]) or "unknown",
        "runners": ", ".join(r["name"] for r in inventory["test_runners"]) or "none",
        "e2e": inventory["e2e_runner"] or "none",
        "test_files": inventory["test_file_count"],
        "source_files": inventory["source_file_count"],
        "recommended_shape": inventory["recommended_shape"]["shape"],
    }
    return emit(report(GATE, "PASS", str(project), findings, [inventory["recommended_shape"]["reason"]], metrics, {"inventory": str(out)}), args.json)


if __name__ == "__main__":
    sys.exit(main())
