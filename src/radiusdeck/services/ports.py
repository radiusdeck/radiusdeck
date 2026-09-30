from typing import Protocol

from radiusdeck.services.backup_models import BackupCreateResult
from radiusdeck.services.reload_models import ReloadResult


class ReloadPort(Protocol):
    async def reload(self) -> ReloadResult: ...


class BackupPort(Protocol):
    async def create_pre_change_backup(
        self,
        *,
        actor: str,
        reason: str,
        client_name: str | None,
        current_content: str,
        proposed_content: str,
    ) -> BackupCreateResult | None: ...
