from __future__ import annotations

from radiusdeck.core.config import AuthMethod

CSRF_PROTECTED_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CSRF_PROTECTED_PUBLIC_PATHS: frozenset[str] = frozenset({"/login", "/logout"})
CSRF_FAILURE_DETAIL = "CSRF token missing or invalid"


def is_csrf_enabled(auth_method: AuthMethod) -> bool:
    return auth_method != "none"


def requires_csrf(auth_method: AuthMethod, method: str) -> bool:
    return is_csrf_enabled(auth_method) and method.upper() in CSRF_PROTECTED_METHODS
