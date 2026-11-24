"""Offline tests for the Sentinel-1 GRD/RTC fetchers and facade mapping.

Ported from GeoDataEngine ``tests/test_planetary_computer_fetcher.py:428-828``.
All catalog/GDAL/MPC calls are mocked — no network and no GDAL install needed.
"""
# ruff: noqa: DTZ001  # naive datetimes intentional — matches _normalize_dates API

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from shapely.geometry import box

from data_engine.fetch.api import SENSORS, _build_fetcher
from data_engine.fetch.types import scenes_from_rows
from data_engine.io.errors import PartialDataError
from data_engine.io.planetary_computer_fetcher import (
    SENTINEL1_NODATA,
    SENTINEL1_RTC_NODATA,
    Sentinel1PlanetaryComputerFetcher,
    Sentinel1RtcPlanetaryComputerFetcher,
)


def _s1_item(
    item_id: str = "S1A_IW_GRDH_1SDV_20240101T000000",
    mode: str = "IW",
    orbit: str = "ascending",
) -> Mock:
    """Mock a Sentinel-1 GRD STAC item."""
    item = Mock()
    item.id = item_id
    item.datetime = datetime(2024, 1, 1, 0, 0, 0)
    item.bbox = [48.0, 31.0, 48.5, 31.5]
    item.collection_id = "sentinel-1-grd"
    item.geometry = {
        "type": "Polygon",
        "coordinates": [
            [[48.0, 31.0], [48.5, 31.0], [48.5, 31.5], [48.0, 31.5], [48.0, 31.0]]
        ],
    }
    item.assets = {
        "vv": Mock(href="https://example.invalid/vv.tif"),
        "vh": Mock(href="https://example.invalid/vh.tif"),
    }
    item.properties = {
        "datetime": "2024-01-01T00:00:00Z",
        "platform": "sentinel-1a",
        "constellation": "Sentinel-1",
        "sar:instrument_mode": mode,
        "sat:orbit_state": orbit,
        "sat:relative_orbit": 72,
        "sar:polarizations": ["VV", "VH"],
        "s1:product_identifier": "S1A_IW_GRDH_1SDV_20240101T000000_000001_0001",
    }
    return item


def _mock_catalog(fetcher: object, items: list[Mock]) -> None:
    """Patch the lazily-opened catalog with a stub yielding ``items``."""
    search = Mock()
    search.items.return_value = items
    with patch.object(fetcher, "client") as mock_client:
        mock_client.search.return_value = search


