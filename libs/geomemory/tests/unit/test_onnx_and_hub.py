"""Unit tests for OnnxTextEmbedder and EmbeddingModelHub."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from geomemory.core.exceptions import EmbeddingUnavailableError
from geomemory.embeddings.hub import (
    EmbeddingModelHub,
    _classify_dir,
    _dir_size,
    _hub_cache_dir_for,
    onnx_repo_for,
)
from geomemory.embeddings.hub import (
    _safe_name as hub_safe_name,
)
from geomemory.embeddings.onnx_text import (
    OnnxTextEmbedder,
    _model_family,
)
from geomemory.embeddings.onnx_text import (
    _safe_name as onnx_safe_name,
)


def test_onnx_helpers_and_properties(tmp_path: Path) -> None:
    assert _model_family("intfloat/multilingual-e5-base") == "e5"
    assert _model_family("BAAI/bge-m3") == "bge"
    assert _model_family("sentence-transformers/all-MiniLM-L6-v2") == "generic"

    embedder = OnnxTextEmbedder(
        "intfloat/e5-small-v2",
        model_id="custom-e5",
        model_dir=tmp_path / "model",
        offline=True,
    )
    assert embedder.model_id == "custom-e5"
    assert embedder.space_id == f"text.onnx.{onnx_safe_name('intfloat/e5-small-v2')}.v1"
    assert embedder._resolve_dir() == tmp_path / "model"

    # Offline error when files missing
    with pytest.raises(EmbeddingUnavailableError, match="not cached locally"):
        embedder._ensure_downloaded(tmp_path / "nonexistent")

    # Success when model files exist
    model_dir = tmp_path / "cached_model"
    model_dir.mkdir(parents=True)
    (model_dir / "model.onnx").write_bytes(b"dummy onnx")
    (model_dir / "tokenizer.json").write_text("{}")
    assert embedder._ensure_downloaded(model_dir) == model_dir

    # Text prefixing
    assert embedder._apply_prefix(["query text"], query=True) == ["query: query text"]
    assert embedder._apply_prefix(["chunk text"], query=False) == ["passage: chunk text"]


def test_onnx_inference_mocked(tmp_path: Path) -> None:
    embedder = OnnxTextEmbedder("test-model", model_dir=tmp_path)

    # Mock tokenizer and ort session
    mock_tok = MagicMock()
    mock_encoding = MagicMock()
    mock_encoding.ids = [1, 2, 3]
    mock_encoding.attention_mask = [1, 1, 1]
    mock_tok.encode_batch.return_value = [mock_encoding]

    mock_session = MagicMock()
    # Mock session output: shape (1, 3, 4)
    hidden_states = np.ones((1, 3, 4), dtype=np.float32)
    mock_session.run.return_value = [hidden_states]

    input_meta = MagicMock()
    input_meta.name = "input_ids"
    mock_session.get_inputs.return_value = [input_meta]

    with patch.object(embedder, "_load", return_value=(mock_session, mock_tok)):
        q_vecs = embedder.embed_query(["search query"])
        assert q_vecs.shape == (1, 4)
        assert pytest.approx(float(np.linalg.norm(q_vecs[0])), 0.01) == 1.0

        c_vecs = embedder.embed(["passage chunk"])
        assert c_vecs.shape == (1, 4)

        b_vecs = embedder.embed_batch(["text 1", "text 2"], batch_size=1)
        assert b_vecs.shape == (2, 4)

        empty_vecs = embedder.embed_batch([], batch_size=1)
        assert empty_vecs.shape == (0, 0)

        # Download with progress hook
        with patch("geomemory.embeddings.hub.EmbeddingModelHub.download", return_value="/tmp/test"):
            p_res = embedder.download_with_progress(on_progress=lambda _: None)
            assert p_res == "/tmp/test"


def test_onnx_resolve_dir_and_load_errors(tmp_path: Path) -> None:
    # 1. Resolve dir without explicit dir uses hub/fallback
    embedder_auto = OnnxTextEmbedder("custom/model")
    res_dir = embedder_auto._resolve_dir()
    assert res_dir is not None

    # 2. _load with missing dependencies raises ImportError
    with (
        patch.dict("sys.modules", {"onnxruntime": None, "tokenizers": None}),
        pytest.raises(ImportError, match="requires the optional `onnxruntime`"),
    ):
        embedder_auto._load()

    # 3. _ensure_downloaded with missing huggingface-hub raises ImportError
    model_dir = tmp_path / "empty_model"
    model_dir.mkdir()
    emb_dl = OnnxTextEmbedder("missing-hub-model", model_dir=model_dir)
    with (
        patch("geomemory.embeddings.hub.EmbeddingModelHub.download", side_effect=ImportError("HF missing")),
        pytest.raises(ImportError, match="requires the optional `onnxruntime`"),
    ):
        emb_dl._ensure_downloaded(model_dir)

    # 4. Incomplete model directory (no onnx file) raises EmbeddingUnavailableError
    (model_dir / "tokenizer.json").write_text("{}")
    with (
        patch.object(emb_dl, "_ensure_downloaded", return_value=model_dir),
        patch("onnxruntime.InferenceSession", MagicMock()),
        patch("tokenizers.Tokenizer.from_file", MagicMock()),
        pytest.raises(EmbeddingUnavailableError, match="is incomplete"),
    ):
        emb_dl._load()

    # 5. Token type IDs in session inputs
    (model_dir / "model.onnx").write_bytes(b"dummy")
    mock_session = MagicMock()
    inp_ids = MagicMock()
    inp_ids.name = "input_ids"
    inp_tok = MagicMock()
    inp_tok.name = "token_type_ids"
    mock_session.get_inputs.return_value = [inp_ids, inp_tok]
    mock_session.run.return_value = [np.ones((1, 3, 4), dtype=np.float32)]

    mock_tok = MagicMock()
    mock_enc = MagicMock()
    mock_enc.ids = [1, 2, 3]
    mock_enc.attention_mask = [1, 1, 1]
    mock_tok.encode_batch.return_value = [mock_enc]

    emb_complete = OnnxTextEmbedder("bge-model", model_dir=model_dir)
    with patch("onnxruntime.InferenceSession", return_value=mock_session), patch("tokenizers.Tokenizer.from_file", return_value=mock_tok):
        vec = emb_complete.embed(["test passage"])
        assert vec.shape == (1, 4)


def test_embedding_model_hub_classification_and_scan(tmp_path: Path) -> None:
    assert onnx_repo_for("sentence-transformers/all-MiniLM-L6-v2") == "Xenova/all-MiniLM-L6-v2"
    assert onnx_repo_for("Xenova/bge-small-en-v1.5") == "Xenova/bge-small-en-v1.5"
    assert onnx_repo_for("custom/foo") == "Xenova/foo"
    assert onnx_repo_for("simple_name") == "simple_name"
    assert hub_safe_name("a/b.c") == "a-b-c"

    # Classification: ONNX at root
    onnx_root = tmp_path / "onnx_root"
    onnx_root.mkdir()
    (onnx_root / "model.onnx").write_bytes(b"dummy")
    assert _classify_dir(onnx_root) == "onnx"

    # Classification: ONNX in onnx/ subdir
    onnx_sub = tmp_path / "onnx_sub"
    (onnx_sub / "onnx").mkdir(parents=True)
    (onnx_sub / "onnx" / "model_quantized.onnx").write_bytes(b"dummy")
    assert _classify_dir(onnx_sub) == "onnx"

    # Classification: sentence-transformers requires weights
    st_dir = tmp_path / "st_dir"
    st_dir.mkdir()
    (st_dir / "tokenizer.json").write_text("{}")
    (st_dir / "config.json").write_text("{}")
    # Tokenizer-only directory without weights is not classified as an ST model
    assert _classify_dir(st_dir) is None

    # Adding model.safetensors makes it loadable
    (st_dir / "model.safetensors").write_bytes(b"dummy")
    assert _classify_dir(st_dir) == "st"

    # Vision models (e.g. OlmoEarth) are excluded
    olmo_dir = tmp_path / "olmoearth-nano-checkpoint"
    olmo_dir.mkdir()
    (olmo_dir / "config.json").write_text('{"model_type": "olmoearth"}')
    (olmo_dir / "model.safetensors").write_bytes(b"dummy")
    assert _classify_dir(olmo_dir) is None

    # Classification: empty/unknown
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert _classify_dir(empty_dir) is None

    # _dir_size
    assert _dir_size(onnx_root) > 0

    # Hub scan (pass tmp_path as embedding_path so it scans children)
    hub = EmbeddingModelHub(
        workspace_dir=tmp_path / "ws",
        embedding_path=tmp_path,
    )
    models = hub.scan()
    assert isinstance(models, list)
    assert len(models) >= 1

    # find_model
    found = hub.find_model("onnx_root", backend="onnx")
    assert found is not None
    assert found["backend"] == "onnx"

    # find_model missing
    assert hub.find_model("nonexistent_model") is None

    # Summary
    summary = hub.summary(active_backend="onnx", active_model="sentence-transformers/all-MiniLM-L6-v2")
    assert summary["hub_count"] >= 1
    assert summary["downloaded"] >= 1
    assert summary["active_backend"] == "onnx"
    assert "text.onnx.sentence-transformers-all-MiniLM-L6-v2.v1" in summary["active_space_id"]

    cf_summary = hub.summary(active_backend="cloudflare", active_model="@cf/baai/bge-base-en-v1.5")
    assert cf_summary["active_space_id"] == "text.cloudflare.cf-baai-bge-base-en-v1-5.v1"

    st_summary = hub.summary(active_backend="st", active_model="BAAI/bge-small-en-v1.5")
    assert "text.st.BAAI-bge-small-en-v1-5.v1" in st_summary["active_space_id"]


def test_embedding_model_hub_roots_and_extra(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Test _hub_cache_dir_for
    cache_dir = _hub_cache_dir_for("org/test-model")
    assert "models--org--test-model" in str(cache_dir)

    monkeypatch.setenv("GEOMEMORY_EMBEDDING_ROOT", str(tmp_path / "env_root"))
    extra = tmp_path / "extra"
    ws = tmp_path / "workspace"
    hub = EmbeddingModelHub(
        extra_roots=[extra],
        workspace_dir=ws,
        embedding_path=tmp_path / "emb",
    )
    roots = hub.roots()
    assert (tmp_path / "env_root") in roots
    assert extra in roots
    assert (tmp_path / "emb") in roots
    assert (ws / "models") in roots
    assert (ws / "indexes") in roots

    # Test _classify_dir with vision config exclusion
    vision_dir = tmp_path / "vision_model"
    vision_dir.mkdir()
    (vision_dir / "config.json").write_text('{"architectures": ["VisionTransformer"], "vision_config": {}}')
    assert _classify_dir(vision_dir) is None

    # Test _classify_dir with pytorch_model.bin
    pt_dir = tmp_path / "pt_model"
    pt_dir.mkdir()
    (pt_dir / "pytorch_model.bin").write_bytes(b"dummy")
    assert _classify_dir(pt_dir) == "st"


def test_embedding_model_hub_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hub = EmbeddingModelHub(workspace_dir=tmp_path)

    # 1. Existing model returns path immediately
    model_dir = tmp_path / "models" / "cached_onnx"
    model_dir.mkdir(parents=True)
    (model_dir / "model.onnx").write_bytes(b"dummy")

    called_progress: list[float] = []
    path = hub.download("cached_onnx", backend="onnx", on_progress=called_progress.append)
    assert path == str(model_dir)
    assert called_progress == [1.0]

    # 2. Offline raises EmbeddingUnavailableError
    with pytest.raises(EmbeddingUnavailableError, match="not cached locally"):
        hub.download("missing_model", offline=True)

    monkeypatch.setenv("GEOMEMORY_OFFLINE", "1")
    with pytest.raises(EmbeddingUnavailableError):
        hub.download("missing_model", offline=False)
    monkeypatch.delenv("GEOMEMORY_OFFLINE", raising=False)

    # 3. Missing huggingface_hub raises ImportError
    with (
        patch.dict("sys.modules", {"huggingface_hub": None}),
        pytest.raises(ImportError, match="requires the optional `huggingface-hub`"),
    ):
        hub.download("new_model")

    # 4. Successful mocked download
    dl_dir = tmp_path / "downloaded_model"
    dl_dir.mkdir(parents=True, exist_ok=True)
    (dl_dir / "model.onnx").write_bytes(b"dummy onnx")

    mock_hf = MagicMock()
    mock_download = MagicMock(return_value=str(dl_dir))
    mock_hf.snapshot_download = mock_download
    with patch.dict("sys.modules", {"huggingface_hub": mock_hf}):
        prog: list[float] = []
        res = hub.download(
            "mock-org/mock-onnx-model",
            backend="onnx",
            on_progress=prog.append,
        )
        assert res == str(dl_dir)
        assert prog == [1.0]
        assert mock_download.called

    # 5. Download missing weights raises EmbeddingUnavailableError
    dl_empty = tmp_path / "empty_dl"
    dl_empty.mkdir(parents=True, exist_ok=True)
    mock_hf.snapshot_download = MagicMock(return_value=str(dl_empty))
    with patch.dict("sys.modules", {"huggingface_hub": mock_hf}):
        with pytest.raises(EmbeddingUnavailableError, match="did not contain valid onnx weights"):
            hub.download("missing_weights_model", backend="onnx")
