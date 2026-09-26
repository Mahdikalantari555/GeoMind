"""Unit tests for IngestionPipeline in geomemory.ingest.pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from geomemory.core.exceptions import CollectionNotFoundError
from geomemory.core.models import SourceRef
from geomemory.ingest.pipeline import IngestionPipeline, _kind_for_mime
from geomemory.storage.object_store import ObjectStore


class DummyExtractor:
    def extract(self, text: str) -> list[tuple[str, str, tuple[float, float, float, float] | None]]:
        if "fail" in text:
            raise RuntimeError("Extractor error")
        return [("Sentinel-2", "sensor", (-120.0, 35.0, -119.0, 36.0))]


def test_kind_for_mime() -> None:
    assert _kind_for_mime("text/markdown") == "document"
    assert _kind_for_mime("application/pdf") == "document"
    assert _kind_for_mime("image/tiff") == "raster"
    assert _kind_for_mime("application/geo+json") == "vector"
    assert _kind_for_mime("unknown/type") == "document"


def test_pipeline_resolve_loader_and_spatial_metadata(temp_workspace, tmp_path: Path) -> None:
    conn = temp_workspace.conn
    objects = ObjectStore(tmp_path / "objects")
    pipeline = IngestionPipeline(conn, objects, artifact_dir=tmp_path / "artifacts")

    # GeoJSON resolution
    loader_geojson = pipeline._resolve_loader(SourceRef(path="/path/test.geojson"))
    assert loader_geojson.__class__.__name__ == "GeoJsonLoader"

    # GeoTIFF resolution
    loader_geotiff = pipeline._resolve_loader(SourceRef(path="/path/test.tif"))
    assert loader_geotiff.__class__.__name__ == "GeoTiffLoader"

    # _attach_spatial_metadata
    col = temp_workspace.create_collection("spatial_docs")
    res = pipeline.ingest_source(SourceRef(content_bytes=b"Hello spatial"), col.id)
    # Get segment id
    seg_row = conn.execute("SELECT id FROM segment WHERE revision_id = ?", (res["revision_id"],)).fetchone()
    pipeline._attach_spatial_metadata([seg_row["id"]], {"sensor": "Landsat-8", "bbox": [0, 0, 1, 1]})
    updated_row = conn.execute("SELECT metadata FROM segment WHERE id = ?", (seg_row["id"],)).fetchone()
    assert "Landsat-8" in updated_row["metadata"]


def test_ingestion_pipeline_lifecycle(temp_workspace, tmp_path: Path) -> None:
    conn = temp_workspace.conn
    objects = ObjectStore(tmp_path / "objects")
    pipeline = IngestionPipeline(
        conn,
        objects,
        entity_extractor=DummyExtractor(),
        artifact_dir=tmp_path / "artifacts",
    )

    # Missing collection raises CollectionNotFoundError
    src1 = SourceRef(content_bytes=b"# Test\n\nContent for ingestion.")
    with pytest.raises(CollectionNotFoundError):
        pipeline.ingest_source(src1, "non_existent_col")

    # Valid collection
    col = temp_workspace.create_collection("docs")
    res1 = pipeline.ingest_source(src1, col.id)
    assert res1["skipped"] is False
    assert res1["asset_id"] is not None
    assert res1["segment_count"] >= 1

    # Duplicate hash deduplication
    res2 = pipeline.ingest_source(src1, col.id)
    assert res2["skipped"] is True
    assert res2["reason"] == "duplicate hash"
    assert res2["asset_id"] == res1["asset_id"]

    # Ingest from path
    sample_file = tmp_path / "sample.md"
    sample_file.write_text("# Chapter 1\n\nText from disk.")
    src_file = SourceRef(path=str(sample_file))
    res3 = pipeline.ingest_source(src_file, col.id)
    assert res3["skipped"] is False

    # SourceRef without path or content_bytes
    with pytest.raises(ValueError, match="SourceRef has no local content"):
        pipeline.ingest_source(SourceRef(url="http://example.com"), col.id)

    # Ingest batch with successes and failures
    bad_source = SourceRef(path="/path/that/does/not/exist.md")
    src4 = SourceRef(content_bytes=b"# Batch 1\n\nSuccess file.")
    batch_res = pipeline.ingest_batch([src4, bad_source], col.id)
    assert batch_res["success_count"] == 1
    assert batch_res["error_count"] == 1
    assert len(batch_res["errors"]) == 1

    # Entity extractor exception handling
    src_fail_extractor = SourceRef(content_bytes=b"# fail\n\nTrigger extractor exception.")
    res_fail = pipeline.ingest_source(src_fail_extractor, col.id)
    assert res_fail["skipped"] is False
