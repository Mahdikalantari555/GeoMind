"""Reciprocal Rank Fusion and linear fusion."""

from __future__ import annotations

from typing import Any

from geomemory.core.models import SearchHit


def rrf_fuse(
    groups: list[list[SearchHit]],
    *,
    top_n: int,
    k: int = 60,
    weights: list[float] | None = None,
) -> list[SearchHit]:
    """Reciprocal Rank Fusion over multiple ranked lists.

    Each hit's fused score is the sum of ``1 / (k + rank + 1)`` across the
    lists in which it appears. Operates on ranks, not raw scores.
    """
    scores: dict[str, float] = {}
    by_id: dict[str, SearchHit] = {}
    seen: dict[str, set[int]] = {}
    if weights is None:
        weights = [1.0] * len(groups)
    if len(weights) != len(groups):
        raise ValueError("weights must match the number of groups")

    for group_idx, (group, weight) in enumerate(zip(groups, weights, strict=True)):
        for rank, hit in enumerate(group):
            key = hit.id
            if key not in by_id:
                by_id[key] = hit
                seen[key] = set()
            else:
                if by_id[key].dense_score is None and hit.dense_score is not None:
                    by_id[key].dense_score = hit.dense_score
                if by_id[key].sparse_score is None and hit.sparse_score is not None:
                    by_id[key].sparse_score = hit.sparse_score
            if group_idx not in seen[key]:
                seen[key].add(group_idx)
                scores[key] = scores.get(key, 0.0) + weight / (k + rank + 1)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    for key, score in ranked:
        by_id[key].score = score
    return [by_id[k] for k, _ in ranked]


# Fused RRF scores are tiny: one top-ranked list with k=60 yields 1/61 ≈ 0.016,
# and even a handful of lists rarely exceeds ~0.05. Callers that build a
# SearchHit directly (tests, adapters) instead put an already-normalised
# relevance into ``score``. Distinguish the two by magnitude so a value like
# 0.2 keeps its literal meaning instead of being multiplied into 1.0 (M-059).
_RRF_SCORE_CEILING = 0.05
_RRF_TOP_SCORE = 1.0 / 61.0


def normalized_relevance(hit: Any) -> float:
    """Return a hit's relevance on a documented ``[0, 1]`` scale.

    ``SearchHit.score`` produced by :func:`rrf_fuse` holds an RRF rank value
    (~0.016 for the top hit with k=60), not a relevance; comparing a
    conventional threshold such as 0.5 against it always abstains (M-059).
    Prefer the real similarity components:

    - ``dense_score`` is a cosine similarity, clamped to ``[0, 1]``.
    - ``sparse_score`` is a BM25 score mapped with ``s / (1 + s)``.
    - A small bare ``score`` (<= :data:`_RRF_SCORE_CEILING`) is a fused RRF
      value and is rescaled by its single-list maximum (``1 / 61``).
    - A larger bare ``score`` is already a relevance value and is used as-is.

    A hit with no score components returns 0.0.
    """
    dense = getattr(hit, "dense_score", None)
    if dense is not None:
        return float(min(1.0, max(0.0, dense)))
    sparse = getattr(hit, "sparse_score", None)
    if sparse is not None:
        value = float(sparse)
        return float(min(1.0, max(0.0, value / (1.0 + value)))) if value > 0 else 0.0
    score = float(getattr(hit, "score", 0.0) or 0.0)
    if score <= _RRF_SCORE_CEILING:
        return float(min(1.0, max(0.0, score / _RRF_TOP_SCORE)))
    return float(min(1.0, max(0.0, score)))


def linear_fuse(
    groups: list[list[SearchHit]],
    *,
    top_n: int,
    weights: list[float] | None = None,
) -> list[SearchHit]:
    """Linear weighted fusion of normalized scores.

    Scores are min-max normalized per list before weighting. If ``weights``
    is None, lists are weighted equally.
    """
    if not groups:
        return []
    if weights is None:
        weights = [1.0 / len(groups)] * len(groups)
    if len(weights) != len(groups):
        raise ValueError("weights must match the number of groups")

    scores: dict[str, float] = {}
    by_id: dict[str, SearchHit] = {}
    for group_idx, group in enumerate(groups):
        if not group:
            continue
        raw = [h.score for h in group]
        lo, hi = min(raw), max(raw)
        span = (hi - lo) or 1.0
        for hit in group:
            norm = (hit.score - lo) / span
            key = hit.id
            if key not in by_id:
                by_id[key] = hit
            scores[key] = scores.get(key, 0.0) + weights[group_idx] * norm
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    for key, score in ranked:
        by_id[key].score = score
    return [by_id[k] for k, _ in ranked]
