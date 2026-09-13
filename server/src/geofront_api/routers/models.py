"""Model-management API — list / download / status for embedding models."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from ..errors import GeoFrontError
from ..jobs import get_job_manager
from ..schemas import DownloadModelRequest
from ..state import get_state

router = APIRouter(prefix="/models", tags=["models"])
log = logging.getLogger("geofront.models")


def _hub() -> Any:
    from geomemory.embeddings.hub import EmbeddingModelHub

    state = get_state()
    ws_dir = str(state.workspace_path) if state.workspace_path is not None else None
    emb_path = None
    if state.is_open:
        emb_path = state.require_workspace().settings.embedding_path
    return EmbeddingModelHub(workspace_dir=ws_dir, embedding_path=emb_path)


@router.get("")
async def list_models() -> list[dict[str, Any]]:
    """Return the embedding model hub inventory."""
    hub = _hub()
    models = await run_in_threadpool(hub.scan)
    return models


@router.post("/download")
async def download_model(req: DownloadModelRequest) -> dict[str, Any]:
    """Enqueue a background model download job → 202."""
    backend = req.backend
    model_name = req.model_name
    if backend not in ("st", "onnx"):
        raise GeoFrontError(
            code="invalid_backend",
            message=f"backend must be 'st' or 'onnx', got '{backend}'",
            status_code=422,
            detail={"available": ["st", "onnx"]},
        )

    # Already cached → fast path
    hub = _hub()
    existing = await run_in_threadpool(hub.find_model, model_name, backend=backend)
    if existing is not None:
        return {
            "status": "already_downloaded",
            "id": existing["id"],
            "path": existing["path"],
        }

    # Offline guard
    state = get_state()
    if state.is_open:
        ws = state.require_workspace()
        if ws.settings.offline:
            raise GeoFrontError(
                code="embedding_unavailable",
                message=f"Model '{model_name}' is not cached locally and workspace is offline.",
                status_code=503,
                detail={"offline": True, "hint": "set offline=false or pre-download"},
            )

    def _do_download() -> dict[str, Any]:
        from geomemory.embeddings.hub import EmbeddingModelHub

        h = EmbeddingModelHub()
        path = h.download(model_name, backend=backend)
        result = h.find_model(model_name, backend=backend)
        return result or {"name": model_name, "backend": backend, "path": path}

    record = await get_job_manager().submit("model_download", _do_download)
    log.info(
        "model download enqueued: model=%s backend=%s job=%s",
        model_name, backend, record.id,
    )
    return {"job_id": record.id, "model_name": model_name, "backend": backend}


@router.post("/vision/download", status_code=202)
async def download_vision_model() -> dict[str, Any]:
    """Enqueue a background vision model download job → 202."""
    state = get_state()
    ws = state.require_workspace()

    if ws.settings.offline:
        raise GeoFrontError(
            code="vision_unavailable",
            message="Vision model is not cached locally and workspace is offline.",
            status_code=503,
            detail={"offline": True, "hint": "set offline=false or pre-download"},
        )

    def _do_download() -> str:
        from geomemory.embeddings.vision_downloader import download_vision_model as _download

        path = _download(ws.settings)
        if path is None:
            raise RuntimeError("Vision model download did not produce a path")
        async def _update_settings() -> None:
            async with state.write_lock:
                await run_in_threadpool(ws.update_settings, vision_path=path)
        asyncio.run(_update_settings())
        return path

    record = await get_job_manager().submit("vision_model_download", _do_download)
    log.info("vision model download enqueued: job=%s", record.id)
    return {"job_id": record.id}


@router.get("/{model_id}/status")
async def model_status(model_id: str) -> dict[str, Any]:
    """Convenience endpoint: is a specific model downloaded?"""
    hub = _hub()
    parts = model_id.split(":", 1)
    if len(parts) == 2:
        backend, name = parts
    else:
        backend, name = "st", model_id

    entry = await run_in_threadpool(hub.find_model, name, backend=backend)
    if entry is None:
        return {"id": model_id, "downloaded": False, "found": False}
    return {
        "id": entry["id"],
        "downloaded": entry.get("downloaded", False),
        "loadable": entry.get("loadable", False),
        "path": entry.get("path"),
        "size_bytes": entry.get("size_bytes", 0),
        "space_id": entry.get("space_id"),
    }
