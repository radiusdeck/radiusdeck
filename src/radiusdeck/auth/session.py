from __future__ import annotations

import time
from collections.abc import Mapping, MutableMapping
from typing import Any, cast

from radiusdeck.auth.models import CurrentUser, Role

_SESSION_USER_KEY = "user"

# compact keys inside the user payload
_U = "u"
_DN = "dn"
_R = "r"
_AM = "am"
_IAT = "iat"
_LS = "ls"


def set_user_session(
    session: MutableMapping[str, Any], user: CurrentUser, *, now: int | None = None
) -> None:
    timestamp = int(time.time()) if now is None else now
    session[_SESSION_USER_KEY] = {
        _U: user.username,
        _DN: user.display_name,
        _R: user.role,
        _AM: user.auth_method,
        _IAT: timestamp,
        _LS: timestamp,
    }


def get_user_from_session(session: Mapping[str, Any]) -> CurrentUser | None:
    raw = session.get(_SESSION_USER_KEY)
    if not isinstance(raw, dict):
        return None

    username = raw.get(_U)
    display_name = raw.get(_DN)
    role = raw.get(_R)
    auth_method = raw.get(_AM)

    if not isinstance(username, str) or not username:
        return None
    if not isinstance(display_name, str) or not display_name:
        return None
    if role not in ("admin", "user"):
        return None
    if not isinstance(auth_method, str) or not auth_method:
        return None

    return CurrentUser(
        username=username,
        display_name=display_name,
        role=cast(Role, role),
        auth_method=auth_method,
    )


def clear_session(session: MutableMapping[str, Any]) -> None:
    # In practice, clearing everything is the safest.
    session.clear()


def is_session_idle_expired(
    session: Mapping[str, Any],
    idle_timeout_seconds: int,
    *,
    now: int | None = None,
) -> bool:
    if idle_timeout_seconds <= 0:
        return False

    raw = session.get(_SESSION_USER_KEY)
    if not isinstance(raw, dict):
        return False

    last_seen = raw.get(_LS)
    if not isinstance(last_seen, int):
        last_seen = raw.get(_IAT)
    if not isinstance(last_seen, int):
        return True

    current_time = int(time.time()) if now is None else now
    return current_time - last_seen > idle_timeout_seconds


def touch_user_session(
    session: MutableMapping[str, Any], *, now: int | None = None
) -> None:
    raw = session.get(_SESSION_USER_KEY)
    if not isinstance(raw, dict):
        return

    raw[_LS] = int(time.time()) if now is None else now
