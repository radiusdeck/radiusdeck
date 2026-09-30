from __future__ import annotations

import sys

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import SecretStr

from radiusdeck.core.config import settings
from radiusdeck.extensions import (
    RADIUSDECK_EXTENSION_API,
    AuthenticationResult,
    ExtensionDefinition,
    StructuralContributions,
)
from radiusdeck.extensions.errors import ExtensionConfigurationError
from radiusdeck.main import create_app


def test_zero_extension_community_app_boots_without_private_import() -> None:
    before = set(sys.modules)
    app = create_app(extensions=())

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200

    newly_imported = set(sys.modules) - before
    assert not any(
        name == "radiusdeck_pro" or name.startswith("radiusdeck_pro.")
        for name in newly_imported
    )


def test_structural_contributions_are_collected_before_lifespan() -> None:
    calls: list[str] = []

    def load_settings() -> object:
        calls.append("settings")
        return {"ready": True}

    def contribute(extension_settings: object | None) -> StructuralContributions:
        calls.append(f"structure:{extension_settings!r}")
        return StructuralContributions()

    extension = ExtensionDefinition(
        name="structural",
        extension_api_version=RADIUSDECK_EXTENSION_API,
        settings_loader=load_settings,
        structural_contributions=contribute,
    )

    app = create_app(extensions=(extension,))

    assert calls == ["settings", "structure:{'ready': True}"]
    assert app.state.extension_contributions.extension_names == ("structural",)


def test_unknown_auth_method_requires_registered_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_method", "kerberos")
    monkeypatch.setattr(settings, "session_secret_key", SecretStr("test-secret"))

    with pytest.raises(ExtensionConfigurationError, match="no registered"):
        create_app(extensions=())


def test_extension_auth_method_identifier_is_validated_against_provider_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class KerberosProvider:
        provider_id = "kerberos"

        async def authenticate(self, _request: Request) -> AuthenticationResult:
            return AuthenticationResult.not_applicable()

    monkeypatch.setattr(settings, "auth_method", "kerberos")
    monkeypatch.setattr(settings, "session_secret_key", SecretStr("test-secret"))
    extension = ExtensionDefinition(
        name="kerberos-auth",
        extension_api_version=RADIUSDECK_EXTENSION_API,
        structural_contributions=lambda _settings: StructuralContributions(
            authentication_providers=(KerberosProvider(),),
        ),
    )

    app = create_app(extensions=(extension,))

    assert app.state.extension_contributions.authentication_providers
