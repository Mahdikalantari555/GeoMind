"""Vision model downloader — OLMoEarth Nano v1.2 weight acquisition."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geomemory.core.models import WorkspaceSettings

HUB_REPO = "allenai/OlmoEarth-v1_2-Nano"


def _find_cached_weights() -> Path | None:
    """Look for an existing OLMoEarth snapshot in the HF cache."""
    cache = Path.home() / ".cache" / "huggingface" / "hub"
    root = cache / "models--allenai--OlmoEarth-v1_2-Nano" / "snapshots"
    if not root.is_dir():
        return None
    for snapshot in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if snapshot.is_dir() and (snapshot / "weights.pth").is_file():
            return snapshot
    return None


def download_vision_model(settings: WorkspaceSettings) -> str | None:
    """Download OLMoEarth vision weights into the workspace project folder or HF cache.

    Returns the resolved path when a ``weights.pth`` is found after download.
    Returns ``None`` when ``offline`` is enabled or the download fails.
    """
    if settings.offline:
        return None

    cached = _find_cached_weights()
    if cached is not None:
        return str(cached)

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise ImportError(
            "Vision model download requires the optional `huggingface-hub` package. "
            "Install with `pip install geomemory[vision]`."
        ) from exc

    # Save into the workspace project folder, falling back to the HF cache.
    ws_dir = getattr(settings, "_ws_dir", None)
    if ws_dir:
        target_dir = Path(ws_dir).expanduser() / "models" / "vision"
    else:
        target_dir = Path.home() / ".cache" / "huggingface" / "hub"

    try:
        local = snapshot_download(
            HUB_REPO,
            allow_patterns=["**/*.pth"],
            cache_dir=str(target_dir),
        )
    except Exception as exc:  # noqa: BLE001 - reportable but non-fatal
        raise RuntimeError(
            f"Failed to download vision model {HUB_REPO}: {exc}"
        ) from exc

    return str(local)
