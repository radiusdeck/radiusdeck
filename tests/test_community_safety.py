from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from radiusdeck.repositories.backup_store import BackupStore
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.repositories.log_file_store import LogFileStore
from radiusdeck.services.backup_models import RollbackValidationError
from radiusdeck.services.backup_service import BackupService
from radiusdeck.services.log_service import LogService
from radiusdeck.services.ports import ReloadPort
from radiusdeck.services.reload_models import ReloadResult
from radiusdeck.web.endpoints import ui_logs
from radiusdeck.web.exception_handlers import register_exception_handlers


@pytest.mark.asyncio
async def test_community_logs_are_basic_and_redacted(tmp_path: Path) -> None:
    log_path = tmp_path / "radius.log"
    log_path.write_text("Info password=hunter2\n", encoding="utf-8")
    service = LogService(
        store=LogFileStore(log_path, max_bytes=4096),
        enabled=True,
        default_lines=500,
    )

    result = await service.tail()

    assert result.requested_lines == 200
    assert "hunter2" not in result.lines[0].text
    assert (await service.tail(lines=201)).requested_lines == 200
    assert not hasattr(service, "tail_for_download")


def test_community_log_page_has_manual_controls_only(tmp_path: Path) -> None:
    log_path = tmp_path / "radius.log"
    log_path.write_text("Info: ready\n", encoding="utf-8")
    app = FastAPI()
    register_exception_handlers(app)
    app.state.log_service = LogService(
        store=LogFileStore(log_path, max_bytes=4096),
        enabled=True,
        default_lines=200,
    )
    app.include_router(ui_logs.router, prefix="/ui")

    with TestClient(app) as client:
        response = client.get("/ui/logs")

    assert response.status_code == 200
    assert ">Refresh<" in response.text
    assert "log-query" not in response.text
    assert 'id="log-auto-refresh"' not in response.text
    assert "/ui/logs/download" not in response.text
    assert 'hx-trigger="every' not in response.text


@pytest.mark.asyncio
async def test_community_automatic_backup_and_latest_rollback_work(
    tmp_path: Path,
) -> None:
    clients_path = tmp_path / "clients.conf"
    original = "client nas {\n    secret = original\n}\n"
    changed = "client nas {\n    secret = changed\n}\n"
    clients_path.write_text(original, encoding="utf-8")
    clients_store = ClientsConfStore(clients_path)
    reloader = AsyncMock(spec=ReloadPort)
    reloader.reload.return_value = ReloadResult.success()
    service = BackupService(
        store=BackupStore(tmp_path / "backups", retention_count=100, max_age_days=None),
        clients_store=clients_store,
        reloader=reloader,
        enabled=True,
        app_version="0.1.0",
    )
    await service.initialize()
    created = await service.create_pre_change_backup(
        actor="admin",
        reason="update",
        client_name="nas",
        current_content=original,
        proposed_content=changed,
    )
    assert created is not None
    await clients_store.save_content(changed)

    latest = await service.get_latest_recovery_point()
    assert latest is not None
    with pytest.raises(
        RollbackValidationError,
        match="Rollback confirmation does not match the latest recovery point",
    ):
        await service.rollback_latest("admin", expected_backup_id="stale-backup-id")
    result = await service.rollback_latest("admin", expected_backup_id=latest.backup_id)

    assert result.restored_backup.backup_id == latest.backup_id
    assert await clients_store.read_content() == original
    assert not hasattr(service, "create_manual_backup")
    assert not hasattr(service, "rollback")


@pytest.mark.asyncio
async def test_basic_logs_redact_complete_quoted_values(tmp_path: Path) -> None:
    path = tmp_path / "radius.log"
    path.write_text(
        "User-Password = \"multiple secret words\"\nsecret='another phrase'\n"
    )
    service = LogService(LogFileStore(path, max_bytes=4096), True)
    result = await service.tail()
    assert [line.text for line in result.lines] == [
        "User-Password = <redacted>",
        "secret=<redacted>",
    ]
