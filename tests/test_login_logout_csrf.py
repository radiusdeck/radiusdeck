from __future__ import annotations

import asyncio
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from radiusdeck.auth.local.models import LocalUsersFile
from radiusdeck.auth.middleware import (
    AuthGuardMiddleware,
    CsrfMiddleware,
    UserContextMiddleware,
)
from radiusdeck.auth.session_keys import SESSION_CSRF_TOKEN
from radiusdeck.core.config import settings
from radiusdeck.extensions import RouteAccess, RoutePolicy
from radiusdeck.extensions.route_policy import (
    build_route_policy_registry,
    policies_for_router,
    policies_for_routes,
)
from radiusdeck.repositories.local_users_store import LocalUsersStore
from radiusdeck.services.local_auth_service import LocalAuthService
from radiusdeck.web.endpoints import auth as auth_endpoints


@pytest.fixture()
def auth_csrf_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FastAPI:
    monkeypatch.setattr(settings, "auth_method", "local")
    monkeypatch.setattr(settings, "csrf_header_name", "X-CSRF-Token")

    store = LocalUsersStore(tmp_path / "users.json")
    asyncio.run(store.save(LocalUsersFile(version=1, users=[])))

    app = FastAPI()
    framework_routes = tuple(app.routes)
    app.state.local_auth_service = LocalAuthService(store)
    app.include_router(auth_endpoints.router)

    @app.get("/__test__/csrf")
    async def csrf_state(request: Request) -> dict[str, Any]:
        return {
            "has_csrf": SESSION_CSRF_TOKEN in request.session,
            "csrf_token": request.session.get(SESSION_CSRF_TOKEN),
        }

    public = RoutePolicy(RouteAccess.PUBLIC, csrf_protected=False)
    auth_policy = RoutePolicy(RouteAccess.PUBLIC, csrf_protected=True)
    policies = (
        policies_for_routes(framework_routes, policy=public)
        + policies_for_router(auth_endpoints.router, prefix="", policy=auth_policy)
        + policies_for_routes((app.routes[-1],), policy=public)
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
def auth_csrf_client(auth_csrf_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(auth_csrf_app) as client:
        yield client


def test_get_login_creates_csrf_token_in_session(
    auth_csrf_client: TestClient,
) -> None:
    response = auth_csrf_client.get("/login")
    assert response.status_code == 200

    csrf_state = auth_csrf_client.get("/__test__/csrf")
    assert csrf_state.status_code == 200
    assert csrf_state.json()["has_csrf"] is True
    assert csrf_state.json()["csrf_token"]


def test_post_login_requires_csrf_token(auth_csrf_client: TestClient) -> None:
    response = auth_csrf_client.post("/login")

    assert response.status_code == 403


def test_post_login_accepts_csrf_token_created_by_get_login(
    auth_csrf_client: TestClient,
) -> None:
    response = auth_csrf_client.get("/login")
    assert response.status_code == 200
    token = auth_csrf_client.get("/__test__/csrf").json()["csrf_token"]

    response = auth_csrf_client.post("/login", headers={"X-CSRF-Token": token})

    assert response.status_code == 401
    assert "Invalid username or password." in response.text


def test_post_logout_requires_csrf_token(auth_csrf_client: TestClient) -> None:
    response = auth_csrf_client.post("/logout", follow_redirects=False)

    assert response.status_code == 403


def test_post_logout_clears_session_with_valid_csrf_token(
    auth_csrf_client: TestClient,
) -> None:
    response = auth_csrf_client.get("/login")
    assert response.status_code == 200
    token = auth_csrf_client.get("/__test__/csrf").json()["csrf_token"]

    response = auth_csrf_client.post(
        "/logout",
        headers={"X-CSRF-Token": token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/login"

    csrf_state = auth_csrf_client.get("/__test__/csrf")
    assert csrf_state.json()["has_csrf"] is False
