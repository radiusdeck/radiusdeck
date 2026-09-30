from __future__ import annotations

from pathlib import Path

import pytest

from radiusdeck.auth.local.models import LocalUserRecord, LocalUsersFile
from radiusdeck.auth.local.passwords import hash_password
from radiusdeck.repositories.local_users_store import LocalUsersStore
from radiusdeck.services.local_auth_service import LocalAuthService


async def make_service(tmp_path: Path) -> LocalAuthService:
    store = LocalUsersStore(tmp_path / "users.json")
    await store.save(
        LocalUsersFile(
            version=1,
            users=[
                LocalUserRecord(
                    username="alice",
                    role="admin",
                    password_hash=hash_password("alice-password"),
                ),
                LocalUserRecord(
                    username="bob",
                    role="user",
                    password_hash=hash_password("bob-password"),
                ),
                LocalUserRecord(
                    username="disabled-user",
                    role="admin",
                    password_hash=hash_password("disabled-password"),
                    disabled=True,
                ),
            ],
        )
    )
    return LocalAuthService(store)


@pytest.mark.asyncio
async def test_local_auth_service_authenticates_valid_user(tmp_path: Path) -> None:
    service = await make_service(tmp_path)

    user = await service.authenticate("alice", "alice-password")

    assert user is not None
    assert user.username == "alice"
    assert user.display_name == "alice"
    assert user.role == "admin"
    assert user.auth_method == "local"


@pytest.mark.asyncio
async def test_local_auth_service_returns_user_role(tmp_path: Path) -> None:
    service = await make_service(tmp_path)

    user = await service.authenticate("bob", "bob-password")

    assert user is not None
    assert user.username == "bob"
    assert user.role == "user"


@pytest.mark.asyncio
async def test_local_auth_service_rejects_wrong_password(tmp_path: Path) -> None:
    service = await make_service(tmp_path)

    assert await service.authenticate("alice", "wrong-password") is None


@pytest.mark.asyncio
async def test_local_auth_service_rejects_unknown_user(tmp_path: Path) -> None:
    service = await make_service(tmp_path)

    assert await service.authenticate("charlie", "password") is None


@pytest.mark.asyncio
async def test_local_auth_service_rejects_disabled_user(tmp_path: Path) -> None:
    service = await make_service(tmp_path)

    assert await service.authenticate("disabled-user", "disabled-password") is None


@pytest.mark.asyncio
async def test_local_auth_service_strips_username(tmp_path: Path) -> None:
    service = await make_service(tmp_path)

    user = await service.authenticate("  alice  ", "alice-password")

    assert user is not None
    assert user.username == "alice"


@pytest.mark.asyncio
async def test_local_auth_service_rejects_blank_username(tmp_path: Path) -> None:
    service = await make_service(tmp_path)

    assert await service.authenticate("  ", "alice-password") is None
