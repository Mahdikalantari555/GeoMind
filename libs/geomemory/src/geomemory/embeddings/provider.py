"""EmbeddingProvider — provider abstraction for dense text embeddings.

Consumers (GeoMemory, SearchService, IndexService, RetrievalBackends) depend
only on this Protocol. The canonical implementation is ONNXEmbeddingProvider
(Xenova/all-MiniLM-L6-v2, quantized ONNX, 384-d, mean-pool + L2). Future
providers (OpenAI, Voyage, Custom) satisfy the same shape over HTTP.
"""

from __future__ import annotations

import contextlib
import json
import os
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from geomemory.core.exceptions import EmbeddingUnavailableError
from geomemory.embeddings.normalization import l2_normalize

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class EmbeddingProvider(Protocol):
    """Provider abstraction for dense text embeddings."""

    @property
    def space_id(self) -> str:
        """Isolated embedding space identifier (e.g. text.onnx.Xenova-...v1)."""
        ...

    @property
    def model_id(self) -> str:
        """Underlying model identifier sent to the inference engine."""
        ...

    @property
    def dimension(self) -> int:
        """Vector dimension (e.g. 384 for MiniLM)."""
        ...

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Embed passages, returning (N, D) float32 L2-normalized."""
        ...

    def embed_query(self, texts: Sequence[str]) -> np.ndarray:
        """Embed queries (may apply e5-style prefixes)."""
        ...

    def embed_batch(self, texts: Sequence[str], batch_size: int) -> np.ndarray:
        """Embed in batches of batch_size."""
        ...


# ---------------------------------------------------------------------------
# ONNX canonical provider
# ---------------------------------------------------------------------------


class ONNXEmbeddingProvider:
    """Canonical provider via onnxruntime + tokenizers + quantized ONNX.

    Wraps :class:`OnnxTextEmbedder` so callers depend only on the provider
    shape. Uses ``Xenova/all-MiniLM-L6-v2`` quantized weights by default
    (``onnx/model_quantized.onnx``, 384-d, mean-pool, L2).
    """

    def __init__(
        self,
        model_name: str = "Xenova/all-MiniLM-L6-v2",
        *,
        model_id: str | None = None,
        model_dir: str | Path | None = None,
        offline: bool = False,
        auto_download: bool = True,
    ) -> None:
        from geomemory.embeddings.onnx_text import OnnxTextEmbedder

        # Normalize legacy HF id "sentence-transformers/all-MiniLM-L6-v2" to
        # the quantized Xenova ONNX export when the caller did not explicitly
        # override to an onnx-community model.
        normalized = model_name
        if model_name == "sentence-transformers/all-MiniLM-L6-v2":
            normalized = "Xenova/all-MiniLM-L6-v2"
        self._inner = OnnxTextEmbedder(
            normalized, model_id=model_id, model_dir=model_dir, offline=offline
        )
        self._auto_download = auto_download
        self._dimension = 384

    @property
    def space_id(self) -> str:
        return self._inner.space_id

    @property
    def model_id(self) -> str:
        return self._inner.model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(self._inner.embed(texts), dtype=np.float32)

    def embed_query(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(self._inner.embed_query(texts), dtype=np.float32)

    def embed_batch(self, texts: Sequence[str], batch_size: int) -> np.ndarray:
        return np.asarray(self._inner.embed_batch(texts, batch_size), dtype=np.float32)

    # Hub parity hook
    def download_with_progress(self, on_progress: Any | None = None) -> str:
        return self._inner.download_with_progress(on_progress=on_progress)


# ---------------------------------------------------------------------------
# Future provider stubs (interface only, no network in this change)
# ---------------------------------------------------------------------------


class _StubProvider:
    """Base for not-yet-implemented cloud providers."""

    def __init__(self, model_name: str = "", **_kw: Any) -> None:
        self._model_name = model_name

    @property
    def space_id(self) -> str:
        safe = self._model_name.replace("/", "-").replace(".", "-") or "unknown"
        return f"text.{self.__class__.__name__.lower()}.{safe}.v1"

    @property
    def model_id(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return 0

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        raise NotImplementedError(
            f"{self.__class__.__name__} not configured — set the API key env (e.g. OPENAI_API_KEY) "
            f"and implement HTTP retrieval, or use ONNXEmbeddingProvider for local inference."
        )

    def embed_query(self, texts: Sequence[str]) -> np.ndarray:
        return self.embed(texts)

    def embed_batch(self, texts: Sequence[str], batch_size: int) -> np.ndarray:
        return self.embed(texts)


class OpenAIEmbeddingProvider(_StubProvider):
    """Future OpenAI provider (stub — interface only)."""


class VoyageEmbeddingProvider(_StubProvider):
    """Future Voyage provider (stub — interface only)."""


class CustomEmbeddingProvider(_StubProvider):
    """Future custom provider (stub — interface only)."""


# ---------------------------------------------------------------------------
# Cloudflare Workers AI provider
# ---------------------------------------------------------------------------


class CloudflareEmbeddingProvider:
    """Dense text embeddings via Cloudflare Workers AI REST API.

    Posts batches to
    ``https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_id}``
    with Bearer authentication. Returns L2-normalized float32 vectors.
    """

    # Known dimensions for common Cloudflare Workers AI embedding models
    _MODEL_DIMENSIONS: dict[str, int] = {
        "@cf/baai/bge-small-en-v1.5": 384,
        "@cf/baai/bge-base-en-v1.5": 768,
        "@cf/baai/bge-large-en-v1.5": 1024,
    }

    def __init__(
        self,
        model_name: str = "@cf/baai/bge-base-en-v1.5",
        *,
        model_id: str | None = None,
        account_id: str | None = None,
        api_token: str | None = None,
        offline: bool = False,
        dimension: int | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._model_id = model_id or model_name or "@cf/baai/bge-base-en-v1.5"
        self._account_id = (
            account_id
            or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
            or os.environ.get("GEOMEMORY_CLOUDFLARE_ACCOUNT_ID")
            or ""
        )
        self._api_token = (
            api_token
            or os.environ.get("CLOUDFLARE_API_TOKEN")
            or os.environ.get("GEOMEMORY_CLOUDFLARE_API_TOKEN")
            or ""
        )
        self._offline = offline
        self._dimension = (
            dimension
            or self._MODEL_DIMENSIONS.get(self._model_id)
            or (384 if "small" in self._model_id else 1024 if "large" in self._model_id else 768)
        )
        self._timeout = timeout

    @property
    def space_id(self) -> str:
        slug = self._model_id.lstrip("@").replace("/", "-").replace(".", "-")
        return f"text.cloudflare.{slug}.v1"

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    def _post_embeddings(self, texts: Sequence[str]) -> np.ndarray:
        if self._offline:
            raise EmbeddingUnavailableError(
                "Cloudflare Workers AI embedding provider requires network access but offline=True is configured.",
                offline=True,
                hint="Set offline=False in workspace settings or use a local embedding provider (onnx/hashing).",
            )
        if not texts:
            return np.zeros((0, self._dimension), dtype=np.float32)

        if not self._account_id or not self._api_token:
            raise EmbeddingUnavailableError(
                "Cloudflare Workers AI requires cloudflare_account_id and cloudflare_api_token.",
                hint="Configure cloudflare_account_id and cloudflare_api_token in settings or environment variables (CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN).",
            )

        url = f"https://api.cloudflare.com/client/v4/accounts/{self._account_id}/ai/run/{self._model_id}"
        payload = json.dumps({"text": list(texts)}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                resp_bytes = resp.read()
                resp_body = resp_bytes.decode("utf-8")
        except urllib.error.HTTPError as exc:
            err_body = ""
            with contextlib.suppress(Exception):
                err_body = exc.read().decode("utf-8", errors="replace")
            if exc.code in (401, 403):
                raise EmbeddingUnavailableError(
                    f"Cloudflare Workers AI authentication failed (HTTP {exc.code}): {err_body or exc.reason}",
                    hint="Check your cloudflare_api_token and account permissions.",
                ) from exc
            if exc.code == 429:
                raise EmbeddingUnavailableError(
                    f"Cloudflare Workers AI rate limit exceeded (HTTP 429): {err_body or exc.reason}",
                    hint="Reduce concurrency or request a quota increase.",
                ) from exc
            if exc.code in (400, 404):
                raise EmbeddingUnavailableError(
                    f"Cloudflare Workers AI request failed (HTTP {exc.code}): {err_body or exc.reason}",
                    hint=f"Verify model_id '{self._model_id}' and account_id.",
                ) from exc
            raise EmbeddingUnavailableError(
                f"Cloudflare Workers AI HTTP error ({exc.code}): {err_body or exc.reason}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise EmbeddingUnavailableError(
                f"Cloudflare Workers AI network error: {exc}",
                hint="Check network connectivity to api.cloudflare.com.",
            ) from exc

        try:
            parsed = json.loads(resp_body)
        except Exception as exc:
            raise EmbeddingUnavailableError(
                f"Failed to parse Cloudflare Workers AI response: {exc}"
            ) from exc

        raw_data: Any = None
        if isinstance(parsed, dict):
            if not parsed.get("success", True) and "errors" in parsed and parsed["errors"]:
                errors_str = "; ".join(
                    str(e.get("message", e)) if isinstance(e, dict) else str(e)
                    for e in parsed["errors"]
                )
                raise EmbeddingUnavailableError(
                    f"Cloudflare Workers AI returned error: {errors_str}"
                )
            res = parsed.get("result")
            if isinstance(res, dict) and "data" in res:
                raw_data = res["data"]
            elif isinstance(res, list):
                raw_data = res
            elif "data" in parsed and isinstance(parsed["data"], list):
                raw_data = parsed["data"]
        elif isinstance(parsed, list):
            raw_data = parsed

        if raw_data is None:
            raise EmbeddingUnavailableError(
                "Unexpected response structure from Cloudflare Workers AI"
            )

        arr = np.asarray(raw_data, dtype=np.float32)
        if arr.ndim == 1 and len(texts) == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[0] != len(texts):
            raise EmbeddingUnavailableError(
                f"Expected {len(texts)} embeddings, got {arr.shape[0]}"
            )
        self._dimension = arr.shape[1]
        return l2_normalize(arr)

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Embed passages, returning (N, D) float32 L2-normalized."""
        return self._post_embeddings(texts)

    def embed_query(self, texts: Sequence[str]) -> np.ndarray:
        """Embed queries."""
        return self.embed(texts)

    def embed_batch(self, texts: Sequence[str], batch_size: int) -> np.ndarray:
        """Embed in batches of batch_size."""
        if not texts:
            return np.zeros((0, self._dimension), dtype=np.float32)
        if batch_size <= 0:
            batch_size = 64
        batches: list[np.ndarray] = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            batches.append(self.embed(chunk))
        return np.concatenate(batches, axis=0) if batches else np.zeros((0, self._dimension), dtype=np.float32)

    def download_with_progress(self, on_progress: Any | None = None) -> str:
        """Hub parity hook."""
        if on_progress is not None:
            on_progress(1.0)
        return ""

