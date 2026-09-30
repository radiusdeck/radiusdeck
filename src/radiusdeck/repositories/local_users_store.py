from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Protocol

import aiofiles

from radiusdeck.auth.local.models import LocalUsersFile


class LocalUsersCodec(Protocol):
    def loads(self, data: str) -> LocalUsersFile: ...

    def dumps(self, data: LocalUsersFile) -> str: ...


class JsonLocalUsersCodec:
    def loads(self, data: str) -> LocalUsersFile:
        return LocalUsersFile.model_validate_json(data)

    def dumps(self, data: LocalUsersFile) -> str:
        return json.dumps(data.model_dump(mode="json"), indent=2) + "\n"


class LocalUsersStore:
    def __init__(
        self,
        path: Path | str,
        *,
        codec: LocalUsersCodec | None = None,
    ) -> None:
        self.path = Path(path)
        self.codec = codec or JsonLocalUsersCodec()
        self._lock: asyncio.Lock = asyncio.Lock()

    @asynccontextmanager
    async def locked(self) -> AsyncIterator[None]:
        async with self._lock:
            yield

    async def load(self) -> LocalUsersFile:
        async with aiofiles.open(self.path, "r", encoding="utf-8") as f:
            return self.codec.loads(await f.read())

    async def save(self, data: LocalUsersFile) -> None:
        async with aiofiles.open(self.path, "w", encoding="utf-8") as f:
            await f.write(self.codec.dumps(data))
