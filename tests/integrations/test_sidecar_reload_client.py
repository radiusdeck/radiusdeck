"""Tests for SidecarReloadClient."""

import httpx
import pytest

from radiusdeck.integrations.sidecar_reload_client import SidecarReloadClient
from radiusdeck.services.reload_models import ReloadStatus


@pytest.mark.anyio
async def test_reload_success() -> None:
    """Successful reload returns SUCCESS status."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == httpx.URL("http://reload-sidecar:9090/reload")
        assert request.headers["Authorization"] == "Bearer my-secret"
        return httpx.Response(
            status_code=200,
            json={
                "ok": True,
                "detail": "container restarted",
                "container": "freeradius",
            },
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SidecarReloadClient(
            http_client=http_client,
            reload_url="http://reload-sidecar:9090/reload",
            token="my-secret",
        )

        result = await client.reload()

    assert result.status == ReloadStatus.SUCCESS
    assert result.detail == "container restarted"
    assert result.is_ok is True


@pytest.mark.anyio
async def test_reload_forbidden() -> None:
    """403 Forbidden returns FAILED status."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=403,
            json={
                "ok": False,
                "error": "forbidden",
            },
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SidecarReloadClient(
            http_client=http_client,
            reload_url="http://reload-sidecar:9090/reload",
            token="wrong-token",
        )

        result = await client.reload()

    assert result.status == ReloadStatus.FAILED
    assert result.detail == "forbidden"
    assert result.is_ok is False


@pytest.mark.anyio
async def test_reload_timeout() -> None:
    """Network timeout returns FAILED status."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SidecarReloadClient(
            http_client=http_client,
            reload_url="http://reload-sidecar:9090/reload",
            token="my-secret",
        )

        result = await client.reload()

    assert result.status == ReloadStatus.FAILED
    assert "timeout" in result.detail.lower()
    assert result.is_ok is False


@pytest.mark.anyio
async def test_reload_non_json_error_response() -> None:
    """Non-JSON 500 error returns FAILED with generic message."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=500,
            content=b"internal error",
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SidecarReloadClient(
            http_client=http_client,
            reload_url="http://reload-sidecar:9090/reload",
            token="my-secret",
        )

        result = await client.reload()

    assert result.status == ReloadStatus.FAILED
    assert "500" in result.detail
    assert result.is_ok is False


@pytest.mark.anyio
async def test_reload_success_no_detail() -> None:
    """Success without detail field uses default message."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"ok": True},  # no "detail" field
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SidecarReloadClient(
            http_client=http_client,
            reload_url="http://reload-sidecar:9090/reload",
        )

        result = await client.reload()

    assert result.status == ReloadStatus.SUCCESS
    assert result.detail == "reloaded"  # default from factory
