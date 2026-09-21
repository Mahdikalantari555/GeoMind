"""Best-effort OLMoEarth vision embedding after raster persistence."""

from __future__ import annotations

import contextlib
import logging
import sqlite3
from pathlib import Path
from typing import Any

from geomemory.core.models import IndexManifest
from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder
from geomemory.index.image_index import ImageIndex
from geomemory.index.manifest import create_manifest

logger = logging.getLogger(__name__)

_MAX_TILES_TO_EMBED = 100


def try_embed_vision(
    *,
    conn: sqlite3.Connection,
    revision_id: str,
    vision_path: str | None,
    index_dir: Path | str,
) -> None:
    """Upsert tile previews into ImageIndex when ``vision_path`` is configured.

    If torch/olmoearth_pretrain are unavailable or any step fails, nothing
    propagates — ingest must remain unaffected.
    """
    if not vision_path:
        return

    try:
        embedder = OlmoEarthVisionEmbedder(vision_path)
    except Exception:  # noqa: BLE001 - model may not be installable yet
        return

    scene_row = conn.execute(
        "SELECT id FROM raster_scene WHERE revision_id = ?", (revision_id,)
    ).fetchone()
    if scene_row is None:
        return
    scene_id = str(scene_row["id"])

    tiles = conn.execute(
        "SELECT id, preview_path FROM raster_tile WHERE scene_id = ?", (scene_id,)
    ).fetchall()
    if not tiles:
        return

    preview_paths = [
        str(t["preview_path"]) for t in tiles[:_MAX_TILES_TO_EMBED] if t["preview_path"]
    ]
    if not preview_paths:
        return

    try:
        embeddings = embedder.embed_images(preview_paths)
    except Exception:  # noqa: BLE001 - model may fail at runtime
        return
    if embeddings.shape[0] != len(preview_paths):
        return

    index = _load_image_index(index_dir)
    for i, _ in enumerate(preview_paths):
        tile_id = str(tiles[i]["id"])
        index.upsert(tile_id, embeddings[i])
    _save_image_index(index, index_dir, space_id=embedder.space_id)


def _load_image_index(index_dir: Path | str) -> ImageIndex:
    target = Path(index_dir) / "image"
    try:
        return ImageIndex.load(target)
    except Exception:
        return ImageIndex()


def _determine_dimension(index: Any) -> int:
    dim: int | None = None
    if hasattr(index, "dimension") and callable(index.dimension):
        with contextlib.suppress(Exception):
            dim = index.dimension()
    if dim is None and hasattr(index, "vector") and callable(index.vector):
        with contextlib.suppress(Exception):
            vec = index.vector(0)
            if hasattr(vec, "shape") and len(vec.shape) > 0:
                dim = int(vec.shape[-1])
    if dim is None and hasattr(index, "vectors"):
        with contextlib.suppress(Exception):
            vecs = index.vectors(0) if callable(index.vectors) else index.vectors
            if hasattr(vecs, "shape") and len(vecs.shape) > 0:
                dim = int(vecs.shape[-1])
    if dim is None and hasattr(index, "_embeddings") and isinstance(index._embeddings, dict) and index._embeddings:
        with contextlib.suppress(Exception):
            first_val = next(iter(index._embeddings.values()))
            if hasattr(first_val, "shape") and len(first_val.shape) > 0:
                dim = int(first_val.shape[-1])
    if dim is None or dim <= 0:
        logger.warning("could not determine vision embedding dimension, defaulting to 768")
        return 768
    return dim


def _save_image_index(
    index: ImageIndex, index_dir: Path | str, *, space_id: str
) -> None:
    target = Path(index_dir) / "image"
    dimension = _determine_dimension(index)
    manifest: IndexManifest | None = None
    with contextlib.suppress(Exception):
        from geomemory.index.manifest import load_manifest

        existing = load_manifest(target)
        manifest = create_manifest(
            space_id=existing.space_id or space_id,
            model_id="olmoearth-nano-v1.2",
            dimension=dimension,
            doc_count=index.count(),
        )
    if manifest is None:
        manifest = create_manifest(
            space_id=space_id,
            model_id="olmoearth-nano-v1.2",
            dimension=dimension,
            doc_count=index.count(),
        )
    index.save(target, manifest)
