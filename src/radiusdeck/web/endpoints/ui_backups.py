from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response

from radiusdeck.auth.authorization import require_admin_user
from radiusdeck.auth.models import CurrentUser
from radiusdeck.extensions.ui import ui_slots
from radiusdeck.services.backup_models import RollbackValidationError
from radiusdeck.services.backup_service import BackupService
from radiusdeck.services.reload_models import ReloadStatus
from radiusdeck.web.deps import get_backup_service, templates

router = APIRouter()

BackupServiceDep = Annotated[BackupService, Depends(get_backup_service)]
AdminUserDep = Annotated[CurrentUser, Depends(require_admin_user)]
ConfirmBackupIdForm = Annotated[str, Form()]


async def _table_context(service: BackupService) -> dict[str, object]:
    latest = await service.get_latest_recovery_point() if service.enabled else None
    return {"backups": [latest] if latest else [], "backup_enabled": service.enabled}


@router.get("/backups", response_class=HTMLResponse)
async def backups_page(
    request: Request, service: BackupServiceDep, _admin: AdminUserDep
) -> Response:
    context = await _table_context(service)
    context["ui_slots"] = await ui_slots(request, "backups.toolbar", "backups.sections")
    return templates.TemplateResponse(request, "backups.html", context)


@router.get("/backups/latest/confirm", response_class=HTMLResponse)
async def latest_rollback_confirmation(
    request: Request,
    service: BackupServiceDep,
    _admin: AdminUserDep,
) -> Response:
    backup = await service.get_latest_recovery_point()
    if backup is None:
        raise RollbackValidationError("No recovery point is available")
    return templates.TemplateResponse(
        request,
        "components/backup_rollback_latest_confirm.html",
        {"backup": backup},
    )


@router.post("/backups/latest/rollback", response_class=HTMLResponse)
async def rollback_latest_backup(
    request: Request,
    service: BackupServiceDep,
    admin: AdminUserDep,
    confirm_backup_id: ConfirmBackupIdForm,
) -> Response:
    result = await service.rollback_latest(
        admin.username, expected_backup_id=confirm_backup_id
    )
    context = await _table_context(service)
    context.update(
        {
            "rollback_result": result,
            "reload_failed": result.reload_result.status is ReloadStatus.FAILED,
        }
    )
    return templates.TemplateResponse(request, "components/backup_table.html", context)
