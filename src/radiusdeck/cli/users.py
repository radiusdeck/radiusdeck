from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO, cast

from radiusdeck.auth.local.models import LocalUserRecord, LocalUsersFile
from radiusdeck.auth.local.passwords import hash_password
from radiusdeck.auth.models import Role
from radiusdeck.repositories.local_users_store import LocalUsersStore


class LocalUsersCliError(Exception):
    pass


async def _load_or_empty(store: LocalUsersStore) -> LocalUsersFile:
    try:
        return await store.load()
    except FileNotFoundError:
        return LocalUsersFile(version=1, users=[])


def _find_user(data: LocalUsersFile, username: str) -> LocalUserRecord | None:
    return next((user for user in data.users if user.username == username), None)


def _replace_user(
    data: LocalUsersFile,
    updated_user: LocalUserRecord,
) -> LocalUsersFile:
    return LocalUsersFile(
        version=data.version,
        users=[
            updated_user if user.username == updated_user.username else user
            for user in data.users
        ],
    )


async def create_user(
    store: LocalUsersStore,
    *,
    username: str,
    role: Role,
    password: str,
) -> LocalUserRecord:
    async with store.locked():
        data = await _load_or_empty(store)
        if _find_user(data, username) is not None:
            raise LocalUsersCliError(f"User already exists: {username}")

        user = LocalUserRecord(
            username=username,
            role=role,
            password_hash=hash_password(password),
            disabled=False,
        )
        await store.save(
            LocalUsersFile(version=data.version, users=[*data.users, user])
        )
        return user


async def change_password(
    store: LocalUsersStore,
    *,
    username: str,
    password: str,
) -> LocalUserRecord:
    async with store.locked():
        data = await _load_or_empty(store)
        user = _find_user(data, username)
        if user is None:
            raise LocalUsersCliError(f"User not found: {username}")

        updated_user = user.model_copy(
            update={"password_hash": hash_password(password)}
        )
        await store.save(_replace_user(data, updated_user))
        return updated_user


async def set_role(
    store: LocalUsersStore,
    *,
    username: str,
    role: Role,
) -> LocalUserRecord:
    async with store.locked():
        data = await _load_or_empty(store)
        user = _find_user(data, username)
        if user is None:
            raise LocalUsersCliError(f"User not found: {username}")

        updated_user = user.model_copy(update={"role": role})
        await store.save(_replace_user(data, updated_user))
        return updated_user


async def set_disabled(
    store: LocalUsersStore,
    *,
    username: str,
    disabled: bool,
) -> LocalUserRecord:
    async with store.locked():
        data = await _load_or_empty(store)
        user = _find_user(data, username)
        if user is None:
            raise LocalUsersCliError(f"User not found: {username}")

        updated_user = user.model_copy(update={"disabled": disabled})
        await store.save(_replace_user(data, updated_user))
        return updated_user


async def delete_user(store: LocalUsersStore, *, username: str) -> None:
    async with store.locked():
        data = await _load_or_empty(store)
        user = _find_user(data, username)
        if user is None:
            raise LocalUsersCliError(f"User not found: {username}")

        await store.save(
            LocalUsersFile(
                version=data.version,
                users=[user for user in data.users if user.username != username],
            )
        )


async def list_users(store: LocalUsersStore) -> list[LocalUserRecord]:
    async with store.locked():
        data = await _load_or_empty(store)
        return list(data.users)


def _prompt_password(label: str) -> str:
    password = getpass.getpass(f"{label}: ")
    confirmation = getpass.getpass(f"{label} again: ")
    if password != confirmation:
        raise LocalUsersCliError("Passwords do not match")
    if not password:
        raise LocalUsersCliError("Password must not be empty")
    return password


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage RadiusDeck local users")
    parser.add_argument(
        "--path",
        required=True,
        type=Path,
        help="Path to the local users file",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a local user")
    create_parser.add_argument("--username", required=True)
    create_parser.add_argument("--role", required=True, choices=("admin", "user"))

    passwd_parser = subparsers.add_parser("passwd", help="Change a local user password")
    passwd_parser.add_argument("--username", required=True)

    set_role_parser = subparsers.add_parser("set-role", help="Change a local user role")
    set_role_parser.add_argument("--username", required=True)
    set_role_parser.add_argument("--role", required=True, choices=("admin", "user"))

    disable_parser = subparsers.add_parser("disable", help="Disable a local user")
    disable_parser.add_argument("--username", required=True)

    enable_parser = subparsers.add_parser("enable", help="Enable a local user")
    enable_parser.add_argument("--username", required=True)

    delete_parser = subparsers.add_parser("delete", help="Delete a local user")
    delete_parser.add_argument("--username", required=True)

    subparsers.add_parser("list", help="List local users")

    return parser


async def run(args: argparse.Namespace, stdout: TextIO) -> int:
    store = LocalUsersStore(args.path)

    if args.command == "create":
        password = _prompt_password("Password")
        user = await create_user(
            store,
            username=args.username,
            role=cast(Role, args.role),
            password=password,
        )
        print(f"Created user {user.username} ({user.role})", file=stdout)
        return 0

    if args.command == "passwd":
        password = _prompt_password("New password")
        user = await change_password(store, username=args.username, password=password)
        print(f"Changed password for {user.username}", file=stdout)
        return 0

    if args.command == "set-role":
        user = await set_role(store, username=args.username, role=cast(Role, args.role))
        print(f"Changed role for {user.username} to {user.role}", file=stdout)
        return 0

    if args.command == "disable":
        user = await set_disabled(store, username=args.username, disabled=True)
        print(f"Disabled user {user.username}", file=stdout)
        return 0

    if args.command == "enable":
        user = await set_disabled(store, username=args.username, disabled=False)
        print(f"Enabled user {user.username}", file=stdout)
        return 0

    if args.command == "delete":
        await delete_user(store, username=args.username)
        print(f"Deleted user {args.username}", file=stdout)
        return 0

    if args.command == "list":
        users = await list_users(store)
        for user in users:
            status = "disabled" if user.disabled else "enabled"
            print(f"{user.username}\t{user.role}\t{status}", file=stdout)
        return 0

    raise LocalUsersCliError(f"Unknown command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(run(args, sys.stdout))
    except LocalUsersCliError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
