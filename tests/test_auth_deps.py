from __future__ import annotations

import pytest
from fastapi import HTTPException, Request
from starlette.datastructures import State
from starlette.types import Scope

from radiusdeck.auth.deps import get_current_user_optional, require_authenticated_user
from radiusdeck.auth.models import CurrentUser
from radiusdeck.core.config import settings


def _make_request_with_state(state: State) -> Request:
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
    }
    req = Request(scope)
    req._state = state
    return req


def test_get_current_user_optional_returns_none_when_missing() -> None:
    state = State()
    req = _make_request_with_state(state)
    assert get_current_user_optional(req) is None


def test_get_current_user_optional_returns_user_when_present() -> None:
    state = State()
    state.user = CurrentUser(
        username="alice",
        display_name="Alice",
        role="admin",
        auth_method="local",
    )
    req = _make_request_with_state(state)
    user = get_current_user_optional(req)
    assert user is not None
    assert user.username == "alice"


def test_get_current_user_optional_returns_current_user_when_present() -> None:
    state = State()
    state.current_user = CurrentUser(
        username="bob",
        display_name="Bob",
        role="user",
        auth_method="local",
    )
    req = _make_request_with_state(state)
    user = get_current_user_optional(req)
    assert user is not None
    assert user.username == "bob"


def test_require_authenticated_user_raises_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_method", "local")
    state = State()
    req = _make_request_with_state(state)

    with pytest.raises(HTTPException) as exc_info:
        require_authenticated_user(req)

    assert exc_info.value.status_code == 403


def test_require_authenticated_user_open_mode_returns_synthetic_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_method", "none")
    state = State()
    req = _make_request_with_state(state)

    user = require_authenticated_user(req)

    assert user.username == "anonymous"
    assert user.role == "admin"
