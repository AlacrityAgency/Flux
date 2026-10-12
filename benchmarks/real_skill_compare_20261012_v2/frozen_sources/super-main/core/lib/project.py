"""Project-owned configuration and feature-based verification requirements."""

import json
from pathlib import Path
from gatekit import is_within

MODES = ("design", "build", "change", "audit", "test", "release-check")
PROFILES = {
    "site": {"ui"},
    "web-app": {"ui", "api", "data", "auth"},
    "saas": {"ui", "api", "data", "auth", "tenancy"},
    "commerce": {"ui", "api", "data", "auth", "payments", "jobs"},
    "service": {"api"},
}
FEATURE_GATES = {
    "ui": ["ui-ux.journey"],
    "api": ["backend.behavior", "testing.api"],
    "data": ["data.integration"],
    "auth": ["security.authorization"],
    "tenancy": ["security.authorization"],
    "payments": ["backend.idempotency"],
    "jobs": ["backend.idempotency"],
}
COMMAND_GATES = {
    "ui-ux.journey", "backend.behavior", "backend.idempotency", "data.integration", "data.restore",
    "security.authorization", "security.dast", "operations.resilience", "operations.load",
    "delivery.build", "delivery.rollback",
    "product.research", "product.content", "product.ux", "product.integrations", "product.seo",
}
SCANNER_GATES = {"security.sast", "security.dependencies"}
KNOWN_GATES = COMMAND_GATES | SCANNER_GATES | {"testing.api"}
PRODUCT_AREAS = {"research", "ux", "ui", "content", "frontend", "backend", "data", "security",
                 "integrations", "accessibility", "performance", "delivery", "seo-analytics"}


