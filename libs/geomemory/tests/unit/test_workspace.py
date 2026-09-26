"""Tests for the workspace lifecycle and GeoMemory public API."""

from __future__ import annotations

from pathlib import Path

import pytest

from geomemory import GeoMemory
from geomemory.core.exceptions import (
    CollectionNotFoundError,
    WorkspaceExistsError,
    WorkspaceNotFoundError,
)


class TestWorkspaceLifecycle:
    def test_create_and_open(self, tmp_path):
        path = tmp_path / "ws"
        ws = GeoMemory.create(path)
        assert (path / ".geomemory").is_file()
        assert (path / "workspace.yaml").is_file()
        assert (path / "geomemory.db").is_file()
        ws.close()

        reopened = GeoMemory.open(path)
        assert reopened.settings.name == "GeoMemory Workspace"
        reopened.close()

    def test_open_missing_raises(self, tmp_path):
        with pytest.raises(WorkspaceNotFoundError):
            GeoMemory.open(tmp_path / "nope")

    def test_create_nonempty_raises(self, tmp_path):
        path = tmp_path / "ws"
        path.mkdir()
        (path / "file.txt").write_text("x")
        with pytest.raises(WorkspaceExistsError):
            GeoMemory.create(path)

    def test_context_manager(self, tmp_path):
        with GeoMemory.create(tmp_path / "ws") as ws:
            assert ws.conn is not None
        # After exit, connection is closed.
        assert ws._closed


class TestCollections:
    def test_create_and_list(self, temp_workspace):
        col = temp_workspace.create_collection("papers", "RS papers")
        assert col.name == "papers"
        cols = temp_workspace.list_collections()
        assert len(cols) == 1
        assert cols[0].id == col.id

    def test_get_collection(self, temp_workspace):
        col = temp_workspace.create_collection("data")
        assert temp_workspace.get_collection(col.id) is not None
        assert temp_workspace.get_collection("missing") is None

    def test_archive_collection(self, temp_workspace):
        col = temp_workspace.create_collection("old")
        assert temp_workspace.archive_collection(col.id) is True
        assert temp_workspace.get_collection(col.id) is None
        assert temp_workspace.list_collections() == []


class TestIngestion:
    def test_ingest_markdown(self, temp_workspace, sample_markdown):
        col = temp_workspace.create_collection("docs")
        job = temp_workspace.ingest(sample_markdown, collection_id=col.id)
        assert job.state == "completed"
        assert job.result["segment_count"] > 0
        assets = temp_workspace.list_assets(col.id)
        assert len(assets) == 1
        assert assets[0].kind == "document"

    def test_ingest_bytes(self, temp_workspace):
        col = temp_workspace.create_collection("docs")
        job = temp_workspace.ingest(b"hello world bytes", collection_id=col.id)
        assert job.state == "completed"

    def test_ingest_duplicate_dedup(self, temp_workspace, sample_markdown):
        col = temp_workspace.create_collection("docs")
        temp_workspace.ingest(sample_markdown, collection_id=col.id)
        job2 = temp_workspace.ingest(sample_markdown, collection_id=col.id)
        assert job2.result["skipped"] is True
        assert len(temp_workspace.list_assets(col.id)) == 1

    def test_ingest_missing_collection(self, temp_workspace, sample_markdown):
        with pytest.raises(CollectionNotFoundError):
            temp_workspace.ingest(sample_markdown, collection_id="missing")

    def test_ingest_missing_file(self, temp_workspace):
        col = temp_workspace.create_collection("docs")
        with pytest.raises(FileNotFoundError):
            temp_workspace.ingest(Path("/nonexistent/file.txt"), collection_id=col.id)


class TestSearch:
    def test_search_returns_hits(self, temp_workspace, sample_markdown):
        col = temp_workspace.create_collection("docs")
        temp_workspace.ingest(sample_markdown, collection_id=col.id)
        result = temp_workspace.search("NDVI crop stress")
        assert result.total_hits > 0
        assert result.retrieval_run_id is not None
        assert result.latency_ms is not None

    def test_search_empty_query(self, temp_workspace):
        result = temp_workspace.search("")
        assert result.hits == []
        assert result.total_hits == 0

    def test_search_no_results(self, temp_workspace):
        result = temp_workspace.search("zzzznothingmatches")
        assert result.hits == []

    def test_search_collection_filter(self, temp_workspace, sample_markdown):
        col = temp_workspace.create_collection("docs")
        temp_workspace.ingest(sample_markdown, collection_id=col.id)
        result = temp_workspace.search("NDVI", collections=[col.id])
        assert result.total_hits > 0
        result2 = temp_workspace.search("NDVI", collections=["nonexistent"])
        assert result2.hits == []


