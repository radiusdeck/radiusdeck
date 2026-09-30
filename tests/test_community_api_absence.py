from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from radiusdeck.core.config import settings
from radiusdeck.main import create_app


@pytest.mark.parametrize("auth_method", ["none", "local"])
def test_community_has_no_api(
    auth_method: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "auth_method", auth_method)
    monkeypatch.setattr(settings, "session_secret_key", SecretStr("test-secret"))
    monkeypatch.setattr(settings, "local_users_path", tmp_path / "users.json")
    monkeypatch.setattr(settings, "backup_enabled", False)
    app = create_app(extensions=())
    with TestClient(app, follow_redirects=False) as client:
        for path in (
            "/api/v1",
            "/api/v1/clients/",
            "/api/v1/backups",
            "/api/v1/logs/tail",
        ):
            assert client.get(path).status_code == 404
            assert client.post(path).status_code == 404
            assert (
                app.state.route_policy_registry.lookup(
                    {"type": "http", "path": path, "method": "GET"}
                )
                is None
            )
        assert client.post("/health").status_code == 405
        assert client.delete("/ui/clients").status_code == 405
    schema = app.openapi()
    assert not any(path.startswith("/api/v1") for path in schema["paths"])
    assert not {"ClientResponse", "LogTailResponse", "BackupResponse"}.intersection(
        schema.get("components", {}).get("schemas", {})
    )


def test_base_source_contains_no_pro_api() -> None:
    root = Path("src/radiusdeck")
    assert not (root / "api").exists()
    assert not (root / "schemas/logs.py").exists()
    assert not (root / "schemas/reload.py").exists()
    for path in root.rglob("*.py"):
        source = path.read_text()
        assert "/api/v1" not in source, path
        assert "class ClientResponse" not in source, path
