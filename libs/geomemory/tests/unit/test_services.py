"""Unit tests for the service layer."""

from __future__ import annotations

import sys

from geomemory.core.models import Job, SearchHit, WorkspaceSettings
from geomemory.services.doctor import doctor_llm_provider
from geomemory.services.job_service import JobService
from geomemory.retrieval.search_service import SearchService


class TestJobService:
    def test_submit_and_get(self, temp_workspace):
        svc = JobService(temp_workspace.conn)
        job = svc.submit_job("indexing", {"space": "x"})
        assert job.state == "pending"
        assert svc.get_job(job.id).id == job.id

    def test_run_job(self, temp_workspace):
        svc = JobService(temp_workspace.conn)
        job = svc.submit_job("evaluation", {})
        done = svc.run_job(job.id, lambda j: {"ok": True})
        assert done.state == "completed"
        assert done.result == {"ok": True}

    def test_run_job_failure(self, temp_workspace):
        svc = JobService(temp_workspace.conn)
        job = svc.submit_job("evaluation", {})

        def _boom(job: Job):
            raise RuntimeError("boom")

        failed = svc.run_job(job.id, _boom)
        assert failed.state == "failed"
        assert "boom" in (failed.error or "")

    def test_cancel_and_list(self, temp_workspace):
        svc = JobService(temp_workspace.conn)
        job = svc.submit_job("ingestion", {})
        assert svc.cancel_job(job.id) is True
        assert svc.list_by_state("cancelled")[0].id == job.id


class TestPublicSearchService:
    def test_canonical_retrieval_service(self, temp_workspace):
        class _FakeBackend:
            space_id = "test.space"

            def search(self, request):
                return [SearchHit(id="h1", score=1.0)]

        svc = SearchService([_FakeBackend()])
        result = svc.search("query", top_n=3)
        assert result.hits[0].id == "h1"


class TestDoctorLLMProvider:
    def test_defaults_no_provider(self, monkeypatch):
        monkeypatch.delenv("GEOMEMORY_LLM_API_KEY", raising=False)
        info = doctor_llm_provider(WorkspaceSettings(name="ws"))
        assert info["provider"] is None
        assert info["model_id"] == "kilo-auto/free"
        assert info["key_env"] == "GEOMEMORY_LLM_API_KEY"
        assert info["key_set"] is False
        assert info["context_window"] == 32768

    def test_key_set_detected(self, monkeypatch):
        monkeypatch.setenv("MY_KEY", "secret")
        s = WorkspaceSettings(name="ws", llm_provider="api", llm_api_key_env="MY_KEY")
        info = doctor_llm_provider(s)
        assert info["provider"] == "api"
        assert info["key_set"] is True
        # The secret value must never be reported.
        assert "secret" not in info.values()


class TestDoctorQdrant:
    def test_client_not_installed(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "qdrant_client", None)
        from geomemory.services.doctor import doctor_qdrant

        info = doctor_qdrant(WorkspaceSettings(name="ws"))
        assert info["client_installed"] is False
        assert "reachable" not in info

    def test_reachable(self, monkeypatch):
        import types

        class _FakeClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def get_collections(self):
                return []

        fake = types.ModuleType("qdrant_client")
        fake.QdrantClient = _FakeClient
        monkeypatch.setitem(sys.modules, "qdrant_client", fake)
        from geomemory.services.doctor import doctor_qdrant

        s = WorkspaceSettings(name="ws", qdrant_url="http://qdrant:6333")
        info = doctor_qdrant(s)
        assert info["client_installed"] is True
        assert info["reachable"] is True
        assert info["url"] == "http://qdrant:6333"

    def test_unreachable(self, monkeypatch):
        import types

        class _FakeClient:
            def __init__(self, **kwargs):
                raise ConnectionError("connection refused")

            def get_collections(self):
                return []

        fake = types.ModuleType("qdrant_client")
        fake.QdrantClient = _FakeClient
        monkeypatch.setitem(sys.modules, "qdrant_client", fake)
        from geomemory.services.doctor import doctor_qdrant

        s = WorkspaceSettings(name="ws", qdrant_url="http://qdrant:6333")
        info = doctor_qdrant(s)
        assert info["reachable"] is False
        assert "connection refused" in info["error"]
