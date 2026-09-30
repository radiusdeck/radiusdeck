from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from radiusdeck.repositories.backup_store import BackupStore
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.schemas.client import ClientUpdate
from radiusdeck.schemas.client_edit_payload import ClientEditTreePayload
from radiusdeck.services.backup_models import BackupWriteError
from radiusdeck.services.backup_service import BackupService
from radiusdeck.services.ports import BackupPort, ReloadPort
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.services.reload_models import ReloadResult


@pytest.mark.asyncio
async def test_noop_creates_no_backup_and_skips_reload(tmp_path: Path) -> None:
    path = tmp_path / "clients.conf"
    path.write_text(
        "client nas {\n    ipaddr = 192.0.2.1\n    secret = same\n}\n",
        encoding="utf-8",
    )
    backup = AsyncMock(spec=BackupPort)
    reloader = AsyncMock(spec=ReloadPort)
    service = RadiusService(ClientsConfStore(path), reloader, backup)

    result = await service.create_or_update_client(
        "nas", ClientUpdate(name="nas", secret="same"), actor_username="admin"
    )

    assert result.changed is False
    assert result.backup is None
    assert result.reload_result.status.value == "skipped"
    backup.create_pre_change_backup.assert_not_awaited()
    reloader.reload.assert_not_awaited()


@pytest.mark.asyncio
async def test_blank_tree_edit_secret_noop_creates_no_backup_or_reload(
    tmp_path: Path,
) -> None:
    path = tmp_path / "clients.conf"
    path.write_text(
        "client nas {\n    ipaddr = 192.0.2.1\n    secret = same\n}\n",
        encoding="utf-8",
    )
    backup = AsyncMock(spec=BackupPort)
    reloader = AsyncMock(spec=ReloadPort)
    service = RadiusService(ClientsConfStore(path), reloader, backup)

    result = await service.update_client_tree(
        "nas",
        ClientEditTreePayload(
            name="nas",
            ipaddr="192.0.2.1",
            secret=None,
            assignments=[],
            blocks=[],
        ),
        actor_username="admin",
    )

    assert result.changed is False
    assert result.backup is None
    backup.create_pre_change_backup.assert_not_awaited()
    reloader.reload.assert_not_awaited()


@pytest.mark.asyncio
async def test_backup_failure_aborts_mutation_and_reload(tmp_path: Path) -> None:
    path = tmp_path / "clients.conf"
    original = "client nas {\n    ipaddr = 192.0.2.1\n    secret = old\n}\n"
    path.write_text(original, encoding="utf-8")
    backup = AsyncMock(spec=BackupPort)
    backup.create_pre_change_backup.side_effect = BackupWriteError("disk full")
    reloader = AsyncMock(spec=ReloadPort)
    service = RadiusService(ClientsConfStore(path), reloader, backup)

    with pytest.raises(BackupWriteError):
        await service.create_or_update_client(
            "nas", ClientUpdate(name="nas", secret="new"), actor_username="admin"
        )

    assert path.read_text(encoding="utf-8") == original
    reloader.reload.assert_not_awaited()


@pytest.mark.asyncio
async def test_enabled_backup_contains_exact_preceding_file(tmp_path: Path) -> None:
    path = tmp_path / "clients.conf"
    original = "client nas {\n\tipaddr = 192.0.2.1\n\tsecret = old # exact\n}\n"
    path.write_text(original, encoding="utf-8")
    store = ClientsConfStore(path)
    reloader = AsyncMock(spec=ReloadPort)
    reloader.reload.return_value = ReloadResult.success()
    backup_service = BackupService(
        store=BackupStore(tmp_path / "backups", retention_count=10, max_age_days=None),
        clients_store=store,
        reloader=reloader,
        enabled=True,
        app_version="0.1.0",
    )
    await backup_service.initialize()
    service = RadiusService(store, reloader, backup_service)

    result = await service.create_or_update_client(
        "nas", ClientUpdate(name="nas", secret="new"), actor_username="admin"
    )

    assert result.changed is True
    assert result.backup is not None
    assert await backup_service.store.read_content(result.backup.backup_id) == original


