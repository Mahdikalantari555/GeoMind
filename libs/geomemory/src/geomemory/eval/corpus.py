"""Corpus registry: versioned benchmark discovery, validation, and loading.

Corpus layout::

    geomemory-evals/corpus/corpus.json   ← registry manifest
    geomemory-evals/corpus/v0.1.0/phase1.jsonl
    geomemory-evals/corpus/v0.1.0/qa.jsonl

``corpus.json`` maps benchmark names to metadata (version, description,
modality, source_dataset). Benchmarks are standard JSONL files consumed by
:func:`geomemory.eval.benchmark.load_benchmark`.

To add a new benchmark:
1. Create a version directory (e.g. ``v0.2.0/``).
2. Place ``.jsonl`` files inside it (one :class:`BenchmarkItem` per line).
3. Register each file in ``corpus.json`` with the required fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from geomemory.eval.benchmark import BenchmarkItem

# ── Registry ────────────────────────────────────────────────────────────────

def load_corpus_registry(path: str | Path) -> dict[str, Any]:
    """Load ``corpus.json`` and return the parsed registry dict.

    Raises ``FileNotFoundError`` when *path* does not exist.
    Raises ``ValueError`` when the JSON is not a top-level object.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Corpus registry not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"corpus.json must be a JSON object, got {type(data).__name__}")
    return data


def list_corpus_benchmarks(corpus_dir: str | Path) -> list[dict[str, Any]]:
    """Enumerate ``.jsonl`` files under ``corpus_dir/*/`` grouped by version.

    Returns a list of dicts with ``version``, ``name``, and ``path`` keys,
    sorted by version then name.  Returns an empty list when the directory
    does not exist.
    """
    root = Path(corpus_dir)
    if not root.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for version_dir in sorted(root.iterdir()):
        if not version_dir.is_dir():
            continue
        for jsonl in sorted(version_dir.glob("*.jsonl")):
            results.append({
                "version": version_dir.name,
                "name": jsonl.stem,
                "path": str(jsonl),
            })
    return results


def resolve_corpus_version(
    benchmark_path: str | Path,
    corpus_dir: str | Path | None = None,
) -> str | None:
    """Look up corpus version for a benchmark file.

    Attempts two strategies:
    1. Infer from parent directory name (e.g. ``corpus/v0.1.0/phase1.jsonl``).
    2. Look up in ``corpus.json`` if *corpus_dir* is given.

    Returns the version string, or ``None`` if unresolvable.
    """
    bp = Path(benchmark_path).resolve()
    # Strategy 1: parent dir name starts with 'v'
    parent_name = bp.parent.name
    if parent_name and parent_name[0] == "v":
        return parent_name

    # Strategy 2: registry lookup
    if corpus_dir is not None:
        registry_path = Path(corpus_dir) / "corpus.json"
        if registry_path.is_file():
            try:
                registry = load_corpus_registry(registry_path)
                entry = registry.get(bp.stem)
                if isinstance(entry, dict):
                    return entry.get("version")
            except (ValueError, json.JSONDecodeError):
                pass
    return None


# ── Validation ──────────────────────────────────────────────────────────────

def validate_benchmark_items(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate raw dicts against :class:`BenchmarkItem`.

    Returns a list of error dicts ``{line, field, message}`` for every row
    that fails Pydantic validation.  An empty return means all rows are valid.
    """
    errors: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        try:
            BenchmarkItem(**row)
        except (ValidationError, TypeError, ValueError) as exc:
            msg = str(exc)
            # Try to extract the first field name from Pydantic errors
            field = ""
            if isinstance(exc, ValidationError):
                locs = exc.errors()
                if locs:
                    loc_parts = locs[0].get("loc", ())
                    field = str(loc_parts[0]) if loc_parts else ""
                    msg = locs[0].get("msg", msg)
            errors.append({"line": idx, "field": field, "message": msg})
    return errors


__all__ = [
    "list_corpus_benchmarks",
    "load_corpus_registry",
    "resolve_corpus_version",
    "validate_benchmark_items",
]
