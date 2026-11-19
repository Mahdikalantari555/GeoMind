"""Gateway ROI store (change: add-studio-knowledge-agent §4.1).

ROIs drawn in Studio (or created by the ``roi_create`` agent tool) are
persisted as a JSON document inside the active workspace
(``<workspace>/rois.json``) so the UI and the agent share one store.
Area/centroid are computed server-side with the same equirectangular
shoelace formula the Studio uses, keeping the two in agreement.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

ROI_FILENAME = "rois.json"


def _store_path(workspace_dir: Path) -> Path:
    return workspace_dir / ROI_FILENAME


def ring_stats(coords: list[list[float]]) -> tuple[float, list[float]]:
    """Return ``(area_ha, centroid)`` for a lon/lat ring.

    Equirectangular projection around the ring's mean latitude, then
    shoelace — identical to Studio's ``ringArea``.
    """
    if len(coords) < 3:
        return 0.0, [0.0, 0.0]
    lat0 = sum(p[1] for p in coords) / len(coords)
    k = math.cos(math.radians(lat0))
    radius = 6371000.0
    pts = [
        (math.radians(p[0]) * radius * k, math.radians(p[1]) * radius) for p in coords
    ]
    area2 = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(len(pts) - 1):
        f = pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1]
        area2 += f
        cx += (coords[i][0] + coords[i + 1][0]) * f
        cy += (coords[i][1] + coords[i + 1][1]) * f
    area2 /= 2.0
    if area2 == 0.0:
        centroid = [coords[0][0], coords[0][1]]
    else:
        centroid = [cx / (6.0 * area2), cy / (6.0 * area2)]
    return abs(area2) / 10000.0, centroid


def _closed_ring(coords: list[list[float]]) -> list[list[float]]:
    ring = [[float(p[0]), float(p[1])] for p in coords]
    if ring and (ring[0][0] != ring[-1][0] or ring[0][1] != ring[-1][1]):
        ring.append(list(ring[0]))
    return ring


def load_rois(workspace_dir: Path) -> list[dict[str, Any]]:
    """Read all persisted ROIs (empty list when the store is absent)."""
    path = _store_path(workspace_dir)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _save(workspace_dir: Path, rois: list[dict[str, Any]]) -> None:
    path = _store_path(workspace_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="rois-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(rois, fh, indent=2)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def create_roi(
    workspace_dir: Path,
    *,
    name: str,
    kind: str,
    coords: list[list[float]],
) -> dict[str, Any]:
    """Create, persist, and return a new ROI."""
    ring = _closed_ring(coords)
    area_ha, centroid = ring_stats(ring)
    roi: dict[str, Any] = {
        "id": f"roi-{uuid.uuid4().hex[:12]}",
        "name": name,
        "kind": kind,
        "coords": ring,
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "areaHa": area_ha,
        "centroid": centroid,
        "createdAt": int(time.time() * 1000),
    }
    rois = load_rois(workspace_dir)
    rois.append(roi)
    _save(workspace_dir, rois)
    return roi


def get_roi(workspace_dir: Path, roi_id: str) -> dict[str, Any] | None:
    for roi in load_rois(workspace_dir):
        if roi.get("id") == roi_id:
            return roi
    return None


def delete_roi(workspace_dir: Path, roi_id: str) -> bool:
    """Delete an ROI; True when one was removed."""
    rois = load_rois(workspace_dir)
    kept = [r for r in rois if r.get("id") != roi_id]
    if len(kept) == len(rois):
        return False
    _save(workspace_dir, kept)
    return True
