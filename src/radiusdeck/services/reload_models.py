"""Domain models for reload operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReloadStatus(Enum):
    """Outcome status of a reload attempt."""

    SUCCESS = "success"  # reload triggered and succeeded
    FAILED = "failed"  # reload triggered but failed
    SKIPPED = "skipped"  # reload not configured / disabled


@dataclass(frozen=True)
class ReloadResult:
    """Immutable result of a reload attempt.

    Returned by service layer to routers for UI feedback.
    """

    status: ReloadStatus
    detail: str

    @property
    def is_ok(self) -> bool:
        """True if reload succeeded or was intentionally skipped."""
        return self.status in (ReloadStatus.SUCCESS, ReloadStatus.SKIPPED)

    # ── factory helpers ──────────────────────────────────

    @classmethod
    def success(cls, detail: str = "reloaded") -> ReloadResult:
        return cls(status=ReloadStatus.SUCCESS, detail=detail)

    @classmethod
    def failed(cls, detail: str) -> ReloadResult:
        return cls(status=ReloadStatus.FAILED, detail=detail)

    @classmethod
    def skipped(cls, detail: str = "reload disabled") -> ReloadResult:
        return cls(status=ReloadStatus.SKIPPED, detail=detail)
