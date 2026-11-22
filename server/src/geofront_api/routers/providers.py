"""Discover chat models only at operator-approved destinations (never a client URL)."""
from __future__ import annotations

import hashlib
import os
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from ..auth import ADMIN_DEPS
from ..errors import GeoFrontError
from ..state import get_state

router = APIRouter(prefix="/providers", tags=["providers"], dependencies=ADMIN_DEPS)


LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _valid_base(url: str, *, https_only: bool) -> bool:
    """Validate a provider base URL.

    Plain HTTP is only allowed for loopback hosts: the gateway forwards the
    operator's API key in an `Authorization` header, so a remote `http://`
    base leaks the credential in cleartext.
    """
    try:
        parsed = urlsplit(url)
        _ = parsed.port  # also validate malformed or out-of-range ports
        if not parsed.hostname or parsed.username is not None or parsed.query or parsed.fragment:
            return False
        if parsed.scheme == "https":
            return True
        if parsed.scheme == "http" and not https_only:
            return (parsed.hostname or "") in LOOPBACK_HOSTS
        return False
    except ValueError:
        return False


def catalog() -> dict[str, tuple[str, str]]:
    entries = {
        "OpenAI": ("https://api.openai.com/v1", "GEOMEMORY_OPENAI_API_KEY"),
        "OpenRouter": ("https://openrouter.ai/api/v1", "GEOMEMORY_OPENROUTER_API_KEY"),
    }
    if (base := os.getenv("GEOMEMORY_LLM_API_BASE_URL")) and _valid_base(base, https_only=False):
        entries["Configured endpoint"] = (base.rstrip("/"), "GEOMEMORY_LLM_API_KEY")
    # Only an operator may authorize outbound destinations. A change of base,
    # including its path, gets a fresh credential namespace.
    for value in os.getenv("GEOMIND_APPROVED_PROVIDER_BASES", "").split(","):
        url = value.strip().rstrip("/")
        if not _valid_base(url, https_only=True):
            continue
        digest = hashlib.sha256(url.encode()).hexdigest()[:24].upper()
        entries[f"Custom-{digest}"] = (url, f"GEOMEMORY_PROVIDER_{digest}_KEY")
    return entries


class ConnectionRequest(BaseModel):
    base: str


@router.post("/connect")
async def connect(request: ConnectionRequest) -> dict[str, str]:
    for name, (url, key) in catalog().items():
        if name.startswith("Custom-") and url == request.base.strip().rstrip("/"):
            return {"name": name, "base": url, "keyEnv": key}
    raise GeoFrontError(code="unapproved_provider", message="Ask the gateway operator to add this HTTPS base to GEOMIND_APPROVED_PROVIDER_BASES", status_code=422)


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
