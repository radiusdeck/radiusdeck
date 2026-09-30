from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from radiusdeck.extensions import (
    RADIUSDECK_EXTENSION_API,
    ExtensionDefinition,
    StructuralContributions,
)
from radiusdeck.extensions.errors import (
    ExtensionCompatibilityError,
    ExtensionDiscoveryError,
)
from radiusdeck.extensions.loader import discover_extensions


def _extension(
    name: str, api_version: Any = RADIUSDECK_EXTENSION_API
) -> ExtensionDefinition:
    return ExtensionDefinition(
        name=name,
        extension_api_version=api_version,
        structural_contributions=lambda _settings: StructuralContributions(),
    )


@dataclass(frozen=True)
class _Distribution:
    name: str


class _EntryPoint:
    def __init__(
        self,
        name: str,
        value: str,
        candidate: object,
        *,
        distribution: str = "test-dist",
        error: Exception | None = None,
    ) -> None:
        self.name = name
        self.value = value
        self.dist = _Distribution(distribution)
        self._candidate = candidate
        self._error = error
        self.load_calls = 0

    def load(self) -> object:
        self.load_calls += 1
        if self._error is not None:
            raise self._error
        return self._candidate


def test_zero_extensions_is_valid() -> None:
    assert discover_extensions(()) == ()


def test_duplicate_entry_point_names_fail_before_any_load() -> None:
    first = _EntryPoint("duplicate", "one:extension", _extension("one"))
    second = _EntryPoint("duplicate", "two:extension", _extension("two"))

    with pytest.raises(ExtensionDiscoveryError, match="Duplicate .*entry-point"):
        discover_extensions((first, second))  # type: ignore[arg-type]

    assert first.load_calls == 0
    assert second.load_calls == 0


def test_extensions_load_in_deterministic_metadata_order() -> None:
    loaded_order: list[str] = []

    class RecordingEntryPoint(_EntryPoint):
        def load(self) -> object:
            loaded_order.append(self.name)
            return super().load()

    zulu = RecordingEntryPoint("zulu", "z:extension", _extension("zulu"))
    alpha = RecordingEntryPoint("alpha", "a:extension", _extension("alpha"))

    result = discover_extensions((zulu, alpha))  # type: ignore[arg-type]

    assert loaded_order == ["alpha", "zulu"]
    assert [extension.name for extension in result] == ["alpha", "zulu"]


@pytest.mark.parametrize("api_version", [True, 1.0, 0, 2])
def test_extension_api_requires_exact_integer_one(api_version: object) -> None:
    entry_point = _EntryPoint(
        "bad-version",
        "bad:extension",
        _extension("bad-version", api_version),
    )

    with pytest.raises(ExtensionCompatibilityError, match="supports exactly 1"):
        discover_extensions((entry_point,))  # type: ignore[arg-type]


def test_malformed_or_broken_installed_extension_fails_clearly() -> None:
    malformed = _EntryPoint("malformed", "bad:value", object())
    with pytest.raises(ExtensionDiscoveryError, match="did not expose"):
        discover_extensions((malformed,))  # type: ignore[arg-type]

    broken = _EntryPoint(
        "broken",
        "broken:value",
        object(),
        error=ImportError("boom"),
    )
    with pytest.raises(ExtensionDiscoveryError, match="Failed to load"):
        discover_extensions((broken,))  # type: ignore[arg-type]


def test_duplicate_runtime_extension_names_fail() -> None:
    first = _EntryPoint("first", "one:value", _extension("same"))
    second = _EntryPoint("second", "two:value", _extension("same"))

    with pytest.raises(ExtensionDiscoveryError, match="Duplicate runtime"):
        discover_extensions((first, second))  # type: ignore[arg-type]
