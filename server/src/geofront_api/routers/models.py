"""Model-management API — list / download / status / training for embedding + online models."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from ..errors import GeoFrontError
from ..jobs import get_job_manager
from ..schemas import DownloadModelRequest, ModelRollbackRequest, TrainRequest
from ..state import get_state

router = APIRouter(prefix="/models", tags=["models"])
log = logging.getLogger("geofront.models")


def _hub() -> Any:
    from geomemory import EmbeddingModelHub

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
    models_raw = await run_in_threadpool(hub.scan)
    return list(models_raw) if models_raw is not None else []


@router.post("/download", status_code=202)
async def download_model(req: DownloadModelRequest) -> dict[str, Any]:
    """Enqueue a background model download job → 202."""
    backend = req.backend
    if backend == "sentence-transformers":
        backend = "st"
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
        h = _hub()
        path = h.download(model_name, backend=backend)
        result = h.find_model(model_name, backend=backend)
        return result or {"name": model_name, "backend": backend, "path": path}

    record = await get_job_manager().submit("model_download", _do_download)
    log.info(
        "model download enqueued: model=%s backend=%s job=%s",
        model_name,
        backend,
        record.id,
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
        path = ws.download_vision_model()
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


# ── Online training (change: add-studio-training-lab) ─────────────────────────


def _version_manager() -> Any:
    from geolearn.versioning import ModelVersionManager

    state = get_state()
    ws = state.require_workspace()
    return ModelVersionManager(Path(ws.path) / "geolearn")


@router.post("/train", status_code=202)
async def train_models(req: TrainRequest) -> dict[str, Any]:
    """Enqueue an online training job over accepted feedback → 202.

    Runs geolearn's TrainingPipeline with the active workspace facade as the
    candidate provider; streams batch progress via ``job.progress`` SSE.
    """
    state = get_state()
    ws = state.require_workspace()
    geolearn_dir = Path(ws.path) / "geolearn"
    manager = get_job_manager()

    def _run(job_id: str) -> dict[str, Any]:
        from geolearn.training_pipeline import TrainingPipeline

        pipeline = TrainingPipeline(geolearn_dir, candidate_source=ws)

        def _cb(stage: str, batch: int, total: int) -> None:
            manager.update_progress(
                job_id,
                stage=stage,
                percent=int(batch / max(1, total) * 100),
                detail=f"batch {batch}/{total}",
            )

        return pipeline.train_on_feedback(
            feedback_ids=req.feedback_ids,
            batch_size=req.batch_size,
            progress_cb=_cb,
        )

    record = await manager.submit("model_train", _run)
    log.info("model training enqueued: job=%s", record.id)
    return {"job_id": record.id}


@router.get("/versions")
async def list_model_versions() -> dict[str, Any]:
    """List saved classifier versions (all keys, newest first)."""
    versions = await run_in_threadpool(_version_manager().list_versions, None)
    return {
        "versions": [
            {
                "key": list(v.key),
                "version": v.version,
                "timestamp": v.timestamp,
                "n_samples": v.n_samples,
                "sha256": v.sha256,
            }
            for v in versions
        ]
    }


@router.post("/rollback")
async def rollback_model(req: ModelRollbackRequest) -> dict[str, Any]:
    """Roll a (crop, region) classifier back to a saved version.

    Every successful rollback is recorded as an audit event
    (``model_rolled_back``) so the Training Lab history stays traceable.
    """
    manager = _version_manager()
    key = (req.key[0], req.key[1])
    rolled = await run_in_threadpool(manager.rollback_to, key, req.version)
    if not rolled:
        raise GeoFrontError(
            code="rollback_failed",
            message=f"no version {req.version} for key {list(req.key)}",
            status_code=404,
        )
    from ..events import get_event_bus

    get_event_bus().publish(
        "model_rolled_back",
        {"key": list(req.key), "version": req.version},
    )
    log.info("model rollback: key=%s version=%s", list(req.key), req.version)
    return {"rolled_back": True, "key": list(req.key), "version": req.version}
