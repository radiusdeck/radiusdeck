from __future__ import annotations

from radiusdeck.auth.authorization import (
    get_current_user_optional,
    require_any_authenticated_user,
)

require_authenticated_user = require_any_authenticated_user

__all__ = [
    "get_current_user_optional",
    "require_authenticated_user",
]
