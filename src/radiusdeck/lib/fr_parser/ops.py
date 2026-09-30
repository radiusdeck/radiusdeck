from __future__ import annotations

from typing import Iterable, List, Optional, Union

from .ast import Assignment, AstNodes, BlankLine, Block, Node
from .utils import needs_quotes


def iter_blocks(nodes: List[Node], kind: str) -> Iterable[Block]:
    for n in nodes:
        if isinstance(n, Block) and n.kind == kind:
            yield n


def find_client(nodes: List[Node], name: str) -> Optional[Block]:
    for b in iter_blocks(nodes, "client"):
        if b.name == name:
            return b
    return None


def get_assignment(block: Block, key: str) -> Optional[Assignment]:
    for ch in block.children:
        if isinstance(ch, Assignment) and ch.key == key:
            return ch
    return None


def set_assignment(
    block: Block, key: str, value: str, quoted: Union[bool, str, None] = None
) -> None:
    quote_char = None
    if quoted is True:
        quote_char = '"'
    elif isinstance(quoted, str):
        quote_char = quoted

    a = get_assignment(block, key)

    # Auto-detect defaults if new
    if quote_char is None and needs_quotes(value):
        quote_char = '"'

    if a is None:
        block.children.append(Assignment(key=key, value=value, quote_char=quote_char))
        return

    a.value = value
    if quoted is not None:
        a.quote_char = quote_char
    elif a.quote_char is None and needs_quotes(value):
        a.quote_char = '"'


def upsert_client(nodes: List[Node], name: str, params: dict[str, str]) -> Block:
    c = find_client(nodes, name)
    if c is None:
        c = Block(kind="client", name=name, children=[])
        nodes.append(c)
        nodes.append(BlankLine())
    for k, v in params.items():
        set_assignment(c, k, v)
    return c


def upsert_client_block(nodes: AstNodes, client_block: Block) -> Block:
    if client_block.kind != "client" or not client_block.name:
        raise ValueError("client_block must be kind='client' with non-empty name")

    # Replace if exists (keep surrounding whitespace/comments untouched)
    for i, n in enumerate(nodes):
        if isinstance(n, Block) and n.kind == "client" and n.name == client_block.name:
            nodes[i] = client_block
            return client_block

    # Insert new: ensure blank line before and after for readability
    if nodes and not isinstance(nodes[-1], BlankLine):
        nodes.append(BlankLine())

    nodes.append(client_block)

    if not nodes or not isinstance(nodes[-1], BlankLine):
        nodes.append(BlankLine())

    return client_block
