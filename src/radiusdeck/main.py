from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from radiusdeck.auth.middleware import (
    AuthGuardMiddleware,
    CsrfMiddleware,
    ExtensionAuthenticationMiddleware,
    UserContextMiddleware,
)
from radiusdeck.core.config import settings
from radiusdeck.core.logging import setup_logging
from radiusdeck.core.middleware import RequestContextMiddleware
from radiusdeck.core.startup_warnings import get_startup_warnings
from radiusdeck.extensions.api import ExtensionDefinition
from radiusdeck.extensions.contributions import (
    CollectedContributions,
    RouteAccess,
    RoutePolicy,
    RoutePolicyContribution,
)
from radiusdeck.extensions.loader import discover_extensions
from radiusdeck.extensions.route_policy import (
    build_route_policy_registry,
    policies_for_router,
    policies_for_routes,
)
from radiusdeck.extensions.runtime import (
    BaseRuntimeServices,
    ExtensionRuntimeContext,
    ExtensionRuntimeManager,
    ExtensionRuntimeRegistry,
)
from radiusdeck.extensions.validation import collect_contributions, validate_auth_method
from radiusdeck.integrations.null_reload_client import NullReloadClient
from radiusdeck.integrations.sidecar_health_client import SidecarHealthClient
from radiusdeck.integrations.sidecar_reload_client import SidecarReloadClient
from radiusdeck.repositories.backup_store import BackupStore
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.repositories.file_diagnostics import FileDiagnostics
from radiusdeck.repositories.local_users_store import LocalUsersStore
from radiusdeck.repositories.log_file_store import LogFileStore
from radiusdeck.services.backup_models import BackupError
from radiusdeck.services.backup_service import BackupService
from radiusdeck.services.local_auth_service import LocalAuthService
from radiusdeck.services.log_service import LogService
from radiusdeck.services.operation_policy import OperationPolicySlot
from radiusdeck.services.ports import ReloadPort
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.services.status_ports import StatusProbePort
from radiusdeck.services.status_service import StatusService
from radiusdeck.version import __version__
from radiusdeck.web.constants import UI_HOME_PATH
from radiusdeck.web.deps import configure_template_search_paths
from radiusdeck.web.endpoints import auth as auth_endpoints
from radiusdeck.web.endpoints import health
from radiusdeck.web.exception_handlers import register_exception_handlers
from radiusdeck.web.router import api_router as web_router

BASE_DIR = Path(__file__).resolve().parent

setup_logging(
    app_name=settings.PROJECT_NAME,
    level=settings.LOG_LEVEL,
    log_format=settings.LOG_FORMAT,
)
logger = logging.getLogger(__name__)


@dataclass
class _BaseResources:
    services: BaseRuntimeServices
    sidecar_http_client: httpx.AsyncClient | None

    async def close(self) -> None:
        if self.sidecar_http_client is not None:
            await self.sidecar_http_client.aclose()


