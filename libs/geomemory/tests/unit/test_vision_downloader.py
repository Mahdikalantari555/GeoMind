"""Test vision model downloader module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from geomemory.embeddings.vision_downloader import (
    HUB_REPO,
    download_vision_model,
)


class TestDownloadVisionModel:
    def test_offline_returns_none(self):
        """When offline=true, no network is attempted."""
        settings = type("S", (), {"offline": True})()
        result = download_vision_model(settings)  # type: ignore[arg-type]
        assert result is None

    def test_existing_cached_weights_are_reused(self, tmp_path, monkeypatch):
        """When HF cache already holds a snapshot with weights.pth, reuse it."""
        settings = type("S", (), {"offline": False})()
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        cache = tmp_path / ".cache" / "huggingface" / "hub"
        snapshot = cache / "models--allenai--OlmoEarth-v1_2-Nano" / "snapshots" / "abc123"
        snapshot.mkdir(parents=True)
        (snapshot / "weights.pth").touch()

        with patch("huggingface_hub.snapshot_download") as dl:
            result = download_vision_model(settings)  # type: ignore[arg-type]
            assert result == str(snapshot)
            dl.assert_not_called()

    def test_missing_weights_trigger_download(self, tmp_path, monkeypatch):
        """Without cached weights, download is attempted and path returned."""
        settings = type("S", (), {"offline": False})()
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        downloaded = tmp_path / "models" / "vision" / "snapshots" / "abc123"
        with patch(
            "huggingface_hub.snapshot_download",
            return_value=str(downloaded),
        ):
            result = download_vision_model(settings)  # type: ignore[arg-type]
            assert result == str(downloaded)

    def test_download_failure_raises_runtime_error(self, tmp_path, monkeypatch):
        """Download failures are surfaced as RuntimeError."""
        settings = type("S", (), {"offline": False})()
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with patch(
            "huggingface_hub.snapshot_download",
            side_effect=Exception("network down"),
        ):
            with pytest.raises(RuntimeError, match="Failed to download vision model"):
                download_vision_model(settings)  # type: ignore[arg-type]
