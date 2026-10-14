#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
export APP_ENV=development
export APP_AUTH_METHOD=none
export APP_RADIUS_CLIENTS_PATH="$DEMO_STATE/config/clients.conf"
export APP_BACKUP_DIR="$DEMO_STATE/backups"
export APP_BACKUP_ENABLED=true
export APP_SIDECAR_RELOAD_ENABLED=false
export APP_FREERADIUS_LOG_VIEWER_ENABLED=false
export APP_LOG_LEVEL=INFO
# An empty working directory prevents loading a repository .env file.
mkdir -p "$DEMO_STATE/work"
cd "$DEMO_STATE/work"
exec "$DEMO_PYTHON" -m radiusdeck.cli.main serve --host 127.0.0.1 --port 18080
