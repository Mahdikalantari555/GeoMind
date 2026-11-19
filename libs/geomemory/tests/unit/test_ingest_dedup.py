from pathlib import Path
from typing import Any

from geomemory import GeoMemory
from geomemory.storage.repositories.asset_repo import AssetRepository


def ingest(ws: GeoMemory, path: Path, collection_id: str) -> dict[str, Any]:
    result = ws.ingest(path, collection_id).result
    assert result is not None
    return result


def test_dedup_only_reuses_assets_in_the_requested_collection(
    temp_workspace: GeoMemory, sample_markdown: Path
) -> None:
    ws = temp_workspace
    a = ws.create_collection("first")
    b = ws.create_collection("second")
    first = ingest(ws, sample_markdown, a.id)
    second = ingest(ws, sample_markdown, b.id)

    assert second["asset_id"] != first["asset_id"]
    assert not second.get("skipped")
    detail = ws.inspect(second["asset_id"])
    assert detail.asset.collection_id == b.id
    assert detail.revision is not None
    assert ws.objects.get(detail.revision.hash) == sample_markdown.read_bytes()
    assert ws.objects.total_objects() == 1

    for col, original in ((a, first), (b, second)):
        duplicate = ingest(ws, sample_markdown, col.id)
        assert duplicate["skipped"] is True
        assert duplicate["asset_id"] == original["asset_id"]
        assert duplicate["revision_id"] == original["revision_id"]


def test_reingest_after_soft_delete_reuses_only_the_live_replacement(
    temp_workspace: GeoMemory, sample_markdown: Path
) -> None:
    ws = temp_workspace
    col = ws.create_collection("docs")
    original = ingest(ws, sample_markdown, col.id)
    assert AssetRepository(ws.conn).soft_delete(original["asset_id"])

    replacement = ingest(ws, sample_markdown, col.id)
    assert replacement["asset_id"] != original["asset_id"]
    assert not replacement.get("skipped")
    assert ingest(ws, sample_markdown, col.id)["asset_id"] == replacement["asset_id"]
    assert ws.objects.total_objects() == 1
