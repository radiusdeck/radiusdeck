from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemLoader
from starlette.templating import _TemplateResponse

from radiusdeck.auth.csrf import get_or_create_csrf_token
from radiusdeck.auth.session_keys import SESSION_CSRF_TOKEN
from radiusdeck.core.config import settings
from radiusdeck.services.backup_service import BackupService
from radiusdeck.services.local_auth_service import LocalAuthService
from radiusdeck.services.log_service import LogService
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.services.status_service import StatusService

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def csrf_template_context(request: Request) -> dict[str, Any]:
    user = getattr(request.state, "user", None)
    log_viewer_nav_visible = settings.freeradius_log_viewer_enabled and (
        settings.auth_method == "none" or getattr(user, "role", None) == "admin"
    )
    status_nav_visible = settings.auth_method == "none" or (
        getattr(user, "role", None) == "admin"
    )
    backups_nav_visible = settings.auth_method == "none" or (
        getattr(user, "role", None) == "admin"
    )

    if not settings.csrf_enabled:
        return {
            SESSION_CSRF_TOKEN: None,
            "csrf_header_name": settings.csrf_header_name,
            "csrf_form_field_name": settings.csrf_form_field_name,
            "csrf_hx_headers": None,
            "log_viewer_nav_visible": log_viewer_nav_visible,
            "status_nav_visible": status_nav_visible,
            "backups_nav_visible": backups_nav_visible,
        }

    try:
        session = request.session
    except AssertionError:
        return {
            SESSION_CSRF_TOKEN: None,
            "csrf_header_name": settings.csrf_header_name,
            "csrf_form_field_name": settings.csrf_form_field_name,
            "csrf_hx_headers": None,
            "log_viewer_nav_visible": log_viewer_nav_visible,
            "status_nav_visible": status_nav_visible,
            "backups_nav_visible": backups_nav_visible,
        }

    token = get_or_create_csrf_token(session)
    return {
        SESSION_CSRF_TOKEN: token,
        "csrf_header_name": settings.csrf_header_name,
        "csrf_form_field_name": settings.csrf_form_field_name,
        "csrf_hx_headers": {settings.csrf_header_name: token},
        "log_viewer_nav_visible": log_viewer_nav_visible,
        "status_nav_visible": status_nav_visible,
        "backups_nav_visible": backups_nav_visible,
    }


class RequestTemplates(Jinja2Templates):
    def TemplateResponse(self, *args: Any, **kwargs: Any) -> _TemplateResponse:
        request = (
            args[0] if args and isinstance(args[0], Request) else kwargs.get("request")
        )
        renderer = (
            getattr(request.app.state, "templates", None)
            if request is not None
            else None
        )
        if renderer is not None:
            return renderer.TemplateResponse(*args, **kwargs)  # type: ignore[no-any-return]
        return super().TemplateResponse(*args, **kwargs)


templates = RequestTemplates(
    directory=str(TEMPLATES_DIR),
    context_processors=[csrf_template_context],
)


def configure_template_search_paths(
    extension_paths: tuple[Path, ...],
) -> Jinja2Templates:
    search_paths = [str(TEMPLATES_DIR), *(str(path) for path in extension_paths)]
    renderer = Jinja2Templates(
        directory=str(TEMPLATES_DIR), context_processors=[csrf_template_context]
    )
    renderer.env.loader = FileSystemLoader(search_paths)
    return renderer


def get_templates() -> Jinja2Templates:
    return templates


def get_radius_service(request: Request) -> RadiusService:
    service: RadiusService = request.app.state.radius_service
    return service


def get_backup_service(request: Request) -> BackupService:
    service: BackupService = request.app.state.backup_service
    return service


def get_log_service(request: Request) -> LogService:
    service: LogService = request.app.state.log_service
    return service


def get_status_service(request: Request) -> StatusService:
    service: StatusService = request.app.state.status_service
    return service


def get_local_auth_service(request: Request) -> LocalAuthService:
    service = getattr(request.app.state, "local_auth_service", None)
    if not isinstance(service, LocalAuthService):
        raise RuntimeError("LocalAuthService is not configured")
    return service
