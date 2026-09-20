"""Superseded candidate memories are excluded from search unless explicitly requested."""

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


def test_superseded_excluded_by_default(repo) -> None:
    old = _make(repo, "OPTRAM works everywhere")
    new = _make(repo, "OPTRAM has saline limitations")
    repo.mark_superseded(old.id, new.id)
    results = repo.search("OPTRAM")
    assert [r.id for r in results] == [new.id]


def test_include_superseded_returns_both(repo) -> None:
    old = _make(repo, "OPTRAM works everywhere")
    new = _make(repo, "OPTRAM has saline limitations")
    repo.mark_superseded(old.id, new.id)
    results = repo.search("OPTRAM", include_superseded=True)
    assert {r.id for r in results} == {old.id, new.id}


def test_non_superseded_search_unaffected(repo) -> None:
    cm = _make(repo, "OPTRAM baseline")
    results = repo.search("OPTRAM")
    assert [r.id for r in results] == [cm.id]


def test_service_passthrough(temp_workspace) -> None:
    from geomemory.services.candidate_memory_service import CandidateMemoryService

    svc = CandidateMemoryService(temp_workspace.conn)
    old = svc.create("OPTRAM works everywhere")
    new = svc.create("OPTRAM has saline limitations")
    svc.repo.mark_superseded(old.id, new.id)
    assert [r.id for r in svc.search("OPTRAM")] == [new.id]
    assert {r.id for r in svc.search("OPTRAM", include_superseded=True)} == {old.id, new.id}
