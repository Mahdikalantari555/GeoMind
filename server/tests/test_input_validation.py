from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from geomemory import GeoMemory

from geofront_api.services.agent import get_agent_service


def assert_rejected(response, code: str, status: int = 422) -> None:
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize("route", ["ingest", "asset"])
@pytest.mark.parametrize("filename", ["../outside.txt", "C:/outside.txt", r"nested\outside.txt"])
def test_multipart_requires_bare_filename(client, open_ws, route, filename):
    # Multipart parsers can normalize old-browser Windows paths before a
    # handler sees them; these variants reach the handler unchanged.
    response = client.post(
        f"/api/v1/{route}",
        files={"file": (filename, b"example")},
        data={"collection_id": "unused"},
    )
    assert_rejected(response, "invalid_filename")


@pytest.mark.parametrize("route", ["ingest/bytes", "asset"])
@pytest.mark.parametrize("filename", ["../outside.txt", r"C:\outside.txt", ".hidden.txt"])
def test_json_requires_bare_filename(client, open_ws, route, filename):
    response = client.post(
        f"/api/v1/{route}",
        json={"filename": filename, "data_base64": "aGk=", "collection_id": "unused"},
    )
    assert_rejected(response, "invalid_filename")


def test_geojson_name_requires_bare_filename(client, open_ws):
    response = client.post(
        "/api/v1/asset", json={"type": "FeatureCollection", "name": "../outside", "features": []}
    )
    assert_rejected(response, "invalid_filename")


def test_playbook_names_reject_path_components(client: TestClient, open_ws):
    response = client.get("/api/v1/agent/playbooks/..%2F..%2Fsettings")
    assert_rejected(response, "invalid_playbook_name")
    response = client.post(
        "/api/v1/agent/playbooks/save", json={"name": "../outside", "content": "unused"}
    )
    assert_rejected(response, "invalid_playbook_name")


def test_playbook_read_rejects_escaping_symlink(client, open_ws, tmp_path):
    root = get_agent_service().settings.workspace / "playbooks"
    root.mkdir(exist_ok=True)
    outside = tmp_path / "outside.md"
    outside.write_text("outside playbooks", encoding="utf-8")
    try:
        (root / "linked.md").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks is not available")
    response = client.get("/api/v1/agent/playbooks/linked")
    assert_rejected(response, "path_outside_sandbox", status=403)


def test_feedback_export_ignores_client_directory(client, open_ws, tmp_path, monkeypatch):
    requested_dir = tmp_path / "client-supplied"
    used_dirs: list[Path] = []

    def export(ws: GeoMemory, task_type: str, output_dir: Path) -> Path:
        used_dirs.append(output_dir)
        assert output_dir.is_dir()
        path = output_dir / f"{task_type}.jsonl"
        path.write_text('{}\n', encoding="utf-8")
        return path

    monkeypatch.setattr(GeoMemory, "export_dataset", export)
    response = client.get(
        "/api/v1/feedback/export",
        params={"task_type": "qa", "output_dir": str(requested_dir)},
    )
    assert response.status_code == 200, response.text
    assert response.text == "{}\n"
    assert "qa.jsonl" in response.headers["content-disposition"]
    assert not requested_dir.exists()
    assert len(used_dirs) == 1 and not used_dirs[0].exists()


@pytest.mark.parametrize("name", ["../../outside", "C:outside", "hidden..name", " "])
def test_workspace_create_requires_safe_name(client, tmp_path, name):
    base = tmp_path / "base"
    response = client.post("/api/v1/workspace/create", json={"path": str(base), "name": name})
    assert_rejected(response, "invalid_workspace_name")
    assert not base.exists()


def test_asset_rejects_malformed_json(client, open_ws):
    response = client.post(
        "/api/v1/asset", content="{", headers={"content-type": "application/json"}
    )
    assert_rejected(response, "invalid_json")


@pytest.mark.parametrize("value", ["not-base64!!", {"not": "a string"}])
def test_asset_rejects_malformed_base64(client, open_ws, value):
    response = client.post("/api/v1/asset", json={"data_base64": value})
    assert_rejected(response, "invalid_base64")
