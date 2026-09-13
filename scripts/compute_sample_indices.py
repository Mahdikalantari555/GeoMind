#!/usr/bin/env python3
"""End-to-end sample pipeline: AOI -> satellite scenes -> index GeoTIFFs."""

import argparse
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

from data_engine.core.datacube import DataCube
from data_engine.io.landsat_reader import LandsatReader
from data_engine.io.planetary_computer_fetcher import (
    PlanetaryComputerLandsatFetcher,
    SentinelPlanetaryComputerFetcher,
)
from data_engine.output.writer import write_geotiff
from data_engine.pipeline.metric_pipeline import METRICPipeline
from data_engine.surface.moisture import MSI, NDMI
from data_engine.surface.vegetation import VegetationIndices

logger = logging.getLogger(__name__)

DATE_WINDOW_DAYS = 15
LANDSAT_OUTPUT_CATEGORIES = ["et_core", "surface_props", "stress_indices", "spectral_indices"]
SENTINEL_BANDS = ["blue", "green", "red", "nir08", "swir16", "swir22"]
SENTINEL_OUTPUT_BANDS = ["ndvi", "savi", "evi", "lai", "fvc", "ndmi", "msi", "optram"]


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute spectral/stress indices for a GeoJSON AOI from Planetary Computer scenes."
    )
    parser.add_argument("--input", required=True, help="GeoJSON AOI file")
    parser.add_argument("--dates", nargs=3, required=True, metavar=("DATE", "DATE", "DATE"),
                        help="Three target dates (YYYY-MM-DD)")
    parser.add_argument("--landsat", action="store_true", help="Run Landsat processing")
    parser.add_argument("--sentinel", action="store_true", help="Run Sentinel-2 processing")
    parser.add_argument("--resolution", type=float, default=30.0, help="Output resolution in meters")
    return parser.parse_args(argv)


def load_aoi(input_path: Path) -> Tuple[Any, List[float]]:
    """Load GeoJSON AOI and return (first geometry, bbox)."""
    with open(input_path) as handle:
        geojson = json.load(handle)
    features = geojson.get("features", [])
    if not features:
        raise ValueError(f"GeoJSON has no features: {input_path}")
    geometry = features[0].get("geometry")
    if geometry is None:
        raise ValueError(f"First GeoJSON feature has no geometry: {input_path}")
    from shapely.geometry import shape

    geom = shape(geometry)
    return geom, list(geom.bounds)


def date_windows(dates: Sequence[str]) -> List[Tuple[datetime, datetime]]:
    """Build +/-15 day windows around each target date."""
    windows = []
    for date_str in dates:
        target = datetime.fromisoformat(date_str)
        start = target - timedelta(days=DATE_WINDOW_DAYS)
        end = target + timedelta(days=DATE_WINDOW_DAYS)
        windows.append((start, end))
    return windows


def _fetch_scenes(fetcher: Any, aoi_geometry: Any, window: Tuple[datetime, datetime],
                  output_dir: Path, resolution: float) -> List[dict]:
    """Search and download scenes for one date window."""
    return fetcher.fetch_scenes(
        roi_geometry=aoi_geometry,
        date_range=window,
        output_dir=str(output_dir),
        resolution=resolution,
    )


def _scene_output_dir(output_base: Path, scene_id: str, sentinel: bool = False) -> Path:
    suffix = "-s2" if sentinel else ""
    return output_base / f"{scene_id}{suffix}"


def _run_landsat_pipeline(scene_dir: Path, output_dir: Path, aoi_path: Path) -> None:
    """Run METRIC pipeline for one Landsat scene."""
    pipeline = METRICPipeline(roi_path=str(aoi_path))
    pipeline.run(
        landsat_dir=str(scene_dir),
        meteo_data={},
        output_dir=str(output_dir),
        roi_path=str(aoi_path),
        output_categories=LANDSAT_OUTPUT_CATEGORIES,
    )


