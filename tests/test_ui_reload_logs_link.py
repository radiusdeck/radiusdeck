from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from radiusdeck.core.config import settings
from radiusdeck.main import app
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.services.ports import ReloadPort
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.services.reload_models import ReloadResult
from radiusdeck.web.deps import get_radius_service
from tests.conftest import make_payload


@pytest.fixture()
def failing_reload_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    config_path = tmp_path / "clients.conf"
    config_path.write_text(
        "client LOCAL {\n    ipaddr = 127.0.0.1\n    secret = testing123\n}\n",
        encoding="utf-8",
    )
    reloader = AsyncMock(spec=ReloadPort)
    reloader.reload.return_value = ReloadResult.failed("reload sidecar failed")
    service = RadiusService(ClientsConfStore(config_path), reloader=reloader)

    def override(_: Request) -> RadiusService:
        return service

    monkeypatch.setattr(settings, "auth_method", "none")
    monkeypatch.setattr(settings, "freeradius_log_viewer_enabled", True)
    app.dependency_overrides[get_radius_service] = override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_radius_service, None)


@pytest.fixture()
def failing_reload_logs_disabled_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    config_path = tmp_path / "clients.conf"
    config_path.write_text("# empty\n", encoding="utf-8")
    reloader = AsyncMock(spec=ReloadPort)
    reloader.reload.return_value = ReloadResult.failed("reload sidecar failed")
    service = RadiusService(ClientsConfStore(config_path), reloader=reloader)

    def override(_: Request) -> RadiusService:
        return service

    monkeypatch.setattr(settings, "auth_method", "none")
    monkeypatch.setattr(settings, "freeradius_log_viewer_enabled", False)
    app.dependency_overrides[get_radius_service] = override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_radius_service, None)


def _assert_reload_warning_with_logs_link(response_text: str) -> None:
    assert "FreeRADIUS reload failed" in response_text
    assert "reload sidecar failed" in response_text
    assert "View FreeRADIUS logs" in response_text
    assert 'href="/ui/logs"' in response_text


def test_create_reload_failure_includes_logs_link(
    failing_reload_client: TestClient,
) -> None:
    payload = make_payload(name="reload-create")

    response = failing_reload_client.post(
        "/ui/clients/add-tree",
        data={"payload_json": payload},
    )

    assert response.status_code == 200
    _assert_reload_warning_with_logs_link(response.text)


def test_update_reload_failure_includes_logs_link(
    failing_reload_client: TestClient,
) -> None:
    payload = {
        "name": "LOCAL",
        "ipaddr": "127.0.0.2",
        "secret": "newsecret",
        "assignments": [],
        "blocks": [],
    }

    response = failing_reload_client.put(
        "/ui/clients/LOCAL/tree",
        data={"payload_json": json.dumps(payload)},
    )

    assert response.status_code == 200
    _assert_reload_warning_with_logs_link(response.text)


def test_delete_reload_failure_includes_logs_link(
    failing_reload_client: TestClient,
) -> None:
    response = failing_reload_client.delete("/ui/clients/LOCAL")

    assert response.status_code == 200
    _assert_reload_warning_with_logs_link(response.text)


def test_reload_failure_omits_logs_link_when_log_viewer_disabled(
    failing_reload_logs_disabled_client: TestClient,
) -> None:
    payload = make_payload(name="reload-create-no-link")

    response = failing_reload_logs_disabled_client.post(
        "/ui/clients/add-tree",
        data={"payload_json": payload},
    )

    assert response.status_code == 200
    assert "FreeRADIUS reload failed" in response.text
    assert "View FreeRADIUS logs" not in response.text
    assert 'href="/ui/logs"' not in response.text
