from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from radiusdeck.integrations.null_reload_client import NullReloadClient
from radiusdeck.lib.fr_parser import parse_clients_conf
from radiusdeck.lib.fr_parser.ast import Block
from radiusdeck.lib.fr_parser.ops import find_client as find_client_in_nodes
from radiusdeck.lib.fr_parser.ops import get_assignment
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.web.deps import get_radius_service
from radiusdeck.web.endpoints import ui_clients


def _make_app(service: RadiusService) -> FastAPI:
    app = FastAPI()
    app.include_router(ui_clients.router, prefix="/ui")

    def _override(_: Request) -> RadiusService:
        return service

    app.dependency_overrides[get_radius_service] = _override
    return app


def _read_nodes(path: Path) -> list[Any]:
    return parse_clients_conf(path.read_text(encoding="utf-8"))


def _find_child_block(parent: Block, kind: str) -> Block | None:
    for ch in parent.children:
        if isinstance(ch, Block) and ch.kind == kind:
            return ch
    return None


@pytest.fixture()
def clients_conf_path(tmp_path: Path) -> Path:
    p = tmp_path / "clients.conf"
    p.write_text("", encoding="utf-8")
    return p


@pytest.fixture()
def service(clients_conf_path: Path) -> RadiusService:
    store = ClientsConfStore(str(clients_conf_path))
    return RadiusService(store, reloader=NullReloadClient())


@pytest.fixture()
def client(service: RadiusService) -> TestClient:
    app = _make_app(service)
    return TestClient(app)


def test_assignment_row_endpoint_renders_assignment_row(
    client_as_admin: TestClient,
) -> None:
    resp = client_as_admin.get("/ui/clients/assignment-row")
    assert resp.status_code == 200
    assert "assignment-row" in resp.text
    assert "assignment-key" in resp.text
    assert "assignment-value" in resp.text


def test_block_form_endpoint_renders_block_form(client_as_admin: TestClient) -> None:
    resp = client_as_admin.get("/ui/clients/block-form?depth=0")
    assert resp.status_code == 200
    assert "client-block" in resp.text
    assert "block-kind" in resp.text
    assert "block-children" in resp.text


def test_add_tree_persists_assignments_and_nested_blocks(
    client_as_admin: TestClient, clients_conf_path: Path
) -> None:
    payload = {
        "name": "wifi2",
        "ipaddr": "192.168.1.50",
        "secret": "radius_secret",
        "assignments": [
            {"key": "shortname", "value": "office"},
            {"key": "message", "value": "Hello there"},  # auto-quote expected
        ],
        "blocks": [
            {
                "kind": "limit",
                "name": None,
                "assignments": [{"key": "max_connections", "value": "16"}],
                "blocks": [],
            }
        ],
    }

    resp = client_as_admin.post(
        "/ui/clients/add-tree", data={"payload_json": json.dumps(payload)}
    )
    assert resp.status_code == 200

    # HX-Trigger should be set to success
    assert "HX-Trigger" in resp.headers
    assert "clientAdded" in resp.headers["HX-Trigger"]

    nodes = _read_nodes(clients_conf_path)
    blk = find_client_in_nodes(nodes, "wifi2")
    assert blk is not None

    ip = get_assignment(blk, "ipaddr")
    assert ip is not None
    assert ip.value == "192.168.1.50"

    sec = get_assignment(blk, "secret")
    assert sec is not None
    assert sec.value == "radius_secret"

    shortname = get_assignment(blk, "shortname")
    assert shortname is not None
    assert shortname.value == "office"

    message = get_assignment(blk, "message")
    assert message is not None
    assert message.value == "Hello there"
    assert message.quote_char == '"'

    limit_blk = _find_child_block(blk, "limit")
    assert limit_blk is not None
    mc = get_assignment(limit_blk, "max_connections")
    assert mc is not None
    assert mc.value == "16"


def test_details_endpoint_renders_nested_content(
    client_as_admin: TestClient, clients_conf_path: Path
) -> None:
    payload = {
        "name": "wifi3",
        "ipaddr": "10.0.0.1",
        "secret": "s",
        "assignments": [],
        "blocks": [
            {
                "kind": "limit",
                "name": None,
                "assignments": [{"key": "idle_timeout", "value": "30"}],
                "blocks": [],
            }
        ],
    }
    client_as_admin.post(
        "/ui/clients/add-tree", data={"payload_json": json.dumps(payload)}
    )

    resp = client_as_admin.get("/ui/clients/wifi3/details")
    assert resp.status_code == 200
    # Enough to check key words in HTML
    assert "limit" in resp.text
    assert "idle_timeout" in resp.text
    assert "30" in resp.text


def test_update_preserves_nested_blocks(
    client_as_admin: TestClient, clients_conf_path: Path
) -> None:
    payload = {
        "name": "wifi4",
        "ipaddr": "10.0.0.2",
        "secret": "old",
        "assignments": [],
        "blocks": [
            {
                "kind": "limit",
                "name": None,
                "assignments": [{"key": "lifetime", "value": "0"}],
                "blocks": [],
            }
        ],
    }
    client_as_admin.post(
        "/ui/clients/add-tree", data={"payload_json": json.dumps(payload)}
    )

    update_payload = {
        "name": "wifi4",
        "ipaddr": "10.0.0.2",
        "secret": "new",
        "assignments": [],
        "blocks": [
            {
                "id": "b:0",
                "kind": "limit",
                "name": None,
                "assignments": [
                    {"id": "b:0/a:0", "key": "lifetime", "value": "0"},
                ],
                "blocks": [],
            }
        ],
    }

    resp = client_as_admin.put(
        "/ui/clients/wifi4/tree",
        data={"payload_json": json.dumps(update_payload)},
    )
    assert resp.status_code == 200

    nodes = _read_nodes(clients_conf_path)
    blk = find_client_in_nodes(nodes, "wifi4")
    assert blk is not None

    sec = get_assignment(blk, "secret")
    assert sec is not None
    assert sec.value == "new"

    limit_blk = _find_child_block(blk, "limit")
    assert limit_blk is not None
    lifetime = get_assignment(limit_blk, "lifetime")
    assert lifetime is not None
    assert lifetime.value == "0"


def test_delete_removes_client(
    client_as_admin: TestClient, clients_conf_path: Path
) -> None:
    payload = {
        "name": "wifi5",
        "ipaddr": "10.0.0.3",
        "secret": "s",
        "assignments": [],
        "blocks": [],
    }
    client_as_admin.post(
        "/ui/clients/add-tree", data={"payload_json": json.dumps(payload)}
    )

    resp = client_as_admin.delete("/ui/clients/wifi5")
    assert resp.status_code == 200

    nodes = _read_nodes(clients_conf_path)
    assert find_client_in_nodes(nodes, "wifi5") is None
