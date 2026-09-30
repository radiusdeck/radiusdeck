"""Domain models and errors for FreeRADIUS log viewing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class LogLine:
    number: int | None
    text: str
    level: str | None = None
    matched: bool = False


@dataclass(frozen=True)
class LogTailResult:
    source: Path
    lines: list[LogLine]
    requested_lines: int
    returned_lines: int
    truncated: bool
    query: str | None
    updated_at: datetime


class LogViewerError(Exception):
    """Base class for log viewer domain/service-layer errors."""


class LogViewerDisabledError(LogViewerError):
    """Raised when log viewing is disabled by configuration."""


class LogFileNotFoundError(LogViewerError):
    """Raised when the configured log file does not exist."""


class LogFilePermissionError(LogViewerError):
    """Raised when the configured log file cannot be read due to permissions."""


class LogReadError(LogViewerError):
    """Raised when reading the configured log file fails."""
