from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import APIRouter, Request
from fastapi.testclient import TestClient
from pydantic import SecretStr

from radiusdeck.auth.models import CurrentUser
from radiusdeck.auth.session import set_user_session
from radiusdeck.core.config import settings
from radiusdeck.core.logging import request_id_ctx
from radiusdeck.extensions import (
    RADIUSDECK_EXTENSION_API,
    AuthenticationResult,
    ExtensionDefinition,
    RouteAccess,
    RoutePolicy,
    RoutePolicyContribution,
    RouterContribution,
    StructuralContributions,
)
from radiusdeck.extensions.errors import RoutePolicyError
from radiusdeck.extensions.route_policy import (
    build_route_policy_registry,
    policies_for_router,
)
from radiusdeck.main import create_app


def _policy_contribution(
    path: str,
    method: str = "GET",
    *,
    access: RouteAccess = RouteAccess.PUBLIC,
) -> RoutePolicyContribution:
    return RoutePolicyContribution(
        path=path,
        methods=frozenset({method}),
        policy=RoutePolicy(access, csrf_protected=False),
    )


def test_router_policies_use_effective_paths_from_included_routers() -> None:
    child = APIRouter()

    @child.get("/items/{item_id}")
    async def item(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    parent = APIRouter()
    parent.include_router(child, prefix="/nested")
    policy = RoutePolicy(RouteAccess.PUBLIC, csrf_protected=False)

    contributions = policies_for_router(parent, prefix="/api", policy=policy)

    assert contributions == (
        RoutePolicyContribution(
            path="/api/nested/items/{item_id}",
            methods=frozenset({"GET"}),
            policy=policy,
        ),
    )


def test_registry_rejects_normalized_dynamic_route_collision() -> None:
    first = APIRouter()
    second = APIRouter()

    @first.get("/x/{id}")
    async def by_id(id: str) -> dict[str, str]:
        return {"id": id}

    @second.get("/x/{name}")
    async def by_name(name: str) -> dict[str, str]:
        return {"name": name}

    with pytest.raises(RoutePolicyError, match="Duplicate registered route shape"):
        build_route_policy_registry(
            (*first.routes, *second.routes),
            (
                _policy_contribution("/x/{id}"),
                _policy_contribution("/x/{name}"),
            ),
            authentication_provider_ids=frozenset(),
        )


def test_registry_rejects_orphan_unclassified_and_contradictory_policies() -> None:
    router = APIRouter()

    @router.get("/known")
    async def known() -> dict[str, bool]:
        return {"ok": True}

    with pytest.raises(RoutePolicyError, match="Orphan"):
        build_route_policy_registry(
            router.routes,
            (_policy_contribution("/missing"),),
            authentication_provider_ids=frozenset(),
        )

    with pytest.raises(RoutePolicyError, match="unclassified"):
        build_route_policy_registry(
            router.routes,
            (),
            authentication_provider_ids=frozenset(),
        )

    policy = _policy_contribution("/known")
    with pytest.raises(RoutePolicyError, match="contradictory"):
        build_route_policy_registry(
            router.routes,
            (policy, policy),
            authentication_provider_ids=frozenset(),
        )


def test_extension_route_collision_with_base_route_fails_app_creation() -> None:
    router = APIRouter()

    @router.get("/health")
    async def conflicting_health() -> dict[str, bool]:
        return {"ok": False}

    extension = ExtensionDefinition(
        name="collision",
        extension_api_version=RADIUSDECK_EXTENSION_API,
        structural_contributions=lambda _settings: StructuralContributions(
            routers=(
                RouterContribution(
                    router=router,
                    policies=(_policy_contribution("/health"),),
                ),
            )
        ),
    )

    with pytest.raises(RoutePolicyError, match="Duplicate registered route shape"):
        create_app(extensions=(extension,))


def test_unknown_wrong_method_and_absent_api_reach_fastapi_routing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "auth_method", "local")
    monkeypatch.setattr(settings, "session_secret_key", SecretStr("test-secret"))
    monkeypatch.setattr(settings, "local_users_path", tmp_path / "users.json")
    app = create_app(extensions=())

    with TestClient(app, follow_redirects=False) as client:
        assert client.get("/does-not-exist").status_code == 404
        assert client.post("/health").status_code == 405
        assert client.get("/api/v1").status_code == 404


def test_observed_security_pipeline_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "auth_method", "local")
    monkeypatch.setattr(settings, "session_secret_key", SecretStr("test-secret"))
    monkeypatch.setattr(settings, "local_users_path", tmp_path / "users.json")
    router = APIRouter()
    observations: list[tuple[str | None, str | None]] = []

    @router.get("/seed")
    async def seed(request: Request) -> dict[str, bool]:
        set_user_session(
            request.session,
            CurrentUser(
                username="session-user",
                display_name="Session User",
                role="user",
                auth_method="local",
            ),
        )
        return {"ok": True}

    @router.post("/secure")
    async def secure(request: Request) -> dict[str, str]:
        return {"username": request.state.user.username}

    class Provider:
        provider_id = "pipeline-provider"

        async def authenticate(self, request: Request) -> AuthenticationResult:
            session_user = getattr(request.state, "user", None)
            observations.append(
                (
                    getattr(session_user, "username", None),
                    request_id_ctx.get(),
                )
            )
            return AuthenticationResult.authenticated(
                CurrentUser(
                    username="provider-user",
                    display_name="Provider User",
                    role="admin",
                    auth_method="local",
                )
            )

    api_policy = RoutePolicy(
        RouteAccess.PROTECTED_API,
        authentication_provider_ids=("pipeline-provider",),
        csrf_protected=True,
        csrf_exempt_provider_ids=("pipeline-provider",),
    )
    extension = ExtensionDefinition(
        name="pipeline-test",
        extension_api_version=RADIUSDECK_EXTENSION_API,
        structural_contributions=lambda _settings: StructuralContributions(
            routers=(
                RouterContribution(
                    router=router,
                    prefix="/__pipeline",
                    policies=(
                        _policy_contribution("/__pipeline/seed"),
                        RoutePolicyContribution(
                            path="/__pipeline/secure",
                            methods=frozenset({"POST"}),
                            policy=api_policy,
                        ),
                    ),
                ),
            ),
            authentication_providers=(Provider(),),
        ),
    )
    app = create_app(extensions=(extension,))

    with TestClient(app) as client:
        assert client.get("/__pipeline/seed").status_code == 200
        response = client.post(
            "/__pipeline/secure",
            headers={"X-Request-ID": "pipeline-request"},
        )

    assert response.status_code == 200
    assert response.json() == {"username": "provider-user"}
    assert response.headers["X-Request-ID"] == "pipeline-request"
    assert observations == [("session-user", "pipeline-request")]
