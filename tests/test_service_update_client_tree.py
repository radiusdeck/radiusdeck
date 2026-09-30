from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from radiusdeck.integrations.null_reload_client import NullReloadClient
from radiusdeck.lib.fr_parser import parse_clients_conf
from radiusdeck.lib.fr_parser.ast import Assignment, BlankLine, CommentLine
from radiusdeck.lib.fr_parser.ops import find_client
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.schemas.client_edit_payload import (
    AssignmentEditPayload,
    BlockEditPayload,
    ClientEditTreePayload,
)
from radiusdeck.services.errors import ClientNotFoundError, InvalidNodeIdError
from radiusdeck.services.radius_service import RadiusService


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture()
def config_path(tmp_path: Path) -> Path:
    p = tmp_path / "clients.conf"
    p.write_text(
        """client LOCAL {
    # header comment
    ipaddr = 127.0.0.1 # inline ip
    secret = testing123

    shortname = old # inline short
    limit {
        max_connections = "16"
    }
}
""",
        encoding="utf-8",
    )
    return p


@pytest.fixture()
def service(config_path: Path) -> RadiusService:
    return RadiusService(
        ClientsConfStore(str(config_path)), reloader=NullReloadClient()
    )


def test_update_client_tree_success_preserves_comments(
    service: RadiusService, config_path: Path
) -> None:
    payload = ClientEditTreePayload(
        name="LOCAL",
        ipaddr="127.0.0.2",
        secret="newsecret",
        assignments=[
            AssignmentEditPayload(id="a:0", key="shortname", value="new"),
        ],
        blocks=[
            BlockEditPayload(
                id="b:0",
                kind="limit",
                name=None,
                assignments=[
                    AssignmentEditPayload(
                        id="b:0/a:0", key="max_connections", value="32"
                    ),
                ],
                blocks=[],
            )
        ],
    )

    updated = _run(service.update_client_tree("LOCAL", payload))
    updated_client = updated.client
    assert updated_client["name"] == "LOCAL"
    assert updated_client["ipaddr"] == "127.0.0.2"
    assert updated_client["secret"] == "newsecret"

    # inspect AST to ensure comments/blanks preserved
    nodes = parse_clients_conf(config_path.read_text(encoding="utf-8"))
    blk = find_client(nodes, "LOCAL")
    assert blk is not None

    # comment line still exists
    assert any(
        isinstance(n, CommentLine) and "header comment" in n.text for n in blk.children
    )
    # blank line still exists
    assert any(isinstance(n, BlankLine) for n in blk.children)

    # inline comment preserved on updated assignments
    ip = next(
        n for n in blk.children if isinstance(n, Assignment) and n.key == "ipaddr"
    )
    assert ip.inline_comment is not None
    assert "inline ip" in ip.inline_comment

    short = next(
        n for n in blk.children if isinstance(n, Assignment) and n.key == "shortname"
    )
    assert short.inline_comment is not None
    assert "inline short" in short.inline_comment


def test_update_client_tree_not_found(service: RadiusService) -> None:
    payload = ClientEditTreePayload(
        name="NOPE",
        ipaddr="1.1.1.1",
        secret="s",
        assignments=[],
        blocks=[],
    )
    with pytest.raises(ClientNotFoundError):
        _run(service.update_client_tree("NOPE", payload))


def test_update_client_tree_invalid_node_id(service: RadiusService) -> None:
    payload = ClientEditTreePayload(
        name="LOCAL",
        ipaddr="127.0.0.1",
        secret="testing123",
        assignments=[AssignmentEditPayload(id="a:99", key="shortname", value="x")],
        blocks=[
            BlockEditPayload(
                id="b:0",
                kind="limit",
                name=None,
                assignments=[
                    AssignmentEditPayload(
                        id="b:0/a:0", key="max_connections", value="16"
                    )
                ],
                blocks=[],
            )
        ],
    )

    with pytest.raises(InvalidNodeIdError):
        _run(service.update_client_tree("LOCAL", payload))
