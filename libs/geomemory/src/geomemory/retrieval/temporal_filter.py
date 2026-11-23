"""Temporal filtering over search hits."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from geomemory.core.models import SearchHit, TemporalFilter


def apply_temporal_filter(hits: list[SearchHit], temporal: TemporalFilter | None) -> list[SearchHit]:
    """Keep hits whose timestamp for ``temporal.field`` falls in the requested range."""
    if temporal is None:
        return hits
    return [hit for hit in hits if _hit_in_range(hit, temporal)]


def _hit_in_range(hit: SearchHit, temporal: TemporalFilter) -> bool:
    value = _field_value(hit, temporal.field)
    if value is None:
        return False
    return time_in_range(value, temporal.from_, temporal.to)


def _field_value(hit: SearchHit, field: str) -> str | None:
    """Resolve the timestamp value for a temporal field from hit metadata."""
    if field == "acquired_at":
        return hit.metadata.get("spatial", {}).get("acquired_at")
    if field == "observed_at":
        observation = hit.metadata.get("observation")
        if isinstance(observation, dict):
            return observation.get("observed_at")
        return None
    if field in ("published_at", "ingested_at"):
        return hit.metadata.get(field)
    return hit.metadata.get(field)


def parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO timestamp/date into an aware UTC datetime.

    Accepts ``Z`` suffixes, explicit offsets, plain dates and naive values
    (assumed UTC). Returns ``None`` for non-string/non-datetime or malformed
    input so a single bad metadata value cannot raise out of filtering (M-056).
    """
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            try:
                parsed = datetime.fromisoformat(text[:10])
            except ValueError:
                return None
    else:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def time_in_range(value: Any, from_: Any, to: Any) -> bool:
    """Return True if a timestamp falls within the inclusive [from_, to] range.

    Comparison is on aware datetimes, so mixed ``Z``/offset/date-only
    representations filter correctly instead of being compared as strings.
    """
    parsed_value = parse_timestamp(value)
    if parsed_value is None:
        return False
    if from_ is not None:
        lower = parse_timestamp(from_)
        if lower is not None and parsed_value < lower:
            return False
    if to is not None:
        upper = parse_timestamp(to)
        if upper is not None and parsed_value > upper:
            return False
    return True
