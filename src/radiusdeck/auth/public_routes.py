from __future__ import annotations

PUBLIC_EXACT_PATHS: frozenset[str] = frozenset(
    {
        "/login",
        "/logout",
        "/health",
        "/favicon.ico",
    }
)

PUBLIC_PATH_PREFIXES: tuple[str, ...] = ("/static",)


def is_public_path(
    path: str,
    *,
    exact_paths: frozenset[str] = PUBLIC_EXACT_PATHS,
    prefixes: tuple[str, ...] = PUBLIC_PATH_PREFIXES,
) -> bool:
    if path in exact_paths:
        return True

    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in prefixes)
