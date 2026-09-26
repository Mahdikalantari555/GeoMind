"""Unit tests for AssetLayout logical-to-physical path resolution."""

from __future__ import annotations

from pathlib import Path

from geomemory.storage.asset_layout import AssetLayout


def test_asset_layout_paths(tmp_path: Path) -> None:
    layout = AssetLayout(tmp_path)
    content_hash = "a" * 64

    # logical path
    doc_path = layout.logical_path(content_hash, kind="document")
    assert doc_path.startswith("assets/documents/aa/aa/")
    assert doc_path.endswith(content_hash)

    raster_path = layout.logical_path(content_hash, kind="raster")
    assert raster_path.startswith("assets/imagery/aa/aa/")

    vector_path = layout.logical_path(content_hash, kind="vector")
    assert vector_path.startswith("assets/vectors/aa/aa/")

    dataset_path = layout.logical_path(content_hash, kind="dataset")
    assert dataset_path.startswith("assets/datasets/aa/aa/")

    unknown_path = layout.logical_path(content_hash, kind="unknown_kind")
    assert unknown_path.startswith("assets/documents/aa/aa/")

    # physical path
    phys = layout.physical_path(content_hash)
    assert phys == tmp_path / "objects" / "sha256" / "aa" / "aa" / content_hash

    # resolve
    assert layout.resolve(content_hash, "raster") == phys

    # kind_for_logical
    assert layout.kind_for_logical("assets/imagery/foo") == "raster"
    assert layout.kind_for_logical("assets/vectors/foo") == "vector"
    assert layout.kind_for_logical("assets/datasets/foo") == "table"
    assert layout.kind_for_logical("assets/documents/foo") == "document"
    assert layout.kind_for_logical("other/path") == "document"
