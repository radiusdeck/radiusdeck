from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.types import ASGIApp

from radiusdeck.auth.csrf import validate_csrf_token
from radiusdeck.auth.csrf_policy import CSRF_FAILURE_DETAIL, requires_csrf
from radiusdeck.auth.session import (
    clear_session,
    get_user_from_session,
    is_session_idle_expired,
    touch_user_session,
)
from radiusdeck.core.config import settings
from radiusdeck.extensions.contributions import (
    AuthenticationDisposition,
    AuthenticationProvider,
    BrowserAuthenticationProvider,
    RouteAccess,
)
from radiusdeck.extensions.route_policy import RoutePolicyRegistry

logger = logging.getLogger(__name__)


class UserContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, route_policies: RoutePolicyRegistry) -> None:
        super().__init__(app)
        self._route_policies = route_policies

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        user = None
        session = getattr(request, "session", None)
        if isinstance(session, dict):
            user = get_user_from_session(session)
            if user is not None:
                if is_session_idle_expired(
                    session, settings.session_idle_timeout_seconds
                ):
                    clear_session(session)
                    user = None
                else:
                    policy = self._route_policies.lookup(request.scope)
                    if policy is not None and policy.access is not RouteAccess.PUBLIC:
                        touch_user_session(session)

        request.state.user = user
        return await call_next(request)


class ExtensionAuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        route_policies: RoutePolicyRegistry,
        providers: tuple[AuthenticationProvider, ...],
        browser_provider: BrowserAuthenticationProvider | None = None,
    ) -> None:
        super().__init__(app)
        self._route_policies = route_policies
        self._providers = {provider.provider_id: provider for provider in providers}
        self._browser_provider = browser_provider

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        policy = self._route_policies.lookup(request.scope)
        if policy is None:
            return await call_next(request)

        if self._browser_provider is not None:
            result = await self._browser_provider.authenticate(request)
            if result.disposition is AuthenticationDisposition.REJECTED:
                assert result.response is not None
                return result.response
            if result.disposition is AuthenticationDisposition.AUTHENTICATED:
                request.state.user = result.user

        for provider_id in policy.authentication_provider_ids:
            provider = self._providers[provider_id]
            result = await provider.authenticate(request)
            if result.disposition is AuthenticationDisposition.REJECTED:
                assert result.response is not None
                return result.response
            if result.disposition is AuthenticationDisposition.AUTHENTICATED:
                assert result.user is not None
                request.state.user = result.user
                request.state.authenticated_provider_id = provider_id
                break
        response = await call_next(request)
        if getattr(request.state, "private_response", False):
            response.headers["Cache-Control"] = "no-store"
        return response


class AuthGuardMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        route_policies: RoutePolicyRegistry,
        login_path: str = "/login",
    ) -> None:
        super().__init__(app)
        self._route_policies = route_policies
        self._login_path = login_path

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if settings.auth_method == "none":
            return await call_next(request)

        policy = self._route_policies.lookup(request.scope)
        if policy is None or policy.access is RouteAccess.PUBLIC:
            return await call_next(request)

        if getattr(request.state, "user", None) is not None:
            return await call_next(request)

        if policy.access is RouteAccess.PROTECTED_API:
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )

        if request.headers.get("HX-Request", "").lower() == "true":
            return Response(status_code=401, headers={"HX-Redirect": self._login_path})
        return RedirectResponse(url=self._login_path, status_code=302)


class CsrfMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, route_policies: RoutePolicyRegistry) -> None:
        super().__init__(app)
        self._route_policies = route_policies

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        policy = self._route_policies.lookup(request.scope)
        if (
            policy is None
            or not policy.csrf_protected
            or not requires_csrf(settings.auth_method, request.method)
        ):
            return await call_next(request)

        provider_id = getattr(request.state, "authenticated_provider_id", None)
        if provider_id in policy.csrf_exempt_provider_ids:
            return await call_next(request)

        session = getattr(request, "session", None)
        provided = await self._csrf_token_from_request(request)
        if isinstance(session, dict) and validate_csrf_token(session, provided):
            return await call_next(request)
        return self._failure_response(policy.access)

    async def _csrf_token_from_request(self, request: Request) -> str | None:
        header_value = request.headers.get(settings.csrf_header_name)
        if header_value:
            return header_value

        content_type = request.headers.get("content-type", "")
        if (
            "application/x-www-form-urlencoded" not in content_type
            and "multipart/form-data" not in content_type
        ):
            return None
        try:
            form = await request.form()
        except Exception:
            return None
        request.state.csrf_form = form
        value = form.get(settings.csrf_form_field_name)
        return value if isinstance(value, str) else None

    @staticmethod
    def _failure_response(access: RouteAccess) -> Response:
        if access is RouteAccess.PROTECTED_API:
            return JSONResponse(
                status_code=403,
                content={"detail": CSRF_FAILURE_DETAIL},
            )
        return Response(
            CSRF_FAILURE_DETAIL,
            status_code=403,
            media_type="text/html",
        )
