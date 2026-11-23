"""Versioned schema migration runner."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from geomemory.core.exceptions import DatabaseError


@dataclass(frozen=True)
class Migration:
    """A single versioned migration."""

    version: int
    description: str
    sql: str


# Migrations are ordered by version. The base schema is version 1.
MIGRATIONS: list[Migration] = [
    Migration(version=1, description="Initial schema (workspace, assets, segments, fts, rtree)", sql=""),
    Migration(
        version=2,
        description="Add metadata column to raster_tile",
        sql="ALTER TABLE raster_tile ADD COLUMN metadata TEXT DEFAULT '{}';",
    ),
    Migration(
        version=3,
        description="Fix spatial_index RTree to use integer rowid + entity-id map",
        sql=(
            "DROP TABLE IF EXISTS spatial_index;"
            "CREATE TABLE IF NOT EXISTS spatial_entity ("
            "    rowid     INTEGER PRIMARY KEY AUTOINCREMENT,"
            "    entity_id TEXT NOT NULL UNIQUE"
            ");"
            "CREATE VIRTUAL TABLE IF NOT EXISTS spatial_index USING rtree("
            "    id, min_lat, max_lat, min_lon, max_lon"
            ");"
        ),
    ),
    Migration(
        version=4,
        description="Add candidate_memory, knowledge_change_proposal, provenance_chain",
        sql=(
            "CREATE TABLE IF NOT EXISTS candidate_memory ("
            "    id TEXT PRIMARY KEY, content TEXT NOT NULL, memory_type TEXT NOT NULL DEFAULT 'fact',"
            "    source_feedback_ids TEXT NOT NULL DEFAULT '[]', confidence_score REAL NOT NULL DEFAULT 5.0,"
            "    state TEXT NOT NULL DEFAULT 'proposed', author TEXT, audit_trail TEXT NOT NULL DEFAULT '[]',"
            "    created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')),"
            "    CHECK (memory_type IN ('fact','correction','annotation','preference')),"
            "    CHECK (state IN ('proposed','supported','verified','rejected'))"
            ");"
            "CREATE INDEX IF NOT EXISTS idx_candidate_state ON candidate_memory(state);"
            "CREATE INDEX IF NOT EXISTS idx_candidate_score ON candidate_memory(confidence_score);"
            "CREATE TABLE IF NOT EXISTS knowledge_change_proposal ("
            "    id TEXT PRIMARY KEY, proposal_type TEXT NOT NULL, diff TEXT NOT NULL DEFAULT '{}',"
            "    source_candidate_ids TEXT NOT NULL DEFAULT '[]', confidence REAL NOT NULL DEFAULT 0.0,"
            "    status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL DEFAULT (datetime('now')),"
            "    reviewed_at TEXT, reviewer_id TEXT, review_note TEXT,"
            "    CHECK (proposal_type IN ('graph_relation','markdown_document','metadata_update','entity_create')),"
            "    CHECK (status IN ('pending','approved','rejected'))"
            ");"
            "CREATE INDEX IF NOT EXISTS idx_proposal_status ON knowledge_change_proposal(status);"
            "CREATE TABLE IF NOT EXISTS provenance_chain ("
            "    id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES candidate_memory(id) ON DELETE CASCADE,"
            "    feedback_id TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now'))"
            ");"
        ),
    ),
    Migration(
        version=5,
        description="Add entity table for geospatial knowledge layer",
        sql=(
            "CREATE TABLE IF NOT EXISTS entity ("
            "    id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,"
            "    workspace_id TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,"
            "    spatial_bbox TEXT, evidence_id TEXT,"
            "    created_at TEXT NOT NULL DEFAULT (datetime('now')),"
            "    CHECK (kind IN ('concept','location','sensor','product','stress_type','metric'))"
            ");"
            "CREATE INDEX IF NOT EXISTS idx_entity_kind ON entity(kind);"
            "CREATE INDEX IF NOT EXISTS idx_entity_workspace ON entity(workspace_id);"
            "CREATE INDEX IF NOT EXISTS idx_entity_name ON entity(name);"
        ),
    ),
    Migration(
        version=6,
        description="add temporal/entity fields to candidate_memory",
        sql=(
            # SQLite cannot ALTER a CHECK constraint, so the table is rebuilt.
            # Foreign keys are disabled for the rebuild so provenance_chain's
            # reference survives the DROP/RENAME; it re-resolves after the
            # rename back to candidate_memory.
            "PRAGMA foreign_keys=OFF;"
            "CREATE TABLE IF NOT EXISTS candidate_memory_v6 ("
            "    id TEXT PRIMARY KEY, content TEXT NOT NULL, memory_type TEXT NOT NULL DEFAULT 'fact',"
            "    source_feedback_ids TEXT NOT NULL DEFAULT '[]', confidence_score REAL NOT NULL DEFAULT 5.0,"
            "    state TEXT NOT NULL DEFAULT 'proposed', author TEXT, audit_trail TEXT NOT NULL DEFAULT '[]',"
            "    created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')),"
            "    observed_at TEXT,"
            "    superseded_by TEXT REFERENCES candidate_memory(id) ON DELETE SET NULL,"
            "    project TEXT,"
            "    CHECK (memory_type IN ('fact','correction','annotation','preference',"
            "'decision','hypothesis','method','dataset_event','episodic','working')),"
            "    CHECK (state IN ('proposed','supported','verified','rejected'))"
            ");"
            "INSERT INTO candidate_memory_v6"
            " (id, content, memory_type, source_feedback_ids, confidence_score, state, author, audit_trail, created_at, updated_at)"
            " SELECT id, content, memory_type, source_feedback_ids, confidence_score, state, author, audit_trail, created_at, updated_at"
            " FROM candidate_memory;"
            "DROP TABLE candidate_memory;"
            "ALTER TABLE candidate_memory_v6 RENAME TO candidate_memory;"
            "CREATE INDEX IF NOT EXISTS idx_candidate_state ON candidate_memory(state);"
            "CREATE INDEX IF NOT EXISTS idx_candidate_score ON candidate_memory(confidence_score);"
            "CREATE INDEX IF NOT EXISTS idx_candidate_observed ON candidate_memory(id, observed_at DESC);"
            "PRAGMA foreign_keys=ON;"
        ),
    ),
    Migration(
        version=7,
        description="Carry citation target type for traceable non-segment sources",
        sql=(
            "ALTER TABLE citation ADD COLUMN target_type TEXT NOT NULL DEFAULT 'segment';"
            "ALTER TABLE citation ADD COLUMN target_id TEXT;"
        ),
    ),
    Migration(
        version=8,
        description="FTS5 index for candidate-memory search (no full-table LIKE scan)",
        sql=(
            "CREATE VIRTUAL TABLE IF NOT EXISTS candidate_memory_fts USING fts5("
            "content, content='candidate_memory', content_rowid='rowid');"
            "CREATE TRIGGER IF NOT EXISTS candidate_memory_ai AFTER INSERT ON candidate_memory BEGIN "
            "INSERT INTO candidate_memory_fts(rowid, content) VALUES (new.rowid, new.content); END;"
            "CREATE TRIGGER IF NOT EXISTS candidate_memory_ad AFTER DELETE ON candidate_memory BEGIN "
            "INSERT INTO candidate_memory_fts(candidate_memory_fts, rowid, content) "
            "VALUES('delete', old.rowid, old.content); END;"
            "CREATE TRIGGER IF NOT EXISTS candidate_memory_au AFTER UPDATE OF content ON candidate_memory BEGIN "
            "INSERT INTO candidate_memory_fts(candidate_memory_fts, rowid, content) "
            "VALUES('delete', old.rowid, old.content); "
            "INSERT INTO candidate_memory_fts(rowid, content) VALUES (new.rowid, new.content); END;"
            "INSERT INTO candidate_memory_fts(candidate_memory_fts) VALUES('rebuild');"
        ),
    ),
]


def _split_statements(sql: str) -> list[str]:
    """Split a SQL script into statements without letting ``executescript``
    implicitly commit mid-migration.

    Handles quoted strings (including doubled quotes), ``--`` comments, and
    ``CREATE TRIGGER ... BEGIN ... END;`` bodies whose internal semicolons
    must stay inside the single statement.
    """
    statements: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    in_trigger = False
    trigger_depth = 0
    i = 0
    while i < len(sql):
        ch = sql[i]
        if quote is not None:
            buf.append(ch)
            if ch == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    buf.append(sql[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if sql.startswith("--", i):
            end = sql.find("\n", i)
            if end == -1:
                break
            buf.append("\n")
            i = end + 1
            continue
        if ch.isalpha():
            j = i
            while j < len(sql) and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            word = sql[i:j].upper()
            if word == "TRIGGER" and "CREATE" in "".join(buf).upper():
                in_trigger = True
                trigger_depth = 0
            elif in_trigger and word == "BEGIN":
                trigger_depth += 1
            elif in_trigger and word == "END":
                trigger_depth = max(0, trigger_depth - 1)
            buf.append(sql[i:j])
            i = j
            continue
        if ch == ";":
            if in_trigger and trigger_depth > 0:
                buf.append(ch)
            else:
                statement = "".join(buf).strip()
                if statement:
                    statements.append(statement)
                buf = []
                in_trigger = False
                trigger_depth = 0
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _execute_script_in_transaction(conn: sqlite3.Connection, sql: str) -> None:
    """Run a SQL script statement-by-statement inside the caller's transaction.

    ``executescript`` issues an implicit COMMIT first, which split a migration
    into two transactions and could leave DDL applied without its version row
    (M-050). ``PRAGMA foreign_keys`` is a no-op inside a transaction, so the
    table-rebuild migration uses ``defer_foreign_keys`` instead; the legacy
    toggles are skipped here.
    """
    conn.execute("PRAGMA defer_foreign_keys=ON")
    for statement in _split_statements(sql):
        normalized = " ".join(statement.lower().split())
        if normalized in ("pragma foreign_keys=off", "pragma foreign_keys=on"):
            continue
        conn.execute(statement)


def current_version(conn: sqlite3.Connection) -> int:
    """Return the highest applied migration version (0 if none)."""
    try:
        row = conn.execute("SELECT COALESCE(MAX(version), 0) AS v FROM schema_migration").fetchone()
    except sqlite3.Error as exc:
        raise DatabaseError(f"Failed to read schema_migration table: {exc}") from exc
    return int(row["v"]) if row is not None else 0


def applied_versions(conn: sqlite3.Connection) -> list[int]:
    """Return the list of applied migration versions."""
    rows = conn.execute("SELECT version FROM schema_migration ORDER BY version").fetchall()
    return [int(r["version"]) for r in rows]


def migrate(conn: sqlite3.Connection, schema_sql: str | None = None) -> list[int]:
    """Apply any pending migrations, returning the versions applied.

    The base schema (schema.sql) is applied first and recorded as version 1,
    then any entries in :data:`MIGRATIONS` with a higher version are applied.
    Each migration runs atomically inside a transaction.
    """
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migration (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')), description TEXT)")
    applied: list[int] = []

    if current_version(conn) == 0:
        conn.execute("BEGIN")
        try:
            if schema_sql:
                _execute_script_in_transaction(conn, schema_sql)
            conn.execute(
                "INSERT INTO schema_migration (version, description) VALUES (1, 'Initial schema')"
            )
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            conn.execute("ROLLBACK")
            raise DatabaseError(f"Migration 1 (initial schema) failed: {exc}") from exc
        applied.append(1)

    for migration in sorted(MIGRATIONS, key=lambda m: m.version):
        if migration.version <= current_version(conn):
            continue
        conn.execute("BEGIN")
        try:
            _execute_script_in_transaction(conn, migration.sql)
            conn.execute(
                "INSERT INTO schema_migration (version, description) VALUES (?, ?)",
                (migration.version, migration.description),
            )
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            conn.execute("ROLLBACK")
            raise DatabaseError(f"Migration {migration.version} ({migration.description}) failed: {exc}") from exc
        applied.append(migration.version)

    return applied
