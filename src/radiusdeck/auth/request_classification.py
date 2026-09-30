from __future__ import annotations

from starlette.requests import Request


def is_api_path(path: str) -> bool:
    return path.startswith("/api/")


def is_api_request(request: Request) -> bool:
    return is_api_path(request.url.path)


def is_htmx_request(request: Request) -> bool:
    return request.headers.get("HX-Request", "").lower() == "true"
