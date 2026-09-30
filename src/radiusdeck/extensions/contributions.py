from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import Response

from radiusdeck.auth.models import CurrentUser


class RouteAccess(StrEnum):
    PUBLIC = "public"
    PROTECTED_BROWSER = "protected_browser"
    PROTECTED_API = "protected_api"


@dataclass(frozen=True)
class RoutePolicy:
    access: RouteAccess
    authentication_provider_ids: tuple[str, ...] = ()
    csrf_protected: bool = True
    csrf_exempt_provider_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.access is not RouteAccess.PROTECTED_API and (
            self.authentication_provider_ids or self.csrf_exempt_provider_ids
        ):
            raise ValueError("Authentication providers are valid only for API routes")
        unknown_exemptions = set(self.csrf_exempt_provider_ids) - set(
            self.authentication_provider_ids
        )
        if unknown_exemptions:
            raise ValueError(
                "CSRF exemptions must reference an API authentication provider"
            )


@dataclass(frozen=True)
class RoutePolicyContribution:
    path: str
    methods: frozenset[str]
    policy: RoutePolicy

    def __post_init__(self) -> None:
        if not self.path.startswith("/"):
            raise ValueError("Route policy paths must be absolute")
        if not self.methods:
            raise ValueError("Route policy methods must not be empty")
        object.__setattr__(
            self,
            "methods",
            frozenset(method.upper() for method in self.methods),
        )


@dataclass(frozen=True)
class RouterContribution:
    router: APIRouter
    policies: tuple[RoutePolicyContribution, ...]
    prefix: str = ""
    tags: tuple[str, ...] = ()


class AuthenticationDisposition(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    AUTHENTICATED = "authenticated"
    REJECTED = "rejected"


@dataclass(frozen=True)
class AuthenticationResult:
    disposition: AuthenticationDisposition
    user: CurrentUser | None = None
    response: Response | None = None

    def __post_init__(self) -> None:
        if self.disposition is AuthenticationDisposition.AUTHENTICATED:
            if self.user is None or self.response is not None:
                raise ValueError("Authenticated result requires exactly one user")
        elif self.disposition is AuthenticationDisposition.REJECTED:
            if self.response is None or self.user is not None:
                raise ValueError("Rejected result requires exactly one response")
        elif self.user is not None or self.response is not None:
            raise ValueError("Not-applicable result cannot contain user or response")

    @classmethod
    def not_applicable(cls) -> "AuthenticationResult":
        return cls(AuthenticationDisposition.NOT_APPLICABLE)

    @classmethod
    def authenticated(cls, user: CurrentUser) -> "AuthenticationResult":
        return cls(AuthenticationDisposition.AUTHENTICATED, user=user)

    @classmethod
    def rejected(cls, response: Response) -> "AuthenticationResult":
        return cls(AuthenticationDisposition.REJECTED, response=response)


class AuthenticationProvider(Protocol):
    provider_id: str

    async def authenticate(self, request: Request) -> AuthenticationResult: ...


class BrowserAuthenticationProvider(AuthenticationProvider, Protocol):
    async def login(self, request: Request) -> Response: ...

    async def logout(self, request: Request) -> Response: ...


@dataclass(frozen=True)
class StaticMountContribution:
    path: str
    directory: Path
    name: str


@dataclass(frozen=True)
class NavigationItem:
    item_id: str
    label: str
    href: str
    order: int = 100


@dataclass(frozen=True)
class StatusContribution:
    contributor_id: str
    label: str


@dataclass(frozen=True)
class ConfigurationContribution:
    contributor_id: str
    label: str


@dataclass(frozen=True)
class UIContribution:
    contribution_id: str
    slot: str
    template: str
    available: Callable[[Request], Awaitable[bool]]
    context: Callable[[Request], Awaitable[Mapping[str, object]]]
    order: int = 100


@dataclass(frozen=True)
class StructuralContributions:
    ui_contributions: tuple[UIContribution, ...] = ()
    routers: tuple[RouterContribution, ...] = ()
    authentication_providers: tuple[AuthenticationProvider, ...] = ()
    template_search_paths: tuple[Path, ...] = ()
    static_mounts: tuple[StaticMountContribution, ...] = ()
    navigation_items: tuple[NavigationItem, ...] = ()
    status_contributors: tuple[StatusContribution, ...] = ()
    configuration_contributors: tuple[ConfigurationContribution, ...] = ()
    preserve_external_backup_history: bool = False
    browser_authentication: BrowserAuthenticationProvider | None = None


@dataclass(frozen=True)
class CollectedContributions:
    routers: tuple[RouterContribution, ...]
    authentication_providers: tuple[AuthenticationProvider, ...]
    template_search_paths: tuple[Path, ...]
    static_mounts: tuple[StaticMountContribution, ...]
    navigation_items: tuple[NavigationItem, ...]
    status_contributors: tuple[StatusContribution, ...]
    configuration_contributors: tuple[ConfigurationContribution, ...]
    preserve_external_backup_history: bool
    extension_names: tuple[str, ...] = field(default=())
    browser_authentication: BrowserAuthenticationProvider | None = None
    extension_settings: Mapping[str, object | None] = field(default_factory=dict)
    ui_contributions: tuple[UIContribution, ...] = ()
