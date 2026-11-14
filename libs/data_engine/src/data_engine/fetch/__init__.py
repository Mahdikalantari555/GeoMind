"""Scene acquisition facade: catalog search + ROI-clipped scene download.

Public surface (gateway consumes only this — change: add-scene-fetcher):

    from data_engine.fetch import stac_search, fetch_scene
"""

from data_engine.fetch.api import fetch_scene, stac_search
from data_engine.fetch.types import (
    FetchProgress,
    FetchProgressCallback,
    FetchResult,
    SceneFetcher,
    SceneFetchError,
    SceneIntegrityError,
    SceneRef,
    SceneSearchError,
    emit_progress,
    scenes_from_rows,
)

__all__ = [
    "FetchProgress",
    "FetchProgressCallback",
    "FetchResult",
    "SceneFetcher",
    "SceneFetchError",
    "SceneIntegrityError",
    "SceneRef",
    "SceneSearchError",
    "emit_progress",
    "fetch_scene",
    "scenes_from_rows",
    "stac_search",
]
