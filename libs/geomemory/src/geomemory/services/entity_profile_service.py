"""EntityProfileService — seeded-alias entity profiles over candidate memories.

Entity linking is alias-based (design D3): a candidate memory whose content
contains an alias (case-insensitive substring) is linked to that entity.
No NER. Users extend the alias index via the workspace settings key
``entity_alias_index`` (JSON array of strings); the in-code
:data:`DEFAULT_ENTITY_ALIASES` list is the fallback seed.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from geomemory.core.models import CandidateMemory
from geomemory.feedback.candidate_memory import _row_to_cm

DEFAULT_ENTITY_ALIASES: list[str] = [
    "OPTRAM",
    "NDVI",
    "Landsat",
    "Sentinel-1",
    "Sentinel-2",
    "salinity",
    "Khuzestan",
    "Farm 183",
]


class EntityProfileService:
    """Build entity profiles by joining candidate memories to entity aliases."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.aliases = self._load_aliases()

    def _load_aliases(self) -> list[str]:
        """Read ``entity_alias_index`` from workspace.settings, else the seed list."""
        row = self.conn.execute("SELECT settings FROM workspace LIMIT 1").fetchone()
        if row is not None:
            try:
                settings = json.loads(row["settings"] or "{}")
            except (TypeError, ValueError):
                settings = {}
            aliases = settings.get("entity_alias_index")
            if isinstance(aliases, list) and aliases:
                return [str(a) for a in aliases]
        return list(DEFAULT_ENTITY_ALIASES)

    def _entity_kind(self, entity_name: str) -> str | None:
        row = self.conn.execute(
            "SELECT kind FROM entity WHERE name = ? COLLATE NOCASE LIMIT 1", (entity_name,)
        ).fetchone()
        return str(row["kind"]) if row is not None else None

    def _related_via_relations(self, entity_name: str) -> set[str]:
        """Entities joined to this one through the relation table."""
        related: set[str] = set()
        entity_rows = self.conn.execute(
            "SELECT id FROM entity WHERE name = ? COLLATE NOCASE", (entity_name,)
        ).fetchall()
        for entity_row in entity_rows:
            entity_id = str(entity_row["id"])
            relations = self.conn.execute(
                "SELECT source_id, target_id FROM relation WHERE source_id = ? OR target_id = ?",
                (entity_id, entity_id),
            ).fetchall()
            for rel in relations:
                other_id = (
                    str(rel["target_id"]) if str(rel["source_id"]) == entity_id else str(rel["source_id"])
                )
                other = self.conn.execute(
                    "SELECT name FROM entity WHERE id = ?", (other_id,)
                ).fetchone()
                if other is not None:
                    related.add(str(other["name"]))
        return related

    def _related_via_cooccurrence(self, matched: list[CandidateMemory]) -> set[str]:
        """Other known aliases mentioned in the same memories (alias collision keeps both)."""
        related: set[str] = set()
        for cm in matched:
            content = cm.content.lower()
            for alias in self.aliases:
                if alias.lower() in content:
                    related.add(alias)
        return related

    def get_profile(self, entity_name: str) -> dict[str, Any]:
        """Return {name, kind, current_beliefs, history, related_entities} for an entity."""
        needle = entity_name.strip().lower()
        known = {alias.strip().lower() for alias in self.aliases}
        if not needle or needle not in known:
            return {
                "name": entity_name,
                "kind": None,
                "current_beliefs": [],
                "history": [],
                "related_entities": [],
            }

        matched = [
            cm
            for cm in (_row_to_cm(r) for r in self.conn.execute("SELECT * FROM candidate_memory").fetchall())
            if needle in cm.content.lower()
        ]
        current = [cm for cm in matched if cm.superseded_by is None and cm.state != "rejected"]
        history = sorted(matched, key=lambda cm: (cm.effective_observed_at, cm.created_at))

        related = self._related_via_relations(entity_name) | self._related_via_cooccurrence(matched)
        related = {r for r in related if r.lower() != needle}

        return {
            "name": entity_name,
            "kind": self._entity_kind(entity_name),
            "current_beliefs": current,
            "history": history,
            "related_entities": sorted(related),
        }