class TestAsk:
    def test_ask_empty(self, temp_workspace):
        answer = temp_workspace.ask("")
        assert answer.abstained is True

    def test_ask_no_evidence(self, temp_workspace):
        answer = temp_workspace.ask("What is the meaning of life?")
        assert answer.abstained is True
        assert "not found" in answer.text

    def test_ask_no_llm_abstains(self, temp_workspace, sample_markdown):
        col = temp_workspace.create_collection("docs")
        temp_workspace.ingest(sample_markdown, collection_id=col.id)
        answer = temp_workspace.ask("What is NDVI?")
        assert answer.abstained is True
        assert "LLM backend" in answer.abstention_reason


class TestAskWithBackend:
    """Grounded QA with a configured (fake) LLM backend."""

    def _patch_factory(self, monkeypatch, fake_backend):

        def _fake_factory(settings):
            return fake_backend, 2000

        monkeypatch.setattr(
            "geomemory.qa.backend_factory.build_llm_backend", _fake_factory
        )

    def test_ask_generates_answer_with_citations(
        self, temp_workspace, sample_markdown, monkeypatch
    ):
        from geomemory.core.models import GenerationRequest, GenerationResult

        class _FakeBackend:
            model_id = "fake"

            def generate(self, request: GenerationRequest) -> GenerationResult:
                text = request.context[0].text + " [1]" if request.context else ""
                return GenerationResult(text=text, prompt_hash="h", model_id=self.model_id)

            def count_tokens(self, text: str) -> int:
                return max(1, len(text) // 4)

        self._patch_factory(monkeypatch, _FakeBackend())
        ws = temp_workspace
        col = ws.create_collection("docs")
        ws.ingest(sample_markdown, collection_id=col.id)

        answer = ws.ask("What is NDVI?")
        assert answer.abstained is False
        assert "NDVI" in answer.text
        assert len(answer.citations) == 1
        assert answer.citations[0].segment_id == answer.sources[0].id
        assert answer.model == "fake"

    def test_ask_persists_answer_and_citations(self, temp_workspace, sample_markdown, monkeypatch):
        from geomemory.core.models import GenerationRequest, GenerationResult

        class _FakeBackend:
            model_id = "fake"

            def generate(self, request: GenerationRequest) -> GenerationResult:
                text = request.context[0].text + " [1]" if request.context else ""
                return GenerationResult(text=text, prompt_hash="h", model_id=self.model_id)

            def count_tokens(self, text: str) -> int:
                return max(1, len(text) // 4)

        self._patch_factory(monkeypatch, _FakeBackend())
        ws = temp_workspace
        col = ws.create_collection("docs")
        ws.ingest(sample_markdown, collection_id=col.id)

        answer = ws.ask("What is NDVI?")
        assert answer.abstained is False

        # Conversation + turns persisted.
        convs = ws.conn.execute("SELECT * FROM conversation").fetchall()
        assert len(convs) == 1
        turns = ws.conn.execute("SELECT * FROM turn ORDER BY created_at").fetchall()
        assert len(turns) == 2
        assert turns[0]["role"] == "user"
        assert turns[1]["role"] == "assistant"

        # Answer + citation persisted.
        answers = ws.conn.execute("SELECT * FROM answer").fetchall()
        assert len(answers) == 1
        assert answers[0]["model"] == "fake"
        assert answers[0]["abstained"] == 0
        citations = ws.conn.execute("SELECT * FROM citation").fetchall()
        assert len(citations) == 1
        assert citations[0]["segment_id"] == answer.citations[0].segment_id

    def test_ask_api_provider_without_key_abstains(self, temp_workspace, sample_markdown, monkeypatch):
        monkeypatch.delenv("GEOMEMORY_LLM_API_KEY", raising=False)
        ws = temp_workspace
        col = ws.create_collection("docs")
        ws.ingest(sample_markdown, collection_id=col.id)
        ws.settings.llm_provider = "api"
        ws.settings.offline = False
        answer = ws.ask("What is NDVI?")
        assert answer.abstained is True
        assert "API key" in answer.abstention_reason

    def test_ask_token_budget_passed_to_service(self, temp_workspace, sample_markdown, monkeypatch):
        from geomemory.core.models import GenerationRequest, GenerationResult, QAResult
        from geomemory.qa.chat_service import ChatService

        captured = {}

        class _FakeBackend:
            model_id = "fake"

            def generate(self, request: GenerationRequest) -> GenerationResult:
                return GenerationResult(text="ok [1]", prompt_hash="h", model_id=self.model_id)

            def count_tokens(self, text: str) -> int:
                return max(1, len(text) // 4)

        class _FakeChatService(ChatService):
            def __init__(self, search_service, llm_backend, *, token_budget=2000, **kw):
                captured["token_budget"] = token_budget
                super().__init__(search_service, llm_backend, token_budget=token_budget, **kw)

            def ask(self, question, **kw):
                return QAResult(text="ok", abstained=False, model=self.llm_backend.model_id)

        monkeypatch.setattr(
            "geomemory.qa.backend_factory.build_llm_backend",
            lambda settings: (_FakeBackend(), 2000),
        )
        monkeypatch.setattr("geomemory.qa.chat_service.ChatService", _FakeChatService)
        ws = temp_workspace
        col = ws.create_collection("docs")
        ws.ingest(sample_markdown, collection_id=col.id)

        ws.ask("What is NDVI?")
        assert captured["token_budget"] == 2000


class TestInspect:
    def test_inspect_asset(self, temp_workspace, sample_markdown):
        col = temp_workspace.create_collection("docs")
        job = temp_workspace.ingest(sample_markdown, collection_id=col.id)
        detail = temp_workspace.inspect(job.result["asset_id"])
        assert detail.asset.id == job.result["asset_id"]
        assert detail.revision is not None
        assert len(detail.segments) > 0
        # Regression: AssetDetail must expose `layers` (vector layers) so the
        # dashboard Assets page does not raise AttributeError. Defaults to [].
        assert hasattr(detail, "layers")
        assert detail.layers == []


class TestWorkspaceSearchFilters:
    def test_search_filters_spatial_temporal_sensor(self, temp_workspace, sample_markdown):
        from geomemory.core.models import SpatialFilter, TemporalFilter

        col = temp_workspace.create_collection("docs")
        temp_workspace.ingest(sample_markdown, collection_id=col.id)

        # Test search with spatial filter
        spatial = SpatialFilter(bbox=(-120.0, 35.0, -119.0, 36.0))
        res_spatial = temp_workspace.search("NDVI", spatial=spatial)
        assert isinstance(res_spatial.hits, list)

        # Test search with temporal filter
        temporal = TemporalFilter(from_="2023-01-01T00:00:00Z", to="2023-12-31T23:59:59Z")
        res_temp = temp_workspace.search("NDVI", temporal=temporal)
        assert isinstance(res_temp.hits, list)

        # Test search with sensor filter
        res_sensor = temp_workspace.search("NDVI", sensor=["sentinel-2"])
        assert isinstance(res_sensor.hits, list)

        # Test expand_relations=True
        res_rel = temp_workspace.search("NDVI", expand_relations=True)
        assert res_rel.total_hits > 0

    def test_search_modalities_and_weights(self, temp_workspace, sample_markdown):
        col = temp_workspace.create_collection("docs")
        temp_workspace.ingest(sample_markdown, collection_id=col.id)

        # Invalid modality_weight raises ValueError
        with pytest.raises(ValueError, match="modality_weight must be between 0 and 1"):
            temp_workspace.search("NDVI", modality_weight=1.5)

        # Search with modalities="image"
        res_img = temp_workspace.search("NDVI", modalities="image")
        assert isinstance(res_img.hits, list)

        # Search with modalities="both"
        res_both = temp_workspace.search("NDVI", modalities="both")
        assert isinstance(res_both.hits, list)


class TestWorkspaceCandidateMemories:
    def test_candidate_memory_lifecycle(self, temp_workspace):
        # Create
        cm = temp_workspace.create_candidate_memory("NDVI threshold for wheat is 0.45", memory_type="fact", author="tester")
        assert cm.id is not None
        assert cm.content == "NDVI threshold for wheat is 0.45"
        assert cm.state == "proposed"

        # Get
        fetched = temp_workspace.get_candidate_memory(cm.id)
        assert fetched is not None
        assert fetched.id == cm.id

        # Missing get
        assert temp_workspace.get_candidate_memory("missing-cm-id") is None

        # List with state filter before score
        proposed_list = temp_workspace.list_candidate_memories(state="proposed")
        assert any(item.id == cm.id for item in proposed_list)

        # Score
        score = temp_workspace.score_candidate_memory(cm.id, {"confirming": 3})
        assert isinstance(score, float)

        # Promote to verified
        promoted = temp_workspace.promote_candidate_memory(cm.id, "verified", reviewer_id="rev-1", note="good")
        assert promoted is not None
        assert promoted.state == "verified"

        # List with states sequence
        verified_list = temp_workspace.list_candidate_memories(states=["verified"])
        assert any(item.id == cm.id for item in verified_list)

        # Candidate hits surfaced in search (exact substring match in candidate_memory search)
        res = temp_workspace.search("NDVI threshold")
        assert any("NDVI threshold for wheat" in h.text for h in res.hits)


class TestWorkspaceExportDataset:
    def test_export_empty_raises(self, temp_workspace, tmp_path):
        with pytest.raises(ValueError, match="No accepted examples"):
            temp_workspace.export_dataset("qa_eval", tmp_path)

    def test_export_with_accepted_example(self, temp_workspace, tmp_path):
        from geomemory.core.models import DatasetExample
        from geomemory.storage.repositories.feedback_repo import DatasetExampleRepository

        repo = DatasetExampleRepository(temp_workspace.conn)
        example = DatasetExample(task_type="qa_eval", review_state="accepted")
        repo.create(example)

        out_path = temp_workspace.export_dataset("qa_eval", tmp_path)
        assert out_path.is_file()
        assert out_path.stat().st_size > 0

