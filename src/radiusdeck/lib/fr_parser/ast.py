from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias


@dataclass(slots=True)
class BlankLine:
    pass


@dataclass(slots=True)
class CommentLine:
    text: str  # without trailing newline


@dataclass(slots=True)
class Assignment:
    key: str
    value: str
    quote_char: str | None = None
    inline_comment: str | None = None


@dataclass(slots=True)
class Block:
    kind: str
    name: str | None = None
    children: list["Node"] = field(default_factory=list)


Node: TypeAlias = BlankLine | CommentLine | Assignment | Block
AstNodes: TypeAlias = list[Node]
