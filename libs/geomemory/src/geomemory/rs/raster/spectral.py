"""Spectral indices and band statistics (delegating to geospatial_core)."""

from __future__ import annotations

import numpy as np
from geospatial_core import (
    band_statistics,
)
from geospatial_core import (
    evi as _geo_evi,
)
from geospatial_core import (
    ndvi as _geo_ndvi,
)

from geomemory.core.exceptions import BandMappingError
from geomemory.rs.raster.metadata import RasterSceneData


def ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Normalized Difference Vegetation Index: (NIR - RED) / (NIR + RED)."""
    return _geo_ndvi(nir, red)


def evi(
    nir: np.ndarray,
    red: np.ndarray,
    blue: np.ndarray,
    *,
    g: float = 2.5,
    c1: float = 6.0,
    c2: float = 7.5,
    light: float = 1.0,
) -> np.ndarray:
    """Enhanced Vegetation Index with the standard coefficients."""
    return _geo_evi(nir, red, blue, g=g, c1=c1, c2=c2, light=light)


def resolve_bands(scene: RasterSceneData, mapping: dict[str, int]) -> dict[str, int]:
    """Validate a band mapping (e.g. ``{"nir": 8, "red": 4, "blue": 2}``).

    Band indices are 1-based. Raises :class:`BandMappingError` when a mapped
    index is outside the scene's band count.
    """
    band_count = len(scene.bands)
    invalid = {
        name: index
        for name, index in mapping.items()
        if not isinstance(index, int) or not (1 <= index <= band_count)
    }
    if invalid:
        raise BandMappingError(
            f"Band mapping out of range for a {band_count}-band scene: {invalid}. "
            f"Band indices are 1-based."
        )
    return {name: int(index) for name, index in mapping.items()}


def _check_shapes(a: np.ndarray, b: np.ndarray, name: str) -> None:
    if a.shape != b.shape:
        raise ValueError(f"{name} requires equal-shaped inputs, got {a.shape} and {b.shape}")


def validate_index(name: str, mapping: dict[str, int], required: set[str]) -> dict[str, int]:
    """Validate that all required bands are present in a mapping."""
    missing = sorted(required - set(mapping))
    if missing:
        raise BandMappingError(
            f"{name} requires bands {sorted(required)}, but mapping is missing {missing}"
        )
    return {k: mapping[k] for k in required}


def compute_index(
    name: str,
    arrays: dict[str, np.ndarray],
    mapping: dict[str, int],
    required: set[str],
) -> np.ndarray:
    """Dispatch to the index function for the mapped band arrays.

    ``arrays`` maps band names to raw numpy arrays; ``mapping`` maps band
    names to 1-based indices (used only for validation).
    """
    _ = mapping
    validate_index(name, mapping, required)
    if name.upper() == "NDVI":
        return ndvi(arrays["nir"], arrays["red"])
    if name.upper() == "EVI":
        return evi(arrays["nir"], arrays["red"], arrays["blue"])
    raise BandMappingError(f"Unsupported spectral index: {name}")


__all__: list[str] = [
    "band_statistics",
    "compute_index",
    "evi",
    "ndvi",
    "resolve_bands",
    "validate_index",
]
