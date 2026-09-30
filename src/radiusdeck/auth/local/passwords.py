from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

_PASSWORD_HASHER = PasswordHasher()


def hash_password(plain: str) -> str:
    return _PASSWORD_HASHER.hash(plain)


def verify_password(hash: str, plain: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(hash, plain)
    except (Argon2Error, ValueError):
        return False
