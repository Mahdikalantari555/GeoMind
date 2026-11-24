"""Typed public API for scene acquisition (change: add-scene-fetcher).

The gateway consumes only this facade — never the fat io fetcher classes —
so provider injection keeps the test suite offline.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

FetchProgressCallback = Callable[["FetchProgress"], None]


# ── Errors ────────────────────────────────────────────────────────────────────


class SceneFetchError(Exception):
    """Base error for the scene-fetch facade."""


class SceneSearchError(SceneFetchError):
    """STAC search failed (bad sensor, bad ROI, upstream unavailable)."""


class SceneIntegrityError(SceneFetchError):
    """A fetched scene is incomplete or failed its integrity expectations."""


# ── Data types ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SceneRef:
    """Scene metadata returned by a catalog search (no download)."""

    scene_id: str
    datetime: str
    cloud_cover: float | None
    platform: str | None
    bbox: list[float]
    geometry: dict[str, Any] | None
    preview_url: str | None = None
    """Optional STAC quicklook (rendered_preview / thumbnail)."""
    assets: dict[str, str] = field(default_factory=dict)
    """Asset name → href from the STAC item (used for band selection)."""
    cloud_available: bool = True
    """False for SAR (Sentinel-1): no cloud property, ``cloud_cover`` is None."""
    coverage: str = "full"
    """``full`` when the scene footprint covers the ROI, else ``partial``."""


@dataclass(frozen=True)
class FetchProgress:
    """Progress event emitted while a scene download runs."""

    scene_id: str
    stage: str
    percent: int
    detail: str | None = None


@dataclass(frozen=True)
class FetchResult:
    """Downloaded scene: band file paths relative to the destination dir."""

    scene_id: str
    date: str
    cloud_cover: float | None
    directory: str
    band_files: dict[str, str] = field(default_factory=dict)
    mtl_file: str | None = None
    band_map: dict[str, str] = field(default_factory=dict)
    """RGB channel → band-file name, e.g. ``{'R': 'red', 'G': 'green', 'B': 'blue'}``."""
    cloud_available: bool = True
    """False for SAR scenes; callers must not fabricate a 0 % cloud value."""


# ── Provider protocol ─────────────────────────────────────────────────────────


@runtime_checkable
class SceneFetcher(Protocol):
    """Structural provider seam over the io fetcher classes.

    Satisfied by ``PlanetaryComputerLandsatFetcher`` and
    ``SentinelPlanetaryComputerFetcher``; tests inject fakes.
    """

    def search_scenes(
        self,
        roi_geometry: dict[str, Any] | Any,
        date_range: tuple[str | datetime, str | datetime],
    ) -> list[dict[str, Any]]: ...

    def fetch_scenes(
        self,
        roi_geometry: dict[str, Any] | Any,
        date_range: tuple[str | datetime, str | datetime],
        output_dir: str,
        *,
        selected_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]: ...


def emit_progress(
    progress_cb: FetchProgressCallback | None, progress: FetchProgress
) -> None:
    """Deliver a progress event, isolating callback errors from the fetch."""
    if progress_cb is None:
        return
    # Progress must never break the fetch.
    with suppress(Exception):
        progress_cb(progress)


def scenes_from_rows(rows: Iterable[dict[str, Any]]) -> list[SceneRef]:
    """Map raw fetcher search rows to typed SceneRef values."""
    refs: list[SceneRef] = []
    for row in rows:
        when = row.get("datetime")
        if isinstance(when, datetime):
            when = when.isoformat()
        raw_cloud = row.get("cloud_cover", 0.0)
        cloud_available = bool(row.get("cloud_available", raw_cloud is not None))
        refs.append(
            SceneRef(
                scene_id=str(row["id"]),
                datetime=str(when or ""),
                cloud_cover=float(raw_cloud) if raw_cloud is not None else None,
                platform=row.get("platform"),
                bbox=[float(x) for x in (row.get("bbox") or [])],
                geometry=row.get("geometry"),
                preview_url=row.get("preview_url"),
                assets={str(k): str(v) for k, v in (row.get("assets") or {}).items()},
                cloud_available=cloud_available,
                coverage=str(row.get("coverage", "full")),
            )
        )
    return refs
