#!/usr/bin/env bash
set -euo pipefail

# GeoMind Studio one-click launcher
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATEWAY_PORT=8000
STUDIO_PORT=5173

cleanup() {
    echo ""
    echo "[GeoMind] Shutting down services..."
    kill 0 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

echo "==========================================="
echo "        Launching GeoMind Studio           "
echo "==========================================="

# 1. Start FastAPI Gateway in background
echo "[1/2] Starting FastAPI gateway on port ${GATEWAY_PORT}..."
conda run --no-capture-output -n geospatial uvicorn geofront_api.main:app --port "${GATEWAY_PORT}" &
GATEWAY_PID=$!

# Wait briefly for gateway health
echo "Waiting for gateway to be ready..."
for i in {1..30}; do
    if curl -s "http://127.0.0.1:${GATEWAY_PORT}/api/v1/health" >/dev/null 2>&1; then
        echo "✓ Gateway online."
        break
    fi
    sleep 0.5
done

# 2. Start SvelteKit Studio dev server and open browser
echo "[2/2] Starting Studio web app on port ${STUDIO_PORT}..."
cd "${ROOT_DIR}/apps/studio"
pnpm dev --open --port "${STUDIO_PORT}" &
STUDIO_PID=$!

echo ""
echo "GeoMind Studio running at: http://localhost:${STUDIO_PORT}"
echo "Press Ctrl+C to stop all services."
echo ""

wait
