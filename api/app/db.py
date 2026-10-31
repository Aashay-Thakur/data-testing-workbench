"""SQLite for saved checks and run history. No secrets and no connection rows."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.config import DATA_DIR

DB_PATH = DATA_DIR / "workbench.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    label TEXT NOT NULL,
    origin TEXT NOT NULL,
    target_json TEXT NOT NULL,
    params_json TEXT NOT NULL,
    blocking INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id INTEGER,
    name TEXT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    blocking INTEGER NOT NULL DEFAULT 0,
    threshold_json TEXT,
    sample_json TEXT,
    metrics_json TEXT,
    message TEXT,
    runtime_ms INTEGER,
    sql_hash TEXT,
    git_sha TEXT,
    target TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs (created_at);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs (status, created_at);
"""


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_check(
    *,
    name: str,
    kind: str,
    label: str,
    origin: str,
    target: dict,
    params: dict,
    blocking: bool,
) -> dict:
    created_at = now()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO checks (name, kind, label, origin, target_json, params_json, blocking, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                kind,
                label,
                origin,
                json.dumps(target),
                json.dumps(params),
                1 if blocking else 0,
                created_at,
            ),
        )
        check_id = int(cursor.lastrowid)
    return get_check(check_id)


def list_checks(origin: str | None = None) -> list[dict]:
    sql = (
        "SELECT id, name, kind, label, origin, target_json, params_json, blocking, created_at "
        "FROM checks"
    )
    args: tuple[Any, ...] = ()
    if origin:
        sql += " WHERE origin = ?"
        args = (origin,)
    sql += " ORDER BY id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_check(row) for row in rows]


def get_check(check_id: int) -> dict:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, name, kind, label, origin, target_json, params_json, blocking, created_at
            FROM checks WHERE id = ?
            """,
            (check_id,),
        ).fetchone()
    if row is None:
        from app.errors import UserError

        raise UserError(f"Check {check_id} was not found.", 404)
    return _check(row)


def find_check_by_kind_param(kind: str, key: str, value: str) -> dict | None:
    for check in list_checks():
        if check["kind"] == kind and str(check["params"].get(key)) == value:
            return check
    return None


def create_run(payload: dict) -> dict:
    created_at = payload.get("created_at") or now()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO runs (
                check_id, name, kind, status, blocking, threshold_json, sample_json,
                metrics_json, message, runtime_ms, sql_hash, git_sha, target, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("check_id"),
                payload.get("name"),
                payload["kind"],
                payload["status"],
                1 if payload.get("blocking") else 0,
                json.dumps(payload.get("threshold") or {}),
                json.dumps(payload.get("sample") or []),
                json.dumps(payload.get("metrics") or {}),
                payload.get("message"),
                payload.get("runtime_ms"),
                payload.get("sql_hash"),
                payload.get("git_sha"),
                payload.get("target"),
                created_at,
            ),
        )
        run_id = int(cursor.lastrowid)
    return get_run(run_id)


def get_run(run_id: int) -> dict:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, check_id, name, kind, status, blocking, threshold_json, sample_json,
                   metrics_json, message, runtime_ms, sql_hash, git_sha, target, created_at
            FROM runs WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
    if row is None:
        from app.errors import UserError

        raise UserError(f"Run {run_id} was not found.", 404)
    return _run(row)


def home_summary() -> dict:
    return {
        "failing": _runs_where("status = 'fail'", 20),
        "blocking": _runs_where("blocking = 1 AND status != 'pass'", 20),
        "last_success": _runs_where("status = 'pass'", 10),
    }


def _runs_where(clause: str, limit: int) -> list[dict]:
    sql = (
        "SELECT id, check_id, name, kind, status, blocking, threshold_json, sample_json, "
        "metrics_json, message, runtime_ms, sql_hash, git_sha, target, created_at "
        f"FROM runs WHERE {clause} ORDER BY created_at DESC LIMIT ?"
    )
    with _connect() as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    return [_run(row) for row in rows]


def _check(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "kind": row["kind"],
        "label": row["label"],
        "origin": row["origin"],
        "target": json.loads(row["target_json"]),
        "params": json.loads(row["params_json"]),
        "blocking": bool(row["blocking"]),
        "created_at": row["created_at"],
    }


def _run(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "check_id": row["check_id"],
        "name": row["name"],
        "kind": row["kind"],
        "status": row["status"],
        "blocking": bool(row["blocking"]),
        "threshold": json.loads(row["threshold_json"] or "{}"),
        "sample": json.loads(row["sample_json"] or "[]"),
        "metrics": json.loads(row["metrics_json"] or "{}"),
        "message": row["message"],
        "runtime_ms": row["runtime_ms"],
        "sql_hash": row["sql_hash"],
        "git_sha": row["git_sha"],
        "target": row["target"],
        "created_at": row["created_at"],
    }
