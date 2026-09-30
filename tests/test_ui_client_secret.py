from __future__ import annotations

import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient
from markupsafe import escape

MASK = "************"
SECRET = "testing123"


def test_initial_client_list_and_details_do_not_contain_secret(
    client: TestClient,
) -> None:
    page = client.get("/ui/clients")
    details = client.get("/ui/clients/LOCAL/details")

    assert page.status_code == 200
    assert details.status_code == 200
    assert SECRET not in page.text
    assert SECRET not in details.text
    assert MASK in page.text
    assert MASK in details.text
    assert "Show shared secret" in page.text
    assert "Show shared secret" in details.text
    assert 'data-lucide="eye"' in page.text
    assert 'data-lucide="eye"' in details.text
    assert "data-secret" not in page.text
    assert "data-secret" not in details.text


def test_edit_form_does_not_contain_existing_secret(
    client_as_admin: TestClient,
) -> None:
    response = client_as_admin.get("/ui/clients/LOCAL/edit-form")

    assert response.status_code == 200
    assert SECRET not in response.text
    assert 'type="password"' in response.text
    assert "Leave blank to keep the current shared secret." in response.text


def test_admin_can_reveal_exact_escaped_secret_with_no_store_headers(
    client_as_admin: TestClient,
) -> None:
    secret = '<script data-test="secret">alert(1)</script>'
    update = client_as_admin.put(
        "/ui/clients/LOCAL/tree",
        data={
            "payload_json": json.dumps(
                {
                    "name": "LOCAL",
                    "ipaddr": "127.0.0.1",
                    "secret": secret,
                    "assignments": [],
                    "blocks": [],
                }
            )
        },
    )
    assert update.status_code == 200

    response = client_as_admin.post("/ui/clients/LOCAL/secret/reveal")

    assert response.status_code == 200
    assert secret not in response.text
    escaped_secret = str(escape(secret))
    assert escaped_secret in response.text
    assert response.text.count(escaped_secret) == 1
    assert "Copy" in response.text
    assert "Hide" in response.text
    assert 'data-auto-hide-ms="30000"' in response.text
    assert "data-secret" not in response.text
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_read_only_user_sees_hidden_state_and_cannot_reveal(
    client_as_user: TestClient,
) -> None:
    details = client_as_user.get("/ui/clients/LOCAL/details")
    reveal = client_as_user.post(
        "/ui/clients/LOCAL/secret/reveal",
        headers={"HX-Request": "true"},
    )

    assert details.status_code == 200
    assert SECRET not in details.text
    assert MASK in details.text
    assert "Hidden" in details.text
    assert "Show shared secret" not in details.text
    assert reveal.status_code == 403
    assert SECRET not in reveal.text


def test_open_mode_synthetic_admin_can_reveal(client: TestClient) -> None:
    response = client.post("/ui/clients/LOCAL/secret/reveal")

    assert response.status_code == 200
    assert SECRET in response.text


def test_missing_client_reveal_returns_404_without_secret(
    client_as_admin: TestClient,
) -> None:
    response = client_as_admin.post(
        "/ui/clients/missing/secret/reveal",
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 404
    assert SECRET not in response.text


def test_reveal_response_does_not_include_another_clients_secret(
    client_as_admin: TestClient,
) -> None:
    other_secret = "other-client-sensitive-value"
    created = client_as_admin.post(
        "/ui/clients/add-tree",
        data={
            "payload_json": json.dumps(
                {
                    "name": "OTHER",
                    "ipaddr": "192.0.2.30",
                    "secret": other_secret,
                    "assignments": [],
                    "blocks": [],
                }
            )
        },
    )
    assert created.status_code == 200

    response = client_as_admin.post("/ui/clients/LOCAL/secret/reveal")

    assert response.status_code == 200
    assert SECRET in response.text
    assert other_secret not in response.text


def test_unauthenticated_reveal_uses_existing_auth_behavior(auth_app: FastAPI) -> None:
    with TestClient(auth_app, follow_redirects=False) as client:
        response = client.post("/ui/clients/LOCAL/secret/reveal")

    assert response.status_code in {302, 303, 307, 401, 403}
    assert SECRET not in response.text


def test_reveal_audit_contains_metadata_but_not_secret(
    client_as_admin: TestClient,
    caplog,
) -> None:
    with caplog.at_level(logging.INFO, logger="radiusdeck.services.radius_service"):
        response = client_as_admin.post("/ui/clients/LOCAL/secret/reveal")

    assert response.status_code == 200
    messages = [record.getMessage() for record in caplog.records]
    assert (
        "Audit client secret access: actor=admin_tester "
        "action=reveal_client_secret client=LOCAL"
    ) in messages
    assert SECRET not in caplog.text


def test_invalid_create_does_not_return_or_log_submitted_secret(
    client: TestClient,
    caplog,
) -> None:
    submitted_secret = "never-log-this-client-secret"
    payload = {
        "name": "invalid",
        "ipaddr": "192.0.2.20",
        "secret": submitted_secret,
        "assignments": [
            {"key": "shortname", "value": "one"},
            {"key": "shortname", "value": "two"},
        ],
        "blocks": [],
    }

    with caplog.at_level(logging.INFO):
        response = client.post(
            "/ui/clients/add-tree",
            data={"payload_json": json.dumps(payload)},
        )

    assert response.status_code == 200
    assert submitted_secret not in response.text
    assert submitted_secret not in response.headers.get("hx-trigger", "")
    assert submitted_secret not in caplog.text
