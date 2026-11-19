"""Counterexamples from the fifth QA pass (2026-11-19): the QA answer
persistence path. qa.chat_service persists an answer row when it is given a
connection; the facade's _persist_answer then inserts the same id and, before
the fix, crashed with a UNIQUE-constraint IntegrityError that rolled back the
whole write transaction. Red on commit 39a21f6, green after the fix.
"""
from __future__ import annotations

import pytest

from geomemory.qa.chat_service import ChatService


@pytest.fixture()
def _citing_backend(monkeypatch):
    """Stub LLM backend producing a two-citation grounded answer."""

    from geomemory.core.models import GenerationRequest, GenerationResult

    class _TwoCitationBackend:
        model_id = "test-fake"

        def generate(self, request: GenerationRequest) -> GenerationResult:
            text = "Remote sensing [1] provides valuable data [2]."
            return GenerationResult(text=text, prompt_hash="h123", model_id=self.model_id)

        def count_tokens(self, text: str) -> int:
            return max(1, len(text) // 4)

    monkeypatch.setattr(
        "geomemory.qa.backend_factory.build_llm_backend",
        lambda settings: (_TwoCitationBackend(), 2000),
    )


@pytest.fixture()
def _two_docs(temp_workspace, tmp_path):
    col = temp_workspace.create_collection("docs")
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("# Overview\n\nRemote sensing covers Earth observation.\n")
    doc2 = tmp_path / "doc2.md"
    doc2.write_text("# Details\n\nSatellite sensors provide valuable data.\n")
    temp_workspace.ingest(doc1, collection_id=col.id)
    temp_workspace.ingest(doc2, collection_id=col.id)
    return temp_workspace


class TestAnswerPersistenceIdempotency:
    def test_ask_survives_chat_service_double_persist(
        self, temp_workspace, _citing_backend, _two_docs, monkeypatch
    ):
        """ChatService persisting first (conn given) must not crash ask()."""
        real_init = ChatService.__init__

        def init_with_conn(self, *args, **kwargs):
            kwargs["conn"] = temp_workspace.conn
            real_init(self, *args, **kwargs)

        monkeypatch.setattr(ChatService, "__init__", init_with_conn)

        result = temp_workspace.ask("What is remote sensing?")
        assert result.abstained is False

        # The facade must have upserted the shared answer id with its own
        # assistant turn id — exactly one answer row, correctly linked.
        row = temp_workspace.conn.execute(
            "SELECT id, turn_id FROM answer"
        ).fetchone()
        assert row is not None
        turn = temp_workspace.conn.execute(
            "SELECT id, role FROM turn WHERE id = ?", (row["turn_id"],)
        ).fetchone()
        assert turn is not None and turn["role"] == "assistant"
        count = temp_workspace.conn.execute(
            "SELECT COUNT(*) AS n FROM answer"
        ).fetchone()
        assert count["n"] == 1
