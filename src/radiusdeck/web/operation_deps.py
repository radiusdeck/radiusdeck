from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request

from radiusdeck.services.operation_policy import DenyOptionalOperations, OperationPolicy


def get_operation_policy(request: Request) -> OperationPolicy:
    policy: OperationPolicy = getattr(
        request.state,
        "operation_policy",
        getattr(request.app.state, "operation_policy", DenyOptionalOperations()),
    )
    return policy


OperationPolicyDep = Annotated[OperationPolicy, Depends(get_operation_policy)]


def require_operation(operation: str) -> Callable[..., None]:
    def dependency(policy: OperationPolicyDep) -> None:
        policy.require(operation)

    return dependency
