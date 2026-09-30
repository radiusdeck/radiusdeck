from __future__ import annotations

from pathlib import Path

import pytest

from radiusdeck.auth.local.passwords import verify_password
from radiusdeck.cli.users import (
    LocalUsersCliError,
    change_password,
    create_user,
    delete_user,
    list_users,
    set_disabled,
    set_role,
)
from radiusdeck.repositories.local_users_store import LocalUsersStore


@pytest.mark.asyncio
async def test_create_user_creates_file_and_hashes_password(tmp_path: Path) -> None:
    store = LocalUsersStore(tmp_path / "users.json")

    user = await create_user(
        store,
        username="alice",
        role="admin",
        password="alice-password",
    )
    data = await store.load()

    assert user.username == "alice"
    assert user.role == "admin"
    assert user.disabled is False
    assert data.users[0].username == "alice"
    assert verify_password(data.users[0].password_hash, "alice-password") is True
    assert data.users[0].password_hash != "alice-password"


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_username(tmp_path: Path) -> None:
    store = LocalUsersStore(tmp_path / "users.json")
    await create_user(
        store,
        username="alice",
        role="admin",
        password="alice-password",
    )

    with pytest.raises(LocalUsersCliError, match="User already exists: alice"):
        await create_user(
            store,
            username="alice",
            role="user",
            password="other-password",
        )


@pytest.mark.asyncio
async def test_change_password_updates_hash(tmp_path: Path) -> None:
    store = LocalUsersStore(tmp_path / "users.json")
    await create_user(
        store,
        username="alice",
        role="admin",
        password="old-password",
    )

    updated_user = await change_password(
        store,
        username="alice",
        password="new-password",
    )
    data = await store.load()

    assert updated_user.username == "alice"
    assert verify_password(data.users[0].password_hash, "old-password") is False
    assert verify_password(data.users[0].password_hash, "new-password") is True


@pytest.mark.asyncio
async def test_change_password_rejects_missing_user(tmp_path: Path) -> None:
    store = LocalUsersStore(tmp_path / "users.json")

    with pytest.raises(LocalUsersCliError, match="User not found: alice"):
        await change_password(store, username="alice", password="new-password")


@pytest.mark.asyncio
async def test_set_role_changes_user_role(tmp_path: Path) -> None:
    store = LocalUsersStore(tmp_path / "users.json")
    await create_user(
        store,
        username="alice",
        role="user",
        password="alice-password",
    )

    updated_user = await set_role(store, username="alice", role="admin")
    data = await store.load()

    assert updated_user.role == "admin"
    assert data.users[0].role == "admin"


@pytest.mark.asyncio
async def test_disable_and_enable_user(tmp_path: Path) -> None:
    store = LocalUsersStore(tmp_path / "users.json")
    await create_user(
        store,
        username="alice",
        role="admin",
        password="alice-password",
    )

    disabled_user = await set_disabled(store, username="alice", disabled=True)
    disabled_data = await store.load()
    enabled_user = await set_disabled(store, username="alice", disabled=False)
    enabled_data = await store.load()

    assert disabled_user.disabled is True
    assert disabled_data.users[0].disabled is True
    assert enabled_user.disabled is False
    assert enabled_data.users[0].disabled is False


@pytest.mark.asyncio
async def test_delete_user_removes_record(tmp_path: Path) -> None:
    store = LocalUsersStore(tmp_path / "users.json")
    await create_user(
        store,
        username="alice",
        role="admin",
        password="alice-password",
    )

    await delete_user(store, username="alice")
    data = await store.load()

    assert data.users == []


@pytest.mark.asyncio
async def test_list_users_returns_records(tmp_path: Path) -> None:
    store = LocalUsersStore(tmp_path / "users.json")
    await create_user(
        store,
        username="alice",
        role="admin",
        password="alice-password",
    )
    await create_user(
        store,
        username="bob",
        role="user",
        password="bob-password",
    )

    users = await list_users(store)

    assert [user.username for user in users] == ["alice", "bob"]
    assert [user.role for user in users] == ["admin", "user"]
