from __future__ import annotations

import os

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/environment", tags=["environment"])

# Env vars the setup wizard is allowed to set at runtime. Values are applied
# in-process only (never persisted to the workspace DB, never returned).
ALLOWED_ENV_VARS = {
    "HF_ENDPOINT": "Hugging Face hub endpoint used for model downloads",
    "GEOMEMORY_EMBEDDING_ROOT": "Shared embedding model cache root scanned by every workspace",
    "HF_HOME": "huggingface_hub home (defaults to ~/.cache/huggingface)",
}


class EnvironmentOverridesRequest(BaseModel):
    """Set runtime env vars from the setup wizard / Settings page."""

    model_config = {"extra": "forbid"}

    env: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of allowed env var name → value (empty value unsets it)",
    )


@router.post("/overrides")
async def set_environment_overrides(req: EnvironmentOverridesRequest) -> dict[str, object]:
    """Apply runtime env-var overrides (HF endpoint, shared embedding cache root).

    Only the allow-listed vars are accepted; unknown keys are ignored with a
    warning so the endpoint never leaks arbitrary env injection.
    """
    applied: dict[str, str | None] = {}
    ignored: list[str] = []
    for key, value in req.env.items():
        if key not in ALLOWED_ENV_VARS:
            ignored.append(key)
            continue
        if value == "":
            os.environ.pop(key, None)
            applied[key] = None
        else:
            os.environ[key] = str(value)
            applied[key] = str(value)
    return {"applied": applied, "ignored": ignored}


@router.get("/overrides")
async def get_environment_overrides() -> dict[str, object]:
    """Return the current values of the allow-listed env vars (values never secret)."""
    return {key: os.environ.get(key) for key in ALLOWED_ENV_VARS}
