"""Small, explicit git helpers. Every call is argv-based (no shell) and bounded by a timeout."""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "Flux", "GIT_AUTHOR_EMAIL": "flux@localhost",
    "GIT_COMMITTER_NAME": "Flux", "GIT_COMMITTER_EMAIL": "flux@localhost",
}


class GitError(RuntimeError):
    pass


def _flags():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def git(cwd, *args, env=None, input=None, timeout=60, check=True) -> str:
    """Run git and return stdout (text). Raises GitError with stderr on failure."""
    full_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C", **(env or {})}
    try:
        proc = subprocess.run(["git", "-c", "core.quotePath=false", *args], cwd=str(cwd), env=full_env, input=input,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, **_flags())
    except FileNotFoundError as exc:
        raise GitError("git پیدا نشد؛ آن را نصب کنید.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git {' '.join(args[:2])} timed out") from exc
    if check and proc.returncode != 0:
        raise GitError((proc.stderr or proc.stdout or f"git {args[0]} failed").strip()[-2000:])
    return proc.stdout


def git_ok(cwd, *args, **kw) -> tuple[int, str, str]:
    full_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C", **(kw.pop("env", None) or {})}
    proc = subprocess.run(["git", "-c", "core.quotePath=false", *args], cwd=str(cwd), env=full_env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=kw.pop("timeout", 60), **_flags())
    return proc.returncode, proc.stdout, proc.stderr


def repo_root(path) -> Path:
    return Path(git(path, "rev-parse", "--show-toplevel").strip()).resolve()


def common_dir(path) -> Path:
    out = git(path, "rev-parse", "--git-common-dir").strip()
    p = Path(out)
    return (Path(path) / p).resolve() if not p.is_absolute() else p.resolve()


def head(path) -> str:
    return git(path, "rev-parse", "HEAD").strip()


def is_repo(path) -> bool:
    try:
        return git_ok(path, "rev-parse", "--is-inside-work-tree")[0] == 0
    except (OSError, subprocess.SubprocessError):
        return False


def version() -> tuple[int, ...]:
    out = git(".", "--version")
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", out)
    return tuple(int(x or 0) for x in match.groups()) if match else (0, 0, 0)


def snapshot_commit(path, base: str | None = None) -> str:
    """Commit object for the current working tree (tracked + untracked, honoring .gitignore).

    Uses a throw-away index so the real index, HEAD and refs are never modified.
    """
    parent = base or head(path)
    fd, index = tempfile.mkstemp(prefix="flux-index-")
    os.close(fd)
    os.unlink(index)  # git must create it itself
    env = {"GIT_INDEX_FILE": index, **GIT_IDENTITY}
    try:
        git(path, "read-tree", parent, env=env)
        git(path, "add", "-A", "--", ".", env=env, timeout=180)
        tree = git(path, "write-tree", env=env).strip()
        return git(path, "commit-tree", tree, "-p", parent, "-m", "flux snapshot", env=env).strip()
    finally:
        try:
            os.unlink(index)
        except OSError:
            pass


def merge_conflicts(path, ours: str, theirs: str) -> list[str] | None:
    """Files that would conflict when merging two commits (no working-tree change).

    Returns None when the installed git cannot answer (older than 2.38).
    """
    if version() < (2, 38):
        return None
    code, out, err = git_ok(path, "merge-tree", "--write-tree", "--name-only", "--no-messages", ours, theirs, timeout=120)
    if code == 0:
        return []
    if code == 1:
        lines = [l.strip() for l in out.splitlines()[1:] if l.strip()]
        return sorted(set(lines))
    raise GitError(err.strip()[-1000:] or "merge-tree failed")


HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def changed_ranges(path, base: str) -> dict[str, list[tuple[int, int]]]:
    """Old-side (base) line ranges touched in the working tree relative to ``base``.

    Pure insertions are represented as a one-line range at the insertion point. New
    untracked files are reported with an empty range list (whole file).
    """
    out = git(path, "diff", "-U0", "--no-color", "--no-ext-diff", "--find-renames", base, "--", timeout=180)
    result: dict[str, list[tuple[int, int]]] = {}
    current = old = None
    for line in out.splitlines():
        if line.startswith("diff --git "):
            current = old = None
        elif line.startswith("--- ") and current is None:
            name = line[4:]
            old = None if name == "/dev/null" else name[2:] if name.startswith("a/") else name
        elif line.startswith("+++ ") and current is None:
            name = line[4:]
            current = old if name == "/dev/null" else name[2:] if name.startswith("b/") else name
            if current is not None:
                result.setdefault(current, [])
        elif current is not None:
            match = HUNK.match(line)
            if match:
                start, count = int(match.group(1)), int(match.group(2) or 1)
                result[current].append((max(start, 1), max(start, 1) + max(count, 1) - 1))
    for name in git(path, "ls-files", "--others", "--exclude-standard").splitlines():
        if name.strip():
            result.setdefault(name.strip(), [])
    return result


def numstat(path, base: str) -> dict[str, tuple[int, int]]:
    stats: dict[str, tuple[int, int]] = {}
    out = git(path, "diff", "--numstat", "--no-color", "--find-renames", base, "--", timeout=180)
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            added = int(parts[0]) if parts[0].isdigit() else 0
            removed = int(parts[1]) if parts[1].isdigit() else 0
            name = parts[-1]
            if " => " in name:  # rename notation: a/{x => y}/b or x => y
                name = re.sub(r"\{[^{}]* => ([^{}]*)\}", r"\1", name)
                name = name.split(" => ")[-1]
            stats[name.replace("//", "/")] = (added, removed)
    root = Path(path)
    for name in git(path, "ls-files", "--others", "--exclude-standard").splitlines():
        name = name.strip()
        if name and name not in stats:
            try:
                with open(root / name, "rb") as handle:
                    data = handle.read(2_000_000)
                stats[name] = (0 if b"\0" in data else data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0), 0)
            except OSError:
                stats[name] = (0, 0)
    return stats
