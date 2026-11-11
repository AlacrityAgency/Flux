"""Isolated agent workspaces: git worktree + unique ports + shared dependency links + private data.

Git worktrees isolate files only. This module adds the rest of the environment so that
several agents can run dev servers, tests and databases at the same time:

* every worktree receives free, reserved TCP ports through environment variables;
* heavy dependency directories are linked (junction/symlink) from the main checkout when
  their lockfile is identical, instead of being reinstalled per worktree;
* each worktree has its own data directory, SQLite URL and Docker Compose project name,
  and optionally an ephemeral Postgres container on tmpfs.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import time
import uuid
from pathlib import Path

from flux.parallel import config as project_config
from flux.parallel.gitops import GitError, common_dir, git, repo_root
from flux.storage.workspace import now

RUNTIME_DIR = ".flux/runtime"


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.").lower()
    return value[:40] or "wt-" + uuid.uuid4().hex[:6]


def make_link(source: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        import _winapi  # junctions need no admin rights, unlike symlinks
        _winapi.CreateJunction(str(source), str(target))
    else:
        os.symlink(str(source), str(target), target_is_directory=True)


def is_link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(path))


def remove_link(path: Path) -> bool:
    """Remove only the link itself; the shared target is never traversed."""
    if hasattr(os.path, "isjunction") and os.path.isjunction(path):
        os.rmdir(path)
        return True
    if path.is_symlink():
        os.unlink(path)
        return True
    return False


def _same_file(a: Path, b: Path) -> bool:
    if a.is_file() != b.is_file():
        return False
    return not a.is_file() or a.read_bytes() == b.read_bytes()


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


class DockerCLI:
    """Minimal Docker wrapper; replaced by a fake in tests."""

    def available(self) -> bool:
        if not shutil.which("docker"):
            return False
        try:
            return subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True,
                                  timeout=8).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def run_postgres(self, name, image, port, password) -> str:
        out = subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-e", f"POSTGRES_PASSWORD={password}",
                              "-e", "POSTGRES_DB=app", "-p", f"127.0.0.1:{port}:5432",
                              "--tmpfs", "/var/lib/postgresql/data:rw", image],
                             capture_output=True, text=True, timeout=120)
        if out.returncode != 0:
            raise RuntimeError(out.stderr.strip()[-800:] or "docker run failed")
        container = out.stdout.strip()
        for _ in range(60):
            ready = subprocess.run(["docker", "exec", name, "pg_isready", "-U", "postgres"], capture_output=True, timeout=10)
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        return container

    def remove(self, name):
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=60)


class WorktreeManager:
    def __init__(self, repo, workspace, events=None, root: str | None = None, docker=None):
        self.repo, self.workspace, self.conn, self.events = repo, workspace, repo.conn, events
        self.root_override = root or os.environ.get("FLUX_WORKTREE_ROOT")
        self.docker = docker or DockerCLI()
        with self.repo._lock, self.conn:
            self.conn.executescript('''
                CREATE TABLE IF NOT EXISTS parallel_worktrees (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL, branch TEXT NOT NULL,
                    path TEXT NOT NULL, main_path TEXT NOT NULL, base_commit TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'active', scope TEXT NOT NULL DEFAULT '[]',
                    env TEXT NOT NULL DEFAULT '{}', links TEXT NOT NULL DEFAULT '[]',
                    services TEXT NOT NULL DEFAULT '[]', setup TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS parallel_ports (
                    port INTEGER PRIMARY KEY, worktree_id TEXT NOT NULL, name TEXT NOT NULL);
            ''')

    # ---------- queries ----------
    def _row(self, row):
        if not row:
            return None
        item = dict(row)
        for key in ("scope", "env", "links", "services", "setup"):
            item[key] = json.loads(item[key])
        item["ports"] = {r["name"]: r["port"] for r in self.conn.execute(
            "SELECT name,port FROM parallel_ports WHERE worktree_id=? ORDER BY name", (item["id"],))}
        return item

    def get(self, ident):
        item = self._row(self.conn.execute("SELECT * FROM parallel_worktrees WHERE id=?", (ident,)).fetchone())
        if not item:
            raise KeyError(ident)
        return item

    def list(self, project_id=None, include_removed=False):
        sql, args = "SELECT * FROM parallel_worktrees WHERE 1=1", []
        if project_id:
            sql += " AND project_id=?"; args.append(project_id)
        if not include_removed:
            sql += " AND state='active'"
        return [self._row(r) for r in self.conn.execute(sql + " ORDER BY created_at", args)]

    def env(self, ident) -> dict:
        return dict(self.get(ident)["env"])

    def by_path(self, path):
        resolved = str(Path(path).resolve())
        for item in self.list():
            if str(Path(item["path"]).resolve()) == resolved:
                return item
        return None

    # ---------- creation ----------
    def _root_for(self, main: Path) -> Path:
        if self.root_override:
            return Path(self.root_override).expanduser().resolve() / main.name
        return main.parent / f"{main.name}.worktrees"

    def _reserve_ports(self, ident, names, port_range):
        low, high = int(port_range[0]), int(port_range[1])
        taken = {r[0] for r in self.conn.execute("SELECT port FROM parallel_ports")}
        assigned = {}
        candidate = low + secrets.randbelow(max(1, high - low))
        for name in names:
            for _ in range(high - low + 1):
                candidate = low if candidate > high else candidate
                if candidate not in taken and port_is_free(candidate):
                    self.conn.execute("INSERT INTO parallel_ports VALUES (?,?,?)", (candidate, ident, name))
                    taken.add(candidate)
                    assigned[name] = candidate
                    candidate += 1
                    break
                candidate += 1
            else:
                raise RuntimeError("پورت آزاد در بازهٔ تعیین‌شده پیدا نشد.")
        return assigned

    def _exclude(self, main: Path, patterns):
        exclude = common_dir(main) / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        existing = exclude.read_text(encoding="utf-8").splitlines() if exclude.is_file() else []
        missing = [p for p in patterns if p not in existing]
        if missing:
            with open(exclude, "a", encoding="utf-8") as handle:
                if existing and existing[-1].strip():
                    handle.write("\n")
                handle.write("# added by Flux parallel worktrees\n" + "\n".join(missing) + "\n")

    def _share_dependencies(self, main: Path, path: Path, names):
        results = []
        for name in names:
            source, target = main / name, path / name
            if not source.is_dir() or is_link(source):
                continue
            if target.exists() or is_link(target):
                results.append({"name": name, "status": "present"})
                continue
            locks = project_config.LOCKFILES.get(name, [])
            differing = [lock for lock in locks if not _same_file(main / Path(name).parent / lock, path / Path(name).parent / lock)]
            if differing:
                results.append({"name": name, "status": "skipped", "reason": "lockfile differs: " + ", ".join(differing)})
                continue
            try:
                make_link(source, target)
                results.append({"name": name, "status": "linked", "source": str(source), "locks": locks})
            except OSError as exc:
                results.append({"name": name, "status": "failed", "reason": str(exc)})
        return results

    def create(self, project_id, name="", base="HEAD", scope=(), run_setup=True):
        project = self.workspace.get_project(project_id)
        if not project or project["archived"]:
            raise ValueError("پروژهٔ فعال پیدا نشد.")
        try:
            main = repo_root(project["path"])
        except GitError as exc:
            raise ValueError("پوشهٔ پروژه مخزن git نیست؛ worktree فقط برای مخزن git ساخته می‌شود.") from exc
        cfg = project_config.load(main)
        iso = cfg["isolation"]
        slug = _slug(name or "agent-" + uuid.uuid4().hex[:6])
        root = self._root_for(main)
        if (root / slug).exists() or self.conn.execute(
                "SELECT 1 FROM parallel_worktrees WHERE path=? AND state='active'", (str(root / slug),)).fetchone():
            slug = f"{slug}-{uuid.uuid4().hex[:4]}"
        branch, path = f"flux/{slug}", root / slug
        base_commit = git(main, "rev-parse", "--verify", f"{base}^{{commit}}").strip()
        ident = "wt_" + uuid.uuid4().hex[:12]
        root.mkdir(parents=True, exist_ok=True)
        git(main, "worktree", "add", "-b", branch, str(path), base_commit, timeout=300)
        links, services = [], []
        try:
            linked_names = [l for l in iso["link"] if (main / l).is_dir()]
            copied = []
            for item in iso["copy"]:
                if (main / item).is_file() and not (path / item).exists():
                    (path / item).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(main / item, path / item)
                    copied.append(item)
            self._exclude(main, [f"/{RUNTIME_DIR}/"] + [f"/{n}" for n in linked_names] + [f"/{c}" for c in copied])
            links = self._share_dependencies(main, path, iso["link"])
            data_dir = path / RUNTIME_DIR / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            with self.repo._lock, self.conn:
                port_names = list(dict.fromkeys(iso["ports"] + (["POSTGRES_PORT"] if iso["database"] == "postgres" else [])))
                ports = self._reserve_ports(ident, port_names, iso["port_range"])
            env = {"FLUX_WORKTREE_ID": ident, "FLUX_WORKTREE_NAME": slug, "FLUX_WORKTREE_PATH": str(path),
                   "FLUX_DATA_DIR": str(data_dir),
                   "COMPOSE_PROJECT_NAME": "flux_" + re.sub(r"[^a-z0-9_]", "_", slug.lower()),
                   **{k: str(v) for k, v in ports.items()}}
            database = iso["database"]
            if database == "postgres":
                if self.docker.available():
                    container = f"flux-pg-{re.sub(r'[^a-z0-9-]', '-', slug)}-{uuid.uuid4().hex[:4]}"
                    password = secrets.token_urlsafe(18)
                    self.docker.run_postgres(container, iso["postgres_image"], ports["POSTGRES_PORT"], password)
                    services.append({"kind": "postgres", "container": container, "port": ports["POSTGRES_PORT"]})
                    env["DATABASE_URL"] = f"postgresql://postgres:{password}@127.0.0.1:{ports['POSTGRES_PORT']}/app"
                else:
                    services.append({"kind": "postgres", "status": "unavailable", "fallback": "sqlite",
                                     "reason": "Docker در دسترس نیست"})
                    database = "sqlite"
            if database == "sqlite":
                sqlite_path = data_dir / "app.db"
                env["FLUX_SQLITE_PATH"] = str(sqlite_path)
                env.setdefault("DATABASE_URL", "sqlite:///" + sqlite_path.as_posix())
            (path / RUNTIME_DIR / "env").write_text("".join(f"{k}={v}\n" for k, v in env.items()), encoding="utf-8")
            (path / RUNTIME_DIR / "env.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
            setup = []
            if run_setup:
                for command in iso["setup"]:
                    setup.append(self._run_setup(path, env, command))
            ts = now()
            with self.repo._lock, self.conn:
                self.conn.execute("INSERT INTO parallel_worktrees VALUES (?,?,?,?,?,?,?,'active',?,?,?,?,?,?,?)",
                                  (ident, project_id, slug, branch, str(path), str(main), base_commit,
                                   json.dumps(list(scope)), json.dumps(env), json.dumps(links + [{"name": c, "status": "copied"} for c in copied]),
                                   json.dumps(services), json.dumps(setup), ts, ts))
        except Exception:
            self._teardown(main, path, branch, links, services, ident, delete_branch=True)
            raise
        item = self.get(ident)
        if self.events:
            self.events.publish("worktree.created", {"id": ident, "project_id": project_id, "name": slug})
        return item

    @staticmethod
    def _run_setup(path, env, command):
        started = time.monotonic()
        try:
            proc = subprocess.run(command, shell=True, cwd=str(path), env={**os.environ, **env}, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", timeout=900)
            return {"command": command, "code": proc.returncode, "seconds": round(time.monotonic() - started, 2),
                    "output": (proc.stdout + proc.stderr)[-4000:]}
        except subprocess.TimeoutExpired:
            return {"command": command, "code": -1, "seconds": 900, "output": "timeout"}

    # ---------- maintenance ----------
    def link_health(self, ident):
        """Detect shared dependency links whose lockfile has since diverged in the worktree."""
        item = self.get(ident)
        main, path, stale = Path(item["main_path"]), Path(item["path"]), []
        for link in item["links"]:
            if link.get("status") != "linked":
                continue
            differing = [l for l in link.get("locks", []) if not _same_file(main / Path(link["name"]).parent / l,
                                                                              path / Path(link["name"]).parent / l)]
            if differing:
                stale.append({"name": link["name"], "locks": differing})
        return stale

    def unshare(self, ident, name):
        """Replace a shared dependency link by nothing, so the agent can install privately."""
        item = self.get(ident)
        target = Path(item["path"]) / name
        if not remove_link(target):
            raise ValueError("این مسیر لینک اشتراکی نیست.")
        links = [{**l, "status": "unshared"} if l["name"] == name else l for l in item["links"]]
        with self.repo._lock, self.conn:
            self.conn.execute("UPDATE parallel_worktrees SET links=?,updated_at=? WHERE id=?", (json.dumps(links), now(), ident))
        return self.get(ident)

    def _teardown(self, main, path, branch, links, services, ident, delete_branch):
        for service in services:
            if service.get("container"):
                try:
                    self.docker.remove(service["container"])
                except Exception:
                    pass
        for link in links:
            if link.get("status") == "linked":
                try:
                    remove_link(Path(path) / link["name"])
                except OSError:
                    pass
        # Never let git recurse into a shared directory: refuse if any link survived.
        for link in links:
            if link.get("status") == "linked" and is_link(Path(path) / link["name"]):
                raise RuntimeError(f"لینک اشتراکی {link['name']} حذف نشد؛ حذف worktree متوقف شد.")
        if Path(path).exists():
            git(main, "worktree", "remove", "--force", str(path), check=False, timeout=300)
        git(main, "worktree", "prune", check=False)
        if delete_branch:
            git(main, "branch", "-D", branch, check=False)
        with self.repo._lock, self.conn:
            self.conn.execute("DELETE FROM parallel_ports WHERE worktree_id=?", (ident,))

    def remove(self, ident, delete_branch=False, active_check=None):
        item = self.get(ident)
        if item["state"] != "active":
            return item
        if active_check and active_check(ident):
            raise RuntimeError("یک عامل هنوز در این worktree در حال اجراست؛ ابتدا آن را متوقف کنید.")
        self._teardown(item["main_path"], item["path"], item["branch"], item["links"], item["services"], ident, delete_branch)
        with self.repo._lock, self.conn:
            self.conn.execute("UPDATE parallel_worktrees SET state='removed',updated_at=? WHERE id=?", (now(), ident))
        if self.events:
            self.events.publish("worktree.removed", {"id": ident})
        return self.get(ident)

    def commit_all(self, ident, message):
        """Commit everything in the worktree on its own branch; returns the new HEAD (or None if clean)."""
        path = self.get(ident)["path"]
        from flux.parallel.gitops import GIT_IDENTITY
        git(path, "add", "-A", timeout=300)
        if not git(path, "status", "--porcelain").strip():
            return None
        configured = git(path, "config", "user.email", check=False).strip()
        git(path, "commit", "-m", message, "--no-verify", env=None if configured else GIT_IDENTITY, timeout=300)
        return git(path, "rev-parse", "HEAD").strip()
