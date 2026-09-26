from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from geofront_api.state import get_state

from tests.integration.conftest import DeterministicLLMBackend


def test_ingest_text_document(gateway: TestClient) -> None:
    """Requirement 1: Gateway persists text document and returns SHA-256 matching content."""
    content = b"Remote sensing evapotranspiration monitoring via Landsat and Sentinel-2.\n"
    content_hash = hashlib.sha256(content).hexdigest()

    resp = gateway.post(
        "/api/v1/asset",
        json={"filename": "et_monitoring.txt", "content": content.decode("utf-8")},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    asset_id = data["id"]
    assert data["sha256"] == content_hash
    assert data["kind"] == "document"

    # GET /api/v1/assets returns the record with identical sha256
    list_resp = gateway.get("/api/v1/assets")
    assert list_resp.status_code == 200, list_resp.text
    assets: list[dict[str, Any]] = list_resp.json()
    matching = [a for a in assets if a["id"] == asset_id]
    assert len(matching) == 1
    assert matching[0]["sha256"] == content_hash


def test_ingest_geojson_vector(gateway: TestClient) -> None:
    """Requirement 1: Ingest sample GeoJSON vector and verify status 201 with kind=vector."""
    sample_path = Path("sample/sasmple.geojson")
    assert sample_path.exists(), "sample/sasmple.geojson must exist"
    geojson_data = json.loads(sample_path.read_text(encoding="utf-8"))

    resp = gateway.post("/api/v1/asset", json=geojson_data)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["kind"] == "vector"
    assert data["sha256"] != ""


def test_search_returns_real_dense_hits(gateway: TestClient) -> None:
    """Requirement 2: Search with mode='dense' returns real dense hits with non-null dense_score."""
    text_content = (
        "NDVI (Normalized Difference Vegetation Index) is a standardized index showing relative biomass. "
        "High NDVI indicates healthy, dense vegetation canopy."
    )
    ingest_resp = gateway.post(
        "/api/v1/asset",
        json={"filename": "ndvi_guide.txt", "content": text_content},
    )
    assert ingest_resp.status_code == 201, ingest_resp.text

    search_resp = gateway.post(
        "/api/v1/search",
        json={"query": "NDVI", "mode": "dense", "top_k": 5},
    )
    assert search_resp.status_code == 200, search_resp.text
    search_data = search_resp.json()
    hits: list[dict[str, Any]] = search_data["hits"]
    assert len(hits) >= 1

    ws = get_state().require_workspace()
    conn = sqlite3.connect(ws.path / "geomemory.db")
    try:
        cur = conn.cursor()
        for hit in hits:
            assert hit["dense_score"] is not None
            assert hit["dense_score"] > 0
            # Locator references an existing segment
            cur.execute("SELECT id FROM segment WHERE id = ?", (hit["id"],))
            assert cur.fetchone() is not None, f"Segment {hit['id']} not in database"
    finally:
        conn.close()


def test_ask_citations_resolve(gateway: TestClient, _llm_backend: DeterministicLLMBackend) -> None:
    """Requirement 3: Provenance chain (answer -> citation -> segment -> asset_revision -> objects/<sha256>)."""
    text_content = (
        "Sugarcane water stress decreases canopy conductance and crop coefficient Kc. "
        "METRIC energy balance mapping tracks evapotranspiration deficits across field parcels."
    )
    ingest_resp = gateway.post(
        "/api/v1/asset",
        json={"filename": "sugarcane_et.txt", "content": text_content},
    )
    assert ingest_resp.status_code == 201, ingest_resp.text

    ask_resp = gateway.post(
        "/api/v1/ask",
        json={"question": "What happens to sugarcane under water stress?"},
    )
    assert ask_resp.status_code == 200, ask_resp.text
    qa_data = ask_resp.json()
    assert qa_data["abstained"] is False
    assert len(qa_data["citations"]) >= 1

    ws = get_state().require_workspace()
    conn = sqlite3.connect(ws.path / "geomemory.db")
    try:
        cur = conn.cursor()
        for cit in qa_data["citations"]:
            seg_id = cit["segment_id"]
            # 1. citation segment_id resolves to segment table
            cur.execute("SELECT revision_id FROM segment WHERE id = ?", (seg_id,))
            seg_row = cur.fetchone()
            assert seg_row is not None, f"segment {seg_id} not found in DB"
            revision_id = seg_row[0]

            # 2. segment revision_id resolves to asset_revision table
            cur.execute("SELECT hash FROM asset_revision WHERE id = ?", (revision_id,))
            rev_row = cur.fetchone()
            assert rev_row is not None, f"asset_revision {revision_id} not found in DB"
            content_hash = rev_row[0]

            # 3. revision hash resolves to a file under objects/sha256/
            obj_path = ws.path / "objects" / "sha256" / content_hash[:2] / content_hash[2:4] / content_hash
            assert obj_path.exists(), f"Object file {obj_path} does not exist"
            assert obj_path.is_file()
            # Verify file content SHA-256 matches
            actual_hash = hashlib.sha256(obj_path.read_bytes()).hexdigest()
            assert actual_hash == content_hash
    finally:
        conn.close()
