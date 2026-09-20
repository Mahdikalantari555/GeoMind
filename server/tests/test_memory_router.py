from __future__ import annotations

from typing import Any

from geofront_api.state import get_state


def _seed_candidate(
    content: str,
    *,
    memory_type: str = "fact",
    project: str | None = None,
    observed_at: str | None = None,
    state: str = "verified",
) -> str:
    """Insert a candidate memory directly (bypasses the review pipeline)."""
    from geomemory.core.models import CandidateMemory
    from geomemory.feedback.candidate_memory import CandidateMemoryRepository

    ws = get_state().workspace
    assert ws is not None
    cm = CandidateMemory(
        content=content,
        memory_type=memory_type,  # type: ignore[arg-type]
        project=project,
        observed_at=observed_at,
        state=state,  # type: ignore[arg-type]
    )
    CandidateMemoryRepository(ws.conn).create(cm)
    return cm.id


def test_entity_profile_200(client, open_ws) -> None:
    _seed_candidate("OPTRAM works well for ETa in Khuzestan")
    resp = client.get("/api/v1/memory/entities/OPTRAM")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "OPTRAM"
    assert len(body["current_beliefs"]) == 1
    assert body["current_beliefs"][0]["content"].startswith("OPTRAM")
    assert body["history"] == body["current_beliefs"]
    assert isinstance(body["related_entities"], list)


def test_entity_profile_unknown_404(client, open_ws) -> None:
    resp = client.get("/api/v1/memory/entities/Nonesuch")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "entity_not_found"


def test_entity_profile_history_includes_superseded(client, open_ws) -> None:
    old = _seed_candidate("OPTRAM works everywhere", observed_at="2025-01-01T00:00:00Z")
    new = _seed_candidate("OPTRAM has saline limits", observed_at="2025-03-01T00:00:00Z")
    ws = get_state().workspace
    assert ws is not None
    from geomemory.feedback.candidate_memory import CandidateMemoryRepository

    CandidateMemoryRepository(ws.conn).mark_superseded(old, new)
    body = client.get("/api/v1/memory/entities/OPTRAM").json()
    assert [cm["id"] for cm in body["current_beliefs"]] == [new]
    assert old in {cm["id"] for cm in body["history"]}


def test_timeline_200_shape_and_order(client, open_ws) -> None:
    _seed_candidate("early decision", memory_type="decision", project="DSPIT", observed_at="2025-01-01T00:00:00Z")
    _seed_candidate("late hypothesis", memory_type="hypothesis", project="DSPIT", observed_at="2025-05-01T00:00:00Z")
    _seed_candidate("other project", project="PIDL")
    resp = client.get("/api/v1/research/timeline", params={"project": "DSPIT"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["project"] == "DSPIT"
    assert body["total"] == 2
    assert [item["content"] for item in body["items"]] == ["late hypothesis", "early decision"]


def test_timeline_type_filter(client, open_ws) -> None:
    _seed_candidate("a decision", memory_type="decision", project="DSPIT")
    _seed_candidate("a hypothesis", memory_type="hypothesis", project="DSPIT")
    body = client.get("/api/v1/research/timeline", params={"project": "DSPIT", "type": "decision"}).json()
    assert body["total"] == 1
    assert body["items"][0]["memory_type"] == "decision"


def test_timeline_as_of_filter(client, open_ws) -> None:
    _seed_candidate("old", project="DSPIT", observed_at="2025-01-01T00:00:00Z")
    _seed_candidate("new", project="DSPIT", observed_at="2025-06-01T00:00:00Z")
    body = client.get("/api/v1/research/timeline", params={"project": "DSPIT", "as_of": "2025-02-01T00:00:00Z"}).json()
    assert body["total"] == 1
    assert body["items"][0]["content"] == "old"


def test_timeline_pagination_boundaries(client, open_ws) -> None:
    for i in range(5):
        _seed_candidate(f"item {i}", project="DSPIT", observed_at=f"2025-01-0{i + 1}T00:00:00Z")
    page1: dict[str, Any] = client.get("/api/v1/research/timeline", params={"project": "DSPIT", "offset": 0, "limit": 2}).json()
    page2: dict[str, Any] = client.get("/api/v1/research/timeline", params={"project": "DSPIT", "offset": 2, "limit": 2}).json()
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2
    assert page1["total"] == page2["total"] == 5
    assert {i["id"] for i in page1["items"]}.isdisjoint({i["id"] for i in page2["items"]})
    # offset past the end returns empty items but the same total
    past: dict[str, Any] = client.get("/api/v1/research/timeline", params={"project": "DSPIT", "offset": 10, "limit": 2}).json()
    assert past["items"] == []
    assert past["total"] == 5


def test_timeline_unknown_project_empty(client, open_ws) -> None:
    body = client.get("/api/v1/research/timeline", params={"project": "NOPE"}).json()
    assert body["items"] == []
    assert body["total"] == 0
