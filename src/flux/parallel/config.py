"""Per-project parallel-work settings, versioned in ``<project>/.flux/flux.json``.

Every key is optional; defaults are chosen so a plain repository works unchanged.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

DEFAULTS = {
    "isolation": {
        # Heavy, reproducible directories shared from the main checkout instead of reinstalled.
        # A link is only made when the relevant lockfile is byte-identical in both checkouts.
        "link": ["node_modules", ".venv", "venv", ".pnpm-store", ".yarn/cache", ".gradle", ".turbo", ".next/cache"],
        # Small untracked configuration copied (never linked) so each worktree may override it.
        "copy": [".env", ".env.local", ".env.development.local", ".env.test.local"],
        # Environment variable names that receive a unique free port per worktree.
        "ports": ["PORT", "API_PORT", "VITE_PORT", "E2E_PORT"],
        "port_range": [20000, 29999],
        # sqlite | postgres | none. "postgres" needs Docker and falls back to sqlite otherwise.
        "database": "sqlite",
        "postgres_image": "postgres:16-alpine",
        # Optional commands run once inside a fresh worktree (e.g. "pnpm install --offline").
        "setup": [],
    },
    "coordination": {
        # defer: start the turn later when it collides with a running agent; warn: notify only.
        "policy": "defer",
        "defer_on": ["conflict", "symbol"],
        "scan_seconds": 20,
    },
    "memory": {
        # Lessons emitted by agents are proposals until approved, unless this is true.
        "auto_verify": False,
        "pinned_budget_chars": 4000,
    },
    "parallel": {"max_agents": 3},
}

LOCKFILES = {
    "node_modules": ["pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lockb", "bun.lock", "package.json"],
    ".pnpm-store": ["pnpm-lock.yaml"],
    ".yarn/cache": ["yarn.lock"],
    ".venv": ["uv.lock", "poetry.lock", "requirements.txt", "requirements-dev.txt", "pyproject.toml", "Pipfile.lock"],
    "venv": ["uv.lock", "poetry.lock", "requirements.txt", "requirements-dev.txt", "pyproject.toml", "Pipfile.lock"],
    ".gradle": ["build.gradle", "build.gradle.kts", "settings.gradle", "gradle.lockfile"],
}


def _merge(base, extra):
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def load(project_path) -> dict:
    data = copy.deepcopy(DEFAULTS)
    path = Path(project_path) / ".flux" / "flux.json"
    if path.is_file():
        try:
            _merge(data, json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            raise ValueError(f"خواندن {path} ناموفق بود: {exc}") from exc
    if data["coordination"]["policy"] not in {"defer", "warn", "off"}:
        raise ValueError("coordination.policy must be defer, warn or off")
    if data["isolation"]["database"] not in {"sqlite", "postgres", "none"}:
        raise ValueError("isolation.database must be sqlite, postgres or none")
    low, high = data["isolation"]["port_range"]
    if not (1024 <= int(low) < int(high) <= 65535):
        raise ValueError("isolation.port_range is invalid")
    return data

