"""Offline tests for the data_engine.fetch facade (fake provider injection).

No network in this suite — the io fetcher classes are never constructed;
fakes satisfy the SceneFetcher protocol (change: add-scene-fetcher).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from data_engine.fetch import (
    FetchProgress,
    FetchResult,
    SceneFetcher,
    SceneFetchError,
    SceneIntegrityError,
    SceneRef,
    SceneSearchError,
    fetch_scene,
    stac_search,
)


class FakeFetcher:
    """Deterministic SceneFetcher double."""

    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        results: list[dict[str, Any]] | None = None,
        search_error: Exception | None = None,
        fetch_error: Exception | None = None,
    ) -> None:
        self.rows = rows or []
        self.results = results or []
        self.search_error = search_error
        self.fetch_error = fetch_error
        self.searched_with: tuple[Any, Any] | None = None
        self.fetched_selected: list[str] | None = None
        self.fetched_dest: str | None = None

    def search_scenes(
        self, roi_geometry: dict[str, Any] | Any, date_range: tuple[str, str]
    ) -> list[dict[str, Any]]:
        self.searched_with = (roi_geometry, date_range)
        if self.search_error is not None:
            raise self.search_error
        return self.rows

    def fetch_scenes(
        self,
        roi_geometry: dict[str, Any] | Any,
        date_range: tuple[str, str],
        output_dir: str,
        *,
        selected_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        self.fetched_selected = selected_ids
        self.fetched_dest = output_dir
        if self.fetch_error is not None:
            raise self.fetch_error
        return self.results


ROI = {"type": "Polygon", "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]]}
ROWS = [
    {
        "id": "LC08_test",
        "datetime": datetime(2024, 7, 1, 8, 0, 0),
        "cloud_cover": 12.5,
        "platform": "landsat-8",
        "bbox": [0.0, 0.0, 1.0, 1.0],
        "geometry": ROI,
    },
    {
        "id": "LC09_test2",
        "datetime": "2024-07-05T08:00:00Z",
        "cloud_cover": 40.0,
        "platform": "landsat-9",
        "bbox": [0.0, 0.0, 1.0, 1.0],
        "geometry": None,
    },
]

RESULT_ROW = {
    "scene_id": "LC08_test",
    "date": "2024-07-01",
    "cloud_cover": 12.5,
    "directory": "dest/landsat_20240701_047_030",
    "band_files": {"blue": "dest/landsat_20240701_047_030/blue.tif"},
    "mtl_file": "dest/landsat_20240701_047_030/MTL.json",
}


def test_search_maps_rows_to_scene_refs() -> None:
    fake = FakeFetcher(rows=ROWS)
    refs = stac_search(ROI, sensor="landsat", date_from="2024-07-01", date_to="2024-07-31", fetcher=fake)
    assert isinstance(refs[0], SceneRef)
    assert refs[0].scene_id == "LC08_test"
    assert refs[0].datetime == "2024-07-01T08:00:00"  # datetime normalized to ISO
    assert refs[0].cloud_cover == pytest.approx(12.5)
    assert refs[1].datetime == "2024-07-05T08:00:00Z"  # strings pass through
    assert fake.searched_with == (ROI, ("2024-07-01", "2024-07-31"))


def test_search_maps_upstream_errors() -> None:
    fake = FakeFetcher(search_error=RuntimeError("planetary computer down"))
    with pytest.raises(SceneSearchError, match="planetary computer down"):
        stac_search(ROI, sensor="landsat", date_from="2024-07-01", date_to="2024-07-02", fetcher=fake)


def test_search_rejects_unknown_sensor_before_instantiation() -> None:
    with pytest.raises(SceneSearchError, match="unknown sensor"):
        stac_search(ROI, sensor="modis", date_from="2024-07-01", date_to="2024-07-02")


def test_fetch_scene_builds_result_and_forwards_selection() -> None:
    fake = FakeFetcher(results=[RESULT_ROW])
    events: list[FetchProgress] = []
    result = fetch_scene(
        "LC08_test",
        ROI,
        sensor="landsat",
        date_from="2024-07-01",
        date_to="2024-07-31",
        dest="out",
        progress_cb=events.append,
        fetcher=fake,
    )
    assert isinstance(result, FetchResult)
    assert result.scene_id == "LC08_test"
    assert result.band_files["blue"].endswith("blue.tif")
    assert result.mtl_file is not None
    assert fake.fetched_selected == ["LC08_test"]  # single-scene selection forwarded
    stages = [e.stage for e in events]
    assert stages[0] == "fetch" and stages[-1] == "done"
    assert "verify" in stages
    assert events[-1].percent == 100


def test_fetch_scene_resume_short_circuit(tmp_path: Path) -> None:
    """Fetcher-level resume: selection pass-through is the seam the gateway uses."""
    fake = FakeFetcher(results=[RESULT_ROW])
    fetch_scene("LC08_test", ROI, sensor="landsat", date_from="2024-07-01", date_to="2024-07-31", dest=tmp_path, fetcher=fake)
    assert fake.fetched_selected == ["LC08_test"]
    assert fake.fetched_dest == str(tmp_path)


def test_fetch_scene_empty_result_raises() -> None:
    fake = FakeFetcher(results=[])
    with pytest.raises(SceneFetchError, match="did not produce results"):
        fetch_scene("gone", ROI, sensor="landsat", date_from="2024-07-01", date_to="2024-07-02", dest="out", fetcher=fake)


def test_fetch_scene_no_band_files_is_integrity_error() -> None:
    row = dict(RESULT_ROW)
    row["band_files"] = {}
    fake = FakeFetcher(results=[row])
    with pytest.raises(SceneIntegrityError, match="no band files"):
        fetch_scene("LC08_test", ROI, sensor="landsat", date_from="2024-07-01", date_to="2024-07-02", dest="out", fetcher=fake)


def test_progress_cb_errors_are_isolated() -> None:
    fake = FakeFetcher(results=[RESULT_ROW])

    def boom(_p: FetchProgress) -> None:
        raise RuntimeError("consumer broke")

    result = fetch_scene(
        "LC08_test", ROI, sensor="landsat", date_from="2024-07-01", date_to="2024-07-02", dest="out", progress_cb=boom, fetcher=fake
    )
    assert result.scene_id == "LC08_test"  # fetch completed despite cb raising


def test_fetcher_protocol_is_structural() -> None:
    assert isinstance(FakeFetcher(), SceneFetcher)


def test_scene_ref_is_json_serializable() -> None:
    refs = stac_search(ROI, sensor="landsat", date_from="2024-07-01", date_to="2024-07-02", fetcher=FakeFetcher(rows=ROWS[:1]))
    payload = json.dumps(refs[0].__dict__)
    assert "LC08_test" in payload
