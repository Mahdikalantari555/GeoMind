"""Discover chat models only at operator-approved destinations (never a client URL)."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from ..auth import ADMIN_DEPS
from ..errors import GeoFrontError
from ..provider_config import (
    _valid_base,
    delete_provider,
    key_env_for,
    load_providers,
    register_provider,
)
from ..state import get_state

router = APIRouter(prefix="/providers", tags=["providers"], dependencies=ADMIN_DEPS)


def catalog() -> dict[str, tuple[str, str]]:
    entries = {
        "OpenAI": ("https://api.openai.com/v1", "GEOMEMORY_OPENAI_API_KEY"),
        "OpenRouter": ("https://openrouter.ai/api/v1", "GEOMEMORY_OPENROUTER_API_KEY"),
    }
    if (base := os.getenv("GEOMEMORY_LLM_API_BASE_URL")) and _valid_base(base, https_only=False):
        entries["Configured endpoint"] = (base.rstrip("/"), "GEOMEMORY_LLM_API_KEY")
    # Environment-approved bases (operator deployment config).
    for value in os.getenv("GEOMIND_APPROVED_PROVIDER_BASES", "").split(","):
        url = value.strip().rstrip("/")
        if not _valid_base(url, https_only=True):
            continue
        digest = key_env_for(url).removeprefix("GEOMEMORY_PROVIDER_").removesuffix("_KEY")
        entries[f"Custom-{digest}"] = (url, key_env_for(url))
    # Operators may also register named providers at runtime (admin scope).
    for provider in load_providers():
        entries[provider["name"]] = (provider["base"], provider["keyEnv"])
    return entries


class ConnectionRequest(BaseModel):
    base: str


class RegisterRequest(BaseModel):
    name: str
    base: str


@router.post("")
async def register(request: RegisterRequest) -> dict[str, str]:
    """Register a named HTTPS provider (admin only). No credential is stored."""
    entry, error = register_provider(request.name, request.base)
    if entry is None:
        messages = {
            "invalid_provider_name": "Provider name must start with a letter and use only letters, digits, spaces, '-' or '_' (max 40).",
            "invalid_provider_base": "Provider base must be a valid HTTPS URL (plain HTTP is allowed only for loopback).",
            "provider_exists": "A provider with this name is already registered.",
        }
        raise GeoFrontError(
            code=error or "invalid_provider",
            message=messages.get(error or "", "Invalid provider"),
            status_code=409 if error == "provider_exists" else 422,
        )
    return entry


@router.delete("/{name}")
async def remove(name: str) -> dict[str, bool]:
    """Remove a registered provider (admin only). Does not touch env keys."""
    return {"deleted": delete_provider(name)}


@router.post("/connect")
async def connect(request: ConnectionRequest) -> dict[str, str]:
    base = request.base.strip().rstrip("/")
    registered = {p["name"] for p in load_providers()}
    for name, (url, key) in catalog().items():
        if (name.startswith("Custom-") or name in registered) and url == base:
            return {"name": name, "base": url, "keyEnv": key}
    raise GeoFrontError(
        code="unapproved_provider",
        message="Ask the gateway operator to register this HTTPS base (POST /providers) or add it to GEOMIND_APPROVED_PROVIDER_BASES",
        status_code=422,
    )


@router.get("")
async def list_providers() -> list[dict[str, object]]:
    return [
        {"name": name, "base": base, "keyEnv": key, "configured": bool(os.getenv(key))}
        for name, (base, key) in catalog().items()
    ]


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
    if not key:
        # Without a credential the provider answers 401 (or, worse, an
        # anonymous list of every public model). Report the missing key
        # instead of making the outbound request.
        raise GeoFrontError(
            code="provider_key_missing",
            message=f"No credential configured for this provider; set {env} on the server.",
            status_code=409,
        )
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            response = await client.get(base + "/models", headers={"Authorization": f"Bearer {key}"})
            response.raise_for_status()
            data = response.json()["data"]
            if not isinstance(data, list):
                raise ValueError("Invalid model list")
            return sorted({item["id"] for item in data if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]})
    except httpx.HTTPStatusError as exc:
        raise GeoFrontError(code="provider_status", message=f"Provider returned HTTP {exc.response.status_code}; check {env}", status_code=502) from None
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        raise GeoFrontError(code="provider_unavailable", message="Cannot read provider model list", status_code=502) from None
