from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from radiusdeck.auth.models import CurrentUser
from radiusdeck.core.config import settings
from radiusdeck.services.status_models import (
    StatusCheck,
    StatusLevel,
    StatusReport,
    StatusSection,
)
from radiusdeck.web.router import api_router as web_router


class FakeStatusService:
    def __init__(self, report: StatusReport) -> None:
        self._report = report

    async def build_report(self) -> StatusReport:
        return self._report


def _report() -> StatusReport:
    sections = [
        StatusSection(
            id=section_id,
            title=title,
            checks=[
                StatusCheck(
                    id=f"{section_id}.check",
                    label=f"{title} check",
                    level=(
                        StatusLevel.ERROR
                        if section_id == "configuration"
                        else StatusLevel.WARNING
                    ),
                    message=(
                        "clients.conf is missing."
                        if section_id == "configuration"
                        else "Diagnostic message."
                    ),
                    remediation="Check the deployment configuration.",
                )
            ],
        )
        for section_id, title in (
            ("application", "Application"),
            ("security", "Security"),
            ("configuration", "Configuration file"),
            ("logs", "FreeRADIUS logs"),
            ("reload", "Reload integration"),
            ("runtime", "Runtime"),
        )
    ]
    return StatusReport(
        overall_level=StatusLevel.ERROR,
        sections=sections,
        metadata={"generated_at": "2026-07-10T00:00:00Z"},
    )


@pytest.fixture()
def status_app(monkeypatch: pytest.MonkeyPatch) -> Generator[FastAPI, None, None]:
    monkeypatch.setattr(settings, "auth_method", "none")
    app = FastAPI()
    app.state.status_service = FakeStatusService(_report())
    app.include_router(web_router, prefix="/ui")
    yield app


def test_status_page_renders_report_and_active_navigation(status_app: FastAPI) -> None:
    with TestClient(status_app) as client:
        response = client.get("/ui/status")

    assert response.status_code == 200
    assert "RadiusDeck deployment diagnostics" in response.text
    assert "Configuration file" in response.text
    assert "FreeRADIUS logs" in response.text
    assert "Reload integration" in response.text
    assert "clients.conf is missing." in response.text
    assert 'class="nav-link active"' in response.text


def test_status_page_does_not_render_secret_values(status_app: FastAPI) -> None:
    with TestClient(status_app) as client:
        response = client.get("/ui/status")

    assert "super-secret-session-key" not in response.text
    assert "super-secret-reload-token" not in response.text
    assert "super-secret-oidc-client-secret" not in response.text


def test_status_page_forbids_read_only_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_method", "local")
    app = FastAPI()
    app.state.status_service = FakeStatusService(_report())

    @app.middleware("http")
    async def add_read_only_user(request: Request, call_next):
        request.state.user = CurrentUser(
            username="reader",
            display_name="Reader",
            role="user",
            auth_method="local",
        )
        return await call_next(request)

    app.include_router(web_router, prefix="/ui")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/ui/status", headers={"Accept": "text/html"})

    assert response.status_code == 403


def test_status_page_allows_authenticated_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_method", "local")
    app = FastAPI()
    app.state.status_service = FakeStatusService(_report())

    @app.middleware("http")
    async def add_admin_user(request: Request, call_next):
        request.state.user = CurrentUser(
            username="admin",
            display_name="Admin",
            role="admin",
            auth_method="local",
        )
        return await call_next(request)

    app.include_router(web_router, prefix="/ui")

    with TestClient(app) as client:
        response = client.get("/ui/status")

    assert response.status_code == 200
    assert ">Status<" in response.text
