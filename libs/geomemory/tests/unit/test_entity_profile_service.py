"""Unit tests for EntityProfileService (seeded-alias entity profiles)."""

from __future__ import annotations

import json

import pytest

from geomemory.core.models import CandidateMemory, Entity
from geomemory.feedback.candidate_memory import CandidateMemoryRepository
from geomemory.services.entity_profile_service import (
    DEFAULT_ENTITY_ALIASES,
    EntityProfileService,
)
from geomemory.storage.repositories.entity_repo import EntityRepository


@pytest.fixture()
def svc(temp_workspace) -> EntityProfileService:
    return EntityProfileService(temp_workspace.conn)


@pytest.fixture()
def repo(temp_workspace) -> CandidateMemoryRepository:
    return CandidateMemoryRepository(temp_workspace.conn)


def _cm(repo: CandidateMemoryRepository, content: str, **kwargs) -> CandidateMemory:
    return repo.create(CandidateMemory(content=content, **kwargs))


@pytest.fixture()
def ws_row(temp_workspace) -> str:
    """Insert the workspace row entity FKs point at; return its id."""
    temp_workspace.conn.execute(
        "INSERT INTO workspace (id, name, settings) VALUES ('ws1', 'test', '{}')"
    )
    temp_workspace.conn.commit()
    return "ws1"


class TestProfileBasics:
    def test_default_aliases_seeded(self, svc):
        assert "OPTRAM" in svc.aliases
        assert set(DEFAULT_ENTITY_ALIASES) <= set(svc.aliases)

    def test_known_entity_returns_linked_memories(self, svc, repo):
        cm = _cm(repo, "OPTRAM works well for ETa retrieval in Khuzestan")
        _cm(repo, "unrelated note about cloud cover")
        profile = svc.get_profile("OPTRAM")
        assert len(profile["current_beliefs"]) == 1
        assert profile["current_beliefs"][0].id == cm.id
        assert profile["name"] == "OPTRAM"

    def test_match_is_case_insensitive(self, svc, repo):
        _cm(repo, "optram lower-case mention")
        profile = svc.get_profile("OPTRAM")
        assert len(profile["current_beliefs"]) == 1

    def test_unknown_entity_returns_empty(self, svc, repo):
        _cm(repo, "OPTRAM works well")
        profile = svc.get_profile("Zanzibar-unknown")
        assert profile["current_beliefs"] == []
        assert profile["history"] == []
        assert profile["related_entities"] == []

    def test_empty_name_returns_empty(self, svc, repo):
        _cm(repo, "OPTRAM works well")
        profile = svc.get_profile("   ")
        assert profile["current_beliefs"] == []


class TestHistory:
    def test_history_includes_superseded(self, svc, repo):
        old = _cm(repo, "OPTRAM works everywhere", observed_at="2025-01-01T00:00:00Z")
        new = _cm(repo, "OPTRAM has saline limitations", observed_at="2025-03-01T00:00:00Z")
        repo.mark_superseded(old.id, new.id)
        profile = svc.get_profile("OPTRAM")
        assert [cm.id for cm in profile["current_beliefs"]] == [new.id]
        assert old.id in {cm.id for cm in profile["history"]}
        assert new.id in {cm.id for cm in profile["history"]}

    def test_rejected_not_current(self, svc, repo):
        _cm(repo, "OPTRAM rejected claim", state="rejected")
        profile = svc.get_profile("OPTRAM")
        assert profile["current_beliefs"] == []
        assert len(profile["history"]) == 1


class TestAliasCollision:
    def test_substring_collision_returns_both(self, svc, repo):
        _cm(repo, "Landsat-9 scene processed for NDVI")
        _cm(repo, "Landsat-8 archive reviewed")
        profile = svc.get_profile("Landsat")
        assert len(profile["current_beliefs"]) == 2

    def test_related_cooccurrence_keeps_both(self, svc, repo):
        _cm(repo, "OPTRAM and NDVI compared for salinity in Khuzestan")
        profile = svc.get_profile("OPTRAM")
        assert set(profile["related_entities"]) >= {"NDVI", "salinity", "Khuzestan"}


class TestRelatedEntities:
    def test_related_via_relation_table(self, svc, repo, ws_row):
        erepo = EntityRepository(svc.conn)
        optram = erepo.create(Entity(name="OPTRAM", kind="metric", workspace_id=ws_row))
        salinity = erepo.create(Entity(name="salinity", kind="stress_type", workspace_id=ws_row))
        svc.conn.execute(
            "INSERT INTO relation (id, source_id, predicate, target_id) VALUES ('rel1', ?, 'related_to', ?)",
            (optram.id, salinity.id),
        )
        svc.conn.commit()
        _cm(repo, "OPTRAM signal degrades with salinity")
        profile = svc.get_profile("OPTRAM")
        assert "salinity" in profile["related_entities"]

    def test_kind_from_entity_table(self, svc, repo, ws_row):
        erepo = EntityRepository(svc.conn)
        erepo.create(Entity(name="OPTRAM", kind="metric", workspace_id=ws_row))
        profile = svc.get_profile("OPTRAM")
        assert profile["kind"] == "metric"

    def test_kind_none_without_entity_row(self, svc, repo):
        _cm(repo, "OPTRAM mention without entity row")
        profile = svc.get_profile("OPTRAM")
        assert profile["kind"] is None


class TestAliasIndexFromSettings:
    def test_custom_aliases_override_seed(self, svc, repo, temp_workspace):
        svc.conn.execute("INSERT INTO workspace (id, name, settings) VALUES ('ws1', 'test', ?)", (json.dumps({"entity_alias_index": ["Zanzibar"]}),))
        svc.conn.commit()
        custom = EntityProfileService(svc.conn)
        assert custom.aliases == ["Zanzibar"]
        _cm(repo, "Zanzibar soil salinity study")
        profile = custom.get_profile("Zanzibar")
        assert len(profile["current_beliefs"]) == 1
        # seed alias no longer linked
        _cm(repo, "OPTRAM note")
        assert custom.get_profile("OPTRAM")["current_beliefs"] == []

    def test_malformed_settings_falls_back_to_seed(self, svc):
        svc.conn.execute("INSERT INTO workspace (id, name, settings) VALUES ('ws1', 'test', 'not-json')")
        svc.conn.commit()
        assert "OPTRAM" in EntityProfileService(svc.conn).aliases
