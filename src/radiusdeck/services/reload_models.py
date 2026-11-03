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


class ApplyState(Enum):
    """Whether the running FreeRADIUS uses a saved configuration change."""

    RELOADED = "reloaded"  # saved and the reload integration succeeded
    RELOAD_FAILED = "reload_failed"  # saved, but the reload attempt failed
    RESTART_REQUIRED = "restart_required"  # saved, no automatic reload configured


def apply_state(reload_result: ReloadResult, *, changed: bool) -> ApplyState | None:
    """Classify a mutation outcome for user feedback.

    Returns ``None`` when nothing was written, so there is nothing to apply.
    """
    if not changed:
        return None
    if reload_result.status is ReloadStatus.SUCCESS:
        return ApplyState.RELOADED
    if reload_result.status is ReloadStatus.FAILED:
        return ApplyState.RELOAD_FAILED
    return ApplyState.RESTART_REQUIRED
