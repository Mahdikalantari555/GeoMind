"""Agent chat route: SSE streaming chat with the GeoAgent core."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...errors import GeoFrontError
from ...services.agent import get_agent_service

router = APIRouter(prefix="/agent", tags=["agent"])

_KEEPALIVE_SECONDS = 15.0


class ContextScope(BaseModel):
    collections: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    context_scope: ContextScope | None = None


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


@router.post("/chat")
async def chat(req: Request, body: ChatRequest) -> StreamingResponse:
    """Stream agent chat responses via SSE.

    Events: `conversation`, `thinking`, `tool_start`, `tool_end`,
    `message`, `error`, `done`.
    """
    service = get_agent_service()
    if not service.is_initialized:
        raise GeoFrontError(
            code="agent_not_ready",
            message="Agent not initialized. Open a workspace first.",
            status_code=409,
        )

    core = service.core
    conv_id = body.conversation_id or core.new_conversation("web-chat")

    async def stream() -> AsyncIterator[str]:
        yield _sse("conversation", {"conversation_id": conv_id})
        yield _sse("thinking", {})

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def on_event(text: str) -> None:
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(queue.put_nowait, text)

        scope_dict = (
            body.context_scope.model_dump() if body.context_scope is not None else None
        )

        def run_chat() -> str:
            text: str = core.chat(
                conv_id,
                body.message,
                on_event=on_event,
                context_scope=scope_dict,
            )
            return text

        task = asyncio.create_task(asyncio.to_thread(run_chat))

        try:
            while not task.done():
                # Support client abort via disconnect detection
                if await req.is_disconnected():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                    yield _sse("error", {"code": "cancelled", "message": "Client aborted stream"})
                    yield _sse("done", {"conversation_id": conv_id})
                    return
                try:
                    event_text = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_SECONDS)
                    if event_text is None:
                        break
                    if event_text.startswith("[tool]"):
                        parts = event_text.split(" -> ", 1)
                        tool_name = parts[0].replace("[tool] ", "").strip()
                        status_info = parts[1] if len(parts) > 1 else ""
                        yield _sse("tool_start", {"tool": tool_name})
                        yield _sse("tool_end", {"tool": tool_name, "status": status_info})
                    elif event_text.startswith("[error]"):
                        error_msg = event_text.replace("[error] ", "").strip()
                        yield _sse("error", {"code": "backend_error", "message": error_msg})
                    else:
                        yield _sse("message", {"text": event_text})
                except asyncio.TimeoutError:
                    yield ": ping\n\n"

            try:
                answer = await task
                yield _sse("message", {"text": answer, "final": True})
                yield _sse("done", {"conversation_id": conv_id})
            except asyncio.CancelledError:
                yield _sse("error", {"code": "cancelled", "message": "Stream cancelled"})
                yield _sse("done", {"conversation_id": conv_id})
            except GeoFrontError as exc:
                yield _sse(
                    "error", {"code": exc.code, "message": exc.message, "detail": exc.detail}
                )
                yield _sse("done", {"conversation_id": conv_id})
            except Exception as exc:  # noqa: BLE001 - SSE error path
                yield _sse("error", {"code": "internal_error", "message": str(exc)})
                yield _sse("done", {"conversation_id": conv_id})
        except asyncio.CancelledError:
            # Client disconnected during streaming
            if not task.done():
                task.cancel()
            yield _sse("error", {"code": "cancelled", "message": "Stream cancelled"})
            yield _sse("done", {"conversation_id": conv_id})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _error_stream(code: str, message: str) -> AsyncIterator[str]:
    yield _sse("error", {"code": code, "message": message})
    yield _sse("done", {})


class AgentRunRequest(BaseModel):
    tool: str | None = None
    tool_name: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    playbook: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/run")
async def run_agent(body: AgentRunRequest) -> dict[str, object]:
    """Run an agent tool or playbook directly against the active workspace."""
    service = get_agent_service()
    if not service.is_initialized:
        raise GeoFrontError(
            code="agent_not_ready",
            message="Agent not initialized. Open a workspace first.",
            status_code=409,
        )

    import time

    from geoagent.registry import RunContext

    registry = service.registry
    target_tool = body.tool or body.tool_name

    if target_tool:
        tool_def = registry.get(target_tool)
        if tool_def is None:
            raise GeoFrontError(
                code="tool_not_found",
                message=f"Tool not found: {target_tool}",
                status_code=404,
            )
        timeout_s = tool_def.timeout_s
        effective_name = target_tool
        effective_args = body.args
    elif body.playbook:
        effective_name = f"pb_{body.playbook.replace('-', '_')}"
        tool_def = registry.get(effective_name)
        if tool_def is None:
            raise GeoFrontError(
                code="playbook_not_found",
                message=f"Playbook not found: {body.playbook}",
                status_code=404,
            )
        timeout_s = 880.0
        effective_args = body.params
    else:
        raise GeoFrontError(
            code="missing_tool",
            message="Must specify tool or playbook",
            status_code=422,
        )

    ctx = RunContext(
        store=service.store,
        workspace_dir=service.settings.workspace,
        sandbox_roots=service.settings.resolve_sandbox_roots(),
        settings=service.settings,
        max_tool_calls=500,
        deadline=time.monotonic() + timeout_s,
    )

    result = registry.call(effective_name, effective_args, ctx)
    dump: dict[str, Any] = result.model_dump(mode="json")
    return dump
