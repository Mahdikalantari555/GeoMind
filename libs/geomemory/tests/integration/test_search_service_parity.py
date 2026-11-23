"""Spike: facade retrieval vs. the SearchService adapter (DIRECTION-01).

Golden fixtures assert that routing retrieval through the SearchService
adapter yields the same hits as the facade's own search path. If these ever
diverge, converging the facade onto SearchService adapters is unsafe.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from geomemory import GeoMemory
from geomemory.core.workspace_search import _WorkspaceSearchAdapter

pytestmark = pytest.mark.integration

GOLDEN_DOC = """# Canopy stress thresholds

The NDVI threshold for severe sugarcane water stress is 0.42 in Khuzestan.
Sentinel-2 band 8 (near infrared) and band 4 (red) compute NDVI.
"""


@pytest.fixture()
def workspace(tmp_path: Path) -> GeoMemory:
    ws = GeoMemory.create(tmp_path / "ws")
    collection = ws.create_collection("papers")
    doc = tmp_path / "thresholds.md"
    doc.write_text(GOLDEN_DOC, encoding="utf-8")
    ws.ingest(str(doc), collection_id=collection.id)
    return ws


def _ids(hits: object) -> list[str]:
    return [hit.id for hit in hits]  # type: ignore[attr-defined]


@pytest.mark.parametrize("query", ["NDVI threshold", "sugarcane water stress", "Sentinel-2 band 8"])
def test_adapter_matches_facade_golden_hits(workspace: GeoMemory, query: str) -> None:
    direct = workspace.search(query, top_k=10)
    via_adapter = _WorkspaceSearchAdapter(workspace).search(query, top_k=10)

    assert _ids(via_adapter.hits) == _ids(direct.hits)
    assert [hit.text for hit in via_adapter.hits] == [hit.text for hit in direct.hits]  # type: ignore[attr-defined]
