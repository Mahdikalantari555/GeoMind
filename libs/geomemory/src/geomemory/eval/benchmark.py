"""Benchmark definition and JSONL loading.

A benchmark is a list of items, each with a query/question, optional gold
document ids, and an optional reference answer. Benchmarks are stored as
JSONL files, one item per line.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from geomemory.core.models import GeoMemoryModel


class BenchmarkItem(GeoMemoryModel):
    """A single benchmark case: a query plus expected gold sources."""

    query: str = Field(description="Search query or QA question text")
    gold_ids: list[str] = Field(default_factory=list, description="Relevant segment/document ids")
    reference_answer: str = Field(default="", description="Optional reference answer for QA eval")
    expected_abstain: bool = Field(default=False, description="Whether the item should abstain")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("query")
    @classmethod
    def _query_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be empty")
        return v


class Benchmark(BaseModel):
    """A loaded benchmark dataset."""

    name: str = "benchmark"
    items: list[BenchmarkItem]
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, index: int) -> BenchmarkItem:
        return self.items[index]


def load_benchmark(path: str | Path, *, corpus_dir: str | Path | None = None) -> Benchmark:
    """Load a benchmark from a JSONL file (one item per line).

    When *corpus_dir* is given, the function looks up the benchmark's corpus
    version in ``corpus.json`` and attaches it to :attr:`Benchmark.metadata`.
    Invalid rows raise :exc:`ValueError` with line-number context.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Benchmark file not found: {p}")

    from geomemory.eval.corpus import (
        resolve_corpus_version,
        validate_benchmark_items,
    )

    raw_rows: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{p}: invalid JSON on line {lineno}: {exc}") from exc
            raw_rows.append(data)

    if not raw_rows:
        raise ValueError(f"Benchmark contains no items: {p}")

    errors = validate_benchmark_items(raw_rows)
    if errors:
        err = errors[0]
        extra = f' field={err["field"]}' if err.get("field") else ""
        raise ValueError(f"{p}: row {err['line']} validation failed{extra}: {err['message']}")

    items = [BenchmarkItem(**row) for row in raw_rows]
    meta: dict[str, Any] = {}
    version = resolve_corpus_version(p, corpus_dir)
    if version is not None:
        meta["corpus_version"] = version
    return Benchmark(name=p.stem, items=items, metadata=meta)


def to_jsonl(rows: list[dict[str, Any]]) -> str:
    """Serialize benchmark rows to JSONL text."""
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
