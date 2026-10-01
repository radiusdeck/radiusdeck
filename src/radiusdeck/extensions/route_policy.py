from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from fastapi import APIRouter
from fastapi.routing import RouteContext, iter_route_contexts
from starlette.routing import BaseRoute, Match, Mount, Route
from starlette.types import Scope

from radiusdeck.extensions.contributions import (
    RoutePolicy,
    RoutePolicyContribution,
)
from radiusdeck.extensions.errors import RoutePolicyError

_PARAMETER_RE = re.compile(r"\{[^{}]+\}")


def normalize_route_path(path: str) -> str:
    return _PARAMETER_RE.sub("{}", path.rstrip("/") or "/")


def join_route_path(prefix: str, path: str) -> str:
    left = prefix.rstrip("/")
    right = path if path.startswith("/") else f"/{path}"
    return f"{left}{right}" or "/"


def policies_for_router(
    router: APIRouter,
    *,
    prefix: str,
    policy: RoutePolicy,
) -> tuple[RoutePolicyContribution, ...]:
    contributions: list[RoutePolicyContribution] = []
    for route in iter_route_contexts(router.routes):
        if not isinstance(route.original_route, Route):
            raise RoutePolicyError(
                "Unsupported route type in router contribution: "
                f"{type(route.original_route).__name__}"
            )
        path = route.path
        if not isinstance(path, str):
            raise RoutePolicyError(
                "Router contribution route has no path: "
                f"{type(route.original_route).__name__}"
            )
        methods = frozenset(route.methods or ())
        contributions.append(
            RoutePolicyContribution(
                path=join_route_path(prefix, path),
                methods=methods,
                policy=policy,
            )
        )
    return tuple(contributions)


def policies_for_routes(
    routes: Iterable[BaseRoute],
    *,
    policy: RoutePolicy,
) -> tuple[RoutePolicyContribution, ...]:
    contributions: list[RoutePolicyContribution] = []
    for route in iter_route_contexts(tuple(routes)):
        path = getattr(route, "path", None)
        if not isinstance(path, str):
            raise RoutePolicyError(
                f"Unsupported registered route type: {type(route).__name__}"
            )
        contributions.append(
            RoutePolicyContribution(
                path=path,
                methods=frozenset(_route_methods(route)),
                policy=policy,
            )
        )
    return tuple(contributions)


@dataclass(frozen=True)
class _Binding:
    route: RouteContext
    policies: dict[str, RoutePolicy]


class RoutePolicyRegistry:
    def __init__(self, bindings: tuple[_Binding, ...]) -> None:
        self._bindings = bindings

    def lookup(self, scope: Scope) -> RoutePolicy | None:
        method = str(scope.get("method", "GET")).upper()
        for binding in self._bindings:
            match, _ = binding.route.matches(scope)
            if match is not Match.FULL:
                continue
            return binding.policies.get(method) or binding.policies.get("*")
        return None


def build_route_policy_registry(
    routes: Iterable[BaseRoute],
    policies: tuple[RoutePolicyContribution, ...],
    *,
    authentication_provider_ids: frozenset[str],
) -> RoutePolicyRegistry:
    route_list = tuple(iter_route_contexts(tuple(routes)))
    route_identities: dict[tuple[str, str], tuple[RouteContext, str]] = {}
    route_methods: dict[int, set[str]] = {}
    route_paths: dict[int, str] = {}

    for route in route_list:
        path = getattr(route, "path", None)
        if not isinstance(path, str):
            raise RoutePolicyError(
                f"Registered route type is not supported: {type(route).__name__}"
            )
        methods = _route_methods(route)
        route_methods[id(route)] = methods
        route_paths[id(route)] = path
        normalized = normalize_route_path(path)
        for method in methods:
            key = (normalized, method)
            if key in route_identities:
                raise RoutePolicyError(
                    f"Duplicate registered route shape: {method} {normalized}"
                )
            route_identities[key] = (route, method)

    matches: dict[tuple[int, str], list[RoutePolicy]] = {}
    for contribution in policies:
        normalized = normalize_route_path(contribution.path)
        for method in contribution.methods:
            key = (normalized, method)
            identity = route_identities.get(key)
            if identity is None:
                raise RoutePolicyError(
                    f"Orphan route policy: {method} {contribution.path}"
                )
            route, route_method = identity
            matches.setdefault((id(route), route_method), []).append(
                contribution.policy
            )
            _validate_provider_references(
                contribution.policy,
                authentication_provider_ids,
                contribution.path,
            )

    bindings: list[_Binding] = []
    for route in route_list:
        compiled: dict[str, RoutePolicy] = {}
        path = route_paths[id(route)]
        for method in route_methods[id(route)]:
            candidates = matches.get((id(route), method), [])
            if len(candidates) != 1:
                reason = "unclassified" if not candidates else "contradictory"
                raise RoutePolicyError(f"Registered route is {reason}: {method} {path}")
            compiled[method] = candidates[0]
        bindings.append(_Binding(route=route, policies=compiled))

    return RoutePolicyRegistry(tuple(bindings))


def _route_methods(route: RouteContext) -> set[str]:
    if isinstance(route.original_route, Mount):
        return {"*"}
    if isinstance(route.original_route, Route):
        methods = route.methods
        if not methods:
            raise RoutePolicyError(
                f"Registered route has no HTTP methods: {route.path}"
            )
        return {method.upper() for method in methods}
    raise RoutePolicyError(
        "Registered route type is not supported: "
        f"{type(route.original_route).__name__}"
    )


def _validate_provider_references(
    policy: RoutePolicy,
    provider_ids: frozenset[str],
    path: str,
) -> None:
    referenced = set(policy.authentication_provider_ids) | set(
        policy.csrf_exempt_provider_ids
    )
    missing = referenced - provider_ids
    if missing:
        rendered = ", ".join(sorted(missing))
        raise RoutePolicyError(
            f"Route policy {path!r} references unknown auth providers: {rendered}"
        )
