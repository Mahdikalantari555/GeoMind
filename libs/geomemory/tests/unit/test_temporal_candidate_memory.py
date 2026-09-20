"""Unit tests for temporal candidate-memory operations (observed_at/superseded_by/project)."""

from __future__ import annotations

import pytest

from geomemory.core.models import CandidateMemory
from geomemory.feedback.candidate_memory import CandidateMemoryRepository


@pytest.fixture()
def repo(temp_workspace) -> CandidateMemoryRepository:
    return CandidateMemoryRepository(temp_workspace.conn)


def _make(repo: CandidateMemoryRepository, content: str, **kwargs) -> CandidateMemory:
    cm = CandidateMemory(content=content, **kwargs)
    return repo.create(cm)


class TestObservedAtDefault:
    def test_unset_observed_at_reads_as_created_at(self, repo):
        cm = _make(repo, "no explicit observation date")
        fetched = repo.get(cm.id)
        assert fetched is not None
        assert fetched.observed_at is None
        assert fetched.effective_observed_at == fetched.created_at

    def test_explicit_observed_at_preserved(self, repo):
        cm = _make(repo, "observed in 2023", observed_at="2023-06-01T00:00:00Z")
        fetched = repo.get(cm.id)
        assert fetched is not None
        assert fetched.observed_at == "2023-06-01T00:00:00Z"
        assert fetched.effective_observed_at == "2023-06-01T00:00:00Z"


class TestGetAsOf:
    def test_returns_row_when_observed_before_cutoff(self, repo):
        cm = _make(repo, "early belief", observed_at="2025-01-10T00:00:00Z")
        fetched = repo.get_as_of(cm.id, "2025-02-01T00:00:00Z")
        assert fetched is not None
        assert fetched.id == cm.id

    def test_returns_none_when_observed_after_cutoff(self, repo):
        cm = _make(repo, "late belief", observed_at="2025-06-01T00:00:00Z")
        assert repo.get_as_of(cm.id, "2025-02-01T00:00:00Z") is None

    def test_falls_back_to_created_at(self, repo):
        cm = _make(repo, "belief without observed_at")
        fetched = repo.get_as_of(cm.id, "2999-01-01T00:00:00Z")
        assert fetched is not None
        assert fetched.id == cm.id

    def test_returns_latest_revision_in_chain(self, repo):
        old = _make(repo, "OPTRAM works everywhere", observed_at="2025-01-01T00:00:00Z")
        new = _make(repo, "OPTRAM has saline limits", observed_at="2025-03-01T00:00:00Z")
        repo.mark_superseded(old.id, new.id)

        as_of_feb = repo.get_as_of(old.id, "2025-02-01T00:00:00Z")
        assert as_of_feb is not None
        assert as_of_feb.id == old.id

        as_of_apr = repo.get_as_of(old.id, "2025-04-01T00:00:00Z")
        assert as_of_apr is not None
        assert as_of_apr.id == new.id

    def test_missing_id_returns_none(self, repo):
        assert repo.get_as_of("nope", "2025-01-01T00:00:00Z") is None


class TestMarkSuperseded:
    def test_sets_fk_on_old_row(self, repo):
        old = _make(repo, "old belief")
        new = _make(repo, "new belief")
        repo.mark_superseded(old.id, new.id)
        fetched = repo.get(old.id)
        assert fetched is not None
        assert fetched.superseded_by == new.id

    def test_chain_traversable(self, repo):
        a = _make(repo, "v1")
        b = _make(repo, "v2")
        c = _make(repo, "v3")
        repo.mark_superseded(a.id, b.id)
        repo.mark_superseded(b.id, c.id)
        chain = [a.id, b.id, c.id]
        current = repo.get(a.id)
        assert current is not None
        hops = [current.id]
        while current is not None and current.superseded_by:
            current = repo.get(current.superseded_by)
            if current is not None:
                hops.append(current.id)
        assert hops == chain


class TestListByProject:
    def test_filters_by_project(self, repo):
        _make(repo, "dspit item", project="DSPIT")
        _make(repo, "pidl item", project="PIDL")
        rows = repo.list_by_project("DSPIT")
        assert len(rows) == 1
        assert rows[0].project == "DSPIT"

    def test_orders_by_observed_at_desc(self, repo):
        early = _make(repo, "early", project="DSPIT", observed_at="2025-01-01T00:00:00Z")
        late = _make(repo, "late", project="DSPIT", observed_at="2025-05-01T00:00:00Z")
        rows = repo.list_by_project("DSPIT")
        assert [r.id for r in rows] == [late.id, early.id]

    def test_filters_by_memory_types(self, repo):
        _make(repo, "a decision", project="DSPIT", memory_type="decision")
        _make(repo, "a hypothesis", project="DSPIT", memory_type="hypothesis")
        rows = repo.list_by_project("DSPIT", types=["decision"])
        assert len(rows) == 1
        assert rows[0].memory_type == "decision"

    def test_paginates(self, repo):
        for i in range(5):
            _make(repo, f"item {i}", project="DSPIT", observed_at=f"2025-01-0{i + 1}T00:00:00Z")
        page1 = repo.list_by_project("DSPIT", offset=0, limit=2)
        page2 = repo.list_by_project("DSPIT", offset=2, limit=2)
        assert len(page1) == 2 and len(page2) == 2
        assert {r.id for r in page1}.isdisjoint({r.id for r in page2})

    def test_empty_for_unknown_project(self, repo):
        assert repo.list_by_project("NOPE") == []
