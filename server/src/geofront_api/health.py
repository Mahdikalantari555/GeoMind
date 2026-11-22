from __future__ import annotations

from fastapi import APIRouter

from . import __version__
from .schemas import HealthLLM, HealthResponse, HealthWorkspace
from .state import get_state

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    state = get_state()
    ws = HealthWorkspace(
        status="open" if state.is_open else "closed",
        # The public probe never reveals a filesystem path.
        path=None,
        name=(state.workspace.settings.name if state.workspace is not None else None),
    )
    probe = state.llm_health()
    return HealthResponse(
        version=__version__,
        workspace=ws,
        llm=HealthLLM(
            provider=str(probe.get("provider") or "api"),
            key_configured=bool(probe.get("key_configured")),
        ),
    )
