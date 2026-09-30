from typing import List, Optional

from .ast import Assignment, BlankLine, Block, CommentLine, Node
from .tokens import Token, tokenize


class ParseError(ValueError):
    pass


class Parser:
    def __init__(self, tokens: List[Token]):
        self.toks = tokens
        self.i = 0

    def peek(self) -> Token:
        return self.toks[self.i]

    def pop(self) -> Token:
        t = self.toks[self.i]
        self.i += 1
        return t

    def accept(self, typ: str, val: Optional[str] = None) -> Optional[Token]:
        t = self.peek()
        if t.typ != typ:
            return None
        if val is not None and t.val != val:
            return None
        return self.pop()

    def expect(self, typ: str, val: Optional[str] = None) -> Token:
        t = self.peek()
        if t.typ != typ or (val is not None and t.val != val):
            raise ParseError(
                f"Expected {typ} {val or ''} at {t.pos}, got {t.typ} {t.val!r}"
            )
        return self.pop()


def _parse_trivia(p: Parser, out: List[Node]) -> bool:
    """
    Парсит 'тривию' (комментарии и пустые строки) в узлы AST.
    Возвращает True если что-то было съедено.
    """
    t = p.peek()

    if t.typ == "NEWLINE":
        p.pop()
        out.append(BlankLine())
        return True

    if t.typ == "COMMENT":
        out.append(CommentLine(p.pop().val))
        p.accept("NEWLINE")  # the terminating newline belongs to this line
        return True

    return False


def parse_clients_conf(text: str) -> List[Node]:
    p = Parser(tokenize(text))
    nodes: List[Node] = []

    while p.peek().typ != "EOF":
        if _parse_trivia(p, nodes):
            continue

        nodes.append(_parse_statement(p))

    return nodes


def _parse_statement(p: Parser) -> Node:
    if _looks_like_block(p):
        return _parse_block(p)
    if _looks_like_assignment(p):
        return _parse_assignment(p)

    t = p.peek()
    raise ParseError(
        f"Ожидался блок или присваивание, got {t.typ} {t.val!r} at {t.pos}"
    )


def _parse_block(p: Parser) -> Block:
    kind_token = p.expect("IDENT")
    kind = kind_token.val

    name = None
    if p.peek().typ in ("IDENT", "STRING", "SSTRING"):
        name_token = p.pop()
        if p.peek().typ == "LBRACE":
            name = name_token.val
        else:
            p.i -= 1
            name = None

    p.expect("LBRACE")
    p.accept("NEWLINE")

    children = _parse_block_body(p)

    # Consume newline after block closing
    p.accept("NEWLINE")

    return Block(kind=kind, name=name, children=children)


def _parse_block_body(p: Parser) -> List[Node]:
    children: List[Node] = []

    while True:
        if _parse_trivia(p, children):
            continue

        t = p.peek()

        if t.typ == "RBRACE":
            p.pop()
            return children

        if t.typ == "EOF":
            raise ParseError("Не закрыт блок — достигнут конец файла")

        if t.typ == "IDENT":
            if _looks_like_block(p):
                children.append(_parse_block(p))
            elif _looks_like_assignment(p):
                children.append(_parse_assignment(p))
            else:
                raise ParseError(f"Нераспознанная конструкция на {t.pos}: {t.val}")
            continue

        raise ParseError(f"Неожиданный токен внутри блока: {t.typ} {t.val!r}")


def _parse_assignment(p: Parser) -> Assignment:
    key = p.expect("IDENT").val
    p.expect("EQUAL")

    value, quote_char = _parse_value(p)

    inline_comment = None
    if p.peek().typ == "COMMENT":
        inline_comment = p.pop().val

    p.accept("NEWLINE")

    return Assignment(
        key=key, value=value, quote_char=quote_char, inline_comment=inline_comment
    )


def _parse_value(p: Parser) -> tuple[str, Optional[str]]:
    parts: List[Token] = []
    while True:
        t = p.peek()
        if t.typ in ("NEWLINE", "COMMENT", "RBRACE", "EOF"):
            break
        if t.typ in ("IDENT", "STRING", "SSTRING"):
            parts.append(p.pop())
            continue
        raise ParseError(f"Unexpected token in value: {t.typ} {t.val!r} at {t.pos}")

    if not parts:
        return "", None

    if len(parts) == 1:
        if parts[0].typ == "STRING":
            return parts[0].val, '"'
        if parts[0].typ == "SSTRING":
            return parts[0].val, "'"

    return " ".join(tok.val for tok in parts), None


def _looks_like_block(p: Parser) -> bool:
    save_i = p.i
    try:
        if p.peek().typ != "IDENT":
            return False
        p.pop()
        next_t = p.peek()
        if next_t.typ == "LBRACE":
            return True
        if next_t.typ in ("IDENT", "STRING", "SSTRING"):
            p.pop()
            if p.peek().typ == "LBRACE":
                return True
        return False
    finally:
        p.i = save_i


def _looks_like_assignment(p: Parser) -> bool:
    save_i = p.i
    try:
        if p.peek().typ != "IDENT":
            return False
        p.pop()
        while p.peek().typ == "NEWLINE":
            p.pop()
        if p.peek().typ != "EQUAL":
            return False
        return True
    finally:
        p.i = save_i
