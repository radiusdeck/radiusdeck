from pathlib import Path

import pytest

from radiusdeck.repositories.file_diagnostics import FileDiagnostics


@pytest.mark.asyncio
async def test_file_diagnostics_inspects_file_without_modifying_it(
    tmp_path: Path,
) -> None:
    path = tmp_path / "clients.conf"
    original = "# unchanged\n"
    path.write_text(original, encoding="utf-8")

    result = await FileDiagnostics().inspect(path)

    assert result.exists is True
    assert result.is_file is True
    assert result.readable is True
    assert result.writable is True
    assert path.read_text(encoding="utf-8") == original


@pytest.mark.asyncio
async def test_file_diagnostics_reports_missing_file(tmp_path: Path) -> None:
    result = await FileDiagnostics().inspect(tmp_path / "missing.conf")

    assert result.exists is False
    assert result.is_file is False
    assert result.readable is False
    assert result.writable is False
