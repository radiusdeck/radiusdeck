from __future__ import annotations

import logging.config
from typing import Any

import pytest

from radiusdeck.core import logging as app_logging


def test_json_logging_uses_current_python_json_logger_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def capture_config(config: dict[str, Any]) -> None:
        captured.update(config)

    monkeypatch.setattr(logging.config, "dictConfig", capture_config)

    app_logging.setup_logging(app_name="RadiusDeck", log_format="json")

    formatter = captured["formatters"]["json"]
    assert formatter["()"] == "pythonjsonlogger.json.JsonFormatter"
