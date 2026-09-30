# src/radiusdeck/web/router.py
from fastapi import APIRouter

from radiusdeck.web.endpoints import ui_backups, ui_clients, ui_logs, ui_status

# In the future add: from radiusdeck.web.endpoints import ui_dashboard

api_router = APIRouter()

# Include clients (paths will be available as /clients...)
api_router.include_router(ui_clients.router, tags=["clients"])
api_router.include_router(ui_logs.router, tags=["logs"])
api_router.include_router(ui_status.router, tags=["status"])
api_router.include_router(ui_backups.router, tags=["backups"])

# In the future:
# api_router.include_router(ui_dashboard.router, tags=["dashboard"])
