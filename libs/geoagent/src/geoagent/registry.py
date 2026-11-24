"""Tool registry: definitions, validation, sandbox, cache, audit, budgets."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from geoagent.store import Store

ToolFn = Callable[[dict[str, Any], "RunContext"], Any]

PATH_SUFFIXES = ("path", "file", "dir")
# Glob-like arguments are paths too: `Path.glob("../../**/*.tif")` leaves the
# sandbox, so they must be validated like any other path argument.
PATH_LIKE_SUFFIXES = PATH_SUFFIXES + ("glob", "dir", "root", "pattern")
# Write destinations are never allowed to be absolute. Attackers only need one
# overlooked key (e.g. `out_png`) to overwrite an arbitrary file, so classify
# by prefix rather than by a hardcoded list of known argument names.
WRITE_PATH_PREFIXES = ("output_", "out_")
GLOB_CHARS = ("*", "?", "[")

# Tool manifests are injected into the system prompt. Cap their token cost
# (tool-registry spec); overflow families collapse to one-line summaries and
# are expandable on demand with `list_tools(family)`.
DEFAULT_MANIFEST_TOKEN_BUDGET = 1200


def _token_estimate(text: str) -> int:
    return max(1, len(text) // 4 + 1)


def _tool_family(name: str) -> str:
    return name.split("_", 1)[0] if "_" in name else name


def _is_write_path(key: str) -> bool:
    return key.startswith(WRITE_PATH_PREFIXES)


def _is_path_like(key: str, value: Any) -> bool:
    """True when the argument is a filesystem path that must stay in-sandbox.

    Write arguments (`output_*`/`out_*`) are always path-checked, so even an
    absolute value must resolve under a sandbox root. Some *read* arguments
    (AOI GeoJSON, reference rasters) legitimately take an operator-supplied
    absolute path, so they are only path-checked when the value looks like an
    escape. Patterns, `~` and any `..` segment are always checked.
    """
    if not isinstance(value, str) or not value:
        return False
    if _is_write_path(key):
        return True
    if key.endswith(PATH_LIKE_SUFFIXES):
        return True
    return value.startswith("~") or ".." in Path(value).parts


class ToolDefinition(BaseModel):
    name: str
    description: str
    params: dict[str, Any] = Field(
        # No `additionalProperties: False` by default: a tool that does not
        # declare its schema must keep accepting arbitrary arguments.
        default_factory=lambda: {"type": "object", "properties": {}}
    )
    returns: str = ""
    timeout_s: float = 60.0
    cacheable: bool = False


class ArtifactRef(BaseModel):
    path: str
    sha256: str | None = None
    entity_ref: str | None = None


class ToolResult(BaseModel):
    status: str = "ok"  # ok | validation_error | failed | timeout | budget_refused
    value: Any = None
    error: str | None = None
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    from_cache: bool = False


@dataclass
class RunContext:
    store: Store
    workspace_dir: Path
    sandbox_roots: list[Path]
    settings: Any = None
    conversation_id: str | None = None
    turn_id: str | None = None
    max_tool_calls: int = 8
    deadline: float = field(default_factory=lambda: time.monotonic() + 120.0)
    calls_used: int = 0
    context_scope: dict[str, list[str]] | None = None
    # Orchestrator/playbook sub-contexts share the parent's wall-clock
    # deadline and a global nested-call ceiling. This replaces the old
    # "500 calls / +880s" reset that made nested fan-out effectively unbounded
    # (L-061), while still allowing an orchestrator to fan out a handful of
    # legitimate sub-steps.
    shared_budget: dict[str, Any] = field(default_factory=dict)
    # Set by the agent loop when a tool call's argument blob could not be
    # parsed, so `Registry.call` reports it instead of validating empty args.
    tool_arguments_invalid: bool = False
    tool_arguments_error: str = ""

    NESTED_CALL_CEILING = 64
    NESTED_FANOUT = 4

    def _deadline(self) -> float:
        return float(self.shared_budget.get("deadline", self.deadline))

    def _nested_used(self) -> int:
        return int(self.shared_budget.get("nested_used", 0))

    def budget_left(self) -> bool:
        return (
            self.calls_used < self.max_tool_calls
            and self._nested_used() < self.NESTED_CALL_CEILING
            and time.monotonic() < self._deadline()
        )

    def budget_reason(self) -> str:
        if self.calls_used >= self.max_tool_calls:
            return f"max tool calls reached ({self.max_tool_calls})"
        if self._nested_used() >= self.NESTED_CALL_CEILING:
            return f"nested call ceiling reached ({self.NESTED_CALL_CEILING})"
        return "wall-clock budget exhausted"

    def consume_call(self) -> None:
        self.calls_used += 1
        if self.shared_budget:
            self.shared_budget["nested_used"] = self._nested_used() + 1

    def derive(self, **overrides: Any) -> RunContext:
        """Create a bounded sub-context sharing the parent's deadline."""
        import dataclasses

        if not self.shared_budget:
            self.shared_budget = {
                "deadline": self.deadline,
                "nested_used": self.calls_used,
            }
        base: dict[str, Any] = {
            "max_tool_calls": max(self.max_tool_calls * self.NESTED_FANOUT, 16),
            "calls_used": 0,
            "deadline": self.deadline,
            "shared_budget": self.shared_budget,
        }
        base.update(overrides)
        return dataclasses.replace(self, **base)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate(value: Any, schema: dict[str, Any], where: str) -> list[str]:
    """Validate the JSON-schema subset the tool definitions actually use.

    Earlier this checked only `type`/`required`/`enum`, so `minimum`,
    `maximum`, `minItems`, `maxItems`, `minLength`, `additionalProperties`
    and nested `required` were advertised to the model but never enforced.
    """
    errors: list[str] = []
    expected = schema.get("type")
    if "enum" in schema and value not in schema["enum"]:
        return [f"{where}: must be one of {schema['enum']}"]
    if expected == "object":
        if not isinstance(value, dict):
            return [f"{where}: expected object"]
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{where}.{req}: required")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{where}.{key}: unknown property")
        for key, sub in value.items():
            if key in props:
                errors.extend(_validate(sub, props[key], f"{where}.{key}"))
    elif expected == "array":
        if not isinstance(value, list):
            return [f"{where}: expected array"]
        if "minItems" in schema and len(value) < int(schema["minItems"]):
            errors.append(f"{where}: needs at least {schema['minItems']} items")
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            errors.append(f"{where}: allows at most {schema['maxItems']} items")
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(value):
                errors.extend(_validate(item, item_schema, f"{where}[{i}]"))
    elif expected == "string":
        if not isinstance(value, str):
            errors.append(f"{where}: expected string")
        else:
            errors.extend(_string_errors(value, schema, where))
    elif expected in ("integer", "number"):
        ok = isinstance(value, int) if expected == "integer" else isinstance(value, (int, float))
        if isinstance(value, bool) or not ok:
            errors.append(f"{where}: expected {expected}")
        elif isinstance(value, (int, float)):
            errors.extend(_range_errors(value, schema, where))
    elif expected == "boolean" and not isinstance(value, bool):
        errors.append(f"{where}: expected boolean")
    return errors


