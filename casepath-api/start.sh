#!/usr/bin/env bash
set -euo pipefail
export CASEPATH_DB_PATH="${CASEPATH_DB_PATH:-/tmp/casepath-api/casepath.db}"
mkdir -p "$(dirname "$CASEPATH_DB_PATH")"
exec uvicorn casepath_api.app:app --app-dir casepath-api --host 0.0.0.0 --port "${PORT:-10000}"
