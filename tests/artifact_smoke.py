"""Smoke the installed Community artifact outside the source checkout."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch


def main() -> None:
    with TemporaryDirectory(prefix="radiusdeck-community-smoke-") as directory:
        root = Path(directory)
        clients = root / "clients.conf"
        clients.write_text("client LOCAL {\n ipaddr = 127.0.0.1\n secret = test\n}\n")
        log = root / "radius.log"
        log.write_text('Info password="hidden words"\n')
        os.environ.update(
            {
                "APP_ENV": "test",
                "APP_AUTH_METHOD": "none",
                "APP_RADIUS_CLIENTS_PATH": str(clients),
                "APP_BACKUP_DIR": str(root / "backups"),
                "APP_FREERADIUS_LOG_VIEWER_ENABLED": "true",
                "APP_FREERADIUS_LOG_PATH": str(log),
                "APP_SIDECAR_RELOAD_ENABLED": "false",
                "APP_SECURE_COOKIES": "false",
            }
        )
        assert importlib.util.find_spec("radiusdeck_pro") is None
        assert importlib.util.find_spec("radiusdeck.api") is None

        from fastapi.testclient import TestClient
        from pydantic import SecretStr

        import radiusdeck
        from radiusdeck.cli.main import build_parser
        from radiusdeck.core.config import Settings, settings
        from radiusdeck.extensions.loader import discover_extensions
        from radiusdeck.main import app, create_app
        from radiusdeck.services.ports import ReloadPort
        from radiusdeck.services.reload_models import ReloadResult

        assert radiusdeck.__file__ is not None
        assert Path(radiusdeck.__file__).is_relative_to(Path(sys.prefix))
        assert discover_extensions() == ()
        assert {
            "edition",
            "license_file",
            "pro_dev_mode",
            "backup_retention_count",
            "freeradius_log_max_lines",
        }.isdisjoint(Settings.model_fields)
        parsed = build_parser().parse_args(["serve"])
        assert (parsed.host, parsed.port) == ("0.0.0.0", 8000)
        explicit = build_parser().parse_args(
            ["serve", "--host", "127.0.0.1", "--port", "9000"]
        )
        assert (explicit.host, explicit.port) == ("127.0.0.1", 9000)
        version = subprocess.run(
            [sys.executable, "-m", "radiusdeck.cli.main", "--version"],
            check=True,
            capture_output=True,
            text=True,
            cwd="/tmp",
            env={**os.environ, "PYTHONPATH": ""},
        )
        assert version.stdout.startswith("radiusdeck ")

        reloader = AsyncMock(spec=ReloadPort)
        reloader.reload.return_value = ReloadResult.skipped()
        with patch("radiusdeck.main.NullReloadClient", return_value=reloader):
            with TestClient(app, follow_redirects=False) as client:
                assert client.get("/health").status_code == 200
                assert client.get("/ui/clients").status_code == 200
                logs = client.get("/ui/logs")
                assert logs.status_code == 200 and "hidden words" not in logs.text
                assert client.get("/ui/status").status_code == 200
                assert client.get("/ui/backups").status_code == 200
                assert client.get("/api/v1/clients/").status_code == 404
                assert not any(
                    path.startswith("/api/v1") for path in app.openapi()["paths"]
                )
                payload = {
                    "name": "artifact-client",
                    "ipaddr": "192.0.2.20",
                    "secret": "artifact-secret",
                    "assignments": [],
                    "blocks": [],
                }
                created = client.post(
                    "/ui/clients/add-tree", data={"payload_json": json.dumps(payload)}
                )
                assert created.status_code == 200
                assert client.get("/ui/backups/latest/confirm").status_code == 200
                assert reloader.reload.await_count == 1

            settings.auth_method = "local"
            settings.local_users_path = root / "users.json"
            settings.session_secret_key = SecretStr("artifact-secret")
            with TestClient(
                create_app(extensions=()), follow_redirects=False
            ) as client:
                assert client.get("/login").status_code == 200
                assert client.get("/api/v1/clients/").status_code == 404

    print("Community installed-artifact smoke passed")


if __name__ == "__main__":
    main()
