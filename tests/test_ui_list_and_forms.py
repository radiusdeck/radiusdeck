"""Tests for list page, assignment-row and block-form endpoints."""

from fastapi.testclient import TestClient


class TestListClients:
    def test_list_page_returns_200(self, client: TestClient) -> None:
        resp = client.get("/ui/clients")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_list_page_contains_existing_client(self, client: TestClient) -> None:
        resp = client.get("/ui/clients")
        assert "LOCAL" in resp.text
        assert "127.0.0.1" in resp.text

    def test_create_form_appends_only_client_tbody(self, client: TestClient) -> None:
        resp = client.get("/ui/clients")
        assert 'id="add-form"' in resp.text
        assert 'hx-target="#clients-table"' in resp.text
        assert "hx-select=\"tbody[id^='client-block-']\"" in resp.text
        assert 'hx-select-oob="#reload-alerts"' in resp.text
        assert 'hx-swap="beforeend"' in resp.text

    def test_list_page_empty_config(self, empty_client: TestClient) -> None:
        resp = empty_client.get("/ui/clients")
        assert resp.status_code == 200
        assert "<td>LOCAL</td>" not in resp.text


class TestAssignmentRow:
    def test_returns_html_with_inputs(self, client_as_admin: TestClient) -> None:
        resp = client_as_admin.get("/ui/clients/assignment-row")
        assert resp.status_code == 200
        assert "assignment-key" in resp.text
        assert "assignment-value" in resp.text
        assert "assignment-row" in resp.text

    def test_unique_ids(self, client_as_admin: TestClient) -> None:
        resp1 = client_as_admin.get("/ui/clients/assignment-row")
        resp2 = client_as_admin.get("/ui/clients/assignment-row")
        assert resp1.text != resp2.text


class TestBlockForm:
    def test_returns_html(self, client: TestClient) -> None:
        resp = client.get("/ui/clients/block-form?depth=0")
        assert resp.status_code == 200
        assert "block-kind" in resp.text
        assert "block-name" in resp.text

    def test_depth_affects_color(self, client: TestClient) -> None:
        resp0 = client.get("/ui/clients/block-form?depth=0")
        resp1 = client.get("/ui/clients/block-form?depth=1")
        assert resp0.text != resp1.text

    def test_sub_block_button_increments_depth(self, client: TestClient) -> None:
        resp = client.get("/ui/clients/block-form?depth=2")
        assert "depth=3" in resp.text

    def test_depth_validation(self, client: TestClient) -> None:
        resp = client.get("/ui/clients/block-form?depth=21")
        assert resp.status_code == 422