class TestSentinel1PlanetaryComputerFetcher:
    """GRD defaults, SAR descriptors, GCP warp and scene folders."""

    def test_init_default(self) -> None:
        fetcher = Sentinel1PlanetaryComputerFetcher()
        assert fetcher.collection == "sentinel-1-grd"
        assert fetcher.bands == ["vv", "vh"]
        assert fetcher.instrument_mode is None
        assert fetcher.orbit_direction is None
        assert fetcher.resolution == 10.0

    def test_init_rejects_unknown_polarisation(self) -> None:
        with pytest.raises(ValueError, match="Unknown band"):
            Sentinel1PlanetaryComputerFetcher(bands=["blue"])

    def test_search_scenes_reports_no_cloud_cover(self) -> None:
        fetcher = Sentinel1PlanetaryComputerFetcher()
        item = _s1_item()
        search = Mock()
        search.items.return_value = [item]
        with patch.object(fetcher, "client") as mock_client:
            mock_client.search.return_value = search
            results = fetcher.search_scenes(
                box(48.0, 31.0, 48.5, 31.5),
                (datetime(2024, 1, 1), datetime(2024, 1, 2)),
            )

        assert len(results) == 1
        assert results[0]["cloud_cover"] is None
        assert results[0]["polarizations"] == ["vv", "vh"]
        assert results[0]["instrument_mode"] == "IW"
        assert results[0]["orbit_state"] == "ascending"

    def test_search_scenes_filters_on_acquisition_mode(self) -> None:
        fetcher = Sentinel1PlanetaryComputerFetcher(instrument_mode="IW")
        ewm = _s1_item("S1A_EW_GRDH_1SDV_20240101T000000", mode="EW")
        search = Mock()
        search.items.return_value = [_s1_item(), ewm]
        with patch.object(fetcher, "client") as mock_client:
            mock_client.search.return_value = search
            results = fetcher.search_scenes(
                box(48.0, 31.0, 48.5, 31.5),
                (datetime(2024, 1, 1), datetime(2024, 1, 2)),
            )
        assert [r["id"] for r in results] == [_s1_item().id]

    def test_scene_dirname_distinguishes_orbit_passes(self) -> None:
        fetcher = Sentinel1PlanetaryComputerFetcher()
        asc = fetcher._scene_dirname(_s1_item("asc", orbit="ascending"))
        desc = fetcher._scene_dirname(_s1_item("desc", orbit="descending"))
        assert asc == "sentinel1_20240101_asc"
        assert desc == "sentinel1_20240101_desc"
        assert asc != desc

    def test_find_existing_scene_accepts_any_polarisation(self, tmp_path: Path) -> None:
        fetcher = Sentinel1PlanetaryComputerFetcher(bands=["vv", "vh"])
        scene_dir = tmp_path / "sentinel1_20240101_asc"
        scene_dir.mkdir()
        (scene_dir / "vv.tif").touch()
        (scene_dir / "MTL.json").touch()
        found = fetcher._find_existing_scene(scene_dir)
        assert found is not None
        assert list(found[0]) == ["vv"]

    def test_find_existing_scene_rejects_missing_metadata(self, tmp_path: Path) -> None:
        fetcher = Sentinel1PlanetaryComputerFetcher()
        scene_dir = tmp_path / "sentinel1_20240101_asc"
        scene_dir.mkdir()
        (scene_dir / "vv.tif").touch()
        assert fetcher._find_existing_scene(scene_dir) is None

    def test_create_mtl_metadata_records_sar_fields(self, tmp_path: Path) -> None:
        fetcher = Sentinel1PlanetaryComputerFetcher()
        item = _s1_item()
        mtl_path = fetcher._create_mtl_metadata(item, tmp_path)
        payload = json.loads(mtl_path.read_text())
        assert payload["item_id"] == item.id
        assert payload["polarizations"] == ["vv", "vh"]
        assert payload["instrument_mode"] == "IW"
        assert payload["orbit_state"] == "ascending"
        assert payload["relative_orbit"] == 72
        assert payload["geolocation"]["method"] == "gdal-tps"

    @patch("data_engine.io.planetary_computer_fetcher._configure_gdal_http")
    @patch("planetary_computer.sign")
    def test_download_clip_bands_requires_gdal(
        self, mock_sign: Mock, mock_gdal: Mock, tmp_path: Path
    ) -> None:
        gdal = Mock()
        gdal.Warp.side_effect = RuntimeError("network down")
        mock_gdal.return_value = gdal
        item = _s1_item()
        mock_sign.return_value = item
        fetcher = Sentinel1PlanetaryComputerFetcher()
        # Per scene-fetch spec: a scene missing required bands raises
        # PartialDataError rather than being reported as a completed download.
        with pytest.raises(PartialDataError, match="incomplete"):
            fetcher.download_and_clip_bands(
                item, [48.0, 31.0, 48.5, 31.5], tmp_path, 10.0
            )

    @patch("data_engine.io.planetary_computer_fetcher._configure_gdal_http")
    @patch("planetary_computer.sign")
    def test_download_clip_bands_writes_one_file_per_polarisation(
        self, mock_sign: Mock, mock_gdal: Mock, tmp_path: Path
    ) -> None:
        import numpy as np
        import rasterio

        calls: list[dict[str, object]] = []

        def fake_warp(dest: str, source: str, **kwargs: object) -> None:
            calls.append({"dest": dest, "source": source, **kwargs})
            with rasterio.open(
                dest,
                "w",
                driver="GTiff",
                height=4,
                width=4,
                count=1,
                dtype="uint16",
                crs=kwargs["dstSRS"],
                transform=rasterio.Affine(10, 0, 0, 0, -10, 0),
                nodata=0,
            ) as dst:
                dst.write(np.full((4, 4), 100, dtype="uint16"), 1)

        gdal = Mock()
        gdal.Warp.side_effect = fake_warp
        mock_gdal.return_value = gdal
        item = _s1_item()
        mock_sign.return_value = item
        fetcher = Sentinel1PlanetaryComputerFetcher()

        files = fetcher.download_and_clip_bands(
            item, [48.0, 31.0, 48.5, 31.5], tmp_path, 10.0
        )
        assert sorted(files) == ["vh", "vv"]
        assert all(path.name.endswith(".tif") for path in files.values())
        assert calls[0]["dstSRS"] == "EPSG:32639"
        assert calls[0]["tps"] is True
        assert str(calls[0]["source"]).startswith("/vsicurl/")

    def test_fetch_scenes_uses_sentinel1_folder_names(self, tmp_path: Path) -> None:
        fetcher = Sentinel1PlanetaryComputerFetcher()
        item = _s1_item()
        fake_files = {"vv": tmp_path / "vv.tif", "vh": tmp_path / "vh.tif"}
        with (
            patch.object(fetcher, "_search_scenes_by_bbox", return_value=[item]),
            patch.object(fetcher, "download_and_clip_bands", return_value=fake_files),
            patch.object(
                fetcher, "_create_mtl_metadata", return_value=tmp_path / "MTL.json"
            ),
        ):
            results = fetcher.fetch_scenes(
                box(48.0, 31.0, 48.5, 31.5),
                ("2024-01-01", "2024-01-02"),
                str(tmp_path),
            )
        assert len(results) == 1
        assert Path(results[0]["directory"]).name == "sentinel1_20240101_asc"
        assert results[0]["polarizations"] == ["vv", "vh"]
        assert results[0]["cloud_cover"] is None
        assert results[0]["cloud_available"] is False


