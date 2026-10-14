#!/usr/bin/env bash
# Shared by the demo launchers. Source this file from Bash.
DEMO_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export DEMO_STATE="${DEMO_STATE:-$DEMO_SCRIPT_DIR/.state}"
export DEMO_RADIUS_LIBDIR="${DEMO_RADIUS_LIBDIR:-/usr/lib/freeradius}"
DEMO_RADIUS_BIN="${DEMO_RADIUS_BIN:-freeradius}"
DEMO_DICTIONARY_DIR="${DEMO_DICTIONARY_DIR:-/usr/share/freeradius}"
DEMO_PYTHON="${DEMO_PYTHON:-$DEMO_SCRIPT_DIR/../../.venv/bin/python}"
if [[ "$DEMO_STATE" != /* ]]; then
    printf 'DEMO_STATE must be an absolute path.\n' >&2
    exit 1
fi
if [[ ! -f "$DEMO_STATE/config/radiusd.conf" ]]; then
    mkdir -p "$DEMO_STATE/config" "$DEMO_STATE/backups"
    cp "$DEMO_SCRIPT_DIR"/config/* "$DEMO_STATE/config/"
fi
