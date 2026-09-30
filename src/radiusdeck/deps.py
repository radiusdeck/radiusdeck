# src/radiusdeck/deps.py

from fastapi import Request

from radiusdeck.services.backup_service import BackupService
from radiusdeck.services.local_auth_service import LocalAuthService
from radiusdeck.services.log_service import LogService
from radiusdeck.services.radius_service import RadiusService
from radiusdeck.services.status_service import StatusService


def get_radius_service(request: Request) -> RadiusService:
    service: RadiusService = request.app.state.radius_service
    return service


def get_backup_service(request: Request) -> BackupService:
    service: BackupService = request.app.state.backup_service
    return service


def get_log_service(request: Request) -> LogService:
    service: LogService = request.app.state.log_service
    return service


def get_status_service(request: Request) -> StatusService:
    service: StatusService = request.app.state.status_service
    return service


def get_local_auth_service(request: Request) -> LocalAuthService:
    service = getattr(request.app.state, "local_auth_service", None)
    if not isinstance(service, LocalAuthService):
        raise RuntimeError("LocalAuthService is not configured")
    return service
