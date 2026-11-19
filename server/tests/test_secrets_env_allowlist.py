import json
import os
from pathlib import Path

import pytest

from geofront_api.state import get_state


@pytest.mark.parametrize("set_key", [False, True])
def test_settings_reject_disallowed_env_name(client, open_ws, set_key):
    before = os.environ.get("PATH")
    body = {"llm_api_key_env": "PATH"}
    if set_key:
        body["llm_api_key"] = "test-value"
    response = client.put("/api/v1/workspace/settings", json=body)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_key_env"
    assert os.environ.get("PATH") == before


@pytest.mark.parametrize("value", ["test-value", ""])
def test_settings_accept_allowed_env_name(client, open_ws, monkeypatch, value):
    name = "GEOMEMORY_TEST_KEY"
    monkeypatch.setenv(name, "previous-value")
    response = client.put(
        "/api/v1/workspace/settings", json={"llm_api_key_env": f" {name} ", "llm_api_key": value}
    )
    assert response.status_code == 200, response.text
    assert response.json()["llm_api_key_env"] == name
    assert "llm_api_key" not in response.json()
    assert os.environ[name] == value


def test_open_workspace_filters_secret_env_names(client, open_ws, monkeypatch, caplog):
    name = "GEOMEMORY_TEST_KEY"
    monkeypatch.setenv(name, "previous-value")
    previous_root = os.environ.get("GEOFOND_WORKSPACE")
    response = client.put("/api/v1/workspace/settings", json={"persist_secrets": True})
    assert response.status_code == 200, response.text
    path = Path(get_state().require_workspace().path)
    secrets = path / ".geofront" / "secrets.json"
    secrets.parent.mkdir(exist_ok=True)
    secrets.write_text(
        json.dumps({"GEOFOND_WORKSPACE": "unused-test-path", name: "test-value"}), encoding="utf-8"
    )
    assert client.post("/api/v1/workspace/close").status_code == 200
    response = client.post("/api/v1/workspace/open", json={"path": str(path)})
    assert response.status_code == 200, response.text
    assert os.environ[name] == "test-value"
    assert os.environ.get("GEOFOND_WORKSPACE") == previous_root
    assert "ignoring non-conforming env var name 'GEOFOND_WORKSPACE'" in caplog.text
    assert "test-value" not in caplog.text
