import pytest

from geomemory import GeoMemory
from geomemory.core.models import GenerationRequest, GenerationResult
from geomemory.qa.backend import NullBackend


def test_candidate_citation_is_returned_but_not_persisted(
    temp_workspace: GeoMemory, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = "The corrected threshold is 0.6 [1]."

    class CandidateBackend(NullBackend):
        model_id = "test-candidate"

        def generate(self, request: GenerationRequest) -> GenerationResult:
            return GenerationResult(text=text, prompt_hash="candidate", model_id=self.model_id)

    monkeypatch.setattr(
        "geomemory.qa.backend_factory.build_llm_backend",
        lambda settings: (CandidateBackend(), 2000),
    )
    ws = temp_workspace
    candidate = ws.create_candidate_memory("The NDVI threshold is 0.6.")
    assert ws.promote_candidate_memory(candidate.id, "supported") is not None

    answer = ws.ask("NDVI threshold")
    assert not answer.abstained
    assert answer.text == text
    assert [citation.segment_id for citation in answer.citations] == [candidate.id]
    answer_id = answer.citations[0].answer_id
    row = ws.conn.execute("SELECT text FROM answer WHERE id = ?", (answer_id,)).fetchone()
    assert row["text"] == text
    assert not ws.conn.execute(
        "SELECT 1 FROM citation WHERE answer_id = ?", (answer_id,)
    ).fetchall()
