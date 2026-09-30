from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from radiusdeck.auth.local.models import LocalUserRecord, LocalUsersFile
from radiusdeck.repositories.local_users_store import LocalUsersStore


def make_users_file() -> LocalUsersFile:
    return LocalUsersFile(
        version=1,
        users=[
            LocalUserRecord(
                username="alice",
                role="admin",
                password_hash="$argon2id$alice",
                disabled=False,
            ),
            LocalUserRecord(
                username="bob",
                role="user",
                password_hash="$argon2id$bob",
                disabled=True,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_local_users_store_load_save_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "users.json"
    store = LocalUsersStore(path)
    expected = make_users_file()

    await store.save(expected)
    loaded = await store.load()

    assert loaded == expected
    assert path.read_text(encoding="utf-8").endswith("\n")


@pytest.mark.asyncio
async def test_local_users_store_missing_file_is_error(tmp_path: Path) -> None:
    store = LocalUsersStore(tmp_path / "missing-users.json")

    with pytest.raises(FileNotFoundError):
        await store.load()


@pytest.mark.asyncio
async def test_local_users_store_locked_serializes_concurrent_work(
    tmp_path: Path,
) -> None:
    store = LocalUsersStore(tmp_path / "users.json")
    order: list[str] = []
    first_entered = asyncio.Event()

    async def first_task() -> None:
        async with store.locked():
            order.append("first-enter")
            first_entered.set()
            await asyncio.sleep(0.05)
            order.append("first-exit")

    async def second_task() -> None:
        await first_entered.wait()
        order.append("second-waiting")
        async with store.locked():
            order.append("second-enter")

    await asyncio.gather(first_task(), second_task())

    assert order == ["first-enter", "second-waiting", "first-exit", "second-enter"]
