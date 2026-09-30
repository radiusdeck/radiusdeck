from __future__ import annotations

from typing import cast

import pytest
from fastapi import FastAPI

from radiusdeck.extensions import (
    RADIUSDECK_EXTENSION_API,
    ExtensionDefinition,
    StructuralContributions,
)
from radiusdeck.extensions.runtime import (
    BaseRuntimeServices,
    ExtensionRuntimeContext,
    ExtensionRuntimeManager,
    ExtensionRuntimeRegistry,
)
from radiusdeck.extensions.validation import collect_contributions
from radiusdeck.main import lifespan


class _Hooks:
    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        startup_error: Exception | None = None,
        shutdown_error: Exception | None = None,
    ) -> None:
        self.name = name
        self.events = events
        self.startup_error = startup_error
        self.shutdown_error = shutdown_error

    async def startup(self, _context: ExtensionRuntimeContext) -> object | None:
        self.events.append(f"start:{self.name}")
        if self.startup_error is not None:
            raise self.startup_error
        return self.name

    async def shutdown(self, _context: ExtensionRuntimeContext) -> None:
        self.events.append(f"stop:{self.name}")
        if self.shutdown_error is not None:
            raise self.shutdown_error


def _definition(name: str, hooks: _Hooks) -> ExtensionDefinition:
    return ExtensionDefinition(
        name=name,
        extension_api_version=RADIUSDECK_EXTENSION_API,
        structural_contributions=lambda _settings: StructuralContributions(),
        runtime_hooks=lambda: hooks,
    )


def _context() -> ExtensionRuntimeContext:
    return ExtensionRuntimeContext(
        services=cast(BaseRuntimeServices, object()),
        registry=ExtensionRuntimeRegistry(),
    )


@pytest.mark.asyncio
async def test_runtime_hooks_start_in_order_and_stop_in_reverse() -> None:
    events: list[str] = []
    manager = ExtensionRuntimeManager(
        (
            _definition("first", _Hooks("first", events)),
            _definition("second", _Hooks("second", events)),
        ),
        _context(),
    )

    await manager.startup()
    await manager.shutdown()

    assert events == ["start:first", "start:second", "stop:second", "stop:first"]


@pytest.mark.asyncio
async def test_partial_startup_cleanup_preserves_original_error() -> None:
    events: list[str] = []
    original = RuntimeError("startup failed")
    manager = ExtensionRuntimeManager(
        (
            _definition(
                "first",
                _Hooks(
                    "first",
                    events,
                    shutdown_error=RuntimeError("first cleanup failed"),
                ),
            ),
            _definition(
                "second",
                _Hooks(
                    "second",
                    events,
                    startup_error=original,
                    shutdown_error=RuntimeError("second cleanup failed"),
                ),
            ),
        ),
        _context(),
    )

    with pytest.raises(RuntimeError, match="startup failed") as raised:
        await manager.startup()

    assert raised.value is original
    assert events == ["start:first", "start:second", "stop:second", "stop:first"]
    notes = getattr(raised.value, "__notes__", [])
    assert any("second cleanup failed" in note for note in notes)
    assert any("first cleanup failed" in note for note in notes)


@pytest.mark.asyncio
async def test_lifespan_closes_base_resources_after_extension_startup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    definition = _definition(
        "broken",
        _Hooks("broken", events, startup_error=RuntimeError("startup failed")),
    )

    class FakeResources:
        def __init__(self) -> None:
            self.services = cast(BaseRuntimeServices, object())
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    resources = FakeResources()

    async def fake_create_resources(
        _app: FastAPI, _contributions: object
    ) -> FakeResources:
        return resources

    monkeypatch.setattr("radiusdeck.main._create_base_resources", fake_create_resources)
    app = FastAPI()
    app.state.extension_definitions = (definition,)
    app.state.extension_contributions = collect_contributions((definition,))

    with pytest.raises(RuntimeError, match="startup failed"):
        async with lifespan(app):
            pytest.fail("lifespan yielded after failed extension startup")

    assert resources.closed is True
    assert events == ["start:broken", "stop:broken"]
