"""Feedback on whether a saved change is applied by the running FreeRADIUS."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from radiusdeck.core.config import settings
from radiusdeck.main import app
from radiusdeck.repositories.backup_store import BackupStore
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.services.backup_service import BackupService
from radiusdeck.services.ports import ReloadPort
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.services.reload_models import ApplyState, ReloadResult, apply_state
from radiusdeck.web.deps import get_backup_service, get_radius_service
from tests.conftest import make_payload

RESTART_NOTICE = "FreeRADIUS has not applied this change yet."
CONFIG = "client LOCAL {\n    ipaddr = 127.0.0.1\n    secret = testing123\n}\n"


@pytest.mark.parametrize(
    ("reload_result", "changed", "expected"),
    [
        (ReloadResult.skipped(), True, ApplyState.RESTART_REQUIRED),
        (ReloadResult.success(), True, ApplyState.RELOADED),
        (ReloadResult.failed("boom"), True, ApplyState.RELOAD_FAILED),
        (ReloadResult.skipped("configuration unchanged"), False, None),
    ],
)
def test_apply_state(
    reload_result: ReloadResult, changed: bool, expected: ApplyState | None
) -> None:
    assert apply_state(reload_result, changed=changed) is expected


def _make_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reload_result: ReloadResult,
) -> Generator[TestClient, None, None]:
    config_path = tmp_path / "clients.conf"
    config_path.write_text(CONFIG, encoding="utf-8")
    store = ClientsConfStore(config_path)
    reloader = AsyncMock(spec=ReloadPort)
    reloader.reload.return_value = reload_result
    backup_service = BackupService(
        store=BackupStore(tmp_path / "backups", retention_count=10, max_age_days=None),
        clients_store=store,
        reloader=reloader,
        enabled=True,
        app_version="0.1.0",
    )
    asyncio.run(backup_service.initialize())
    service = RadiusService(store, reloader=reloader, backup=backup_service)

    def radius_override(_: Request) -> RadiusService:
        return service

    def backup_override(_: Request) -> BackupService:
        return backup_service

    monkeypatch.setattr(settings, "auth_method", "none")
    monkeypatch.setattr(settings, "backup_enabled", False)
    app.dependency_overrides[get_radius_service] = radius_override
    app.dependency_overrides[get_backup_service] = backup_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_radius_service, None)
    app.dependency_overrides.pop(get_backup_service, None)


@pytest.fixture()
def disabled_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    yield from _make_client(tmp_path, monkeypatch, ReloadResult.skipped())


@pytest.fixture()
def reloading_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    yield from _make_client(
        tmp_path, monkeypatch, ReloadResult.success("container restarted")
    )


def _edit_payload(ipaddr: str) -> str:
    return json.dumps(
        {
            "name": "LOCAL",
            "ipaddr": ipaddr,
            "secret": None,
            "assignments": [],
            "blocks": [],
        }
    )


def _assert_restart_notice(text: str) -> None:
    assert 'data-apply-state="restart_required"' in text
    assert RESTART_NOTICE in text
    assert "radiusd -XC" in text


def test_add_without_sidecar_shows_restart_notice(disabled_client: TestClient) -> None:
    response = disabled_client.post(
        "/ui/clients/add-tree", data={"payload_json": make_payload(name="nas-1")}
    )

    assert response.status_code == 200
    _assert_restart_notice(response.text)
    assert "Recovery backup created" in response.text


def test_edit_without_sidecar_shows_restart_notice(
    disabled_client: TestClient,
) -> None:
    response = disabled_client.put(
        "/ui/clients/LOCAL/tree", data={"payload_json": _edit_payload("127.0.0.2")}
    )

    assert response.status_code == 200
    _assert_restart_notice(response.text)


def test_delete_without_sidecar_shows_restart_notice(
    disabled_client: TestClient,
) -> None:
    response = disabled_client.delete("/ui/clients/LOCAL")

    assert response.status_code == 200
    _assert_restart_notice(response.text)


def test_unchanged_edit_shows_no_apply_notice(disabled_client: TestClient) -> None:
    response = disabled_client.put(
        "/ui/clients/LOCAL/tree", data={"payload_json": _edit_payload("127.0.0.1")}
    )

    assert response.status_code == 200
    assert "data-apply-state" not in response.text
    assert RESTART_NOTICE not in response.text


def test_add_with_sidecar_reports_completed_reload(
    reloading_client: TestClient,
) -> None:
    response = reloading_client.post(
        "/ui/clients/add-tree", data={"payload_json": make_payload(name="nas-2")}
    )

    assert response.status_code == 200
    assert 'data-apply-state="reloaded"' in response.text
    assert "FreeRADIUS reload completed: container restarted." in response.text
    assert RESTART_NOTICE not in response.text


def _rollback(client: TestClient) -> str:
    edited = client.put(
        "/ui/clients/LOCAL/tree", data={"payload_json": _edit_payload("127.0.0.2")}
    )
    assert edited.status_code == 200
    confirm = client.get("/ui/backups/latest/confirm")
    assert confirm.status_code == 200
    backup_id = confirm.text.split('name="confirm_backup_id" value="')[1].split('"')[0]
    response = client.post(
        "/ui/backups/latest/rollback", data={"confirm_backup_id": backup_id}
    )
    assert response.status_code == 200
    return response.text


def test_rollback_without_sidecar_shows_restart_notice(
    disabled_client: TestClient,
) -> None:
    text = _rollback(disabled_client)

    assert "Configuration restored." in text
    assert "restored successfully" not in text
    _assert_restart_notice(text)


def test_rollback_with_sidecar_reports_reload(reloading_client: TestClient) -> None:
    text = _rollback(reloading_client)

    assert 'data-apply-state="reloaded"' in text
    assert "Configuration restored and FreeRADIUS reloaded." in text
    assert RESTART_NOTICE not in text
