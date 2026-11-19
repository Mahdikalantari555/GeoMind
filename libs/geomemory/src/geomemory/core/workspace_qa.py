"""Grounded QA capability of the workspace facade."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from geomemory.core.models import (
    QAResult,
    SearchFilters,
    Turn,
)
from geomemory.core.workspace_search import SearchMixin, _WorkspaceSearchAdapter


class QAMixin(SearchMixin):
    # ── QA ──────────────────────────────────────────────────────────────────

    def ask(
        self,
        question: str,
        *,
        mode: str = "grounded_qa",
        collections: list[str] | None = None,
        filters: SearchFilters | None = None,
        modalities: Literal["text", "image", "both"] | None = None,
        modality_weight: float = 0.7,
    ) -> QAResult:
        """Answer a question using retrieved context.

        Without a loaded LLM, the system abstains with a clear reason.
        Grounded answers require a local GGUF model configured in settings.
        """
        if not (question or "").strip():
            return QAResult(
                text="",
                abstained=True,
                abstention_reason="Empty question",
                model="none",
            )
        result = self.search(
            question,
            collections=collections,
            spatial=filters.spatial if filters else None,
            temporal=filters.temporal if filters else None,
            sensor=filters.sensors if filters else None,
            modalities=modalities,
            modality_weight=modality_weight,
        )
        if not result.hits:
            return QAResult(
                text="not found in selected sources",
                abstained=True,
                abstention_reason="No relevant context found",
                sources=result.hits,
                retrieval_run_id=result.retrieval_run_id,
                latency_ms=result.latency_ms,
                model="none",
            )
        # Grounded QA via the QA chat service (search → pack → generate → cite).
        from geomemory.qa.backend_factory import LLMBackendUnavailableError, build_llm_backend
        from geomemory.qa.chat_service import ChatService as QAChatService

        try:
            backend, token_budget = build_llm_backend(self.settings)
        except LLMBackendUnavailableError as exc:
            return QAResult(
                text="not found in selected sources",
                abstained=True,
                abstention_reason=str(exc),
                sources=result.hits,
                retrieval_run_id=result.retrieval_run_id,
                latency_ms=result.latency_ms,
                model="none",
            )
        chat = QAChatService(
            _WorkspaceSearchAdapter(
                self,
                collections=collections,
                modalities=modalities,
                modality_weight=modality_weight,
            ),
            backend,
            token_budget=token_budget,
        )
        answer = chat.ask(
            question,
            mode=mode,
            filters=filters,
            modalities=modalities,
            modality_weight=modality_weight,
            search_result=result,
        )
        self._persist_answer(question, answer)
        return answer

    def _persist_answer(self, question: str, answer: QAResult) -> None:
        """Persist a QA exchange (conversation, turns, answer, citations)."""
        from geomemory.core.models import Answer, Conversation
        from geomemory.storage.repositories.conversation_repo import (
            ConversationRepository,
            TurnRepository,
        )

        conv = Conversation(
            workspace_id=self._workspace_id(),
            title=(question or "")[:80],
        )
        with self._write_tx():
            ConversationRepository(self.conn).create(conv, commit=False)
            user_turn = Turn(conversation_id=conv.id, role="user", content=question)
            TurnRepository(self.conn).create(user_turn, commit=False)
            assistant_turn = Turn(
                conversation_id=conv.id,
                role="assistant",
                content=answer.text,
                metadata={"abstained": answer.abstained},
            )
            TurnRepository(self.conn).create(assistant_turn, commit=False)

            prompt_hash = hashlib.sha256((question or "").encode("utf-8")).hexdigest()
            existing_answer_id = (
                answer.citations[0].answer_id
                if (answer.citations and answer.citations[0].answer_id)
                else None
            )
            answer_row = (
                Answer(
                    id=existing_answer_id,
                    turn_id=assistant_turn.id,
                    model=answer.model or "none",
                    prompt_hash=prompt_hash,
                    text=answer.text,
                    abstained=answer.abstained,
                )
                if existing_answer_id
                else Answer(
                    turn_id=assistant_turn.id,
                    model=answer.model or "none",
                    prompt_hash=prompt_hash,
                    text=answer.text,
                    abstained=answer.abstained,
                )
            )
            self.conn.execute(
                "INSERT INTO answer "
                "(id, turn_id, model, prompt_hash, text, abstained, created_at, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    answer_row.id,
                    answer_row.turn_id,
                    answer_row.model,
                    answer_row.prompt_hash,
                    answer_row.text,
                    1 if answer_row.abstained else 0,
                    answer_row.created_at,
                    json.dumps(answer_row.metadata),
                ),
            )
            for citation in answer.citations:
                citation.answer_id = answer_row.id
                # Image scenes are valid QA sources but are not rows in ``segment``.
                # Keep them in the returned citation list without violating the
                # text-segment foreign key in the persistence schema.
                if citation.locator.get("target_type") == "raster_tile":
                    continue
                # Candidate memories and other non-segment sources are returned
                # to the caller but cannot satisfy the citation's segment FK.
                segment = self.conn.execute(
                    "SELECT 1 FROM segment WHERE id = ? LIMIT 1", (citation.segment_id,)
                ).fetchone()
                if segment is None:
                    continue
                self.conn.execute(
                    "INSERT INTO citation (id, answer_id, segment_id, locator, claim_span, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        citation.id,
                        answer_row.id,
                        citation.segment_id,
                        json.dumps(citation.locator),
                        json.dumps(citation.claim_span) if citation.claim_span else None,
                        citation.created_at,
                    ),
                )

