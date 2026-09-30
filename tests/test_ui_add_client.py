"""Tests for adding clients (POST /ui/clients/add-tree) and config file verification."""

import json
from pathlib import Path

from fastapi import Request
from fastapi.testclient import TestClient

from radiusdeck.integrations.null_reload_client import NullReloadClient
from radiusdeck.main import app
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.web.deps import get_radius_service
from tests.conftest import make_payload


class TestAddTree:
    def test_add_simple_client(self, empty_client: TestClient) -> None:
        payload = make_payload(name="simple", ipaddr="10.0.0.1", secret="s3cr3t")
        resp = empty_client.post("/ui/clients/add-tree", data={"payload_json": payload})
        assert resp.status_code == 200
        assert "simple" in resp.text
        assert "10.0.0.1" in resp.text

    def test_add_client_with_extra_params(self, empty_client: TestClient) -> None:
        payload = make_payload(
            name="with-extras",
            assignments=[
                {"key": "shortname", "value": "office"},
                {"key": "nastype", "value": "other"},
            ],
        )
        resp = empty_client.post("/ui/clients/add-tree", data={"payload_json": payload})
        assert resp.status_code == 200
        assert "with-extras" in resp.text

    def test_add_client_with_nested_block(self, empty_client: TestClient) -> None:
        payload = make_payload(
            name="with-block",
            blocks=[
                {
                    "kind": "limit",
                    "name": None,
                    "assignments": [
                        {"key": "max_connections", "value": "16"},
                        {"key": "lifetime", "value": "0"},
                    ],
                    "blocks": [],
                }
            ],
        )
        resp = empty_client.post("/ui/clients/add-tree", data={"payload_json": payload})
        assert resp.status_code == 200
        assert "with-block" in resp.text

    def test_add_client_with_deeply_nested_blocks(
        self, empty_client: TestClient
    ) -> None:
        payload = make_payload(
            name="deep-nest",
            blocks=[
                {
                    "kind": "security",
                    "name": None,
                    "assignments": [
                        {"key": "require_message_authenticator", "value": "yes"},
                    ],
                    "blocks": [
                        {
                            "kind": "tls",
                            "name": None,
                            "assignments": [
                                {"key": "cert_file", "value": "/path/to/cert"},
                            ],
                            "blocks": [],
                        }
                    ],
                }
            ],
        )
        resp = empty_client.post("/ui/clients/add-tree", data={"payload_json": payload})
        assert resp.status_code == 200
        assert "deep-nest" in resp.text

    def test_add_client_empty_payload(self, client: TestClient) -> None:
        resp = client.post("/ui/clients/add-tree", data={"payload_json": ""})
        assert resp.status_code == 200
        assert "clientAddError" in resp.headers.get("hx-trigger", "")

    def test_add_client_no_payload(self, client: TestClient) -> None:
        resp = client.post("/ui/clients/add-tree", data={})
        assert "clientAddError" in resp.headers.get("hx-trigger", "")

    def test_add_client_invalid_json(self, client: TestClient) -> None:
        resp = client.post("/ui/clients/add-tree", data={"payload_json": "not-json"})
        assert "clientAddError" in resp.headers.get("hx-trigger", "")

    def test_add_client_missing_required_field(self, client: TestClient) -> None:
        payload = json.dumps({"name": "x", "ipaddr": "1.2.3.4"})
        resp = client.post("/ui/clients/add-tree", data={"payload_json": payload})
        assert "clientAddError" in resp.headers.get("hx-trigger", "")

    def test_add_client_duplicate_assignment_keys(self, client: TestClient) -> None:
        payload = make_payload(
            assignments=[
                {"key": "shortname", "value": "a"},
                {"key": "shortname", "value": "b"},
            ],
        )
        resp = client.post("/ui/clients/add-tree", data={"payload_json": payload})
        assert "clientAddError" in resp.headers.get("hx-trigger", "")

    def test_add_client_reserved_assignment_key(self, client: TestClient) -> None:
        payload = make_payload(assignments=[{"key": "ipaddr", "value": "hack"}])
        resp = client.post("/ui/clients/add-tree", data={"payload_json": payload})
        assert "clientAddError" in resp.headers.get("hx-trigger", "")

    def test_add_triggers_clientAdded_event(self, empty_client: TestClient) -> None:
        payload = make_payload(name="trigger-test")
        resp = empty_client.post("/ui/clients/add-tree", data={"payload_json": payload})
        assert resp.status_code == 200
        assert "clientAdded" in resp.headers.get("hx-trigger", "")


class TestConfigFileContent:
    def test_simple_client_in_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "clients.conf"
        config_file.write_text("# empty\n", encoding="utf-8")

        service = RadiusService(
            ClientsConfStore(str(config_file)), reloader=NullReloadClient()
        )

        def override(request: Request) -> RadiusService:
            return service

        app.dependency_overrides[get_radius_service] = override

        with TestClient(app) as c:
            payload = make_payload(name="filetest", ipaddr="10.10.10.10", secret="abc")
            c.post("/ui/clients/add-tree", data={"payload_json": payload})

        app.dependency_overrides.pop(get_radius_service, None)

        content = config_file.read_text(encoding="utf-8")
        assert "client filetest" in content
        assert "ipaddr = 10.10.10.10" in content
        assert "secret = abc" in content

    def test_nested_block_in_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "clients.conf"
        config_file.write_text("# empty\n", encoding="utf-8")

        service = RadiusService(
            ClientsConfStore(str(config_file)), reloader=NullReloadClient()
        )

        def override(request: Request) -> RadiusService:
            return service

        app.dependency_overrides[get_radius_service] = override

        with TestClient(app) as c:
            payload = make_payload(
                name="nested-test",
                blocks=[
                    {
                        "kind": "limit",
                        "name": None,
                        "assignments": [
                            {"key": "max_connections", "value": "16"},
                            {"key": "lifetime", "value": "0"},
                        ],
                        "blocks": [],
                    }
                ],
            )
            c.post("/ui/clients/add-tree", data={"payload_json": payload})

        app.dependency_overrides.pop(get_radius_service, None)

        content = config_file.read_text(encoding="utf-8")
        assert "client nested-test" in content
        assert "limit {" in content
        assert "max_connections = 16" in content
        assert "lifetime = 0" in content

    def test_extra_params_in_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "clients.conf"
        config_file.write_text("# empty\n", encoding="utf-8")

        service = RadiusService(
            ClientsConfStore(str(config_file)), reloader=NullReloadClient()
        )

        def override(request: Request) -> RadiusService:
            return service

        app.dependency_overrides[get_radius_service] = override

        with TestClient(app) as c:
            payload = make_payload(
                name="extras-test",
                assignments=[
                    {"key": "shortname", "value": "office"},
                    {"key": "nastype", "value": "other"},
                ],
            )
            c.post("/ui/clients/add-tree", data={"payload_json": payload})

        app.dependency_overrides.pop(get_radius_service, None)

        content = config_file.read_text(encoding="utf-8")
        assert "shortname = office" in content
        assert "nastype = other" in content
