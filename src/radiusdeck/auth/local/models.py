from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from radiusdeck.auth.models import Role

LOCAL_USERS_FILE_VERSION = 1


class LocalUserRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: str = Field(min_length=1)
    role: Role
    password_hash: str = Field(min_length=1)
    disabled: bool = False

    @field_validator("username", "password_hash")
    @classmethod
    def validate_required_string(cls, v: str) -> str:
        if not v:
            raise ValueError("Field must not be empty")
        return v


class LocalUsersFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = LOCAL_USERS_FILE_VERSION
    users: list[LocalUserRecord] = Field(default_factory=list)

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: int) -> int:
        if v != LOCAL_USERS_FILE_VERSION:
            raise ValueError(
                f"Unsupported local users file version: {v}. "
                f"Expected {LOCAL_USERS_FILE_VERSION}"
            )
        return v

    @model_validator(mode="after")
    def validate_unique_usernames(self) -> "LocalUsersFile":
        seen: set[str] = set()
        for user in self.users:
            if user.username in seen:
                raise ValueError(f"Duplicate local username: {user.username}")
            seen.add(user.username)
        return self
