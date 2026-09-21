"""Tests for dashboard-facing public API helpers and doctor service."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_stats_empty_workspace(temp_workspace) -> None:
    stats = temp_workspace.stats()
    assert stats["collections"] == 0
    assert stats["assets"] == 0
    assert stats["segments"] == 0
    assert stats["spatial_entities"] == 0
    assert stats["feedback_events"] == 0
    assert isinstance(stats["storage_bytes"], int)


@pytest.mark.unit
def test_stats_after_ingest(temp_workspace, sample_markdown) -> None:
    ws = temp_workspace
    col = ws.create_collection("papers")
    ws.ingest(str(sample_markdown), collection_id=col.id)
    stats = ws.stats()
    assert stats["collections"] == 1
    assert stats["assets"] == 1
    assert stats["segments"] >= 1


@pytest.mark.unit
def test_stats_grouped_aggregation_multiple_assets(temp_workspace) -> None:
    ws = temp_workspace
    col = ws.create_collection("c1")

    # 5 assets: 3 with revisions, 2 without
    for i in range(1, 6):
        ws.conn.execute(
            "INSERT INTO asset (id, collection_id, kind, title, current_revision_id) VALUES (?, ?, ?, ?, ?)",
            (f"a{i}", col.id, "document", f"Asset {i}", f"r{i}" if i <= 3 else None),
        )

    for i in range(1, 4):
        ws.conn.execute(
            "INSERT INTO asset_revision (id, asset_id, hash, mime_type, size_bytes, parser_version) VALUES (?, ?, ?, ?, ?, ?)",
            (f"r{i}", f"a{i}", f"hash{i}", "text/plain", 100, "1.0"),
        )

    # Segments: r1 has 3, r2 has 2, r3 has 0 -> total 5
    seg_id = 0
    for rev_id, count in [("r1", 3), ("r2", 2)]:
        for _ in range(count):
            seg_id += 1
            ws.conn.execute(
                "INSERT INTO segment (id, revision_id, segment_type, text) VALUES (?, ?, ?, ?)",
                (f"s{seg_id}", rev_id, "paragraph", "sample text"),
            )

    # Raster scenes: r1 has 1, r3 has 2 -> total 3
    scn_id = 0
    for rev_id, count in [("r1", 1), ("r3", 2)]:
        for _ in range(count):
            scn_id += 1
            ws.conn.execute(
                "INSERT INTO raster_scene (id, revision_id, crs) VALUES (?, ?, ?)",
                (f"scn{scn_id}", rev_id, "EPSG:4326"),
            )

    # Vector layers: r2 has 2, r3 has 1 -> total 3
    lyr_id = 0
    for rev_id, count in [("r2", 2), ("r3", 1)]:
        for _ in range(count):
            lyr_id += 1
            ws.conn.execute(
                "INSERT INTO vector_layer (id, revision_id, geometry_type, crs) VALUES (?, ?, ?, ?)",
                (f"lyr{lyr_id}", rev_id, "Polygon", "EPSG:4326"),
            )
    ws.conn.commit()

    executed_queries: list[str] = []
    ws.conn.set_trace_callback(executed_queries.append)
    try:
        stats = ws.stats()
    finally:
        ws.conn.set_trace_callback(None)

    assert stats["collections"] == 1
    assert stats["assets"] == 5
    assert stats["segments"] == 5
    assert stats["raster_scenes"] == 3
    assert stats["vector_layers"] == 3

    # Ensure exactly 1 query per table with GROUP BY (no per-revision queries)
    group_queries = [q for q in executed_queries if "GROUP BY revision_id" in q]
    assert len(group_queries) == 3


@pytest.mark.unit
def test_review_example_accept_reject(temp_workspace) -> None:
    ws = temp_workspace
    from geomemory.core.models import DatasetExample, FeedbackEvent

    ev = ws.record_feedback(
        FeedbackEvent(
            target_type="answer",
            target_id="ans1",
            label="answer_rating",
            payload={"rating": 1},
        )
    )
    from geomemory.storage.repositories.feedback_repo import DatasetExampleRepository

    dsx = DatasetExampleRepository(ws.conn).create(
        DatasetExample(task_type="rag_eval", source_feedback_ids=[ev.id])
    )
    assert len(ws.get_review_queue()) == 1
    assert ws.review_example(dsx.id, accept=True)
    assert len(ws.get_review_queue()) == 0
    # Accepting an already-reviewed example returns False (no change).
    assert not ws.review_example(dsx.id, accept=True)


@pytest.mark.unit
def test_update_settings_validated(temp_workspace) -> None:
    ws = temp_workspace
    updated = ws.update_settings(batch_size=32, model_path="/models/qwen.gguf")
    assert updated.batch_size == 32
    assert updated.model_path == "/models/qwen.gguf"
    assert ws.settings.batch_size == 32
    with pytest.raises(ValueError):
        ws.update_settings(not_a_real_field=1)


@pytest.mark.unit
def test_doctor_environment():
    from geomemory.services.doctor import doctor_environment

    env = doctor_environment()
    assert env["python_ok"] is True
    assert env["core_ok"] is True
    assert isinstance(env["optional_deps"], dict)
    assert "rasterio" in env["optional_deps"]


@pytest.mark.unit
def test_doctor_workspace_ok(temp_workspace):
    from geomemory.services.doctor import doctor_workspace, doctor_workspace_open

    rep = doctor_workspace(temp_workspace.path)
    assert rep["ok"] is True
    assert rep["checks"]["marker_exists"] is True
    assert rep["checks"]["settings_valid"] is True

    opened = doctor_workspace_open(temp_workspace.path)
    assert opened["ok"] is True
    assert opened["checks"]["stats"] is True


@pytest.mark.unit
def test_doctor_workspace_missing(tmp_path):
    from geomemory.services.doctor import doctor_workspace

    rep = doctor_workspace(tmp_path / "nope")
    assert rep["ok"] is False
