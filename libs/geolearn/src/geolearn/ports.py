"""Ports — structural interfaces geolearn requires from its hosts.

geolearn sits below geomemory in the dependency graph (ARCHITECTURE.md), so
it must never import geomemory or read another lib's storage directly.
Hosts (the gateway, geoagent tools) inject a
:class:`CandidateMemoryProvider` instead — usually the ``geomemory.GeoMemory``
facade they already hold, which satisfies the protocol structurally.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol, runtime_checkable


class CandidateLike(Protocol):
    """Minimal candidate-memory view the training pipeline needs."""

    id: str
    content: str


@runtime_checkable
class CandidateMemoryProvider(Protocol):
    """Source of verified/supported candidate memories for training.

    Implementations return candidates filtered to the given states
    (``["verified", "supported"]`` in the default training flow). Every
    candidate must expose ``id`` and a JSON ``content`` string with the
    training payload (``asset_id``, ``label``, ``crop_type``, ``region``).
    """

    def list_candidate_memories(
        self, states: list[str] | None = None, **kwargs: Any
    ) -> Iterable[CandidateLike]:
        """List candidate memories, optionally filtered by state."""
        ...
