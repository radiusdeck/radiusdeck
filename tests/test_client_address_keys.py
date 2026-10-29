"""Clients whose address is in ipv4addr or ipv6addr instead of ipaddr.

The stock FreeRADIUS clients.conf has `client localhost_ipv6 { ipv6addr = ::1 }`.
The list showed no address for it and Edit answered 500.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from radiusdeck.lib.fr_parser import parse_clients_conf
from radiusdeck.lib.fr_parser.merge import merge_client_block
from radiusdeck.lib.fr_parser.ops import find_client
from radiusdeck.main import app
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.schemas.client_edit_payload import (
    AssignmentEditPayload,
    ClientEditTreePayload,
)
from radiusdeck.schemas.client_payload_tree import (
    AssignmentPayload,
    ClientCreateTreePayload,
)
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.web.deps import get_radius_service
from tests.conftest import UiEnv

CONFIG = """client localhost {
    ipaddr = 127.0.0.1
    secret = testing123
}
client localhost_ipv6 {
    ipv6addr = ::1 # stock client
    secret = testing123
    shortname = localhost6
}
client branch-vpn {
    ipv4addr = 198.51.100.20
    secret = example-secret
}
"""


@pytest.fixture()
def env(tmp_path: Path, reloader_mock: AsyncMock) -> Generator[UiEnv, None, None]:
    config_file = tmp_path / "clients.conf"
    config_file.write_text(CONFIG, encoding="utf-8")
    service = RadiusService(ClientsConfStore(config_file), reloader=reloader_mock)
    app.dependency_overrides[get_radius_service] = lambda: service
    with TestClient(app) as test_client:
        yield UiEnv(client=test_client, config_path=config_file)
    app.dependency_overrides.pop(get_radius_service, None)


def _client_text(config: str, name: str) -> str:
    start = config.index(f"client {name} {{")
    return config[start : config.index("}", start) + 1]


# ── list ─────────────────────────────────────────────


def test_list_shows_ipv6addr_and_ipv4addr(env: UiEnv) -> None:
    html = env.client.get("/ui/clients").text

    assert "<td>::1</td>" in html
    assert "<td>198.51.100.20</td>" in html


# ── edit form ────────────────────────────────────────


def test_edit_form_opens_for_ipv6addr_client(env: UiEnv) -> None:
    resp = env.client.get("/ui/clients/localhost_ipv6/edit-form")

    assert resp.status_code == 200
    assert 'value="::1"' in resp.text
    assert "ipv6addr" in resp.text  # the form says which key is edited
    # ipv6addr is the address field, not an extra parameter
    assert 'value="ipv6addr"' not in resp.text
    assert 'value="shortname"' in resp.text


def test_edit_saves_into_existing_ipv6addr(env: UiEnv) -> None:
    payload = {
        "name": "localhost_ipv6",
        "ipaddr": "::2",
        "assignments": [{"id": "a:0", "key": "shortname", "value": "localhost6"}],
    }

    resp = env.client.put(
        "/ui/clients/localhost_ipv6/tree", data={"payload_json": json.dumps(payload)}
    )

    assert resp.status_code == 200
    block = _client_text(env.config_path.read_text(encoding="utf-8"), "localhost_ipv6")
    assert "ipv6addr = ::2 # stock client" in block
    assert "ipaddr" not in block.replace("ipv6addr", "")
    assert "shortname = localhost6" in block


def test_edit_saves_into_existing_ipv4addr(env: UiEnv) -> None:
    payload = {"name": "branch-vpn", "ipaddr": "198.51.100.21"}

    resp = env.client.put(
        "/ui/clients/branch-vpn/tree", data={"payload_json": json.dumps(payload)}
    )

    assert resp.status_code == 200
    block = _client_text(env.config_path.read_text(encoding="utf-8"), "branch-vpn")
    assert "ipv4addr = 198.51.100.21" in block
    assert "ipaddr" not in block.replace("ipv4addr", "")


def test_edit_rejects_ipv4_for_ipv6addr(env: UiEnv) -> None:
    before = env.config_path.read_text(encoding="utf-8")
    payload = {"name": "localhost_ipv6", "ipaddr": "192.0.2.10"}

    resp = env.client.put(
        "/ui/clients/localhost_ipv6/tree", data={"payload_json": json.dumps(payload)}
    )

    assert resp.status_code == 400
    assert "ipv6addr" in resp.text
    assert "IPv6" in resp.text
    assert env.config_path.read_text(encoding="utf-8") == before


# ── merge and payload rules ──────────────────────────


def test_merge_updates_the_existing_address_key() -> None:
    nodes = parse_clients_conf(CONFIG)
    block = find_client(nodes, "localhost_ipv6")
    assert block is not None

    merge_client_block(
        block,
        ClientEditTreePayload(
            name="localhost_ipv6",
            ipaddr="::2",
            assignments=[AssignmentEditPayload(id="a:0", key="shortname", value="x")],
        ),
    )

    keys = [getattr(ch, "key", None) for ch in block.children]
    assert "ipaddr" not in keys
    assert keys.count("ipv6addr") == 1


@pytest.mark.parametrize("key", ["ipv4addr", "ipv6addr"])
def test_edit_rejects_second_address_key_as_extra(env: UiEnv, key: str) -> None:
    payload = {
        "name": "localhost",
        "ipaddr": "127.0.0.1",
        "assignments": [{"id": None, "key": key, "value": "::1"}],
    }

    resp = env.client.put(
        "/ui/clients/localhost/tree", data={"payload_json": json.dumps(payload)}
    )

    assert resp.status_code == 400
    assert "reserved" in resp.text


@pytest.mark.parametrize("key", ["ipv4addr", "ipv6addr"])
def test_create_rejects_address_key_as_extra(key: str) -> None:
    with pytest.raises(ValueError, match="reserved"):
        ClientCreateTreePayload(
            name="new-ap",
            ipaddr="192.0.2.10",
            secret="example-secret",
            assignments=[AssignmentPayload(key=key, value="192.0.2.11")],
        )
