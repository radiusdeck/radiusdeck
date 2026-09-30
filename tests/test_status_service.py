from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from radiusdeck.core.config import Settings
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.repositories.file_diagnostics import (
    FileDiagnostics,
    FileDiagnosticsResult,
)
from radiusdeck.repositories.log_file_store import LogFileStore
from radiusdeck.services.log_service import LogService
from radiusdeck.services.status_models import StatusCheck, StatusLevel, StatusReport
from radiusdeck.services.status_ports import ProbeResult
from radiusdeck.services.status_service import StatusService


class FakeFileDiagnostics(FileDiagnostics):
    def __init__(self, results: dict[Path, FileDiagnosticsResult]) -> None:
        self._results = results

    async def inspect(self, path: Path) -> FileDiagnosticsResult:
        return self._results[path]


class FakeProbe:
    def __init__(self, result: ProbeResult) -> None:
        self._result = result

    async def check(self) -> ProbeResult:
        return self._result


def _settings(clients_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "RADIUS_CLIENTS_PATH": clients_path,
        "auth_method": "none",
        "freeradius_log_viewer_enabled": False,
        "SIDECAR_RELOAD_ENABLED": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def _diagnostics(
    *,
    exists: bool = True,
    readable: bool = True,
    writable: bool = True,
) -> FileDiagnosticsResult:
    return FileDiagnosticsResult(
        exists=exists,
        is_file=exists,
        readable=readable,
        writable=writable,
    )


def _service(
    settings: Settings,
    diagnostics: dict[Path, FileDiagnosticsResult],
    *,
    probe: FakeProbe | None = None,
) -> StatusService:
    log_store = LogFileStore(
        settings.freeradius_log_path, settings.freeradius_log_max_bytes
    )
    return StatusService(
        settings=settings,
        clients_store=ClientsConfStore(settings.RADIUS_CLIENTS_PATH),
        log_service=LogService(
            store=log_store,
            enabled=settings.freeradius_log_viewer_enabled,
            default_lines=settings.freeradius_log_default_lines,
        ),
        file_diagnostics=FakeFileDiagnostics(diagnostics),
        reload_probe=probe,
    )


def _check(report: StatusReport, check_id: str) -> StatusCheck:
    return next(
        check
        for section in report.sections
        for check in section.checks
        if check.id == check_id
    )


@pytest.mark.asyncio
async def test_open_auth_is_ok_and_disabled_reload_produces_warning(
    tmp_path: Path,
) -> None:
    clients_path = tmp_path / "clients.conf"
    clients_path.write_text("# empty\n", encoding="utf-8")
    settings = _settings(clients_path)

    report = await _service(settings, {clients_path: _diagnostics()}).build_report()

    assert _check(report, "security.auth_mode").level is StatusLevel.OK
    assert _check(report, "security.auth_mode").message == "Authentication mode: none."
    assert all(section.id != "edition" for section in report.sections)
    assert _check(report, "reload.enabled").level is StatusLevel.WARNING
    assert report.overall_level is StatusLevel.WARNING


@pytest.mark.asyncio
async def test_public_url_is_skipped_when_missing_in_open_mode(tmp_path: Path) -> None:
    clients_path = tmp_path / "clients.conf"
    clients_path.write_text("# empty\n", encoding="utf-8")
    settings = _settings(clients_path, public_url=None)

    report = await _service(settings, {clients_path: _diagnostics()}).build_report()

    assert _check(report, "app.public_url").level is StatusLevel.SKIPPED


@pytest.mark.asyncio
async def test_http_public_url_is_skipped_in_open_mode(tmp_path: Path) -> None:
    clients_path = tmp_path / "clients.conf"
    clients_path.write_text("# empty\n", encoding="utf-8")
    settings = _settings(clients_path, public_url="http://192.0.2.10:8000")

    report = await _service(settings, {clients_path: _diagnostics()}).build_report()

    assert _check(report, "app.public_url").level is StatusLevel.SKIPPED


@pytest.mark.asyncio
async def test_missing_clients_conf_produces_error(tmp_path: Path) -> None:
    clients_path = tmp_path / "missing.conf"
    settings = _settings(clients_path)

    report = await _service(
        settings,
        {clients_path: _diagnostics(exists=False, readable=False, writable=False)},
    ).build_report()

    assert _check(report, "clients.exists").level is StatusLevel.ERROR
    assert _check(report, "clients.parse").level is StatusLevel.SKIPPED
    assert report.overall_level is StatusLevel.ERROR


@pytest.mark.asyncio
async def test_non_writable_clients_conf_produces_error(tmp_path: Path) -> None:
    clients_path = tmp_path / "clients.conf"
    clients_path.write_text("# empty\n", encoding="utf-8")
    settings = _settings(clients_path)

    report = await _service(
        settings, {clients_path: _diagnostics(writable=False)}
    ).build_report()

    assert _check(report, "clients.writable").level is StatusLevel.ERROR


@pytest.mark.asyncio
async def test_disabled_log_viewer_skips_file_checks(tmp_path: Path) -> None:
    clients_path = tmp_path / "clients.conf"
    clients_path.write_text("# empty\n", encoding="utf-8")
    settings = _settings(clients_path)

    report = await _service(settings, {clients_path: _diagnostics()}).build_report()

    assert _check(report, "logs.enabled").level is StatusLevel.WARNING
    assert _check(report, "logs.exists").level is StatusLevel.SKIPPED
    assert _check(report, "logs.tail").level is StatusLevel.SKIPPED


@pytest.mark.asyncio
async def test_enabled_log_viewer_with_missing_file_produces_error(
    tmp_path: Path,
) -> None:
    clients_path = tmp_path / "clients.conf"
    clients_path.write_text("# empty\n", encoding="utf-8")
    log_path = tmp_path / "missing.log"
    settings = _settings(
        clients_path,
        freeradius_log_viewer_enabled=True,
        freeradius_log_path=log_path,
    )

    report = await _service(
        settings,
        {
            clients_path: _diagnostics(),
            log_path: _diagnostics(exists=False, readable=False, writable=False),
        },
    ).build_report()

    assert _check(report, "logs.exists").level is StatusLevel.ERROR
    assert _check(report, "logs.tail").level is StatusLevel.SKIPPED
    assert report.overall_level is StatusLevel.ERROR


@pytest.mark.asyncio
async def test_report_does_not_display_container_log_path(tmp_path: Path) -> None:
    clients_path = tmp_path / "clients.conf"
    clients_path.write_text("# empty\n", encoding="utf-8")
    log_path = Path("/var/log/freeradius/radius.log")
    settings = _settings(
        clients_path,
        freeradius_log_viewer_enabled=True,
        freeradius_log_path=log_path,
    )

    report = await _service(
        settings,
        {
            clients_path: _diagnostics(),
            log_path: _diagnostics(exists=False, readable=False, writable=False),
        },
    ).build_report()

    assert str(log_path) not in repr(report)


@pytest.mark.asyncio
async def test_report_does_not_display_container_clients_path(tmp_path: Path) -> None:
    clients_path = Path("/data/clients.conf")
    settings = _settings(clients_path)

    report = await _service(
        settings,
        {
            clients_path: _diagnostics(exists=False, readable=False, writable=False),
        },
    ).build_report()

    assert str(clients_path) not in repr(report)


@pytest.mark.asyncio
async def test_reload_probe_failure_produces_error(tmp_path: Path) -> None:
    clients_path = tmp_path / "clients.conf"
    clients_path.write_text("# empty\n", encoding="utf-8")
    settings = _settings(
        clients_path,
        SIDECAR_RELOAD_ENABLED=True,
        SIDECAR_RELOAD_URL="http://sidecar:9090/reload",
        SIDECAR_HEALTH_URL="http://sidecar:9090/health",
        SIDECAR_RELOAD_TOKEN=SecretStr("configured-token"),
    )

    report = await _service(
        settings,
        {clients_path: _diagnostics()},
        probe=FakeProbe(ProbeResult(True, False, "Sidecar is unavailable.")),
    ).build_report()

    assert _check(report, "reload.reachable").level is StatusLevel.ERROR


@pytest.mark.asyncio
async def test_report_does_not_contain_secret_values(tmp_path: Path) -> None:
    clients_path = tmp_path / "clients.conf"
    clients_path.write_text("# empty\n", encoding="utf-8")
    settings = _settings(
        clients_path,
        session_secret_key=SecretStr("super-secret-session-key"),
        SIDECAR_RELOAD_ENABLED=True,
        SIDECAR_RELOAD_URL="http://sidecar:9090/reload",
        SIDECAR_HEALTH_URL="http://sidecar:9090/health",
        SIDECAR_RELOAD_TOKEN=SecretStr("super-secret-reload-token"),
        oidc_client_secret=SecretStr("super-secret-oidc-client-secret"),
    )

    report = await _service(
        settings,
        {clients_path: _diagnostics()},
        probe=FakeProbe(ProbeResult(True, True, "Sidecar is healthy.")),
    ).build_report()
    report_text = repr(report)

    assert "super-secret-session-key" not in report_text
    assert "super-secret-reload-token" not in report_text
    assert "super-secret-oidc-client-secret" not in report_text
