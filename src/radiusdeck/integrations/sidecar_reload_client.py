"""HTTP client for docker-reload-sidecar API."""

from __future__ import annotations

import json
import logging

import httpx

from radiusdeck.services.ports import ReloadPort
from radiusdeck.services.reload_models import ReloadResult

logger = logging.getLogger(__name__)


class SidecarReloadClient(ReloadPort):
    """Concrete implementation of ReloadPort using sidecar HTTP API."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        reload_url: str,
        token: str | None = None,
    ) -> None:
        self._http_client = http_client
        self._reload_url = reload_url
        self._token = token

    async def reload(self) -> ReloadResult:
        """POST /reload. Never raises — returns ReloadResult."""
        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            response = await self._http_client.post(
                self._reload_url,
                headers=headers,
            )
        except httpx.TimeoutException:
            logger.warning("Sidecar reload request timed out")
            return ReloadResult.failed("sidecar reload timeout")

        except httpx.HTTPError as exc:
            logger.warning("Sidecar reload request failed: %s", exc)
            return ReloadResult.failed(f"connection error: {exc}")

        # ── parse response body ──────────────────────────────
        body: dict[str, object] | None = None
        detail: str | None = None
        error: str | None = None

        try:
            parsed = response.json()
            if isinstance(parsed, dict):
                body = parsed
        except (json.JSONDecodeError, ValueError):
            body = None

        if body is not None:
            detail_value = body.get("detail")
            error_value = body.get("error")

            if isinstance(detail_value, str):
                detail = detail_value
            if isinstance(error_value, str):
                error = error_value

        # ── determine result ─────────────────────────────────
        if response.is_success:
            logger.info(
                "Sidecar reload succeeded: status=%s detail=%s",
                response.status_code,
                detail,
            )
            return ReloadResult.success(detail or "reloaded")

        logger.warning(
            "Sidecar reload failed: status=%s error=%s",
            response.status_code,
            error,
        )
        return ReloadResult.failed(
            error or f"sidecar returned HTTP {response.status_code}"
        )