@pytest.mark.asyncio
async def test_disabled_backups_keep_editing_available(tmp_path: Path) -> None:
    path = tmp_path / "clients.conf"
    path.write_text(
        "client nas {\n    ipaddr = 192.0.2.1\n    secret = old\n}\n",
        encoding="utf-8",
    )
    store = ClientsConfStore(path)
    reloader = AsyncMock(spec=ReloadPort)
    reloader.reload.return_value = ReloadResult.skipped()
    backup_service = BackupService(
        store=BackupStore(tmp_path / "backups", retention_count=10, max_age_days=None),
        clients_store=store,
        reloader=reloader,
        enabled=False,
        app_version="0.1.0",
    )
    service = RadiusService(store, reloader, backup_service)

    result = await service.create_or_update_client(
        "nas", ClientUpdate(name="nas", secret="new"), actor_username="admin"
    )

    assert result.changed is True
    assert result.backup is None
    assert "secret = new" in path.read_text(encoding="utf-8")
    reloader.reload.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_mutations_backup_each_exact_preceding_state(
    tmp_path: Path,
) -> None:
    path = tmp_path / "clients.conf"
    original = "client nas {\n    ipaddr = 192.0.2.1\n    secret = original\n}\n"
    path.write_text(original, encoding="utf-8")
    store = ClientsConfStore(path)
    reloader = AsyncMock(spec=ReloadPort)
    reloader.reload.return_value = ReloadResult.success()
    backup_service = BackupService(
        store=BackupStore(tmp_path / "backups", retention_count=10, max_age_days=None),
        clients_store=store,
        reloader=reloader,
        enabled=True,
        app_version="0.1.0",
    )
    await backup_service.initialize()
    service = RadiusService(store, reloader, backup_service)

    await asyncio.gather(
        service.create_or_update_client(
            "nas", ClientUpdate(name="nas", secret="first"), actor_username="one"
        ),
        service.create_or_update_client(
            "nas", ClientUpdate(name="nas", secret="second"), actor_username="two"
        ),
    )

    entries = await backup_service.store.list()
    contents = {
        await backup_service.store.read_content(entry.backup_id) for entry in entries
    }
    final_content = path.read_text(encoding="utf-8")
    assert len(entries) == 2
    assert original in contents
    assert final_content not in contents
    assert any("secret = first" in content for content in contents | {final_content})
    assert any("secret = second" in content for content in contents | {final_content})
    assert reloader.reload.await_count == 2


@pytest.mark.asyncio
async def test_save_failure_leaves_created_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "clients.conf"
    original = "client nas {\n    ipaddr = 192.0.2.1\n    secret = old\n}\n"
    path.write_text(original, encoding="utf-8")
    store = ClientsConfStore(path)
    reloader = AsyncMock(spec=ReloadPort)
    backup_service = BackupService(
        store=BackupStore(tmp_path / "backups", retention_count=10, max_age_days=None),
        clients_store=store,
        reloader=reloader,
        enabled=True,
        app_version="0.1.0",
    )
    await backup_service.initialize()
    service = RadiusService(store, reloader, backup_service)
    save_mock = AsyncMock(side_effect=OSError("simulated save failure"))
    monkeypatch.setattr(store, "save_content", save_mock)

    with pytest.raises(OSError):
        await service.create_or_update_client(
            "nas", ClientUpdate(name="nas", secret="new"), actor_username="admin"
        )

    entries = await backup_service.store.list()
    assert len(entries) == 1
    assert await backup_service.store.read_content(entries[0].backup_id) == original
    reloader.reload.assert_not_awaited()


@pytest.mark.asyncio
async def test_reload_failure_keeps_saved_mutation_and_backup(tmp_path: Path) -> None:
    path = tmp_path / "clients.conf"
    path.write_text(
        "client nas {\n    ipaddr = 192.0.2.1\n    secret = old\n}\n",
        encoding="utf-8",
    )
    store = ClientsConfStore(path)
    reloader = AsyncMock(spec=ReloadPort)
    reloader.reload.return_value = ReloadResult.failed("sidecar unavailable")
    backup_service = BackupService(
        store=BackupStore(tmp_path / "backups", retention_count=10, max_age_days=None),
        clients_store=store,
        reloader=reloader,
        enabled=True,
        app_version="0.1.0",
    )
    await backup_service.initialize()
    service = RadiusService(store, reloader, backup_service)

    result = await service.create_or_update_client(
        "nas", ClientUpdate(name="nas", secret="new"), actor_username="admin"
    )

    assert result.reload_result == ReloadResult.failed("sidecar unavailable")
    assert result.backup is not None
    assert "secret = new" in path.read_text(encoding="utf-8")
