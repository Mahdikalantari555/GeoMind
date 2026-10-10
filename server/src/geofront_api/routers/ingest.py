from __future__ import annotations

import base64
import binascii
import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from geomemory import AssetNotFoundError, GeoMemory, GeoMemoryError

from ..errors import GeoFrontError
from ..jobs import get_job_manager
from ..schemas import IngestBytesRequest
from ..state import get_state

router = APIRouter(tags=["ingest"])

# Matches geomemory's loader table (DOCX is a known gap — not accepted here).
ACCEPTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".pdf",
    ".py",
    ".js",
    ".ipynb",
    ".geojson",
    ".gpkg",
    ".tif",
    ".tiff",
}


def _require_ws() -> GeoMemory:
    return get_state().require_workspace()


MAX_INGEST_BYTES = 500 * 1024 * 1024  # 500 MB per spec


def _check_extension(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in ACCEPTED_EXTENSIONS:
        raise GeoFrontError(
            code="unsupported_format",
            message=f"Unsupported file type: '{suffix or filename}'. "
            f"Accepted: {', '.join(sorted(ACCEPTED_EXTENSIONS))}",
            status_code=422,
            detail={"accepted": sorted(ACCEPTED_EXTENSIONS), "received": suffix or filename},
        )


def _check_size(data: bytes) -> None:
    if len(data) > MAX_INGEST_BYTES:
        raise GeoFrontError(
            code="payload_too_large",
            message=f"File too large: {len(data)} bytes exceeds limit {MAX_INGEST_BYTES} bytes (500 MB).",
            status_code=413,
            detail={"size_bytes": len(data), "limit_bytes": MAX_INGEST_BYTES},
        )


def _make_ingest_job(
    ws: GeoMemory,
    filename: str,
    data: bytes,
    collection_id: str,
    parser: str | None,
    index_after: bool,
) -> Callable[[], Any]:
    """Build an async job closure that owns its temp file lifecycle and enforces write_lock."""

    async def _run() -> dict[str, object]:
        def _sync_ingest() -> dict[str, object]:
            with tempfile.TemporaryDirectory(prefix="gf-ingest-") as tmp:
                target = Path(tmp) / filename
                target.write_bytes(data)
                job = ws.ingest(target, collection_id, parser=parser, index_after=index_after)
                payload: dict[str, object] = dict(job.result or {})
                payload["job_type"] = job.type
                if job.error is not None:
                    payload["error"] = job.error
                asset_id = payload.get("asset_id")
                if asset_id and not payload.get("skipped"):
                    # Thread context — EventBus.publish is thread-safe.
                    from ..events import get_event_bus

                    get_event_bus().publish(
                        "asset_created",
                        {"asset_id": asset_id, "collection_id": collection_id, "filename": filename},
                    )
                return payload

        async with get_state().write_lock:
            return await run_in_threadpool(_sync_ingest)

    return _run


async def _submit(
    ws: GeoMemory,
    filename: str,
    data: bytes,
    collection_id: str,
    parser: str | None,
    index_after: bool,
) -> dict[str, str]:
    record = await get_job_manager().submit(
        "ingestion", _make_ingest_job(ws, filename, data, collection_id, parser, index_after)
    )
    return {"job_id": record.id, "status": "accepted"}


@router.post("/ingest", status_code=202)
async def ingest_file(
    file: Annotated[UploadFile, File()],
    collection_id: Annotated[str, Form()],
    index_after: Annotated[bool, Form()] = True,
    parser: Annotated[str | None, Form()] = None,
) -> dict[str, str]:
    ws = _require_ws()
    _check_extension(file.filename or "")
    data = await file.read()
    _check_size(data)
    return await _submit(ws, file.filename or "upload", data, collection_id, parser, index_after)


@router.post("/ingest/bytes", status_code=202)
async def ingest_bytes(req: IngestBytesRequest) -> dict[str, str]:
    ws = _require_ws()
    _check_extension(req.filename)
    try:
        raw = base64.b64decode(req.data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise GeoFrontError(
            code="invalid_base64", message="data_base64 is not valid base64.", status_code=422
        ) from exc
    _check_size(raw)
    return await _submit(ws, req.filename, raw, req.collection_id, req.parser, req.index_after)


@router.post("/asset", status_code=201)
async def create_asset(
    request: Request,
    collection_id: str | None = None,
) -> dict[str, object]:
    """Ingest an asset synchronously and return its created record with sha256."""
    ws = _require_ws()
    content_type = request.headers.get("content-type", "")
    filename = "document.txt"
    data = b""

    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload and hasattr(upload, "read"):
            data = await upload.read()
            filename = getattr(upload, "filename", "document.txt") or "document.txt"
            if "collection_id" in form:
                collection_id = str(form["collection_id"])
    elif "application/json" in content_type:
        body = await request.json()
        if isinstance(body, dict):
            if body.get("type") in ("FeatureCollection", "Feature"):
                filename = body.get("name", "vector.geojson")
                if not filename.endswith(".geojson"):
                    filename += ".geojson"
                data = json.dumps(body).encode("utf-8")
            elif "data_base64" in body:
                filename = body.get("filename", "document.txt")
                data = base64.b64decode(body["data_base64"])
            elif "content" in body:
                filename = body.get("filename", "document.txt")
                content = body["content"]
                data = content.encode("utf-8") if isinstance(content, str) else content
            if "collection_id" in body and body["collection_id"]:
                collection_id = str(body["collection_id"])
    else:
        data = await request.body()
        filename = "document.txt"

    _check_extension(filename)
    _check_size(data)

    def _sync_ingest() -> tuple[str, str, str, str, str, str]:
        # Under write lock: resolve collection
        if not collection_id:
            cols = ws.list_collections()
            if cols:
                cid = cols[0].id
            else:
                col = ws.create_collection("default")
                cid = col.id
        else:
            cid = collection_id

        with tempfile.TemporaryDirectory(prefix="gf-asset-") as tmp:
            target = Path(tmp) / filename
            target.write_bytes(data)
            job = ws.ingest(target, cid, index_after=True)
            res = dict(job.result or {})
            asset_id = str(res.get("asset_id", ""))
        detail = ws.inspect(asset_id)
        sha256 = detail.revision.hash if detail.revision else ""
        return (
            asset_id,
            sha256,
            detail.asset.kind,
            detail.asset.title or "",
            detail.asset.collection_id,
            detail.asset.created_at,
        )

    async with get_state().write_lock:
        asset_id, sha256, kind, title, col_id, created_at = await run_in_threadpool(_sync_ingest)

    return {
        "id": asset_id,
        "sha256": sha256,
        "kind": kind,
        "title": title,
        "collection_id": col_id,
        "created_at": created_at,
    }


@router.get("/assets")
async def list_assets(
    collection_id: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=1000, ge=1, le=5000),
) -> list[dict[str, object]]:
    """List assets, optionally filtered by collection with pagination."""
    ws = _require_ws()
    assets = await run_in_threadpool(ws.list_assets, collection_id, offset=offset, limit=limit)
    res = []
    for a in assets:
        d = a.model_dump(mode="json")
        if a.current_revision_id:
            rev = ws._revision_by_id(a.current_revision_id)
            if rev:
                d["sha256"] = rev.hash
        res.append(d)
    return res


@router.get("/assets/{asset_id}")
async def inspect_asset(asset_id: str) -> dict[str, object]:
    ws = _require_ws()
    try:
        detail = await run_in_threadpool(ws.inspect, asset_id)
    except AssetNotFoundError as exc:
        raise GeoFrontError(
            code="asset_not_found",
            message=f"Asset not found: {asset_id}",
            status_code=404,
        ) from exc
    except GeoMemoryError as exc:
        raise GeoFrontError(code="inspect_failed", message=str(exc), status_code=400) from exc
    return detail.model_dump(mode="json")
