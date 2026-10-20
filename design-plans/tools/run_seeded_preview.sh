#!/bin/bash
# Provider-free preview of the nine deterministic reference histories (v1 then v2, with
# knowledge qualification and reuse). Copies the main workspace database into
# .runtime/preview-$PORT, stages the runs there and serves it on 127.0.0.1:$PORT.
# Never writes the main data root and never touches the server on 4173.
# Prerequisite: ./bin/casepath prepare, and one sealed ./bin/casepath dev start so a
# source capsule for the current manifest exists. Usage: PORT=4180 design-plans/tools/run_seeded_preview.sh
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd); PORT=${PORT:-4180}; W=${SEED_W:-$ROOT/.runtime/preview-$PORT}
R=$ROOT/.runtime/casepath-dev-v2; PY=$R/venv/bin/python
CAP=${CAP_DIR:-$(ls -td "$R"/source-capsules/*/ | head -1)}; CAP=${CAP%/}
rm -rf "$W"; mkdir -p "$W/data" "$W/home" "$W/tmp"
"$PY" -c "import sqlite3,sys; s=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close()" "$ROOT/.runtime/casepath-data-v1/casepath.db" "$W/data/casepath.db"
[ -e "$ROOT/.runtime/casepath-data-v1/artifact-registry" ] && cp -r "$ROOT/.runtime/casepath-data-v1/artifact-registry" "$W/data/"
(cd "$ROOT/casepath-api" && "$PY" "$ROOT/design-plans/tools/stage_reference_nine.py" "$W/data" clm_0f4f13b1e3e1328c,clm_2c55cdd816b1d0e8,clm_314f2d309fea25e6,clm_393285577dcb12c4,clm_4a07dbbbd859a3ce,clm_4a53299cfe619303,clm_543f08f2415b2a33,clm_7dbd7c7d1c4ddf90,clm_95d08975bc575592)
exec env -i HOME="$W/home" TMPDIR="$W/tmp" LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=UTC PATH=/usr/bin:/bin PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 \
  CASEPATH_MODEL_MODE=deterministic_reference CASEPATH_SOURCE_COMMIT="$(git -C "$ROOT" rev-parse HEAD)" \
  CASEPATH_DB_PATH="$W/data/casepath.db" CASEPATH_ARTIFACT_REGISTRY_PATH="$W/data/artifact-registry" CASEPATH_LOCAL_STATIC_ROOT="$CAP/casepath-public" \
  LANGSMITH_TRACING=false LANGCHAIN_TRACING=false LANGCHAIN_TRACING_V2=false \
  "$PY" -I -B -P -m uvicorn casepath_api.app:app --app-dir "${APP_DIR:-$CAP/casepath-api}" --host 127.0.0.1 --port "$PORT" --no-access-log
