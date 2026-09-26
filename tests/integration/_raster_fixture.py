from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds


def create_synthetic_raster(
    output_path: Path | str,
    bounds: tuple[float, float, float, float] = (48.19, 30.95, 48.28, 31.05),
    width: int = 100,
    height: int = 100,
    bands: int = 4,
) -> Path:
    """Generate a 4-band synthetic GeoTIFF (Red, Green, NIR, SWIR) covering bounds."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    west, south, east, north = bounds
    transform = from_bounds(west, south, east, north, width, height)

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": bands,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": transform,
        "nodata": -9999.0,
    }

    rng = np.random.default_rng(42)
    with rasterio.open(target, "w", **profile) as dst:
        for b in range(1, bands + 1):
            data = rng.uniform(0.1, 0.9, (height, width)).astype("float32")
            dst.write(data, b)

    return target
