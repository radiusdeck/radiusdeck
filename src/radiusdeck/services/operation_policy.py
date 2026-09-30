"""Neutral authorization port for optional operations during extraction."""

from typing import Protocol


class OperationUnavailableError(Exception):
    def public_payload(self) -> dict[str, str]:
        return {"detail": "Operation unavailable"}


class OperationPolicy(Protocol):
    def is_enabled(self, operation: str) -> bool: ...

    def require(self, operation: str) -> None: ...


class DenyOptionalOperations:
    def is_enabled(self, operation: str) -> bool:
        return False

    def require(self, operation: str) -> None:
        raise OperationUnavailableError(operation)


class OperationPolicySlot:
    """Set once during extension startup, before any request can run."""

    def __init__(self) -> None:
        self._policy: OperationPolicy = DenyOptionalOperations()
        self._configured = False

    def configure(self, policy: OperationPolicy) -> None:
        if self._configured:
            raise ValueError("Optional operation policy already configured")
        self._policy = policy
        self._configured = True

    def is_enabled(self, operation: str) -> bool:
        return self._policy.is_enabled(operation)

    def require(self, operation: str) -> None:
        self._policy.require(operation)
