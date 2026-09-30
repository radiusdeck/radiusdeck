from __future__ import annotations

import pytest

from radiusdeck.lib.fr_parser.ast import Assignment, BlankLine, Block, CommentLine
from radiusdeck.lib.fr_parser.merge import merge_client_block
from radiusdeck.schemas.client_edit_payload import (
    AssignmentEditPayload,
    BlockEditPayload,
    ClientEditTreePayload,
)


def _client_with_one_extra() -> Block:
    return Block(
        kind="client",
        name="LOCAL",
        children=[
            CommentLine("header comment"),
            Assignment(key="ipaddr", value="127.0.0.1"),
            Assignment(key="secret", value="testing123"),
            BlankLine(),
            Assignment(key="shortname", value="old", inline_comment="keep-inline"),
            Block(
                kind="limit",
                name=None,
                children=[
                    Assignment(key="max_connections", value="16", quote_char='"'),
                ],
            ),
        ],
    )


def test_merge_updates_assignment_value() -> None:
    blk = _client_with_one_extra()

    payload = ClientEditTreePayload(
        name="LOCAL",
        ipaddr="127.0.0.1",
        secret="testing123",
        assignments=[AssignmentEditPayload(id="a:0", key="shortname", value="new")],
        blocks=[],
    )
    merge_client_block(blk, payload)

    short = next(
        n for n in blk.children if isinstance(n, Assignment) and n.key == "shortname"
    )
    assert short.value == "new"
    assert short.inline_comment == "keep-inline"


def test_merge_renames_assignment_key() -> None:
    blk = _client_with_one_extra()

    payload = ClientEditTreePayload(
        name="LOCAL",
        ipaddr="127.0.0.1",
        secret="testing123",
        assignments=[AssignmentEditPayload(id="a:0", key="shortname2", value="old")],
        blocks=[],
    )
    merge_client_block(blk, payload)

    assert any(
        isinstance(n, Assignment) and n.key == "shortname2" for n in blk.children
    )
    assert not any(
        isinstance(n, Assignment) and n.key == "shortname" for n in blk.children
    )


def test_merge_deletes_assignment_if_missing_from_payload() -> None:
    blk = _client_with_one_extra()

    payload = ClientEditTreePayload(
        name="LOCAL",
        ipaddr="127.0.0.1",
        secret="testing123",
        assignments=[],
        blocks=[],
    )
    merge_client_block(blk, payload)

    assert not any(
        isinstance(n, Assignment) and n.key == "shortname" for n in blk.children
    )
    # required stay
    assert any(isinstance(n, Assignment) and n.key == "ipaddr" for n in blk.children)
    assert any(isinstance(n, Assignment) and n.key == "secret" for n in blk.children)


def test_inline_comment_removed_with_assignment() -> None:
    blk = _client_with_one_extra()
    assert any(
        isinstance(n, Assignment)
        and n.key == "shortname"
        and n.inline_comment == "keep-inline"
        for n in blk.children
    )

    payload = ClientEditTreePayload(
        name="LOCAL",
        ipaddr="127.0.0.1",
        secret="testing123",
        assignments=[],
        blocks=[],
    )
    merge_client_block(blk, payload)

    assert not any(
        isinstance(n, Assignment) and n.inline_comment == "keep-inline"
        for n in blk.children
    )


def test_comment_and_blankline_preserved() -> None:
    blk = _client_with_one_extra()

    payload = ClientEditTreePayload(
        name="LOCAL",
        ipaddr="127.0.0.1",
        secret="testing123",
        assignments=[],
        blocks=[],
    )
    merge_client_block(blk, payload)

    assert any(
        isinstance(n, CommentLine) and n.text == "header comment" for n in blk.children
    )
    assert any(isinstance(n, BlankLine) for n in blk.children)


def test_add_new_assignment_id_null() -> None:
    blk = _client_with_one_extra()

    payload = ClientEditTreePayload(
        name="LOCAL",
        ipaddr="127.0.0.1",
        secret="testing123",
        assignments=[AssignmentEditPayload(id=None, key="nastype", value="other")],
        blocks=[],
    )
    merge_client_block(blk, payload)

    assert any(
        isinstance(n, Assignment) and n.key == "nastype" and n.value == "other"
        for n in blk.children
    )


