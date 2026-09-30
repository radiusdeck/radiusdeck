from __future__ import annotations

import pytest
from pydantic import ValidationError

from radiusdeck.core.config import Settings


def test_session_secret_not_required_when_auth_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_METHOD", "none")
    monkeypatch.delenv("APP_SESSION_SECRET_KEY", raising=False)
    s = Settings(_env_file=None)
    assert s.auth_method == "none"
    assert s.session_secret_key is None


def test_session_secret_required_when_auth_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_METHOD", "local")
    monkeypatch.delenv("APP_SESSION_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_session_secret_accepts_value_when_auth_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_METHOD", "local")
    monkeypatch.setenv("APP_SESSION_SECRET_KEY", "super-secret")
    monkeypatch.setenv("APP_LOCAL_USERS_PATH", "/tmp/radiusdeck-users.json")
    s = Settings(_env_file=None)
    assert s.auth_method == "local"
    assert s.session_secret_key is not None
    assert s.session_max_age_seconds == 86400
    assert s.session_idle_timeout_seconds == 86400
    assert s.session_cookie_name == "radiusdeck_session"
    assert s.session_samesite == "lax"
    assert s.secure_cookies is None


def test_session_idle_timeout_accepts_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_METHOD", "none")
    monkeypatch.setenv("APP_SESSION_IDLE_TIMEOUT_SECONDS", "1800")

    s = Settings(_env_file=None)

    assert s.session_idle_timeout_seconds == 1800


def test_session_idle_timeout_rejects_negative_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_METHOD", "none")
    monkeypatch.setenv("APP_SESSION_IDLE_TIMEOUT_SECONDS", "-1")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_local_users_path_required_when_auth_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_METHOD", "local")
    monkeypatch.setenv("APP_SESSION_SECRET_KEY", "super-secret")
    monkeypatch.delenv("APP_LOCAL_USERS_PATH", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_local_users_path_accepts_value_when_auth_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_METHOD", "local")
    monkeypatch.setenv("APP_SESSION_SECRET_KEY", "super-secret")
    monkeypatch.setenv("APP_LOCAL_USERS_PATH", "/tmp/radiusdeck-users.json")

    s = Settings(_env_file=None)

    assert s.local_users_path is not None
    assert str(s.local_users_path) == "/tmp/radiusdeck-users.json"


def test_https_public_url_enables_secure_cookies_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_METHOD", "local")
    monkeypatch.setenv("APP_SESSION_SECRET_KEY", "super-secret")
    monkeypatch.setenv("APP_LOCAL_USERS_PATH", "/tmp/radiusdeck-users.json")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://radiusdeck.example.com")
    monkeypatch.delenv("APP_SECURE_COOKIES", raising=False)

    s = Settings(_env_file=None)

    assert s.secure_cookies is None
    assert s.effective_secure_cookies is True


def test_http_public_url_disables_secure_cookies_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_METHOD", "local")
    monkeypatch.setenv("APP_SESSION_SECRET_KEY", "super-secret")
    monkeypatch.setenv("APP_LOCAL_USERS_PATH", "/tmp/radiusdeck-users.json")
    monkeypatch.setenv("APP_PUBLIC_URL", "http://localhost:8000")
    monkeypatch.delenv("APP_SECURE_COOKIES", raising=False)

    s = Settings(_env_file=None)

    assert s.secure_cookies is None
    assert s.effective_secure_cookies is False


def test_explicit_secure_cookie_setting_overrides_public_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_METHOD", "local")
    monkeypatch.setenv("APP_SESSION_SECRET_KEY", "super-secret")
    monkeypatch.setenv("APP_LOCAL_USERS_PATH", "/tmp/radiusdeck-users.json")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://radiusdeck.example.com")
    monkeypatch.setenv("APP_SECURE_COOKIES", "false")

    s = Settings(_env_file=None)

    assert s.secure_cookies is False
    assert s.effective_secure_cookies is False
