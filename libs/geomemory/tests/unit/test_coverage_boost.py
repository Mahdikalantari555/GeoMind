"""Comprehensive coverage tests for services, storage, and evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from geomemory.eval.pipeline_stats import STATS_FIELDS, collect_stats, is_valid_stats, stats_to_json
from geomemory.eval.run_store import BaselineStore, RunStore, _sanitize_dataset
from geomemory.services.research_timeline_service import ResearchTimelineService
from geomemory.storage.repositories.conversation_repo import ConversationRepository, TurnRepository
from geomemory.storage.repositories.spatial_repo import SpatialRepository


def test_research_timeline_service(temp_workspace) -> None:
    conn = temp_workspace.conn
    service = ResearchTimelineService(conn)

    # Insert test candidate memories into sqlite directly
    conn.execute(
        "INSERT INTO candidate_memory (id, project, content, memory_type, state, confidence_score, observed_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("cm1", "proj-alpha", "Fact A", "fact", "verified", 0.9, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO candidate_memory (id, project, content, memory_type, state, confidence_score, observed_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("cm2", "proj-alpha", "Correction B", "correction", "proposed", 0.7, "2026-02-01T00:00:00Z", "2026-02-01T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO candidate_memory (id, project, content, memory_type, state, confidence_score, observed_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("cm3", "proj-beta", "Fact C", "fact", "proposed", 0.5, "2026-03-01T00:00:00Z", "2026-03-01T00:00:00Z"),
    )
    conn.commit()

    # Timeline with all memory types
    tl = service.get_timeline("proj-alpha")
    assert tl["total"] == 2
    assert len(tl["items"]) == 2
    assert tl["items"][0].id == "cm2"  # newest observed_at first

    # Timeline with filtered memory types
    tl_filtered = service.get_timeline("proj-alpha", memory_types=["fact"])
    assert tl_filtered["total"] == 1
    assert tl_filtered["items"][0].id == "cm1"

    # Timeline with as_of filter
    tl_as_of = service.get_timeline("proj-alpha", as_of="2026-01-15T00:00:00Z")
    assert tl_as_of["total"] == 1
    assert tl_as_of["items"][0].id == "cm1"

    # Timeline with pagination
    tl_page = service.get_timeline("proj-alpha", offset=1, limit=1)
    assert len(tl_page["items"]) == 1
    assert tl_page["items"][0].id == "cm1"


def test_pipeline_stats_and_run_store(tmp_path: Path, temp_workspace) -> None:
    conn = temp_workspace.conn
    stats = collect_stats(conn, temp_workspace.path, duration_seconds=1.23)
    assert is_valid_stats(stats)
    assert stats["duration_seconds"] == 1.23
    for f in STATS_FIELDS:
        assert f in stats

    # Invalid stats check
    assert not is_valid_stats("not a dict")
    assert not is_valid_stats({"files": 1})
    assert not is_valid_stats({f: "bad" for f in STATS_FIELDS})
    assert not is_valid_stats({**{f: 1 for f in STATS_FIELDS}, "files": True})

    # stats_to_json
    json_str = stats_to_json(stats)
    parsed = json.loads(json_str)
    assert parsed["duration_seconds"] == 1.23

    # RunStore write, append, read, list
    store = RunStore(tmp_path / "runs")
    with pytest.raises(ValueError, match="Invalid dataset name"):
        _sanitize_dataset("..")

    run_dir = store.write_run(
        "ds_test",
        "bench1",
        stats,
        [{"query": "ndvi", "retrieved": ["seg1"]}],
        timestamp="20260901T120000Z",
        metrics={"f1": 0.88},
    )
    assert run_dir.is_dir()

    # Second write with same timestamp creates suffixed directory
    run_dir2 = store.write_run(
        "ds_test",
        "bench2",
        stats,
        [{"query": "flood"}],
        timestamp="20260901T120000Z",
        metrics={"recall": 0.95},
    )
    assert run_dir2 != run_dir
    assert run_dir2.is_dir()

    # Read run
    run_data = store.read_run("ds_test", "20260901T120000Z")
    assert "bench1" in run_data["benchmarks"]

    # List runs
    runs = store.list_runs("ds_test")
    assert len(runs) >= 2

    # write_stats_only
    stats_dir = store.write_stats_only("ds_test", stats)
    assert (stats_dir / "stats.json").is_file()

    # BaselineStore
    bl_store = BaselineStore(tmp_path / "baselines")
    bl_store.set("ds_test", "20260901T120000Z", str(run_dir), {"bench1": {"f1": 0.88}})
    bl = bl_store.get("ds_test")
    assert bl is not None
    assert bl["timestamp"] == "20260901T120000Z"
    assert len(bl_store.list_datasets()) == 1


def test_workspace_advanced_operations(temp_workspace, sample_markdown) -> None:
    ws = temp_workspace
    col = ws.create_collection("docs")
    ws.ingest(sample_markdown, collection_id=col.id)

    # Asset pagination in list_assets
    assets = ws.list_assets(col.id, limit=1, offset=0)
    assert len(assets) == 1

    # Knowledge change proposals
    cm = ws.create_candidate_memory("Updated sensor spec for Sentinel-2", memory_type="fact")
    proposal = ws.create_proposal(
        proposal_type="entity_create",
        diff={"name": "Sentinel-2", "entity_type": "sensor"},
        source_candidate_ids=[cm.id],
        confidence=0.95,
    )
    assert proposal.id is not None
    assert proposal.status == "pending"

    # Review proposal: approve
    approved = ws.review_proposal(proposal.id, approve=True, reviewer_id="rev-user")
    assert approved is not None
    assert approved.status == "approved"

    # Reject proposal test
    p2 = ws.create_proposal(
        proposal_type="metadata_update",
        diff={"action": "drop"},
        source_candidate_ids=[cm.id],
    )
    rejected = ws.review_proposal(p2.id, approve=False, reviewer_id="rev-user")
    assert rejected is not None
    assert rejected.status == "rejected"

    # Entity traversal
    ws_id = ws._workspace_id()
    # Insert entity and relation
    ws.conn.execute(
        "INSERT INTO entity (id, workspace_id, name, kind) VALUES (?, ?, ?, ?)",
        ("ent1", ws_id, "Crop Health", "concept"),
    )
    ws.conn.execute(
        "INSERT INTO entity (id, workspace_id, name, kind) VALUES (?, ?, ?, ?)",
        ("ent2", ws_id, "NDVI", "metric"),
    )
    ws.conn.execute(
        "INSERT INTO relation (id, source_id, predicate, target_id) VALUES (?, ?, ?, ?)",
        ("rel1", "ent1", "measured_by", "ent2"),
    )
    ws.conn.commit()

    graph = ws.traverse("ent1", depth=1)
    assert graph["entity"] is not None
    assert graph["entity"]["id"] == "ent1"
    assert len(graph["relations"]) == 1
    assert graph["relations"][0]["target"]["id"] == "ent2"

    # Search images fallback
    img_hits = ws.search_images([0.1] * 128, top_k=5)
    assert isinstance(img_hits, list)


def test_conversation_repo_lifecycle(temp_workspace) -> None:
    from geomemory.core.models import Conversation, Turn

    ws_id = temp_workspace._workspace_id()
    repo = ConversationRepository(temp_workspace.conn)
    conv = Conversation(workspace_id=ws_id, title="Discussion on drought")
    repo.create(conv)
    assert conv.id is not None
    assert conv.title == "Discussion on drought"

    # List conversations
    convs = repo.list_by_workspace(ws_id)
    assert any(c.id == conv.id for c in convs)

    # Get conversation
    fetched = repo.get(conv.id)
    assert fetched is not None
    assert fetched.title == conv.title

    # Add turn
    turn_repo = TurnRepository(temp_workspace.conn)
    turn = Turn(conversation_id=conv.id, role="user", content="What is ETa?")
    turn_repo.create(turn)
    assert turn.id is not None
    assert turn.role == "user"

    # List turns
    turns = turn_repo.list_by_conversation(conv.id)
    assert len(turns) == 1
    assert turns[0].content == "What is ETa?"

    # Delete conversation
    assert repo.delete(conv.id) is True
    assert repo.get(conv.id) is None


def test_spatial_repository(temp_workspace) -> None:
    repo = SpatialRepository(temp_workspace.conn)

    # Insert bbox [min_lon, min_lat, max_lon, max_lat]
    repo.insert("entity_1", [-120.0, 35.0, -119.0, 36.0])

    # Intersects query
    matches = repo.intersects((-120.5, 34.5, -118.5, 36.5))
    assert "entity_1" in matches

    # Within query
    within_matches = repo.within((-121.0, 34.0, -118.0, 37.0))
    assert "entity_1" in within_matches

    # Outside query
    outside = repo.intersects((0.0, 0.0, 1.0, 1.0))
    assert "entity_1" not in outside

    # Delete
    repo.delete("entity_1")
    assert "entity_1" not in repo.intersects((-120.5, 34.5, -118.5, 36.5))