def load_config(project):
    path = Path(project) / "superagent.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("superagent.json must be an object with version: 1")
    if "profile" in data and (not isinstance(data["profile"], str) or data["profile"] not in PROFILES):
        raise ValueError("Unknown project profile")
    agent = data.get("agent", {})
    if not isinstance(agent, dict) or set(agent) - {"provider", "model", "reasoning"} or any(not isinstance(value, str) or not value or len(value) > 256 for value in agent.values()):
        raise ValueError("agent accepts short provider/model/reasoning strings only")
    features = data.get("features", [])
    if not isinstance(features, list) or any(not isinstance(f, str) or f not in FEATURE_GATES for f in features):
        raise ValueError("features must be a list of supported feature names")
    if not isinstance(data.get("environment", "local"), str) or data.get("environment", "local") not in {"local", "test", "staging", "production"}:
        raise ValueError("Unknown environment")
    checks = data.get("checks", {})
    if not isinstance(checks, dict):
        raise ValueError("checks must be an object")
    for name, check in checks.items():
        if name not in KNOWN_GATES or not isinstance(check, dict):
            raise ValueError("Unknown or malformed project check: " + name)
        if name in COMMAND_GATES:
            argv = check.get("command")
            if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or not x for x in argv):
                raise ValueError(name + " command must be a nonempty argv array")
            expected = check.get("expected")
            if not isinstance(expected, list) or not expected or any(not isinstance(x, str) or not x for x in expected) or len(set(expected)) != len(expected):
                raise ValueError(name + " requires unique expected scenario names")
            if check.get("format", "checks") not in {"checks", "k6"}:
                raise ValueError(name + " has an unsupported report format")
            if check.get("format") == "k6" and name != "operations.load":
                raise ValueError("k6 reports belong to operations.load")
        if "timeout" in check and (type(check["timeout"]) is not int or not 1 <= check["timeout"] <= 1800):
            raise ValueError(name + " timeout must be an integer in 1..1800")
    acceptance = data.get("acceptance", [])
    if not isinstance(acceptance, list):
        raise ValueError("acceptance must be a list")
    ids = set()
    for row in acceptance:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"] or row["id"] in ids:
            raise ValueError("acceptance items need unique nonempty ids")
        ids.add(row["id"])
        if not isinstance(row.get("criterion"), str) or not row["criterion"].strip():
            raise ValueError("acceptance criterion must describe observable behaviour")
        if not isinstance(row.get("gate"), str) or row["gate"] not in COMMAND_GATES or not isinstance(row.get("scenario"), str) or not row["scenario"]:
            raise ValueError("acceptance must map to a gate and named scenario")
        if row["gate"] in COMMAND_GATES and row["scenario"] not in checks.get(row["gate"], {}).get("expected", []):
            raise ValueError("acceptance scenario must appear in the gate's expected scenarios")
        trace = row.get("trace", {})
        if not isinstance(trace, dict) or set(trace) - {"design", "content", "code", "tests"}:
            raise ValueError("acceptance.trace supports design/content/code/tests")
        for kind, reference in trace.items():
            if not isinstance(reference, dict) or set(reference) != {"applicable", "reason", "paths"} or type(reference.get("applicable")) is not bool or not isinstance(reference.get("reason"), str) or not reference["reason"].strip() or not isinstance(reference.get("paths"), list):
                raise ValueError("Trace items require applicable, reason and paths")
            if reference["applicable"] and not reference["paths"]:
                raise ValueError("Applicable trace items require artifact paths")
            for rel in reference["paths"]:
                if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts or not is_within(Path(project) / rel, Path(project)):
                    raise ValueError("Trace artifacts must stay inside the project")
    sources = data.get("sources", {})
    if not isinstance(sources, dict) or set(sources) - {"active", "reference", "generated", "entrypoints"}:
        raise ValueError("sources supports active/reference/generated/entrypoints")
    for paths in sources.values():
        if not isinstance(paths, list):
            raise ValueError("Source roots must be lists")
        for value in paths:
            if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts or not is_within(Path(project) / value, Path(project)):
                raise ValueError("Source paths must remain inside the project")
    testing = data.get("testing", {})
    if not isinstance(testing, dict) or set(testing) - {"repeat", "suites", "static_workers"}:
        raise ValueError("testing supports repeat, suites and static_workers")
    if "static_workers" in testing and (type(testing["static_workers"]) is not int or not 1 <= testing["static_workers"] <= 4):
        raise ValueError("testing.static_workers must be an integer in 1..4")
    if "repeat" in testing and (type(testing["repeat"]) is not int or not 1 <= testing["repeat"] <= 5):
        raise ValueError("testing.repeat must be an integer in 1..5")
    if "suites" in testing:
        if not isinstance(testing["suites"], list) or not testing["suites"]:
            raise ValueError("testing.suites must be a nonempty list")
        seen_suites = set()
        for suite in testing["suites"]:
            if not isinstance(suite, dict) or set(suite) != {"name", "cwd"} or suite.get("name") not in {"vitest", "jest", "node-test", "mocha", "npm-test", "pytest", "unittest", "go", "playwright"}:
                raise ValueError("Each suite requires a supported name and relative cwd")
            cwd = suite["cwd"]
            if not isinstance(cwd, str) or Path(cwd).is_absolute() or ".." in Path(cwd).parts or not is_within(Path(project) / cwd, Path(project)):
                raise ValueError("Suite cwd escapes the project")
            key = (suite["name"], cwd)
            if key in seen_suites:
                raise ValueError("Duplicate test suite")
            seen_suites.add(key)
    if "product" in data:
        product = data["product"]
        if not isinstance(product, dict) or set(product) != {"areas"} or not isinstance(product["areas"], dict) or set(product["areas"]) != PRODUCT_AREAS:
            raise ValueError("product.areas must classify every product area")
        for name, area in product["areas"].items():
            if not isinstance(area, dict) or type(area.get("applicable")) is not bool:
                raise ValueError(name + " needs an applicable boolean")
            if not isinstance(area.get("reason"), str) or not area["reason"].strip():
                raise ValueError(name + " needs an applicability reason")
            criteria = area.get("criteria", [])
            if not isinstance(criteria, list) or any(not isinstance(c, str) or c not in ids for c in criteria) or len(set(criteria)) != len(criteria):
                raise ValueError(name + " criteria must reference unique acceptance ids")
            if area["applicable"] and not criteria:
                raise ValueError(name + " needs mapped acceptance criteria")
            if not area["applicable"] and criteria:
                raise ValueError(name + " cannot be inapplicable with mapped criteria")
    return data


def requirements(config, inventory, mode="audit", profile=None, depth="standard"):
    selected = profile or config.get("profile")
    features = set(PROFILES.get(selected, set())) | set(config.get("features", []))
    if "frontend" in inventory["layers"]:
        features.add("ui")
    if "backend" in inventory["layers"] or inventory["openapi_specs"]:
        features.add("api")
    if inventory.get("databases"):
        features.add("data")
    gates = set()
    # A feature profile keeps sensitive checks required even in quick mode.
    for feature in features:
        gates.update(FEATURE_GATES[feature])
    gates.update(config.get("checks", {}))
    gates.update(row["gate"] for row in config.get("acceptance", []))
    if features and depth != "quick":
        gates.update(SCANNER_GATES)
    if mode in {"build", "change", "release-check"}:
        gates.add("delivery.build")
    if config.get("product") or mode in {"build", "release-check"}:
        gates.add("product.coverage")
    if mode == "release-check":
        gates.update(SCANNER_GATES | {"operations.resilience", "delivery.rollback"})
        if "data" in features:
            gates.add("data.restore")
        if "api" in features:
            gates.add("operations.load")
    return selected or "detected", sorted(features), sorted(gates)
