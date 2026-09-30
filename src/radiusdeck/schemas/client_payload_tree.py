from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssignmentPayload(BaseModel):
    key: str = Field(min_length=1)
    value: str = Field(default="")

    @field_validator("key")
    @classmethod
    def strip_key(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Assignment key must not be empty")
        return v


class BlockPayload(BaseModel):
    kind: str = Field(min_length=1)
    name: str | None = None
    assignments: list[AssignmentPayload] = Field(default_factory=list)
    blocks: list["BlockPayload"] = Field(default_factory=list)

    @field_validator("kind")
    @classmethod
    def strip_kind(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Block kind must not be empty")
        return v

    @model_validator(mode="after")
    def no_duplicate_keys_in_block(self) -> "BlockPayload":
        seen: set[str] = set()
        for a in self.assignments:
            if a.key in seen:
                raise ValueError(
                    f"Duplicate assignment key in block '{self.kind}': {a.key}"
                )
            seen.add(a.key)
        return self


class ClientCreateTreePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    ipaddr: str = Field(min_length=1)
    secret: str = Field(min_length=1)
    assignments: list[AssignmentPayload] = Field(default_factory=list)
    blocks: list[BlockPayload] = Field(default_factory=list)

    @field_validator("name", "ipaddr", "secret")
    @classmethod
    def strip_required(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field must not be empty")
        return v

    @model_validator(mode="after")
    def validate_root_assignments(self) -> "ClientCreateTreePayload":
        reserved = {"name", "ipaddr", "secret"}
        seen: set[str] = set()

        for a in self.assignments:
            if a.key in reserved:
                raise ValueError(
                    f"'{a.key}' is reserved and cannot be used as assignment key"
                )
            if a.key in seen:
                raise ValueError(f"Duplicate assignment key: {a.key}")
            seen.add(a.key)

        return self
