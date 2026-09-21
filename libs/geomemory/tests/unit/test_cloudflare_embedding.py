"""Unit tests for Cloudflare Workers AI text embedding provider."""

from __future__ import annotations

import json
import urllib.error
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from geomemory.core.config import load_settings, save_settings
from geomemory.core.exceptions import EmbeddingUnavailableError
from geomemory.core.models import WorkspaceSettings
from geomemory.embeddings.factory import build_text_embedder
from geomemory.embeddings.provider import CloudflareEmbeddingProvider
from geomemory.services.doctor import doctor_embedding


def _make_mock_response(status: int = 200, data: Any = None) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.code = status
    body_bytes = json.dumps(data).encode("utf-8") if data is not None else b""
    resp.read.return_value = body_bytes
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = None
    return resp


class TestCloudflareEmbeddingProvider:
    def test_space_id_naming_and_dimension(self) -> None:
        p1 = CloudflareEmbeddingProvider("@cf/baai/bge-base-en-v1.5")
        assert p1.space_id == "text.cloudflare.cf-baai-bge-base-en-v1-5.v1"
        assert p1.model_id == "@cf/baai/bge-base-en-v1.5"
        assert p1.dimension == 768

        p2 = CloudflareEmbeddingProvider("@cf/baai/bge-small-en-v1.5")
        assert p2.space_id == "text.cloudflare.cf-baai-bge-small-en-v1-5.v1"
        assert p2.dimension == 384

        p3 = CloudflareEmbeddingProvider("baai/bge-large-en-v1.5")
        assert p3.space_id == "text.cloudflare.baai-bge-large-en-v1-5.v1"
        assert p3.dimension == 1024

    def test_bearer_auth_header_and_request_construction(self) -> None:
        provider = CloudflareEmbeddingProvider(
            "@cf/baai/bge-base-en-v1.5",
            account_id="test-account-id",
            api_token="test-api-token",
        )
        mock_resp_data = {
            "result": {
                "shape": [1, 768],
                "data": [[1.0] * 768],
            },
            "success": True,
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _make_mock_response(200, mock_resp_data)
            out = provider.embed(["sample remote sensing query"])

            assert mock_urlopen.call_count == 1
            req = mock_urlopen.call_args[0][0]
            assert (
                req.full_url
                == "https://api.cloudflare.com/client/v4/accounts/test-account-id/ai/run/@cf/baai/bge-base-en-v1.5"
            )
            assert req.headers["Authorization"] == "Bearer test-api-token"
            assert req.headers["Content-type"] == "application/json"

            body = json.loads(req.data.decode("utf-8"))
            assert body == {"text": ["sample remote sensing query"]}

            assert out.shape == (1, 768)
            assert out.dtype == np.float32
            # L2 normalized
            assert np.isclose(np.linalg.norm(out[0]), 1.0, atol=1e-5)

    def test_embed_l2_normalization(self) -> None:
        provider = CloudflareEmbeddingProvider(
            account_id="acc",
            api_token="tok",
        )
        # 3-4-5 triangle: norm of [3, 4] is 5, normalized is [0.6, 0.8]
        mock_resp_data = {
            "result": {
                "data": [[3.0, 4.0], [0.0, 5.0]],
            },
            "success": True,
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _make_mock_response(200, mock_resp_data)
            out = provider.embed(["text1", "text2"])
            assert out.shape == (2, 2)
            assert np.allclose(out[0], [0.6, 0.8], atol=1e-5)
            assert np.allclose(out[1], [0.0, 1.0], atol=1e-5)
            assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-5)

    def test_embed_query_delegates(self) -> None:
        provider = CloudflareEmbeddingProvider(
            account_id="acc",
            api_token="tok",
        )
        mock_resp = {"result": {"data": [[1.0, 0.0]]}, "success": True}
        with patch("urllib.request.urlopen", return_value=_make_mock_response(200, mock_resp)):
            q = provider.embed_query(["query"])
            assert q.shape == (1, 2)

    def test_batch_chunking(self) -> None:
        provider = CloudflareEmbeddingProvider(
            account_id="acc",
            api_token="tok",
        )
        texts = [f"sentence_{i}" for i in range(5)]

        def side_effect(req: Any, **_kwargs: Any) -> MagicMock:
            body = json.loads(req.data.decode("utf-8"))
            n = len(body["text"])
            # Return n dummy vectors
            return _make_mock_response(
                200,
                {"result": {"data": [[float(i + 1)] * 4 for i in range(n)]}, "success": True},
            )

        with patch("urllib.request.urlopen", side_effect=side_effect) as mock_urlopen:
            vecs = provider.embed_batch(texts, batch_size=2)
            # 5 texts split into chunks of 2, 2, 1 -> 3 requests
            assert mock_urlopen.call_count == 3
            assert vecs.shape == (5, 4)

    def test_empty_input(self) -> None:
        provider = CloudflareEmbeddingProvider(
            account_id="acc",
            api_token="tok",
        )
        assert provider.embed([]).shape == (0, 768)
        assert provider.embed_batch([], batch_size=2).shape == (0, 768)

    def test_offline_refusal(self) -> None:
        provider = CloudflareEmbeddingProvider(
            account_id="acc",
            api_token="tok",
            offline=True,
        )
        with pytest.raises(EmbeddingUnavailableError, match="requires network access"):
            provider.embed(["test"])

        with pytest.raises(EmbeddingUnavailableError, match="requires network access"):
            provider.embed_query(["test"])

    def test_missing_credentials_refusal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
        monkeypatch.delenv("GEOMEMORY_CLOUDFLARE_ACCOUNT_ID", raising=False)
        monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
        monkeypatch.delenv("GEOMEMORY_CLOUDFLARE_API_TOKEN", raising=False)

        provider = CloudflareEmbeddingProvider(account_id="", api_token="")
        with pytest.raises(EmbeddingUnavailableError, match="requires cloudflare_account_id"):
            provider.embed(["test"])

    def test_http_401_auth_error(self) -> None:
        provider = CloudflareEmbeddingProvider(account_id="acc", api_token="bad_tok")
        http_err = urllib.error.HTTPError(
            url="http://api.cloudflare.com",
            code=401,
            msg="Unauthorized",
            hdrs=None,  # type: ignore[arg-type]
            fp=MagicMock(read=lambda: b'{"errors": ["Invalid token"]}'),
        )
        with (
            patch("urllib.request.urlopen", side_effect=http_err),
            pytest.raises(EmbeddingUnavailableError, match="authentication failed"),
        ):
            provider.embed(["test"])

    def test_http_429_rate_limit_error(self) -> None:
        provider = CloudflareEmbeddingProvider(account_id="acc", api_token="tok")
        http_err = urllib.error.HTTPError(
            url="http://api.cloudflare.com",
            code=429,
            msg="Too Many Requests",
            hdrs=None,  # type: ignore[arg-type]
            fp=MagicMock(read=lambda: b'{"errors": ["Rate limit"]}'),
        )
        with (
            patch("urllib.request.urlopen", side_effect=http_err),
            pytest.raises(EmbeddingUnavailableError, match="rate limit exceeded"),
        ):
            provider.embed(["test"])

    def test_network_url_error(self) -> None:
        provider = CloudflareEmbeddingProvider(account_id="acc", api_token="tok")
        with (
            patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")),
            pytest.raises(EmbeddingUnavailableError, match="network error"),
        ):
            provider.embed(["test"])


class TestCloudflareFactoryAndDoctor:
    def test_factory_resolves_cloudflare_provider(self) -> None:
        settings = WorkspaceSettings(
            name="test_ws",
            embedding_provider="cloudflare",
            cloudflare_account_id="acc_abc",
            cloudflare_api_token="tok_xyz",
            cloudflare_model_id="@cf/baai/bge-base-en-v1.5",
        )
        embedder = build_text_embedder(settings)
        assert isinstance(embedder, CloudflareEmbeddingProvider)
        assert embedder.model_id == "@cf/baai/bge-base-en-v1.5"
        assert embedder.space_id == "text.cloudflare.cf-baai-bge-base-en-v1-5.v1"

    def test_factory_honors_offline_setting(self) -> None:
        settings = WorkspaceSettings(
            name="test_ws",
            embedding_provider="cloudflare",
            offline=True,
            cloudflare_account_id="acc_abc",
            cloudflare_api_token="tok_xyz",
        )
        embedder = build_text_embedder(settings)
        with pytest.raises(EmbeddingUnavailableError, match="offline=True"):
            embedder.embed(["hello"])

    def test_doctor_reports_cloudflare_active_provider(self) -> None:
        settings = WorkspaceSettings(
            name="test_ws",
            embedding_provider="cloudflare",
            cloudflare_model_id="@cf/baai/bge-base-en-v1.5",
        )
        doc = doctor_embedding(settings)
        assert doc["active_provider"] == "cloudflare"
        assert doc["active_model"] == "@cf/baai/bge-base-en-v1.5"
        assert doc["active_space_id"] == "text.cloudflare.cf-baai-bge-base-en-v1-5.v1"


class TestCloudflareSettingsPersistence:
    def test_api_token_excluded_from_persistence(self, tmp_path: Any) -> None:
        settings = WorkspaceSettings(
            name="ws",
            embedding_provider="cloudflare",
            cloudflare_account_id="my-account",
            cloudflare_api_token="super-secret-token",
            cloudflare_model_id="@cf/baai/bge-base-en-v1.5",
        )
        dumped = settings.model_dump()
        assert "cloudflare_api_token" not in dumped
        assert dumped["cloudflare_account_id"] == "my-account"

        filepath = tmp_path / "workspace.yaml"
        save_settings(filepath, settings)

        content = filepath.read_text(encoding="utf-8")
        assert "super-secret-token" not in content
        assert "cloudflare_api_token" not in content
        assert "cloudflare_account_id: my-account" in content

        loaded = load_settings(filepath)
        assert loaded.cloudflare_account_id == "my-account"
        assert loaded.cloudflare_api_token == ""
