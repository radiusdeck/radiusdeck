from __future__ import annotations

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from radiusdeck.core.config import settings
from radiusdeck.web.constants import UI_HOME_PATH


def test_login_redirects_to_home_when_auth_none(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "auth_method", "none")
    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == UI_HOME_PATH
