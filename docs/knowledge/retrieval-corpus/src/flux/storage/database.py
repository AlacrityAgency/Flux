"""SQLite Database connection and table schemas."""

import sqlite3
import os
from pathlib import Path


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    root_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    human_owner TEXT NOT NULL,
    task_payload TEXT NOT NULL,
    idempotency_key TEXT UNIQUE,
    status TEXT NOT NULL,
    budget_cap_usd REAL NOT NULL,
    spent_cost_usd REAL DEFAULT 0.0,
    reserved_cost_usd REAL DEFAULT 0.0,
    unknown_cost_usd REAL DEFAULT 0.0,
    total_calls INTEGER DEFAULT 0,
    active_runtime_seconds REAL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS subtasks (
    subtask_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    objective TEXT NOT NULL,
    assigned_agent TEXT NOT NULL,
    acceptance_criteria TEXT NOT NULL,
    dependencies TEXT NOT NULL,
    max_output_tokens INTEGER NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER DEFAULT 0,
    summary TEXT,
    output TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (run_id, subtask_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_calls (
    call_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    subtask_id TEXT,
    agent_role TEXT NOT NULL,
    model_id TEXT NOT NULL,
    prompt_hash TEXT,
    attempt INTEGER DEFAULT 1,
    status TEXT NOT NULL,
    error_message TEXT,
    latency_ms INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    subtask_id TEXT,
    type TEXT NOT NULL,
    ref TEXT NOT NULL,
    description TEXT,
    content_hash TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS checks (
    check_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    subtask_id TEXT,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    blocking_issues TEXT,
    passed_criteria TEXT,
    failed_criteria TEXT,
    confidence TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS budget_reservations (
    reservation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    call_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    reserved_amount_usd REAL NOT NULL,
    price_snapshot_input REAL NOT NULL,
    price_snapshot_output REAL NOT NULL,
    settled_amount_usd REAL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS usage_records (
    usage_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    call_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    cached_input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER NOT NULL,
    estimated_cost_usd REAL NOT NULL,
    actual_cost_usd REAL,
    is_unknown INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL,
    reason TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id, sequence);
CREATE INDEX IF NOT EXISTS idx_calls_run ON agent_calls(run_id);
"""


def init_db(db_path: str = "var/flux.db") -> sqlite3.Connection:
    """Initialize database and create schema."""
    if db_path != ":memory:":
        parent = Path(db_path).parent
        parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA_SQL)
    conn.execute("CREATE TABLE IF NOT EXISTS agent_settings (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
    conn.commit()
    return conn