def test_new_assignment_inserted_before_first_block() -> None:
    blk = _client_with_one_extra()

    payload = ClientEditTreePayload(
        name="LOCAL",
        ipaddr="127.0.0.1",
        secret="testing123",
        assignments=[AssignmentEditPayload(id=None, key="nastype", value="other")],
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
    merge_client_block(blk, payload)

    pos_new = next(
        i
        for i, n in enumerate(blk.children)
        if isinstance(n, Assignment) and n.key == "nastype"
    )
    pos_block = next(
        i
        for i, n in enumerate(blk.children)
        if isinstance(n, Block) and n.kind == "limit"
    )
    assert pos_new < pos_block


def test_merge_updates_nested_block_assignment_recursively() -> None:
    blk = _client_with_one_extra()

    payload = ClientEditTreePayload(
        name="LOCAL",
        ipaddr="127.0.0.1",
        secret="testing123",
        assignments=[],
        blocks=[
            BlockEditPayload(
                id="b:0",
                kind="limit",
                name=None,
                assignments=[
                    AssignmentEditPayload(
                        id="b:0/a:0", key="max_connections", value="32"
                    )
                ],
                blocks=[],
            )
        ],
    )
    merge_client_block(blk, payload)

    limit = next(n for n in blk.children if isinstance(n, Block) and n.kind == "limit")
    mc = next(
        n
        for n in limit.children
        if isinstance(n, Assignment) and n.key == "max_connections"
    )
    assert mc.value == "32"
    # quote preserved because user did not provide explicit quotes and existing had quote_char '"'
    assert mc.quote_char == '"'


def test_delete_nested_block() -> None:
    blk = _client_with_one_extra()
    assert any(isinstance(n, Block) and n.kind == "limit" for n in blk.children)

    payload = ClientEditTreePayload(
        name="LOCAL",
        ipaddr="127.0.0.1",
        secret="testing123",
        assignments=[],
        blocks=[],
    )
    merge_client_block(blk, payload)

    assert not any(isinstance(n, Block) and n.kind == "limit" for n in blk.children)


def test_add_new_nested_block_at_end() -> None:
    blk = Block(
        kind="client",
        name="LOCAL",
        children=[
            Assignment(key="ipaddr", value="127.0.0.1"),
            Assignment(key="secret", value="testing123"),
        ],
    )

    payload = ClientEditTreePayload(
        name="LOCAL",
        ipaddr="127.0.0.1",
        secret="testing123",
        assignments=[],
        blocks=[
            BlockEditPayload(
                id=None,
                kind="limit",
                name=None,
                assignments=[AssignmentEditPayload(id=None, key="lifetime", value="0")],
                blocks=[],
            )
        ],
    )
    merge_client_block(blk, payload)

    assert any(isinstance(n, Block) and n.kind == "limit" for n in blk.children)


def test_unknown_node_id_raises_value_error() -> None:
    blk = _client_with_one_extra()

    payload = ClientEditTreePayload(
        name="LOCAL",
        ipaddr="127.0.0.1",
        secret="testing123",
        assignments=[AssignmentEditPayload(id="a:99", key="shortname", value="x")],
        blocks=[],
    )

    with pytest.raises(ValueError, match="Unknown node id"):
        merge_client_block(blk, payload)


def test_duplicate_key_raises_value_error() -> None:
    blk = Block(
        kind="client",
        name="LOCAL",
        children=[
            Assignment(key="ipaddr", value="127.0.0.1"),
            Assignment(key="secret", value="testing123"),
            Assignment(key="k1", value="v1"),
            Assignment(key="k2", value="v2"),
        ],
    )

    # Bypass schema-level duplicate prevention by using model_construct
    #  (even if we later add such checks)
    payload = ClientEditTreePayload.model_construct(
        name="LOCAL",
        ipaddr="127.0.0.1",
        secret="testing123",
        assignments=[
            AssignmentEditPayload.model_construct(id="a:0", key="dup", value="v1"),
            AssignmentEditPayload.model_construct(id="a:1", key="dup", value="v2"),
        ],
        blocks=[],
    )

    with pytest.raises(ValueError, match="Duplicate assignment key"):
        merge_client_block(blk, payload)


def test_quote_char_preserved_on_update_without_explicit_quotes() -> None:
    blk = Block(
        kind="client",
        name="LOCAL",
        children=[
            Assignment(key="ipaddr", value="127.0.0.1"),
            Assignment(key="secret", value="testing123"),
            Assignment(key="msg", value="old", quote_char="'"),
        ],
    )

    payload = ClientEditTreePayload(
        name="LOCAL",
        ipaddr="127.0.0.1",
        secret="testing123",
        assignments=[AssignmentEditPayload(id="a:0", key="msg", value="new val")],
        blocks=[],
    )
    merge_client_block(blk, payload)

    msg = next(n for n in blk.children if isinstance(n, Assignment) and n.key == "msg")
    assert msg.value == "new val"
    assert msg.quote_char == "'"


def test_ipaddr_and_secret_not_deleted_when_assignments_empty() -> None:
    blk = _client_with_one_extra()

    payload = ClientEditTreePayload(
        name="LOCAL",
        ipaddr="10.0.0.1",
        secret="new",
        assignments=[],
        blocks=[],
    )
    merge_client_block(blk, payload)

    ip = next(
        n for n in blk.children if isinstance(n, Assignment) and n.key == "ipaddr"
    )
    sec = next(
        n for n in blk.children if isinstance(n, Assignment) and n.key == "secret"
    )
    assert ip.value == "10.0.0.1"
    assert sec.value == "new"
