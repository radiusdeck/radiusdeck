from __future__ import annotations

import pytest

from radiusdeck.schemas.client_payload_tree import ClientCreateTreePayload


def test_payload_rejects_reserved_assignment_key() -> None:
    with pytest.raises(ValueError, match="reserved"):
        ClientCreateTreePayload.model_validate(
            {
                "name": "n",
                "ipaddr": "1.1.1.1",
                "secret": "s",
                "assignments": [{"key": "secret", "value": "x"}],
                "blocks": [],
            }
        )


def test_payload_rejects_duplicate_assignment_keys() -> None:
    with pytest.raises(ValueError, match="Duplicate assignment key"):
        ClientCreateTreePayload.model_validate(
            {
                "name": "n",
                "ipaddr": "1.1.1.1",
                "secret": "s",
                "assignments": [
                    {"key": "shortname", "value": "a"},
                    {"key": "shortname", "value": "b"},
                ],
                "blocks": [],
            }
        )


def test_payload_rejects_duplicate_keys_inside_block() -> None:
    with pytest.raises(ValueError, match="Duplicate assignment key in block"):
        ClientCreateTreePayload.model_validate(
            {
                "name": "n",
                "ipaddr": "1.1.1.1",
                "secret": "s",
                "assignments": [],
                "blocks": [
                    {
                        "kind": "limit",
                        "name": None,
                        "assignments": [
                            {"key": "max_connections", "value": "1"},
                            {"key": "max_connections", "value": "2"},
                        ],
                        "blocks": [],
                    }
                ],
            }
        )
