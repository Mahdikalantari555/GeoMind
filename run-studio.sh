#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
for cmd in conda pnpm curl; do
  command -v "$cmd" >/dev/null || { echo "Missing $cmd. Install $cmd and follow README.md Quickstart before launching." >&2; exit 1; }
done
pids=()
cleanup() { for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT
trap 'exit 130' INT TERM
conda run --no-capture-output -n "${GEOMIND_CONDA_ENV:-geo}" uvicorn geofront_api.main:app --port 8000 &
gateway=$!; pids+=("$gateway")
ready=false
for _ in {1..60}; do
  kill -0 "$gateway" 2>/dev/null || { echo 'Gateway exited during startup' >&2; exit 1; }
  if curl -fsS --max-time 2 http://127.0.0.1:8000/api/v1/health >/dev/null 2>&1; then ready=true; break; fi
  sleep .5
done
$ready || { echo 'Gateway did not become healthy on port 8000' >&2; exit 1; }
cd apps/studio
pnpm dev --port 5174 --strictPort &
pids+=("$!")
wait -n
