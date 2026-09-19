"""Shapefile loader — produces a searchable vector layer description.

Requires the ``rs`` extra (geopandas/shapely). Importing this module without
those dependencies raises a clear ``RuntimeError`` naming the missing package.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from geomemory.core.models import ParsedObject, SourceRef


def _require_rs() -> None:
    """Raise a clear error when the ``rs`` extra is not installed."""
    try:
        import geopandas  # noqa: F401
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Shapefile loading requires the 'rs' extra (geopandas/shapely). "
            "Install with `pip install geomemory[rs]`."
        ) from exc


# Importing this module without the ``rs`` extra fails loudly rather than
# producing an opaque ImportError later during ingestion.
_require_rs()


class ShapefileLoader:
    """Load shapefiles (``.shp``) into a searchable vector layer payload.

    Sidecar files (``.shx``, ``.dbf``, ``.prj``) are consumed automatically by
    geopandas when the ``.shp`` is read.
    """

    def __init__(self, *, reader: Any | None = None) -> None:
        _require_rs()
        from geomemory.rs.vector.reader import VectorReader

        self.reader = reader or VectorReader()

    def supports(self, source: SourceRef) -> bool:
        """Return True for shapefiles (by extension)."""
        if source.path is None:
            return False
        return Path(source.path).suffix.lower() == ".shp"

    def load(self, source: SourceRef) -> Iterable[ParsedObject]:
        """Read layer metadata and yield a single ParsedObject."""
        if source.path is None:
            raise ValueError("ShapefileLoader requires a local file path")
        from geomemory.rs.vector.reader import describe_layer

        layer = self.reader.read_layer(source.path)
        title = Path(source.path).name
        yield ParsedObject(
            source=source,
            mime_type="application/x-shp",
            title=title,
            text=describe_layer(layer),
            metadata={
                "vector": {"layer": layer.model_dump()},
                "locators": [{"file": str(source.path), "asset": title}],
            },
            raw=layer,
        )


__all__ = ["ShapefileLoader"]
