from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

# Ensure repo root is importable
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import pytest
from fastapi.testclient import TestClient
from geofront_api.events import reset_event_bus
from geofront_api.jobs import reset_job_manager
from geofront_api.main import create_app
from geofront_api.services.agent import reset_agent_service
from geofront_api.state import reset_state
from geomemory.core.models import GenerationRequest, GenerationResult

from tests.integration._workspace import create_workspace


class DeterministicLLMBackend:
    """Deterministic LLM backend for integration testing."""

    model_id = "deterministic-mock"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        context_preview = request.context[0].text[:40] if request.context else "synthesized"
        text = f"Remote sensing analysis confirms: {context_preview} [1]"
        return GenerationResult(
            text=text,
            prompt_hash="mock_hash",
            model_id=self.model_id,
        )

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)


@pytest.fixture(autouse=True)
def _isolate_geofront_state(tmp_path: Path) -> Iterator[None]:
    state_path = tmp_path / "active_workspace"
    old_state = os.environ.get("GEOFONT_STATE_PATH")
    old_provider = os.environ.get("GEOMEMORY_EMBEDDING_PROVIDER")
    os.environ["GEOFONT_STATE_PATH"] = str(state_path)
    os.environ["GEOMEMORY_EMBEDDING_PROVIDER"] = "hashing"
    try:
        yield
    finally:
        if old_state is None:
            os.environ.pop("GEOFONT_STATE_PATH", None)
        else:
            os.environ["GEOFONT_STATE_PATH"] = old_state
        if old_provider is None:
            os.environ.pop("GEOMEMORY_EMBEDDING_PROVIDER", None)
        else:
            os.environ["GEOMEMORY_EMBEDDING_PROVIDER"] = old_provider


@pytest.fixture()
def _llm_backend(monkeypatch: pytest.MonkeyPatch) -> DeterministicLLMBackend:
    backend = DeterministicLLMBackend()
    import geomemory.qa.backend_factory as bf

    monkeypatch.setattr(bf, "build_llm_backend", lambda settings: (backend, 2000))
    return backend


@pytest.fixture()
def gateway(tmp_path: Path) -> Iterator[TestClient]:
    reset_state()
    reset_job_manager()
    reset_event_bus()
    reset_agent_service()
    app = create_app()
    with TestClient(app) as client:
        ws_path = str(tmp_path / "ws")
        create_workspace(client, path=ws_path, name="IntegrationWS", embedding_backend="hashing")
        yield client
    reset_state()
    reset_job_manager()
    reset_event_bus()
    reset_agent_service()
