"""ResearchTimelineService — project-scoped chronological view of candidate memories."""

from __future__ import annotations

import sqlite3
from typing import Any

from geomemory.core.models import CandidateMemory
from geomemory.feedback.candidate_memory import _row_to_cm


class ResearchTimelineService:
    """Timeline queries over candidate memories, ordered by observed_at DESC."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get_timeline(
        self,
        project: str,
        memory_types: list[str] | None = None,
        as_of: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return {project, items, total} for a project, newest observation first."""
        where = ["project = ?"]
        params: list[object] = [project]
        if memory_types:
            where.append(f"memory_type IN ({','.join('?' * len(memory_types))})")
            params.extend(memory_types)
        if as_of:
            where.append("COALESCE(observed_at, created_at) <= ?")
            params.append(as_of)
        clause = " AND ".join(where)

        total_row = self.conn.execute(
            f"SELECT COUNT(*) AS c FROM candidate_memory WHERE {clause}", params
        ).fetchone()
        total = int(total_row["c"]) if total_row is not None else 0

        rows = self.conn.execute(
            f"SELECT * FROM candidate_memory WHERE {clause}"
            " ORDER BY COALESCE(observed_at, created_at) DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        items: list[CandidateMemory] = [_row_to_cm(r) for r in rows]
        return {"project": project, "items": items, "total": total}
