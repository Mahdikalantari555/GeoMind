from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from geolearn.cache import EmbeddingCache
from geolearn.db import connect_db
from geolearn.persistence import ClassifierStore
from geolearn.ports import CandidateMemoryProvider

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int, int], None]


class TrainingPipeline:
    """Incremental training over accepted feedback candidate memories.

    Candidates come from a host-injected :class:`CandidateMemoryProvider`
    (structurally, the ``geomemory.GeoMemory`` facade). geolearn itself
    never opens another lib's storage.
    """

    def __init__(
        self,
        geolearn_dir: str | Path,
        candidate_source: CandidateMemoryProvider | None = None,
    ) -> None:
        self.geolearn_dir = Path(geolearn_dir)
        self.candidate_source = candidate_source
        self.geolearn_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.geolearn_dir / "geolearn.db"
        self.cache = EmbeddingCache(self.geolearn_dir)
        self.store = ClassifierStore(self.geolearn_dir)
        self._init_db()

    def _init_db(self) -> None:
        with connect_db(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trained_candidates (
                    candidate_id TEXT PRIMARY KEY,
                    trained_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS training_log (
                    id TEXT PRIMARY KEY,
                    key_crop TEXT NOT NULL,
                    key_region TEXT NOT NULL,
                    n_samples INTEGER NOT NULL,
                    trained_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _get_pending_candidates(
        self, feedback_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        if self.candidate_source is None:
            return []

        with connect_db(self.db_path) as conn:
            cursor = conn.execute("SELECT candidate_id FROM trained_candidates")
            trained_ids = {row[0] for row in cursor}

        try:
            candidate_objs = list(
                self.candidate_source.list_candidate_memories(
                    states=["verified", "supported"]
                )
            )
        except Exception as exc:  # noqa: BLE001 — provider failures must not crash training
            logger.warning("candidate provider failed: %s", exc)
            return []

        candidates: list[dict[str, Any]] = []
        for cm in candidate_objs:
            cid = cm.id
            if cid in trained_ids:
                continue
            if feedback_ids is not None and cid not in feedback_ids:
                continue

            try:
                data = json.loads(cm.content)
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.warning("skipping candidate %s: content is not valid JSON", cid)
                continue
            if not isinstance(data, dict):
                logger.warning("skipping candidate %s: content is not a JSON object", cid)
                continue

            # A malformed label must never be silently trained as class 0 —
            # that poisons the model with a confident wrong answer (L-063).
            raw_label = data.get("label")
            if raw_label is None:
                logger.warning("skipping candidate %s: missing label", cid)
                continue
            try:
                label = int(raw_label)
            except (TypeError, ValueError):
                logger.warning("skipping candidate %s: invalid label %r", cid, raw_label)
                continue

            candidates.append({
                "id": cid,
                "asset_id": str(data.get("asset_id") or cid),
                "label": label,
                "crop_type": str(data.get("crop_type") or "unknown"),
                "region": str(data.get("region") or "global"),
            })
        return candidates

    def pending_count(self) -> dict[str, Any]:
        candidates = self._get_pending_candidates()
        by_key: dict[str, int] = {}
        for c in candidates:
            k = f"{c['crop_type']}__{c['region']}"
            by_key[k] = by_key.get(k, 0) + 1
        return {"total_pending": len(candidates), "by_key": by_key}

    def train_on_feedback(
        self,
        feedback_ids: list[str] | None = None,
        batch_size: int = 10,
        progress_cb: ProgressCallback | None = None,
    ) -> dict[str, dict[str, int]]:
        candidates = self._get_pending_candidates(feedback_ids=feedback_ids)
        if not candidates:
            return {}

        by_key_candidates: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for c in candidates:
            key = (c["crop_type"], c["region"])
            by_key_candidates.setdefault(key, []).append(c)

        keys = sorted(by_key_candidates)
        total_batches = sum(
            -(-len(by_key_candidates[key]) // max(1, batch_size)) for key in keys
        )
        batch_no = 0
        result: dict[str, dict[str, int]] = {}
        now = datetime.now(timezone.utc).isoformat()

        for key in keys:
            items = by_key_candidates[key]
            clf = self.store.get_classifier(key)
            X_list: list[np.ndarray] = []
            y_list: list[int] = []
            valid_cids: list[str] = []

            for item in items:
                emb = self.cache.lookup(item["asset_id"])
                if emb is None:
                    continue
                X_list.append(emb)
                y_list.append(item["label"])
                valid_cids.append(item["id"])

            if not X_list:
                continue

            stage_key = f"{key[0]}__{key[1]}"
            for i in range(0, len(X_list), batch_size):
                batch_X = np.array(X_list[i : i + batch_size], dtype=np.float32)
                batch_y = np.array(y_list[i : i + batch_size], dtype=np.int64)
                clf.partial_fit(batch_X, batch_y)
                batch_no += 1
                if progress_cb is not None:
                    try:
                        progress_cb(stage_key, batch_no, max(1, total_batches))
                    except Exception:
                        logger.debug("progress_cb raised", exc_info=True)

            crop, region = key
            with connect_db(self.db_path) as conn:
                cur = conn.execute(
                    "SELECT n_samples FROM classifier_state WHERE key_crop = ? AND key_region = ?",
                    (crop, region),
                )
                row = cur.fetchone()
                prior_samples = row[0] if row else 0
                total_samples = prior_samples + len(X_list)

            self.store.save_classifier(
                key, clf, n_samples=total_samples, feedback_ids=valid_cids
            )

            with connect_db(self.db_path) as conn:
                for cid in valid_cids:
                    conn.execute(
                        "INSERT OR IGNORE INTO trained_candidates (candidate_id, trained_at) VALUES (?, ?)",
                        (cid, now),
                    )
                conn.execute(
                    "INSERT INTO training_log (id, key_crop, key_region, n_samples, trained_at) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), crop, region, len(X_list), now),
                )
                conn.commit()

            result[stage_key] = {
                "samples_trained": len(X_list),
                "total_n_samples": total_samples,
            }

        return result

    def run(
        self,
        feedback_ids: list[str] | None = None,
        batch_size: int = 10,
        progress_cb: ProgressCallback | None = None,
    ) -> dict[str, dict[str, int]]:
        """Run incremental training cycle over pending feedback candidates."""
        return self.train_on_feedback(
            feedback_ids=feedback_ids, batch_size=batch_size, progress_cb=progress_cb
        )

    def rollback_feedback(
        self, revoked_feedback_id: str, reason: str = ""
    ) -> list[tuple[tuple[str, ...], int]]:
        """Roll back classifier models that incorporated the revoked candidate feedback."""
        rolled_back = self.store.rollback_feedback(revoked_feedback_id, reason=reason)
        if not rolled_back:
            return []

        cids_to_remove: set[str] = {revoked_feedback_id}
        with connect_db(self.db_path) as conn:
            for key, target_ver in rolled_back:
                crop = key[0]
                region = key[1]
                cursor = conn.execute(
                    """
                    SELECT feedback_ids FROM model_versions
                    WHERE key_crop = ? AND key_region = ? AND version > ?
                    """,
                    (crop, region, target_ver),
                )
                for (fb_json,) in cursor.fetchall():
                    if fb_json:
                        try:
                            fids = json.loads(fb_json)
                            cids_to_remove.update(fids)
                        except Exception as e:  # noqa: BLE001
                            logger.warning("Failed to parse feedback_ids JSON: %s", e)

            for cid in cids_to_remove:
                conn.execute(
                    "DELETE FROM trained_candidates WHERE candidate_id = ?",
                    (cid,),
                )
            conn.commit()

        return rolled_back
