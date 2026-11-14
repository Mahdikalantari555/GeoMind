"""Feedback, review, dataset export, and evaluation capability."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from geomemory.core.models import (
    BenchmarkResult,
    DatasetExample,
    FeedbackEvent,
)
from geomemory.core.workspace_qa import QAMixin


class FeedbackMixin(QAMixin):
    # ── Feedback ────────────────────────────────────────────────────────────

    def record_feedback(self, event: FeedbackEvent) -> FeedbackEvent:
        """Record an immutable feedback event."""
        from geomemory.storage.repositories.feedback_repo import FeedbackRepository

        return FeedbackRepository(self.conn).create(event)

    def get_review_queue(self) -> list[DatasetExample]:
        """Return pending dataset examples for review."""
        from geomemory.storage.repositories.feedback_repo import DatasetExampleRepository

        return DatasetExampleRepository(self.conn).list_by_state("pending")

    def review_example(
        self, example_id: str, *, accept: bool, reviewer_id: str | None = None
    ) -> bool:
        """Accept or reject a pending dataset example. Returns True on change."""
        from geomemory.storage.repositories.feedback_repo import DatasetExampleRepository

        repo = DatasetExampleRepository(self.conn)
        current = repo.get(example_id)
        if current is None:
            return False
        target = "accepted" if accept else "rejected"
        if current.review_state == target:
            return False
        return repo.update_state(example_id, target, reviewer_id)
    def export_dataset(self, task_type: str, output_dir: str | Path) -> Path:
        """Export accepted examples for a task type to a JSONL file."""
        from geomemory.services.feedback_service import FeedbackService

        return FeedbackService(self.conn).export_dataset(task_type, output_dir)


    # ── Evaluation ──────────────────────────────────────────────────────────

    def run_benchmark(
        self,
        benchmark_path: str,
        config: str | None = None,
        *,
        run_store: Any | None = None,
        dataset: str | None = None,
        stats: dict[str, Any] | None = None,
        manifest: dict[str, Any] | None = None,
    ) -> BenchmarkResult:
        """Run a benchmark from a JSONL file.

        When ``run_store`` and ``dataset`` are provided, per-query rows are
        persisted alongside the aggregated metrics under
        ``runs/<dataset>/<timestamp>/``.
        """
        from geomemory.eval.runner import BenchmarkRunner

        runner = BenchmarkRunner(self)
        return runner.run(
            benchmark_path,
            config,
            run_store=run_store,
            dataset=dataset,
            stats=stats,
            manifest=manifest,
        )

    def pipeline_stats(self, *, duration_seconds: float = 0.0) -> dict[str, Any]:
        """Return pipeline-level statistics for this workspace.

        Queries the production database tables (asset_revision, segment,
        embedding_record, entity, relation) and walks the workspace directory
        for storage size. On a fresh, un-ingested workspace all counts are zero.
        """
        from geomemory.eval.pipeline_stats import collect_stats

        return collect_stats(self.conn, self.path, duration_seconds=duration_seconds)

