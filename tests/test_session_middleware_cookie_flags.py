from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware


def _make_app(*, https_only: bool) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret",
        https_only=https_only,
        same_site="lax",
        session_cookie="radiusdeck_session",
        max_age=86400,
    )

    @app.get("/set")
    async def set_session(request: Request) -> dict[str, bool]:
        request.session["x"] = "1"  # modify session -> Set-Cookie will be emitted
        return {"ok": True}

    return app


def test_session_cookie_has_secure_flag_when_https_only_true() -> None:
    app = _make_app(https_only=True)
    with TestClient(app) as client:
        resp = client.get("/set")

    set_cookie = resp.headers.get("set-cookie")
    assert set_cookie is not None
    assert set_cookie.startswith("radiusdeck_session=")

    cookie_lower = set_cookie.lower()
    assert "secure" in cookie_lower


def test_session_cookie_has_no_secure_flag_when_https_only_false() -> None:
    app = _make_app(https_only=False)
    with TestClient(app) as client:
        resp = client.get("/set")

    set_cookie = resp.headers.get("set-cookie")
    assert set_cookie is not None
    assert set_cookie.startswith("radiusdeck_session=")

    cookie_lower = set_cookie.lower()
    assert "secure" not in cookie_lower
