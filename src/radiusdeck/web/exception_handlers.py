from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, Response

from radiusdeck.auth.request_classification import is_api_request, is_htmx_request
from radiusdeck.services.backup_models import (
    BackupCorruptError,
    BackupDisabledError,
    BackupError,
    BackupIntegrityError,
    BackupNotFoundError,
    BackupPermissionError,
    BackupReadError,
    BackupWriteError,
    RollbackValidationError,
)
from radiusdeck.services.errors import ClientNotFoundError
from radiusdeck.services.operation_policy import OperationUnavailableError
from radiusdeck.web.deps import templates


async def forbidden_exception_handler(request: Request, exc: Exception) -> Response:
    if is_api_request(request):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Forbidden"},
        )

    if is_htmx_request(request):
        return HTMLResponse(
            content=(
                '<div class="alert alert-danger mb-0" role="alert">'
                "Недостаточно прав для выполнения действия."
                "</div>"
            ),
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return templates.TemplateResponse(
        request,
        "403.html",
        {"detail": "Недостаточно прав для выполнения действия."},
        status_code=status.HTTP_403_FORBIDDEN,
    )


async def client_not_found_exception_handler(
    request: Request, exc: Exception
) -> Response:
    detail = "Client not found"
    if is_api_request(request):
        return JSONResponse(status_code=404, content={"detail": detail})
    if is_htmx_request(request):
        return HTMLResponse(
            content=f'<div class="alert alert-danger" role="alert">{detail}</div>',
            status_code=404,
        )
    return HTMLResponse(content=detail, status_code=404)


async def backup_exception_handler(request: Request, exc: Exception) -> Response:
    if isinstance(exc, BackupNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
        detail = "Backup not found"
    elif isinstance(
        exc,
        (
            BackupCorruptError,
            BackupIntegrityError,
            RollbackValidationError,
            BackupDisabledError,
        ),
    ):
        status_code = status.HTTP_409_CONFLICT
        detail = str(exc)
    elif isinstance(exc, (BackupPermissionError, BackupReadError, BackupWriteError)):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        detail = "Backup storage is unavailable"
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        detail = "Backup operation failed"

    if is_api_request(request):
        return JSONResponse(status_code=status_code, content={"detail": detail})
    if is_htmx_request(request):
        return HTMLResponse(
            content=f'<div class="alert alert-danger" role="alert">{detail}</div>',
            status_code=status.HTTP_200_OK,
        )
    return HTMLResponse(
        content=f'<div class="alert alert-danger" role="alert">{detail}</div>',
        status_code=status_code,
    )


async def operation_unavailable_exception_handler(
    request: Request, exc: Exception
) -> Response:
    return (
        HTMLResponse("Operation unavailable", status_code=403)
        if not is_api_request(request)
        else JSONResponse(
            (
                exc.public_payload()
                if isinstance(exc, OperationUnavailableError)
                else {"detail": "Operation unavailable"}
            ),
            status_code=403,
        )
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(status.HTTP_403_FORBIDDEN, forbidden_exception_handler)
    app.add_exception_handler(ClientNotFoundError, client_not_found_exception_handler)
    app.add_exception_handler(BackupError, backup_exception_handler)
    app.add_exception_handler(
        OperationUnavailableError, operation_unavailable_exception_handler
    )
