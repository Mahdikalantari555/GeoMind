"""Collections capability of the workspace facade."""

from __future__ import annotations

from geomemory.core.events import (
    COLLECTION_CREATED,
    DomainEvent,
)
from geomemory.core.models import (
    Collection,
)
from geomemory.core.workspace_internals import InternalsMixin


class CollectionsMixin(InternalsMixin):
    # ── Collections ──────────────────────────────────────────────────────────

    def create_collection(self, name: str, description: str = "") -> Collection:
        """Create a collection, emitting a ``collection_created`` event."""
        collection = Collection(
            workspace_id=self._workspace_id(), name=name, description=description
        )
        self.conn.execute(
            "INSERT INTO collection (id, workspace_id, name, description, created_at, archived) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (collection.id, collection.workspace_id, collection.name, collection.description, collection.created_at),
        )
        self.conn.commit()
        self.events.emit(
            DomainEvent(
                event_type=COLLECTION_CREATED,
                entity_id=collection.id,
                payload={"name": name, "workspace_id": self._workspace_id()},
            )
        )
        return collection

    def list_collections(self) -> list[Collection]:
        """Return all non-archived collections."""
        rows = self.conn.execute(
            "SELECT * FROM collection WHERE archived = 0 ORDER BY created_at"
        ).fetchall()
        return [Collection(**dict(r)) for r in rows]

    def get_collection(self, collection_id: str) -> Collection | None:
        """Return a collection by id, or None."""
        row = self.conn.execute(
            "SELECT * FROM collection WHERE id = ? AND archived = 0", (collection_id,)
        ).fetchone()
        return Collection(**dict(row)) if row is not None else None

    def archive_collection(self, collection_id: str) -> bool:
        """Soft-delete a collection. Returns True if archived."""
        cur = self.conn.execute(
            "UPDATE collection SET archived = 1 WHERE id = ?", (collection_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0

