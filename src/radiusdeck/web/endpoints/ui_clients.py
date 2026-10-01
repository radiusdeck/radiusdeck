import json
import logging
from hashlib import sha256
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError

from radiusdeck.auth.authorization import require_admin_user
from radiusdeck.auth.models import CurrentUser
from radiusdeck.core.config import settings
from radiusdeck.schemas.client_edit_payload import ClientEditTreePayload
from radiusdeck.schemas.client_payload_tree import ClientCreateTreePayload
from radiusdeck.services.backup_models import BackupEntry
from radiusdeck.services.errors import (
    ClientNotFoundError,
    DuplicateKeyError,
    InvalidNodeIdError,
    MergeClientError,
)
from radiusdeck.services.radius_service import DeleteResult, RadiusService, UpsertResult
from radiusdeck.services.reload_models import ReloadResult
from radiusdeck.web.deps import get_radius_service, templates

RadiusServiceDep = Annotated[RadiusService, Depends(get_radius_service)]
AdminUserDep = Annotated[CurrentUser, Depends(require_admin_user)]
DepthQuery = Annotated[int, Query(ge=0, le=20)]
PayloadJsonOptionalForm = Annotated[str | None, Form()]
PayloadJsonForm = Annotated[str, Form()]
SecretSurfaceForm = Annotated[Literal["list", "details"], Form()]

SURFACE_CONTEXT_KEY = "secret_surface"
CLIENT_SURFACE_CONTEXT_KEY = "client_secret_surface"
REVEAL_ALLOWED_CONTEXT_KEY = "can_reveal_secret"

logger = logging.getLogger(__name__)

router = APIRouter()


def _can_write(request: Request) -> bool:
    user = getattr(request.state, "user", None)
    return user is None or user.role == "admin"


def _can_reveal_secret(request: Request) -> bool:
    user = getattr(request.state, "user", None)
    return settings.auth_method == "none" or getattr(user, "role", None) == "admin"


def _client_secret_dom_id(name: str, surface: str) -> str:
    digest = sha256(name.encode("utf-8")).hexdigest()[:16]
    return f"client-secret-{surface}-{digest}"


def _client_row_context(request: Request, client: dict[str, str]) -> dict[str, str]:
    name = client["name"]
    return {
        "name": name,
        "ipaddr": client.get("ipaddr", ""),
        "secret_dom_id": _client_secret_dom_id(name, "list"),
        "secret_reveal_url": str(request.url_for("reveal_client_secret", name=name)),
        SURFACE_CONTEXT_KEY: "list",
    }


def _render_reload_alert(
    request: Request,
    reload_result: ReloadResult,
    backup: BackupEntry | None = None,
) -> str:
    return templates.get_template("components/reload_alert.html").render(
        request=request,
        reload_result=reload_result,
        backup=backup,
        show_logs_link=settings.freeradius_log_viewer_enabled,
    )


def _render_with_reload_alert(
    request: Request,
    template_name: str,
    context: dict[str, object],
    reload_result: ReloadResult,
    backup: BackupEntry | None,
) -> str:
    html = templates.get_template(template_name).render(request=request, **context)
    return html + _render_reload_alert(request, reload_result, backup)


def _render_table_fragment_with_reload_alert(
    request: Request,
    template_name: str,
    context: dict[str, object],
    reload_result: ReloadResult,
    backup: BackupEntry | None,
) -> str:
    html = templates.get_template(template_name).render(request=request, **context)
    return f"<table>{html}</table>" + _render_reload_alert(
        request, reload_result, backup
    )


# ──────────────────────────────────────────────
#  Static routes FIRST (without {name})
# ──────────────────────────────────────────────


@router.get("/clients", response_class=HTMLResponse)
async def list_clients(
    request: Request,
    service: RadiusServiceDep,
) -> Response:
    clients = [
        _client_row_context(request, client)
        for client in await service.get_all_clients_for_ui()
    ]
    return templates.TemplateResponse(
        request,
        "clients.html",
        {
            "clients": clients,
            "can_write": _can_write(request),
            REVEAL_ALLOWED_CONTEXT_KEY: _can_reveal_secret(request),
        },
    )


@router.get("/clients/assignment-row", response_class=HTMLResponse)
async def assignment_row(
    request: Request,
    _admin: AdminUserDep,
) -> Response:
    row_id = f"a{uuid4().hex}"
    return templates.TemplateResponse(
        request,
        "components/assignment_row.html",
        {"row_id": row_id},
    )


@router.get("/clients/block-form", response_class=HTMLResponse)
async def block_form(
    request: Request,
    _admin: AdminUserDep,
    depth: DepthQuery = 0,
) -> Response:
    block_id = f"b{uuid4().hex}"
    palette = ["#0d6efd", "#198754", "#6f42c1", "#fd7e14", "#dc3545"]
    border_color = palette[depth % len(palette)]
    return templates.TemplateResponse(
        request,
        "components/block_form.html",
        {
            "block_id": block_id,
            "depth": depth,
            "border_color": border_color,
        },
    )


