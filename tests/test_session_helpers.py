from __future__ import annotations

from typing import Any

from radiusdeck.auth.models import CurrentUser
from radiusdeck.auth.session import (
    clear_session,
    get_user_from_session,
    is_session_idle_expired,
    set_user_session,
    touch_user_session,
)


def test_session_round_trip() -> None:
    session: dict[str, Any] = {}
    user = CurrentUser(
        username="alice",
        display_name="Alice",
        role="admin",
        auth_method="local",
    )

    set_user_session(session, user, now=100)
    restored = get_user_from_session(session)

    assert restored == user
    assert session["user"]["iat"] == 100
    assert session["user"]["ls"] == 100


def test_session_invalid_payload_returns_none() -> None:
    session: dict[str, Any] = {
        "user": {"u": "alice", "dn": "Alice", "r": "root", "am": "local"}
    }
    assert get_user_from_session(session) is None


def test_clear_session() -> None:
    session: dict[str, Any] = {"user": {"u": "a"}, "other": 123}
    clear_session(session)
    assert session == {}


def test_session_idle_timeout_uses_last_seen() -> None:
    session: dict[str, Any] = {}
    set_user_session(
        session,
        CurrentUser(
            username="alice",
            display_name="Alice",
            role="admin",
            auth_method="local",
        ),
        now=100,
    )

    assert not is_session_idle_expired(session, 30, now=130)
    assert is_session_idle_expired(session, 30, now=131)


def test_session_idle_timeout_can_be_disabled() -> None:
    session: dict[str, Any] = {"user": {"iat": 100, "ls": 100}}
    assert not is_session_idle_expired(session, 0, now=100_000)


def test_session_idle_timeout_falls_back_to_issued_at_for_old_sessions() -> None:
    session: dict[str, Any] = {"user": {"iat": 100}}
    assert not is_session_idle_expired(session, 30, now=130)
    assert is_session_idle_expired(session, 30, now=131)


def test_session_idle_timeout_expires_malformed_timestamp() -> None:
    session: dict[str, Any] = {"user": {"iat": "bad", "ls": "bad"}}
    assert is_session_idle_expired(session, 30, now=100)


def test_touch_user_session_updates_last_seen() -> None:
    session: dict[str, Any] = {}
    set_user_session(
        session,
        CurrentUser(
            username="alice",
            display_name="Alice",
            role="admin",
            auth_method="local",
        ),
        now=100,
    )

    touch_user_session(session, now=125)

    assert session["user"]["iat"] == 100
    assert session["user"]["ls"] == 125
