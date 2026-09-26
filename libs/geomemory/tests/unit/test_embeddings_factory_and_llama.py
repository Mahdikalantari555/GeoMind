"""Unit tests for embeddings factory and llama_cpp text/vision embedders."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from geomemory.core.exceptions import ModelNotLoadedError
from geomemory.core.models import WorkspaceSettings
from geomemory.embeddings.factory import (
    _vision_path_from_settings,
    build_text_embedder,
    build_vision_embedder,
)
from geomemory.embeddings.hashing_text import HashingTextEmbedder
from geomemory.embeddings.llama_cpp_text import LlamaCppTextEmbedder
from geomemory.embeddings.llama_cpp_vision import LlamaCppVisionEmbedder, _encode_image
from geomemory.embeddings.provider import (
    CloudflareEmbeddingProvider,
    CustomEmbeddingProvider,
    ONNXEmbeddingProvider,
    OpenAIEmbeddingProvider,
    VoyageEmbeddingProvider,
)
from geomemory.embeddings.vision_embedder import PlaceholderVisionEmbedder


def test_vision_path_from_settings(tmp_path: Path) -> None:
    # None settings
    s_none = WorkspaceSettings(name="test")
    with patch("geomemory.embeddings.vision_downloader._find_cached_weights", return_value=None):
        assert _vision_path_from_settings(s_none) is None

    # File path
    f = tmp_path / "model.pth"
    f.write_bytes(b"test")
    s_file = WorkspaceSettings(name="test", vision_path=str(f))
    assert _vision_path_from_settings(s_file) == str(f)

    # Directory with weights.pth
    d = tmp_path / "model_dir"
    d.mkdir()
    (d / "weights.pth").write_bytes(b"weights")
    s_dir = WorkspaceSettings(name="test", vision_path=str(d))
    assert _vision_path_from_settings(s_dir) == str(d)

    # Cached weights fallback
    with patch("geomemory.embeddings.vision_downloader._find_cached_weights", return_value=f):
        assert _vision_path_from_settings(s_none) == str(f)


def test_build_text_embedder_providers() -> None:
    # ONNX default
    s_onnx = WorkspaceSettings(name="test", embedding_provider="onnx", onnx_model_name="Xenova/all-MiniLM-L6-v2")
    emb = build_text_embedder(s_onnx)
    assert isinstance(emb, ONNXEmbeddingProvider)

    # Legacy sentence-transformers warning
    s_legacy_st = WorkspaceSettings.model_construct(
        name="test",
        embedding_provider="onnx",
        embedding_backend="sentence-transformers",
        onnx_model_name="sentence-transformers/all-MiniLM-L6-v2",
    )
    with pytest.deprecated_call():
        emb_st = build_text_embedder(s_legacy_st)
        assert isinstance(emb_st, ONNXEmbeddingProvider)

    # Hashing
    s_hash = WorkspaceSettings(name="test", embedding_provider="hashing")
    assert isinstance(build_text_embedder(s_hash), HashingTextEmbedder)

    # Legacy backend = hashing
    s_leg_hash = WorkspaceSettings.model_construct(
        name="test",
        embedding_provider=None,
        embedding_backend="hashing",
    )
    assert isinstance(build_text_embedder(s_leg_hash), HashingTextEmbedder)

    # Legacy backend = llama-cpp without path falls back to hashing
    s_leg_llama = WorkspaceSettings.model_construct(
        name="test",
        embedding_provider=None,
        embedding_backend="llama-cpp",
    )
    assert isinstance(build_text_embedder(s_leg_llama), HashingTextEmbedder)

    # Legacy backend = llama-cpp with path
    s_leg_llama_path = WorkspaceSettings.model_construct(
        name="test",
        embedding_provider=None,
        embedding_backend="llama-cpp",
        model_path="/fake/path.gguf",
    )
    emb_llama = build_text_embedder(s_leg_llama_path)
    assert isinstance(emb_llama, LlamaCppTextEmbedder)

    # OpenAI
    s_oai = WorkspaceSettings(name="test", embedding_provider="openai")
    assert isinstance(build_text_embedder(s_oai), OpenAIEmbeddingProvider)

    # Voyage
    s_voy = WorkspaceSettings(name="test", embedding_provider="voyage")
    assert isinstance(build_text_embedder(s_voy), VoyageEmbeddingProvider)

    # Custom
    s_cust = WorkspaceSettings(name="test", embedding_provider="custom")
    assert isinstance(build_text_embedder(s_cust), CustomEmbeddingProvider)

    # Cloudflare
    s_cf = WorkspaceSettings(
        name="test",
        embedding_provider="cloudflare",
        cloudflare_account_id="acc123",
        cloudflare_api_token="tok123",
    )
    assert isinstance(build_text_embedder(s_cf), CloudflareEmbeddingProvider)


def test_build_vision_embedder(tmp_path: Path) -> None:
    # offline and no path -> placeholder
    s_off = WorkspaceSettings(name="test", offline=True, vision_path=None)
    with patch("geomemory.embeddings.vision_downloader._find_cached_weights", return_value=None):
        v_off = build_vision_embedder(s_off)
        assert isinstance(v_off, PlaceholderVisionEmbedder)

    # online but download returns None -> placeholder
    s_on = WorkspaceSettings(name="test", offline=False, vision_path=None)
    with (
        patch("geomemory.embeddings.vision_downloader._find_cached_weights", return_value=None),
        patch("geomemory.embeddings.vision_downloader.download_vision_model", return_value=None),
    ):
        v_on = build_vision_embedder(s_on)
        assert isinstance(v_on, PlaceholderVisionEmbedder)

    # online and download succeeds -> OlmoEarthVisionEmbedder
    mock_file = tmp_path / "model.pth"
    mock_file.write_bytes(b"data")
    with (
        patch("geomemory.embeddings.vision_downloader._find_cached_weights", return_value=None),
        patch("geomemory.embeddings.vision_downloader.download_vision_model", return_value=str(mock_file)),
        patch("geomemory.embeddings.olmoearth_vision.OlmoEarthVisionEmbedder") as mock_olmo,
    ):
        build_vision_embedder(s_on)
        mock_olmo.assert_called_once_with(str(mock_file))


def test_llama_cpp_text_embedder() -> None:
    embedder = LlamaCppTextEmbedder("fake.gguf")
    assert embedder.model_id == "nomic-embed-text-v2-moe"

    mock_llama = MagicMock()
    mock_llama.create_embedding.return_value = {
        "data": [{"embedding": [0.1, 0.2, 0.3, 0.4]}]
    }

    with patch.dict(sys.modules, {"llama_cpp": MagicMock(Llama=MagicMock(return_value=mock_llama))}):
        vecs = embedder.embed(["hello", "world"])
        assert vecs.shape == (2, 4)
        assert np.isclose(np.linalg.norm(vecs[0]), 1.0)

        # embed_batch
        vecs_batch = embedder.embed_batch(["a", "b", "c"], batch_size=2)
        assert vecs_batch.shape == (3, 4)

        # empty embed_batch
        assert embedder.embed_batch([], batch_size=2).shape == (0, 0)


def test_llama_cpp_vision_embedder(tmp_path: Path) -> None:
    # unset model_path
    emb_empty = LlamaCppVisionEmbedder("")
    with pytest.raises(ModelNotLoadedError, match="Vision model path is not configured"):
        emb_empty.embed_images(["test.jpg"])

    emb = LlamaCppVisionEmbedder("fake.gguf")
    assert emb.model_id == "olmoearth-nano"
    assert emb.embed_texts(["hello"]) is None

    # _encode_image
    img_file = tmp_path / "img.png"
    img_file.write_bytes(b"png")
    assert _encode_image(img_file) == str(img_file)
    assert _encode_image(b"bytes") == b"bytes"
    with pytest.raises(TypeError, match="image must be a path, bytes"):
        _encode_image(12345)

    # embed_images
    mock_llama = MagicMock()
    mock_llama.create_embedding.return_value = {
        "data": [{"embedding": [0.5, 0.5, 0.5, 0.5]}]
    }

    with patch.dict(sys.modules, {"llama_cpp": MagicMock(Llama=MagicMock(return_value=mock_llama))}):
        vecs = emb.embed_images([b"dummy_bytes"])
        assert vecs.shape == (1, 4)
        assert np.isclose(np.linalg.norm(vecs[0]), 1.0)
