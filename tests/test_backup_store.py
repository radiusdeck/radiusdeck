from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from radiusdeck.repositories.backup_store import BackupStore, content_sha256
from radiusdeck.services.backup_models import (
    BackupCorruptError,
    BackupIntegrityError,
    BackupMetadata,
    BackupNotFoundError,
    BackupSource,
    BackupWriteError,
)


def _metadata(
    backup_id: str,
    content: str,
    *,
    created_at: datetime | None = None,
) -> BackupMetadata:
    checksum = content_sha256(content)
    return BackupMetadata(
        version=1,
        backup_id=backup_id,
        created_at=created_at or datetime.now(timezone.utc),
        actor="tester",
        reason="update_client",
        source=BackupSource.AUTOMATIC,
        client_name="nas",
        rollback_target_id=None,
        content_sha256=checksum,
        live_config_sha256_before=checksum,
        live_config_sha256_after=checksum,
        app_version="0.1.0",
    )


@pytest.mark.asyncio
async def test_create_read_list_and_permissions(tmp_path: Path) -> None:
    directory = tmp_path / "backups"
    store = BackupStore(directory, retention_count=10, max_age_days=None)
    await store.initialize()
    content = "client nas {\n    secret = exact-secret\n}\n"
    backup_id = store.generate_id()

    entry, pruned = await store.create(content, _metadata(backup_id, content))

    assert pruned == ()
    assert entry.backup_id == backup_id
    assert await store.read_content(backup_id) == content
    assert [item.backup_id for item in await store.list()] == [backup_id]
    assert directory.stat().st_mode & 0o777 == 0o700
    assert (directory / f"{backup_id}.conf").stat().st_mode & 0o777 == 0o600
    assert (directory / f"{backup_id}.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.asyncio
@pytest.mark.parametrize("backup_id", ["../escape", "short", "with.dot", "/tmp/x"])
async def test_rejects_malformed_ids(tmp_path: Path, backup_id: str) -> None:
    store = BackupStore(tmp_path, retention_count=10, max_age_days=None)
    with pytest.raises(BackupNotFoundError):
        await store.get(backup_id)


@pytest.mark.asyncio
async def test_incomplete_pair_is_corrupt(tmp_path: Path) -> None:
    store = BackupStore(tmp_path, retention_count=10, max_age_days=None)
    backup_id = store.generate_id()
    (tmp_path / f"{backup_id}.conf").write_text("# orphan\n", encoding="utf-8")

    with pytest.raises(BackupCorruptError):
        await store.get(backup_id)
    with pytest.raises(BackupCorruptError):
        await store.list()


@pytest.mark.asyncio
async def test_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    store = BackupStore(tmp_path, retention_count=10, max_age_days=None)
    content = "# original\n"
    backup_id = store.generate_id()
    await store.create(content, _metadata(backup_id, content))
    (tmp_path / f"{backup_id}.conf").write_text("# tampered\n", encoding="utf-8")

    with pytest.raises(BackupIntegrityError):
        await store.read_content(backup_id)


@pytest.mark.asyncio
async def test_retention_by_count_and_age(tmp_path: Path) -> None:
    store = BackupStore(tmp_path, retention_count=2, max_age_days=2)
    now = datetime.now(timezone.utc)
    ids: list[str] = []
    for index, age_days in enumerate((10, 1, 0)):
        content = f"# backup {index}\n"
        backup_id = store.generate_id()
        ids.append(backup_id)
        await store.create(
            content,
            _metadata(
                backup_id,
                content,
                created_at=now - timedelta(days=age_days),
            ),
        )

    assert [entry.backup_id for entry in await store.list()] == [ids[2], ids[1]]
    assert not (tmp_path / f"{ids[0]}.conf").exists()


@pytest.mark.asyncio
async def test_concurrent_creates_produce_complete_pairs(tmp_path: Path) -> None:
    store = BackupStore(tmp_path, retention_count=20, max_age_days=None)

    async def create_one(index: int) -> None:
        content = f"# concurrent {index}\n"
        backup_id = store.generate_id()
        await store.create(content, _metadata(backup_id, content))

    import asyncio

    await asyncio.gather(*(create_one(index) for index in range(8)))

    entries = await store.list()
    assert len(entries) == 8
    for entry in entries:
        assert await store.read_content(entry.backup_id)


@pytest.mark.asyncio
async def test_metadata_without_required_fields_is_corrupt(tmp_path: Path) -> None:
    store = BackupStore(tmp_path, retention_count=10, max_age_days=None)
    backup_id = store.generate_id()
    (tmp_path / f"{backup_id}.conf").write_text("# config\n", encoding="utf-8")
    (tmp_path / f"{backup_id}.json").write_text(
        json.dumps({"backup_id": backup_id}), encoding="utf-8"
    )

    with pytest.raises(BackupCorruptError):
        await store.get(backup_id)


@pytest.mark.asyncio
async def test_temporary_files_are_cleaned_after_publish_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = BackupStore(tmp_path, retention_count=10, max_age_days=None)
    content = "# config\n"
    backup_id = store.generate_id()

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated publish failure")

    monkeypatch.setattr("radiusdeck.repositories.backup_store.os.replace", fail_replace)
    with pytest.raises(BackupWriteError):
        await store.create(content, _metadata(backup_id, content))

    assert [path for path in tmp_path.iterdir()] == []
