"""Address errors and warnings in the add and edit endpoints."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import httpx2

from tests.conftest import UiEnv, make_payload


def _add(env: UiEnv, name: str, ipaddr: str) -> tuple[httpx2.Response, dict[str, Any]]:
    resp = env.client.post(
        "/ui/clients/add-tree",
        data={"payload_json": make_payload(name=name, ipaddr=ipaddr)},
    )
    return resp, json.loads(resp.headers["hx-trigger"])


def test_add_invalid_address_reports_reason(
    env_complex: UiEnv, reloader_mock: AsyncMock
) -> None:
    before = env_complex.config_path.read_text(encoding="utf-8")

    _, trigger = _add(env_complex, "new-ap", "300.1.1.1")

    assert "clientAdded" not in trigger
    assert trigger["clientAddError"] == (
        'IP address "300.1.1.1" is not a valid IPv4 address or network.'
    )
    assert env_complex.config_path.read_text(encoding="utf-8") == before
    reloader_mock.reload.assert_not_awaited()


def test_add_duplicate_address_names_the_other_client(env_complex: UiEnv) -> None:
    _, trigger = _add(env_complex, "new-ap", "127.0.0.1")

    assert trigger["clientAddError"] == (
        "Address 127.0.0.1 is already used by client LOCAL."
    )


def test_add_host_name_shows_warning_after_save(env_complex: UiEnv) -> None:
    resp, trigger = _add(env_complex, "new-ap", "nas.example.com")

    assert "clientAdded" in trigger
    assert "FreeRADIUS resolves nas.example.com once at startup" in resp.text


def test_edit_invalid_address_returns_form_with_reason(env_complex: UiEnv) -> None:
    before = env_complex.config_path.read_text(encoding="utf-8")
    payload = {"name": "LOCAL", "ipaddr": "192.0.2.010"}

    resp = env_complex.client.put(
        "/ui/clients/LOCAL/tree", data={"payload_json": json.dumps(payload)}
    )

    assert resp.status_code == 400
    assert 'id="edit-form"' in resp.text
    assert (
        "IP address &#34;192.0.2.010&#34; is not a valid IPv4 address or network."
        in resp.text
    )
    assert env_complex.config_path.read_text(encoding="utf-8") == before


def test_edit_any_address_shows_warning_after_save(env_complex: UiEnv) -> None:
    payload = {"name": "LOCAL", "ipaddr": "*"}

    resp = env_complex.client.put(
        "/ui/clients/LOCAL/tree", data={"payload_json": json.dumps(payload)}
    )

    assert resp.status_code == 200
    assert "accepts requests from any IPv4 address" in resp.text
