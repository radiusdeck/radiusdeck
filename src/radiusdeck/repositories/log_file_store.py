from __future__ import annotations

import asyncio
from pathlib import Path

import aiofiles

from radiusdeck.services.log_models import (
    LogFileNotFoundError,
    LogFilePermissionError,
    LogReadError,
)


class LogFileStore:
    def __init__(self, path: Path, max_bytes: int) -> None:
        self._path = path
        self._max_bytes = max_bytes

    @property
    def path(self) -> Path:
        return self._path

    async def tail(self, line_count: int) -> tuple[list[str], bool]:
        try:
            file_size = (await asyncio.to_thread(self._path.stat)).st_size
            offset = max(file_size - self._max_bytes, 0)
            truncated = offset > 0

            async with aiofiles.open(self._path, "rb") as f:
                await f.seek(offset)
                data = await f.read()
        except FileNotFoundError as e:
            raise LogFileNotFoundError(str(self._path)) from e
        except PermissionError as e:
            raise LogFilePermissionError(str(self._path)) from e
        except OSError as e:
            raise LogReadError(str(e)) from e

        if line_count <= 0:
            return [], truncated

        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        return lines[-line_count:], truncated
