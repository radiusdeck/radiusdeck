"""Shared Community/base test fixtures."""

from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import SecretStr

from radiusdeck.auth.csrf import get_or_create_csrf_token
from radiusdeck.auth.models import CurrentUser
from radiusdeck.auth.session import set_user_session
from radiusdeck.core.config import settings
from radiusdeck.extensions import (
    RADIUSDECK_EXTENSION_API,
    ExtensionDefinition,
    RouteAccess,
    RoutePolicy,
    RouterContribution,
    StructuralContributions,
)
from radiusdeck.extensions.route_policy import policies_for_router
from radiusdeck.main import app, create_app
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.services.ports import ReloadPort
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.services.reload_models import ReloadResult
from radiusdeck.web.deps import get_radius_service


@dataclass(frozen=True)
class UiEnv:
    client: TestClient
    config_path: Path


@pytest.fixture
def reloader_mock() -> AsyncMock:
    mock = AsyncMock(spec=ReloadPort)
    mock.reload.return_value = ReloadResult.skipped()
    return mock


def _write_config(path: Path, content: str) -> RadiusService:
    path.write_text(content, encoding="utf-8")
    reloader = AsyncMock(spec=ReloadPort)
    reloader.reload.return_value = ReloadResult.skipped()
    return RadiusService(ClientsConfStore(path), reloader=reloader)


@pytest.fixture()
def client(
    tmp_path: Path, reloader_mock: AsyncMock
) -> Generator[TestClient, None, None]:
    config_file = tmp_path / "clients.conf"
    config_file.write_text(
        "client LOCAL {\n    ipaddr = 127.0.0.1\n    secret = testing123\n}\n\n",
        encoding="utf-8",
    )
    service = RadiusService(ClientsConfStore(config_file), reloader=reloader_mock)
    app.dependency_overrides[get_radius_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_radius_service, None)


@pytest.fixture()
def empty_client(
    tmp_path: Path,
    reloader_mock: AsyncMock,
) -> Generator[TestClient, None, None]:
    config_file = tmp_path / "clients.conf"
    config_file.write_text("# empty\n", encoding="utf-8")
    service = RadiusService(ClientsConfStore(config_file), reloader=reloader_mock)
    app.dependency_overrides[get_radius_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_radius_service, None)


@pytest.fixture()
def env_complex(
    tmp_path: Path,
    reloader_mock: AsyncMock,
) -> Generator[UiEnv, None, None]:
    config_file = tmp_path / "clients.conf"
    config_file.write_text(
        """client LOCAL {
    # header comment
    ipaddr = 127.0.0.1 # inline ip
    secret = testing123

    shortname = old # inline short
    limit {
        max_connections = "16"
        lifetime = 0
    }
}
""",
        encoding="utf-8",
    )
    service = RadiusService(ClientsConfStore(config_file), reloader=reloader_mock)
    app.dependency_overrides[get_radius_service] = lambda: service
    with TestClient(app) as test_client:
        yield UiEnv(client=test_client, config_path=config_file)
    app.dependency_overrides.pop(get_radius_service, None)


def make_payload(
    name: str = "test-client",
    ipaddr: str = "10.0.0.1",
    secret: str = "supersecret",
    assignments: list[dict[str, str]] | None = None,
    blocks: list[dict[str, Any]] | None = None,
) -> str:
    return json.dumps(
        {
            "name": name,
            "ipaddr": ipaddr,
            "secret": secret,
            "assignments": assignments or [],
            "blocks": blocks or [],
        }
    )


def _test_login_extension() -> ExtensionDefinition:
    router = APIRouter()

    @router.get("/login_as/{role}")
    async def login_as(role: str, request: Request) -> dict[str, str]:
        if role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="invalid role")
        set_user_session(
            request.session,
            CurrentUser(
                username=f"{role}_tester",
                display_name=f"{role}_tester",
                role=role,  # type: ignore[arg-type]
                auth_method="local",
            ),
        )
        return {
            "ok": "true",
            "role": role,
            "csrf_token": get_or_create_csrf_token(request.session),
        }

    def contributions(_settings: object | None) -> StructuralContributions:
        policy = RoutePolicy(RouteAccess.PUBLIC, csrf_protected=False)
        return StructuralContributions(
            routers=(
                RouterContribution(
                    router=router,
                    prefix="/__test__",
                    policies=policies_for_router(
                        router,
                        prefix="/__test__",
                        policy=policy,
                    ),
                ),
            )
        )

    return ExtensionDefinition(
        name="test-login",
        extension_api_version=RADIUSDECK_EXTENSION_API,
        structural_contributions=contributions,
    )


def _authenticated_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    service: RadiusService,
    config_path: Path,
) -> FastAPI:
    monkeypatch.setattr(settings, "auth_method", "local")
    monkeypatch.setattr(settings, "session_secret_key", SecretStr("test-secret"))
    monkeypatch.setattr(settings, "local_users_path", tmp_path / "users.json")
    monkeypatch.setattr(settings, "RADIUS_CLIENTS_PATH", config_path)
    monkeypatch.setattr(settings, "backup_enabled", False)
    monkeypatch.setattr(settings, "SIDECAR_RELOAD_ENABLED", False)
    application = create_app(extensions=(_test_login_extension(),))
    application.dependency_overrides[get_radius_service] = lambda: service
    return application


@pytest.fixture()
def auth_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> FastAPI:
    config_path = tmp_path / "clients.conf"
    service = _write_config(
        config_path,
        "client LOCAL {\n    ipaddr = 127.0.0.1\n    secret = testing123\n}\n",
    )
    return _authenticated_app(monkeypatch, tmp_path, service, config_path)


@pytest.fixture()
def auth_app_complex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> FastAPI:
    config_path = tmp_path / "clients.conf"
    service = _write_config(
        config_path,
        """client LOCAL {
    # header comment
    ipaddr = 127.0.0.1 # inline ip
    secret = testing123

    shortname = old # inline short
    limit {
        max_connections = "16"
        lifetime = 0
    }
}
""",
    )
    return _authenticated_app(monkeypatch, tmp_path, service, config_path)


@pytest.fixture()
def client_as_admin(auth_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(auth_app) as test_client:
        response = test_client.get("/__test__/login_as/admin")
        assert response.status_code == 200
        test_client.headers[settings.csrf_header_name] = response.json()["csrf_token"]
        yield test_client


@pytest.fixture()
def client_as_user(auth_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(auth_app) as test_client:
        response = test_client.get("/__test__/login_as/user")
        assert response.status_code == 200
        test_client.headers[settings.csrf_header_name] = response.json()["csrf_token"]
        yield test_client


@pytest.fixture()
def client_as_admin_complex(
    auth_app_complex: FastAPI,
) -> Generator[TestClient, None, None]:
    with TestClient(auth_app_complex) as test_client:
        response = test_client.get("/__test__/login_as/admin")
        assert response.status_code == 200
        test_client.headers[settings.csrf_header_name] = response.json()["csrf_token"]
        yield test_client


@pytest.fixture()
def client_as_user_complex(
    auth_app_complex: FastAPI,
) -> Generator[TestClient, None, None]:
    with TestClient(auth_app_complex) as test_client:
        response = test_client.get("/__test__/login_as/user")
        assert response.status_code == 200
        test_client.headers[settings.csrf_header_name] = response.json()["csrf_token"]
        yield test_client
