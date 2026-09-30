from __future__ import annotations

_ALLOWED_UNQUOTED = set(
    "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "0123456789" "._-/:*@+"
)


def needs_quotes(value: str) -> bool:
    v = value.strip()
    if v == "":
        return False

    # spaces always require quotes
    if any(ch.isspace() for ch in v):
        return True

    # comment char would break syntax
    if "#" in v:
        return True

    # quotes must be explicit
    if '"' in v or "'" in v:
        return True

    # braces etc. are unsafe unquoted
    if "{" in v or "}" in v:
        return True

    # allow common FreeRADIUS bare tokens: numbers, ip, ipv6(::), *, /path, etc.
    return any(ch not in _ALLOWED_UNQUOTED for ch in v)
