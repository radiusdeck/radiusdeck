# src/radiusdeck/core/logging.py
import logging
import logging.config
from contextvars import ContextVar
from typing import Optional

try:
    from pythonjsonlogger.json import JsonFormatter
except ImportError:  # pragma: no cover - optional dependency guard
    JsonFormatter = None  # type: ignore[misc, assignment]

request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or "-"
        return True


def setup_logging(
    *, app_name: str, level: str = "INFO", log_format: str = "console"
) -> None:
    level = level.upper()

    formatters = {
        "console": {
            "format": "%(asctime)s %(levelname)s %(name)s [request_id=%(request_id)s] %(message)s",
        },
    }

    if log_format == "json":
        if JsonFormatter is None:
            raise RuntimeError(
                "LOG_FORMAT=json requires python-json-logger in requirements.txt"
            )

        # In JSON, it's usually better to keep keys stable
        formatters["json"] = {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
        }

    chosen_formatter = "json" if log_format == "json" else "console"

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": "radiusdeck.core.logging.RequestIdFilter"},
        },
        "formatters": formatters,
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": chosen_formatter,
                "filters": ["request_id"],
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": level,
            "handlers": ["default"],
        },
        # Important: so that uvicorn does not duplicate and writes with the same handlers
        "loggers": {
            "uvicorn": {"level": level, "handlers": ["default"], "propagate": False},
            "uvicorn.error": {
                "level": level,
                "handlers": ["default"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": level,
                "handlers": ["default"],
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(config)
    logging.getLogger(__name__).info("Logging configured", extra={"app_name": app_name})