def _load_sentinel_cube(scene_dir: Path) -> DataCube:
    """Load a downloaded Sentinel-2 scene into a DataCube."""
    band_mapping = {band: f"{band}.tif" for band in SENTINEL_BANDS}
    return LandsatReader(band_mapping=band_mapping).load(str(scene_dir))


def _compute_sentinel_indices(cube: DataCube) -> DataCube:
    """Compute vegetation, moisture, and OPTRAM indices."""
    VegetationIndices(compute_optram=True).compute(cube)
    NDMI().compute(cube)
    MSI().compute(cube)
    return cube


def _write_sentinel_outputs(cube: DataCube, output_dir: Path, scene_id: str) -> List[Path]:
    """Write Sentinel index bands as GeoTIFFs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    produced = []
    for band_name in SENTINEL_OUTPUT_BANDS:
        if band_name not in cube.bands():
            continue
        path = output_dir / f"{band_name}_{scene_id}.tif"
        write_geotiff(str(path), cube.data[band_name], cube)
        produced.append(path)
    return produced


def process_landsat(aoi_geometry: Any, windows: Sequence[Tuple[datetime, datetime]],
                    output_base: Path, resolution: float, aoi_path: Path) -> List[Path]:
    """Process Landsat scenes for each date window."""
    produced = []
    fetcher = PlanetaryComputerLandsatFetcher()
    for start, end in windows:
        try:
            scenes = _fetch_scenes(fetcher, aoi_geometry, (start, end), output_base / ".work", resolution)
        except Exception as exc:
            logger.warning(f"No Landsat scene for {start.date()}..{end.date()}: {exc}")
            continue
        if not scenes:
            logger.warning(f"No Landsat scene for {start.date()}..{end.date()}")
            continue
        scene = scenes[0]
        scene_dir = Path(scene["directory"])
        scene_id = scene["scene_id"]
        output_dir = _scene_output_dir(output_base, scene_id)
        _run_landsat_pipeline(scene_dir, output_dir, aoi_path)
        produced.extend(output_dir.iterdir())
    return produced


def process_sentinel(aoi_geometry: Any, windows: Sequence[Tuple[datetime, datetime]],
                     output_base: Path, resolution: float, aoi_path: Path) -> List[Path]:
    """Process Sentinel-2 scenes for each date window."""
    produced = []
    fetcher = SentinelPlanetaryComputerFetcher()
    for start, end in windows:
        try:
            scenes = _fetch_scenes(fetcher, aoi_geometry, (start, end), output_base / ".work", resolution)
        except Exception as exc:
            logger.warning(f"No Sentinel-2 scene for {start.date()}..{end.date()}: {exc}")
            continue
        if not scenes:
            logger.warning(f"No Sentinel-2 scene for {start.date()}..{end.date()}")
            continue
        scene = scenes[0]
        scene_dir = Path(scene["directory"])
        scene_id = scene["scene_id"]
        output_dir = _scene_output_dir(output_base, scene_id, sentinel=True)
        cube = _load_sentinel_cube(scene_dir)
        _compute_sentinel_indices(cube)
        produced.extend(_write_sentinel_outputs(cube, output_dir, scene_id))
    return produced


def _nearest_scene_message(searched_dates: Sequence[str]) -> str:
    """Build an error message listing searched dates when no scene intersects the AOI."""
    return "No scene intersects AOI. Searched dates: " + ", ".join(searched_dates)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    input_path = Path(args.input)
    output_base = input_path.parent / "output"
    output_base.mkdir(parents=True, exist_ok=True)

    aoi_geometry, _ = load_aoi(input_path)
    windows = date_windows(args.dates)

    run_landsat = args.landsat or not args.sentinel
    run_sentinel = args.sentinel

    produced = []
    if run_landsat:
        produced.extend(process_landsat(aoi_geometry, windows, output_base, args.resolution, input_path))
    if run_sentinel:
        produced.extend(process_sentinel(aoi_geometry, windows, output_base, args.resolution, input_path))

    if not produced:
        raise SystemExit(_nearest_scene_message(args.dates))

    print(f"Produced {len(produced)} file(s) under {output_base}")
    for path in produced:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
