"""Unit tests for ReviewQueue, FeedbackRepository, and DatasetExampleRepository."""

from __future__ import annotations

import pytest

from geomemory.core.models import DatasetExample, FeedbackEvent
from geomemory.core.workspace import GeoMemory
from geomemory.feedback.events import build_dataset_example
from geomemory.feedback.review_queue import ReviewQueue
from geomemory.storage.repositories.feedback_repo import (
    DatasetExampleRepository,
    FeedbackRepository,
)


def test_review_queue_lifecycle(temp_workspace: GeoMemory) -> None:
    conn = temp_workspace.conn
    q = ReviewQueue(conn)

    # enqueue non-pending raises ValueError
    accepted_ex = build_dataset_example(task_type="qa_eval")
    accepted_ex.review_state = "accepted"
    with pytest.raises(ValueError, match="Only pending examples"):
        q.enqueue(accepted_ex)

    # enqueue pending
    ex1 = build_dataset_example(task_type="qa_eval", question="q1")
    q.enqueue(ex1)

    ex2 = build_dataset_example(task_type="rag_eval", question="q2")
    q.enqueue(ex2)

    assert q.count_by_state("pending") == 2
    assert len(q.pending()) == 2
    assert q.get(ex1.id) is not None

    # invalid state
    with pytest.raises(ValueError, match="Unknown review state"):
        q.count_by_state("invalid")

    # review accept
    assert q.review(ex1.id, accept=True, reviewer_id="user1") is True
    # review reject
    assert q.reject(ex2.id, reviewer_id="user2") is True

    assert q.count_by_state("accepted") == 1
    assert q.count_by_state("rejected") == 1
    assert q.count_by_state("pending") == 0

    # accepted with task_type filter
    assert len(q.accepted()) == 1
    assert len(q.accepted(task_type="qa_eval")) == 1
    assert len(q.accepted(task_type="rag_eval")) == 0


def test_feedback_and_dataset_repositories(temp_workspace: GeoMemory) -> None:
    conn = temp_workspace.conn
    f_repo = FeedbackRepository(conn)
    d_repo = DatasetExampleRepository(conn)

    # FeedbackRepository
    ev = FeedbackEvent(
        id="fb-1",
        target_type="answer",
        target_id="ans-1",
        actor="user",
        label="thumbs_up",
        payload={"score": 1},
        metadata={"client": "web"},
    )
    f_repo.create(ev)
    assert f_repo.count() == 1

    fetched = f_repo.get("fb-1")
    assert fetched is not None
    assert fetched.payload["score"] == 1
    assert fetched.metadata["client"] == "web"
    assert f_repo.get("missing") is None

    by_target = f_repo.list_by_target("answer", "ans-1")
    assert len(by_target) == 1
    all_events = f_repo.list_all(limit=10)
    assert len(all_events) == 1

    # DatasetExampleRepository
    ex = DatasetExample(
        id="de-1",
        task_type="classification",
        source_feedback_ids=["fb-1"],
        review_state="pending",
        dataset_card={"info": "card"},
    )
    d_repo.create(ex)
    loaded = d_repo.get("de-1")
    assert loaded is not None
    assert loaded.source_feedback_ids == ["fb-1"]
    assert loaded.dataset_card == {"info": "card"}
    assert d_repo.get("missing") is None

    assert len(d_repo.list_by_task("classification")) == 1
    assert len(d_repo.list_by_task("other")) == 0

    assert d_repo.update_state("de-1", "accepted", "admin") is True
    assert d_repo.update_state("nonexistent", "accepted") is False
    assert len(d_repo.list_by_state("accepted")) == 1
