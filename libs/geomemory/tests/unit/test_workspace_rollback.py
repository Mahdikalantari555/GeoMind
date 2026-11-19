import sqlite3
from pathlib import Path
from typing import Any

import pytest

from geomemory import GeoMemory
from geomemory.core.models import QAResult


@pytest.mark.parametrize(
    ("suffix", "payload"),
    [
        (".tif", {"scene": {"bbox": [0, 0, 1, 1]}, "tiles": [{"window": {}}]}),
        (".geojson", {"layer": {"bbox": [0, 0, 1, 1]}}),
    ],
)
def test_ingest_rolls_back_spatial_writes(
    temp_workspace: GeoMemory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
    payload: dict[str, Any],
) -> None:
    ws = temp_workspace
    col = ws.create_collection("input")
    source = tmp_path / f"asset{suffix}"
    source.write_bytes(b"test spatial asset")
    monkeypatch.setattr(
        ws,
        "_parse_spatial_source",
        lambda *_: (
            [{"segment_type": "paragraph", "text": "test segment", "locator": {}}],
            payload,
        ),
    )
    ws.conn.execute("""
        CREATE TEMP TRIGGER reject_revision BEFORE UPDATE OF current_revision_id ON asset
        BEGIN SELECT RAISE(ABORT, 'test ingest failure'); END
    """)

    with pytest.raises(sqlite3.IntegrityError, match="test ingest failure"):
        ws.ingest(source, col.id)

    assert not ws.conn.in_transaction
    ws.create_collection("unrelated write")
    for table in (
        "asset",
        "asset_revision",
        "segment",
        "raster_scene",
        "raster_tile",
        "vector_layer",
        "spatial_entity",
        "spatial_index",
    ):
        assert ws.conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_qa_rolls_back_conversation_and_turns(temp_workspace: GeoMemory) -> None:
    ws = temp_workspace
    ws.conn.execute("""
        CREATE TEMP TRIGGER reject_answer BEFORE INSERT ON answer
        BEGIN SELECT RAISE(ABORT, 'test answer failure'); END
    """)

    with pytest.raises(sqlite3.IntegrityError, match="test answer failure"):
        ws._persist_answer("question", QAResult(text="answer", model="stub"))

    assert not ws.conn.in_transaction
    ws.create_collection("unrelated write")
    for table in ("conversation", "turn", "answer", "citation"):
        assert ws.conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
