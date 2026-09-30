from __future__ import annotations

from typing import Any

from radiusdeck.lib.fr_parser.ast import Assignment, Block
from radiusdeck.lib.fr_parser.ops import get_assignment


def _block_to_edit_model(block: Block, block_id: str) -> dict[str, Any]:
    assignments: list[dict[str, str]] = []
    blocks: list[dict[str, Any]] = []

    a_idx = 0
    b_idx = 0

    for ch in block.children:
        if isinstance(ch, Assignment):
            assignments.append(
                {
                    "id": f"{block_id}/a:{a_idx}",
                    "key": ch.key,
                    "value": ch.value,
                }
            )
            a_idx += 1
        elif isinstance(ch, Block):
            child_id = f"{block_id}/b:{b_idx}"
            blocks.append(_block_to_edit_model(ch, child_id))
            b_idx += 1

    return {
        "id": block_id,
        "kind": block.kind,
        "name": block.name,
        "assignments": assignments,
        "blocks": blocks,
    }


def client_block_to_edit_model(client: Block) -> dict[str, Any]:
    """
    Build edit-model for left-side edit form.

    Root-level assignments in the edit form are *extra* only:
    ipaddr/secret are handled via dedicated inputs.
    """
    ip = get_assignment(client, "ipaddr")
    secret = get_assignment(client, "secret")

    if ip is None or secret is None:
        raise ValueError("Client must have ipaddr and secret assignments")

    extra_assignments: list[dict[str, str]] = []
    a_idx = 0
    for ch in client.children:
        if isinstance(ch, Assignment) and ch.key not in {"ipaddr", "secret"}:
            extra_assignments.append(
                {"id": f"a:{a_idx}", "key": ch.key, "value": ch.value}
            )
            a_idx += 1

    blocks: list[dict[str, Any]] = []
    b_idx = 0
    for ch in client.children:
        if isinstance(ch, Block):
            blocks.append(_block_to_edit_model(ch, f"b:{b_idx}"))
            b_idx += 1

    return {
        "name": client.name or "",
        "ipaddr": ip.value,
        "assignments": extra_assignments,
        "blocks": blocks,
    }
