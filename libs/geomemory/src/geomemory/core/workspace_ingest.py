"""Ingestion capability of the workspace facade."""

from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path
from typing import Any, Literal

from geomemory.core.events import (
    ASSET_CREATED,
    DomainEvent,
)
from geomemory.core.exceptions import (
    CollectionNotFoundError,
)
from geomemory.core.hashing import sha256_bytes
from geomemory.core.models import (
    Asset,
    AssetRevision,
    Job,
    ParsedObject,
    Segment,
    SourceRef,
    WorkspaceSettings,
)
from geomemory.core.workspace_collections import CollectionsMixin
from geomemory.core.workspace_shared import (
    logger,
)


class IngestMixin(CollectionsMixin):
    # ── Ingestion (synchronous core) ────────────────────────────────────────

    def ingest(
        self,
        source: str | Path | bytes,
        collection_id: str,
        *,
        parser: str | None = None,
        index_after: bool = True,
    ) -> Job:
        """Ingest a file or raw bytes into a collection.

        This executes the full pipeline synchronously and returns a completed
        ``Job``. Background execution is provided by the ingestion service.
        """
        collection = self.get_collection(collection_id)
        if collection is None:
            raise CollectionNotFoundError(f"Collection not found: {collection_id}")

        if isinstance(source, (str, Path)):
            src_path = Path(source)
            if not src_path.is_file():
                raise FileNotFoundError(f"Source file not found: {src_path}")
            raw = src_path.read_bytes()
            source_ref_path = str(src_path)
        elif isinstance(source, bytes):
            raw = source
            source_ref_path = "<bytes>"
        else:
            raise TypeError("source must be str, Path, or bytes")

        content_hash = sha256_bytes(raw)
        mime_type = _detect_mime(Path(source_ref_path))

        # Locate a live duplicate in the requested collection before LIMIT;
        # other collections and deleted assets may also reference this hash.
        existing = self.conn.execute(
            "SELECT r.id, r.asset_id FROM asset_revision AS r "
            "JOIN asset AS a ON a.id = r.asset_id "
            "WHERE r.hash = ? AND a.collection_id = ? AND a.deleted_at IS NULL "
            "ORDER BY r.ingested_at DESC, r.id LIMIT 1",
            (content_hash, collection_id),
        ).fetchone()
        if existing is not None:
            return _job_completed(
                "ingestion",
                {
                    "asset_id": existing["asset_id"],
                    "revision_id": existing["id"],
                    "skipped": True,
                    "reason": "duplicate hash",
                },
            )

        # Parse + chunk the document.
        kind = _kind_for_mime(mime_type)
        spatial_payload: dict[str, Any] | None = None
        if kind in ("raster", "vector"):
            chunks, spatial_payload = self._parse_spatial_source(source_ref_path, kind)
        elif mime_type == "application/pdf":
            chunks = _chunk_pdf(raw, source_ref_path, self._settings)
        else:
            chunks = _chunk_document(raw, mime_type, source_ref_path, parser=parser)

        # Store raw bytes in object store.
        stored_hash = self.objects.put_bytes(raw)
        assert stored_hash == content_hash

        # Create asset + revision.
        asset = Asset(collection_id=collection_id, kind=kind, title=Path(source_ref_path).name)
        asset_id = asset.id
        revision = AssetRevision(
            asset_id=asset_id,
            hash=content_hash,
            mime_type=mime_type,
            size_bytes=len(raw),
            parser_version="0.1.0",
        )
        with self._write_tx():
            self.conn.execute(
                "INSERT INTO asset (id, collection_id, kind, title, current_revision_id, deleted_at, created_at, metadata) "
                "VALUES (?, ?, ?, ?, ?, NULL, ?, ?)",
                (
                    asset.id,
                    asset.collection_id,
                    asset.kind,
                    asset.title,
                    None,
                    asset.created_at,
                    json.dumps(asset.metadata),
                ),
            )
            self.conn.execute(
                "INSERT INTO asset_revision (id, asset_id, hash, mime_type, size_bytes, parser_version, ingested_at, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    revision.id,
                    revision.asset_id,
                    revision.hash,
                    revision.mime_type,
                    revision.size_bytes,
                    revision.parser_version,
                    revision.ingested_at,
                    json.dumps(revision.metadata),
                ),
            )
            # Store segments (locators preserved; spatial metadata for rs assets).
            segment_ids: list[str] = []
            for chunk in chunks:
                meta = chunk.get("metadata") or {}
                segment = Segment(
                    revision_id=revision.id,
                    segment_type=chunk["segment_type"],
                    text=chunk["text"],
                    locator=chunk["locator"],
                    metadata=meta,
                )
                self.conn.execute(
                    "INSERT INTO segment (id, revision_id, segment_type, text, locator, parent_section_id, neighbor_ids, metadata, created_at) "
                    "VALUES (?, ?, ?, ?, ?, NULL, '[]', ?, ?)",
                    (
                        segment.id,
                        segment.revision_id,
                        segment.segment_type,
                        segment.text,
                        json.dumps(segment.locator),
                        json.dumps(meta),
                        segment.created_at,
                    ),
                )
                segment_ids.append(segment.id)

            # Persist raster scenes / vector layers and their spatial index entries.
            if spatial_payload is not None:
                if kind == "raster":
                    from geomemory.rs.persist import persist_scene

                    persist_scene(
                        self.conn,
                        revision.id,
                        spatial_payload["scene"],
                        tiles=spatial_payload.get("tiles"),
                        commit=False,
                    )
                elif kind == "vector":
                    from geomemory.rs.persist import persist_vector_layer

                    persist_vector_layer(self.conn, revision.id, spatial_payload["layer"], commit=False)

            self.conn.execute(
                "UPDATE asset SET current_revision_id = ? WHERE id = ?", (revision.id, asset.id)
            )

        # This best-effort filesystem index should only see committed tiles.
        if spatial_payload is not None and kind == "raster":
            try:
                from geomemory.ingest.vision_embed import try_embed_vision
                try_embed_vision(
                    conn=self.conn,
                    revision_id=revision.id,
                    vision_path=self.settings.vision_path,
                    index_dir=self.index_dir,
                )
            except Exception as exc:  # noqa: BLE001 - best-effort; never abort ingest
                logger.info("vision embed skipped for revision %s: %s", revision.id, exc)

        self.events.emit(
            DomainEvent(
                event_type=ASSET_CREATED,
                entity_id=asset.id,
                payload={
                    "revision_id": revision.id,
                    "hash": content_hash,
                    "mime_type": mime_type,
                    "segment_count": len(segment_ids),
                },
            )
        )

        return _job_completed(
            "ingestion",
            {"asset_id": asset.id, "revision_id": revision.id, "segment_count": len(segment_ids)},
        )

    def _parse_spatial_source(
        self, source_path: str, kind: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Parse a raster/vector source via the rs loaders into chunks + payload."""
        from geomemory.core.exceptions import UnsupportedFormatError
        from geomemory.core.models import SourceRef
        from geomemory.ingest.loaders.geojson import GeoJsonLoader
        from geomemory.ingest.loaders.geotiff import GeoTiffLoader
        from geomemory.rs.persist import spatial_metadata

        loader = (
            GeoTiffLoader(artifact_dir=self.path / "artifacts")
            if kind == "raster"
            else GeoJsonLoader()
        )
        parsed = list(loader.load(SourceRef(path=source_path)))
        if not parsed:
            raise UnsupportedFormatError(f"No spatial content parsed from {source_path}")
        obj = parsed[0]
        payload = obj.metadata.get("raster") or obj.metadata.get("vector") or {}
        scene = payload.get("scene")
        layer = payload.get("layer")
        spatial: dict[str, Any] = {}
        if scene:
            spatial = spatial_metadata(
                bbox=scene.get("bbox"),
                acquired_at=scene.get("acquired_at"),
                sensor=scene.get("sensor"),
            )
        elif layer:
            spatial = spatial_metadata(bbox=layer.get("bbox"))
        chunks = [
            {
                "text": obj.text,
                "segment_type": "paragraph",
                "locator": {"file": source_path},
                "metadata": {"spatial": spatial} if spatial else {},
            }
        ]
        return chunks, payload



# ──────────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ──────────────────────────────────────────────────────────────────────────────


def _detect_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    table = {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".py": "text/x-python",
        ".js": "text/javascript",
        ".ipynb": "application/x-ipynb+json",
        ".csv": "text/csv",
        ".geojson": "application/geo+json",
        ".gpkg": "application/geo+json",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }
    return table.get(suffix, "application/octet-stream")


AssetKind = Literal["document", "code", "raster", "vector", "table"]


def _kind_for_mime(mime_type: str) -> AssetKind:
    if mime_type.startswith("text/"):
        return "document"
    if mime_type in ("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
        return "document"
    if mime_type in ("text/x-python", "text/javascript"):
        return "code"
    if mime_type in ("image/tiff", "image/geotiff"):
        return "raster"
    if mime_type == "application/geo+json":
        return "vector"
    if mime_type == "application/x-shp":
        return "vector"
    if mime_type == "text/csv":
        return "table"
    return "document"


def _chunk_document(
    raw: bytes,
    mime_type: str,
    source_path: str,
    *,
    parser: str | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[dict[str, Any]]:
    """Parse raw bytes into a simple text representation and split into chunks.

    Structural chunking (header-first) is implemented in the ingest layer;
    this core fallback performs fixed-size token-approximation chunking so the
    workspace is usable standalone.
    """
    text = raw.decode("utf-8", errors="replace")
    # Simple header-aware splitting: split on newline, accumulate to size.
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[dict[str, Any]] = []
    current: list[str] = []
    current_tokens = 0
    approx_per_char = 0.25  # rough token estimate

    def flush() -> None:
        nonlocal current, current_tokens
        if current:
            joined = "\n".join(current)
            chunks.append(
                {
                    "text": joined,
                    "segment_type": "paragraph",
                    "locator": {"file": source_path},
                }
            )
            current = []
            current_tokens = 0

    for para in paragraphs:
        para_tokens = max(1, int(len(para) * approx_per_char))
        if current_tokens + para_tokens > chunk_size and current:
            flush()
        current.append(para)
        current_tokens += para_tokens
    flush()

    if not chunks and text.strip():
        chunks.append(
            {
                "text": text.strip()[:4000],
                "segment_type": "paragraph",
                "locator": {"file": source_path},
            }
        )
    return chunks


def _chunk_pdf(raw: bytes, source_path: str, settings: WorkspaceSettings) -> list[dict[str, Any]]:
    """Parse a PDF via the configured parser and chunk with header awareness.

    Falls back to PyMuPDF if the preferred parser (e.g. OpenDataLoader) fails
    on a specific PDF, then to plain-text decoding as a last resort.
    """
    from geomemory.ingest.chunkers import default_registry
    from geomemory.ingest.loaders import select_pdf_loader
    from geomemory.ingest.loaders.pdf import PdfLoader

    chunker_registry = default_registry()

    source = SourceRef(path=source_path)
    parsed_objects: list[ParsedObject] = []
    try:
        loader = select_pdf_loader(settings)
        parsed_objects = list(loader.load(source))
    except Exception:
        # Preferred parser failed on this PDF; try PyMuPDF fallback.
        with contextlib.suppress(Exception):
            parsed_objects = list(PdfLoader().load(source))
    if not parsed_objects:
        return []

    chunker = chunker_registry.get("header_then_token")
    if chunker is None:
        from geomemory.ingest.chunkers.header_then_token import HeaderThenTokenChunker
        chunker = HeaderThenTokenChunker()

    chunks: list[dict[str, Any]] = []
    for parsed in parsed_objects:
        for draft in chunker.split(parsed):
            chunks.append(
                {
                    "text": draft.text,
                    "segment_type": draft.segment_type,
                    "locator": draft.locator,
                    "metadata": draft.metadata,
                }
            )
    return chunks


_FTS_TERM_RE = re.compile(r"\w+", re.UNICODE)


def _job_completed(job_type: str, result: dict[str, Any]) -> Job:
    return Job(
        type=job_type,
        state="completed",
        progress=1.0,
        result=result,
    )
