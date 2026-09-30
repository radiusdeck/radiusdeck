from __future__ import annotations

from radiusdeck.auth.local.passwords import hash_password, verify_password


def test_hash_password_verifies_original_password() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert password_hash.startswith("$argon2")
    assert verify_password(password_hash, "correct horse battery staple") is True


def test_verify_password_rejects_wrong_password() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert verify_password(password_hash, "wrong password") is False


def test_verify_password_rejects_invalid_hash() -> None:
    assert verify_password("not-an-argon2-hash", "password") is False
