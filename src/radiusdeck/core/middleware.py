# src/radiusdeck/core/middleware.py
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from radiusdeck.core.logging import request_id_ctx

logger = logging.getLogger("radiusdeck.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(rid)

        start = time.perf_counter()

        logger.debug("-> %s %s", request.method, request.url.path)
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled exception during request")
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000

            # Log the request summary (can be made DEBUG if noisy)
            logger.info(
                "%s %s -> %s (%.2fms)",
                request.method,
                request.url.path,
                getattr(locals().get("response", None), "status_code", "ERR"),
                duration_ms,
            )

            request_id_ctx.reset(token)

        response.headers["X-Request-ID"] = rid
        return response
