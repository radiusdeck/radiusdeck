from __future__ import annotations

from radiusdeck.lib.fr_parser.ast import Assignment, Block
from radiusdeck.mappers.client_tree_mapper import client_block_from_payload
from radiusdeck.schemas.client_payload_tree import ClientCreateTreePayload


def test_client_tree_mapper_quotes_and_nested_blocks() -> None:
    payload = ClientCreateTreePayload.model_validate(
        {
            "name": "wifi",
            "ipaddr": "192.168.1.50",
            "secret": "radius_secret",
            "assignments": [
                {
                    "key": "message",
                    "value": "Hello there",
                },  # whitespace -> double quotes
                {"key": "filter", "value": "'yes \\' is allowed'"},
            ],
            "blocks": [
                {
                    "kind": "limit",
                    "name": None,
                    "assignments": [{"key": "max_connections", "value": "16"}],
                    "blocks": [],
                }
            ],
        }
    )

    client_blk = client_block_from_payload(payload)
    assert client_blk.kind == "client"
    assert client_blk.name == "wifi"

    msg = next(
        ch
        for ch in client_blk.children
        if isinstance(ch, Assignment) and ch.key == "message"
    )
    assert msg.value == "Hello there"
    assert msg.quote_char == '"'

    flt = next(
        ch
        for ch in client_blk.children
        if isinstance(ch, Assignment) and ch.key == "filter"
    )
    assert flt.value == "yes \\' is allowed"
    assert flt.quote_char == "'"

    limit_blk = next(
        ch for ch in client_blk.children if isinstance(ch, Block) and ch.kind == "limit"
    )
    assert any(
        isinstance(ch, Assignment) and ch.key == "max_connections" and ch.value == "16"
        for ch in limit_blk.children
    )
