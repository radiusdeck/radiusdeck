from __future__ import annotations


class RadiusDomainError(Exception):
    """Base class for domain/service-layer errors."""


class ClientNotFoundError(RadiusDomainError):
    def __init__(self, name: str):
        super().__init__(f"Client not found: {name}")
        self.name = name


class InvalidClientUpsertError(RadiusDomainError):
    """Raised when an upsert would create an invalid client block."""


class MergeClientError(RadiusDomainError):
    """Generic merge/validation error."""


class InvalidNodeIdError(MergeClientError):
    """Raised when payload references unknown node_id."""


class DuplicateKeyError(MergeClientError):
    """Raised when merge results in duplicate keys inside a block."""
