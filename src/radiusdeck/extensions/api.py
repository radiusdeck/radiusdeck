from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from radiusdeck.extensions.contributions import StructuralContributions

if TYPE_CHECKING:
    from radiusdeck.extensions.runtime import ExtensionRuntimeContext

RADIUSDECK_EXTENSION_API = 1


class ExtensionRuntimeHooks(Protocol):
    async def startup(self, context: "ExtensionRuntimeContext") -> object | None: ...

    async def shutdown(self, context: "ExtensionRuntimeContext") -> None: ...


@dataclass(frozen=True)
class ExtensionDefinition:
    name: str
    extension_api_version: int
    structural_contributions: Callable[[object | None], StructuralContributions]
    settings_loader: Callable[[], object] | None = None
    runtime_hooks: Callable[[], ExtensionRuntimeHooks] | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Extension name must not be empty")
