from __future__ import annotations

import httpx
import pytest

from radiusdeck.integrations.sidecar_health_client import SidecarHealthClient


@pytest.mark.asyncio
async def test_sidecar_health_client_reports_success_and_sends_token() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer health-token"
        return httpx.Response(200, json={"status": "ok"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SidecarHealthClient(
            client, "http://sidecar:9090/health", "health-token"
        ).check()

    assert result.available is True
    assert result.healthy is True
    assert "health-token" not in result.message


@pytest.mark.asyncio
async def test_sidecar_health_client_reports_http_failure() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SidecarHealthClient(client, "http://sidecar:9090/health").check()

    assert result.available is True
    assert result.healthy is False
    assert "503" in result.message


@pytest.mark.asyncio
async def test_sidecar_health_client_hides_network_error_details() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("secret-host-details")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SidecarHealthClient(client, "http://sidecar:9090/health").check()

    assert result.available is True
    assert result.healthy is False
    assert "secret-host-details" not in result.message
