from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

import radiusdeck as app_pkg
from radiusdeck.auth.models import CurrentUser


def _make_templates() -> Jinja2Templates:
    app_dir = Path(app_pkg.__file__).resolve().parent
    return Jinja2Templates(directory=str(app_dir / "templates"))


def test_base_template_shows_user_and_logout_when_user_present() -> None:
    templates = _make_templates()
    app = FastAPI()

    @app.get("/t")
    async def t(request: Request):
        request.state.user = CurrentUser(
            username="alice",
            display_name="Alice",
            role="admin",
            auth_method="local",
        )
        return templates.TemplateResponse(request, "base.html")

    with TestClient(app) as client:
        resp = client.get("/t")
        assert resp.status_code == 200
        assert "Alice" in resp.text
        assert "/logout" in resp.text


def test_base_template_hides_user_block_when_user_missing() -> None:
    templates = _make_templates()
    app = FastAPI()

    @app.get("/t")
    async def t(request: Request):
        return templates.TemplateResponse(request, "base.html")

    with TestClient(app) as client:
        resp = client.get("/t")
        assert resp.status_code == 200
        assert "/logout" not in resp.text