def _string_errors(value: str, schema: dict[str, Any], where: str) -> list[str]:
    errors: list[str] = []
    if "minLength" in schema and len(value) < int(schema["minLength"]):
        errors.append(f"{where}: must be at least {schema['minLength']} characters")
    if "maxLength" in schema and len(value) > int(schema["maxLength"]):
        errors.append(f"{where}: must be at most {schema['maxLength']} characters")
    if "pattern" in schema and not _matches(value, str(schema["pattern"])):
        errors.append(f"{where}: does not match {schema['pattern']}")
    return errors


def _matches(value: str, pattern: str) -> bool:
    try:
        return re.search(pattern, value) is not None
    except re.error:
        return True  # an unsupported pattern must not reject valid input


def _range_errors(value: float, schema: dict[str, Any], where: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return errors
    if "minimum" in schema and value < schema["minimum"]:
        errors.append(f"{where}: must be >= {schema['minimum']}")
    if "maximum" in schema and value > schema["maximum"]:
        errors.append(f"{where}: must be <= {schema['maximum']}")
    return errors


def _path_args(args: dict[str, Any]) -> list[str]:
    return [k for k, v in args.items() if _is_path_like(k, v)]


def _check_sandbox(path_keys: list[str], args: dict[str, Any], roots: list[Path], workspace: Path) -> str | None:
    for key in path_keys:
        raw = args[key]
        if raw.startswith("~"):
            return f"path '{raw}' is outside sandbox roots (home expansion is not allowed)"
        # Glob patterns are checked on their static prefix: `../../**/*.tif`
        # must not resolve outside even though the wildcard itself cannot.
        static = raw.split("*", 1)[0].split("?", 1)[0].split("[", 1)[0]
        probe = Path(static or ".")
        if ".." in probe.parts:
            return f"path '{raw}' escapes sandbox roots ({', '.join(str(r) for r in roots)})"
        p = Path(raw)
        try:
            resolved = (p if p.is_absolute() else workspace / p).resolve()
        except (OSError, RuntimeError):
            return f"path '{raw}' cannot be resolved"
        if not any(resolved.is_relative_to(root) for root in roots):
            return (
                f"path '{raw}' is outside sandbox roots "
                f"({', '.join(str(r) for r in roots)})"
            )
    return None


def validate_path_args(
    args: dict[str, Any],
    roots: list[Path],
    workspace: Path,
    *,
    path_params: Sequence[str] = (),
    output_params: Sequence[str] = (),
) -> str | None:
    """Validate declared path/output params before an external CLI is executed.

    Returns an error string when a declared path escapes the sandbox. Kept
    here so registry tool calls and CLI tools share one containment policy.
    """
    declared = set(path_params) | set(output_params)
    path_keys = [k for k in declared if k in args and isinstance(args[k], str) and args[k]]
    return _check_sandbox(path_keys, args, list(roots), workspace)


def _cache_key(name: str, args: dict[str, Any], workspace: Path) -> tuple[str, bool]:
    payload: dict[str, Any] = {"n": name, "a": args}
    files_ok = True
    for key, val in args.items():
        if isinstance(val, str) and key.endswith(PATH_SUFFIXES):
            p = Path(val)
            p = p if p.is_absolute() else workspace / p
            if p.is_file():
                payload[key + "_sha"] = sha256_file(p)
            else:
                files_ok = False
    blob = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return digest, files_ok


class Registry:
    def __init__(self, manifest_token_budget: int = DEFAULT_MANIFEST_TOKEN_BUDGET) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._fns: dict[str, ToolFn] = {}
        self._usage: dict[str, int] = {}
        self._manifest_token_budget = manifest_token_budget
        try:
            from geoagent.tools import geolearn_tools

            geolearn_tools.register(self)
        except ImportError:
            pass
        try:
            from geoagent.tools import rs_tools

            rs_tools.register(self)
        except ImportError:
            pass
        try:
            from geoagent.tools import learning_loop_tools

            learning_loop_tools.register(self)
        except ImportError:
            pass
        self._register_manifest_tool()

    def _register_manifest_tool(self) -> None:
        """Escape hatch for families collapsed by the manifest cap."""

        @self.register(
            ToolDefinition(
                name="list_tools",
                description="List full definitions for a tool family collapsed by the manifest token cap.",
                params={
                    "type": "object",
                    "properties": {
                        "family": {"type": "string", "description": 'family prefix, e.g. "geo"'}
                    },
                    "required": ["family"],
                    "additionalProperties": False,
                },
                returns="full definitions for the requested family",
            )
        )
        def list_tools(args: dict[str, Any], ctx: RunContext) -> ToolResult:  # noqa: ARG001
            family = str(args.get("family", ""))
            definitions = [
                t.model_dump(mode="json")
                for name, t in sorted(self._tools.items())
                if _tool_family(name) == family
            ]
            return ToolResult(
                status="ok" if definitions else "validation_error",
                value={"family": family, "tools": definitions},
                error=None if definitions else f"unknown family: {family}",
            )

    def _manifest_visible(self) -> tuple[list[ToolDefinition], list[str]]:
        """Return (full definitions, collapsed family names) within the budget."""
        tools = sorted(self._tools.values(), key=lambda x: x.name)
        lines = [f"- {t.name}: {t.description}" for t in tools]
        if sum(_token_estimate(x) for x in lines) <= self._manifest_token_budget:
            return tools, []
        # Most-recently-used families stay expanded; least-used collapse first.
        families = sorted(
            {_tool_family(t.name) for t in tools},
            key=lambda f: (-sum(self._usage.get(t.name, 0) for t in tools if _tool_family(t.name) == f), f),
        )
        used = _token_estimate("- list_tools(family): expand a collapsed family")
        kept: list[ToolDefinition] = []
        collapsed: list[str] = []
        for family in families:
            members = [t for t in tools if _tool_family(t.name) == family]
            cost = sum(_token_estimate(f"- {t.name}: {t.description}") for t in members)
            if used + cost <= self._manifest_token_budget:
                kept.extend(members)
                used += cost
            else:
                collapsed.append(family)
                used += _token_estimate(f"- {family}: {len(members)} tools (use list_tools)")
        return kept, collapsed

    def register(self, definition: ToolDefinition) -> Callable[[ToolFn], ToolFn]:
        def deco(fn: ToolFn) -> ToolFn:
            if definition.name in self._tools:
                raise ValueError(
                    f"duplicate tool name '{definition.name}' "
                    f"(already registered with {self._fns[definition.name]})"
                )
            self._tools[definition.name] = definition
            self._fns[definition.name] = fn
            return fn

        return deco

    def names(self) -> list[str]:
        return sorted(self._tools)

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def openai_tools(self) -> list[dict[str, Any]]:
        visible, collapsed = self._manifest_visible()
        tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.params,
                },
            }
            for t in visible
        ]
        if collapsed:
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": "list_tools",
                        "description": "Expand a tool family collapsed by the manifest token cap.",
                        "parameters": self._tools["list_tools"].params,
                    },
                }
            )
        return tools

    def manifest_lines(self) -> list[str]:
        visible, collapsed = self._manifest_visible()
        lines = [f"- {t.name}: {t.description}" for t in visible]
        for family in collapsed:
            count = sum(1 for name in self._tools if _tool_family(name) == family)
            lines.append(f"- {family}: {count} tools (use list_tools to expand)")
        if collapsed:
            lines.append("- list_tools(family): expand a collapsed family on demand")
        return lines

    def call(self, name: str, args: dict[str, Any], ctx: RunContext) -> ToolResult:
        started = time.perf_counter()
        tool = self._tools.get(name)
        if tool is None:
            result = ToolResult(status="validation_error", error=f"unknown tool: {name}")
            self._audit(ctx, name, args, "", result, started)
            return result
        # Track usage so the manifest cap collapses least-recently-used families
        # first (tool-registry spec).
        self._usage[name] = self._usage.get(name, 0) + 1
        if not ctx.budget_left():
            result = ToolResult(status="budget_refused", error=ctx.budget_reason())
            self._audit(ctx, name, args, "", result, started)
            return result

        if getattr(ctx, "tool_arguments_invalid", False):
            err = str(getattr(ctx, "tool_arguments_error", "malformed tool arguments"))
            result = ToolResult(status="validation_error", error=err)
            ctx.tool_arguments_invalid = False
            self._audit(ctx, name, args, "", result, started)
            return result

        errors = _validate(args, tool.params, "$")
        bad_paths = _path_args(args)
        sandbox_err = (
            _check_sandbox(bad_paths, args, ctx.sandbox_roots, ctx.workspace_dir)
            if bad_paths
            else None
        )
        if errors or sandbox_err:
            msg = "; ".join(errors + ([sandbox_err] if sandbox_err else []))
            result = ToolResult(status="validation_error", error=msg)
            self._audit(ctx, name, args, "", result, started)
            return result

        ctx.consume_call()

        cache_dir = ctx.workspace_dir / "runs" / "cache"
        key: str | None = None
        if tool.cacheable:
            key, _ = _cache_key(name, args, ctx.workspace_dir)
            cached = cache_dir / key / "result.json"
            if cached.is_file():
                try:
                    result = ToolResult.model_validate(json.loads(cached.read_text(encoding="utf-8")))
                    result.from_cache = True
                    self._audit(ctx, name, args, key, result, started)
                    return result
                except (json.JSONDecodeError, ValueError):
                    pass

        box: dict[str, Any] = {}

        def target() -> None:
            try:
                box["result"] = self._fns[name](args, ctx)
            except Exception as exc:  # noqa: BLE001 - tool boundary
                box["error"] = f"{type(exc).__name__}: {exc}"

        worker = threading.Thread(target=target, daemon=True)
        worker.start()
        # Two-phase join: give thread timeout + 0.5s buffer to finish cleanly
        worker.join(tool.timeout_s + 0.5)
        if worker.is_alive():
            import logging
            logging.getLogger(__name__).warning(
                f"tool '{name}' thread still alive after {tool.timeout_s + 0.5:.1f}s — "
                "will be reclaimed on process exit (daemon thread). Timeout does NOT "
                "roll back side effects the tool already performed; design tools to "
                "write atomically."
            )
            result = ToolResult(status="timeout", error=f"{name} exceeded {tool.timeout_s:.0f}s")
            self._audit(ctx, name, args, key or "", result, started)
            return result
        if "error" in box:
            result = ToolResult(status="failed", error=str(box["error"])[:2000])
            self._audit(ctx, name, args, key or "", result, started)
            return result

        raw = box.get("result")
        result = raw if isinstance(raw, ToolResult) else ToolResult(status="ok", value=raw)

        for art in result.artifacts:
            p = Path(art.path)
            if art.sha256 is None and p.is_file():
                art.sha256 = sha256_file(p)

        if key is not None and result.status == "ok":
            out_dir = cache_dir / key
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "result.json").write_text(result.model_dump_json(), encoding="utf-8")

        self._audit(ctx, name, args, key or "", result, started)
        return result

    def _audit(
        self,
        ctx: RunContext,
        name: str,
        args: dict[str, Any],
        cache_key: str,
        result: ToolResult,
        started: float,
    ) -> None:
        latency_ms = int((time.perf_counter() - started) * 1000)
        args_blob = json.dumps(args, sort_keys=True, default=str).encode("utf-8")
        args_hash = hashlib.sha256(cache_key.encode() + b"\x00" + args_blob).hexdigest()
        ctx.store.record_tool_run(
            conversation_id=ctx.conversation_id,
            turn_id=ctx.turn_id,
            tool=name,
            args=args,
            args_hash=args_hash,
            status=result.status,
            latency_ms=latency_ms,
            error=result.error,
            artifacts=[a.model_dump() for a in result.artifacts],
            from_cache=result.from_cache,
        )
