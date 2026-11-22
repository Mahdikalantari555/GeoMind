# Gateway — FastAPI facade over geomemory + geoagent
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for rasterio/geopandas optional (kept minimal for core)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential \
  && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests first for layer caching
COPY libs/geodomain/pyproject.toml libs/geodomain/README.md* libs/geodomain/
COPY libs/geospatial_core/pyproject.toml libs/geospatial_core/README.md* libs/geospatial_core/
COPY libs/data_engine/pyproject.toml libs/data_engine/README.md* libs/data_engine/
COPY libs/geolearn/pyproject.toml libs/geolearn/README.md* libs/geolearn/
COPY libs/geomemory/pyproject.toml libs/geomemory/README.md* libs/geomemory/
COPY libs/geoagent/pyproject.toml libs/geoagent/README.md* libs/geoagent/
COPY server/pyproject.toml server/

# Copy sources (install needs package data)
COPY libs/geodomain/src libs/geodomain/src
COPY libs/geospatial_core/src libs/geospatial_core/src
COPY libs/data_engine/src libs/data_engine/src
COPY libs/geolearn/src libs/geolearn/src
COPY libs/geomemory/src libs/geomemory/src
COPY libs/geomemory/geomemorytest libs/geomemory/geomemorytest
COPY libs/geoagent/src libs/geoagent/src
COPY libs/geoagent/tests libs/geoagent/tests
COPY server/src server/src

# The gateway imports Data Engine visualization and STAC support; Conda
# normally supplies these runtime dependencies, but the slim image does not.
RUN pip install --upgrade pip \
 && pip install "matplotlib>=3.7" "pystac-client>=0.7" "planetary-computer>=1.0" \
 && pip install -e libs/geodomain \
 && pip install -e libs/geospatial_core \
 && pip install -e libs/data_engine \
 && pip install -e libs/geolearn \
 && pip install -e libs/geomemory \
 && pip install -e libs/geoagent \
 && pip install -e server

EXPOSE 8000

ENV GEOFOND_WORKSPACE=/workspace \
    GEOMEMORY_LLM_API_KEY="" \
    PYTHONPATH=/app/server/src:/app/libs/geomemory/src:/app/libs/geoagent/src

# Single worker per SPEC (SQLite single writer). Bind loopback by default;
# compose opts into 0.0.0.0 because container port mapping provides isolation.
CMD ["sh", "-c", "uvicorn geofront_api.main:app --host \"${GEOMIND_BIND:-127.0.0.1}\" --port \"${GEOMIND_PORT:-8000}\" --workers 1"]
