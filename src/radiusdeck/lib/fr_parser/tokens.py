from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Token:
    typ: str  # IDENT, STRING, SSTRING, LBRACE, RBRACE, EQUAL, NEWLINE, COMMENT, EOF
    val: str
    pos: int


_PUNCT_STOP = set("{}=\n")


def tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    n = len(text)

    def emit(typ: str, val: str, pos: int) -> None:
        tokens.append(Token(typ, val, pos))

    while i < n:
        c = text[i]

        if c == "\n":
            emit("NEWLINE", "\n", i)
            i += 1
            continue

        if c.isspace():
            i += 1
            continue

        # Comments
        if c == "#":
            start = i
            j = i
            while j < n and text[j] != "\n":
                j += 1
            emit("COMMENT", text[start:j], start)
            i = j
            continue

        if c == "/" and i + 1 < n and text[i + 1] == "/":
            start = i
            j = i
            while j < n and text[j] != "\n":
                j += 1
            emit("COMMENT", text[start:j], start)
            i = j
            continue

        # Punctuation
        if c == "{":
            emit("LBRACE", "{", i)
            i += 1
            continue
        if c == "}":
            emit("RBRACE", "}", i)
            i += 1
            continue
        if c == "=":
            emit("EQUAL", "=", i)
            i += 1
            continue

        # Quoted strings
        if c in ("'", '"'):
            quote = c
            start = i
            i += 1
            buf = []
            while i < n:
                c2 = text[i]
                if c2 == "\\" and i + 1 < n:
                    next_char = text[i + 1]
                    # Escape only if the next character is a quote or slash
                    if next_char in ("'", '"', "\\"):
                        buf.append(next_char)
                        i += 2
                        continue
                    buf.append("\\")
                    i += 1
                    continue

                if c2 == quote:
                    i += 1
                    break

                buf.append(c2)
                i += 1

            tok_type = "SSTRING" if quote == "'" else "STRING"
            emit(tok_type, "".join(buf), start)
            continue

        # Identifiers / bare words
        start = i
        while i < n:
            c2 = text[i]
            if c2.isspace() or c2 in _PUNCT_STOP or c2 == "#":
                break
            if c2 == "/" and i + 1 < n and text[i + 1] == "/":
                break
            i += 1
        emit("IDENT", text[start:i], start)

    emit("EOF", "", n)
    return tokens
