"""Playbooks: saved tool sequences executed as fast-path tools.

File format ``<workspace>/playbooks/<name>.md`` — YAML frontmatter + markdown::

    ---
    name: farm-stress-map
    version: 1
    triggers: ["stress map", "نقشه تنش"]
    params:
      input_tif: {type: string}
    steps:
      - tool: geo_compute_indices
        args: {input_tif: "{{params.input_tif}}", indices: ["NDVI"]}
      - tool: geo_reclassify
        args:
          input_tif: "{{steps.0.artifacts.0.path}}"
          rules: [{min: -1, max: 0.4, out: 2}]
          output_tif: runs/stress/classes.tif
    ---
    Human-readable description (ignored by the engine).

Templates: ``{{params.x}}`` and ``{{steps.N.<result|artifacts>.path…}}``.
Each playbook registers as tool ``pb_<name>`` so the LLM calls it like any
tool; step execution involves zero intermediate LLM calls.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from geoagent.config import AgentSettings
from geoagent.registry import Registry, RunContext, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)

_FULL_TEMPLATE = re.compile(r"^\{\{\s*([\w.]+)\s*\}\}$")
_PARTIAL_TEMPLATE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
_STEP_REF = re.compile(r"^steps\.(\d+)\.")


class Step(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class Playbook(BaseModel):
    name: str
    version: int = 1
    triggers: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    steps: list[Step]
    source_path: str | None = None


class PlaybookError(Exception):
    pass


def parse_playbook(text: str, source_path: str | None = None) -> Playbook:
    if not text.startswith("---"):
        raise PlaybookError(f"{source_path}: missing YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise PlaybookError(f"{source_path}: unterminated frontmatter")
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise PlaybookError(f"{source_path}: bad frontmatter ({exc})") from exc
    try:
        pb = Playbook(source_path=source_path, **meta)
    except Exception as exc:
        raise PlaybookError(f"{source_path}: {exc}") from exc
    if not pb.steps:
        raise PlaybookError(f"{source_path}: no steps")
    return pb


def load_playbooks(workspace_dir: Path) -> list[Playbook]:
    directory = workspace_dir / "playbooks"
    out: list[Playbook] = []
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.md")):
        try:
            out.append(parse_playbook(path.read_text(encoding="utf-8"), str(path)))
        except PlaybookError as exc:
            logger.warning("skipped invalid playbook %s: %s", path, exc)
            continue
    return out


def validate_playbook(pb: Playbook, registry: Registry) -> list[str]:
    """Return human-readable problems; empty list means runnable."""
    problems: list[str] = []
    required_params = set(pb.params.keys())
    for i, step in enumerate(pb.steps):
        if registry.get(step.tool) is None:
            problems.append(f"step {i}: unknown tool '{step.tool}'")
        for ref in _refs_in(step.args):
            m = _STEP_REF.match(ref)
            if m:
                if int(m.group(1)) >= i:
                    problems.append(f"step {i}: '{ref}' references a later/own step")
                continue
            if ref.startswith("params."):
                if ref.split(".", 1)[1] not in required_params:
                    problems.append(f"step {i}: '{ref}' not declared in params")
            else:
                problems.append(f"step {i}: template root must be 'params' or 'steps' — got '{ref}'")
    return problems


def _refs_in(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.extend(_PARTIAL_TEMPLATE.findall(value))
    elif isinstance(value, dict):
        for v in value.values():
            found.extend(_refs_in(v))
    elif isinstance(value, list):
        for v in value:
            found.extend(_refs_in(v))
    return found


def _deref(path: str, params: dict[str, Any], step_results: list[dict[str, Any]]) -> Any:
    node: Any = {"params": params, "steps": step_results}
    for part in path.split("."):
        if isinstance(node, dict):
            node = node.get(part)
        elif isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if node is None:
            return None
    return node


def _substitute(value: Any, params: dict[str, Any], step_results: list[dict[str, Any]]) -> Any:
    if isinstance(value, str):
        full = _FULL_TEMPLATE.match(value.strip())
        if full:
            return _deref(full.group(1), params, step_results)
        return _PARTIAL_TEMPLATE.sub(
            lambda m: str(_deref(m.group(1), params, step_results)), value
        )
    if isinstance(value, dict):
        return {k: _substitute(v, params, step_results) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, params, step_results) for v in value]
    return value


def _unresolved_refs(
    value: Any, params: dict[str, Any], step_results: list[dict[str, Any]]
) -> set[str]:
    """Template references that still resolve to ``None`` after substitution."""
    missing: set[str] = set()

    def walk(node: Any, original: Any) -> None:
        if isinstance(node, str):
            for ref in _PARTIAL_TEMPLATE.findall(node):
                if _deref(ref, params, step_results) is None:
                    missing.add(ref)
        elif isinstance(node, dict):
            for key, sub in node.items():
                walk(sub, original.get(key) if isinstance(original, dict) else None)
        elif isinstance(node, list):
            for item in node:
                walk(item, None)
        elif node is None and isinstance(original, str) and "{{" in original:
            for ref in _PARTIAL_TEMPLATE.findall(original):
                missing.add(ref)

    walk(value, value)
    return missing


def run_playbook(
    pb: Playbook,
    params: dict[str, Any],
    ctx: RunContext,
    registry: Registry,
) -> ToolResult:
    step_results: list[dict[str, Any]] = []
    step_names: list[str] = []
    for i, step in enumerate(pb.steps):
        resolved_args = _substitute(step.args, params, step_results)
        missing = _unresolved_refs(resolved_args, params, step_results)
        if missing:
            # `{{params.x}}` for an undeclared parameter silently became None,
            # so the step ran with a null argument and failed deeper inside a
            # tool with a confusing message.
            return ToolResult(
                status="validation_error",
                error=(
                    f"step {i} ({step.tool}): unresolved template value(s) "
                    f"{', '.join(sorted(missing))}"
                ),
                value={"completed_steps": step_names, "failed_step": i},
            )
        result = registry.call(step.tool, resolved_args, ctx)
        dumped = result.model_dump(mode="json")
        step_names.append(step.tool)
        step_results.append(dumped)
        if result.status != "ok":
            return ToolResult(
                status=result.status,
                error=f"step {i} ({step.tool}) failed: {result.error}",
                value={
                    "completed_steps": step_names[:-1],
                    "failed_step": i,
                    "steps": step_results,
                },
            )
    return ToolResult(
        status="ok",
        value={
            "playbook": pb.name,
            "steps": [
                {"tool": name, "status": s["status"], "value": s["value"],
                 "artifacts": s.get("artifacts")}
                for name, s in zip(step_names, step_results, strict=False)
            ],
        },
    )


def register_playbook_tools(registry: Registry, settings: AgentSettings) -> None:
    seen: dict[str, str | None] = {}
    for pb in load_playbooks(settings.workspace):
        tool_name = f"pb_{pb.name.replace('-', '_')}"
        if tool_name in seen:
            # Two files declaring the same `name:` used to raise out of
            # `Registry.register` and take the whole agent (every tool) down.
            logger.warning(
                "skipping playbook %s: name %r already registered by %s",
                pb.source_path,
                pb.name,
                seen[tool_name],
            )
            continue
        seen[tool_name] = pb.source_path
        problems = validate_playbook(pb, registry)
        _register_one(registry, pb, problems, registry)


def _register_one(
    parent: Registry, pb: Playbook, problems: list[str], call_registry: Registry
) -> None:
    def make_fn(bound: Playbook, issues: list[str]) -> Callable[[dict[str, Any], RunContext], ToolResult]:
        def fn(args: dict[str, Any], ctx: RunContext) -> ToolResult:
            if issues:
                detail = "; ".join(issues[:5])
                return ToolResult(status="validation_error", error=f"playbook '{bound.name}' invalid: {detail}")
            return run_playbook(bound, args, ctx, call_registry)

        return fn

    parent.register(
        ToolDefinition(
            name=f"pb_{pb.name.replace('-', '_')}",
            description=(
                f"Playbook '{pb.name}' (v{pb.version}): execute {len(pb.steps)} saved "
                f"steps in order. Triggers: {', '.join(pb.triggers) or '—'}"
                + (" [INVALID PLAYBOOK]" if problems else "")
            ),
            params=_params_schema(pb.params),
            timeout_s=600.0,
            cacheable=True,
        )
    )(make_fn(pb, problems))


def _params_schema(params: dict[str, Any]) -> dict[str, Any]:
    props = {
        name: ({"type": spec} if isinstance(spec, str) else dict(spec))
        for name, spec in params.items()
    }
    required = [n for n, s in props.items() if s.get("required", True)]
    for s in props.values():
        s.pop("required", None)
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


DRAFT_PROMPT = """\
You convert a successful GeoAgent conversation into a reusable playbook file.

