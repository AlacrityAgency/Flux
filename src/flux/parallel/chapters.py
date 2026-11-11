"""Diff chapters: split a large change into ordered, reviewable chapters.

Review order follows how a reviewer reasons about a change: contracts and data first,
then the code that implements them, then tests that prove it, then docs and noise.
"""
from __future__ import annotations

import re
from pathlib import PurePosixPath

from flux.parallel.gitops import git, numstat

CHAPTERS = [
    ("dependencies", "وابستگی‌ها و پیکربندی ساخت", re.compile(
        r"(^|/)(package(-lock)?\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb?|requirements[^/]*\.txt|pyproject\.toml|"
        r"poetry\.lock|uv\.lock|Pipfile(\.lock)?|go\.(mod|sum)|Cargo\.(toml|lock)|Gemfile(\.lock)?|composer\.(json|lock)|"
        r"Dockerfile|docker-compose[^/]*\.ya?ml|\.github/|Makefile|tsconfig[^/]*\.json|vite\.config\.\w+|setup\.(py|cfg))$")),
    ("data", "داده، اسکیما و مهاجرت‌ها", re.compile(r"(^|/)(migrations?|schema|alembic|prisma|db)(/|\.)|\.sql$|schema\.\w+$")),
    ("contracts", "قراردادها و رابط‌ها (API/تایپ‌ها)", re.compile(
        r"(^|/)(api|contracts?|types?|interfaces?|routes?|proto|openapi)(/|\.)|\.d\.ts$|\.proto$|openapi\.\w+$")),
    ("tests", "آزمون‌ها", re.compile(r"(^|/)(tests?|__tests__|spec|e2e)/|(^|/)test_[^/]+$|[._-](test|spec)\.\w+$")),
    ("docs", "مستندات", re.compile(r"\.(md|mdx|rst|txt|adoc)$|(^|/)docs?/")),
    ("assets", "دارایی‌ها و فایل‌های تولیدی", re.compile(r"\.(png|jpe?g|gif|svg|ico|woff2?|ttf|pdf|lock|min\.js|map)$")),
]
ORDER = ["dependencies", "data", "contracts", "source", "tests", "docs", "assets"]


def classify(path: str) -> str:
    for key, _, pattern in CHAPTERS:
        if pattern.search(path):
            return key
    return "source"


def chapter_title(key: str, module: str = "") -> str:
    if key == "source":
        return f"پیاده‌سازی: {module}" if module else "پیاده‌سازی"
    return next(title for k, title, _ in CHAPTERS if k == key)


def _is_secret_env(name: str) -> bool:
    base = PurePosixPath(name).name.lower()
    return (base == ".env" or base.startswith(".env.")) and not base.endswith((".example", ".sample", ".template"))


def build_chapters(path: str, base: str, include_patch: bool = True, max_patch_chars: int = 60000) -> dict:
    stats = {k: v for k, v in numstat(path, base).items() if not _is_secret_env(k)}
    groups: dict[tuple, list] = {}
    for name, (added, removed) in stats.items():
        key = classify(name)
        parts = PurePosixPath(name).parts
        module = "/".join(parts[:2]) if key == "source" and len(parts) > 2 else (parts[0] if key == "source" and len(parts) > 1 else "")
        groups.setdefault((key, module), []).append({"path": name, "added": added, "removed": removed})
    chapters = []
    for (key, module), files in sorted(groups.items(), key=lambda g: (ORDER.index(g[0][0]), g[0][1])):
        files.sort(key=lambda f: (-(f["added"] + f["removed"]), f["path"]))
        chapter = {"key": key, "module": module, "title": chapter_title(key, module), "files": files,
                   "added": sum(f["added"] for f in files), "removed": sum(f["removed"] for f in files)}
        chapter["risk"] = "high" if key in {"data", "contracts", "dependencies"} else "low" if key in {"docs", "assets"} else "medium"
        chapters.append(chapter)
    if include_patch:
        budget = max_patch_chars
        for chapter in chapters:
            if chapter["key"] == "assets":
                continue
            names = [f["path"] for f in chapter["files"]]
            untracked = set(git(path, "ls-files", "--others", "--exclude-standard", "--", *names).split("\n")) - {""}
            patch = git(path, "diff", "--no-color", "--no-ext-diff", "--find-renames", base, "--", *names, timeout=180)
            for name in sorted(untracked):
                patch += git(path, "diff", "--no-index", "--no-color", "--", "/dev/null", name, check=False)
            chapter["patch"] = patch[:max(0, budget)]
            chapter["patch_truncated"] = len(patch) > budget
            budget -= len(chapter["patch"])
    total_added = sum(c["added"] for c in chapters)
    total_removed = sum(c["removed"] for c in chapters)
    return {"base": base, "files": len(stats), "added": total_added, "removed": total_removed, "chapters": chapters}
