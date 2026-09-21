from __future__ import annotations

import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from geoagent.config import AgentSettings, ProviderSettings
from geoagent.llm.base import LLMError
from geoagent.llm.openai_compat import OpenAICompatBackend


def test_retry_on_429_then_succeed() -> None:
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"choices": [{"message": {"content": "ok"}}]}'
    mock_resp.__enter__.return_value = mock_resp

    calls = 0

    def fake_urlopen(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)
        return mock_resp

    settings = AgentSettings(
        provider=ProviderSettings(api_key="test-key", base_url="http://localhost:8000/v1"),
        llm_retry_max_attempts=3,
        llm_retry_base_delay_s=0.01,
    )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        backend = OpenAICompatBackend(settings)
        resp = backend.chat([{"role": "user", "content": "hello"}])
        assert resp.content == "ok"
        assert calls == 3


def test_retry_settings_defaults() -> None:
    settings = AgentSettings()
    assert settings.llm_retry_max_attempts == 3
    assert settings.llm_retry_base_delay_s == 1.0
