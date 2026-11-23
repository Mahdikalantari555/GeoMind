"""Operator-managed custom provider registry (no credentials stored)."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from geofront_api.errors import GeoFrontError
from geofront_api.routers import providers
from geofront_api.routers.workspace import _validate_key_env


@pytest.fixture()
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "state" / "providers.json"
    monkeypatch.setattr("geofront_api.provider_config.providers_path", lambda: path)
    return path


def test_register_catalog_connect(registry: Path) -> None:
    entry, error = providers.register_provider("Acme", "https://llm.acme.test/v1")
    assert error is None
    assert entry is not None
    assert entry["name"] == "Acme"
    assert entry["base"] == "https://llm.acme.test/v1"
    assert entry["keyEnv"].startswith("GEOMEMORY_PROVIDER_")

    assert "Acme" in providers.catalog()
    resolved = asyncio.run(providers.connect(providers.ConnectionRequest(base="https://llm.acme.test/v1/")))
    assert resolved == entry
    # Only the env-var *name* is persisted — never a credential value.
    import json

    stored = json.loads(registry.read_text(encoding="utf-8"))
    assert set(stored[0]) == {"name", "base", "keyEnv"}


def test_register_rejects_bad_inputs(registry: Path) -> None:
    for name, base in [
        ("OpenAI", "https://x.test/v1"),          # reserved name
        ("1bad", "https://x.test/v1"),            # must start with a letter
        ("Good", "http://remote.test/v1"),        # cleartext remote
        ("Good", "https://user@x.test/v1"),       # embedded credentials
        ("Good", "https://x.test/v1?key=leak"),   # query string
    ]:
        entry, error = providers.register_provider(name, base)
        assert entry is None and error is not None, (name, base)


def test_duplicate_name_and_delete(registry: Path) -> None:
    assert providers.register_provider("Acme", "https://one.test/v1")[1] is None
    assert providers.register_provider("Acme", "https://two.test/v1")[1] == "provider_exists"

    before = providers.catalog()["Acme"][1]
    assert providers.delete_provider("ACME") is True
    assert "Acme" not in providers.catalog()
    # A fresh registration at a different URL gets a different key slot.
    entry, _ = providers.register_provider("Acme", "https://two.test/v1")
    assert entry is not None and entry["keyEnv"] != before
    assert providers.delete_provider("missing") is False


def test_registry_survives_reload(registry: Path) -> None:
    providers.register_provider("Acme", "https://llm.acme.test/v1")
    # Simulate a process restart: fresh load from disk.
    assert any(p["name"] == "Acme" for p in providers.load_providers())


def test_corrupt_registry_is_treated_as_empty(registry: Path) -> None:
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text("{not json", encoding="utf-8")
    assert providers.load_providers() == []


def test_key_env_validation_accepts_registered_slot_and_rejects_path(registry: Path) -> None:
    entry, _ = providers.register_provider("Acme", "https://llm.acme.test/v1")
    assert entry is not None
    assert _validate_key_env(entry["keyEnv"]) == entry["keyEnv"]
    assert _validate_key_env("PATH") is None
    assert _validate_key_env("GEOMEMORY_LLM_API_KEY") == "GEOMEMORY_LLM_API_KEY"


def test_unapproved_base_still_rejected(registry: Path) -> None:
    with pytest.raises(GeoFrontError) as exc:
        asyncio.run(providers.connect(providers.ConnectionRequest(base="https://elsewhere.test/v1")))
    assert exc.value.code == "unapproved_provider"
