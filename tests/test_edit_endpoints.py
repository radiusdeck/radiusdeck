from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from radiusdeck.integrations.null_reload_client import NullReloadClient
from radiusdeck.main import app
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.web.deps import get_radius_service


@pytest.fixture()
def config_path(tmp_path: Path) -> Path:
    p = tmp_path / "clients.conf"
    p.write_text(
        """client LOCAL {
    # header comment
    ipaddr = 127.0.0.1 # inline ip
    secret = testing123

    shortname = old # inline short
    limit {
        max_connections = "16"
        lifetime = 0
    }
}
""",
        encoding="utf-8",
    )
    return p


@pytest.fixture()
def client(config_path: Path) -> Generator[TestClient, None, None]:
    service = RadiusService(
        ClientsConfStore(str(config_path)), reloader=NullReloadClient()
    )

    def override(_: Request) -> RadiusService:
        return service

    app.dependency_overrides[get_radius_service] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_radius_service, None)


def test_get_edit_form_renders_edit_mode(client_as_admin_complex: TestClient) -> None:
    resp = client_as_admin_complex.get("/ui/clients/LOCAL/edit-form")
    assert resp.status_code == 200
    html = resp.text

    assert 'id="form-card"' in html
    assert 'id="edit-form"' in html

    # name readonly
    assert 'name="name"' in html
    assert "readonly" in html

    # node ids must exist for existing elements
    assert 'data-node-id="a:0"' in html  # shortname
    assert 'data-node-id="b:0"' in html  # limit block
    assert 'data-node-id="b:0/a:0"' in html  # max_connections


def test_get_create_form_renders_create_mode(client_as_admin: TestClient) -> None:
    resp = client_as_admin.get("/ui/clients/create-form")
    assert resp.status_code == 200
    html = resp.text

    assert 'id="form-card"' in html
    assert 'id="add-form"' in html
    assert 'hx-post="/ui/clients/add-tree"' in html


def test_put_tree_success_updates_file_and_triggers_event(
    client_as_admin: TestClient, config_path: Path
) -> None:
    payload = {
        "name": "LOCAL",
        "ipaddr": "127.0.0.2",
        "secret": "newsecret",
        "assignments": [
            {"id": "a:0", "key": "shortname", "value": "new"},
        ],
        "blocks": [
            {
                "id": "b:0",
                "kind": "limit",
                "name": None,
                "assignments": [
                    {"id": "b:0/a:0", "key": "max_connections", "value": "32"},
                    {"id": "b:0/a:1", "key": "lifetime", "value": "0"},
                ],
                "blocks": [],
            }
        ],
    }

    resp = client_as_admin.put(
        "/ui/clients/LOCAL/tree", data={"payload_json": json.dumps(payload)}
    )
    assert resp.status_code == 200

    html = resp.text

    # Main part = create form (form reset)
    assert 'id="add-form"' in html

    # HX-Trigger to reload table row via JS
    trigger_header = resp.headers.get("hx-trigger", "")
    assert "clientUpdated" in trigger_header

    trigger_data = json.loads(trigger_header)
    assert trigger_data["clientUpdated"] == "LOCAL"
    assert trigger_data["reloadResult"]["status"] == "skipped"

    # File updated
    text = config_path.read_text(encoding="utf-8")
    assert "ipaddr = 127.0.0.2" in text
    assert "secret = newsecret" in text
    assert "shortname = new" in text

    # Preserved comments/blanks
    assert "# header comment" in text
    assert "# inline ip" in text
    assert "# inline short" in text


def test_put_tree_invalid_node_id_returns_400_and_edit_form(
    client_as_admin: TestClient,
) -> None:
    payload = {
        "name": "LOCAL",
        "ipaddr": "127.0.0.1",
        "secret": "testing123",
        "assignments": [{"id": "a:99", "key": "shortname", "value": "x"}],
        "blocks": [
            {
                "id": "b:0",
                "kind": "limit",
                "name": None,
                "assignments": [
                    {"id": "b:0/a:0", "key": "max_connections", "value": "16"},
                ],
                "blocks": [],
            },
        ],
    }

    resp = client_as_admin.put(
        "/ui/clients/LOCAL/tree", data={"payload_json": json.dumps(payload)}
    )
    assert resp.status_code == 400

    html = resp.text
    assert 'id="edit-form"' in html
    assert "Unknown node id" in html or "node id" in html
