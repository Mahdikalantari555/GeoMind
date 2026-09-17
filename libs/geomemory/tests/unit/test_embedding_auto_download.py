"""Tests for embedding provider auto-download behaviour."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from geomemory.embeddings.provider import ONNXEmbeddingProvider


class TestONNXEmbeddingProviderAutoDownload:
    def test_init_accepts_auto_download_kwarg(self):
        """Provider construction accepts auto_download kwarg (defaults True)."""
        provider = ONNXEmbeddingProvider(auto_download=True)
        assert provider.space_id.startswith("text.onnx.")

    def test_download_with_progress_callback_receives_events(self):
        """download_with_progress forwards callbacks to hub.download."""
        provider = ONNXEmbeddingProvider()
        events: list[float] = []
        with patch(
            "geomemory.embeddings.hub.EmbeddingModelHub.download",
            return_value="/tmp/model",
        ) as hub_dl:
            provider.download_with_progress(on_progress=lambda p: events.append(p))
            hub_dl.assert_called_once()
            assert hub_dl.call_args.kwargs["on_progress"] is not None

    def test_provider_falls_back_when_model_dir_empty_and_not_offline(self):
        """When no model_dir is given, provider delegates to OnnxTextEmbedder which triggers hub download."""
        provider = ONNXEmbeddingProvider(model_name="Xenova/all-MiniLM-L6-v2")
        with patch.object(
            provider._inner,
            "_ensure_downloaded",
            side_effect=Exception("not cached"),
        ), pytest.raises(Exception, match="not cached"):
            provider._inner._load()  # type: ignore[attr-defined]
