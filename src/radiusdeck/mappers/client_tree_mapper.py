from __future__ import annotations

from radiusdeck.lib.fr_parser.ast import Assignment, Block
from radiusdeck.schemas.client_payload_tree import (
    AssignmentPayload,
    BlockPayload,
    ClientCreateTreePayload,
)


def _assignment_from_payload(a: AssignmentPayload) -> Assignment:
    raw = a.value.strip()

    quote_char: str | None = None
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        quote_char = raw[0]
        raw = raw[1:-1]
    elif any(ch.isspace() for ch in raw):
        quote_char = '"'

    return Assignment(key=a.key, value=raw, quote_char=quote_char)


def _block_from_payload(b: BlockPayload) -> Block:
    name = (b.name or "").strip() or None
    blk = Block(kind=b.kind, name=name)
    blk.children.extend(_assignment_from_payload(a) for a in b.assignments)
    blk.children.extend(_block_from_payload(sb) for sb in b.blocks)
    return blk


def client_block_from_payload(p: ClientCreateTreePayload) -> Block:
    client = Block(kind="client", name=p.name)

    client.children.append(Assignment(key="ipaddr", value=p.ipaddr))
    client.children.append(Assignment(key="secret", value=p.secret))

    client.children.extend(_assignment_from_payload(a) for a in p.assignments)
    client.children.extend(_block_from_payload(b) for b in p.blocks)

    return client
