#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
exec "$DEMO_RADIUS_BIN" -X -d "$DEMO_STATE/config" -D "$DEMO_DICTIONARY_DIR"
