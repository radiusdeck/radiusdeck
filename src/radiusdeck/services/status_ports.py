from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProbeResult:
    available: bool
    healthy: bool
    message: str


class StatusProbePort(Protocol):
    async def check(self) -> ProbeResult: ...
