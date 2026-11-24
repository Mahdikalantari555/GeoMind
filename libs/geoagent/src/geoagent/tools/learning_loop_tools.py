"""Learning-loop tools — thin wrappers over GeoMemory's public feedback facades.

Implements the `learning-loop` spec: raw feedback is immutable, review state
stays inside GeoMemory, exports are artifacts. No ML imports (L38-L41).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from geoagent.config import AgentSettings
from geoagent.registry import ArtifactRef, Registry, RunContext, ToolDefinition, ToolResult
from geoagent.tools import memory_tools

_SUPPORTED_TASKS = ("rag_eval", "qa_eval", "sft", "preference")


def _memory(ctx: RunContext) -> Any:  # noqa: ANN401
    settings: AgentSettings = ctx.settings
    return memory_tools._get_memory(settings)


def _write(memory: Any, fn: Any, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
    lock = memory_tools._WRITE_LOCK
    if lock is not None and hasattr(lock, "__enter__"):
        with lock:
            return fn(*args, **kwargs)
    return fn(*args, **kwargs)


def _target_type(ref: str) -> str:
    if ref.startswith("ans_"):
        return "answer"
    if ref.startswith("run_"):
        return "tool_run"
    if ref.startswith(("seg_", "ast_")):
        return "segment"
    if ref.startswith("retr_"):
        return "retrieval_run"
    return "answer"


def register(registry: Registry) -> None:
    @registry.register(
        ToolDefinition(
            name="geo_record_feedback",
            description=(
                "Persist immutable expert feedback, tagging answer/asset/tool-run "
                "targets. Never updates an existing event."
            ),
            params={
                "type": "object",
                "properties": {
                    "comment": {"type": "string", "description": "free-text correction"},
                    "rating": {"type": ["number", "null"]},
                    "target_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "answer, asset or tool-run identifiers",
                    },
                },
                "required": ["comment", "target_refs"],
                "additionalProperties": False,
            },
            returns="ids of the recorded feedback events",
        )
    )
    def geo_record_feedback(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        try:
            from geomemory import FeedbackEvent
        except ImportError as exc:  # pragma: no cover - geomemory is a hard dep
            return ToolResult(status="failed", error=f"geomemory unavailable: {exc}")

        refs = [str(r) for r in (args.get("target_refs") or [])]
        if not refs:
            return ToolResult(status="validation_error", error="target_refs must not be empty")
        memory = _memory(ctx)
        recorded: list[str] = []
        for ref in refs:
            payload = {
                "comment": str(args.get("comment", "")),
                "rating": args.get("rating"),
            }
            event = FeedbackEvent(
                target_type=_target_type(ref),
                target_id=ref,
                label="answer_rating" if args.get("rating") is not None else "edited_answer",
                actor="expert",
                payload=payload,
                metadata={"target_refs": refs},
            )
            stored = _write(memory, memory.record_feedback, event)
            recorded.append(str(getattr(stored, "id", event.id)))
        return ToolResult(status="ok", value={"event_ids": recorded})

    @registry.register(
        ToolDefinition(
            name="geo_review_queue",
            description="List pending dataset examples awaiting human review.",
            params={"type": "object", "properties": {}, "additionalProperties": False},
            returns="list of dataset examples with review_state",
        )
    )
    def geo_review_queue(args: dict[str, Any], ctx: RunContext) -> ToolResult:  # noqa: ARG001
        memory = _memory(ctx)
        examples = [_dump(e) for e in memory.get_review_queue()]
        return ToolResult(status="ok", value={"examples": examples})

    @registry.register(
        ToolDefinition(
            name="geo_review",
            description="Accept or reject a dataset example as a named reviewer.",
            params={
                "type": "object",
                "properties": {
                    "example_id": {"type": "string"},
                    "accept": {"type": "boolean"},
                    "reviewer_id": {"type": "string"},
                },
                "required": ["example_id", "accept"],
                "additionalProperties": False,
            },
            returns="whether the review state changed",
        )
    )
    def geo_review(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        memory = _memory(ctx)
        changed = _write(
            memory,
            memory.review_example,
            str(args["example_id"]),
            accept=bool(args["accept"]),
            reviewer_id=args.get("reviewer_id"),
        )
        return ToolResult(status="ok", value={"changed": bool(changed)})

    @registry.register(
        ToolDefinition(
            name="geo_export_dataset",
            description=(
                "Export accepted examples as JSONL for downstream training. "
                "The export file is returned as a SHA-256 artifact."
            ),
            params={
                "type": "object",
                "properties": {
                    "task_type": {"type": "string", "enum": list(_SUPPORTED_TASKS)},
                    "output_dir": {"type": "string", "description": "relative destination directory"},
                },
                "required": ["task_type", "output_dir"],
                "additionalProperties": False,
            },
            returns="path of the exported JSONL (plus dataset card)",
            timeout_s=120.0,
        )
    )
    def geo_export_dataset(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        task_type = str(args["task_type"])
        if task_type not in _SUPPORTED_TASKS:
            return ToolResult(
                status="validation_error",
                error=f"unsupported task_type {task_type!r}; expected {list(_SUPPORTED_TASKS)}",
            )
        out = Path(str(args["output_dir"]))
        if not out.is_absolute():
            out = ctx.workspace_dir / out
        out.mkdir(parents=True, exist_ok=True)
        try:
            path = _write(_memory(ctx), _memory(ctx).export_dataset, task_type, str(out))
        except ValueError as exc:
            return ToolResult(status="failed", error=str(exc))
        return ToolResult(
            status="ok",
            value={"path": str(path)},
            artifacts=[ArtifactRef(path=str(path))],
        )

    @registry.register(
        ToolDefinition(
            name="geo_export_runs",
            description=(
                "Dump ToolRun audit rows (tool, status, latency, budgets hit, "
                "from_cache) to CSV or JSONL for thesis metrics."
            ),
            params={
                "type": "object",
                "properties": {
                    "output_path": {"type": "string", "description": "relative output file"},
                    "format": {"type": "string", "enum": ["csv", "jsonl"], "default": "csv"},
                    "filters": {
                        "type": "object",
                        "properties": {
                            "tool": {"type": "string"},
                            "status": {"type": "string"},
                            "conversation_id": {"type": "string"},
                            "limit": {"type": "integer", "minimum": 1},
                        },
                        "additionalProperties": False,
                    },
                },
                "required": ["output_path"],
                "additionalProperties": False,
            },
            returns="path of the exported audit file",
        )
    )
    def geo_export_runs(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        out = Path(str(args["output_path"]))
        if not out.is_absolute():
            out = ctx.workspace_dir / out
        out.parent.mkdir(parents=True, exist_ok=True)
        fmt = str(args.get("format", "csv"))
        filters = args.get("filters") or {}
        rows = ctx.store.list_tool_runs(
            tool=filters.get("tool"),
            status=filters.get("status"),
            conversation_id=filters.get("conversation_id"),
            limit=int(filters.get("limit", 1000)),
        )
        columns = [
            "id", "tool", "status", "latency_ms", "budgets_hit", "from_cache",
            "error", "conversation_id", "created_at", "args_json",
        ]
        if fmt == "jsonl":
            out.write_text(
                "\n".join(json.dumps({k: row.get(k) for k in columns}, default=str) for row in rows) + "\n",
                encoding="utf-8",
            )
        elif fmt == "csv":
            with out.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
        else:
            return ToolResult(status="validation_error", error=f"unsupported format: {fmt}")
        return ToolResult(
            status="ok",
            value={"path": str(out), "rows": len(rows)},
            artifacts=[ArtifactRef(path=str(out))],
        )


def _dump(obj: Any) -> dict[str, Any]:  # noqa: ANN401
    """Serialize a facade model without importing non-public classes."""
    if hasattr(obj, "model_dump"):
        return dict(obj.model_dump(mode="json"))
    return dict(obj)
