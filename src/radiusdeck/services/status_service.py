from __future__ import annotations

import os
import platform
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path

from radiusdeck.core.config import Settings
from radiusdeck.core.startup_warnings import is_development_secret
from radiusdeck.repositories.clients_conf_store import ClientsConfStore
from radiusdeck.repositories.file_diagnostics import (
    FileDiagnostics,
    FileDiagnosticsResult,
)
from radiusdeck.services.backup_models import BackupError
from radiusdeck.services.backup_service import BackupService
from radiusdeck.services.log_models import LogViewerError
from radiusdeck.services.log_service import LogService
from radiusdeck.services.status_models import (
    StatusCheck,
    StatusLevel,
    StatusReport,
    StatusSection,
    overall_status,
)
from radiusdeck.services.status_ports import StatusProbePort


class StatusService:
    def __init__(
        self,
        *,
        settings: Settings,
        clients_store: ClientsConfStore,
        log_service: LogService,
        file_diagnostics: FileDiagnostics,
        reload_probe: StatusProbePort | None = None,
        app_version: str | None = None,
        backup_service: BackupService | None = None,
    ) -> None:
        self._settings = settings
        self._clients_store = clients_store
        self._log_service = log_service
        self._file_diagnostics = file_diagnostics
        self._reload_probe = reload_probe
        self._app_version = app_version
        self._backup_service = backup_service
        self._contributors: list[Callable[[], Awaitable[StatusSection]]] = []

    def add_contributor(
        self, contributor: Callable[[], Awaitable[StatusSection]]
    ) -> None:
        self._contributors.append(contributor)

    async def build_report(self) -> StatusReport:
        clients_path = Path(self._clients_store.path)
        clients_diagnostics = await self._file_diagnostics.inspect(clients_path)
        log_diagnostics = (
            await self._file_diagnostics.inspect(self._settings.freeradius_log_path)
            if self._settings.freeradius_log_viewer_enabled
            else None
        )

        sections = [
            *[await contributor() for contributor in self._contributors],
            self._application_section(),
            self._security_section(),
            await self._clients_section(clients_path, clients_diagnostics),
            await self._logs_section(log_diagnostics),
            *(
                [await self._backups_section()]
                if self._backup_service is not None
                else []
            ),
            await self._reload_section(),
            self._runtime_section(),
        ]
        return StatusReport(
            overall_level=overall_status(sections),
            sections=sections,
            metadata={
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "python_version": platform.python_version(),
                "app_version": self._app_version or "unknown",
            },
        )

    async def _backups_section(self) -> StatusSection:
        backup_service = self._backup_service
        if backup_service is None:
            raise RuntimeError("Backup status requested without a backup service")
        if not backup_service.enabled:
            return StatusSection(
                id="backups",
                title="Backups",
                checks=[
                    StatusCheck(
                        id="backups.enabled",
                        label="Automatic backups",
                        level=StatusLevel.WARNING,
                        message=(
                            "Backups are disabled. Client editing remains available "
                            "without recovery points."
                        ),
                        remediation="Set APP_BACKUP_ENABLED=true to enable backups.",
                    ),
                    *[
                        self._skipped(check_id, label, "Backups are disabled.")
                        for check_id, label in (
                            ("backups.path", "Backup path"),
                            ("backups.exists", "Backup directory exists"),
                            ("backups.writable", "Backup directory writable"),
                            ("backups.retention", "Retention policy"),
                            ("backups.latest", "Latest backup"),
                        )
                    ],
                ],
            )

        store = backup_service.store
        diagnostics = await self._file_diagnostics.inspect_directory(store.directory)
        exists_ok = diagnostics.exists and diagnostics.is_directory
        checks = [
            StatusCheck(
                id="backups.enabled",
                label="Automatic backups",
                level=StatusLevel.OK,
                message="Automatic pre-change backups are enabled.",
            ),
            StatusCheck(
                id="backups.path",
                label="Backup path",
                level=StatusLevel.OK,
                message="The backup directory path is configured.",
            ),
            self._file_check(
                "backups.exists",
                "Backup directory exists",
                exists_ok,
                "The backup directory exists.",
                "The backup directory is missing or is not a directory.",
                "Check APP_BACKUP_DIR and its volume mount.",
            ),
            self._file_check(
                "backups.writable",
                "Backup directory writable",
                diagnostics.writable,
                "The backup directory is writable.",
                "The backup directory is not writable.",
                "Check the backup directory ownership and permissions.",
            ),
            StatusCheck(
                id="backups.retention",
                label="Retention policy",
                level=StatusLevel.OK,
                message=(
                    f"Keep {store.retention_count} backups"
                    + (
                        f" for at most {store.max_age_days} days."
                        if store.max_age_days is not None
                        else "."
                    )
                ),
            ),
        ]

        if not exists_ok or not diagnostics.readable:
            latest = self._skipped(
                "backups.latest",
                "Latest backup",
                "The latest backup check was skipped because storage is unavailable.",
            )
        else:
            try:
                latest_entry = await backup_service.get_latest_recovery_point()
            except BackupError:
                latest = StatusCheck(
                    id="backups.latest",
                    label="Latest backup",
                    level=StatusLevel.ERROR,
                    message="The latest backup is corrupt or cannot be read.",
                    remediation="Inspect the backup volume and backup metadata.",
                )
            else:
                latest = (
                    StatusCheck(
                        id="backups.latest",
                        label="Latest backup",
                        level=StatusLevel.OK,
                        message="The latest backup passed integrity verification.",
                    )
                    if latest_entry is not None
                    else self._skipped(
                        "backups.latest",
                        "Latest backup",
                        "No backups have been created yet.",
                    )
                )
        checks.append(latest)
        return StatusSection(id="backups", title="Backups", checks=checks)

    def _application_section(self) -> StatusSection:
        version_check = StatusCheck(
            id="app.version",
            label="Application version",
            level=StatusLevel.OK if self._app_version else StatusLevel.WARNING,
            message=(
                f"RadiusDeck version: {self._app_version}"
                if self._app_version
                else "RadiusDeck version is not available."
            ),
        )

        public_url = (
            str(self._settings.public_url)
            if self._settings.public_url is not None
            else None
        )
        if public_url is None:
            public_url_check = StatusCheck(
                id="app.public_url",
                label="Public URL",
                level=(
                    StatusLevel.SKIPPED
                    if self._settings.auth_method == "none"
                    else StatusLevel.WARNING
                ),
                message=(
                    "APP_PUBLIC_URL is not required in open mode."
                    if self._settings.auth_method == "none"
                    else "APP_PUBLIC_URL is not configured."
                ),
                remediation=(
                    None
                    if self._settings.auth_method == "none"
                    else "Set APP_PUBLIC_URL to the externally reachable URL."
                ),
            )
        elif public_url.lower().startswith("https://"):
            public_url_check = StatusCheck(
                id="app.public_url",
                label="Public URL",
                level=StatusLevel.OK,
                message="The public URL uses HTTPS.",
                details=public_url,
            )
        else:
            public_url_check = StatusCheck(
                id="app.public_url",
                label="Public URL",
                level=(
                    StatusLevel.WARNING
                    if self._settings.auth_method != "none"
                    else StatusLevel.SKIPPED
                ),
                message=(
                    "The public URL uses HTTP, which is allowed in open mode."
                    if self._settings.auth_method == "none"
                    else "The public URL uses HTTP."
                ),
                details=public_url,
                remediation=(
                    "Use HTTPS before exposing an authenticated deployment."
                    if self._settings.auth_method != "none"
                    else None
                ),
            )

        return StatusSection(
            id="application",
            title="Application",
            checks=[version_check, public_url_check],
        )

    def _security_section(self) -> StatusSection:
        auth_enabled = self._settings.auth_method != "none"
        auth_check = StatusCheck(
            id="security.auth_mode",
            label="Authentication mode",
            level=StatusLevel.OK,
            message=f"Authentication mode: {self._settings.auth_method}.",
        )

        secret = self._settings.session_secret_key
        if not auth_enabled and secret is None:
            secret_check = StatusCheck(
                id="security.session_secret",
                label="Session secret",
                level=StatusLevel.SKIPPED,
                message="A session secret is not required in open mode.",
            )
        elif secret is None:
            secret_check = StatusCheck(
                id="security.session_secret",
                label="Session secret",
                level=StatusLevel.ERROR,
                message="The session secret is missing.",
                remediation="Set APP_SESSION_SECRET_KEY to a long random value.",
            )
        elif is_development_secret(secret.get_secret_value()):
            secret_check = StatusCheck(
                id="security.session_secret",
                label="Session secret",
                level=StatusLevel.WARNING,
                message="The session secret appears to use a development value.",
                remediation="Replace APP_SESSION_SECRET_KEY with a long random value.",
            )
        else:
            secret_check = StatusCheck(
                id="security.session_secret",
                label="Session secret",
                level=StatusLevel.OK,
                message="A session secret is configured.",
            )

        public_url = (
            str(self._settings.public_url).lower()
            if self._settings.public_url is not None
            else None
        )
        uses_https = public_url is not None and public_url.startswith("https://")
        if uses_https:
            https_check = StatusCheck(
                id="security.https",
                label="HTTPS readiness",
                level=StatusLevel.OK,
                message="APP_PUBLIC_URL uses HTTPS.",
            )
        elif auth_enabled:
            https_check = StatusCheck(
                id="security.https",
                label="HTTPS readiness",
                level=StatusLevel.WARNING,
                message="Authenticated deployments should use HTTPS.",
                remediation="Set APP_PUBLIC_URL to the external HTTPS URL.",
            )
        else:
            https_check = StatusCheck(
                id="security.https",
                label="HTTPS readiness",
                level=StatusLevel.SKIPPED,
                message="HTTPS readiness is not enforced in open mode.",
            )

        if uses_https and not self._settings.effective_secure_cookies:
            cookie_check = StatusCheck(
                id="security.secure_cookies",
                label="Secure cookies",
                level=StatusLevel.WARNING,
                message="Secure cookies are disabled for an HTTPS public URL.",
                remediation="Enable APP_SECURE_COOKIES or remove its false override.",
            )
        elif uses_https:
            cookie_check = StatusCheck(
                id="security.secure_cookies",
                label="Secure cookies",
                level=StatusLevel.OK,
                message="Secure cookies are enabled.",
            )
        elif auth_enabled:
            cookie_check = StatusCheck(
                id="security.secure_cookies",
                label="Secure cookies",
                level=StatusLevel.WARNING,
                message="Secure session cookies require an HTTPS public URL.",
                remediation="Configure APP_PUBLIC_URL with an HTTPS URL.",
            )
        else:
            cookie_check = StatusCheck(
                id="security.secure_cookies",
                label="Secure cookies",
                level=StatusLevel.SKIPPED,
                message="Session cookies are not used in open mode.",
            )

        return StatusSection(
            id="security",
            title="Security",
            checks=[auth_check, secret_check, https_check, cookie_check],
        )

    async def _clients_section(
        self, path: Path, diagnostics: FileDiagnosticsResult
    ) -> StatusSection:
        checks = [
            StatusCheck(
                id="clients.path",
                label="Configuration path",
                level=StatusLevel.OK,
                message="The clients.conf path is configured.",
            ),
            self._file_check(
                "clients.exists",
                "Configuration file exists",
                diagnostics.exists and diagnostics.is_file,
                "clients.conf exists and is a file.",
                "clients.conf is missing or is not a regular file.",
                "Check APP_RADIUS_CLIENTS_PATH and the Docker volume mount.",
            ),
            self._file_check(
                "clients.readable",
                "Configuration file readable",
                diagnostics.readable,
                "clients.conf is readable.",
                "clients.conf cannot be read by the application process.",
                "Check the mounted file ownership and read permissions.",
            ),
            self._file_check(
                "clients.writable",
                "Configuration file writable",
                diagnostics.writable,
                "clients.conf is writable.",
                "clients.conf cannot be written by the application process.",
                "Check the mounted file ownership and write permissions.",
            ),
        ]

        if diagnostics.readable and diagnostics.is_file:
            try:
                await self._clients_store.load()
            except (OSError, UnicodeError, ValueError):
                parse_check = StatusCheck(
                    id="clients.parse",
                    label="Configuration parses",
                    level=StatusLevel.ERROR,
                    message="clients.conf could not be parsed.",
                    remediation="Validate the FreeRADIUS client configuration syntax.",
                )
            else:
                parse_check = StatusCheck(
                    id="clients.parse",
                    label="Configuration parses",
                    level=StatusLevel.OK,
                    message="clients.conf parses successfully.",
                )
        else:
            parse_check = StatusCheck(
                id="clients.parse",
                label="Configuration parses",
                level=StatusLevel.SKIPPED,
                message="Parsing was skipped because clients.conf is not readable.",
            )
        checks.append(parse_check)

        return StatusSection(
            id="configuration",
            title="Configuration file",
            checks=checks,
        )

    async def _logs_section(
        self, diagnostics: FileDiagnosticsResult | None
    ) -> StatusSection:
        if not self._settings.freeradius_log_viewer_enabled:
            skipped = StatusCheck(
                id="logs.enabled",
                label="Log viewer enabled",
                level=StatusLevel.WARNING,
                message="The FreeRADIUS log viewer is disabled.",
                remediation="Set APP_FREERADIUS_LOG_VIEWER_ENABLED=true to enable it.",
            )
            return StatusSection(
                id="logs",
                title="FreeRADIUS logs",
                checks=[
                    skipped,
                    *[
                        StatusCheck(
                            id=check_id,
                            label=label,
                            level=StatusLevel.SKIPPED,
                            message="The check was skipped because the log viewer is disabled.",
                        )
                        for check_id, label in (
                            ("logs.path", "Log path"),
                            ("logs.exists", "Log file exists"),
                            ("logs.readable", "Log file readable"),
                            ("logs.tail", "Log tail read"),
                        )
                    ],
                ],
            )

        if diagnostics is None:
            raise RuntimeError("Log status requested without file diagnostics")
        checks = [
            StatusCheck(
                id="logs.enabled",
                label="Log viewer enabled",
                level=StatusLevel.OK,
                message="The FreeRADIUS log viewer is enabled.",
            ),
            StatusCheck(
                id="logs.path",
                label="Log path",
                level=StatusLevel.OK,
                message="The FreeRADIUS log path is configured.",
            ),
            self._file_check(
                "logs.exists",
                "Log file exists",
                diagnostics.exists and diagnostics.is_file,
                "The FreeRADIUS log file exists.",
                "The FreeRADIUS log file is missing or is not a regular file.",
                "Check APP_FREERADIUS_LOG_PATH and the read-only volume mount.",
            ),
            self._file_check(
                "logs.readable",
                "Log file readable",
                diagnostics.readable,
                "The FreeRADIUS log file is readable.",
                "The FreeRADIUS log file cannot be read.",
                "Check the log file ownership and read permissions.",
            ),
        ]

        if diagnostics.readable and diagnostics.is_file:
            try:
                await self._log_service.tail(lines=1)
            except LogViewerError:
                tail_check = StatusCheck(
                    id="logs.tail",
                    label="Log tail read",
                    level=StatusLevel.ERROR,
                    message="The log tail check failed.",
                    remediation="Check the configured log path and volume permissions.",
                )
            else:
                tail_check = StatusCheck(
                    id="logs.tail",
                    label="Log tail read",
                    level=StatusLevel.OK,
                    message="The log file can be tailed.",
                )
        else:
            tail_check = StatusCheck(
                id="logs.tail",
                label="Log tail read",
                level=StatusLevel.SKIPPED,
                message="The tail check was skipped because the log file is not readable.",
            )
        checks.append(tail_check)
        return StatusSection(id="logs", title="FreeRADIUS logs", checks=checks)

    async def _reload_section(self) -> StatusSection:
        if not self._settings.SIDECAR_RELOAD_ENABLED:
            return StatusSection(
                id="reload",
                title="Reload integration",
                checks=[
                    StatusCheck(
                        id="reload.enabled",
                        label="Automatic reload",
                        level=StatusLevel.WARNING,
                        message=(
                            "Reload sidecar is disabled. Configuration changes will not "
                            "reload FreeRADIUS automatically."
                        ),
                        remediation="Enable APP_SIDECAR_RELOAD_ENABLED if required.",
                    ),
                    self._skipped("reload.url", "Reload URL", "Reload is disabled."),
                    self._skipped(
                        "reload.token", "Reload token", "Reload is disabled."
                    ),
                    self._skipped(
                        "reload.reachable", "Sidecar reachable", "Reload is disabled."
                    ),
                ],
            )

        url_check = StatusCheck(
            id="reload.url",
            label="Reload URL",
            level=(
                StatusLevel.OK
                if self._settings.SIDECAR_RELOAD_URL is not None
                else StatusLevel.ERROR
            ),
            message=(
                "The reload URL is configured."
                if self._settings.SIDECAR_RELOAD_URL is not None
                else "The reload URL is missing."
            ),
            remediation=(
                None
                if self._settings.SIDECAR_RELOAD_URL is not None
                else "Set APP_SIDECAR_RELOAD_URL."
            ),
        )
        token_check = StatusCheck(
            id="reload.token",
            label="Reload token",
            level=(
                StatusLevel.OK
                if self._settings.SIDECAR_RELOAD_TOKEN is not None
                else StatusLevel.WARNING
            ),
            message=(
                "A reload token is configured."
                if self._settings.SIDECAR_RELOAD_TOKEN is not None
                else "No reload token is configured."
            ),
            remediation=(
                None
                if self._settings.SIDECAR_RELOAD_TOKEN is not None
                else "Configure APP_SIDECAR_RELOAD_TOKEN when sidecar auth is enabled."
            ),
        )

        if self._settings.SIDECAR_HEALTH_URL is None:
            reachable_check = StatusCheck(
                id="reload.reachable",
                label="Sidecar reachable",
                level=StatusLevel.WARNING,
                message="No reload sidecar health URL is configured.",
                remediation="Set APP_SIDECAR_HEALTH_URL to the sidecar health endpoint.",
            )
        elif self._reload_probe is None:
            reachable_check = self._skipped(
                "reload.reachable",
                "Sidecar reachable",
                "The reload sidecar health probe is unavailable.",
            )
        else:
            result = await self._reload_probe.check()
            reachable_check = StatusCheck(
                id="reload.reachable",
                label="Sidecar reachable",
                level=(
                    StatusLevel.OK
                    if result.healthy
                    else StatusLevel.ERROR if result.available else StatusLevel.SKIPPED
                ),
                message=result.message,
                remediation=(
                    None
                    if result.healthy
                    else "Check the sidecar URL, network, health endpoint, and token."
                ),
            )

        return StatusSection(
            id="reload",
            title="Reload integration",
            checks=[
                StatusCheck(
                    id="reload.enabled",
                    label="Automatic reload",
                    level=StatusLevel.OK,
                    message="Reload sidecar integration is enabled.",
                ),
                url_check,
                token_check,
                reachable_check,
            ],
        )

    def _runtime_section(self) -> StatusSection:
        if hasattr(os, "geteuid"):
            is_root = os.geteuid() == 0
            user_check = StatusCheck(
                id="runtime.user",
                label="Process user",
                level=StatusLevel.WARNING if is_root else StatusLevel.OK,
                message=(
                    "RadiusDeck is running as root."
                    if is_root
                    else f"RadiusDeck is running as UID {os.geteuid()}."
                ),
                remediation=(
                    "Run the application as a non-root user." if is_root else None
                ),
            )
        else:
            user_check = self._skipped(
                "runtime.user",
                "Process user",
                "Process user checks are unavailable on this platform.",
            )

        return StatusSection(
            id="runtime",
            title="Runtime",
            checks=[
                user_check,
                StatusCheck(
                    id="runtime.python_version",
                    label="Python version",
                    level=StatusLevel.OK,
                    message=f"Python version: {platform.python_version()}.",
                ),
            ],
        )

    @staticmethod
    def _file_check(
        check_id: str,
        label: str,
        passed: bool,
        success_message: str,
        error_message: str,
        remediation: str,
    ) -> StatusCheck:
        return StatusCheck(
            id=check_id,
            label=label,
            level=StatusLevel.OK if passed else StatusLevel.ERROR,
            message=success_message if passed else error_message,
            remediation=None if passed else remediation,
        )

    @staticmethod
    def _skipped(check_id: str, label: str, message: str) -> StatusCheck:
        return StatusCheck(
            id=check_id,
            label=label,
            level=StatusLevel.SKIPPED,
            message=message,
        )
