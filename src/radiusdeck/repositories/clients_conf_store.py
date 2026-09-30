# src/radiusdeck/repositories/clients_conf_store.py
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import aiofiles

from radiusdeck.lib.fr_parser import parse_clients_conf, render_clients_conf
from radiusdeck.lib.fr_parser.ast import AstNodes


@dataclass(frozen=True)
class ClientsConfSnapshot:
    content: str
    nodes: AstNodes


class ClientsConfStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._lock: asyncio.Lock = asyncio.Lock()

    @asynccontextmanager
    async def locked(self) -> AsyncIterator[None]:
        async with self._lock:
            yield

    async def load(self) -> AstNodes:
        return (await self.load_snapshot()).nodes

    async def load_snapshot(self) -> ClientsConfSnapshot:
        content = await self.read_content()
        return ClientsConfSnapshot(content=content, nodes=parse_clients_conf(content))

    async def read_content(self) -> str:
        async with aiofiles.open(self.path, "r", encoding="utf-8") as f:
            return await f.read()

    async def save(self, nodes: AstNodes) -> None:
        await self.save_content(render_clients_conf(nodes))

    async def save_content(self, content: str) -> None:
        async with aiofiles.open(self.path, "w", encoding="utf-8") as f:
            await f.write(content)
