from __future__ import annotations

import os
from pathlib import Path

import pytest

from radiusdeck.repositories.log_file_store import LogFileStore
from radiusdeck.services.log_models import (
    LogFileNotFoundError,
    LogFilePermissionError,
)


@pytest.mark.asyncio
async def test_tail_returns_last_requested_lines(tmp_path: Path) -> None:
    log_path = tmp_path / "radius.log"
    log_path.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")
    store = LogFileStore(log_path, max_bytes=1024)

    lines, truncated = await store.tail(2)

    assert lines == ["line 2", "line 3"]
    assert truncated is False


@pytest.mark.asyncio
async def test_tail_returns_fewer_lines_when_file_has_fewer(tmp_path: Path) -> None:
    log_path = tmp_path / "radius.log"
    log_path.write_text("line 1\nline 2\n", encoding="utf-8")
    store = LogFileStore(log_path, max_bytes=1024)

    lines, truncated = await store.tail(10)

    assert lines == ["line 1", "line 2"]
    assert truncated is False


@pytest.mark.asyncio
async def test_tail_empty_file_returns_empty_list(tmp_path: Path) -> None:
    log_path = tmp_path / "radius.log"
    log_path.write_text("", encoding="utf-8")
    store = LogFileStore(log_path, max_bytes=1024)

    lines, truncated = await store.tail(10)

    assert lines == []
    assert truncated is False


@pytest.mark.asyncio
async def test_tail_large_file_reads_max_window_and_marks_truncated(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "radius.log"
    log_path.write_text(
        "prefix line outside window\nline 1\nline 2\nline 3\n",
        encoding="utf-8",
    )
    store = LogFileStore(log_path, max_bytes=len("line 2\nline 3\n"))

    lines, truncated = await store.tail(2)

    assert lines == ["line 2", "line 3"]
    assert truncated is True


@pytest.mark.asyncio
async def test_tail_invalid_utf8_replaces_invalid_bytes(tmp_path: Path) -> None:
    log_path = tmp_path / "radius.log"
    log_path.write_bytes(b"ok\nbad \xff line\n")
    store = LogFileStore(log_path, max_bytes=1024)

    lines, truncated = await store.tail(2)

    assert lines == ["ok", "bad \ufffd line"]
    assert truncated is False


@pytest.mark.asyncio
async def test_tail_missing_file_maps_to_log_file_not_found(tmp_path: Path) -> None:
    store = LogFileStore(tmp_path / "missing.log", max_bytes=1024)

    with pytest.raises(LogFileNotFoundError):
        await store.tail(10)


@pytest.mark.asyncio
async def test_tail_permission_denied_maps_to_log_file_permission_error(
    tmp_path: Path,
) -> None:
    if os.name == "nt":
        pytest.skip("chmod permission behavior is platform-specific on Windows")

    log_path = tmp_path / "radius.log"
    log_path.write_text("line 1\n", encoding="utf-8")
    log_path.chmod(0)
    try:
        store = LogFileStore(log_path, max_bytes=1024)
        if os.access(log_path, os.R_OK):
            pytest.skip("test process can still read chmod 000 file")

        with pytest.raises(LogFilePermissionError):
            await store.tail(10)
    finally:
        log_path.chmod(0o600)
