"""Entities, candidate memories, proposals, and traversal capability."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from geomemory.core.models import (
    CandidateMemory,
    Entity,
    KnowledgeChangeProposal,
)
from geomemory.core.workspace_feedback import FeedbackMixin


class KnowledgeMixin(FeedbackMixin):
    # ── Public facade methods (server boundary) ────────────────────────────

    def list_entities(self, kind: str | None = None) -> list[Entity]:
        """Return workspace entities, optionally filtered by ``kind``."""
        from geomemory.storage.repositories.entity_repo import EntityRepository

        repo = EntityRepository(self.conn)
        wid = self._workspace_id()
        if kind is not None:
            return repo.list_by_kind(kind, workspace_id=wid)
        return repo.list_by_workspace(wid)

    def get_entity_profile(self, name: str) -> dict[str, Any]:
        """Return entity profile: current beliefs, history, related entities."""
        from geomemory.services.entity_profile_service import EntityProfileService

        return EntityProfileService(self.conn).get_profile(name)

    def get_research_timeline(
        self,
        project: str,
        *,
        memory_types: list[str] | None = None,
        as_of: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return project research timeline, newest observation first."""
        from geomemory.services.research_timeline_service import ResearchTimelineService

        return ResearchTimelineService(self.conn).get_timeline(
            project,
            memory_types=memory_types,
            as_of=as_of,
            offset=offset,
            limit=limit,
        )

    def create_candidate_memory(
        self,
        content: str,
        memory_type: str = "correction",
        *,
        source_feedback_ids: list[str] | None = None,
        author: str | None = None,
    ) -> CandidateMemory:
        """Create a candidate memory entry."""
        from geomemory.services.candidate_memory_service import CandidateMemoryService

        return CandidateMemoryService(self.conn).create(
            content,
            memory_type=memory_type,
            source_feedback_ids=source_feedback_ids,
            author=author,
        )

    def get_candidate_memory(self, cm_id: str) -> CandidateMemory | None:
        """Return a candidate memory by id, or None."""
        from geomemory.services.candidate_memory_service import CandidateMemoryService

        return CandidateMemoryService(self.conn).get(cm_id)

    def score_candidate_memory(self, cm_id: str, signals: dict[str, Any] | None = None) -> float:
        """Score a candidate memory from feedback signals."""
        from geomemory.services.candidate_memory_service import CandidateMemoryService

        return CandidateMemoryService(self.conn).score(cm_id, signals)

    def promote_candidate_memory(
        self,
        cm_id: str,
        new_state: str,
        reviewer_id: str | None = None,
        note: str | None = None,
    ) -> CandidateMemory | None:
        """Promote/reject a candidate memory to a new state."""
        from geomemory.services.candidate_memory_service import CandidateMemoryService

        return CandidateMemoryService(self.conn).promote(cm_id, new_state, reviewer_id, note)

    def list_candidate_memories(
        self,
        state: str | None = None,
        *,
        states: Sequence[str] | None = None,
        min_observed_at: str | None = None,
    ) -> list[CandidateMemory]:
        """List candidate memories, optionally filtered by state(s) and temporal criteria."""
        from geomemory.services.candidate_memory_service import CandidateMemoryService

        return CandidateMemoryService(self.conn).list(state, states=states, min_observed_at=min_observed_at)

    def create_proposal(
        self,
        *,
        proposal_type: str,
        diff: dict[str, Any],
        source_candidate_ids: list[str],
        confidence: float = 0.8,
    ) -> KnowledgeChangeProposal:
        """Create a knowledge change proposal."""
        from geomemory.feedback.proposals import ProposalEngine

        return ProposalEngine(self.conn).create(
            proposal_type=proposal_type,
            diff=diff,
            source_candidate_ids=source_candidate_ids,
            confidence=confidence,
        )

    def list_proposals(self, status: str | None = None) -> list[KnowledgeChangeProposal]:
        """List knowledge change proposals, optionally filtered by status."""
        from geomemory.feedback.proposals import ProposalEngine

        return ProposalEngine(self.conn).list(status)

    def get_proposal(self, proposal_id: str) -> KnowledgeChangeProposal | None:
        """Return a knowledge change proposal by id, or None."""
        from geomemory.feedback.proposals import ProposalEngine

        return ProposalEngine(self.conn).get(proposal_id)

    def apply_proposal(
        self, proposal_id: str, reviewer: str = "human"
    ) -> KnowledgeChangeProposal:
        """Approve and apply a knowledge change proposal."""
        from geomemory.feedback.proposals import ProposalEngine

        return ProposalEngine(self.conn).apply(proposal_id, reviewer)

    def reject_proposal(
        self, proposal_id: str, reason: str = ""
    ) -> KnowledgeChangeProposal:
        """Reject a knowledge change proposal."""
        from geomemory.feedback.proposals import ProposalEngine

        return ProposalEngine(self.conn).reject(proposal_id, reason)

    def review_proposal(
        self,
        proposal_id: str,
        approve: bool,
        reviewer_id: str | None = None,
        note: str | None = None,
    ) -> KnowledgeChangeProposal | None:
        """Approve or reject a proposal."""
        from geomemory.feedback.proposals import ProposalEngine

        return ProposalEngine(self.conn).review(proposal_id, approve, reviewer_id, note)



    def traverse(
        self, entity_id: str, *, depth: int = 1
    ) -> dict[str, Any]:
        """Return an entity with its transitive relations up to *depth* (max 3)."""
        from geomemory.storage.repositories.entity_repo import EntityRepository

        max_depth = min(depth, 3)
        seen_relations: set[str] = set()
        hits: list[dict[str, Any]] = []
        total_hits = 0
        max_hits = 50

        def _fetch(current_id: str, current_depth: int) -> None:
            nonlocal total_hits
            if current_depth > max_depth or total_hits >= max_hits:
                return
            entity_row = self.conn.execute(
                "SELECT * FROM entity WHERE id = ?", (current_id,)
            ).fetchone()
            if entity_row is None:
                return
            entity = EntityRepository(self.conn)._load(entity_row)
            rows = self.conn.execute(
                "SELECT * FROM relation WHERE source_id = ? OR target_id = ?",
                (current_id, current_id),
            ).fetchall()
            for row in rows:
                rel_id = str(row["id"])
                if rel_id in seen_relations:
                    continue
                seen_relations.add(rel_id)
                src_id, tgt_id = str(row["source_id"]), str(row["target_id"])
                target_id = tgt_id if src_id == current_id else src_id
                target_row = self.conn.execute(
                    "SELECT * FROM entity WHERE id = ?", (target_id,)
                ).fetchone()
                target_entity = (
                    EntityRepository(self.conn)._load(target_row).model_dump(mode="json")
                    if target_row is not None
                    else None
                )
                hits.append(
                    {
                        "id": rel_id,
                        "predicate": row["predicate"],
                        "confidence": float(row["confidence"]),
                        "source": entity.model_dump(mode="json"),
                        "target": target_entity,
                    }
                )
                total_hits += 1
                if total_hits < max_hits:
                    _fetch(target_id, current_depth + 1)

        _fetch(entity_id, 0)
        first_entity = None
        if hits:
            first_entity = hits[0]["source"]
        return {"entity": first_entity, "relations": hits}

