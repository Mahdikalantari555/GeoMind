"""Unit tests for asset pagination."""

from __future__ import annotations

from geomemory.core.models import Asset
from geomemory.storage.repositories.asset_repo import AssetRepository


def test_asset_pagination_repository_and_workspace(temp_workspace):
    repo = AssetRepository(temp_workspace.conn)
    col = temp_workspace.create_collection("Test")
    col_id = col.id

    for i in range(25):
        repo.insert(
            Asset(
                id=f"ast_{i:03d}",
                collection_id=col_id,
                kind="document",
                current_revision_id=None,
            )
        )

    # Repository list_all with pagination
    first_ten = repo.list_all(limit=10, offset=0)
    assert len(first_ten) == 10
    assert first_ten[0].id == "ast_000"
    assert first_ten[-1].id == "ast_009"

    next_ten = repo.list_all(limit=10, offset=10)
    assert len(next_ten) == 10
    assert next_ten[0].id == "ast_010"
    assert next_ten[-1].id == "ast_019"

    last_five = repo.list_all(limit=10, offset=20)
    assert len(last_five) == 5
    assert last_five[0].id == "ast_020"
    assert last_five[-1].id == "ast_024"

    # Workspace list_assets with pagination
    ws_first = temp_workspace.list_assets(offset=0, limit=5)
    assert len(ws_first) == 5
    assert ws_first[0].id == "ast_000"

    ws_second = temp_workspace.list_assets(offset=5, limit=5)
    assert len(ws_second) == 5
    assert ws_second[0].id == "ast_005"

    assert temp_workspace.get_workspace_path() == temp_workspace.path
