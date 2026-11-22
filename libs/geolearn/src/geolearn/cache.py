import io
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from geolearn.db import connect_db


class EmbeddingCache:
    def __init__(self, workspace_dir: str | Path) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.workspace_dir / "geolearn.db"
        # k-NN used to reload + deserialize every blob from SQLite on each
        # query. Keep the matrix in memory, invalidated by a cheap signature
        # so external writers are still noticed (P-070).
        self._nn_signature: tuple[int, str | None] | None = None
        self._nn_ids: list[str] = []
        self._nn_matrix: np.ndarray | None = None
        self._init_db()

    def _signature(self, conn: Any) -> tuple[int, str | None]:
        row = conn.execute(
            "SELECT COUNT(*), MAX(created_at) FROM embedding_cache"
        ).fetchone()
        return int(row[0]), (str(row[1]) if row[1] is not None else None)

    def _invalidate(self) -> None:
        self._nn_signature = None
        self._nn_matrix = None
        self._nn_ids = []

    def _init_db(self) -> None:
        with connect_db(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    asset_id TEXT PRIMARY KEY,
                    embedding BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    label INTEGER
                )
                """
            )
            try:
                conn.execute("ALTER TABLE embedding_cache ADD COLUMN label INTEGER")
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def insert(
        self,
        asset_id: str,
        vector: np.ndarray | list[float],
        label: int | None = None,
    ) -> None:
        vec_f32 = np.asarray(vector, dtype=np.float32)
        buf = io.BytesIO()
        joblib.dump(vec_f32, buf)
        blob = buf.getvalue()
        now = datetime.now(timezone.utc).isoformat()
        with connect_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO embedding_cache (asset_id, embedding, created_at, label)
                VALUES (?, ?, ?, ?)
                """,
                (asset_id, blob, now, label),
            )
            conn.commit()
        self._invalidate()

    def set_label(self, asset_id: str, label: int) -> None:
        with connect_db(self.db_path) as conn:
            conn.execute(
                "UPDATE embedding_cache SET label = ? WHERE asset_id = ?",
                (label, asset_id),
            )
            conn.commit()

    def get_label(self, asset_id: str) -> int | None:
        with connect_db(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT label FROM embedding_cache WHERE asset_id = ?", (asset_id,)
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                return None
            return int(row[0])

    def lookup(self, asset_id: str) -> np.ndarray | None:
        with connect_db(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT embedding FROM embedding_cache WHERE asset_id = ?", (asset_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            buf = io.BytesIO(row[0])
            arr = joblib.load(buf)
            return np.asarray(arr, dtype=np.float32)

    def nn_lookup(
        self, vector: np.ndarray | list[float], k: int = 3
    ) -> list[tuple[str, float]]:
        vec_f32 = np.asarray(vector, dtype=np.float32)
        with connect_db(self.db_path) as conn:
            signature = self._signature(conn)
            if signature != self._nn_signature or self._nn_matrix is None:
                ids: list[str] = []
                rows: list[np.ndarray] = []
                for asset_id, blob in conn.execute(
                    "SELECT asset_id, embedding FROM embedding_cache ORDER BY asset_id"
                ):
                    rows.append(np.asarray(joblib.load(io.BytesIO(blob)), dtype=np.float32))
                    ids.append(asset_id)
                if rows:
                    width = max(row.size for row in rows)
                    matrix = np.zeros((len(rows), width), dtype=np.float32)
                    for i, row in enumerate(rows):
                        matrix[i, : row.size] = row.ravel()
                else:
                    matrix = np.empty((0, 0), dtype=np.float32)
                self._nn_ids = ids
                self._nn_matrix = matrix
                self._nn_signature = signature

        matrix = self._nn_matrix
        if matrix is None or matrix.shape[0] == 0:
            return []
        width = min(vec_f32.size, matrix.shape[1])
        probe = np.zeros(matrix.shape[1], dtype=np.float32)
        probe[:width] = vec_f32.ravel()[:width]
        # One vectorised distance computation instead of one DB row + joblib
        # load per candidate.
        padded = matrix
        dists = np.linalg.norm(padded - probe, axis=1)
        order = np.argsort(dists)[:k]
        return [(self._nn_ids[int(i)], float(dists[int(i)])) for i in order]
