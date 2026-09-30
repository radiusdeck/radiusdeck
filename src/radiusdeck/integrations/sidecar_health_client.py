from __future__ import annotations

import httpx

from radiusdeck.services.status_ports import ProbeResult


class SidecarHealthClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        health_url: str,
        token: str | None = None,
    ) -> None:
        self._http_client = http_client
        self._health_url = health_url
        self._token = token

    async def check(self) -> ProbeResult:
        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            response = await self._http_client.get(self._health_url, headers=headers)
        except httpx.TimeoutException:
            return ProbeResult(True, False, "Reload sidecar health check timed out.")
        except httpx.HTTPError:
            return ProbeResult(True, False, "Reload sidecar health check failed.")

        if response.is_success:
            return ProbeResult(True, True, "Reload sidecar is reachable.")
        return ProbeResult(
            True,
            False,
            f"Reload sidecar health endpoint returned HTTP {response.status_code}.",
        )
