from __future__ import annotations

from collections.abc import Generator
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from radiusdeck.integrations.null_reload_client import NullReloadClient
from radiusdeck.main import app
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.web.deps import get_radius_service, templates


class _EditFormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.attributes: list[tuple[str, str | None]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "form" and ("id", "edit-form") in attrs:
            self.attributes = attrs


@pytest.fixture()
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    config_file = tmp_path / "clients.conf"
    config_file.write_text(
        "client LOCAL {\n    ipaddr = 127.0.0.1\n    secret = testing123\n}\n",
        encoding="utf-8",
    )

    service = RadiusService(
        ClientsConfStore(str(config_file)), reloader=NullReloadClient()
    )

    def override(_: Request) -> RadiusService:
        return service

    app.dependency_overrides[get_radius_service] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_radius_service, None)


def test_clients_page_renders_create_form_card(client: TestClient) -> None:
    resp = client.get("/ui/clients")
    assert resp.status_code == 200
    html = resp.text

    assert 'id="client-form-panel"' in html
    assert 'id="form-card"' in html

    # create-mode form contract
    assert 'id="add-form"' in html
    assert 'hx-post="/ui/clients/add-tree"' in html

    # IMPORTANT: in your current table layout you append <tbody> to the <table>
    assert 'hx-target="#clients-table"' in html

    assert 'id="extra-params"' in html
    assert 'id="nested-blocks"' in html


def test_assignment_row_fragment_has_data_node_id(client_as_admin: TestClient) -> None:
    resp = client_as_admin.get("/ui/clients/assignment-row")
    assert resp.status_code == 200
    assert "assignment-row" in resp.text
    assert "assignment-key" in resp.text
    assert "assignment-value" in resp.text
    assert 'data-node-id=""' in resp.text


def test_block_form_fragment_has_data_node_id(client_as_admin: TestClient) -> None:
    resp = client_as_admin.get("/ui/clients/block-form?depth=0")
    assert resp.status_code == 200
    assert "client-block" in resp.text
    assert "block-kind" in resp.text
    assert "block-name" in resp.text
    assert 'data-node-id=""' in resp.text


def test_edit_mode_templates_render_prefilled_node_ids() -> None:
    # This is a template-unit test: we pass a synthetic "edit model"
    # that already contains ids for assignments/blocks.
    client_ctx = {
        "name": "LOCAL",
        "ipaddr": "127.0.0.1",
        "secret": "testing123",
        "assignments": [
            {"id": "a:0", "key": "shortname", "value": "local"},
        ],
        "blocks": [
            {
                "id": "b:0",
                "kind": "limit",
                "name": None,
                "assignments": [
                    {"id": "b:0/a:0", "key": "max_connections", "value": "16"},
                ],
                "blocks": [],
            }
        ],
    }

    tpl = templates.get_template("components/client_form_card.html")
    html = tpl.render(mode="edit", client=client_ctx)

    assert 'id="edit-form"' in html
    assert 'hx-put="/ui/clients/LOCAL/tree"' in html

    # name readonly
    assert 'name="name"' in html
    assert "readonly" in html
    assert "testing123" not in html
    assert 'type="password"' in html

    # node ids present
    assert 'data-node-id="a:0"' in html
    assert 'data-node-id="b:0"' in html
    assert 'data-node-id="b:0/a:0"' in html

    assert "Save Changes" in html
    assert "Cancel" in html

    parser = _EditFormParser()
    parser.feed(html)
    assert parser.attributes is not None
    assert ("hx-put", "/ui/clients/LOCAL/tree") in parser.attributes
    assert all(name != '"' and value is not None for name, value in parser.attributes)
