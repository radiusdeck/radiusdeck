from __future__ import annotations


class RadiusDomainError(Exception):
    """Base class for domain/service-layer errors."""


class ClientNotFoundError(RadiusDomainError):
    def __init__(self, name: str):
        super().__init__(f"Client not found: {name}")
        self.name = name


class ClientAlreadyExistsError(RadiusDomainError):
    def __init__(self, name: str):
        super().__init__(f"Client already exists: {name}")
        self.name = name


class InvalidClientAddressError(RadiusDomainError):
    """The client address would be rejected or misread by FreeRADIUS."""


class DuplicateClientAddressError(RadiusDomainError):
    def __init__(self, address: str, owner: str):
        super().__init__(f"Address {address} is already used by client {owner}.")
        self.address = address
        self.owner = owner


class InvalidClientUpsertError(RadiusDomainError):
    """Raised when an upsert would create an invalid client block."""


class MergeClientError(RadiusDomainError):
    """Generic merge/validation error."""


class InvalidNodeIdError(MergeClientError):
    """Raised when payload references unknown node_id."""


class DuplicateKeyError(MergeClientError):
    """Raised when merge results in duplicate keys inside a block."""