Output ONLY the file content: YAML frontmatter (name: {name}, version: 1, \
triggers: short phrases that should activate it, params: JSON-schema map of \
the variable inputs) then '---' then a short markdown description. Steps \
reference tools EXACTLY as called, with variable parts replaced by \
{{{{params.x}}}} templates and downstream inputs wired via \
{{{{steps.N.artifacts.0.path}}}}. Do not invent tools that were not used.

Conversation tool sequence:
{transcript}
"""


def draft_playbook_text(
    backend: Any, name: str, tool_sequence: list[dict[str, Any]]
) -> str:
    transcript = "\n".join(
        json.dumps(t, ensure_ascii=False, sort_keys=True) for t in tool_sequence
    )
    response = backend.chat(
        [{"role": "user", "content": DRAFT_PROMPT.format(name=name, transcript=transcript)}]
    )
    text = (response.content or "").strip()
    if text.startswith("```"):
        # The fence may carry any language tag ("yaml", "yml", "markdown"), and
        # dropping only a literal "markdown" left "yaml\n---" at the top of the
        # file, which `parse_playbook` then rejects as missing frontmatter.
        fenced = text.split("\n", 1)[1] if "\n" in text else ""
        if fenced:
            text = fenced
        if "\n```" in text:
            text = text[: text.rindex("\n```")]
    return text.strip()


_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]*$")


def save_playbook(workspace_dir: Path, name: str, text: str) -> Path:
    """Write a playbook, refusing names that are not plain slugs.

    The name used to be interpolated straight into a filename
    (`workspace / "playbooks" / f"{safe}.md"`), so `..` wrote outside the
    playbook directory and an empty name wrote `playbooks/.md`.
    """
    if not isinstance(name, str) or not _SLUG.match(name):
        raise PlaybookError(
            f"invalid playbook name {name!r}: use lowercase letters, digits, '-' or '_'"
        )
    parse_playbook(text)
    safe = name.replace("-", "_").replace(" ", "_")
    target = workspace_dir / "playbooks" / f"{safe}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text.rstrip() + "\n", encoding="utf-8")
    return target