async def _create_base_resources(
    app: FastAPI,
    contributions: CollectedContributions,
) -> _BaseResources:
    access_policy = OperationPolicySlot()
    app.state.operation_policy = access_policy
    clients_store = ClientsConfStore(settings.RADIUS_CLIENTS_PATH)
    sidecar_http_client: httpx.AsyncClient | None = None
    status_probe: StatusProbePort | None = None
    reloader: ReloadPort
    if settings.SIDECAR_RELOAD_ENABLED:
        sidecar_http_client = httpx.AsyncClient(
            timeout=settings.SIDECAR_RELOAD_TIMEOUT_SECONDS
        )
        reloader = SidecarReloadClient(
            http_client=sidecar_http_client,
            reload_url=str(settings.SIDECAR_RELOAD_URL),
            token=(
                settings.SIDECAR_RELOAD_TOKEN.get_secret_value()
                if settings.SIDECAR_RELOAD_TOKEN
                else None
            ),
        )
        if settings.SIDECAR_HEALTH_URL is not None:
            status_probe = SidecarHealthClient(
                http_client=sidecar_http_client,
                health_url=str(settings.SIDECAR_HEALTH_URL),
                token=(
                    settings.SIDECAR_RELOAD_TOKEN.get_secret_value()
                    if settings.SIDECAR_RELOAD_TOKEN
                    else None
                ),
            )
    else:
        reloader = NullReloadClient()

    backup_store = BackupStore(
        settings.backup_dir,
        retention_count=100,
        max_age_days=None,
        pruning_enabled=not contributions.preserve_external_backup_history,
    )
    backup_service = BackupService(
        store=backup_store,
        clients_store=clients_store,
        reloader=reloader,
        enabled=settings.backup_enabled,
        app_version=__version__,
    )
    try:
        await backup_service.initialize()
    except BackupError as exc:
        logger.error("Backup storage initialization failed: %s", exc)

    radius_service = RadiusService(
        store=clients_store,
        reloader=reloader,
        backup=backup_service,
    )
    log_store = LogFileStore(
        path=settings.freeradius_log_path,
        max_bytes=settings.freeradius_log_max_bytes,
    )
    log_service = LogService(
        store=log_store,
        enabled=settings.freeradius_log_viewer_enabled,
        default_lines=settings.freeradius_log_default_lines,
    )
    status_service = StatusService(
        settings=settings,
        clients_store=clients_store,
        log_service=log_service,
        file_diagnostics=FileDiagnostics(),
        reload_probe=status_probe,
        app_version=__version__,
        backup_service=backup_service,
    )
    local_auth_service: LocalAuthService | None = None
    if settings.auth_method == "local":
        assert settings.local_users_path is not None
        local_auth_service = LocalAuthService(
            LocalUsersStore(settings.local_users_path)
        )

    app.state.radius_service = radius_service
    app.state.backup_service = backup_service
    app.state.log_service = log_service
    app.state.status_service = status_service
    app.state.local_auth_service = local_auth_service

    return _BaseResources(
        services=BaseRuntimeServices(
            radius=radius_service,
            backup=backup_service,
            logs=log_service,
            status=status_service,
            local_auth=local_auth_service,
            operation_policy=access_policy,
        ),
        sidecar_http_client=sidecar_http_client,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    contributions = getattr(
        app.state,
        "extension_contributions",
        collect_contributions(()),
    )
    definitions = getattr(app.state, "extension_definitions", ())
    resources = await _create_base_resources(app, contributions)
    registry = ExtensionRuntimeRegistry()
    app.state.extension_runtime_registry = registry
    manager = ExtensionRuntimeManager(
        definitions,
        ExtensionRuntimeContext(
            services=resources.services,
            registry=registry,
            extension_settings=contributions.extension_settings,
        ),
    )
    try:
        await manager.startup()
        try:
            yield
        finally:
            await manager.shutdown()
    finally:
        await resources.close()
        logger.info("Application shutdown complete.")


def create_app(
    *,
    extensions: tuple[ExtensionDefinition, ...] | None = None,
) -> FastAPI:
    definitions = discover_extensions() if extensions is None else extensions
    contributions = collect_contributions(definitions)
    validate_auth_method(settings.auth_method, contributions)
    application = FastAPI(
        title="FreeRADIUS API Manager",
        version=__version__,
        lifespan=lifespan,
    )
    application.state.extension_definitions = definitions
    application.state.extension_contributions = contributions
    register_exception_handlers(application)

    framework_routes = tuple(application.routes)
    application.mount(
        "/static",
        StaticFiles(directory=str(BASE_DIR / "static")),
        name="static",
    )
    application.include_router(auth_endpoints.router, tags=["auth"])
    application.include_router(health.router, tags=["system"])
    application.include_router(web_router, prefix="/ui")

    @application.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url=UI_HOME_PATH)

    for router_contribution in contributions.routers:
        application.include_router(
            router_contribution.router,
            prefix=router_contribution.prefix,
            tags=list(router_contribution.tags),
        )
    for static_contribution in contributions.static_mounts:
        application.mount(
            static_contribution.path,
            StaticFiles(directory=str(static_contribution.directory)),
            name=static_contribution.name,
        )
    application.state.templates = configure_template_search_paths(
        contributions.template_search_paths
    )

    public = RoutePolicy(RouteAccess.PUBLIC, csrf_protected=False)
    public_with_csrf = RoutePolicy(RouteAccess.PUBLIC, csrf_protected=True)
    browser = RoutePolicy(RouteAccess.PROTECTED_BROWSER, csrf_protected=True)
    policy_contributions: list[RoutePolicyContribution] = []
    policy_contributions.extend(policies_for_routes(framework_routes, policy=browser))
    policy_contributions.append(
        RoutePolicyContribution(
            path="/static",
            methods=frozenset({"*"}),
            policy=public,
        )
    )
    policy_contributions.extend(
        policies_for_router(
            auth_endpoints.router,
            prefix="",
            policy=public_with_csrf,
        )
    )
    policy_contributions.extend(
        policies_for_router(health.router, prefix="", policy=public)
    )
    policy_contributions.extend(
        policies_for_router(web_router, prefix="/ui", policy=browser)
    )
    policy_contributions.append(
        RoutePolicyContribution(
            path="/",
            methods=frozenset({"GET"}),
            policy=browser,
        )
    )
    for router_contribution in contributions.routers:
        policy_contributions.extend(router_contribution.policies)
    for static_contribution in contributions.static_mounts:
        policy_contributions.append(
            RoutePolicyContribution(
                path=static_contribution.path,
                methods=frozenset({"*"}),
                policy=public,
            )
        )

    provider_ids = frozenset(
        provider.provider_id for provider in contributions.authentication_providers
    )
    registry = build_route_policy_registry(
        application.routes,
        tuple(policy_contributions),
        authentication_provider_ids=provider_ids,
    )
    application.state.route_policy_registry = registry

    application.add_middleware(CsrfMiddleware, route_policies=registry)
    application.add_middleware(
        AuthGuardMiddleware,
        route_policies=registry,
    )
    application.add_middleware(
        ExtensionAuthenticationMiddleware,
        route_policies=registry,
        providers=contributions.authentication_providers,
        browser_provider=contributions.browser_authentication,
    )
    if settings.auth_method != "none":
        application.add_middleware(
            UserContextMiddleware,
            route_policies=registry,
        )
        assert settings.session_secret_key is not None
        application.add_middleware(
            SessionMiddleware,
            secret_key=settings.session_secret_key.get_secret_value(),
            max_age=settings.session_max_age_seconds,
            https_only=settings.effective_secure_cookies,
            same_site=settings.session_samesite,
            session_cookie=settings.session_cookie_name,
        )
    application.add_middleware(RequestContextMiddleware)

    logger.info("Application created with extensions=%s", contributions.extension_names)
    logger.info("ENV APP_AUTH_METHOD=%r", os.getenv("APP_AUTH_METHOD"))
    logger.info("Effective APP_AUTH_METHOD=%s", settings.auth_method)
    for startup_warning in get_startup_warnings(settings):
        logger.warning(startup_warning)
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("radiusdeck.main:app", host="0.0.0.0", port=8000, reload=True)
