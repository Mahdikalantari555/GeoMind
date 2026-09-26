from __future__ import annotations

import concurrent.futures
import sqlite3
from typing import Any

from fastapi.testclient import TestClient
from geofront_api.state import get_state


def test_concurrent_writes_serialize(gateway: TestClient) -> None:
    """Requirement 5 (Task 6.1): N concurrent POST /api/v1/asset serialize with zero locked DB errors."""
    concurrency = 8

    def _post(i: int) -> tuple[int, dict[str, Any]]:
        resp = gateway.post(
            "/api/v1/asset",
            json={
                "filename": f"concurrent_doc_{i}.txt",
                "content": f"Document content for worker {i} describing remote sensing indices.",
            },
        )
        return resp.status_code, resp.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(_post, range(concurrency)))

    # Verify all succeeded with 201 and distinct IDs
    status_codes = [status for status, _ in results]
    assert all(code == 201 for code in status_codes), f"Not all requests returned 201: {status_codes}"

    asset_ids = [body["id"] for _, body in results]
    assert len(set(asset_ids)) == concurrency, f"Duplicate asset IDs returned: {asset_ids}"

    # Verify SQLite asset table has exactly N rows
    ws = get_state().require_workspace()
    conn = sqlite3.connect(ws.path / "geomemory.db")
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM asset")
        count = cur.fetchone()[0]
        assert count == concurrency, f"Expected {concurrency} assets in DB, found {count}"
    finally:
        conn.close()
