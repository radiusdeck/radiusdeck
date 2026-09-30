from __future__ import annotations

import re
from datetime import datetime, timezone

from radiusdeck.repositories.log_file_store import LogFileStore
from radiusdeck.services.log_models import (
    LogLine,
    LogTailResult,
    LogViewerDisabledError,
)

_SENSITIVE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(User-Password|client_secret|password|secret)\b(\s*[=:]\s*)"
            r"(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|\S+)",
            re.I,
        ),
        r"\1\2<redacted>",
    ),
    (
        re.compile(r"\b(Authorization\s*:\s*Bearer)\s+\S+", re.I),
        r"\1 <redacted>",
    ),
)

_LEVEL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(error|err|failed|failure)\b", re.I), "error"),
    (re.compile(r"\b(warn|warning)\b", re.I), "warning"),
    (re.compile(r"\binfo\b", re.I), "info"),
    (re.compile(r"\bdebug\b", re.I), "debug"),
)


def redact_log_line(line: str) -> str:
    for pattern, replacement in _SENSITIVE_PATTERNS:
        line = pattern.sub(replacement, line)
    return line


def detect_log_level(line: str) -> str | None:
    for pattern, level in _LEVEL_PATTERNS:
        if pattern.search(line):
            return level
    return None


class LogService:
    MAX_LINES = 200

    def __init__(
        self, store: LogFileStore, enabled: bool, default_lines: int = 200
    ) -> None:
        self.store = store
        self.enabled = enabled
        self.configured_default_lines = default_lines
        self.default_lines = max(1, min(default_lines, self.MAX_LINES))

    async def tail(self, lines: int | None = None) -> LogTailResult:
        if not self.enabled:
            raise LogViewerDisabledError("FreeRADIUS log viewer is disabled")
        count = max(1, min(lines or self.default_lines, self.MAX_LINES))
        raw_lines, truncated = await self.store.tail(count)
        result = [
            LogLine(
                number=None,
                text=redact_log_line(line),
                level=detect_log_level(line),
                matched=False,
            )
            for line in raw_lines
        ]
        return LogTailResult(
            source=self.store.path,
            lines=result,
            requested_lines=count,
            returned_lines=len(result),
            truncated=truncated,
            query=None,
            updated_at=datetime.now(timezone.utc),
        )
