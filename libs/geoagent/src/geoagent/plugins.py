"""Custom-tool discovery: workspace plugins dir + installed entry points.

Two ways to add tools without touching core:
1. drop a ``*.py`` file into ``<workspace>/plugins/`` exposing ``register(registry)``
2. ``pip install`` any package declaring entry point group ``geoagent.tools``
   (module must expose ``register(registry)``)

A broken plugin never blocks startup — it is reported and skipped.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from geoagent.registry import Registry

log = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_plugins(
    registry: Registry,
    workspace_dir: Path,
    plugin_hashes: dict[str, str] | None = None,
) -> list[str]:
    """Load workspace plugins.

    When ``plugin_hashes`` is provided (the production path), only files whose
    filename is pinned and whose SHA-256 matches are loaded. An unpinned or
    modified plugin is skipped — workspace plugins are arbitrary Python and
    must not execute without an operator-approved digest.
    """
    loaded: list[str] = []
    for name, module in _workspace_plugins(workspace_dir, plugin_hashes):
        if _try_register(registry, module):
            loaded.append(f"plugin:{name}")
    for dist, ep in _entry_point_plugins():
        try:
            target = ep.load()
            if _try_register(registry, target):
                loaded.append(f"entrypoint:{dist}:{ep.name}")
        except Exception:  # noqa: BLE001, S112 - plugin isolation by design
            continue
    return loaded


def load_plugin_module(path: Path) -> ModuleType | None:
    try:
        spec = importlib.util.spec_from_file_location(f"geoagent_plugin_{path.stem}", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    except Exception:  # noqa: BLE001 - plugin isolation
        return None


def _workspace_plugins(
    workspace_dir: Path, plugin_hashes: dict[str, str] | None = None
) -> list[tuple[str, ModuleType]]:
    directory = workspace_dir / "plugins"
    out: list[tuple[str, ModuleType]] = []
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.py")):
        if plugin_hashes is not None:
            expected = plugin_hashes.get(path.name)
            if expected is None:
                log.warning("skipping unpinned workspace plugin %s", path.name)
                continue
            if _sha256(path).lower() != expected.lower():
                log.warning("skipping workspace plugin %s: sha256 mismatch", path.name)
                continue
        module = load_plugin_module(path)
        if module is not None:
            out.append((path.stem, module))
    return out


def _entry_point_plugins() -> list[tuple[str, Any]]:
    eps = importlib.metadata.entry_points()
    select = eps.select(group="geoagent.tools")
    return [(ep.dist.name if ep.dist else "?", ep) for ep in sorted(select, key=lambda e: e.name)]


def _try_register(registry: Registry, module: ModuleType) -> bool:
    try:
        register = getattr(module, "register", None)
        if not callable(register):
            return False
        register(registry)
        return True
    except Exception:  # noqa: BLE001 - plugin isolation
        return False
