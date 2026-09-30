from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import Response

from radiusdeck.auth.authorization import require_admin_user
from radiusdeck.auth.models import CurrentUser
from radiusdeck.core.config import settings
from radiusdeck.extensions.ui import ui_slots
from radiusdeck.services.log_models import (
    LogFileNotFoundError,
    LogFilePermissionError,
    LogReadError,
    LogTailResult,
    LogViewerDisabledError,
)
from radiusdeck.services.log_service import LogService
from radiusdeck.web.deps import get_log_service, templates

router = APIRouter()

LogServiceDep = Annotated[LogService, Depends(get_log_service)]
AdminUserDep = Annotated[CurrentUser, Depends(require_admin_user)]
LinesQuery = Annotated[int | None, Query(ge=1)]
QueryText = Annotated[str | None, Query(alias="q")]


def _format_updated_at(value: datetime | None) -> str:
    if value is None:
        return "Unavailable"
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


def _line_options(selected_lines: int) -> list[int]:
    options = {
        min(selected_lines, 200),
        min(settings.freeradius_log_default_lines, 200),
        100,
        200,
    }
    return sorted(options)


def _logs_context(
    *,
    result: LogTailResult | None,
    error: str | None,
    lines: int | None,
) -> dict[str, object]:
    selected_lines = (
        result.requested_lines
        if result is not None
        else min(lines or settings.freeradius_log_default_lines, 200)
    )
    return {
        "result": result,
        "error": error,
        "lines": selected_lines,
        "selected_lines": selected_lines,
        "line_options": _line_options(selected_lines),
        "query": "",
        "source": str(result.source if result else settings.freeradius_log_path),
        "last_updated_display": _format_updated_at(
            result.updated_at if result else None
        ),
        "default_lines": settings.freeradius_log_default_lines,
    }


def _error_status(exc: Exception) -> int:
    if isinstance(exc, LogViewerDisabledError):
        return status.HTTP_403_FORBIDDEN
    if isinstance(exc, LogFileNotFoundError):
        return status.HTTP_404_NOT_FOUND
    if isinstance(exc, LogFilePermissionError):
        return status.HTTP_403_FORBIDDEN
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def _error_message(exc: Exception) -> str:
    if isinstance(exc, LogViewerDisabledError):
        return "Log viewer is disabled."
    if isinstance(exc, LogFileNotFoundError):
        return "Log file not found."
    if isinstance(exc, LogFilePermissionError):
        return "Log file access denied."
    return "Failed to read log file."


async def _tail(
    service: LogService,
    *,
    lines: int | None,
) -> tuple[LogTailResult | None, str | None, int]:
    try:
        return await service.tail(lines=lines), None, status.HTTP_200_OK
    except (
        LogViewerDisabledError,
        LogFileNotFoundError,
        LogFilePermissionError,
        LogReadError,
    ) as exc:
        return None, _error_message(exc), _error_status(exc)


@router.get("/logs")
async def logs_page(
    request: Request,
    service: LogServiceDep,
    _admin: AdminUserDep,
    lines: LinesQuery = None,
) -> Response:
    result, error, response_status = await _tail(service, lines=lines)
    return templates.TemplateResponse(
        request,
        "logs.html",
        {
            "ui_slots": await ui_slots(request, "logs.toolbar", "logs.sections"),
            **_logs_context(
                result=result,
                error=error,
                lines=lines,
            ),
        },
        status_code=response_status,
    )


@router.get("/logs/tail")
async def logs_tail_partial(
    request: Request,
    service: LogServiceDep,
    _admin: AdminUserDep,
    lines: LinesQuery = None,
) -> Response:
    result, error, _response_status = await _tail(service, lines=lines)
    return templates.TemplateResponse(
        request,
        "components/log_output.html",
        {"result": result, "error": error},
        # HTMX does not swap non-2xx responses by default. Keep the full page
        # status codes strict, but let partial refreshes replace stale output
        # with the rendered error message.
        status_code=status.HTTP_200_OK,
    )