@router.post("/clients/add-tree", response_class=HTMLResponse)
async def add_client_tree(
    request: Request,
    service: RadiusServiceDep,
    admin: AdminUserDep,
    payload_json: PayloadJsonOptionalForm = None,
) -> Response:
    if not payload_json:
        return Response(
            content="",
            media_type="text/html",
            headers={
                "HX-Trigger": json.dumps({"clientAddError": "payload_json is empty"})
            },
        )

    try:
        payload = ClientCreateTreePayload.model_validate_json(payload_json)
        result: UpsertResult = await service.create_or_update_client_tree(
            payload,
            actor_username=admin.username,
        )
    except Exception as e:
        logger.error("Error adding client: %s", type(e).__name__)
        return Response(
            content="",
            media_type="text/html",
            headers={
                "HX-Trigger": json.dumps(
                    {"clientAddError": "Unable to add client. Check form values."}
                )
            },
        )

    resp = HTMLResponse(
        content=_render_table_fragment_with_reload_alert(
            request,
            "components/client_row_with_details.html",
            {
                "client": _client_row_context(request, result.client),
                REVEAL_ALLOWED_CONTEXT_KEY: True,
            },
            result.reload_result,
            result.backup,
        ),
    )
    resp.headers["HX-Trigger"] = json.dumps(
        {
            "clientAdded": True,
            "reloadResult": {
                "status": result.reload_result.status.value,
                "detail": result.reload_result.detail,
            },
        }
    )
    return resp


# ──────────────────────────────────────────────
#  Dynamic routes AFTER (with {name})
# ──────────────────────────────────────────────


@router.get("/clients/{name}/edit-form", response_class=HTMLResponse)
async def get_edit_form(
    request: Request,
    name: str,
    service: RadiusServiceDep,
    _admin: AdminUserDep,
) -> Response:
    try:
        client_model = await service.get_client_edit_model(name)
    except ClientNotFoundError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=str(e)) from e

    return templates.TemplateResponse(
        request,
        "components/client_form_card.html",
        {"mode": "edit", "client": client_model},
    )


@router.get("/clients/create-form", response_class=HTMLResponse)
async def get_create_form(
    request: Request,
    _admin: AdminUserDep,
) -> Response:
    return templates.TemplateResponse(
        request,
        "components/client_form_card.html",
        {"mode": "create"},
    )


@router.put("/clients/{name}/tree", response_class=HTMLResponse)
async def update_client_tree(
    request: Request,
    name: str,
    service: RadiusServiceDep,
    payload_json: PayloadJsonForm,
    admin: AdminUserDep,
) -> Response:
    try:
        payload = ClientEditTreePayload.model_validate_json(payload_json)
        result: UpsertResult = await service.update_client_tree(
            name,
            payload,
            actor_username=admin.username,
        )
    except ClientNotFoundError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=str(e)) from e
    except (InvalidNodeIdError, DuplicateKeyError, MergeClientError, ValueError) as e:
        try:
            client_model = await service.get_client_edit_model(name)
        except ClientNotFoundError:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Client not found") from e

        error = "Invalid client data." if isinstance(e, ValidationError) else str(e)
        html = templates.get_template("components/client_form_card.html").render(
            request=request,
            mode="edit",
            client=client_model,
            error=error,
        )
        return HTMLResponse(content=html, status_code=400)

    resp = HTMLResponse(
        content=_render_with_reload_alert(
            request,
            "components/client_form_card.html",
            {"mode": "create"},
            result.reload_result,
            result.backup,
        ),
    )
    client_data = result.client
    reload_data = result.reload_result
    resp.headers["HX-Trigger"] = json.dumps(
        {
            "clientUpdated": client_data["name"],
            "reloadResult": {
                "status": reload_data.status.value,
                "detail": reload_data.detail,
            },
        }
    )
    return resp


@router.get("/clients/{name}/details", response_class=HTMLResponse)
async def get_client_details(
    request: Request,
    name: str,
    service: RadiusServiceDep,
) -> Response:
    details = await service.get_client_full_for_ui(name)
    details["kind"] = "client"
    return templates.TemplateResponse(
        request,
        "components/client_details.html",
        {
            "details": details,
            "client_secret_dom_id": _client_secret_dom_id(name, "details"),
            "client_secret_reveal_url": request.url_for(
                "reveal_client_secret", name=name
            ),
            CLIENT_SURFACE_CONTEXT_KEY: "details",
            REVEAL_ALLOWED_CONTEXT_KEY: _can_reveal_secret(request),
        },
    )


@router.post("/clients/{name}/secret/reveal", response_class=HTMLResponse)
async def reveal_client_secret(
    request: Request,
    name: str,
    service: RadiusServiceDep,
    admin: AdminUserDep,
    surface: SecretSurfaceForm = "details",
) -> Response:
    secret = await service.get_client_secret(name, actor_username=admin.username)
    return templates.TemplateResponse(
        request,
        "components/client_secret_revealed.html",
        {
            "secret": secret,
            "client_secret_dom_id": _client_secret_dom_id(name, surface),
            "client_secret_reveal_url": request.url_for(
                "reveal_client_secret", name=name
            ),
            CLIENT_SURFACE_CONTEXT_KEY: surface,
            REVEAL_ALLOWED_CONTEXT_KEY: True,
        },
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.delete("/clients/{name}", response_class=HTMLResponse)
async def delete_client(
    request: Request,
    name: str,
    service: RadiusServiceDep,
    admin: AdminUserDep,
) -> Response:
    result: DeleteResult = await service.delete_client(
        name, actor_username=admin.username
    )
    resp = HTMLResponse(
        content=_render_reload_alert(request, result.reload_result, result.backup),
        status_code=200,
    )
    resp.headers["HX-Trigger"] = json.dumps(
        {
            "clientDeleted": name,
            "reloadResult": {
                "status": result.reload_result.status.value,
                "detail": result.reload_result.detail,
            },
        }
    )
    return resp
