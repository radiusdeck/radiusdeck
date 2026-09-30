"""Tests for client details and delete endpoints."""

from fastapi.testclient import TestClient

from tests.conftest import make_payload


class TestClientDetails:
    def test_details_existing_client(self, client: TestClient) -> None:
        resp = client.get("/ui/clients/LOCAL/details")
        assert resp.status_code == 200
        assert "127.0.0.1" in resp.text
        assert "testing123" not in resp.text
        assert "************" in resp.text

    def test_details_nonexistent_client(self, client: TestClient) -> None:
        resp = client.get("/ui/clients/NONEXISTENT/details")
        assert resp.status_code == 404

    def test_details_shows_nested_blocks(self, empty_client: TestClient) -> None:
        payload = make_payload(
            name="detailed",
            blocks=[
                {
                    "kind": "limit",
                    "name": None,
                    "assignments": [{"key": "max_connections", "value": "16"}],
                    "blocks": [],
                }
            ],
        )
        empty_client.post("/ui/clients/add-tree", data={"payload_json": payload})

        resp = empty_client.get("/ui/clients/detailed/details")
        assert resp.status_code == 200
        assert "limit" in resp.text
        assert "max_connections" in resp.text
        assert "16" in resp.text


class TestDeleteClient:
    def test_delete_client(self, client_as_admin: TestClient) -> None:
        resp = client_as_admin.delete("/ui/clients/LOCAL")
        assert resp.status_code == 200

        resp = client_as_admin.get("/ui/clients/LOCAL/details")
        assert resp.status_code == 404

    def test_delete_nonexistent_client(self, client_as_admin: TestClient) -> None:
        resp = client_as_admin.delete("/ui/clients/NONEXISTENT")
        assert resp.status_code == 404
