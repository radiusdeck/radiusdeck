from __future__ import annotations

from importlib import metadata
from typing import Iterable

from radiusdeck.extensions.api import (
    RADIUSDECK_EXTENSION_API,
    ExtensionDefinition,
)
from radiusdeck.extensions.errors import (
    ExtensionCompatibilityError,
    ExtensionDiscoveryError,
)

EXTENSION_ENTRY_POINT_GROUP = "radiusdeck.extensions"


def _distribution_name(entry_point: metadata.EntryPoint) -> str:
    distribution = getattr(entry_point, "dist", None)
    name = getattr(distribution, "name", "")
    return str(name or "")


def discover_extensions(
    entry_points: Iterable[metadata.EntryPoint] | None = None,
) -> tuple[ExtensionDefinition, ...]:
    discovered = list(
        metadata.entry_points(group=EXTENSION_ENTRY_POINT_GROUP)
        if entry_points is None
        else entry_points
    )

    names: set[str] = set()
    duplicates: set[str] = set()
    for entry_point in discovered:
        if entry_point.name in names:
            duplicates.add(entry_point.name)
        names.add(entry_point.name)
    if duplicates:
        rendered = ", ".join(sorted(duplicates))
        raise ExtensionDiscoveryError(
            f"Duplicate {EXTENSION_ENTRY_POINT_GROUP} entry-point names: {rendered}"
        )

    ordered = sorted(
        discovered,
        key=lambda item: (item.name, _distribution_name(item), item.value),
    )
    loaded: list[ExtensionDefinition] = []
    runtime_names: set[str] = set()
    for entry_point in ordered:
        try:
            candidate = entry_point.load()
        except Exception as exc:
            raise ExtensionDiscoveryError(
                f"Failed to load extension entry point {entry_point.name!r}"
            ) from exc
        if not isinstance(candidate, ExtensionDefinition):
            raise ExtensionDiscoveryError(
                f"Extension entry point {entry_point.name!r} did not expose "
                "ExtensionDefinition"
            )
        if (
            type(candidate.extension_api_version) is not int
            or candidate.extension_api_version != RADIUSDECK_EXTENSION_API
        ):
            raise ExtensionCompatibilityError(
                f"Extension {candidate.name!r} requires API "
                f"{candidate.extension_api_version}; base supports exactly "
                f"{RADIUSDECK_EXTENSION_API}"
            )
        if candidate.name in runtime_names:
            raise ExtensionDiscoveryError(
                f"Duplicate runtime extension name: {candidate.name}"
            )
        runtime_names.add(candidate.name)
        loaded.append(candidate)
    return tuple(loaded)
