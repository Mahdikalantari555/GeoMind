"""Tests for doctor endpoint vision/embedding availability flags."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_doctor_includes_vision_model_available(
    client: TestClient, open_ws: dict[str, object]
) -> None:
    resp = client.get("/api/v1/doctor")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "diagnostics" in body
    assert "vision" in body["diagnostics"]
    assert "model_available" in body["diagnostics"]["vision"], (
        f"diagnostics.vision missing model_available field; actual keys: {body['diagnostics']['vision'].keys()}"
    )


def test_doctor_includes_embedding_model_available(
    client: TestClient, open_ws: dict[str, object]
) -> None:
    resp = client.get("/api/v1/doctor")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "diagnostics" in body
    assert "embedding" in body["diagnostics"]
    assert "model_available" in body["diagnostics"]["embedding"], (
        f"diagnostics.embedding missing model_available field; actual keys: {body['diagnostics']['embedding'].keys()}"
    )


def test_doctor_llm_probe(client: TestClient, open_ws: dict[str, object]) -> None:
    resp = client.get("/api/v1/doctor/llm")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "provider" in body
    assert "key_configured" in body

    # Test active probe with test=true
    resp_test = client.get("/api/v1/doctor/llm?test=true")
    assert resp_test.status_code == 200, resp_test.text
    body_test = resp_test.json()
    assert "reachable" in body_test
    assert "error" in body_test or "latency_ms" in body_test

