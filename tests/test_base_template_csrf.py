from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from radiusdeck.core.config import settings
from radiusdeck.web.deps import templates


def test_base_template_includes_csrf_hx_headers_when_auth_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_method", "local")
    monkeypatch.setattr(settings, "csrf_header_name", "X-CSRF-Token")

    app = FastAPI()

    @app.get("/t")
    async def t(request: Request) -> object:
        return templates.TemplateResponse(request, "base.html", {})

    app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret",
        https_only=False,
        same_site="lax",
        session_cookie="radiusdeck_session",
        max_age=86400,
    )

    with TestClient(app) as client:
        resp = client.get("/t")

    assert resp.status_code == 200
    assert 'hx-headers=\'{"X-CSRF-Token":' in resp.text


def test_base_template_omits_csrf_hx_headers_when_auth_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_method", "none")

    app = FastAPI()

    @app.get("/t")
    async def t(request: Request) -> object:
        return templates.TemplateResponse(request, "base.html", {})

    with TestClient(app) as client:
        resp = client.get("/t")

    assert resp.status_code == 200
    assert "hx-headers=" not in resp.text
