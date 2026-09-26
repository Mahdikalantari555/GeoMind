"""Unit tests for ProposalEngine in geomemory.feedback.proposals."""

from __future__ import annotations

import pytest

from geomemory.core.models import CandidateMemory
from geomemory.feedback.proposals import ProposalEngine


def test_proposal_engine_lifecycle(temp_workspace) -> None:
    conn = temp_workspace.conn
    engine = ProposalEngine(conn, max_per_session=2)

    # 1. create proposal directly
    prop1 = engine.create(
        proposal_type="entity_create",
        diff={"name": "Sentinel-2", "entity_type": "sensor"},
        source_candidate_ids=["cm1"],
        confidence=0.9,
    )
    assert prop1.id is not None
    assert prop1.status == "pending"

    # get proposal
    fetched = engine.get(prop1.id)
    assert fetched is not None
    assert fetched.id == prop1.id
    assert fetched.diff == {"name": "Sentinel-2", "entity_type": "sensor"}
    assert engine.get("missing_id") is None

    # list proposals
    props = engine.list()
    assert len(props) >= 1
    assert any(p.id == prop1.id for p in props)

    # apply proposal (review: True)
    applied = engine.apply(prop1.id, reviewer="alice")
    assert applied.status == "approved"
    assert applied.reviewer_id == "alice"

    # reject proposal on second created proposal
    prop2 = engine.create(
        proposal_type="metadata_update",
        diff={"action": "drop"},
        source_candidate_ids=["cm2"],
    )
    rejected = engine.reject(prop2.id, reason="not relevant")
    assert rejected.status == "rejected"
    assert rejected.review_note == "not relevant"

    # apply/reject missing proposal raises ValueError
    with pytest.raises(ValueError, match="Proposal not found"):
        engine.apply("non_existent")
    with pytest.raises(ValueError, match="Proposal not found"):
        engine.reject("non_existent")

    # list with status filter
    assert len(engine.list(status="approved")) >= 1
    assert len(engine.list(status="rejected")) >= 1


def test_proposal_engine_generate(temp_workspace) -> None:
    temp_workspace.create_collection("default")
    conn = temp_workspace.conn
    engine = ProposalEngine(conn, max_per_session=2)

    # Candidate not verified returns None
    unverified = CandidateMemory(
        content="Salinity reduces NDVI",
        state="proposed",
        memory_type="fact",
    )
    assert engine.generate(unverified) is None

    # Verified preference -> metadata_update
    cand_pref = CandidateMemory(
        content="User prefers dark mode",
        state="verified",
        memory_type="preference",
    )
    p_pref = engine.generate(cand_pref)
    assert p_pref is not None
    assert p_pref.proposal_type == "metadata_update"

    # Verified entity -> entity_create
    cand_ent = CandidateMemory(
        content="Entity Landsat-8 was observed",
        state="verified",
        memory_type="fact",
    )
    p_ent = engine.generate(cand_ent)
    assert p_ent is not None
    assert p_ent.proposal_type == "entity_create"

    # Max per session hit
    cand_extra = CandidateMemory(
        content="Another entity",
        state="verified",
        memory_type="fact",
    )
    assert engine.generate(cand_extra) is None


def test_proposal_engine_apply_graph_relation(temp_workspace) -> None:
    temp_workspace.create_collection("default")
    conn = temp_workspace.conn
    engine = ProposalEngine(conn)

    # 1. Structured diff: source, predicate, target
    prop_struct = engine.create(
        proposal_type="graph_relation",
        diff={"source": "salinity stress", "predicate": "causes", "target": "reduced NDVI"},
        source_candidate_ids=["cm1"],
    )
    engine.apply(prop_struct.id, reviewer="bob")

    # Verify entities and relation created
    row_rel = conn.execute("SELECT * FROM relation WHERE predicate = 'causes'").fetchone()
    assert row_rel is not None

    # Check kind classification for metric, stress_type, location, sensor, concept
    row_src = conn.execute("SELECT * FROM entity WHERE id = ?", (row_rel["source_id"],)).fetchone()
    assert row_src["kind"] == "stress_type"
    row_tgt = conn.execute("SELECT * FROM entity WHERE id = ?", (row_rel["target_id"],)).fetchone()
    assert row_tgt["kind"] == "metric"

    # 2. String diff with '->' format
    prop_str = engine.create(
        proposal_type="graph_relation",
        diff={"proposed": "Khuzestan province -> contains -> Sentinel-2"},
        source_candidate_ids=["cm2"],
    )
    engine.apply(prop_str.id, reviewer="charlie")

    row_loc = conn.execute("SELECT * FROM entity WHERE name = 'Khuzestan province'").fetchone()
    assert row_loc["kind"] == "location"
    row_sen = conn.execute("SELECT * FROM entity WHERE name = 'Sentinel-2'").fetchone()
    assert row_sen["kind"] == "sensor"

    # 3. Invalid diff structure falls back silently without error
    prop_bad = engine.create(
        proposal_type="graph_relation",
        diff={"proposed": "invalid format"},
        source_candidate_ids=["cm3"],
    )
    engine.apply(prop_bad.id)
