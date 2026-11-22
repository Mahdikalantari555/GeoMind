# GeoAgent

Lightweight agent framework for remote-sensing workflows, built on the
[GeoMemory](../GeoMemory/) public API. Local-first, offline-by-default,
CPU-friendly (frugal AI).

- Specs: [`openspec/project.md`](openspec/project.md)
- Status: implemented. Capability inventory (one page per capability):
  [`agent-core`](openspec/specs/agent-core/spec.md) ·
  [`tool-registry`](openspec/specs/tool-registry/spec.md) ·
  [`memory-tools`](openspec/specs/memory-tools/spec.md) ·
  [`gis-tools`](openspec/specs/gis-tools/spec.md) ·
  [`advisor`](openspec/specs/advisor/spec.md) ·
  [`cli-runner`](openspec/specs/cli-runner/spec.md) ·
  [`customizable-plugins`](openspec/specs/customizable-plugins/spec.md) ·
  [`playbooks`](openspec/specs/playbooks/spec.md) ·
  [`learning-loop`](openspec/specs/learning-loop/spec.md) ·
  [`mcp-interface`](openspec/specs/mcp-interface/spec.md)
- Thesis context: `../Ideas/`

```
User ──chat──▶ Agent Core (GGUF LLM, planner)
                 │ tool calling
                 ▼
              Tool Registry ──▶ memory tools ──▶ geomemory public API
                            ├─▶ gis tools (rasterio/geopandas, lazy)
                            ├─▶ CLI runner (external libs)
                            └─▶ advisor tools (report/recommend)
                 │
                 ▼
            Playbooks (SKILL.md) — replay common workflows fast
```
