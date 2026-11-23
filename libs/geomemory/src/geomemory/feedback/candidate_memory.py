"""CandidateMemory repository helpers."""

from __future__ import annotations

import builtins
import json
import re
import sqlite3
from collections.abc import Sequence
from typing import Any

from geomemory.core.models import CandidateMemory, utc_now

_FTS_TERM_RE = re.compile(r"\w+", re.UNICODE)


def _row_to_cm(row: sqlite3.Row) -> CandidateMemory:
    data = dict(row)
    for k in ("source_feedback_ids", "audit_trail"):
        if isinstance(data.get(k), str):
            try:
                data[k] = json.loads(data[k])
            except Exception:
                data[k] = []
    return CandidateMemory(**data)


class CandidateMemoryRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(self, cm: CandidateMemory) -> CandidateMemory:
        self.conn.execute(
            "INSERT INTO candidate_memory (id, content, memory_type, source_feedback_ids, confidence_score, state, author, audit_trail, created_at, updated_at, observed_at, superseded_by, project) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                cm.id,
                cm.content,
                cm.memory_type,
                json.dumps(cm.source_feedback_ids),
                cm.confidence_score,
                cm.state,
                cm.author,
                json.dumps(cm.audit_trail),
                cm.created_at,
                cm.updated_at,
                cm.observed_at,
                cm.superseded_by,
                cm.project,
            ),
        )
        self.conn.commit()
        return cm

    def get(self, cm_id: str) -> CandidateMemory | None:
        row = self.conn.execute("SELECT * FROM candidate_memory WHERE id=?", (cm_id,)).fetchone()
        return _row_to_cm(row) if row else None

    def list(
        self,
        state: str | None = None,
        *,
        states: Sequence[str] | None = None,
        min_observed_at: str | None = None,
    ) -> builtins.list[CandidateMemory]:
        clauses: list[str] = []
        params: list[Any] = []

        if states:
            placeholders = ",".join("?" for _ in states)
            clauses.append(f"state IN ({placeholders})")
            params.extend(states)
        elif state:
            clauses.append("state = ?")
            params.append(state)

        if min_observed_at:
            clauses.append("observed_at >= ?")
            params.append(min_observed_at)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM candidate_memory {where_sql} ORDER BY updated_at DESC"
        rows = self.conn.execute(query, tuple(params)).fetchall()
        return [_row_to_cm(r) for r in rows]

    def promote(self, cm_id: str, new_state: str, reviewer_id: str | None, note: str | None, *, allow_regression: bool = False) -> CandidateMemory | None:
        cm = self.get(cm_id)
        if not cm:
            return None
        # validate transition: proposed->supported->verified|rejected, etc.
        valid = {
            "proposed": {"supported", "rejected"},
            "supported": {"verified", "rejected"},
            "verified": {"rejected"},
            "rejected": set(),
        }
        if new_state not in valid.get(cm.state, set()) and new_state != cm.state:
            # allow direct to rejected from any non-rejected
            if new_state == "rejected" and cm.state != "rejected":
                pass
            elif allow_regression:
                pass  # score-driven backward transition
            elif new_state != cm.state:
                raise ValueError(f"Invalid transition {cm.state} -> {new_state}")
        audit = list(cm.audit_trail)
        audit.append({"action": "promote", "to_state": new_state, "reviewer_id": reviewer_id, "note": note, "timestamp": utc_now()})
        updated_at = utc_now()
        self.conn.execute(
            "UPDATE candidate_memory SET state=?, audit_trail=?, updated_at=? WHERE id=?",
            (new_state, json.dumps(audit), updated_at, cm_id),
        )
        self.conn.commit()
        return self.get(cm_id)

    def update_score(self, cm_id: str, score: float) -> None:
        self.conn.execute("UPDATE candidate_memory SET confidence_score=?, updated_at=? WHERE id=?", (score, utc_now(), cm_id))
        self.conn.commit()

    def search(self, query: str, min_score: float = 0, *, include_superseded: bool = False) -> builtins.list[CandidateMemory]:
        """Search candidate memories by term via FTS5.

        The old ``LIKE '%query%'`` full scan could not use an index and let
        user-supplied ``%``/``_`` change the match semantics (P-074). The FTS
        index is maintained by triggers (migration 8); fall back to an escaped
        LIKE only on databases created without that migration.
        """
        terms = [term for term in _FTS_TERM_RE.findall(query) if term]
        if not terms:
            return []
        fts_query = " OR ".join(f'"{term}"' for term in terms)
        sql = (
            "SELECT cm.* FROM candidate_memory_fts f "
            "JOIN candidate_memory cm ON cm.rowid = f.rowid "
            "WHERE candidate_memory_fts MATCH ? AND cm.confidence_score >= ?"
        )
        params: builtins.list[object] = [fts_query, min_score]
        if not include_superseded:
            sql += " AND cm.superseded_by IS NULL"
        sql += " ORDER BY cm.confidence_score DESC"
        try:
            rows = self.conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            # Legacy DB without the FTS table: keep LIKE but neutralise
            # wildcard characters in the user's query.
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            fallback = (
                "SELECT * FROM candidate_memory "
                "WHERE confidence_score >= ? AND content LIKE ? ESCAPE '\\'"
            )
            params = [min_score, f"%{escaped}%"]
            if not include_superseded:
                fallback += " AND superseded_by IS NULL"
            fallback += " ORDER BY confidence_score DESC"
            rows = self.conn.execute(fallback, params).fetchall()
        return [_row_to_cm(r) for r in rows]

    def _revision_chain(self, cm_id: str) -> builtins.list[CandidateMemory]:
        """Collect the supersession chain around cm_id in both directions."""
        seen: dict[str, CandidateMemory] = {}
        frontier = [cm_id]
        while frontier:
            row = self.conn.execute(
                "SELECT * FROM candidate_memory WHERE id = ?", (frontier.pop(),)
            ).fetchone()
            if row is None:
                continue
            cm = _row_to_cm(row)
            if cm.id in seen:
                continue
            seen[cm.id] = cm
            if cm.superseded_by and cm.superseded_by not in seen:
                frontier.append(cm.superseded_by)
            predecessors = self.conn.execute(
                "SELECT id FROM candidate_memory WHERE superseded_by = ?", (cm.id,)
            ).fetchall()
            frontier.extend(p["id"] for p in predecessors if p["id"] not in seen)
        return list(seen.values())

    def get_as_of(self, cm_id: str, as_of: str) -> CandidateMemory | None:
        """Return the latest revision of the item whose observed_at <= as_of."""
        visible = [cm for cm in self._revision_chain(cm_id) if cm.effective_observed_at <= as_of]
        if not visible:
            return None
        return max(visible, key=lambda cm: (cm.effective_observed_at, cm.updated_at))

    def mark_superseded(self, cm_id: str, by_id: str) -> None:
        """Point cm_id at the row that replaced it (self-FK, ON DELETE SET NULL)."""
        self.conn.execute(
            "UPDATE candidate_memory SET superseded_by = ?, updated_at = ? WHERE id = ?",
            (by_id, utc_now(), cm_id),
        )
        self.conn.commit()

    def list_by_project(
        self,
        project: str,
        types: builtins.list[str] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> builtins.list[CandidateMemory]:
        """List a project's candidate memories, newest observed first, paginated."""
        sql = "SELECT * FROM candidate_memory WHERE project = ?"
        params: builtins.list[object] = [project]
        if types:
            sql += f" AND memory_type IN ({','.join('?' * len(types))})"
            params.extend(types)
        sql += " ORDER BY COALESCE(observed_at, created_at) DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self.conn.execute(sql, params).fetchall()
        return [_row_to_cm(r) for r in rows]
