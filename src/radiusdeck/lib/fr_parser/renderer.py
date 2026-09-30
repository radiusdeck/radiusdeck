from typing import List, Optional

from .ast import Assignment, BlankLine, Block, CommentLine, Node
from .utils import needs_quotes


def render_clients_conf(nodes: List[Node], indent: str = "    ") -> str:
    out: List[str] = []
    for node in nodes:
        out.append(_render_node(node, indent=indent, level=0))
    return "".join(out)


def _render_node(node: Node, indent: str, level: int) -> str:
    pref = indent * level

    if isinstance(node, BlankLine):
        return "\n"

    if isinstance(node, CommentLine):
        return f"{pref}{node.text}\n"

    if isinstance(node, Assignment):
        v = _render_value(node.value, quote_char=node.quote_char)
        s = f"{pref}{node.key} = {v}"
        if node.inline_comment:
            s += f" {node.inline_comment}"
        return s + "\n"

    if isinstance(node, Block):
        header = f"{pref}{node.kind}"
        if node.name is not None:
            header += f" {node.name}"
        header += " {\n"
        body = "".join(
            _render_node(ch, indent=indent, level=level + 1) for ch in node.children
        )
        tail = f"{pref}}}\n"
        return header + body + tail

    raise TypeError(f"Unknown node type: {type(node)}")


def _render_value(value: str, quote_char: Optional[str]) -> str:
    if quote_char is None:
        if needs_quotes(value):
            quote_char = '"'
        else:
            return value

    if quote_char == "'":
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"

    # Default to double quotes
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'
