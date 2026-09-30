from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssignmentEditPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str | None = None
    key: str = Field(min_length=1)
    value: str = Field(default="")

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Assignment key must not be empty")
        return v


class BlockEditPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str | None = None
    kind: str = Field(min_length=1)
    name: str | None = None
    assignments: list[AssignmentEditPayload] = Field(default_factory=list)
    blocks: list["BlockEditPayload"] = Field(default_factory=list)

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Block kind must not be empty")
        return v


class ClientEditTreePayload(BaseModel):
    """
    Payload for editing an existing `client {}` with stable node ids.

    Root-level `assignments` represent extra assignments only (ipaddr/secret excluded).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    ipaddr: str = Field(min_length=1)
    secret: str | None = None

    assignments: list[AssignmentEditPayload] = Field(default_factory=list)
    blocks: list[BlockEditPayload] = Field(default_factory=list)

    @field_validator("secret", mode="before")
    @classmethod
    def blank_secret_preserves_existing(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value
