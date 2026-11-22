#!/usr/bin/env bash
# GeoMind — one-command local dev launcher.
# Starts the FastAPI gateway (:8000) and the Vite web app (:5173) together.
# Stop with Ctrl+C.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

CONDA_ENV="${CONDA_ENV:-geospatial}"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda not found. Install Miniforge/conda first." >&2
  exit 1
fi
if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm not found. Install pnpm first (npm i -g pnpm)." >&2
  exit 1
fi
if [ ! -d "apps/web/node_modules" ]; then
  echo "[GeoMind] installing web deps..."
  (cd apps/web && pnpm install)
fi

echo "[GeoMind] starting gateway on http://localhost:8000 ..."
conda run -n "$CONDA_ENV" uvicorn geofront_api.main:app --host "${GEOMIND_BIND:-127.0.0.1}" --port 8000 &
GW_PID=$!

# wait for gateway health
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "[GeoMind] gateway ready."
    break
  fi
  sleep 1
done

echo "[GeoMind] starting web on http://localhost:5173 ..."
(cd apps/web && pnpm dev) &
WEB_PID=$!

trap 'echo; echo "[GeoMind] stopping..."; kill $GW_PID $WEB_PID 2>/dev/null || true' INT TERM EXIT
wait $WEB_PID