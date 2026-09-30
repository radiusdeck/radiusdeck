from __future__ import annotations

import pytest
from pydantic import ValidationError

from radiusdeck.auth.local.models import (
    LOCAL_USERS_FILE_VERSION,
    LocalUserRecord,
    LocalUsersFile,
)


def test_local_users_file_accepts_valid_v1_structure() -> None:
    data = LocalUsersFile.model_validate(
        {
            "version": 1,
            "users": [
                {
                    "username": "alice",
                    "role": "admin",
                    "password_hash": "$argon2id$alice",
                    "disabled": False,
                },
                {
                    "username": "bob",
                    "role": "user",
                    "password_hash": "$argon2id$bob",
                    "disabled": True,
                },
            ],
        }
    )

    assert data.version == LOCAL_USERS_FILE_VERSION
    assert data.users == [
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
    ]


def test_local_user_record_defaults_disabled_to_false() -> None:
    user = LocalUserRecord.model_validate(
        {
            "username": "alice",
            "role": "admin",
            "password_hash": "$argon2id$alice",
        }
    )

    assert user.disabled is False


def test_local_users_file_rejects_duplicate_usernames() -> None:
    with pytest.raises(ValidationError, match="Duplicate local username: alice"):
        LocalUsersFile.model_validate(
            {
                "version": 1,
                "users": [
                    {
                        "username": "alice",
                        "role": "admin",
                        "password_hash": "$argon2id$alice",
                    },
                    {
                        "username": "alice",
                        "role": "user",
                        "password_hash": "$argon2id$other",
                    },
                ],
            }
        )


def test_local_user_record_rejects_invalid_role() -> None:
    with pytest.raises(ValidationError):
        LocalUserRecord.model_validate(
            {
                "username": "alice",
                "role": "operator",
                "password_hash": "$argon2id$alice",
            }
        )


def test_local_user_record_rejects_blank_required_fields() -> None:
    with pytest.raises(ValidationError):
        LocalUserRecord.model_validate(
            {
                "username": "  ",
                "role": "admin",
                "password_hash": "$argon2id$alice",
            }
        )

    with pytest.raises(ValidationError):
        LocalUserRecord.model_validate(
            {
                "username": "alice",
                "role": "admin",
                "password_hash": "  ",
            }
        )


def test_local_users_file_rejects_unknown_version() -> None:
    with pytest.raises(ValidationError, match="Unsupported local users file version"):
        LocalUsersFile.model_validate({"version": 2, "users": []})


def test_local_models_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LocalUserRecord.model_validate(
            {
                "username": "alice",
                "role": "admin",
                "password_hash": "$argon2id$alice",
                "email": "alice@example.test",
            }
        )

    with pytest.raises(ValidationError):
        LocalUsersFile.model_validate({"version": 1, "users": [], "format": "json"})
