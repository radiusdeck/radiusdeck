from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from radiusdeck.auth.authorization import require_admin_user
from radiusdeck.auth.models import CurrentUser
from radiusdeck.services.status_service import StatusService
from radiusdeck.web.deps import get_status_service, templates

router = APIRouter()

StatusServiceDep = Annotated[StatusService, Depends(get_status_service)]
AdminUserDep = Annotated[CurrentUser, Depends(require_admin_user)]

_BADGE_CLASSES: dict[str, str] = {
    "ok": "success",
    "warning": "warning",
    "error": "danger",
    "skipped": "secondary",
}


@router.get("/status")
async def status_page(
    request: Request,
    service: StatusServiceDep,
    _admin: AdminUserDep,
) -> Response:
    report = await service.build_report()
    return templates.TemplateResponse(
        request,
        "status.html",
        {"report": report, "status_badge_classes": _BADGE_CLASSES},
    )
