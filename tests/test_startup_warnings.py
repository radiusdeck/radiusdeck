from __future__ import annotations

import pytest

from radiusdeck.core.config import Settings
from radiusdeck.core.startup_warnings import get_startup_warnings


def test_startup_warnings_include_open_mode_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_METHOD", "none")

    warnings = get_startup_warnings(Settings())

    assert "APP_AUTH_METHOD=none. Do not expose this instance publicly." in warnings


def test_startup_warnings_include_auth_without_https_public_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_METHOD", "local")
    monkeypatch.setenv("APP_SESSION_SECRET_KEY", "super-secret")
    monkeypatch.setenv("APP_LOCAL_USERS_PATH", "/tmp/radiusdeck-users.json")
    monkeypatch.setenv("APP_PUBLIC_URL", "http://localhost:8000")

    warnings = get_startup_warnings(Settings())

    assert (
        "APP_AUTH_METHOD is enabled but APP_PUBLIC_URL does not use https://."
        in warnings
    )


def test_startup_warnings_include_development_session_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_METHOD", "local")
    monkeypatch.setenv("APP_SESSION_SECRET_KEY", "dev-session-secret-change-me")
    monkeypatch.setenv("APP_LOCAL_USERS_PATH", "/tmp/radiusdeck-users.json")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://radiusdeck.example.com")

    warnings = get_startup_warnings(Settings())

    assert (
        "APP_SESSION_SECRET_KEY appears to use a development/default value." in warnings
    )


def test_startup_warnings_include_https_with_disabled_secure_cookies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_METHOD", "local")
    monkeypatch.setenv("APP_SESSION_SECRET_KEY", "super-secret")
    monkeypatch.setenv("APP_LOCAL_USERS_PATH", "/tmp/radiusdeck-users.json")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://radiusdeck.example.com")
    monkeypatch.setenv("APP_SECURE_COOKIES", "false")

    warnings = get_startup_warnings(Settings())

    assert "Secure cookies are disabled while APP_PUBLIC_URL uses https://." in warnings
