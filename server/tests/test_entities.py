from __future__ import annotations

from fastapi.testclient import TestClient
from geomemory import Entity, GeoMemory
from geomemory.storage.repositories.entity_repo import EntityRepository


def _seed_entities(client: TestClient, open_ws: dict) -> tuple[str, str]:
    workspace_path = client.get("/api/v1/workspace").json()["path"]
    ws = GeoMemory.open(workspace_path)
    try:
        wid = ws._workspace_id()
        repo = EntityRepository(ws.conn)
        metric = repo.create(Entity(name="NDVI", kind="metric", workspace_id=wid))
        location = repo.create(Entity(name="FieldStation", kind="location", workspace_id=wid))
        ws.conn.execute(
            "INSERT INTO relation (id, source_id, predicate, target_id, confidence) "
            "VALUES (?, ?, ?, ?, ?)",
            ("rel_1", metric.id, "measured_in", location.id, 0.9),
        )
        ws.conn.commit()
    finally:
        ws.close()
    return metric.id, location.id


class TestEntitiesRouter:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.get("/api/v1/entities")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "workspace_not_open"

    def test_list_entities_empty(self, client: TestClient, open_ws: dict) -> None:
        resp = client.get("/api/v1/entities")
        assert resp.status_code == 200
        body = resp.json()
        assert body["entities"] == []

    def test_list_entities_filter_by_kind(self, client: TestClient, open_ws: dict) -> None:
        _seed_entities(client, open_ws)
        resp = client.get("/api/v1/entities?kind=metric")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["entities"]) == 1
        assert body["entities"][0]["kind"] == "metric"

    def test_entity_relations_missing(self, client: TestClient, open_ws: dict) -> None:
        resp = client.get("/api/v1/entities/nonexistent-id/relations")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "entity_not_found"

    def test_entity_relations_closed_workspace(self, client: TestClient) -> None:
        resp = client.get("/api/v1/entities/some-id/relations")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "workspace_not_open"

    def test_entity_relations_for_known_entity(self, client: TestClient, open_ws: dict) -> None:
        metric_id, location_id = _seed_entities(client, open_ws)
        resp = client.get(f"/api/v1/entities/{metric_id}/relations")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["relations"]) == 1
        rel = body["relations"][0]
        assert rel["source_id"] == metric_id
        assert rel["predicate"] == "measured_in"
        assert rel["target_id"] == location_id
        assert rel["confidence"] == 0.9
