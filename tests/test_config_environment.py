from __future__ import annotations

import pytest

from radiusdeck.core.config import Settings


def _clear_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("APP_ENVIRONMENT", raising=False)


def test_environment_defaults_to_production(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_environment(monkeypatch)

    assert Settings(_env_file=None).env == "production"


def test_deprecated_environment_alias_is_accepted_with_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_environment(monkeypatch)
    monkeypatch.setenv("APP_ENVIRONMENT", "development")

    with pytest.warns(DeprecationWarning, match="APP_ENVIRONMENT is deprecated"):
        configured = Settings(_env_file=None)

    assert configured.env == "development"


def test_app_env_wins_and_conflict_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_ENVIRONMENT", "development")

    with pytest.warns(DeprecationWarning, match="Conflicting values"):
        configured = Settings(_env_file=None)

    assert configured.env == "test"


def test_matching_alias_still_warns_without_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_ENVIRONMENT", "test")

    with pytest.warns(DeprecationWarning) as warnings:
        configured = Settings(_env_file=None)

    assert configured.env == "test"
    assert "Conflicting values" not in str(warnings[0].message)
