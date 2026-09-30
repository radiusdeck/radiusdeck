from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TypeVar

from radiusdeck.extensions.api import ExtensionDefinition, ExtensionRuntimeHooks
from radiusdeck.services.backup_service import BackupService
from radiusdeck.services.local_auth_service import LocalAuthService
from radiusdeck.services.log_service import LogService
from radiusdeck.services.operation_policy import OperationPolicySlot
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.services.status_service import StatusService

logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass(frozen=True)
class BaseRuntimeServices:
    radius: RadiusService
    backup: BackupService
    logs: LogService
    status: StatusService
    local_auth: LocalAuthService | None
    operation_policy: OperationPolicySlot = field(default_factory=OperationPolicySlot)


@dataclass
class ExtensionRuntimeRegistry:
    _values: dict[str, object | None] = field(default_factory=dict)

    def register(self, extension_name: str, value: object | None) -> None:
        if extension_name in self._values:
            raise ValueError(f"Runtime state already registered: {extension_name}")
        self._values[extension_name] = value

    def resolve(self, extension_name: str, expected_type: type[T]) -> T:
        if extension_name not in self._values:
            raise LookupError(f"Extension runtime is not registered: {extension_name}")
        value = self._values[extension_name]
        if not isinstance(value, expected_type):
            raise TypeError(
                f"Extension runtime {extension_name!r} is not "
                f"{expected_type.__name__}"
            )
        return value

    def contains(self, extension_name: str) -> bool:
        return extension_name in self._values


@dataclass(frozen=True)
class ExtensionRuntimeContext:
    services: BaseRuntimeServices
    registry: ExtensionRuntimeRegistry
    extension_settings: Mapping[str, object | None] = field(default_factory=dict)


class ExtensionRuntimeManager:
    def __init__(
        self,
        definitions: tuple[ExtensionDefinition, ...],
        context: ExtensionRuntimeContext,
    ) -> None:
        self._definitions = definitions
        self._context = context
        self._started: list[tuple[str, ExtensionRuntimeHooks]] = []

    async def startup(self) -> None:
        for definition in self._definitions:
            if definition.runtime_hooks is None:
                self._context.registry.register(definition.name, None)
                continue

            hooks: ExtensionRuntimeHooks | None = None
            try:
                hooks = definition.runtime_hooks()
                value = await hooks.startup(self._context)
                self._context.registry.register(definition.name, value)
                self._started.append((definition.name, hooks))
            except BaseException as startup_error:
                cleanup_errors: list[BaseException] = []
                if hooks is not None:
                    try:
                        await hooks.shutdown(self._context)
                    except BaseException as cleanup_error:
                        cleanup_errors.append(cleanup_error)
                cleanup_errors.extend(await self._shutdown_started())
                for recorded_cleanup_error in cleanup_errors:
                    startup_error.add_note(
                        "Extension cleanup failed: "
                        f"{type(recorded_cleanup_error).__name__}: "
                        f"{recorded_cleanup_error}"
                    )
                raise

    async def shutdown(self) -> None:
        errors = await self._shutdown_started()
        for error in errors:
            logger.exception(
                "Extension shutdown failed",
                exc_info=(type(error), error, error.__traceback__),
            )

    async def _shutdown_started(self) -> list[BaseException]:
        errors: list[BaseException] = []
        while self._started:
            _, hooks = self._started.pop()
            try:
                await hooks.shutdown(self._context)
            except BaseException as error:
                errors.append(error)
        return errors
