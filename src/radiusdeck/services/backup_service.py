from __future__ import annotations

import logging
from datetime import datetime, timezone

from radiusdeck.lib.fr_parser import parse_clients_conf
from radiusdeck.repositories.backup_store import BackupStore, content_sha256
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.services.backup_models import (
    BackupCreateResult,
    BackupDisabledError,
    BackupEntry,
    BackupIntegrityError,
    BackupMetadata,
    BackupSource,
    RollbackResult,
    RollbackValidationError,
)
from radiusdeck.services.ports import ReloadPort

logger = logging.getLogger(__name__)


class BackupService:
    def __init__(
        self,
        *,
        store: BackupStore,
        clients_store: ClientsConfStore,
        reloader: ReloadPort,
        enabled: bool,
        app_version: str,
    ) -> None:
        self._store = store
        self._clients_store = clients_store
        self._reloader = reloader
        self._enabled = enabled
        self._app_version = app_version

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def store(self) -> BackupStore:
        return self._store

    @property
    def clients_store(self) -> ClientsConfStore:
        return self._clients_store

    def require_enabled(self) -> None:
        self._require_enabled()

    async def initialize(self) -> None:
        if self._enabled:
            await self._store.initialize()

    async def create_pre_change_backup(
        self,
        *,
        actor: str,
        reason: str,
        client_name: str | None,
        current_content: str,
        proposed_content: str,
    ) -> BackupCreateResult | None:
        if not self._enabled:
            return None
        return await self.create_snapshot(
            content=current_content,
            actor=actor,
            reason=reason,
            source=BackupSource.AUTOMATIC,
            client_name=client_name,
            rollback_target_id=None,
            before_hash=content_sha256(current_content),
            after_hash=content_sha256(proposed_content),
            audit_event="backup_created",
        )

    async def get_latest_recovery_point(self) -> BackupEntry | None:
        self._require_enabled()
        entries = await self._store.list(limit=1)
        return entries[0] if entries else None

    async def rollback_latest(
        self, actor: str, *, expected_backup_id: str
    ) -> RollbackResult:
        async with self._clients_store.locked():
            latest = await self.get_latest_recovery_point()
            if latest is None:
                raise RollbackValidationError("No recovery point is available")
            if latest.backup_id != expected_backup_id:
                raise RollbackValidationError(
                    "Rollback confirmation does not match the latest recovery point"
                )
            return await self._restore_locked(latest.backup_id, actor)

    async def restore_snapshot(self, backup_id: str, actor: str) -> RollbackResult:
        """Shared integrity/safety transaction; callers authorize target selection."""
        async with self._clients_store.locked():
            return await self._restore_locked(backup_id, actor)

    async def _restore_locked(self, backup_id: str, actor: str) -> RollbackResult:
        self._require_enabled()
        self._audit("rollback_started", actor=actor, backup_id=backup_id)

        try:
            restored_backup, restored_content = await self._store.get_with_content(
                backup_id
            )
        except BackupIntegrityError:
            self._audit("backup_integrity_failed", actor=actor, backup_id=backup_id)
            raise
        try:
            parse_clients_conf(restored_content)
        except ValueError as exc:
            raise RollbackValidationError(
                "Selected backup is not a valid clients.conf"
            ) from exc

        current_content = await self._clients_store.read_content()
        before_hash = content_sha256(current_content)
        after_hash = content_sha256(restored_content)
        if before_hash == after_hash:
            raise RollbackValidationError(
                "Selected backup is identical to the current configuration"
            )

        safety_result = await self.create_snapshot(
            content=current_content,
            actor=actor,
            reason="rollback_safety",
            source=BackupSource.ROLLBACK_SAFETY,
            client_name=None,
            rollback_target_id=backup_id,
            before_hash=before_hash,
            after_hash=after_hash,
            audit_event="backup_created",
        )
        await self._clients_store.save_content(restored_content)
        verified_content = await self._clients_store.read_content()
        if content_sha256(verified_content) != after_hash:
            raise RollbackValidationError(
                "Restored clients.conf failed checksum verification"
            )
        reload_result = await self._reloader.reload()
        event = (
            "rollback_completed" if reload_result.is_ok else "rollback_reload_failed"
        )
        self._audit(
            event,
            actor=actor,
            backup_id=backup_id,
            safety_backup_id=safety_result.backup.backup_id,
            reload_status=reload_result.status.value,
        )
        return RollbackResult(
            restored_backup=restored_backup,
            safety_backup=safety_result.backup,
            live_config_sha256_before=before_hash,
            live_config_sha256_after=after_hash,
            reload_result=reload_result,
        )

    async def create_snapshot(
        self,
        *,
        content: str,
        actor: str,
        reason: str,
        source: BackupSource,
        client_name: str | None,
        rollback_target_id: str | None,
        before_hash: str,
        after_hash: str,
        audit_event: str,
    ) -> BackupCreateResult:
        backup_id = self._store.generate_id()
        checksum = content_sha256(content)
        metadata = BackupMetadata(
            version=1,
            backup_id=backup_id,
            created_at=datetime.now(timezone.utc),
            actor=self._normalize_actor(actor),
            reason=reason,
            source=source,
            client_name=client_name,
            rollback_target_id=rollback_target_id,
            content_sha256=checksum,
            live_config_sha256_before=before_hash,
            live_config_sha256_after=after_hash,
            app_version=self._app_version,
        )
        backup, pruned = await self._store.create(content, metadata)
        self._audit(
            audit_event,
            actor=metadata.actor,
            backup_id=backup_id,
            reason=reason,
            source=source.value,
            client_name=client_name,
            checksum=checksum,
        )
        for pruned_id in pruned:
            self._audit("backup_pruned", backup_id=pruned_id)
        return BackupCreateResult(backup=backup, pruned_backup_ids=pruned)

    def _require_enabled(self) -> None:
        if not self._enabled:
            raise BackupDisabledError("Backups are disabled")

    @staticmethod
    def _normalize_actor(actor: str) -> str:
        normalized = actor.strip()[:128]
        return normalized or "unknown"

    @staticmethod
    def _audit(event: str, **fields: object) -> None:
        rendered = " ".join(
            f"{key}={str(value).replace(chr(10), '_').replace(chr(13), '_')}"
            for key, value in fields.items()
            if value is not None
        )
        logger.info("Audit backup: event=%s %s", event, rendered)
