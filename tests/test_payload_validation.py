"""Tests for payload validation and mapper unit tests."""

import pytest

from radiusdeck.lib.fr_parser.ast import Block
from radiusdeck.mappers.client_tree_mapper import (
    _assignment_from_payload,
    client_block_from_payload,
)
from radiusdeck.schemas.client_payload_tree import (
    AssignmentPayload,
    BlockPayload,
    ClientCreateTreePayload,
)


class TestClientTreeMapper:
    def test_simple_payload(self) -> None:
        payload = ClientCreateTreePayload(name="test", ipaddr="1.2.3.4", secret="sec")
        block = client_block_from_payload(payload)

        assert block.kind == "client"
        assert block.name == "test"
        assert len(block.children) == 2

    def test_payload_with_assignments(self) -> None:
        payload = ClientCreateTreePayload(
            name="test",
            ipaddr="1.2.3.4",
            secret="sec",
            assignments=[AssignmentPayload(key="shortname", value="office")],
        )
        block = client_block_from_payload(payload)
        assert len(block.children) == 3

    def test_payload_with_nested_block(self) -> None:
        payload = ClientCreateTreePayload(
            name="test",
            ipaddr="1.2.3.4",
            secret="sec",
            blocks=[
                BlockPayload(
                    kind="limit",
                    assignments=[AssignmentPayload(key="max_connections", value="16")],
                ),
            ],
        )
        block = client_block_from_payload(payload)
        assert len(block.children) == 3

        limit_block = block.children[2]
        assert isinstance(limit_block, Block)
        assert limit_block.kind == "limit"
        assert len(limit_block.children) == 1

    def test_quoted_value_preserved(self) -> None:
        a = _assignment_from_payload(
            AssignmentPayload(key="msg", value="'hello world'")
        )
        assert a.value == "hello world"
        assert a.quote_char == "'"

    def test_value_with_spaces_auto_quoted(self) -> None:
        a = _assignment_from_payload(AssignmentPayload(key="msg", value="hello world"))
        assert a.value == "hello world"
        assert a.quote_char == '"'

    def test_simple_value_no_quotes(self) -> None:
        a = _assignment_from_payload(AssignmentPayload(key="key", value="simple"))
        assert a.value == "simple"
        assert a.quote_char is None


class TestPayloadValidation:
    def test_empty_name_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ClientCreateTreePayload(name="", ipaddr="1.2.3.4", secret="s")

    def test_empty_ipaddr_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ClientCreateTreePayload(name="x", ipaddr="", secret="s")

    def test_duplicate_assignment_keys_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ClientCreateTreePayload(
                name="x",
                ipaddr="1.2.3.4",
                secret="s",
                assignments=[
                    AssignmentPayload(key="a", value="1"),
                    AssignmentPayload(key="a", value="2"),
                ],
            )

    def test_reserved_key_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ClientCreateTreePayload(
                name="x",
                ipaddr="1.2.3.4",
                secret="s",
                assignments=[AssignmentPayload(key="ipaddr", value="hack")],
            )

    def test_duplicate_keys_in_nested_block_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ClientCreateTreePayload(
                name="x",
                ipaddr="1.2.3.4",
                secret="s",
                blocks=[
                    BlockPayload(
                        kind="limit",
                        assignments=[
                            AssignmentPayload(key="k", value="1"),
                            AssignmentPayload(key="k", value="2"),
                        ],
                    )
                ],
            )

    def test_empty_block_kind_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BlockPayload(kind="")

    def test_valid_payload_passes(self) -> None:
        p = ClientCreateTreePayload(
            name="ok",
            ipaddr="10.0.0.1",
            secret="pass",
            assignments=[AssignmentPayload(key="shortname", value="test")],
            blocks=[
                BlockPayload(
                    kind="limit",
                    assignments=[AssignmentPayload(key="max", value="10")],
                    blocks=[
                        BlockPayload(
                            kind="inner",
                            assignments=[AssignmentPayload(key="x", value="1")],
                        )
                    ],
                )
            ],
        )
        assert p.name == "ok"
        assert len(p.blocks) == 1
        assert len(p.blocks[0].blocks) == 1
