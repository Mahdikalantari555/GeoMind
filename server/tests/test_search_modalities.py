from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from .conftest import make_collection, wait_job


def ingest_text(client: TestClient, collection_id: str, text: bytes, filename: str = "notes.md") -> dict:
    resp = client.post(
        "/api/v1/ingest/bytes",
        json={
            "filename": filename,
            "data_base64": base64.b64encode(text).decode(),
            "collection_id": collection_id,
            "index_after": False,
        },
    )
    assert resp.status_code == 202
    job = wait_job(client, resp.json()["job_id"])
    assert job["status"] == "completed", job
    return job


class TestSearchModalities:
    def test_search_accepts_modalities_param(self, client: TestClient, open_ws: dict) -> None:
        cid = make_collection(client)
        ingest_text(
            client,
            cid,
            b"# NDVI monitoring\nSugarcane fields under stress show NDVI decline.\n" * 5,
        )
        resp = client.post(
            "/api/v1/search",
            json={"query": "ndvi", "mode": "hybrid", "modalities": "text"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["query_plan"]["modalities"] == "text"
        assert body["total_hits"] >= 1

    def test_search_forwards_modalities_image(self, client: TestClient, open_ws: dict) -> None:
        cid = make_collection(client)
        ingest_text(
            client,
            cid,
            b"# Notes\nnothing relevant here.\n" * 3,
        )
        # Image-only search on empty image index returns zero image hits; still 200
        resp = client.post(
            "/api/v1/search",
            json={"query": "anything", "mode": "dense", "modalities": "image", "top_n": 3},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["query_plan"]["modalities"] == "image"

    def test_search_accepts_modalities_both(self, client: TestClient, open_ws: dict) -> None:
        cid = make_collection(client)
        ingest_text(
            client,
            cid,
            b"# Crop report\nWheat yield increased by 12 percent.\n" * 5,
        )
        resp = client.post(
            "/api/v1/search",
            json={"query": "wheat", "mode": "hybrid", "modalities": "both", "top_n": 5},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["query_plan"]["modalities"] == "both"
        assert body["total_hits"] >= 1


class TestAskModalities:
    def test_ask_accepts_modalities_param(self, client: TestClient, open_ws: dict) -> None:
        cid = make_collection(client)
        ingest_text(
            client,
            cid,
            b"# Irrigation notes\nDeficit irrigation reduces yield by 20 percent.\n" * 5,
        )
        resp = client.post(
            "/api/v1/ask",
            json={"question": "What is the effect of deficit irrigation?", "modalities": "text"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["abstained"] is True  # offline, no LLM
        # Sources should include retrieved segments
        assert "sources" in body

    def test_ask_accepts_modalities_image(self, client: TestClient, open_ws: dict) -> None:
        cid = make_collection(client)
        ingest_text(
            client,
            cid,
            b"# Random text\nsome content.\n" * 3,
        )
        resp = client.post(
            "/api/v1/ask",
            json={"question": "predictive models", "modalities": "image"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["abstained"] is True
