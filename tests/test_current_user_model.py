from __future__ import annotations

from radiusdeck.auth.models import CurrentUser


def test_current_user_create() -> None:
    user = CurrentUser(
        username="alice",
        display_name="Alice",
        role="admin",
        auth_method="local",
    )
    assert user.username == "alice"
    assert user.display_name == "Alice"
    assert user.role == "admin"
    assert user.auth_method == "local"
