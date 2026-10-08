"""Repository for atomic database operations."""

import json
import sqlite3
import threading
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from flux.contracts.head import SubtaskSpec
from flux.contracts.run import RunState, RunEvent
from flux.contracts.reviewer import ReviewDecision
from flux.contracts.envelope import ArtifactSpec, CheckSpec


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._lock = threading.RLock()
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS legacy_root_budgets (root_id TEXT PRIMARY KEY, cap_usd REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS budget_reconciliation_conflicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, reservation_id TEXT NOT NULL,
                observation TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')
        self.conn.commit()

    def create_run(
        self,
        run_id: str,
        task_id: str,
        root_id: str,
        project_id: str,
        human_owner: str,
        task_payload: dict,
        budget_cap_usd: float,
        idempotency_key: Optional[str] = None
    ) -> bool:
        """Atomically create a run or return False if idempotency conflict."""
        with self._lock:
            now = utc_now_iso()
            try:
                self.conn.execute(
                    """
                    INSERT INTO runs (
                        run_id, task_id, root_id, project_id, human_owner,
                        task_payload, idempotency_key, status, budget_cap_usd,
                        spent_cost_usd, reserved_cost_usd, unknown_cost_usd,
                        total_calls, active_runtime_seconds, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'NEW', ?, 0.0, 0.0, 0.0, 0, 0.0, ?, ?)
                    """,
                    (
                        run_id, task_id, root_id, project_id, human_owner,
                        json.dumps(task_payload), idempotency_key, budget_cap_usd,
                        now, now
                    )
                )
                self.conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_run_by_idempotency_key(self, idempotency_key: str) -> Optional[dict]:
        with self._lock:
            cursor = self.conn.execute(
                "SELECT * FROM runs WHERE idempotency_key = ?", (idempotency_key,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_run(self, run_id: str) -> Optional[dict]:
        with self._lock:
            cursor = self.conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_runs(self, limit: int = 50) -> List[dict]:
        with self._lock:
            cursor = self.conn.execute(
                """
                SELECT run_id, task_id, root_id, project_id, human_owner,
                       status, budget_cap_usd, spent_cost_usd, reserved_cost_usd,
                       unknown_cost_usd, total_calls, created_at, completed_at,
                       json_extract(task_payload, '$.objective') as objective
                FROM runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(r) for r in cursor.fetchall()]

    def update_run_status(
        self,
        run_id: str,
        to_state: RunState,
        reason: str,
        metadata: Optional[dict] = None
    ) -> int:
        """Atomically update state and insert an event with incrementing sequence."""
        with self._lock:
            now = utc_now_iso()
            # Get current state and max sequence
            cursor = self.conn.execute(
                "SELECT status FROM runs WHERE run_id = ?", (run_id,)
            )
            row = cursor.fetchone()
            from_state = row["status"] if row else None

            seq_cur = self.conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_seq FROM events WHERE run_id = ?",
                (run_id,)
            )
            next_seq = seq_cur.fetchone()["next_seq"]

            completed_at = now if to_state in (
                "ACCEPT_CANDIDATE", "REJECTED", "FAILED", "CANCELLED", "ESCALATED"
            ) else None

            self.conn.execute(
                """
                UPDATE runs
                SET status = ?, updated_at = ?, completed_at = COALESCE(completed_at, ?)
                WHERE run_id = ?
                """,
                (to_state, now, completed_at, run_id)
            )

            self.conn.execute(
                """
                INSERT INTO events (run_id, sequence, from_state, to_state, reason, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, next_seq, from_state, to_state, reason, json.dumps(metadata or {}), now)
            )
            self.conn.commit()
            return next_seq

    def record_active_time(self, run_id: str, seconds: float):
        with self._lock:
            self.conn.execute(
                """
                UPDATE runs
                SET active_runtime_seconds = active_runtime_seconds + ?, updated_at = ?
                WHERE run_id = ?
                """,
                (seconds, utc_now_iso(), run_id)
            )
            self.conn.commit()

    def add_subtasks(self, run_id: str, subtasks: List[SubtaskSpec]):
        with self._lock:
            now = utc_now_iso()
            for s in subtasks:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO subtasks (
                        subtask_id, run_id, objective, assigned_agent,
                        acceptance_criteria, dependencies, max_output_tokens,
                        status, attempts, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'QUEUED', 0, ?, ?)
                    """,
                    (
                        s.subtask_id, run_id, s.objective, s.assigned_agent,
                        json.dumps(s.acceptance_criteria), json.dumps(s.dependencies),
                        s.max_output_tokens, now, now
                    )
                )
            self.conn.commit()

    def get_subtasks(self, run_id: str) -> List[dict]:
        with self._lock:
            cursor = self.conn.execute(
                "SELECT * FROM subtasks WHERE run_id = ? ORDER BY created_at, rowid", (run_id,)
            )
            res = []
            for row in cursor.fetchall():
                d = dict(row)
                d["acceptance_criteria"] = json.loads(d["acceptance_criteria"])
                d["dependencies"] = json.loads(d["dependencies"])
                if d["output"]:
                    d["output"] = json.loads(d["output"])
                res.append(d)
            return res

    def update_subtask_execution(
        self,
        run_id: str,
        subtask_id: str,
        status: str,
        summary: str,
        output: dict,
        increment_attempt: bool = True
    ):
        with self._lock:
            now = utc_now_iso()
            attempt_expr = "attempts + 1" if increment_attempt else "attempts"
            self.conn.execute(
                f"""
                UPDATE subtasks
                SET status = ?, summary = ?, output = ?, attempts = {attempt_expr}, updated_at = ?
                WHERE run_id = ? AND subtask_id = ?
                """,
                (status, summary, json.dumps(output), now, run_id, subtask_id)
            )
            self.conn.commit()

    def add_call(
        self,
        call_id: str,
        run_id: str,
        agent_role: str,
        model_id: str,
        subtask_id: Optional[str] = None,
        prompt_hash: Optional[str] = None,
        attempt: int = 1
    ):
        with self._lock:
            now = utc_now_iso()
            self.conn.execute(
                """
                INSERT INTO agent_calls (
                    call_id, run_id, subtask_id, agent_role, model_id,
                    prompt_hash, attempt, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (call_id, run_id, subtask_id, agent_role, model_id, prompt_hash, attempt, now)
            )
            self.conn.execute(
                "UPDATE runs SET total_calls = total_calls + 1, updated_at = ? WHERE run_id = ?",
                (now, run_id)
            )
            self.conn.commit()

    def update_call_status(
        self,
        call_id: str,
        status: str,
        error_message: Optional[str] = None,
        latency_ms: int = 0
    ):
        with self._lock:
            self.conn.execute(
                """
                UPDATE agent_calls
                SET status = ?, error_message = ?, latency_ms = ?
                WHERE call_id = ?
                """,
                (status, error_message, latency_ms, call_id)
            )
            self.conn.commit()

    def add_artifact(
        self,
        artifact_id: str,
        run_id: str,
        subtask_id: Optional[str],
        artifact_type: str,
        ref: str,
        description: str = "",
        content_hash: Optional[str] = None
    ):
        with self._lock:
            now = utc_now_iso()
            self.conn.execute(
                """
                INSERT INTO artifacts (artifact_id, run_id, subtask_id, type, ref, description, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (artifact_id, run_id, subtask_id, artifact_type, ref, description, content_hash, now)
            )
            self.conn.commit()

    def get_artifacts(self, run_id: str) -> List[dict]:
        with self._lock:
            cursor = self.conn.execute("SELECT * FROM artifacts WHERE run_id = ?", (run_id,))
            return [dict(r) for r in cursor.fetchall()]

    def add_check(
        self,
        check_id: str,
        run_id: str,
        subtask_id: Optional[str],
        name: str,
        status: str,
        evidence: str = ""
    ):
        with self._lock:
            now = utc_now_iso()
            self.conn.execute(
                """
                INSERT INTO checks (check_id, run_id, subtask_id, name, status, evidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (check_id, run_id, subtask_id, name, status, evidence, now)
            )
            self.conn.commit()

    def get_checks(self, run_id: str) -> List[dict]:
        with self._lock:
            cursor = self.conn.execute("SELECT * FROM checks WHERE run_id = ?", (run_id,))
            return [dict(r) for r in cursor.fetchall()]

    def add_decision(
        self,
        decision_id: str,
        run_id: str,
        decision: str,
        blocking_issues: list,
        passed_criteria: list,
        failed_criteria: list,
        confidence: str
    ):
        with self._lock:
            now = utc_now_iso()
            self.conn.execute(
                """
                INSERT INTO decisions (
                    decision_id, run_id, decision, blocking_issues,
                    passed_criteria, failed_criteria, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id, run_id, decision, json.dumps(blocking_issues),
                    json.dumps(passed_criteria), json.dumps(failed_criteria), confidence, now
                )
            )
            self.conn.commit()

    def get_decision(self, run_id: str) -> Optional[dict]:
        with self._lock:
            cursor = self.conn.execute("SELECT * FROM decisions WHERE run_id = ? ORDER BY created_at DESC LIMIT 1", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["blocking_issues"] = json.loads(d["blocking_issues"])
            d["passed_criteria"] = json.loads(d["passed_criteria"])
            d["failed_criteria"] = json.loads(d["failed_criteria"])
            return d

    # Budget operations
    def reserve_budget(
        self,
        reservation_id: str,
        run_id: str,
        call_id: str,
        model_id: str,
        amount_usd: float,
        price_input: float,
        price_output: float
    ) -> bool:
        """Atomically checks invariant and reserves budget.
        Invariant: spent_known + held_unknown + reserved_cost + amount <= budget_cap
        """
        if not math.isfinite(amount_usd) or amount_usd<0:raise ValueError('Invalid reservation amount.')
        with self._lock, self.conn:
            self.conn.execute('BEGIN IMMEDIATE')
            now = utc_now_iso()
            existing=self.conn.execute('SELECT * FROM budget_reservations WHERE reservation_id=?',(reservation_id,)).fetchone()
            if existing:
                if existing['run_id']!=run_id or existing['call_id']!=call_id or existing['model_id']!=model_id or existing['reserved_amount_usd']!=amount_usd:
                    raise ValueError('Reservation idempotency conflict.')
                return existing['status']=='active'
            cursor = self.conn.execute(
                "SELECT budget_cap_usd, spent_cost_usd, reserved_cost_usd, unknown_cost_usd FROM runs WHERE run_id = ?",
                (run_id,)
            )
            run_row = cursor.fetchone()
            if not run_row:
                return False

            cap = run_row["budget_cap_usd"]
            spent = run_row["spent_cost_usd"]
            reserved = run_row["reserved_cost_usd"]
            unknown = run_row["unknown_cost_usd"]

            if round(spent + reserved + unknown + amount_usd, 6) > round(cap, 6):
                return False  # Over budget!
            root=self.conn.execute('SELECT root_id FROM runs WHERE run_id=?',(run_id,)).fetchone()[0]
            blocked=self.conn.execute('SELECT 1 FROM budget_reconciliation_conflicts c JOIN budget_reservations b ON c.reservation_id=b.reservation_id JOIN runs r ON b.run_id=r.run_id WHERE r.root_id=?',(root,)).fetchone()
            if blocked:return False
            self.conn.execute('INSERT OR IGNORE INTO legacy_root_budgets VALUES (?,?)',(root,cap))
            root_cap=self.conn.execute('SELECT cap_usd FROM legacy_root_budgets WHERE root_id=?',(root,)).fetchone()[0]
            root_total=self.conn.execute('SELECT COALESCE(SUM(spent_cost_usd+reserved_cost_usd+unknown_cost_usd),0) FROM runs WHERE root_id=?',(root,)).fetchone()[0]
            if round(root_total+amount_usd,6)>round(root_cap,6):return False

            # Workspace daily cap covers all runs; late settlement stays with its run's UTC day.
            if self.conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='preferences'").fetchone():
                pref = self.conn.execute("SELECT value FROM preferences WHERE key='daily_budget'").fetchone()
                daily_cap = float(json.loads(pref[0])) if pref else 5.0
                day = self.conn.execute("SELECT substr(created_at,1,10) FROM runs WHERE run_id=?", (run_id,)).fetchone()[0]
                total = self.conn.execute("SELECT COALESCE(SUM(spent_cost_usd+reserved_cost_usd+unknown_cost_usd),0) FROM runs WHERE substr(created_at,1,10)=?", (day,)).fetchone()[0]
                if round(total + amount_usd, 6) > round(daily_cap, 6):
                    return False

            self.conn.execute(
                """
                INSERT INTO budget_reservations (
                    reservation_id, run_id, call_id, model_id,
                    reserved_amount_usd, price_snapshot_input, price_snapshot_output,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
                """,
                (reservation_id, run_id, call_id, model_id, amount_usd, price_input, price_output, now)
            )
            self.conn.execute(
                """
                UPDATE runs
                SET reserved_cost_usd = reserved_cost_usd + ?, updated_at = ?
                WHERE run_id = ?
                """,
                (amount_usd, now, run_id)
            )
            self.conn.commit()
            return True

    def settle_reservation(
        self,
        reservation_id: str,
        actual_cost_usd: Optional[float],
        is_unknown: bool = False
    ):
        """Settle reservation with actual cost, or hold as unknown if missing."""
        if actual_cost_usd is not None and (not math.isfinite(actual_cost_usd) or actual_cost_usd<0):raise ValueError('Invalid actual cost.')
        with self._lock, self.conn:
            self.conn.execute('BEGIN IMMEDIATE')
            now = utc_now_iso()
            res_cur = self.conn.execute(
                "SELECT run_id, reserved_amount_usd, settled_amount_usd, status FROM budget_reservations WHERE reservation_id = ?",
                (reservation_id,)
            )
            res_row = res_cur.fetchone()
            if not res_row:raise KeyError(reservation_id)
            if res_row['status']=='settled':
                if not is_unknown and actual_cost_usd==res_row['settled_amount_usd']:return 'settled'
                self.conn.execute('INSERT INTO budget_reconciliation_conflicts (reservation_id,observation,created_at) VALUES (?,?,?)',(reservation_id,json.dumps({'actual':actual_cost_usd,'is_unknown':is_unknown,'prior':res_row['settled_amount_usd']}),now))
                return 'BLOCKED_RECONCILIATION'
            if res_row['status']=='held_unknown' and (is_unknown or actual_cost_usd is None):return 'held_unknown'

            run_id = res_row["run_id"]
            reserved_amount = res_row["reserved_amount_usd"]
            if res_row['status']=='held_unknown':
                self.conn.execute("UPDATE budget_reservations SET settled_amount_usd=?,status='settled' WHERE reservation_id=?",(actual_cost_usd,reservation_id))
                self.conn.execute('UPDATE runs SET unknown_cost_usd=MAX(0,unknown_cost_usd-?),spent_cost_usd=spent_cost_usd+?,updated_at=? WHERE run_id=?',(reserved_amount,actual_cost_usd,now,run_id))
                self.conn.execute('UPDATE usage_records SET actual_cost_usd=?,is_unknown=0 WHERE call_id=(SELECT call_id FROM budget_reservations WHERE reservation_id=?)',(actual_cost_usd,reservation_id))
                return 'settled'

            if is_unknown or actual_cost_usd is None:
                # Keep reserved amount as held_unknown, do NOT release!
                self.conn.execute(
                    """
                    UPDATE budget_reservations
                    SET status = 'held_unknown'
                    WHERE reservation_id = ?
                    """,
                    (reservation_id,)
                )
                self.conn.execute(
                    """
                    UPDATE runs
                    SET reserved_cost_usd = MAX(0.0, reserved_cost_usd - ?),
                        unknown_cost_usd = unknown_cost_usd + ?,
                        updated_at = ?
                    WHERE run_id = ?
                    """,
                    (reserved_amount, reserved_amount, now, run_id)
                )
            else:
                self.conn.execute(
                    """
                    UPDATE budget_reservations
                    SET settled_amount_usd = ?, status = 'settled'
                    WHERE reservation_id = ?
                    """,
                    (actual_cost_usd, reservation_id)
                )
                self.conn.execute(
                    """
                    UPDATE runs
                    SET reserved_cost_usd = MAX(0.0, reserved_cost_usd - ?),
                        spent_cost_usd = spent_cost_usd + ?,
                        updated_at = ?
                    WHERE run_id = ?
                    """,
                    (reserved_amount, actual_cost_usd, now, run_id)
                )
            self.conn.commit()
            return 'held_unknown' if is_unknown or actual_cost_usd is None else 'settled'

    def record_usage(
        self,
        usage_id: str,
        run_id: str,
        call_id: str,
        model_id: str,
        input_tokens: int,
        cached_input_tokens: int,
        output_tokens: int,
        estimated_cost_usd: float,
        actual_cost_usd: Optional[float],
        is_unknown: bool = False
    ):
        with self._lock:
            now = utc_now_iso()
            self.conn.execute(
                """
                INSERT INTO usage_records (
                    usage_id, run_id, call_id, model_id,
                    input_tokens, cached_input_tokens, output_tokens,
                    estimated_cost_usd, actual_cost_usd, is_unknown, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    usage_id, run_id, call_id, model_id,
                    input_tokens, cached_input_tokens, output_tokens,
                    estimated_cost_usd, actual_cost_usd, 1 if is_unknown else 0, now
                )
            )
            self.conn.commit()

    def get_usage_summary(self, run_id: str) -> dict:
        with self._lock:
            run = self.get_run(run_id)
            if not run:
                return {}
            cur = self.conn.execute(
                """
                SELECT
                    model_id,
                    SUM(input_tokens) as total_in,
                    SUM(cached_input_tokens) as total_cached_in,
                    SUM(output_tokens) as total_out,
                    SUM(COALESCE(actual_cost_usd, 0.0)) as total_cost,
                    COUNT(*) as call_count
                FROM usage_records
                WHERE run_id = ?
                GROUP BY model_id
                """,
                (run_id,)
            )
            breakdown = [dict(r) for r in cur.fetchall()]
            return {
                "run_id": run_id,
                "budget_cap_usd": run["budget_cap_usd"],
                "spent_cost_usd": run["spent_cost_usd"],
                "reserved_cost_usd": run["reserved_cost_usd"],
                "unknown_cost_usd": run["unknown_cost_usd"],
                "remaining_budget_usd": max(
                    0.0,
                    run["budget_cap_usd"] - (run["spent_cost_usd"] + run["reserved_cost_usd"] + run["unknown_cost_usd"])
                ),
                "total_calls": run["total_calls"],
                "by_model": breakdown
            }

    def get_events(self, run_id: str, after_sequence: int = 0, limit: int = 100) -> List[dict]:
        with self._lock:
            cur = self.conn.execute(
                """
                SELECT sequence, run_id, from_state, to_state, reason, metadata, created_at
                FROM events
                WHERE run_id = ? AND sequence > ?
                ORDER BY sequence ASC
                LIMIT ?
                """,
                (run_id, after_sequence, limit)
            )
            res = []
            for row in cur.fetchall():
                d = dict(row)
                d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
                res.append(d)
            return res
