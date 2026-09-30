from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from radiusdeck.services.reload_models import ReloadResult


class BackupSource(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    ROLLBACK_SAFETY = "rollback_safety"


@dataclass(frozen=True)
class BackupMetadata:
    version: int
    backup_id: str
    created_at: datetime
    actor: str
    reason: str
    source: BackupSource
    client_name: str | None
    rollback_target_id: str | None
    content_sha256: str
    live_config_sha256_before: str
    live_config_sha256_after: str
    app_version: str


@dataclass(frozen=True)
class BackupEntry:
    metadata: BackupMetadata
    size_bytes: int

    @property
    def backup_id(self) -> str:
        return self.metadata.backup_id

    @property
    def created_at(self) -> datetime:
        return self.metadata.created_at

    @property
    def reason(self) -> str:
        return self.metadata.reason


@dataclass(frozen=True)
class BackupCreateResult:
    backup: BackupEntry
    pruned_backup_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RollbackResult:
    restored_backup: BackupEntry
    safety_backup: BackupEntry
    live_config_sha256_before: str
    live_config_sha256_after: str
    reload_result: ReloadResult


class BackupError(Exception):
    """Base class for backup domain errors."""


class BackupDisabledError(BackupError):
    pass


class BackupNotFoundError(BackupError):
    pass


class BackupCorruptError(BackupError):
    pass


class BackupIntegrityError(BackupError):
    pass


class BackupPermissionError(BackupError):
    pass


class BackupReadError(BackupError):
    pass


class BackupWriteError(BackupError):
    pass


class RollbackValidationError(BackupError):
    pass
