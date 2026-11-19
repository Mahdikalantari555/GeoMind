"""Discover chat models only at operator-approved destinations (never a client URL)."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from ..errors import GeoFrontError
from ..state import get_state

router = APIRouter(prefix="/providers", tags=["providers"])


def catalog() -> dict[str, tuple[str, str]]:
    entries = {
        "OpenAI": ("https://api.openai.com/v1", "GEOMEMORY_OPENAI_API_KEY"),
        "OpenRouter": ("https://openrouter.ai/api/v1", "GEOMEMORY_OPENROUTER_API_KEY"),
    }
    if base := os.getenv("GEOMEMORY_LLM_API_BASE_URL"):
        entries["Configured endpoint"] = (base.rstrip("/"), "GEOMEMORY_LLM_API_KEY")
    return entries


@router.get("")
async def list_providers() -> list[dict[str, str]]:
    return [{"name": name, "base": base, "keyEnv": key} for name, (base, key) in catalog().items()]


@router.get("/{name}/models")
async def discover(name: str) -> list[str]:
    ws = get_state().require_workspace()
    if ws.settings.offline:
        raise GeoFrontError(code="offline", message="Workspace is offline", status_code=409)
    entry = catalog().get(name)
    if not entry:
        raise GeoFrontError(code="unknown_provider", message="Unknown provider", status_code=404)
    base, env = entry
    key = os.getenv(env)
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            response = await client.get(base + "/models", headers={"Authorization": f"Bearer {key}"} if key else {})
            response.raise_for_status()
            data = response.json()["data"]
            if not isinstance(data, list):
                raise ValueError("Invalid model list")
            return sorted({item["id"] for item in data if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]})
    except httpx.HTTPStatusError as exc:
        raise GeoFrontError(code="provider_status", message=f"Provider returned HTTP {exc.response.status_code}; check {env}", status_code=502) from None
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        raise GeoFrontError(code="provider_unavailable", message="Cannot read provider model list", status_code=502) from None