class TestSentinel1RtcPlanetaryComputerFetcher:
    """Terrain-corrected (``sentinel-1-rtc``) fetcher."""

    @staticmethod
    def _rtc_item() -> Mock:
        item = Mock()
        item.id = "S1A_IW_GRDH_1SDV_20240101T000000_057296_070CA3_rtc"
        item.datetime = datetime(2024, 1, 1, 0, 0, 0)
        item.bbox = [48.0, 31.0, 48.5, 31.5]
        item.collection_id = "sentinel-1-rtc"
        item.geometry = {
            "type": "Polygon",
            "coordinates": [
                [[48.0, 31.0], [48.5, 31.0], [48.5, 31.5], [48.0, 31.5], [48.0, 31.0]]
            ],
        }
        item.assets = {
            "vv": Mock(href="https://example.invalid/vv_rtc.tif"),
            "vh": Mock(href="https://example.invalid/vh_rtc.tif"),
        }
        item.properties = {
            "datetime": "2024-01-01T00:00:00Z",
            "platform": "SENTINEL-1A",
            "constellation": "Sentinel-1",
            "sar:instrument_mode": "IW",
            "sat:orbit_state": "ascending",
            "sat:relative_orbit": 72,
            "sar:polarizations": ["VV", "VH"],
            "s1:processing_level": "1",
        }
        return item

    def test_init_default(self) -> None:
        fetcher = Sentinel1RtcPlanetaryComputerFetcher()
        assert fetcher.collection == "sentinel-1-rtc"
        assert fetcher.bands == ["vv", "vh"]
        assert fetcher.resolution == 10.0

    def test_init_rejects_unknown_polarisation(self) -> None:
        with pytest.raises(ValueError, match="Unknown band"):
            Sentinel1RtcPlanetaryComputerFetcher(bands=["blue"])

    @patch("data_engine.io.planetary_computer_fetcher._configure_gdal_http")
    @patch("planetary_computer.sign")
    def test_download_clip_bands_is_a_plain_warp(
        self, mock_sign: Mock, mock_gdal: Mock, tmp_path: Path
    ) -> None:
        import numpy as np
        import rasterio

        calls: list[dict[str, object]] = []

        def fake_warp(dest: str, source: str, **kwargs: object) -> None:
            calls.append({"dest": dest, "source": source, **kwargs})
            with rasterio.open(
                dest,
                "w",
                driver="GTiff",
                height=4,
                width=4,
                count=1,
                dtype="float32",
                crs=kwargs["dstSRS"],
                transform=rasterio.Affine(10, 0, 0, 0, -10, 0),
                nodata=0,
            ) as dst:
                dst.write(np.full((4, 4), 0.1, dtype="float32"), 1)

        gdal = Mock()
        gdal.Warp.side_effect = fake_warp
        mock_gdal.return_value = gdal
        item = self._rtc_item()
        mock_sign.return_value = item
        fetcher = Sentinel1RtcPlanetaryComputerFetcher()

        files = fetcher.download_and_clip_bands(
            item, [48.0, 31.0, 48.5, 31.5], tmp_path, 10.0
        )
        assert sorted(files) == ["vh", "vv"]
        assert all(path.name.endswith(".tif") for path in files.values())
        assert calls[0]["dstSRS"] == "EPSG:32639"
        assert "tps" not in calls[0]
        assert calls[0]["srcNodata"] == SENTINEL1_RTC_NODATA
        assert calls[0]["dstNodata"] == SENTINEL1_NODATA
        assert str(calls[0]["source"]).startswith("/vsicurl/")

    def test_create_mtl_metadata_records_rtc_fields(self, tmp_path: Path) -> None:
        fetcher = Sentinel1RtcPlanetaryComputerFetcher()
        item = self._rtc_item()
        mtl_path = fetcher._create_mtl_metadata(item, tmp_path)
        payload = json.loads(mtl_path.read_text())
        assert payload["item_id"] == item.id
        assert payload["product_identifier"] == item.id
        assert payload["processing_level"] == "L1 GRD (RTC gamma-0)"
        assert payload["radiometry"]["measure"] == "gamma0"
        assert payload["radiometry"]["scale"] == "linear power"
        assert payload["geolocation"]["method"] == "provider-rtc"
        assert payload["geolocation"]["dem"] == "Copernicus DEM GLO-30"
        assert payload["METADATA"]["PRODUCT_METADATA"]["PROCESSING_LEVEL"] == "RTC gamma-0"

    def test_fetch_scenes_uses_sentinel1_folder_names(self, tmp_path: Path) -> None:
        fetcher = Sentinel1RtcPlanetaryComputerFetcher()
        item = self._rtc_item()
        fake_files = {"vv": tmp_path / "vv.tif", "vh": tmp_path / "vh.tif"}
        with (
            patch.object(fetcher, "_search_scenes_by_bbox", return_value=[item]),
            patch.object(fetcher, "download_and_clip_bands", return_value=fake_files),
            patch.object(
                fetcher, "_create_mtl_metadata", return_value=tmp_path / "MTL.json"
            ),
        ):
            results = fetcher.fetch_scenes(
                box(48.0, 31.0, 48.5, 31.5),
                ("2024-01-01", "2024-01-02"),
                str(tmp_path),
            )
        assert len(results) == 1
        assert Path(results[0]["directory"]).name == "sentinel1_20240101_asc"


class TestSentinel1Facade:
    """Facade wiring: sensor selection and cloud-cover mapping."""

    def test_build_fetcher_selects_s1_variants(self) -> None:
        assert "sentinel-1" in SENSORS
        assert "sentinel-1-rtc" in SENSORS
        assert isinstance(_build_fetcher("sentinel-1"), Sentinel1PlanetaryComputerFetcher)
        assert isinstance(
            _build_fetcher("sentinel-1-rtc"), Sentinel1RtcPlanetaryComputerFetcher
        )

    def test_sar_scene_cloud_mapping_preserves_none(self) -> None:
        refs = scenes_from_rows([{"id": "s1", "datetime": "2024-01-01", "cloud_cover": None}])
        assert refs[0].cloud_cover is None
        assert refs[0].cloud_available is False

    def test_optical_scene_cloud_mapping(self) -> None:
        refs = scenes_from_rows([{"id": "lc08", "datetime": "2024-01-01", "cloud_cover": 12.5}])
        assert refs[0].cloud_cover == 12.5
        assert refs[0].cloud_available is True
