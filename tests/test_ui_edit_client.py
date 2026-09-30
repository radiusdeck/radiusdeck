"""Tests for editing clients (PUT /ui/clients/{name}/tree) — Story 6 E2E."""

import json
import re

from tests.conftest import UiEnv


class TestTreeEditE2E:
    def test_get_edit_form_returns_prefilled_form(self, env_complex: UiEnv) -> None:
        c = env_complex.client
        resp = c.get("/ui/clients/LOCAL/edit-form")
        assert resp.status_code == 200
        html = resp.text

        assert 'id="form-card"' in html
        assert 'id="edit-form"' in html
        assert "Edit Client" in html
        assert 'name="name"' in html
        assert "readonly" in html
        assert 'data-node-id="a:0"' in html
        assert 'data-node-id="b:0"' in html
        assert 'data-node-id="b:0/a:0"' in html
        assert 'data-node-id="b:0/a:1"' in html
        assert "testing123" not in html
        assert 'type="password"' in html

    def test_blank_secret_preserves_existing_value(self, env_complex: UiEnv) -> None:
        payload = {
            "name": "LOCAL",
            "ipaddr": "127.0.0.1",
            "secret": "",
            "assignments": [{"id": "a:0", "key": "shortname", "value": "old"}],
            "blocks": [
                {
                    "id": "b:0",
                    "kind": "limit",
                    "name": None,
                    "assignments": [
                        {
                            "id": "b:0/a:0",
                            "key": "max_connections",
                            "value": "16",
                        },
                        {"id": "b:0/a:1", "key": "lifetime", "value": "0"},
                    ],
                    "blocks": [],
                }
            ],
        }

        response = env_complex.client.put(
            "/ui/clients/LOCAL/tree",
            data={"payload_json": json.dumps(payload)},
        )

        assert response.status_code == 200
        content = env_complex.config_path.read_text(encoding="utf-8")
        assert "secret = testing123" in content

    def test_get_create_form_returns_empty_create_form(
        self, env_complex: UiEnv
    ) -> None:
        c = env_complex.client
        resp = c.get("/ui/clients/create-form")
        assert resp.status_code == 200
        html = resp.text

        assert 'id="form-card"' in html
        assert 'id="add-form"' in html
        assert 'hx-post="/ui/clients/add-tree"' in html

    def test_put_tree_updates_existing_assignment(self, env_complex: UiEnv) -> None:
        c = env_complex.client
        payload = {
            "name": "LOCAL",
            "ipaddr": "127.0.0.1",
            "secret": "testing123",
            "assignments": [{"id": "a:0", "key": "shortname", "value": "new"}],
            "blocks": [
                {
                    "id": "b:0",
                    "kind": "limit",
                    "name": None,
                    "assignments": [
                        {"id": "b:0/a:0", "key": "max_connections", "value": "16"},
                        {"id": "b:0/a:1", "key": "lifetime", "value": "0"},
                    ],
                    "blocks": [],
                }
            ],
        }
        resp = c.put(
            "/ui/clients/LOCAL/tree", data={"payload_json": json.dumps(payload)}
        )
        assert resp.status_code == 200
        assert 'id="add-form"' in resp.text
        assert "clientUpdated" in resp.headers.get("hx-trigger", "")

        text = env_complex.config_path.read_text(encoding="utf-8")
        assert "shortname = new" in text

    def test_put_tree_adds_new_assignment(self, env_complex: UiEnv) -> None:
        c = env_complex.client
        payload = {
            "name": "LOCAL",
            "ipaddr": "127.0.0.1",
            "secret": "testing123",
            "assignments": [
                {"id": "a:0", "key": "shortname", "value": "old"},
                {"id": None, "key": "nastype", "value": "other"},
            ],
            "blocks": [
                {
                    "id": "b:0",
                    "kind": "limit",
                    "name": None,
                    "assignments": [
                        {"id": "b:0/a:0", "key": "max_connections", "value": "16"},
                        {"id": "b:0/a:1", "key": "lifetime", "value": "0"},
                    ],
                    "blocks": [],
                }
            ],
        }
        resp = c.put(
            "/ui/clients/LOCAL/tree", data={"payload_json": json.dumps(payload)}
        )
        assert resp.status_code == 200

        text = env_complex.config_path.read_text(encoding="utf-8")
        assert "nastype = other" in text

    def test_put_tree_deletes_assignment_when_missing(self, env_complex: UiEnv) -> None:
        c = env_complex.client
        payload = {
            "name": "LOCAL",
            "ipaddr": "127.0.0.1",
            "secret": "testing123",
            "assignments": [],
            "blocks": [
                {
                    "id": "b:0",
                    "kind": "limit",
                    "name": None,
                    "assignments": [
                        {"id": "b:0/a:0", "key": "max_connections", "value": "16"},
                        {"id": "b:0/a:1", "key": "lifetime", "value": "0"},
                    ],
                    "blocks": [],
                }
            ],
        }
        resp = c.put(
            "/ui/clients/LOCAL/tree", data={"payload_json": json.dumps(payload)}
        )
        assert resp.status_code == 200

        text = env_complex.config_path.read_text(encoding="utf-8")
        assert "shortname" not in text
        assert "inline short" not in text

    def test_put_tree_updates_nested_block_and_adds_new_block(
        self, env_complex: UiEnv
    ) -> None:
        c = env_complex.client
        payload = {
            "name": "LOCAL",
            "ipaddr": "127.0.0.1",
            "secret": "testing123",
            "assignments": [{"id": "a:0", "key": "shortname", "value": "old"}],
            "blocks": [
                {
                    "id": "b:0",
                    "kind": "limit",
                    "name": None,
                    "assignments": [
                        {"id": "b:0/a:0", "key": "max_connections", "value": "32"},
                        {"id": "b:0/a:1", "key": "lifetime", "value": "0"},
                    ],
                    "blocks": [],
                },
                {
                    "id": None,
                    "kind": "coa",
                    "name": None,
                    "assignments": [{"id": None, "key": "enabled", "value": "yes"}],
                    "blocks": [],
                },
            ],
        }
        resp = c.put(
            "/ui/clients/LOCAL/tree", data={"payload_json": json.dumps(payload)}
        )
        assert resp.status_code == 200

        text = env_complex.config_path.read_text(encoding="utf-8")
        assert re.search(r'max_connections\s*=\s*"?32"?', text)
        assert "coa {" in text
        assert "enabled = yes" in text

    def test_put_tree_preserves_comments_in_file(self, env_complex: UiEnv) -> None:
        c = env_complex.client
        payload = {
            "name": "LOCAL",
            "ipaddr": "127.0.0.2",
            "secret": "testing123",
            "assignments": [{"id": "a:0", "key": "shortname", "value": "old"}],
            "blocks": [
                {
                    "id": "b:0",
                    "kind": "limit",
                    "name": None,
                    "assignments": [
                        {"id": "b:0/a:0", "key": "max_connections", "value": "16"},
                        {"id": "b:0/a:1", "key": "lifetime", "value": "0"},
                    ],
                    "blocks": [],
                }
            ],
        }
        resp = c.put(
            "/ui/clients/LOCAL/tree", data={"payload_json": json.dumps(payload)}
        )
        assert resp.status_code == 200

        text = env_complex.config_path.read_text(encoding="utf-8")
        assert "# header comment" in text
        assert "# inline ip" in text

    def test_put_tree_invalid_node_id_returns_400(self, env_complex: UiEnv) -> None:
        c = env_complex.client
        payload = {
            "name": "LOCAL",
            "ipaddr": "127.0.0.1",
            "secret": "testing123",
            "assignments": [{"id": "a:99", "key": "shortname", "value": "x"}],
            "blocks": [
                {
                    "id": "b:0",
                    "kind": "limit",
                    "name": None,
                    "assignments": [
                        {"id": "b:0/a:0", "key": "max_connections", "value": "16"},
                        {"id": "b:0/a:1", "key": "lifetime", "value": "0"},
                    ],
                    "blocks": [],
                }
            ],
        }
        resp = c.put(
            "/ui/clients/LOCAL/tree", data={"payload_json": json.dumps(payload)}
        )
        assert resp.status_code == 400
        assert 'id="edit-form"' in resp.text

        text = env_complex.config_path.read_text(encoding="utf-8")
        assert "shortname = old" in text

    def test_put_tree_nonexistent_client_returns_404(self, env_complex: UiEnv) -> None:
        c = env_complex.client
        payload = {
            "name": "NOPE",
            "ipaddr": "1.1.1.1",
            "secret": "s",
            "assignments": [],
            "blocks": [],
        }
        resp = c.put(
            "/ui/clients/NOPE/tree", data={"payload_json": json.dumps(payload)}
        )
        assert resp.status_code == 404

    def test_put_tree_response_triggers_row_update(self, env_complex: UiEnv) -> None:
        c = env_complex.client
        payload = {
            "name": "LOCAL",
            "ipaddr": "127.0.0.9",
            "secret": "zzz",
            "assignments": [{"id": "a:0", "key": "shortname", "value": "old"}],
            "blocks": [
                {
                    "id": "b:0",
                    "kind": "limit",
                    "name": None,
                    "assignments": [
                        {"id": "b:0/a:0", "key": "max_connections", "value": "16"},
                        {"id": "b:0/a:1", "key": "lifetime", "value": "0"},
                    ],
                    "blocks": [],
                }
            ],
        }
        resp = c.put(
            "/ui/clients/LOCAL/tree", data={"payload_json": json.dumps(payload)}
        )
        assert resp.status_code == 200

        trigger = resp.headers.get("hx-trigger", "")
        assert "clientUpdated" in trigger
        assert "LOCAL" in trigger
        assert 'id="add-form"' in resp.text

        text = env_complex.config_path.read_text(encoding="utf-8")
        assert "ipaddr = 127.0.0.9" in text
        assert "secret = zzz" in text
