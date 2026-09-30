from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from radiusdeck.auth.csrf import get_or_create_csrf_token
from radiusdeck.auth.request_classification import is_htmx_request
from radiusdeck.auth.session import clear_session, set_user_session
from radiusdeck.core.config import settings
from radiusdeck.extensions.contributions import BrowserAuthenticationProvider
from radiusdeck.services.local_auth_service import LocalAuthService
from radiusdeck.web.constants import UI_HOME_PATH
from radiusdeck.web.deps import get_local_auth_service, templates

router = APIRouter()
LocalAuthServiceDep = Annotated[LocalAuthService, Depends(get_local_auth_service)]


def get_browser_provider(request: Request) -> BrowserAuthenticationProvider | None:
    contributions = getattr(request.app.state, "extension_contributions", None)
    provider: BrowserAuthenticationProvider | None = getattr(
        contributions, "browser_authentication", None
    )
    return provider


@router.get("/login", include_in_schema=False, response_model=None)
async def login(
    request: Request,
    provider: Annotated[
        BrowserAuthenticationProvider | None, Depends(get_browser_provider)
    ],
) -> Response:
    if settings.auth_method == "none":
        return RedirectResponse(url=UI_HOME_PATH, status_code=302)
    if provider is not None and provider.provider_id == settings.auth_method:
        return await provider.login(request)
    try:
        get_or_create_csrf_token(request.session)
    except AssertionError:
        pass
    return templates.TemplateResponse(
        request, "login.html", {"error": None, "username": ""}
    )


@router.post("/login", include_in_schema=False, response_model=None)
async def login_submit(
    request: Request,
    local_auth_service: LocalAuthServiceDep,
) -> Response:
    if settings.auth_method == "none":
        return RedirectResponse(url=UI_HOME_PATH, status_code=302)

    if settings.auth_method != "local":
        return HTMLResponse(
            "Login is not available for this auth method.", status_code=400
        )

    form = getattr(request.state, "csrf_form", None)
    if form is None:
        form = await request.form()
    username_value = form.get("username")
    password_value = form.get("password")
    username = username_value if isinstance(username_value, str) else ""
    password = password_value if isinstance(password_value, str) else ""

    user = await local_auth_service.authenticate(username, password)
    if user is None:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": "Invalid username or password.",
                "username": username.strip(),
            },
            status_code=401,
        )

    clear_session(request.session)
    set_user_session(request.session, user)
    return RedirectResponse(url=UI_HOME_PATH, status_code=302)


@router.post("/logout", include_in_schema=False, response_model=None)
async def logout(
    request: Request,
    provider: Annotated[
        BrowserAuthenticationProvider | None, Depends(get_browser_provider)
    ],
) -> Response:
    if provider is not None and provider.provider_id == settings.auth_method:
        return await provider.logout(request)
    try:
        clear_session(request.session)
    except AssertionError:
        pass
    if is_htmx_request(request):
        return Response(status_code=204, headers={"HX-Redirect": "/login"})
    return RedirectResponse(url="/login", status_code=302)
