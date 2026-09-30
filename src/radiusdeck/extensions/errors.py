from __future__ import annotations


class ExtensionError(RuntimeError):
    """Base error for extension discovery, validation, and lifecycle failures."""


class ExtensionDiscoveryError(ExtensionError):
    """Installed extension metadata could not be loaded safely."""


class ExtensionCompatibilityError(ExtensionError):
    """An extension targets an unsupported extension API."""


class ExtensionConflictError(ExtensionError):
    """Structural extension contributions conflict."""


class ExtensionConfigurationError(ExtensionError):
    """An extension-owned settings loader rejected its configuration."""


class ExtensionStartupError(ExtensionError):
    """An extension failed while creating its runtime state."""


class RoutePolicyError(ExtensionConflictError):
    """Registered routes and their authentication policies are inconsistent."""
