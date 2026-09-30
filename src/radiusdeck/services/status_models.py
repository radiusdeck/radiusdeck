from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class StatusLevel(StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class StatusCheck:
    id: str
    label: str
    level: StatusLevel
    message: str
    details: str | None = None
    remediation: str | None = None


@dataclass(frozen=True)
class StatusSection:
    id: str
    title: str
    checks: list[StatusCheck]


@dataclass(frozen=True)
class StatusReport:
    overall_level: StatusLevel
    sections: list[StatusSection]
    metadata: dict[str, str] = field(default_factory=dict)


def overall_status(sections: list[StatusSection]) -> StatusLevel:
    levels = {check.level for section in sections for check in section.checks}
    if StatusLevel.ERROR in levels:
        return StatusLevel.ERROR
    if StatusLevel.WARNING in levels:
        return StatusLevel.WARNING
    return StatusLevel.OK
