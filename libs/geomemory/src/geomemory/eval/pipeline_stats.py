"""Pipeline statistics collection after a full ingestion run.

Queries the production database tables (no eval-specific ingestion logic) and
walks the workspace directory for on-disk size. Emits a stable ``stats.json``
schema so runs across GeoMemory versions remain comparable.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

# The eight numeric fields the stats schema guarantees. Used by tests and the
# JSON serializer to keep the schema stable across versions.
STATS_FIELDS: tuple[str, ...] = (
    "files",
    "documents",
    "chunks",
    "embeddings",
    "entities",
    "relations",
    "duration_seconds",
    "storage_bytes",
)


def _count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
    return int(row["c"]) if row is not None else 0


def _directory_size(path: Path) -> int:
    """Total on-disk size of every file under ``path`` (0 if absent)."""
    if not path.is_dir():
        return 0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                continue
    return total


def collect_stats(
    conn: sqlite3.Connection,
    path: str | Path,
    *,
    duration_seconds: float = 0.0,
) -> dict[str, Any]:
    """Collect pipeline statistics for a workspace after a complete ingestion.

    ``path`` is the workspace directory (used for ``storage_bytes``).
    ``duration_seconds`` is the wall-clock duration of the ingestion phase;
    callers measure it, this function records it.
    """
    files = _count(conn, "asset")
    documents = _count(conn, "asset_revision")
    chunks = _count(conn, "segment")
    embeddings = _count(conn, "embedding_record")
    entities = _count(conn, "entity")
    relations = _count(conn, "relation")
    storage_bytes = _directory_size(Path(path))

    return {
        "files": files,
        "documents": documents,
        "chunks": chunks,
        "embeddings": embeddings,
        "entities": entities,
        "relations": relations,
        "duration_seconds": float(duration_seconds),
        "storage_bytes": int(storage_bytes),
    }


def stats_to_json(stats: dict[str, Any]) -> str:
    """Serialize stats to JSON, guaranteeing all eight numeric fields."""
    import json

    payload = {field: stats.get(field, 0) for field in STATS_FIELDS}
    # Coerce to plain JSON numbers (never strings).
    out: dict[str, Any] = {}
    for field in STATS_FIELDS:
        value = payload[field]
        if field == "duration_seconds":
            out[field] = float(value)
        else:
            out[field] = int(value)
    return json.dumps(out, sort_keys=True, indent=2)


def is_valid_stats(stats: Any) -> bool:
    """Return True when ``stats`` has all eight numeric fields."""
    if not isinstance(stats, dict):
        return False
    for field in STATS_FIELDS:
        if field not in stats:
            return False
        value = stats[field]
        if isinstance(value, bool):
            return False
        if not isinstance(value, (int, float)):
            return False
    return True


__all__ = [
    "STATS_FIELDS",
    "collect_stats",
    "is_valid_stats",
    "stats_to_json",
]
