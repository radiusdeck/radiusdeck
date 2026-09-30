from pydantic import BaseModel, ConfigDict, Field


class ClientBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    ipaddr: str | None = None
    secret: str | None = None
    shortname: str | None = None
    extra_params: dict[str, str] = Field(default_factory=dict)


class ClientCreate(ClientBase):
    ipaddr: str
    secret: str


class ClientUpdate(ClientBase):
    pass
