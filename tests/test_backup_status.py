from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from radiusdeck.core.config import Settings
from radiusdeck.repositories.backup_store import BackupStore
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.repositories.file_diagnostics import FileDiagnostics
from radiusdeck.repositories.log_file_store import LogFileStore
from radiusdeck.services.backup_service import BackupService
from radiusdeck.services.log_service import LogService
from radiusdeck.services.ports import ReloadPort
from radiusdeck.services.reload_models import ReloadResult
from radiusdeck.services.status_models import StatusCheck, StatusLevel, StatusReport
from radiusdeck.services.status_service import StatusService


async def _build_service(
    tmp_path: Path, *, enabled: bool
) -> tuple[StatusService, BackupService]:
    clients_path = tmp_path / "clients.conf"
    clients_path.write_text("# empty\n", encoding="utf-8")
    backup_dir = tmp_path / "backups"
    settings = Settings(
        _env_file=None,
        RADIUS_CLIENTS_PATH=clients_path,
        auth_method="none",
        backup_enabled=enabled,
        backup_dir=backup_dir,
        SIDECAR_RELOAD_ENABLED=False,
    )
    clients_store = ClientsConfStore(clients_path)
    reloader = AsyncMock(spec=ReloadPort)
    reloader.reload.return_value = ReloadResult.skipped()
    backup_service = BackupService(
        store=BackupStore(backup_dir, retention_count=10, max_age_days=None),
        clients_store=clients_store,
        reloader=reloader,
        enabled=enabled,
        app_version="0.1.0",
    )
    await backup_service.initialize()
    log_service = LogService(
        store=LogFileStore(
            settings.freeradius_log_path, settings.freeradius_log_max_bytes
        ),
        enabled=False,
        default_lines=200,
    )
    return (
        StatusService(
            settings=settings,
            clients_store=clients_store,
            log_service=log_service,
            file_diagnostics=FileDiagnostics(),
            app_version="0.1.0",
            backup_service=backup_service,
        ),
        backup_service,
    )


def _check(report: StatusReport, check_id: str) -> StatusCheck:
    return next(
        check
        for section in report.sections
        for check in section.checks
        if check.id == check_id
    )


@pytest.mark.asyncio
async def test_enabled_empty_backup_storage_is_ready(tmp_path: Path) -> None:
    status_service, _ = await _build_service(tmp_path, enabled=True)

    report = await status_service.build_report()

    assert _check(report, "backups.enabled").level is StatusLevel.OK
    assert _check(report, "backups.exists").level is StatusLevel.OK
    assert _check(report, "backups.writable").level is StatusLevel.OK
    assert _check(report, "backups.latest").level is StatusLevel.SKIPPED
    assert _check(report, "backups.path").details is None
    assert all(section.id != "edition" for section in report.sections)


@pytest.mark.asyncio
async def test_latest_valid_and_corrupt_backup_status(tmp_path: Path) -> None:
    status_service, backup_service = await _build_service(tmp_path, enabled=True)
    created = await backup_service.create_pre_change_backup(
        actor="admin",
        reason="update",
        client_name=None,
        current_content="client nas {\n secret = old\n}\n",
        proposed_content="client nas {\n secret = new\n}\n",
    )
    assert created is not None

    valid_report = await status_service.build_report()
    assert _check(valid_report, "backups.latest").level is StatusLevel.OK

    backup_path = backup_service.store.directory / f"{created.backup.backup_id}.conf"
    backup_path.write_text("tampered\n", encoding="utf-8")
    corrupt_report = await status_service.build_report()
    assert _check(corrupt_report, "backups.latest").level is StatusLevel.ERROR


@pytest.mark.asyncio
async def test_disabled_backups_are_warning_not_editing_error(tmp_path: Path) -> None:
    status_service, _ = await _build_service(tmp_path, enabled=False)

    report = await status_service.build_report()

    assert _check(report, "backups.enabled").level is StatusLevel.WARNING
    assert "editing remains available" in _check(report, "backups.enabled").message
    assert _check(report, "backups.latest").level is StatusLevel.SKIPPED
