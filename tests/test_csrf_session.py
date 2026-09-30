from __future__ import annotations

from typing import Any

from radiusdeck.auth.csrf import get_or_create_csrf_token, validate_csrf_token
from radiusdeck.auth.session_keys import SESSION_CSRF_TOKEN


def test_get_or_create_csrf_token_creates_and_stores_token() -> None:
    session: dict[str, Any] = {}

    token = get_or_create_csrf_token(session)

    assert isinstance(token, str)
    assert token
    assert session[SESSION_CSRF_TOKEN] == token


def test_get_or_create_csrf_token_reuses_existing_token() -> None:
    session: dict[str, Any] = {SESSION_CSRF_TOKEN: "existing-token"}

    token = get_or_create_csrf_token(session)

    assert token == "existing-token"
    assert session[SESSION_CSRF_TOKEN] == "existing-token"


def test_get_or_create_csrf_token_replaces_invalid_existing_token() -> None:
    session: dict[str, Any] = {SESSION_CSRF_TOKEN: ""}

    token = get_or_create_csrf_token(session)

    assert token
    assert token != ""
    assert session[SESSION_CSRF_TOKEN] == token


def test_validate_csrf_token_accepts_matching_token() -> None:
    session: dict[str, Any] = {SESSION_CSRF_TOKEN: "valid-token"}

    assert validate_csrf_token(session, "valid-token")


def test_validate_csrf_token_rejects_mismatching_token() -> None:
    session: dict[str, Any] = {SESSION_CSRF_TOKEN: "valid-token"}

    assert not validate_csrf_token(session, "invalid-token")


def test_validate_csrf_token_rejects_missing_provided_token() -> None:
    session: dict[str, Any] = {SESSION_CSRF_TOKEN: "valid-token"}

    assert not validate_csrf_token(session, None)


def test_validate_csrf_token_rejects_missing_session_token() -> None:
    session: dict[str, Any] = {}

    assert not validate_csrf_token(session, "valid-token")


def test_validate_csrf_token_rejects_invalid_session_token() -> None:
    session: dict[str, Any] = {SESSION_CSRF_TOKEN: 123}

    assert not validate_csrf_token(session, "valid-token")
