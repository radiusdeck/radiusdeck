from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Role = Literal["admin", "user"]
AuthMethod = str


@dataclass(frozen=True, slots=True)
class CurrentUser:
    username: str
    display_name: str
    role: Role
    auth_method: AuthMethod
