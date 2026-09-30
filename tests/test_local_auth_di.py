from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from radiusdeck.auth.local.models import LocalUserRecord, LocalUsersFile
from radiusdeck.auth.local.passwords import hash_password
from radiusdeck.core.config import settings
from radiusdeck.main import lifespan
from radiusdeck.repositories.local_users_store import LocalUsersStore
from radiusdeck.services.local_auth_service import LocalAuthService
from radiusdeck.services.log_service import LogService
from radiusdeck.services.status_service import StatusService


@pytest.mark.asyncio
async def test_lifespan_creates_local_auth_service_for_local_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clients_path = tmp_path / "clients.conf"
    clients_path.write_text("# empty\n", encoding="utf-8")
    users_path = tmp_path / "users.json"
    await LocalUsersStore(users_path).save(
        LocalUsersFile(
            version=1,
            users=[
                LocalUserRecord(
                    username="alice",
                    role="admin",
                    password_hash=hash_password("alice-password"),
                )
            ],
        )
    )

    monkeypatch.setattr(settings, "auth_method", "local")
    monkeypatch.setattr(settings, "local_users_path", users_path)
    monkeypatch.setattr(settings, "RADIUS_CLIENTS_PATH", clients_path)
    monkeypatch.setattr(settings, "SIDECAR_RELOAD_ENABLED", False)
    monkeypatch.setattr(settings, "session_secret_key", SecretStr("test-secret"))

    app = FastAPI(lifespan=lifespan)

    with TestClient(app):
        service = app.state.local_auth_service
        assert isinstance(service, LocalAuthService)
        user = await service.authenticate("alice", "alice-password")

    assert user is not None
    assert user.username == "alice"
    assert user.role == "admin"


@pytest.mark.asyncio
async def test_lifespan_creates_log_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clients_path = tmp_path / "clients.conf"
    clients_path.write_text("# empty\n", encoding="utf-8")
    log_path = tmp_path / "radius.log"
    log_path.write_text("line 1\n", encoding="utf-8")

    monkeypatch.setattr(settings, "auth_method", "none")
    monkeypatch.setattr(settings, "RADIUS_CLIENTS_PATH", clients_path)
    monkeypatch.setattr(settings, "SIDECAR_RELOAD_ENABLED", False)
    monkeypatch.setattr(settings, "freeradius_log_viewer_enabled", True)
    monkeypatch.setattr(settings, "freeradius_log_path", log_path)
    monkeypatch.setattr(settings, "freeradius_log_max_bytes", 1024)
    monkeypatch.setattr(settings, "freeradius_log_default_lines", 20)

    app = FastAPI(lifespan=lifespan)

    with TestClient(app):
        service = app.state.log_service
        result = await service.tail()

    assert isinstance(service, LogService)
    assert result.source == log_path
    assert [line.text for line in result.lines] == ["line 1"]


@pytest.mark.asyncio
async def test_lifespan_creates_status_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clients_path = tmp_path / "clients.conf"
    clients_path.write_text("# empty\n", encoding="utf-8")

    monkeypatch.setattr(settings, "auth_method", "none")
    monkeypatch.setattr(settings, "RADIUS_CLIENTS_PATH", clients_path)
    monkeypatch.setattr(settings, "SIDECAR_RELOAD_ENABLED", False)
    monkeypatch.setattr(settings, "freeradius_log_viewer_enabled", False)

    app = FastAPI(lifespan=lifespan)

    with TestClient(app):
        service = app.state.status_service
        report = await service.build_report()

    assert isinstance(service, StatusService)
    assert any(section.id == "configuration" for section in report.sections)
    version_check = next(
        check
        for section in report.sections
        for check in section.checks
        if check.id == "app.version"
    )
    assert version_check.message == "RadiusDeck version: 0.1.0"
