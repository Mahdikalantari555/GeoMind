"""Unit tests for QA building blocks: abstention, citations, context packing."""

from __future__ import annotations

from geomemory.core.models import GenerationRequest, SearchHit
from geomemory.qa.abstention import abstention_reason, should_abstain
from geomemory.qa.backend import NullBackend
from geomemory.qa.citation import extract_citation_keys, map_citations, validate_citations
from geomemory.retrieval.context_packer import estimate_tokens, format_context, pack_context


class TestAbstention:
    def test_detects_phrase(self):
        assert should_abstain("I do not know the answer")
        assert should_abstain("not found in selected sources")

    def test_normal_text_is_not_abstention(self):
        assert not should_abstain("The NDVI value is 0.6")

    def test_reason_nonempty(self):
        assert abstention_reason("") == "Empty answer generated"


class TestCitation:
    def test_extract_keys(self):
        assert extract_citation_keys("Flood [1] and [2] extent") == [1, 2]

    def test_map_citations_to_sources(self):
        sources = [SearchHit(id="s1"), SearchHit(id="s2")]
        citations = map_citations("ans-1", "Text [2]", sources)
        assert len(citations) == 1
        assert citations[0].segment_id == "s2"

    def test_out_of_range_key_ignored(self):
        sources = [SearchHit(id="s1")]
        assert map_citations("ans-1", "Text [5]", sources) == []

    def test_validate_citations(self):
        sources = [SearchHit(id="s1")]
        citations = map_citations("ans-1", "Text [1]", sources)
        assert validate_citations(citations, sources) is True


class TestContextPacker:
    def test_estimate_tokens(self):
        assert estimate_tokens("abcd") == 1

    def test_pack_within_budget(self):
        hits = [SearchHit(id="s1", text="x" * 100), SearchHit(id="s2", text="y" * 100)]
        packed = pack_context(hits, token_budget=40, per_hit_budget=25)
        assert len(packed) == 1
        assert packed[0].id == "s1"

    def test_format_context_numbered(self):
        hits = [SearchHit(id="s1", locator={"page": 3}, text="body")]
        out = format_context(hits)
        assert "[1]" in out
        assert "page=3" in out


class TestNullBackend:
    def test_generate_abstains(self):
        backend = NullBackend()
        result = backend.generate(GenerationRequest(prompt="q"))
        assert result.abstained is True
        assert "not found" in result.text

    def test_count_tokens(self):
        assert NullBackend().count_tokens("abcd") >= 1


class TestCitationProvenance:
    """Regression tests for citation answer_id provenance integrity."""

    def test_citation_answer_id_matches_persisted_answer(
        self, temp_workspace, monkeypatch, tmp_path
    ):
        from geomemory.core.models import GenerationRequest, GenerationResult

        class _TwoCitationBackend:
            model_id = "test-fake"

            def generate(self, request: GenerationRequest) -> GenerationResult:
                text = "Remote sensing [1] provides valuable data [2]."
                return GenerationResult(
                    text=text, prompt_hash="h123", model_id=self.model_id
                )

            def count_tokens(self, text: str) -> int:
                return max(1, len(text) // 4)

        monkeypatch.setattr(
            "geomemory.qa.backend_factory.build_llm_backend",
            lambda settings: (_TwoCitationBackend(), 2000),
        )

        ws = temp_workspace
        col = ws.create_collection("docs")

        doc1 = tmp_path / "doc1.md"
        doc1.write_text("# Overview\n\nRemote sensing covers Earth observation.\n")
        doc2 = tmp_path / "doc2.md"
        doc2.write_text("# Details\n\nSatellite sensors provide valuable data.\n")

        ws.ingest(doc1, collection_id=col.id)
        ws.ingest(doc2, collection_id=col.id)

        result = ws.ask("What is remote sensing?")
        assert result.abstained is False
        assert len(result.citations) >= 2

        answer_id = result.citations[0].answer_id
        assert isinstance(answer_id, str)
        assert len(answer_id) > 0
        assert answer_id.startswith("ans_")

        row = ws.conn.execute("SELECT id FROM answer").fetchone()
        assert row is not None
        assert answer_id == row["id"]
        assert result.citations[1].answer_id == row["id"]

    def test_abstention_returns_empty_citations(self, temp_workspace, sample_markdown):
        ws = temp_workspace
        col = ws.create_collection("docs")
        ws.ingest(sample_markdown, collection_id=col.id)

        result = ws.ask("What is NDVI?")
        assert result.abstained is True
        assert len(result.citations) == 0

