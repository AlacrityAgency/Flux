"""Shadow Git Checkpoints (Cline-style Zero-Interference Snapshots).

Maintains a private bare-style shadow git directory per workspace under Flux's own
data root (never touching the project's ``.git`` index, commits, branches, or stashes).
Captures instant pre-turn and post-turn snapshots so any bad edit or runaway loop
can be rolled back with a single click or API call.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

from flux.storage.workspace import now

SHADOW_EXCLUDES = [
    ".git/",
    ".git",
    "node_modules/",
    ".venv/",
    ".venv*/",
    "venv/",
    "__pycache__/",
    "*.pyc",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".flux-worktree/",
    "dist/",
    "build/",
    "target/",
    ".next/",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
]


def _default_shadow_root() -> Path:
    custom = os.environ.get("FLUX_SHADOW_ROOT")
    if custom:
        return Path(custom).expanduser().resolve()
    return (Path.home() / ".flux" / "shadow-git").resolve()


class ShadowCheckpoints:
    def __init__(self, repo, shadow_root: str | Path | None = None):
        self.repo, self.conn = repo, repo.conn
        self.shadow_root = Path(shadow_root).resolve() if shadow_root else _default_shadow_root()
        with self.repo._lock, self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS shadow_checkpoints (
                    id TEXT PRIMARY KEY,
                    cwd TEXT NOT NULL,
                    chat_id TEXT NOT NULL DEFAULT '',
                    turn_id TEXT NOT NULL DEFAULT '',
                    stage TEXT NOT NULL DEFAULT 'manual',
                    label TEXT NOT NULL DEFAULT '',
                    commit_sha TEXT NOT NULL,
                    files_changed TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_shadow_cp_cwd ON shadow_checkpoints(cwd, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_shadow_cp_chat ON shadow_checkpoints(chat_id, created_at DESC);
                """
            )

    def _shadow_dir(self, cwd: str | Path) -> Path:
        norm = str(Path(cwd).resolve()).lower()
        digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
        return self.shadow_root / digest

    def _git(self, cwd: Path, shadow_dir: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        env = {
            **os.environ,
            "GIT_DIR": str(shadow_dir),
            "GIT_WORK_TREE": str(cwd),
            "GIT_AUTHOR_NAME": "Flux Shadow",
            "GIT_AUTHOR_EMAIL": "shadow@flux.local",
            "GIT_COMMITTER_NAME": "Flux Shadow",
            "GIT_COMMITTER_EMAIL": "shadow@flux.local",
            "GIT_TERMINAL_PROMPT": "0",
        }
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        proc = subprocess.run(
            ["git", "-c", "core.quotePath=false", "-c", "core.autocrlf=false", *args],
            cwd=str(cwd), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, **flags,
        )
        if check and proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout).strip() or f"shadow git failed: {args}")
        return proc

    def _ensure_repo(self, cwd: Path) -> Path:
        shadow_dir = self._shadow_dir(cwd)
        if not (shadow_dir / "HEAD").is_file():
            shadow_dir.mkdir(parents=True, exist_ok=True)
            clean_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            clean_env["GIT_TERMINAL_PROMPT"] = "0"
            flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
            subprocess.run(
                ["git", "init", "--bare", str(shadow_dir)],
                env=clean_env, check=True, capture_output=True, text=True, timeout=30, **flags,
            )
            subprocess.run(
                ["git", "--git-dir", str(shadow_dir), "config", "core.bare", "false"],
                env=clean_env, check=True, capture_output=True, text=True, timeout=15, **flags,
            )
            subprocess.run(
                ["git", "--git-dir", str(shadow_dir), "config", "gc.auto", "0"],
                env=clean_env, check=True, capture_output=True, text=True, timeout=15, **flags,
            )
        excl = shadow_dir / "info" / "exclude"
        excl.parent.mkdir(parents=True, exist_ok=True)
        excl.write_text("\n".join(SHADOW_EXCLUDES) + "\n", encoding="utf-8")
        return shadow_dir

    def _has_head(self, cwd: Path, shadow_dir: Path) -> bool:
        return self._git(cwd, shadow_dir, "rev-parse", "--verify", "HEAD", check=False).returncode == 0

    def changed_since(self, cwd: str | Path, commit_sha: str) -> list[str]:
        """List workspace files changed or created relative to ``commit_sha`` in the shadow repo."""
        root = Path(cwd).resolve()
        shadow_dir = self._ensure_repo(root)
        tracked = self._git(root, shadow_dir, "diff", "--name-only", commit_sha, check=False).stdout.splitlines()
        untracked = self._git(root, shadow_dir, "ls-files", "--others", "--exclude-standard", check=False).stdout.splitlines()
        return sorted({p.strip() for p in (*tracked, *untracked) if p.strip()})

    def capture(self, cwd: str | Path, chat_id: str = "", turn_id: str = "", stage: str = "manual", label: str = "") -> dict:
        root = Path(cwd).resolve()
        if not root.is_dir():
            raise ValueError("پوشهٔ کاری برای ثبت چک‌پوینت وجود ندارد.")
        shadow_dir = self._ensure_repo(root)
        prev_head = self._git(root, shadow_dir, "rev-parse", "--verify", "HEAD", check=False).stdout.strip() if self._has_head(root, shadow_dir) else ""
        self._git(root, shadow_dir, "add", "-A")
        tree_sha = self._git(root, shadow_dir, "write-tree").stdout.strip()

        reuse = False
        if prev_head:
            prev_tree = self._git(root, shadow_dir, "rev-parse", f"{prev_head}^{{tree}}", check=False).stdout.strip()
            reuse = prev_tree == tree_sha

        if reuse:
            commit_sha = prev_head
            changed = []
        else:
            msg = label or f"flux checkpoint ({stage})"
            args = ["commit-tree", tree_sha, "-m", msg]
            if prev_head:
                args[2:2] = ["-p", prev_head]
            commit_sha = self._git(root, shadow_dir, *args).stdout.strip()
            self._git(root, shadow_dir, "update-ref", "HEAD", commit_sha)
            if prev_head:
                changed = [
                    p.strip() for p in self._git(root, shadow_dir, "diff-tree", "--no-commit-id", "--name-only", "-r", prev_head, commit_sha).stdout.splitlines()
                    if p.strip()
                ]
            else:
                changed = []

        ident = "cp_" + uuid.uuid4().hex[:12]
        ts = now()
        with self.repo._lock, self.conn:
            self.conn.execute(
                "INSERT INTO shadow_checkpoints (id, cwd, chat_id, turn_id, stage, label, commit_sha, files_changed, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (ident, str(root), chat_id, turn_id, stage, label or stage, commit_sha, json.dumps(changed, ensure_ascii=False), ts),
            )
        return self.get(ident)

    def get(self, ident: str) -> dict:
        row = self.conn.execute("SELECT * FROM shadow_checkpoints WHERE id=?", (ident,)).fetchone()
        if not row:
            raise KeyError(ident)
        data = dict(row)
        data["files_changed"] = json.loads(data["files_changed"] or "[]")
        return data

    def list(self, cwd: str | None = None, chat_id: str | None = None, limit: int = 50) -> list[dict]:
        clauses, params = [], []
        if cwd:
            clauses.append("cwd=?")
            params.append(str(Path(cwd).resolve()))
        if chat_id:
            clauses.append("chat_id=?")
            params.append(chat_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self.conn.execute(
            f"SELECT id FROM shadow_checkpoints {where} ORDER BY created_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [self.get(r[0]) for r in rows]

    def diff(self, ident: str, max_chars: int = 50_000) -> dict:
        cp = self.get(ident)
        root = Path(cp["cwd"])
        shadow_dir = self._ensure_repo(root)
        # Stage current tree into a temporary index to diff cleanly including untracked files
        with tempfile.TemporaryDirectory(prefix="flux-cp-diff-") as tmp:
            idx = Path(tmp) / "index"
            env = {**os.environ, "GIT_DIR": str(shadow_dir), "GIT_WORK_TREE": str(root), "GIT_INDEX_FILE": str(idx)}
            flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
            subprocess.run(["git", "read-tree", cp["commit_sha"]], cwd=str(root), env=env, capture_output=True, timeout=20, **flags)
            subprocess.run(["git", "add", "-A"], cwd=str(root), env=env, capture_output=True, timeout=30, **flags)
            res = subprocess.run(
                ["git", "-c", "core.quotePath=false", "diff", "--cached", "--no-color", cp["commit_sha"]],
                cwd=str(root), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, **flags,
            )
        patch = res.stdout or ""
        return {
            "checkpoint_id": ident,
            "commit_sha": cp["commit_sha"],
            "files": self.changed_since(root, cp["commit_sha"]),
            "patch": patch[:max_chars],
            "truncated": len(patch) > max_chars,
        }

    def restore(self, ident: str, create_backup: bool = True) -> dict:
        """Roll the workspace cleanly back to ``ident`` without touching ``.git`` or ignored dirs."""
        cp = self.get(ident)
        root = Path(cp["cwd"])
        if not root.is_dir():
            raise ValueError("پوشهٔ کاری دیگر وجود ندارد.")
        shadow_dir = self._ensure_repo(root)
        backup = None
        if create_backup:
            backup = self.capture(root, cp["chat_id"], cp["turn_id"], stage="pre_restore_backup", label=f"backup before {ident}")
        # Determine files present now (tracked in shadow HEAD + untracked non-ignored) vs target checkpoint
        target_files = set(
            p.strip() for p in self._git(root, shadow_dir, "ls-tree", "-r", "--name-only", cp["commit_sha"]).stdout.splitlines() if p.strip()
        )
        current_untracked = set(
            p.strip() for p in self._git(root, shadow_dir, "ls-files", "--others", "--exclude-standard", check=False).stdout.splitlines() if p.strip()
        )
        current_tracked = set(
            p.strip() for p in self._git(root, shadow_dir, "ls-tree", "-r", "--name-only", "HEAD", check=False).stdout.splitlines() if p.strip()
        )
        extras = (current_tracked | current_untracked) - target_files

        # Restore all files in target commit
        self._git(root, shadow_dir, "read-tree", "--reset", "-u", cp["commit_sha"])
        self._git(root, shadow_dir, "checkout-index", "-f", "-a")
        self._git(root, shadow_dir, "update-ref", "HEAD", cp["commit_sha"])

        removed = []
        for rel in sorted(extras):
            victim = (root / rel).resolve()
            try:
                victim.relative_to(root)
            except ValueError:
                continue
            if ".git" in victim.parts:
                continue
            if victim.is_file() or victim.is_symlink():
                victim.unlink(missing_ok=True)
                removed.append(rel)

        return {
            "restored": True,
            "checkpoint": cp,
            "removed_extra_files": removed,
            "backup_checkpoint_id": backup["id"] if backup else None,
        }
