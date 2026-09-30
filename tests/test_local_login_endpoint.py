from __future__ import annotations

import asyncio
import re
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from radiusdeck.auth.local.models import LocalUserRecord, LocalUsersFile
from radiusdeck.auth.local.passwords import hash_password
from radiusdeck.auth.middleware import (
    AuthGuardMiddleware,
    CsrfMiddleware,
    UserContextMiddleware,
)
from radiusdeck.core.config import settings
from radiusdeck.extensions import RouteAccess, RoutePolicy
from radiusdeck.extensions.route_policy import (
    build_route_policy_registry,
    policies_for_router,
    policies_for_routes,
)
from radiusdeck.repositories.local_users_store import LocalUsersStore
from radiusdeck.services.local_auth_service import LocalAuthService
from radiusdeck.web.constants import UI_HOME_PATH
from radiusdeck.web.endpoints import auth as auth_endpoints


@pytest.fixture()
def local_login_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> FastAPI:
    monkeypatch.setattr(settings, "auth_method", "local")
    monkeypatch.setattr(settings, "csrf_header_name", "X-CSRF-Token")
    monkeypatch.setattr(settings, "csrf_form_field_name", "csrf_token")

    users_path = tmp_path / "users.json"
    store = LocalUsersStore(users_path)
    users_file = LocalUsersFile(
        version=1,
        users=[
            LocalUserRecord(
                username="alice",
                role="admin",
                password_hash=hash_password("alice-password"),
            )
        ],
    )
    asyncio.run(store.save(users_file))

    app = FastAPI()
    framework_routes = tuple(app.routes)
    app.state.local_auth_service = LocalAuthService(store)
    app.include_router(auth_endpoints.router)
    public = RoutePolicy(RouteAccess.PUBLIC, csrf_protected=False)
    auth_policy = RoutePolicy(RouteAccess.PUBLIC, csrf_protected=True)
    policies = policies_for_routes(
        framework_routes, policy=public
    ) + policies_for_router(
        auth_endpoints.router,
        prefix="",
        policy=auth_policy,
    )
    registry = build_route_policy_registry(
        app.routes,
        policies,
        authentication_provider_ids=frozenset(),
    )
    app.add_middleware(CsrfMiddleware, route_policies=registry)
    app.add_middleware(AuthGuardMiddleware, route_policies=registry)
    app.add_middleware(UserContextMiddleware, route_policies=registry)
    app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret",
        https_only=False,
        same_site="lax",
        session_cookie="radiusdeck_session",
        max_age=86400,
    )
    return app


@pytest.fixture()
def local_login_client(local_login_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(local_login_app) as client:
        yield client


def extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_get_login_renders_local_login_form(local_login_client: TestClient) -> None:
    response = local_login_client.get("/login")

    assert response.status_code == 200
    assert '<form method="post" action="/login">' in response.text
    assert 'name="username"' in response.text
    assert 'name="password"' in response.text
    assert 'name="csrf_token"' in response.text


def test_post_login_with_valid_credentials_sets_session_cookie(
    local_login_client: TestClient,
) -> None:
    response = local_login_client.get("/login")
    csrf_token = extract_csrf_token(response.text)

    response = local_login_client.post(
        "/login",
        data={
            "username": "alice",
            "password": "alice-password",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == UI_HOME_PATH
    assert "radiusdeck_session=" in response.headers["set-cookie"]


def test_post_login_with_invalid_credentials_returns_login_error(
    local_login_client: TestClient,
) -> None:
    response = local_login_client.get("/login")
    csrf_token = extract_csrf_token(response.text)

    response = local_login_client.post(
        "/login",
        data={
            "username": "alice",
            "password": "wrong-password",
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 401
    assert "Invalid username or password." in response.text
