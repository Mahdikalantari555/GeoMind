from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
if "tests" in sys.modules and str(_repo_root / "tests") not in getattr(
    sys.modules["tests"], "__path__", []
):
    sys.modules["tests"].__path__.append(str(_repo_root / "tests"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from geofront_api.events import reset_event_bus  # noqa: E402
from geofront_api.jobs import reset_job_manager  # noqa: E402
from geofront_api.main import create_app  # noqa: E402
from geofront_api.services.agent import reset_agent_service  # noqa: E402
from geofront_api.state import reset_state  # noqa: E402
from tests.integration._workspace import (  # noqa: E402
    create_workspace,
    make_collection,
    wait_job,
)

__all__ = ["create_workspace", "make_collection", "wait_job", "open_ws", "client"]


@pytest.fixture(autouse=True)
def _isolate_geofront_state(tmp_path: Path) -> Iterator[None]:
    state_path = tmp_path / "active_workspace"
    old = os.environ.get("GEOFONT_STATE_PATH")
    os.environ["GEOFONT_STATE_PATH"] = str(state_path)
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("GEOFONT_STATE_PATH", None)
        else:
            os.environ["GEOFONT_STATE_PATH"] = old


@pytest.fixture()
def client() -> Iterator[TestClient]:
    reset_state()
    reset_job_manager()
    reset_event_bus()
    reset_agent_service()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_state()
    reset_job_manager()
    reset_event_bus()
    reset_agent_service()


@pytest.fixture()
def open_ws(client: TestClient, tmp_path: pytest.PathFactory) -> dict[str, object]:
    """Create + open a workspace; return {'path': str}."""
    path = str(tmp_path / "ws")
    return create_workspace(client, path=path, name="M2")
