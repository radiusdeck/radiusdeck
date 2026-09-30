from __future__ import annotations

import asyncio
import builtins
import hashlib
import json
import os
import re
import secrets
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiofiles

from radiusdeck.services.backup_models import (
    BackupCorruptError,
    BackupEntry,
    BackupIntegrityError,
    BackupMetadata,
    BackupNotFoundError,
    BackupPermissionError,
    BackupReadError,
    BackupSource,
    BackupWriteError,
)

_BACKUP_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class BackupStore:
    def __init__(
        self,
        directory: Path,
        *,
        retention_count: int,
        max_age_days: int | None,
        pruning_enabled: bool = True,
    ) -> None:
        self.directory = directory
        self.retention_count = retention_count
        self.max_age_days = max_age_days
        self.pruning_enabled = pruning_enabled
        self._lock = asyncio.Lock()

    @staticmethod
    def generate_id() -> str:
        return secrets.token_urlsafe(18)

    @staticmethod
    def validate_id(backup_id: str) -> None:
        if _BACKUP_ID_RE.fullmatch(backup_id) is None:
            raise BackupNotFoundError("Backup not found")

    async def initialize(self) -> None:
        try:
            await asyncio.to_thread(self.directory.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(self.directory.chmod, 0o700)
        except PermissionError as exc:
            raise BackupPermissionError("Backup directory is not writable") from exc
        except OSError as exc:
            raise BackupWriteError("Backup directory could not be initialized") from exc

    async def create(
        self, content: str, metadata: BackupMetadata
    ) -> tuple[BackupEntry, tuple[str, ...]]:
        async with self._lock:
            return await self._create_unlocked(content, metadata)

    async def _create_unlocked(
        self, content: str, metadata: BackupMetadata
    ) -> tuple[BackupEntry, tuple[str, ...]]:
        self.validate_id(metadata.backup_id)
        if metadata.content_sha256 != content_sha256(content):
            raise BackupIntegrityError(
                "Backup metadata checksum does not match content"
            )

        conf_path, json_path = self._paths(metadata.backup_id)
        nonce = secrets.token_hex(6)
        conf_tmp = self.directory / f".{metadata.backup_id}.{nonce}.conf.tmp"
        json_tmp = self.directory / f".{metadata.backup_id}.{nonce}.json.tmp"
        payload = self._metadata_to_dict(metadata)
        size_bytes = len(content.encode("utf-8"))
        payload["size_bytes"] = size_bytes

        try:
            await self._write_private_file(conf_tmp, content)
            await self._write_private_file(
                json_tmp, json.dumps(payload, sort_keys=True, indent=2) + "\n"
            )
            await asyncio.to_thread(os.replace, conf_tmp, conf_path)
            await asyncio.to_thread(os.replace, json_tmp, json_path)
            pruned = await self._prune_unlocked() if self.pruning_enabled else ()
        except PermissionError as exc:
            await self._cleanup_paths(conf_tmp, json_tmp, conf_path, json_path)
            raise BackupPermissionError("Backup files cannot be written") from exc
        except BackupErrorTypes:
            await self._cleanup_paths(conf_tmp, json_tmp, conf_path, json_path)
            raise
        except OSError as exc:
            await self._cleanup_paths(conf_tmp, json_tmp, conf_path, json_path)
            raise BackupWriteError("Backup could not be written") from exc

        return BackupEntry(metadata=metadata, size_bytes=size_bytes), pruned

    async def list(self, limit: int | None = None) -> builtins.list[BackupEntry]:
        async with self._lock:
            entries = await self._list_unlocked()
            return entries if limit is None else entries[:limit]

    async def get(self, backup_id: str) -> BackupEntry:
        async with self._lock:
            entry, _ = await self._read_pair_unlocked(backup_id)
            return entry

    async def read_content(self, backup_id: str) -> str:
        async with self._lock:
            _, content = await self._read_pair_unlocked(backup_id)
            return content

    async def get_with_content(self, backup_id: str) -> tuple[BackupEntry, str]:
        async with self._lock:
            return await self._read_pair_unlocked(backup_id)

    async def delete(self, backup_id: str) -> None:
        async with self._lock:
            await self._delete_unlocked(backup_id)

    async def prune(self) -> tuple[str, ...]:
        async with self._lock:
            return await self._prune_unlocked() if self.pruning_enabled else ()

    async def _list_unlocked(self) -> builtins.list[BackupEntry]:
        try:
            paths = await asyncio.to_thread(
                lambda: {
                    path.stem
                    for pattern in ("*.conf", "*.json")
                    for path in self.directory.glob(pattern)
                }
            )
        except PermissionError as exc:
            raise BackupPermissionError("Backup directory cannot be read") from exc
        except OSError as exc:
            raise BackupReadError("Backup directory cannot be read") from exc

        entries: builtins.list[BackupEntry] = []
        for backup_id in paths:
            entry, _ = await self._read_pair_unlocked(backup_id)
            entries.append(entry)
        entries.sort(key=lambda item: item.metadata.created_at, reverse=True)
        return entries

    async def _read_pair_unlocked(self, backup_id: str) -> tuple[BackupEntry, str]:
        self.validate_id(backup_id)
        conf_path, json_path = self._paths(backup_id)
        conf_exists, json_exists = await asyncio.gather(
            asyncio.to_thread(conf_path.is_file),
            asyncio.to_thread(json_path.is_file),
        )
        if not conf_exists and not json_exists:
            raise BackupNotFoundError("Backup not found")
        if not conf_exists or not json_exists:
            raise BackupCorruptError("Backup file pair is incomplete")

        try:
            async with aiofiles.open(conf_path, "r", encoding="utf-8") as stream:
                content = await stream.read()
            async with aiofiles.open(json_path, "r", encoding="utf-8") as stream:
                raw_metadata = json.loads(await stream.read())
        except PermissionError as exc:
            raise BackupPermissionError("Backup cannot be read") from exc
        except (UnicodeError, json.JSONDecodeError, TypeError) as exc:
            raise BackupCorruptError("Backup metadata is corrupt") from exc
        except OSError as exc:
            raise BackupReadError("Backup cannot be read") from exc

        try:
            metadata = self._metadata_from_dict(raw_metadata)
            size_bytes = int(raw_metadata["size_bytes"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BackupCorruptError("Backup metadata is corrupt") from exc

        if metadata.backup_id != backup_id:
            raise BackupCorruptError("Backup ID does not match metadata")
        if content_sha256(content) != metadata.content_sha256:
            raise BackupIntegrityError("Backup checksum verification failed")
        if len(content.encode("utf-8")) != size_bytes:
            raise BackupIntegrityError("Backup size verification failed")
        return BackupEntry(metadata=metadata, size_bytes=size_bytes), content

    async def _prune_unlocked(self) -> tuple[str, ...]:
        entries = await self._list_unlocked()
        expired_ids: set[str] = set()
        if self.max_age_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)
            expired_ids.update(
                entry.backup_id
                for entry in entries
                if entry.metadata.created_at < cutoff
            )
        retained = [entry for entry in entries if entry.backup_id not in expired_ids]
        expired_ids.update(
            entry.backup_id for entry in retained[self.retention_count :]
        )
        for backup_id in expired_ids:
            await self._delete_unlocked(backup_id)
        return tuple(sorted(expired_ids))

    async def _delete_unlocked(self, backup_id: str) -> None:
        self.validate_id(backup_id)
        for path in self._paths(backup_id):
            try:
                await asyncio.to_thread(path.unlink, missing_ok=True)
            except PermissionError as exc:
                raise BackupPermissionError("Backup cannot be deleted") from exc
            except OSError as exc:
                raise BackupWriteError("Backup cannot be deleted") from exc

    def _paths(self, backup_id: str) -> tuple[Path, Path]:
        self.validate_id(backup_id)
        return (
            self.directory / f"{backup_id}.conf",
            self.directory / f"{backup_id}.json",
        )

    async def _write_private_file(self, path: Path, content: str) -> None:
        async with aiofiles.open(path, "x", encoding="utf-8") as stream:
            await stream.write(content)
            await stream.flush()
        await asyncio.to_thread(path.chmod, 0o600)

    async def _cleanup_paths(self, *paths: Path) -> None:
        for path in paths:
            try:
                await asyncio.to_thread(path.unlink, missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _metadata_to_dict(metadata: BackupMetadata) -> dict[str, Any]:
        payload = asdict(metadata)
        payload["created_at"] = metadata.created_at.isoformat()
        payload["source"] = metadata.source.value
        return payload

    @staticmethod
    def _metadata_from_dict(payload: dict[str, Any]) -> BackupMetadata:
        version = int(payload["version"])
        if version != 1:
            raise ValueError("Unsupported backup metadata version")
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        if created_at.tzinfo is None:
            raise ValueError("Backup timestamp must include a timezone")
        return BackupMetadata(
            version=version,
            backup_id=str(payload["backup_id"]),
            created_at=created_at,
            actor=str(payload["actor"]),
            reason=str(payload["reason"]),
            source=BackupSource(str(payload["source"])),
            client_name=(
                str(payload["client_name"])
                if payload.get("client_name") is not None
                else None
            ),
            rollback_target_id=(
                str(payload["rollback_target_id"])
                if payload.get("rollback_target_id") is not None
                else None
            ),
            content_sha256=str(payload["content_sha256"]),
            live_config_sha256_before=str(payload["live_config_sha256_before"]),
            live_config_sha256_after=str(payload["live_config_sha256_after"]),
            app_version=str(payload["app_version"]),
        )


BackupErrorTypes = (
    BackupCorruptError,
    BackupIntegrityError,
    BackupNotFoundError,
    BackupPermissionError,
    BackupReadError,
    BackupWriteError,
)
