# Extension interface

RadiusDeck exposes a neutral Python extension interface for separately installed
packages. The application remains responsible for process startup, base
services, middleware ordering, and shutdown.

## Discovery and compatibility

Extensions register one entry point in the `radiusdeck.extensions` group:

```toml
[project.entry-points."radiusdeck.extensions"]
example = "example_extension:extension"
```

The entry point must expose an `ExtensionDefinition`. Discovery sorts entries by
entry-point name, distribution name, and target, so construction order is
deterministic. Duplicate entry-point names or runtime extension names fail
startup.

`RADIUSDECK_EXTENSION_API = 1` is independent from the RadiusDeck package
version. An extension must declare the exact integer API version it implements;
an unsupported value fails before the application starts.

## Structural and runtime phases

The structural phase runs while `create_app()` assembles the application. It
may contribute routers, route policies, authentication providers, templates,
static mounts, navigation, status/configuration descriptors, and UI slots.
Structural contribution functions must not start background resources.

The runtime phase runs inside the application lifespan after base services are
ready. `startup()` receives an `ExtensionRuntimeContext` with base services,
loaded extension settings, and a runtime registry. Its return value is stored in
the registry. Hooks stop in reverse startup order. If startup fails, RadiusDeck
cleans up the failing hook and all hooks that already started.

## Settings

`settings_loader` returns an extension-owned settings object or `None`.
RadiusDeck passes that value to the extension's structural function and makes
the complete mapping available in the runtime context. Extension settings stay
outside the base `Settings` model.

## Authentication providers and route policies

An `AuthenticationProvider` has a stable `provider_id` and an asynchronous
`authenticate(request)` method. It returns one of:

- `not_applicable`, allowing another provider to try;
- `authenticated`, with a `CurrentUser`;
- `rejected`, with the response that must be returned.

A browser provider also implements `login()` and `logout()`. Router
contributions declare a `RoutePolicyContribution` for every route and method.
Policy collection rejects missing policies, conflicts, unknown provider IDs,
and unsafe CSRF exemptions.

## UI and templates

An extension can add template search paths, named static mounts, navigation
items, and `UIContribution` objects. Each UI contribution names a supported
slot, a template, deterministic order, an asynchronous availability function,
and an asynchronous context function. RadiusDeck evaluates availability per
request and renders only available contributions. IDs, navigation targets,
mount names, and slot ordering must be unique where the collector requires it.

## Status and configuration

`StatusContribution` and `ConfigurationContribution` reserve stable contributor
IDs and user-facing labels. Runtime hooks can use the supplied base services and
registry to attach the implementation. Duplicate IDs fail collection instead
of silently replacing another extension.

## Minimal extension

```python
from __future__ import annotations

from radiusdeck.extensions import (
    RADIUSDECK_EXTENSION_API,
    ExtensionDefinition,
    StructuralContributions,
)


def contributions(settings: object | None) -> StructuralContributions:
    return StructuralContributions()


extension = ExtensionDefinition(
    name="example",
    extension_api_version=RADIUSDECK_EXTENSION_API,
    settings_loader=None,
    structural_contributions=contributions,
    runtime_hooks=None,
)
```

The extension package declares its supported RadiusDeck package range in its
normal dependency metadata and declares the extension API value in code. Both
checks are required because package compatibility and interface compatibility
answer different questions.
