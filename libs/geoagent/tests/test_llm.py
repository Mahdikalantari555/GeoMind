"""Unit tests for geoagent.llm (OpenAI-compatible backend, tool calls, error handling)."""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from tenacity import RetryError

from geoagent.config import AgentSettings, ProviderSettings
from geoagent.llm.base import LLMError, ToolCall
from geoagent.llm.openai_compat import OpenAICompatBackend, _is_transient_http_error


def test_tool_call_parsed_arguments() -> None:
    # Valid dict
    tc1 = ToolCall(id="c1", name="search", arguments='{"query": "wheat"}')
    assert tc1.parsed_arguments() == {"query": "wheat"}

    # Invalid JSON
    tc2 = ToolCall(id="c2", name="search", arguments="invalid json")
    assert tc2.parsed_arguments() == {}

    # JSON not a dict (e.g. list or integer)
    tc3 = ToolCall(id="c3", name="search", arguments="[1, 2, 3]")
    assert tc3.parsed_arguments() == {}

    # Empty string
    tc4 = ToolCall(id="c4", name="search", arguments="")
    assert tc4.parsed_arguments() == {}


def test_is_transient_http_error() -> None:
    # 429 and 503 are transient
    err_429 = urllib.error.HTTPError("http://test", 429, "Too Many Requests", {}, io.BytesIO(b""))
    err_503 = urllib.error.HTTPError("http://test", 503, "Service Unavailable", {}, io.BytesIO(b""))
    err_404 = urllib.error.HTTPError("http://test", 404, "Not Found", {}, io.BytesIO(b""))
    url_err = urllib.error.URLError("connection refused")
    val_err = ValueError("bad value")

    assert _is_transient_http_error(err_429) is True
    assert _is_transient_http_error(err_503) is True
    assert _is_transient_http_error(err_404) is False
    assert _is_transient_http_error(url_err) is True
    assert _is_transient_http_error(val_err) is False


def test_openai_compat_init_url_and_key() -> None:
    # URL without /v1 gets /v1 appended
    settings = AgentSettings(
        provider=ProviderSettings(base_url="https://api.openai.com", api_key="secret-key")
    )
    backend = OpenAICompatBackend(settings)
    assert backend._url == "https://api.openai.com/v1/chat/completions"

    # URL already ending in /v1 stays as is
    settings_v1 = AgentSettings(
        provider=ProviderSettings(base_url="https://api.openai.com/v1", api_key="secret-key")
    )
    backend_v1 = OpenAICompatBackend(settings_v1)
    assert backend_v1._url == "https://api.openai.com/v1/chat/completions"

    # Missing API key raises LLMError
    settings_no_key = AgentSettings(
        provider=ProviderSettings(base_url="https://api.openai.com/v1", api_key=None, api_key_env="NONEXISTENT_KEY_ENV_XYZ")
    )
    with pytest.raises(LLMError, match="No API key configured"):
        OpenAICompatBackend(settings_no_key)


def test_openai_compat_chat_success_with_tool_calls() -> None:
    settings = AgentSettings(
        provider=ProviderSettings(base_url="https://api.example.com/v1", api_key="test-key")
    )
    backend = OpenAICompatBackend(settings)

    mock_resp_payload = {
        "choices": [
            {
                "message": {
                    "content": "Analyzing...",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {
                                "name": "geo_search",
                                "arguments": '{"query": "crop"}',
                            },
                        }
                    ],
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_resp_payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = backend.chat(
            messages=[{"role": "user", "content": "find crops"}],
            tools=[{"type": "function", "function": {"name": "geo_search"}}],
        )
        assert res.content == "Analyzing..."
        assert len(res.tool_calls) == 1
        assert res.tool_calls[0].name == "geo_search"
        assert res.tool_calls[0].parsed_arguments() == {"query": "crop"}


def test_openai_compat_http_401_error() -> None:
    settings = AgentSettings(
        provider=ProviderSettings(base_url="https://api.example.com/v1", api_key="bad-key"),
        llm_retry_max_attempts=1,
    )
    backend = OpenAICompatBackend(settings)

    http_err = urllib.error.HTTPError(
        "https://api.example.com/v1/chat/completions",
        401,
        "Unauthorized",
        {},
        io.BytesIO(b"Invalid token"),
    )

    with (
        patch("urllib.request.urlopen", side_effect=http_err),
        pytest.raises(LLMError, match="check provider.api_key"),
    ):
        backend.chat(messages=[{"role": "user", "content": "hi"}])


def test_openai_compat_http_500_error() -> None:
    settings = AgentSettings(
        provider=ProviderSettings(base_url="https://api.example.com/v1", api_key="key"),
        llm_retry_max_attempts=1,
    )
    backend = OpenAICompatBackend(settings)

    http_err = urllib.error.HTTPError(
        "https://api.example.com/v1/chat/completions",
        500,
        "Internal Server Error",
        {},
        io.BytesIO(b"Model crashed"),
    )

    with (
        patch("urllib.request.urlopen", side_effect=http_err),
        pytest.raises(LLMError, match="check base_url and model name"),
    ):
        backend.chat(messages=[{"role": "user", "content": "hi"}])


def test_openai_compat_url_error() -> None:
    settings = AgentSettings(
        provider=ProviderSettings(base_url="https://unreachable.local/v1", api_key="key"),
        llm_retry_max_attempts=1,
    )
    backend = OpenAICompatBackend(settings)

    url_err = urllib.error.URLError("Connection refused")

    with (
        patch("urllib.request.urlopen", side_effect=url_err),
        pytest.raises(LLMError, match="cannot reach LLM provider"),
    ):
        backend.chat(messages=[{"role": "user", "content": "hi"}])


def test_openai_compat_retry_error_wrapper() -> None:
    settings = AgentSettings(
        provider=ProviderSettings(base_url="https://api.example.com/v1", api_key="key"),
        llm_retry_max_attempts=1,
    )
    backend = OpenAICompatBackend(settings)

    # Simulate a RetryError where cause is generic exception
    fut = MagicMock()
    fut.exception.return_value = RuntimeError("Unexpected network drop")
    retry_err = RetryError(fut)

    with (
        patch("urllib.request.urlopen", side_effect=retry_err),
        pytest.raises(LLMError, match="LLM request failed: Unexpected network drop"),
    ):
        backend.chat(messages=[{"role": "user", "content": "hi"}])
