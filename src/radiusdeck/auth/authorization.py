from __future__ import annotations

import logging
from typing import NoReturn

from fastapi import HTTPException, Request, status

from radiusdeck.auth.models import CurrentUser
from radiusdeck.core.config import settings

logger = logging.getLogger(__name__)


def get_current_user_optional(request: Request) -> CurrentUser | None:
    user = getattr(request.state, "current_user", None)
    if user is None:
        user = getattr(request.state, "user", None)

    if user is None:
        scope_user = request.scope.get("user")
        if isinstance(scope_user, CurrentUser):
            user = scope_user

    return user


def _is_ui_request(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    if "text/html" in accept.lower():
        return True

    path = request.url.path
    return not path.startswith("/api")


def _raise_forbidden(request: Request) -> NoReturn:
    user = get_current_user_optional(request)
    username = user.username if user is not None else "anonymous"
    role = user.role if user is not None else "none"
    logger.warning(
        "Access denied: username=%s role=%s method=%s path=%s",
        username,
        role,
        request.method,
        request.url.path,
    )

    if _is_ui_request(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden",
    )


def require_any_authenticated_user(request: Request) -> CurrentUser:
    # OPEN MODE: allow everything without requiring a session/user
    if settings.auth_method == "none":
        return CurrentUser(
            username="anonymous",
            display_name="anonymous",
            role="admin",
            auth_method="local",
        )

    user = get_current_user_optional(request)
    if user is None:
        _raise_forbidden(request)
    return user


def require_admin_user(request: Request) -> CurrentUser:
    user = require_any_authenticated_user(request)

    # OPEN MODE already returns admin, but keep it explicit/readable:
    if settings.auth_method == "none":
        return user

    if getattr(user, "role", None) != "admin":
        _raise_forbidden(request)

    return user
