"""Shared scene-download flow (change: add-studio-knowledge-agent §4.2).

Both ``POST /data/download`` (wrapped in a background job) and the
``data_download`` agent tool run this exact flow: ``data_engine.fetch``
ROI-clipped band download followed by workspace asset registration so the
answer → citation → segment → asset provenance chain stays traceable.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from data_engine.fetch import FetchProgress, FetchResult
from data_engine.fetch import fetch_scene as fetch_scene

log = logging.getLogger("geofront.scene_download")

SCENES_COLLECTION = "scenes"


def ensure_scenes_collection(ws: Any) -> Any:
    """Return the workspace's ``scenes`` collection, creating it once."""
    for collection in ws.list_collections():
        if collection.name == SCENES_COLLECTION and not collection.archived:
            return collection
    return ws.create_collection(
        SCENES_COLLECTION, "Downloaded satellite scenes (acquire pipeline)"
    )


def run_scene_download(
    ws: Any,
    *,
    scene_id: str,
    roi: dict[str, Any],
    sensor: str,
    date_from: str,
    date_to: str,
    progress_cb: Callable[[FetchProgress], None] | None = None,
) -> dict[str, Any]:
    """Download a scene for ``roi`` and register every band as an asset.

    Returns the job-result dict ``{scene_id, date, cloud_cover, directory,
    band_files, asset_ids}`` with workspace-relative band paths.
    """
    workspace_dir = Path(ws.path)
    dest = workspace_dir / "data" / "scenes"
    result = fetch_scene(
        scene_id,
        roi,
        sensor=sensor,
        date_from=date_from,
        date_to=date_to,
        dest=dest,
        progress_cb=progress_cb,
    )

    return register_scene_download(ws, result)


def register_scene_download(ws: Any, result: FetchResult) -> dict[str, Any]:
    """Register fetched bands while holding the workspace write lock."""
    workspace_dir = Path(ws.path)
    collection = ensure_scenes_collection(ws)
    asset_ids: dict[str, str] = {}
    band_files: dict[str, str] = {}
    for band, band_path in sorted(result.band_files.items()):
        rel = str(Path(band_path).relative_to(workspace_dir))
        band_files[band] = rel
        try:
            ingest_job = ws.ingest(Path(band_path), collection.id, index_after=False)
            ingest_result = ingest_job.result or {}
            if ingest_result.get("asset_id"):
                asset_ids[band] = str(ingest_result["asset_id"])
        except Exception as exc:  # noqa: BLE001 — registration must not fail the download
            log.warning("asset registration failed for %s: %s", band, exc)

    return {
        "scene_id": result.scene_id,
        "date": result.date,
        "cloud_cover": result.cloud_cover,
        "directory": str(Path(result.directory).relative_to(workspace_dir)),
        "band_files": band_files,
        "band_map": dict(getattr(result, "band_map", {}) or {}),
        "asset_ids": asset_ids,
        # Explicit, not inferred: an incomplete band set must be visible to
        # the client instead of looking like a successful download.
        "partial": bool(getattr(result, "partial", False)),
    }
