from __future__ import annotations

import logging

from radiusdeck.auth.local.passwords import verify_password
from radiusdeck.auth.models import CurrentUser
from radiusdeck.repositories.local_users_store import LocalUsersStore

logger = logging.getLogger(__name__)


class LocalAuthService:
    def __init__(self, store: LocalUsersStore) -> None:
        self._store = store

    async def authenticate(self, username: str, password: str) -> CurrentUser | None:
        normalized_username = username.strip()
        if not normalized_username:
            logger.info("Local login failed: empty username")
            return None

        async with self._store.locked():
            users_file = await self._store.load()

        user = next(
            (
                record
                for record in users_file.users
                if record.username == normalized_username
            ),
            None,
        )

        if user is None:
            logger.info(
                "Local login failed: username=%s reason=not_found", normalized_username
            )
            return None

        if user.disabled:
            logger.info(
                "Local login failed: username=%s reason=disabled", normalized_username
            )
            return None

        if not verify_password(user.password_hash, password):
            logger.info(
                "Local login failed: username=%s reason=invalid_password",
                normalized_username,
            )
            return None

        logger.info("Local login succeeded: username=%s", normalized_username)
        return CurrentUser(
            username=user.username,
            display_name=user.username,
            role=user.role,
            auth_method="local",
        )
