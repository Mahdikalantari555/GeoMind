"""SQLite-backed agent session store: conversations, turns, tool-run audit."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


SCHEMA = """
CREATE TABLE IF NOT EXISTS conversation (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS turn (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversation(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS tool_run (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    turn_id TEXT,
    tool TEXT NOT NULL,
    args_json TEXT NOT NULL,
    args_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    latency_ms INTEGER,
    error TEXT,
    artifacts_json TEXT NOT NULL DEFAULT '[]',
    from_cache INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_turn_conversation ON turn(conversation_id);
CREATE INDEX IF NOT EXISTS idx_tool_run_conversation ON tool_run(conversation_id);
"""


class Store:
    """Owns ``agent.db``; GeoMemory's DB is never touched directly."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        # Tool calls run on daemon threads; serialize writes so the single WAL
        # connection is never used concurrently (SQLite writes are single-file).
        self._write_lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def create_conversation(self, title: str) -> str:
        conv_id = _new_id("conv")
        with self._write_lock:
            self.conn.execute(
                "INSERT INTO conversation (id, title, created_at) VALUES (?, ?, ?)",
                (conv_id, title[:80], _now()),
            )
            self.conn.commit()
        return conv_id

    def list_conversations(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id, title, created_at FROM conversation ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def add_turn(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        turn_id = _new_id("turn")
        with self._write_lock:
            self.conn.execute(
                "INSERT INTO turn (id, conversation_id, role, content, created_at, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    turn_id,
                    conversation_id,
                    role,
                    content,
                    _now(),
                    json.dumps(metadata or {}),
                ),
            )
            self.conn.commit()
        return turn_id

    def turns(self, conversation_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id, role, content, metadata FROM turn "
            "WHERE conversation_id = ? ORDER BY created_at, rowid",
            (conversation_id,),
        ).fetchall()
        out = []
        for r in rows:
            item = dict(r)
            item["metadata"] = json.loads(item["metadata"])
            out.append(item)
        return out

    def record_tool_run(
        self,
        *,
        conversation_id: str | None,
        turn_id: str | None,
        tool: str,
        args: dict[str, Any],
        args_hash: str,
        status: str,
        latency_ms: int,
        error: str | None,
        artifacts: list[dict[str, Any]],
        from_cache: bool,
    ) -> str:
        run_id = _new_id("run")
        with self._write_lock:
            self.conn.execute(
                "INSERT INTO tool_run "
                "(id, conversation_id, turn_id, tool, args_json, args_hash, status, "
                " latency_ms, error, artifacts_json, from_cache, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    conversation_id,
                    turn_id,
                    tool,
                    json.dumps(args, default=str),
                    args_hash,
                    status,
                    latency_ms,
                    error,
                    json.dumps(artifacts),
                    int(from_cache),
                    _now(),
                ),
            )
            self.conn.commit()
        return run_id

    def list_tool_runs(
        self,
        *,
        tool: str | None = None,
        status: str | None = None,
        conversation_id: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Read ToolRun audit rows for export (learning-loop spec L32)."""
        clauses: list[str] = []
        params: list[Any] = []
        if tool:
            clauses.append("tool = ?")
            params.append(tool)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if conversation_id:
            clauses.append("conversation_id = ?")
            params.append(conversation_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(int(limit), 100000)))
        rows = self.conn.execute(
            "SELECT id, conversation_id, turn_id, tool, args_json, args_hash, "
            "status, latency_ms, error, artifacts_json, from_cache, created_at "
            f"FROM tool_run{where} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [
            {
                "id": str(r["id"]),
                "conversation_id": r["conversation_id"],
                "turn_id": r["turn_id"],
                "tool": str(r["tool"]),
                "args_json": str(r["args_json"]),
                "args_hash": str(r["args_hash"]),
                "status": str(r["status"]),
                "latency_ms": r["latency_ms"],
                "error": r["error"],
                "artifacts_json": str(r["artifacts_json"]),
                "from_cache": bool(r["from_cache"]),
                "created_at": str(r["created_at"]),
                # "budgets hit" is represented by the budget_refused status.
                "budgets_hit": str(r["status"]) == "budget_refused",
            }
            for r in rows
        ]
