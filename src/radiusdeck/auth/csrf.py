from __future__ import annotations

import hmac
import secrets
from collections.abc import Mapping, MutableMapping
from typing import Any

from radiusdeck.auth.session_keys import SESSION_CSRF_TOKEN


def get_or_create_csrf_token(session: MutableMapping[str, Any]) -> str:
    existing = session.get(SESSION_CSRF_TOKEN)
    if isinstance(existing, str) and existing:
        return existing

    token = secrets.token_urlsafe(32)
    session[SESSION_CSRF_TOKEN] = token
    return token


def validate_csrf_token(session: Mapping[str, Any], provided: str | None) -> bool:
    if provided is None:
        return False

    expected = session.get(SESSION_CSRF_TOKEN)
    if not isinstance(expected, str) or not expected:
        return False

    return hmac.compare_digest(expected, provided)
