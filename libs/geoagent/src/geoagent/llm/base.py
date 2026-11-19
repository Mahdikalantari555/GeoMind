"""LLM backend protocol and message models."""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class LLMError(Exception):
    """Raised when the LLM provider is unreachable or misconfigured."""


class MalformedToolArgumentsError(ValueError):
    """Raised when a tool call's argument blob is not a valid JSON object."""


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: str = "{}"

    def parsed_arguments(self) -> dict[str, Any]:
        """Parse the streamed argument JSON, or raise on a malformed object.

        Swallowing the `JSONDecodeError` and returning `{}` made a truncated
        argument blob look like "the model called the tool with no arguments":
        `required` fields then failed as `$.q: required` and the tool ran with
        empty arguments when nothing was mandatory.
        """
        raw = (self.arguments or "{}").strip() or "{}"
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MalformedToolArgumentsError(f"arguments for {self.name} are not valid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise MalformedToolArgumentsError(
                f"arguments for {self.name} must be a JSON object, got {type(value).__name__}"
            )
        return value


class ChatResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = []


@runtime_checkable
class LLMBackend(Protocol):
    def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> ChatResponse: ...
