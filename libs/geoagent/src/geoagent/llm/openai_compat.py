"""OpenAI-compatible Chat Completions backend (stdlib urllib, no SDK lock-in)."""

from __future__ import annotations

import contextlib
import json
import urllib.error
import urllib.request
from typing import Any

from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from geoagent.config import AgentSettings
from geoagent.llm.base import ChatResponse, LLMError, ToolCall


def _is_transient_http_error(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (429, 503)
    return isinstance(exc, urllib.error.URLError)


class OpenAICompatBackend:
    def __init__(self, settings: AgentSettings) -> None:
        self._settings = settings
        base = settings.provider.base_url.rstrip("/")
        if not base.endswith("/v1") and "/v1" not in base.rsplit("/", 1)[-1]:
            base = f"{base}/v1"
        self._url = f"{base}/chat/completions"
        self._api_key = settings.resolve_api_key()
        if not self._api_key:
            env = settings.provider.api_key_env
            raise LLMError(
                f"No API key configured. Set the {env} environment variable "
                f"or provider.api_key in agent.yaml."
            )

    def _execute_request(self, request: urllib.request.Request) -> dict[str, Any]:
        retrying = Retrying(
            stop=stop_after_attempt(self._settings.llm_retry_max_attempts),
            wait=wait_exponential(
                multiplier=self._settings.llm_retry_base_delay_s,
                min=self._settings.llm_retry_base_delay_s,
                max=30.0,
            ),
            retry=retry_if_exception(_is_transient_http_error),
            reraise=True,
        )

        try:
            for attempt in retrying:
                with attempt, urllib.request.urlopen(request, timeout=self._settings.provider.timeout_s) as resp:
                    return json.loads(resp.read().decode("utf-8"))  # type: ignore[no-any-return]
        except (RetryError, urllib.error.HTTPError, urllib.error.URLError) as exc:
            if isinstance(exc, RetryError):
                cause = exc.last_attempt.exception() if exc.last_attempt else exc
            else:
                cause = exc

            if isinstance(cause, urllib.error.HTTPError):
                tail = ""
                with contextlib.suppress(Exception):
                    tail = cause.read().decode("utf-8", errors="replace")[:500]
                hint = (
                    "check provider.api_key / OPENAI_API_KEY"
                    if cause.code == 401
                    else "check base_url and model name"
                )
                raise LLMError(f"provider returned HTTP {cause.code}: {tail} ({hint})") from cause
            if isinstance(cause, urllib.error.URLError):
                raise LLMError(f"cannot reach LLM provider at {self._url}: {cause.reason}") from cause
            raise LLMError(f"LLM request failed: {cause}") from cause

        raise LLMError("LLM request failed: empty retry cycle")

    def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> ChatResponse:
        body: dict[str, Any] = {
            "model": self._settings.provider.model,
            "messages": messages,
            "temperature": self._settings.provider.temperature,
        }
        if tools:
            body["tools"] = tools
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self._url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        data = self._execute_request(request)

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message", {})
        raw_calls = message.get("tool_calls") or []
        tool_calls = [
            ToolCall(
                id=tc.get("id", ""),
                name=tc.get("function", {}).get("name", ""),
                arguments=tc.get("function", {}).get("arguments", "{}"),
            )
            for tc in raw_calls
        ]
        return ChatResponse(content=message.get("content"), tool_calls=tool_calls)
