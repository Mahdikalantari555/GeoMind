"""Operator-managed custom provider registry.

Registered providers are **gateway configuration**, not workspace data: they
hold a display name, an approved HTTPS base URL and the *name* of the process
environment variable that holds the key. Keys are never written here — they
are set at runtime via ``PUT /workspace/settings`` and live only in the
process environment.

The key-slot name is derived from the base URL so that changing a provider's
destination always gets a fresh credential namespace (no accidental reuse of
a key issued for a different host).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 _-]{0,39}$")
RESERVED_NAMES = {"openai", "openrouter", "configured endpoint"}

# Built-in catalog names we must never shadow.
PROVIDERS_FILENAME = "providers.json"


def _valid_base(url: str, *, https_only: bool) -> bool:
    """Validate a provider base URL (SSRF / cleartext-credential guard).

    Plain HTTP is allowed only for loopback hosts: the gateway forwards the
    operator's API key in an ``Authorization`` header, so a remote ``http://``
    base would leak it in cleartext.
    """
    try:
        parsed = urlsplit(url)
        _ = parsed.port  # validates malformed / out-of-range ports
        if not parsed.hostname or parsed.username is not None or parsed.query or parsed.fragment:
            return False
        if parsed.scheme == "https":
            return True
        if parsed.scheme == "http" and not https_only:
            return (parsed.hostname or "") in LOOPBACK_HOSTS
        return False
    except ValueError:
        return False


def _state_dir() -> Path:
    """Directory that holds the active-workspace marker and the registry."""
    env = (
        os.environ.get("GEOMIND_STATE_PATH", "").strip()
        or os.environ.get("GEOFONT_STATE_PATH", "").strip()
    )
    if env:
        return Path(env).expanduser().parent
    from .state import get_default_workspace_root

    return get_default_workspace_root() / ".geofront"


def providers_path() -> Path:
    return _state_dir() / PROVIDERS_FILENAME


def key_env_for(base: str) -> str:
    """Deterministic, URL-scoped key slot (fresh slot when the URL changes)."""
    normalized = base.strip().rstrip("/")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24].upper()
    return f"GEOMEMORY_PROVIDER_{digest}_KEY"


def _normalize_entry(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    name, base = raw.get("name"), raw.get("base")
    if not isinstance(name, str) or not isinstance(base, str):
        return None
    if not _NAME_RE.fullmatch(name) or not _valid_base(base, https_only=True):
        return None
    return {"name": name, "base": base.rstrip("/"), "keyEnv": key_env_for(base)}


def load_providers() -> list[dict[str, str]]:
    """Read the registry; a missing or corrupt file is treated as empty."""
    path = providers_path()
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(payload, list):
        return []
    entries = [entry for item in payload if (entry := _normalize_entry(item)) is not None]
    return entries


def _save_providers(entries: list[dict[str, str]]) -> None:
    """Atomically persist the registry so a crash cannot truncate it."""
    path = providers_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def register_provider(name: str, base: str) -> tuple[dict[str, str] | None, str | None]:
    """Register a provider. Returns (entry, error_message)."""
    clean_name = name.strip()
    clean_base = base.strip().rstrip("/")
    if not _NAME_RE.fullmatch(clean_name) or clean_name.lower() in RESERVED_NAMES:
        return None, "invalid_provider_name"
    if not _valid_base(clean_base, https_only=True):
        return None, "invalid_provider_base"
    entries = load_providers()
    if any(e["name"].lower() == clean_name.lower() for e in entries):
        return None, "provider_exists"
    entry = {"name": clean_name, "base": clean_base, "keyEnv": key_env_for(clean_base)}
    entries.append(entry)
    _save_providers(entries)
    return entry, None


def delete_provider(name: str) -> bool:
    entries = load_providers()
    kept = [e for e in entries if e["name"].lower() != name.strip().lower()]
    if len(kept) == len(entries):
        return False
    _save_providers(kept)
    return True
