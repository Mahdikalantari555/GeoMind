"""Tests for the OLMoEarth v1.2 Nano torch-native vision embedder.

These tests use the real OLMoEarth model loader when available.
They skip gracefully if torch, an OLMoEarth loader package, or a real
checkpoint is not present, so the core package stays installable without
heavy deps.

The loader can be either the full ``olmoearth_pretrain`` package or the
lightweight ``olmoearth_pretrain_minimal`` package (encoder-only, no
training stack).  The minimal package is preferred — it avoids pulling in
a 900 MB+ CUDA torch while still loading the v1.2 Nano encoder.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest


# Resolve a real OLMoEarth v1.2 Nano checkpoint: env var first, then HF cache.
def _resolve_vision_path() -> str | None:
    path = os.environ.get("GEOMEMORY_TEST_VISION_PATH")
    if path:
        return str(Path(path).resolve())
    from geomemory.embeddings.vision_downloader import _find_cached_weights
    cached = _find_cached_weights()
    return str(cached) if cached is not None else None


VISION_PATH = _resolve_vision_path()

torch_available = False
olmoearth_available = False
try:
    import torch  # noqa: F401

    torch_available = True
    # Accept either the full package or the lightweight minimal package.
    try:
        import olmoearth_pretrain  # noqa: F401
    except ImportError:
        import olmoearth_pretrain_minimal  # noqa: F401

    olmoearth_available = True
except ImportError:
    pass

needs_vision = pytest.mark.skipif(
    not (torch_available and olmoearth_available and VISION_PATH),
    reason="requires [vision] extra and GEOMEMORY_TEST_VISION_PATH",
)


@pytest.fixture
def embedder():
    from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

    return OlmoEarthVisionEmbedder(VISION_PATH)


class TestContractWithoutModel:
    """Contract checks that do not require a real checkpoint."""

    def test_space_id_prefix(self) -> None:
        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        assert OlmoEarthVisionEmbedder("dummy").space_id == "image.olmoearth-nano-v12.v1"
        assert OlmoEarthVisionEmbedder("dummy").space_id.startswith("image.")

    def test_embed_texts_returns_none(self) -> None:
        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        assert OlmoEarthVisionEmbedder("dummy").embed_texts(["hello"]) is None

    def test_missing_checkpoint_error_names_path(self, tmp_path: Path) -> None:
        from geomemory.core.exceptions import ModelNotLoadedError
        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        missing = tmp_path / "nonexistent.pth"
        emb = OlmoEarthVisionEmbedder(str(missing))
        with pytest.raises(ModelNotLoadedError) as exc_info:
            emb._load()
        assert str(missing) in str(exc_info.value)

    def test_model_id_and_modality_tensor_types(self, tmp_path: Path) -> None:
        import io

        from PIL import Image

        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        emb = OlmoEarthVisionEmbedder("dummy", model_id="custom-nano")
        assert emb.model_id == "custom-nano"

        # 1. Bytes input
        img = Image.new("RGB", (64, 64), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        arr_bytes = emb._to_modality_tensor(buf.getvalue())
        assert arr_bytes.shape == (64, 64, 3)

        # 2. 2D array (single channel)
        arr_2d = np.ones((50, 50), dtype=np.float32) * 100.0
        res_2d = emb._to_modality_tensor(arr_2d)
        assert res_2d.shape == (50, 50, 3)
        assert np.allclose(res_2d, 0.0)  # hi - lo == 0 branch

        # 3. 3D array with max > 1.0
        arr_3d = np.ones((10, 10, 3), dtype=np.float32) * 200.0
        res_3d = emb._to_modality_tensor(arr_3d)
        assert res_3d.shape == (10, 10, 3)

        # 4. Large image resizing (> 128)
        large_img = Image.new("RGB", (256, 128), color="red")
        res_large = emb._to_modality_tensor(large_img)
        assert res_large.shape == (128, 128, 3)

        # 5. Unsupported type raises TypeError
        with pytest.raises(TypeError, match="Unsupported image type"):
            emb._to_modality_tensor(12345)

    def test_load_fallback_and_errors(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock, patch

        from geomemory.core.exceptions import ModelNotLoadedError
        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        # Directory without weights.pth
        model_dir = tmp_path / "model_dir"
        model_dir.mkdir()
        emb = OlmoEarthVisionEmbedder(str(model_dir))

        # 1. Missing vision extra raises ModelNotLoadedError
        with (
            patch.dict("sys.modules", {"olmoearth_pretrain_minimal": None, "olmoearth_pretrain": None, "olmoearth_pretrain.config": None}),
            pytest.raises(ModelNotLoadedError, match="The 'vision' extra is required"),
        ):
            emb._load()

        # 2. Mock full olmoearth_pretrain installed
        mock_pretrain = MagicMock()
        mock_config_mod = MagicMock()
        mock_pretrain.config = mock_config_mod
        with patch.dict("sys.modules", {
            "olmoearth_pretrain_minimal": None,
            "olmoearth_pretrain": mock_pretrain,
            "olmoearth_pretrain.config": mock_config_mod,
        }):
            with pytest.raises(ModelNotLoadedError, match="weights not found"):
                emb._load()

            # Create dummy weights
            weights = model_dir / "weights.pth"
            weights.write_bytes(b"dummy weights")

            # Config download failure
            with (
                patch("huggingface_hub.hf_hub_download", side_effect=RuntimeError("Network down")),
                pytest.raises(ModelNotLoadedError, match="could not be downloaded"),
            ):
                emb._load()

            # Create config.json
            config_file = model_dir / "config.json"
            config_file.write_text('{"model": {}}')
            mock_config_mod.Config.from_dict.side_effect = ValueError("Invalid architecture")
            with pytest.raises(ModelNotLoadedError, match="Failed to load vision model"):
                emb._load()

    def test_embed_images_multichannel(self) -> None:
        from unittest.mock import MagicMock, patch

        import torch

        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        emb = OlmoEarthVisionEmbedder("dummy")
        mock_model = MagicMock()
        out_dict = {"project_aggregated": torch.ones((1, 128), dtype=torch.float32)}
        mock_model.encoder.return_value = out_dict
        emb._model = mock_model

        with patch.object(emb, "_to_modality_tensor", return_value=np.ones((64, 64, 16), dtype=np.float32)):
            vecs = emb.embed_images(["dummy_input"])
            assert vecs.shape == (1, 128)
            assert np.isclose(np.linalg.norm(vecs[0]), 1.0)


class TestRealCheckpoint:
    """Behavioural tests against a real OLMoEarth Nano checkpoint."""

    @needs_vision
    def test_load_dim(self, embedder) -> None:
        model = embedder._load()
        assert model is not None

    @needs_vision
    def test_embed_shape_dtype_l2norm(self, embedder) -> None:
        images = [np.random.RandomState(i).rand(32, 32, 3).astype(np.float32) for i in range(3)]
        result = embedder.embed_images(images)
        assert result.shape == (3, 128)
        assert result.dtype == np.float32
        norms = np.linalg.norm(result, axis=1)
        assert np.allclose(norms, 1.0, atol=1e-5)

    @needs_vision
    def test_embed_empty_list(self, embedder) -> None:
        result = embedder.embed_images([])
        assert result.shape == (0, 128)

    @needs_vision
    def test_semantic_similarity_ordering(self, embedder) -> None:
        """Near-duplicate inputs should be more similar than random inputs."""
        rng = np.random.RandomState(0)
        base = rng.rand(64, 64, 3).astype(np.float32)
        noisy = np.clip(base + rng.rand(64, 64, 3).astype(np.float32) * 0.02, 0, 1)
        other = rng.rand(64, 64, 3).astype(np.float32)

        e_base = embedder.embed_images([base])[0]
        e_noisy = embedder.embed_images([noisy])[0]
        e_other = embedder.embed_images([other])[0]

        def _cos(a, b):
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

        assert _cos(e_base, e_noisy) > _cos(e_base, e_other)

    @needs_vision
    def test_pil_and_path_inputs(self, embedder, tmp_path: Path) -> None:
        from PIL import Image

        arr = np.random.RandomState(1).rand(48, 48, 3).astype(np.float32)
        img = Image.fromarray((arr * 255).astype(np.uint8))
        p = tmp_path / "img.png"
        img.save(p)

        r_path = embedder.embed_images([str(p)])[0]
        r_pil = embedder.embed_images([img])[0]
        cos = float(np.dot(r_path, r_pil) / (np.linalg.norm(r_path) * np.linalg.norm(r_pil)))
        assert cos > 0.99  # same image -> same embedding
