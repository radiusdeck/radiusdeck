from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import aiofiles


@dataclass(frozen=True)
class FileDiagnosticsResult:
    exists: bool
    is_file: bool
    readable: bool
    writable: bool
    error: str | None = None


@dataclass(frozen=True)
class DirectoryDiagnosticsResult:
    exists: bool
    is_directory: bool
    readable: bool
    writable: bool


class FileDiagnostics:
    async def inspect(self, path: Path) -> FileDiagnosticsResult:
        try:
            await asyncio.to_thread(path.stat)
        except FileNotFoundError:
            return FileDiagnosticsResult(
                exists=False,
                is_file=False,
                readable=False,
                writable=False,
            )
        except OSError as exc:
            return FileDiagnosticsResult(
                exists=False,
                is_file=False,
                readable=False,
                writable=False,
                error=self._safe_error(exc),
            )

        is_file = await asyncio.to_thread(path.is_file)
        readable = await self._can_open(path, "r") if is_file else False
        writable = await self._can_open(path, "r+") if is_file else False
        return FileDiagnosticsResult(
            exists=True,
            is_file=is_file,
            readable=readable,
            writable=writable,
        )

    async def inspect_directory(self, path: Path) -> DirectoryDiagnosticsResult:
        exists, is_directory, readable, writable = await asyncio.to_thread(
            self._inspect_directory_sync, path
        )
        return DirectoryDiagnosticsResult(
            exists=exists,
            is_directory=is_directory,
            readable=readable,
            writable=writable,
        )

    @staticmethod
    def _inspect_directory_sync(path: Path) -> tuple[bool, bool, bool, bool]:
        exists = path.exists()
        is_directory = path.is_dir() if exists else False
        return (
            exists,
            is_directory,
            is_directory and os.access(path, os.R_OK | os.X_OK),
            is_directory and os.access(path, os.W_OK | os.X_OK),
        )

    @staticmethod
    async def _can_open(path: Path, mode: Literal["r", "r+"]) -> bool:
        try:
            async with aiofiles.open(path, mode, encoding="utf-8"):
                return True
        except (OSError, UnicodeError):
            return False

    @staticmethod
    def _safe_error(exc: OSError) -> str:
        return exc.strerror or exc.__class__.__name__
