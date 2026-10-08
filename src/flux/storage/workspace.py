"""Local conversation and memory storage. Existing engine tables are left intact."""
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: str, limit: int = 20000) -> str:
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"متن باید کمتر از {limit} نویسه باشد.")
    if re.search(r"sk-[A-Za-z0-9_-]{16,}|-----BEGIN .*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{30,}|(?:api_key|access_token|password)\s*[:=]\s*['\"][A-Za-z0-9_-]{16,}", value,re.I):
        raise ValueError("کلید یا اطلاعات محرمانه را وارد گفت‌وگو و حافظه نکنید.")
    return value


class Workspace:
    def __init__(self, repo):
        self.repo = repo
        self.conn = repo.conn
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS conversation_runs (
                run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
                conversation_id TEXT NOT NULL REFERENCES conversations(id));
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1, revision INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS acceptances (
                run_id TEXT PRIMARY KEY REFERENCES runs(run_id), content_hash TEXT NOT NULL,
                accepted_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '', default_criteria TEXT NOT NULL DEFAULT '',
                default_budget REAL NOT NULL DEFAULT 0.5, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS project_tasks (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                title TEXT NOT NULL, objective TEXT NOT NULL, acceptance_criteria TEXT NOT NULL,
                budget_cap_usd REAL NOT NULL DEFAULT 0.5, priority TEXT NOT NULL DEFAULT 'P1',
                workflow TEXT NOT NULL DEFAULT 'auto', status TEXT NOT NULL DEFAULT 'PENDING',
                last_run_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        ''')
        self.conn.commit()
        columns = {r[1] for r in self.conn.execute('PRAGMA table_info(memories)')}
        with self.repo._lock, self.conn:
            for name, definition in [('project_id', "TEXT NOT NULL DEFAULT ''"),
                                     ('status', "TEXT NOT NULL DEFAULT 'verified'"),
                                     ('provenance', "TEXT NOT NULL DEFAULT '[]'")]:
                if name not in columns:
                    self.conn.execute(f'ALTER TABLE memories ADD COLUMN {name} {definition}')
            self.conn.executescript('''
                CREATE TABLE IF NOT EXISTS memory_revisions (
                    id TEXT NOT NULL, revision INTEGER NOT NULL, project_id TEXT NOT NULL,
                    title TEXT NOT NULL, content TEXT NOT NULL, enabled INTEGER NOT NULL,
                    status TEXT NOT NULL, provenance TEXT NOT NULL, content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL, PRIMARY KEY(id,revision));
                CREATE TABLE IF NOT EXISTS memory_epochs (scope TEXT PRIMARY KEY, epoch INTEGER NOT NULL);
            ''')
            for row in self.conn.execute('SELECT * FROM memories').fetchall():
                self._record_memory_revision(dict(row))
        # Make pre-redesign runs visible in the new sidebar without changing their data.
        for row in self.conn.execute("SELECT run_id,task_payload,created_at FROM runs WHERE run_id NOT IN (SELECT run_id FROM conversation_runs)").fetchall():
            payload = json.loads(row["task_payload"])
            ident = "legacy_" + row["run_id"]
            self.conn.execute("INSERT OR IGNORE INTO conversations VALUES (?,?,?,?,0)",
                              (ident, str(payload.get("objective") or row["run_id"])[:160], row["created_at"], row["created_at"]))
            self.conn.execute("INSERT INTO conversation_runs VALUES (?,?)", (row["run_id"], ident))
        self.conn.commit()

    def conversations(self):
        return [dict(r) for r in self.conn.execute('''
            SELECT c.*, COUNT(cr.run_id) AS run_count FROM conversations c
            LEFT JOIN conversation_runs cr ON c.id=cr.conversation_id
            WHERE c.archived=0 GROUP BY c.id ORDER BY c.updated_at DESC
        ''')]

    def create_conversation(self, title):
        ident = "chat_" + uuid.uuid4().hex[:12]
        with self.repo._lock, self.conn:
            self.conn.execute("INSERT INTO conversations VALUES (?,?,?,?,0)",
                              (ident, clean_text(title, 160), now(), now()))
        return self.get_conversation(ident)

    def get_conversation(self, ident):
        r = self.conn.execute("SELECT * FROM conversations WHERE id=?", (ident,)).fetchone()
        return dict(r) if r else None

    def link_run(self, chat_id, run_id):
        with self.repo._lock, self.conn:
            self.conn.execute("INSERT OR IGNORE INTO conversation_runs VALUES (?,?)", (run_id, chat_id))
            self.conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now(), chat_id))

    def conversation_run_ids(self, ident):
        return [r[0] for r in self.conn.execute('''
            SELECT cr.run_id FROM conversation_runs cr JOIN runs r ON r.run_id=cr.run_id
            WHERE conversation_id=? ORDER BY r.created_at
        ''', (ident,))]

    def update_conversation(self, ident, title=None, archived=None):
        with self.repo._lock, self.conn:
            if title is not None:
                self.conn.execute("UPDATE conversations SET title=? WHERE id=?", (clean_text(title, 160), ident))
            if archived is not None:
                self.conn.execute("UPDATE conversations SET archived=? WHERE id=?", (int(archived), ident))
        return self.get_conversation(ident)

    def memories(self, query="", project_id=None, include_global=False):
        rows = [dict(r) for r in self.conn.execute("SELECT * FROM memories ORDER BY updated_at DESC")]
        if project_id is not None:
            rows = [r for r in rows if r['project_id'] == project_id or (include_global and r['project_id'] == '*')]
        rows = [r for r in rows if r['status'] != 'deleted']
        for row in rows:
            row['provenance'] = json.loads(row['provenance'])
        normalize = lambda s: s.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").lower()
        q = normalize(query.strip())
        return [r for r in rows if not q or q in normalize(r["title"] + " " + r["content"])]

    def _record_memory_revision(self, row):
        from flux.knowledge.retrieval import digest
        self.conn.execute('INSERT OR IGNORE INTO memory_revisions VALUES (?,?,?,?,?,?,?,?,?,?)',
                          (row['id'],row['revision'],row['project_id'],row['title'],row['content'],row['enabled'],row['status'],row['provenance'],digest(row['content']),now()))

    def memory_epoch(self, project_id=''):
        scopes = (project_id, '*') if project_id != '*' else ('*',)
        return ':'.join(str((self.conn.execute('SELECT epoch FROM memory_epochs WHERE scope=?',(scope,)).fetchone() or [0])[0]) for scope in scopes)

    def _invalidate_memory_sessions(self, project_id):
        self.conn.execute('INSERT INTO memory_epochs VALUES (?,1) ON CONFLICT(scope) DO UPDATE SET epoch=epoch+1',(project_id,))
        if self.conn.execute("SELECT 1 FROM sqlite_master WHERE name='local_chats'").fetchone():
            columns={r[1] for r in self.conn.execute('PRAGMA table_info(local_chats)')}
            if 'project_id' in columns:
                if project_id == '*':self.conn.execute('UPDATE local_chats SET session_id=NULL')
                else:self.conn.execute('UPDATE local_chats SET session_id=NULL WHERE project_id=?',(project_id,))

    def _memory_mutation_gate(self, scopes):
        if not self.conn.execute("SELECT 1 FROM sqlite_master WHERE name='local_chats'").fetchone():return
        if 'project_id' not in {r[1] for r in self.conn.execute('PRAGMA table_info(local_chats)')}:return
        active=self.conn.execute("SELECT c.project_id FROM local_turns t JOIN local_chats c ON c.id=t.chat_id WHERE t.state IN ('queued','running')").fetchall()
        if any('*' in scopes or r[0] in scopes for r in active):
            raise ValueError('ابتدا اجرای پروژه را متوقف یا تمام کنید؛ تغییر حافظهٔ در حال استفاده مجاز نیست.')

    def save_memory(self, title, content, enabled=True, ident=None, project_id=None, status='verified', provenance=None, expected_revision=None, emission_key=None):
        title, content = clean_text(title, 120), clean_text(content, 12000)
        if not title or not content:
            raise ValueError("عنوان و متن حافظه را وارد کنید.")
        if status not in {'verified','proposed','stale'}:raise ValueError('Invalid memory status.')
        with self.repo._lock, self.conn:
            emission_id=None
            if emission_key:
                emission_id='mem_'+hashlib.sha256(emission_key.encode()).hexdigest()[:24]
                prior=self.conn.execute('SELECT * FROM memories WHERE id=?',(emission_id,)).fetchone()
                if prior:
                    result=dict(prior);result['provenance']=json.loads(result['provenance']);return result
            old = self.conn.execute('SELECT * FROM memories WHERE id=?',(ident,)).fetchone() if ident else None
            if ident:
                if not old or old['status']=='deleted':
                    raise KeyError(ident)
                if expected_revision is not None and expected_revision != old['revision']:
                    raise ValueError('Memory revision changed; reload before editing.')
            scope=project_id if project_id is not None else old['project_id'] if old else ''
            if scope not in {'','*'} and (not self.get_project(scope) or self.get_project(scope)['archived']):
                raise ValueError('Active project required for memory.')
            self._memory_mutation_gate({scope,old['project_id'] if old else scope})
            refs = json.dumps(provenance if provenance is not None else json.loads(old['provenance']) if old else [],ensure_ascii=False)
            if old:
                # Proposed changes are separate records; they cannot hide a verified note.
                if status=='proposed' and old['status']=='verified':raise ValueError('Create a separate proposal instead of replacing verified memory.')
                self.conn.execute('''UPDATE memories SET title=?,content=?,enabled=?,project_id=?,status=?,provenance=?,
                    revision=revision+1,updated_at=? WHERE id=?''', (title, content, int(enabled),scope,status,refs,now(),ident))
            else:
                ident = emission_id or "mem_" + uuid.uuid4().hex[:12]
                self.conn.execute("INSERT INTO memories (id,title,content,enabled,revision,created_at,updated_at,project_id,status,provenance) VALUES (?,?,?,?,1,?,?,?,?,?)",
                                  (ident,title,content,int(enabled),now(),now(),scope,status,refs))
            row=dict(self.conn.execute('SELECT * FROM memories WHERE id=?',(ident,)).fetchone())
            self._record_memory_revision(row)
            for affected in {scope,old['project_id'] if old else scope}:self._invalidate_memory_sessions(affected)
        row['provenance']=json.loads(row['provenance'])
        return row

    def delete_memory(self, ident):
        with self.repo._lock, self.conn:
            row=self.conn.execute('SELECT * FROM memories WHERE id=?',(ident,)).fetchone()
            if not row or row['status']=='deleted':return False
            self._memory_mutation_gate({row['project_id']})
            self.conn.execute("UPDATE memories SET content='',enabled=0,status='deleted',revision=revision+1,updated_at=? WHERE id=?",(now(),ident))
            # Preserve lifecycle metadata and hashes, purge deleted source text.
            self.conn.execute("UPDATE memory_revisions SET content='' WHERE id=?",(ident,))
            self._record_memory_revision(dict(self.conn.execute('SELECT * FROM memories WHERE id=?',(ident,)).fetchone()))
            self._invalidate_memory_sessions(row['project_id'])
            return True

    def evidence_pack(self, objective, project_id='', criteria=(), budget=3000, include_sources=True):
        from flux.knowledge.retrieval import build_pack, digest
        records=[]
        if project_id not in {'','*'}:
            project=self.get_project(project_id)
            if not project or project['archived']:raise ValueError('Active project required.')
        for item in self.memories(project_id=project_id,include_global=True):
            records.append({**item,'ref':item['id'],'content_hash':digest(item['content']),'evidence_type':'approved_decision','source_ref':'human-memory'})
        if project_id and include_sources:
            from flux.knowledge.sources import SourceIndex
            records.extend(SourceIndex(self.repo,self).records(project_id))
        return build_pack(objective,list(criteria),records,budget)

    def retrieve(self, objective, limit=3000, project_id='', criteria=()):
        return self.evidence_pack(objective,project_id,criteria,limit)['evidence'][:12]

    def preferences(self):
        values = {"daily_budget": 5.0, "default_budget": 0.5, "theme": "dark"}
        values.update({r[0]: json.loads(r[1]) for r in self.conn.execute("SELECT key,value FROM preferences")})
        return values

    def save_preferences(self, values):
        with self.repo._lock, self.conn:
            for key, value in values.items():
                self.conn.execute("INSERT OR REPLACE INTO preferences VALUES (?,?)", (key, json.dumps(value)))
        return self.preferences()

    def usage(self):
        today = now()[:10]
        summary = dict(self.conn.execute('''SELECT COUNT(*) AS runs,
            COALESCE(SUM(spent_cost_usd),0) AS spent,
            COALESCE(SUM(reserved_cost_usd),0) AS reserved,
            COALESCE(SUM(unknown_cost_usd),0) AS unknown,
            COALESCE(SUM(total_calls),0) AS calls FROM runs WHERE substr(created_at,1,10)=?''', (today,)).fetchone())
        summary["day"] = today
        summary["timezone"] = "UTC"
        summary["cap"] = self.preferences()["daily_budget"]
        summary["remaining"] = max(0, summary["cap"]-summary["spent"]-summary["reserved"]-summary["unknown"])
        summary["models"] = [dict(r) for r in self.conn.execute('''
            SELECT model_id,SUM(input_tokens) AS input_tokens,SUM(output_tokens) AS output_tokens,
            SUM(COALESCE(actual_cost_usd,0)) AS cost,COUNT(*) AS calls
            FROM usage_records WHERE substr(created_at,1,10)=? GROUP BY model_id''', (today,))]
        return summary

    def accept(self, run_id):
        content = json.dumps(self.repo.get_subtasks(run_id), sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(content.encode()).hexdigest()
        with self.repo._lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO acceptances VALUES (?,?,?)", (run_id, digest, now()))
        return self.acceptance(run_id)

    def acceptance(self, run_id):
        r = self.conn.execute("SELECT * FROM acceptances WHERE run_id=?", (run_id,)).fetchone()
        if not r:return None
        content=json.dumps(self.repo.get_subtasks(run_id),sort_keys=True,ensure_ascii=False)
        if hashlib.sha256(content.encode()).hexdigest()!=r['content_hash']:return None
        return dict(r)

    def projects(self, include_archived=False):
        where = "" if include_archived else "WHERE p.archived=0"
        rows = self.conn.execute(f'''
            SELECT p.*,
                   COUNT(DISTINCT pt.id) AS task_count,
                   COUNT(DISTINCT CASE WHEN pt.status IN ('COMPLETED', 'ACCEPT_CANDIDATE') THEN pt.id END) AS completed_task_count,
                   COALESCE(SUM(r.spent_cost_usd), 0.0) AS spent_cost_usd
            FROM projects p
            LEFT JOIN project_tasks pt ON pt.project_id = p.id
            LEFT JOIN runs r ON r.project_id = p.id
            {where}
            GROUP BY p.id
            ORDER BY p.updated_at DESC
        ''').fetchall()
        return [dict(r) for r in rows]

    def create_project(self, name, path, description="", default_criteria="", default_budget=0.5):
        ident = "proj_" + uuid.uuid4().hex[:12]
        name = clean_text(name, 120)
        path = clean_text(path, 1000)
        description = clean_text(description or "", 5000)
        default_criteria = clean_text(default_criteria or "", 5000)
        ts = now()
        with self.repo._lock, self.conn:
            self.conn.execute("INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,0)",
                              (ident, name, path, description, default_criteria, float(default_budget), ts, ts))
        return self.get_project(ident)

    def get_project(self, ident):
        r = self.conn.execute('''
            SELECT p.*,
                   COUNT(DISTINCT pt.id) AS task_count,
                   COUNT(DISTINCT CASE WHEN pt.status IN ('COMPLETED', 'ACCEPT_CANDIDATE') THEN pt.id END) AS completed_task_count,
                   COALESCE(SUM(r.spent_cost_usd), 0.0) AS spent_cost_usd
            FROM projects p
            LEFT JOIN project_tasks pt ON pt.project_id = p.id
            LEFT JOIN runs r ON r.project_id = p.id
            WHERE p.id=?
            GROUP BY p.id
        ''', (ident,)).fetchone()
        return dict(r) if r else None

    def update_project(self, ident, name=None, path=None, description=None, default_criteria=None, default_budget=None, archived=None):
        project = self.get_project(ident)
        if not project:
            return None
        with self.repo._lock, self.conn:
            if name is not None:
                self.conn.execute("UPDATE projects SET name=?, updated_at=? WHERE id=?", (clean_text(name, 120), now(), ident))
            if path is not None:
                self.conn.execute("UPDATE projects SET path=?, updated_at=? WHERE id=?", (clean_text(path, 1000), now(), ident))
            if description is not None:
                self.conn.execute("UPDATE projects SET description=?, updated_at=? WHERE id=?", (clean_text(description, 5000), now(), ident))
            if default_criteria is not None:
                self.conn.execute("UPDATE projects SET default_criteria=?, updated_at=? WHERE id=?", (clean_text(default_criteria, 5000), now(), ident))
            if default_budget is not None:
                self.conn.execute("UPDATE projects SET default_budget=?, updated_at=? WHERE id=?", (float(default_budget), now(), ident))
            if archived is not None:
                self.conn.execute("UPDATE projects SET archived=?, updated_at=? WHERE id=?", (int(archived), now(), ident))
        return self.get_project(ident)

    def delete_project(self, ident):
        with self.repo._lock, self.conn:
            cur = self.conn.execute("DELETE FROM projects WHERE id=?", (ident,))
            return cur.rowcount > 0

    def project_tasks(self, project_id):
        rows = self.conn.execute('''
            SELECT pt.*, r.status AS run_status, r.spent_cost_usd AS run_spent_usd
            FROM project_tasks pt
            LEFT JOIN runs r ON r.run_id = pt.last_run_id
            WHERE pt.project_id=?
            ORDER BY pt.created_at DESC
        ''', (project_id,)).fetchall()
        result = []
        for r in rows:
            item = dict(r)
            try:
                item["acceptance_criteria"] = json.loads(item["acceptance_criteria"])
            except Exception:
                item["acceptance_criteria"] = [item["acceptance_criteria"]] if item["acceptance_criteria"] else []
            result.append(item)
        return result

    def create_project_task(self, project_id, title, objective, acceptance_criteria, budget_cap_usd=0.5, priority="P1", workflow="low"):
        if not self.get_project(project_id):
            raise ValueError("پروژه پیدا نشد.")
        ident = "ptask_" + uuid.uuid4().hex[:12]
        title = clean_text(title, 160)
        objective = clean_text(objective, 12000)
        if isinstance(acceptance_criteria, list):
            crit_json = json.dumps([clean_text(c, 1000) for c in acceptance_criteria if c.strip()], ensure_ascii=False)
        else:
            crit_json = json.dumps([clean_text(acceptance_criteria, 1000)], ensure_ascii=False)
        ts = now()
        with self.repo._lock, self.conn:
            self.conn.execute("INSERT INTO project_tasks VALUES (?,?,?,?,?,?,?,?,?,NULL,?,?)",
                              (ident, project_id, title, objective, crit_json, float(budget_cap_usd), priority, workflow, "PENDING", ts, ts))
            self.conn.execute("UPDATE projects SET updated_at=? WHERE id=?", (ts, project_id))
        return self.get_project_task(ident)

    def get_project_task(self, task_id):
        r = self.conn.execute('''
            SELECT pt.*, r.status AS run_status, r.spent_cost_usd AS run_spent_usd
            FROM project_tasks pt
            LEFT JOIN runs r ON r.run_id = pt.last_run_id
            WHERE pt.id=?
        ''', (task_id,)).fetchone()
        if not r:
            return None
        item = dict(r)
        try:
            item["acceptance_criteria"] = json.loads(item["acceptance_criteria"])
        except Exception:
            item["acceptance_criteria"] = [item["acceptance_criteria"]] if item["acceptance_criteria"] else []
        return item

    def update_project_task(self, task_id, title=None, objective=None, acceptance_criteria=None,
                            budget_cap_usd=None, priority=None, workflow=None, status=None, last_run_id=None):
        task = self.get_project_task(task_id)
        if not task:
            return None
        ts = now()
        with self.repo._lock, self.conn:
            if title is not None:
                self.conn.execute("UPDATE project_tasks SET title=?, updated_at=? WHERE id=?", (clean_text(title, 160), ts, task_id))
            if objective is not None:
                self.conn.execute("UPDATE project_tasks SET objective=?, updated_at=? WHERE id=?", (clean_text(objective, 12000), ts, task_id))
            if acceptance_criteria is not None:
                if isinstance(acceptance_criteria, list):
                    crit_json = json.dumps([clean_text(c, 1000) for c in acceptance_criteria if c.strip()], ensure_ascii=False)
                else:
                    crit_json = json.dumps([clean_text(acceptance_criteria, 1000)], ensure_ascii=False)
                self.conn.execute("UPDATE project_tasks SET acceptance_criteria=?, updated_at=? WHERE id=?", (crit_json, ts, task_id))
            if budget_cap_usd is not None:
                self.conn.execute("UPDATE project_tasks SET budget_cap_usd=?, updated_at=? WHERE id=?", (float(budget_cap_usd), ts, task_id))
            if priority is not None:
                self.conn.execute("UPDATE project_tasks SET priority=?, updated_at=? WHERE id=?", (priority, ts, task_id))
            if workflow is not None:
                self.conn.execute("UPDATE project_tasks SET workflow=?, updated_at=? WHERE id=?", (workflow, ts, task_id))
            if status is not None:
                self.conn.execute("UPDATE project_tasks SET status=?, updated_at=? WHERE id=?", (status, ts, task_id))
            if last_run_id is not None:
                self.conn.execute("UPDATE project_tasks SET last_run_id=?, updated_at=? WHERE id=?", (last_run_id, ts, task_id))
            self.conn.execute("UPDATE projects SET updated_at=? WHERE id=?", (ts, task["project_id"]))
        return self.get_project_task(task_id)

    def complete_project_task_for_run(self, run_id):
        """Mark the linked project task complete after the user accepts its output."""
        with self.repo._lock, self.conn:
            self.conn.execute(
                "UPDATE project_tasks SET status='COMPLETED', updated_at=? WHERE last_run_id=?",
                (now(), run_id),
            )

    def delete_project_task(self, task_id):
        with self.repo._lock, self.conn:
            cur = self.conn.execute("DELETE FROM project_tasks WHERE id=?", (task_id,))
            return cur.rowcount > 0
