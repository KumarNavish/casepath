#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
qa_directory="$repository_root/casepath-qa"
qa_output="$qa_directory/guided-v13-smoke-out"
qa_tmp_root="${TMPDIR:-/tmp}"
qa_tmp_root="${qa_tmp_root%/}"
preflight_tmp="$(mktemp -d "$qa_tmp_root/casepath-qa-preflight.XXXXXX")"
preflight_output="$preflight_tmp/evidence"
insurance_parent="$(mktemp -d "$qa_tmp_root/casepath-insurance-qa-real.XXXXXX")"
insurance_output="$insurance_parent/evidence"
python_environment="$preflight_tmp/python"
web_log="$preflight_tmp/frontend.log"
api_log="$preflight_tmp/api.log"
web_port="4173"
api_port="8000"
python_command="${CASEPATH_QA_PYTHON:-python}"
web_pid=""
api_pid=""
playwright_executable="${PLAYWRIGHT_EXECUTABLE_PATH:-/Applications/ego lite.app/Contents/MacOS/ego lite}"
macos_text_encoding="$(printf '0x%X:0x0:0x0' "$(/usr/bin/id -u)")"

path_must_be_safe() {
  local candidate="$1"
  [[ -n "$candidate" && "$candidate" != "/" && "$candidate" == "$qa_tmp_root"/* ]]
}

if ! path_must_be_safe "$preflight_tmp" || [[ "$preflight_tmp" != "$qa_tmp_root"/casepath-qa-preflight.* ]]; then
  printf 'Unsafe deterministic preflight directory: %s\n' "$preflight_tmp" >&2
  exit 2
fi
if ! path_must_be_safe "$preflight_output" || ! path_must_be_safe "$insurance_parent" || ! path_must_be_safe "$insurance_output" || ! path_must_be_safe "$python_environment"; then
  printf 'Unsafe deterministic preflight child path.\n' >&2
  exit 2
fi
if [[ "$qa_output" != "$repository_root"/casepath-qa/guided-v13-smoke-out ]]; then
  printf 'Unexpected production QA evidence path: %s\n' "$qa_output" >&2
  exit 2
fi

terminate_process() {
  local process_id="$1"
  if [[ -n "$process_id" ]] && kill -0 "$process_id" 2>/dev/null; then
    kill "$process_id" 2>/dev/null || true
    wait "$process_id" 2>/dev/null || true
  fi
}

cleanup() {
  terminate_process "$api_pid"
  terminate_process "$web_pid"
  case "$preflight_tmp" in
    "$qa_tmp_root"/casepath-qa-preflight.*) rm -rf -- "$preflight_tmp" ;;
    *) printf 'Refusing to remove unexpected preflight path: %s\n' "$preflight_tmp" >&2 ;;
  esac
  case "$insurance_parent" in
    "$qa_tmp_root"/casepath-insurance-qa-real.*) rm -rf -- "$insurance_parent" ;;
    *) printf 'Refusing to remove unexpected insurance path: %s\n' "$insurance_parent" >&2 ;;
  esac
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

fail_with_log() {
  local label="$1"
  local log_path="$2"
  printf '%s failed to become ready.\n' "$label" >&2
  if [[ -f "$log_path" ]]; then
    tail -n 80 "$log_path" >&2
  fi
  return 1
}

wait_for_http() {
  local url="$1"
  local process_id="$2"
  local label="$3"
  local log_path="$4"
  local attempt
  for ((attempt = 0; attempt < 240; attempt += 1)); do
    if ! kill -0 "$process_id" 2>/dev/null; then
      fail_with_log "$label" "$log_path"
      return 1
    fi
    if "$python_environment/bin/python" -c \
      'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=1).read()' \
      "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  fail_with_log "$label" "$log_path"
}

if [[ ! "${RENDER_GIT_COMMIT:-}" =~ ^[0-9a-fA-F]{40}$ ]]; then
  printf 'RENDER_GIT_COMMIT must be the exact 40-character QA source commit.\n' >&2
  exit 2
fi
if [[ "${CASEPATH_ALLOW_PRODUCTION_MUTATION:-}" != "1" ]]; then
  printf 'CASEPATH_ALLOW_PRODUCTION_MUTATION=1 is required for the hosted production phase.\n' >&2
  exit 2
fi
if ! command -v "$python_command" >/dev/null 2>&1; then
  printf 'Pinned QA Python executable is unavailable: %s\n' "$python_command" >&2
  exit 2
fi
if [[ ! -x "$playwright_executable" ]]; then
  printf 'Governed ego lite browser executable is unavailable: %s\n' "$playwright_executable" >&2
  exit 2
fi
"$python_command" - <<'PY'
import sys

expected = (3, 13, 9)
if sys.version_info[:3] != expected:
    raise SystemExit(
        f"QA Python must be {'.'.join(map(str, expected))}; got {sys.version.split()[0]}"
    )
PY

cd "$repository_root"
"$python_command" casepath/tools/build_static_site.py --require-known-commit
"$python_command" -m venv "$python_environment"
"$python_environment/bin/python" -m pip install \
  --disable-pip-version-check \
  --no-cache-dir \
  --requirement casepath-api/requirements.lock

export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1786406400}"
"$python_environment/bin/python" casepath-api/generate_artifacts.py
"$python_environment/bin/python" casepath-api/replace_photographic_evidence.py .
for required_artifact in \
  lease-agreement.pdf \
  notification-email.eml \
  management-reply.eml \
  defect-timeline.pdf \
  delivery-receipt.pdf \
  bedroom-corner-2026-07-27.jpg \
  later-claim-email.eml \
  later-lease-agreement.pdf \
  later-notification-email.eml \
  later-management-reply.eml \
  window-replacement-notice.pdf \
  window-corner-2026-08-08.jpg \
  IMAGE_PROVENANCE.json; do
  test -s "$repository_root/casepath-api/artifacts/$required_artifact"
done

"$python_command" -m http.server "$web_port" \
  --bind 127.0.0.1 \
  --directory "$repository_root/casepath-public" \
  >"$web_log" 2>&1 &
web_pid="$!"

(
  unset OPENROUTER_API_KEY CASEPATH_AGENT_RUNTIME_PROFILE CASEPATH_SOURCE_COMMIT
  export CASEPATH_MODEL_MODE=deterministic_reference
  export CASEPATH_DB_PATH="$preflight_tmp/preflight.db"
  export LANGSMITH_TRACING=false
  exec "$python_environment/bin/python" -m uvicorn casepath_api.app:app \
    --app-dir casepath-api \
    --host 127.0.0.1 \
    --port "$api_port"
) >"$api_log" 2>&1 &
api_pid="$!"

wait_for_http "http://127.0.0.1:$web_port/deployment.json" "$web_pid" "deterministic frontend" "$web_log"
wait_for_http "http://127.0.0.1:$api_port/readyz" "$api_pid" "deterministic API" "$api_log"

printf 'Running mandatory zero-provider full-browser preflight.\n'
(
  cd "$qa_directory"
  exec env -i \
  HOME="$HOME" \
  LANG=C.UTF-8 \
  LC_ALL=C.UTF-8 \
  PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  TMPDIR="$qa_tmp_root" \
  TZ=UTC \
  __CF_USER_TEXT_ENCODING="$macos_text_encoding" \
  CASEPATH_QA_OUT="$preflight_output" \
  CASEPATH_EXPECTED_SOURCE_COMMIT="$RENDER_GIT_COMMIT" \
  CASEPATH_ALLOW_PRODUCTION_MUTATION=0 \
  CASEPATH_QA_API_BOOT_RECEIPT="${CASEPATH_QA_API_BOOT_RECEIPT:-}" \
  CASEPATH_QA_SERVICE_ROOT="${CASEPATH_QA_SERVICE_ROOT:-}" \
  PLAYWRIGHT_EXECUTABLE_PATH="$playwright_executable" \
  BASE_URL="http://127.0.0.1:$web_port" \
  API_URL="http://127.0.0.1:$api_port" \
  /usr/local/bin/node browser-focused-v20.mjs
)

"$python_environment/bin/python" casepath/tools/casepath_release.py \
  verify-runtime-causal-evidence \
  --report "$preflight_output/report.json" \
  --evidence-manifest "$preflight_output/evidence-manifest.json"

printf 'Insurance protocol gate is topology-separated from this retained split-origin legacy/hosted runner; run it only against ./bin/casepath dev with an explicit CASEPATH_QA_RUN_ID.\n'

"$python_environment/bin/python" - "$preflight_output/report.json" "http://127.0.0.1:$api_port/api/model-ledger" <<'PY'
import json
import sys
import urllib.request
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert report["status"] == "passed", report.get("error")
assert report["failed"] == 0, report.get("checks")

with urllib.request.urlopen(sys.argv[2], timeout=5) as response:
    ledger = json.load(response)
summary = ledger["summary"]
assert summary["records"] == 0, summary
assert summary["network_calls"] == 0, summary
assert summary["actual_cost_usd"] == 0, summary
assert ledger["items"] == [], ledger["items"]
print("Mandatory deterministic browser preflight passed with zero provider calls.")
PY

terminate_process "$api_pid"
api_pid=""
terminate_process "$web_pid"
web_pid=""

printf 'Deterministic preflight cleared; starting the one authorized production journey.\n'
(
  cd "$qa_directory"
  CASEPATH_QA_OUT="$qa_output" \
  BASE_URL=https://casepath.kumarnavish.chatgpt.site \
  API_URL=https://casepath-agentic-api.onrender.com \
  node browser-guided-v13-smoke.mjs
)

"$python_environment/bin/python" casepath/tools/casepath_release.py \
  verify-runtime-evidence \
  --report "$qa_output/report.json" \
  --evidence-manifest "$qa_output/evidence-manifest.json"
