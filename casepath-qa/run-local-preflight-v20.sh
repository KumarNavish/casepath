#!/usr/bin/env bash
set -euo pipefail

# Zero-provider desktop preflight for the currently served authored frontend.
# The wrapper never starts, stops, or mutates a hosted service. It intentionally
# fails if either endpoint is non-local, the served assets are stale, or the API
# is not a fresh deterministic-reference instance.

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
qa_directory="$repository_root/casepath-qa"
frontend_url="${CASEPATH_LOCAL_FRONTEND_URL:-http://localhost:4173}"
api_url="${CASEPATH_LOCAL_API_URL:-http://127.0.0.1:8002}"
qa_tmp_root="${TMPDIR:-/tmp}"
qa_tmp_root="${qa_tmp_root%/}"
preflight_root="$(mktemp -d "$qa_tmp_root/casepath-qa-preflight.XXXXXX")"
preflight_output="$preflight_root/evidence"
insurance_parent="$(mktemp -d "$qa_tmp_root/casepath-insurance-qa-real.XXXXXX")"
insurance_output="$insurance_parent/evidence"
browser_log="$preflight_root/browser.log"
insurance_browser_log="$preflight_root/insurance-browser.log"
verifier_log="$preflight_root/verifier.log"
frontend_log="$preflight_root/frontend.log"
api_log="$preflight_root/api.log"
frontend_pid=""
api_pid=""
passed="0"
insurance_gate_ran="0"
playwright_executable="${PLAYWRIGHT_EXECUTABLE_PATH:-/Applications/ego lite.app/Contents/MacOS/ego lite}"
macos_text_encoding="$(printf '0x%X:0x0:0x0' "$(/usr/bin/id -u)")"

if [[ -n "${CASEPATH_QA_PYTHON:-}" ]]; then
  python_command="$CASEPATH_QA_PYTHON"
elif [[ -x /private/tmp/casepath-langchain-venv/bin/python ]]; then
  python_command="/private/tmp/casepath-langchain-venv/bin/python"
else
  printf 'CASEPATH LOCAL PREFLIGHT: FAIL\n' >&2
  printf 'Pinned QA Python is unavailable. Set CASEPATH_QA_PYTHON to the Python 3.13.9 environment installed from casepath-api/requirements.lock.\n' >&2
  exit 2
fi

finish() {
  local exit_code="$?"
  terminate_process "$api_pid"
  terminate_process "$frontend_pid"
  if [[ "$exit_code" -eq 0 && "$passed" == "1" ]]; then
    printf '\nCASEPATH LOCAL PREFLIGHT: PASS\n'
    printf 'Evidence: %s\n' "$preflight_output"
    if [[ "$insurance_gate_ran" == "1" ]]; then
      printf 'Insurance evidence: %s\n' "$insurance_output"
    else
      printf 'Insurance gate: separate same-origin ./bin/casepath dev validation required\n'
    fi
    printf 'Browser log: %s\n' "$browser_log"
    printf 'Insurance browser log: %s\n' "$insurance_browser_log"
    printf 'Verifier log: %s\n' "$verifier_log"
  else
    printf '\nCASEPATH LOCAL PREFLIGHT: FAIL\n' >&2
    printf 'Diagnostics: %s\n' "$preflight_root" >&2
    printf 'Insurance diagnostics: %s\n' "$insurance_parent" >&2
  fi
}
trap finish EXIT

terminate_process() {
  local process_id="$1"
  if [[ -n "$process_id" ]] && kill -0 "$process_id" 2>/dev/null; then
    kill "$process_id" 2>/dev/null || true
    wait "$process_id" 2>/dev/null || true
  fi
}

fail_with_log() {
  local message="$1"
  local log_path="${2:-}"
  printf '%s\n' "$message" >&2
  if [[ -n "$log_path" && -f "$log_path" ]]; then
    tail -n 120 "$log_path" >&2
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
      fail_with_log "$label stopped before becoming ready." "$log_path"
      return 1
    fi
    if curl --fail --silent --show-error --max-time 1 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  fail_with_log "$label did not become ready." "$log_path"
}

"$python_command" - "$frontend_url" "$api_url" <<'PY'
import sys
from urllib.parse import urlsplit

for label, raw in (("frontend", sys.argv[1]), ("API", sys.argv[2])):
    parsed = urlsplit(raw)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit(f"{label} must be an explicit loopback HTTP URL; got {raw!r}")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SystemExit(f"{label} URL must not carry credentials, query, or fragment")

frontend = urlsplit(sys.argv[1])
if frontend.port != 4173:
    raise SystemExit("frontend must use local port 4173, the API's governed CORS origin")
PY

"$python_command" "$repository_root/casepath/tools/build_static_site.py" \
  >"$preflight_root/static-build.json"

if ! curl --fail --silent --show-error --max-time 2 \
  "${frontend_url%/}/index.html" >/dev/null 2>&1; then
  frontend_url="http://127.0.0.1:4173"
  "$python_command" -m http.server 4173 \
    --bind 127.0.0.1 \
    --directory "$repository_root/casepath-public" \
    >"$frontend_log" 2>&1 &
  frontend_pid="$!"
  wait_for_http "$frontend_url/index.html" "$frontend_pid" "Authored frontend" "$frontend_log"
fi

while IFS= read -r relative_path; do
  served_path="$preflight_root/served-${relative_path//\//-}"
  curl --fail --silent --show-error --max-time 5 \
    "${frontend_url%/}/$relative_path" \
    --output "$served_path" \
    || fail_with_log "Current-source frontend is not reachable at $frontend_url."
  cmp --silent "$served_path" "$repository_root/casepath-public/$relative_path" \
    || fail_with_log "Served frontend differs from the canonical static build at $relative_path."
  if [[ -f "$repository_root/casepath/$relative_path" ]]; then
    cmp --silent "$served_path" "$repository_root/casepath/$relative_path" \
      || fail_with_log "Built frontend differs from authored bytes at $relative_path."
  fi
done < <("$python_command" - "$repository_root/casepath/tools/build_static_site.py" <<'PY'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("casepath_static_build", sys.argv[1])
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
for value in sorted(module.PUBLIC_INVENTORY):
    print(value)
PY
)

source_only_status="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 5 "${frontend_url%/}/README.md")"
[[ "$source_only_status" == "404" ]] \
  || fail_with_log "Canonical static server exposed a source-only path (HTTP $source_only_status)."

if ! curl --fail --silent --show-error --max-time 2 \
  "${api_url%/}/healthz" >/dev/null 2>&1; then
  api_port="$("$python_command" - "$api_url" <<'PY'
import sys
from urllib.parse import urlsplit

parsed = urlsplit(sys.argv[1])
print(parsed.port or 80)
PY
)"
  (
    unset OPENROUTER_API_KEY CASEPATH_AGENT_RUNTIME_PROFILE CASEPATH_SOURCE_COMMIT \
      RENDER_GIT_COMMIT LANGSMITH_API_KEY LANGCHAIN_API_KEY
    export CASEPATH_MODEL_MODE=deterministic_reference
    export CASEPATH_DB_PATH="$preflight_root/preflight.db"
    export LANGSMITH_TRACING=false
    export LANGCHAIN_TRACING_V2=false
    export LANGCHAIN_TRACING=false
    exec "$python_command" -m uvicorn casepath_api.app:app \
      --app-dir "$repository_root/casepath-api" \
      --host 127.0.0.1 \
      --port "$api_port"
  ) >"$api_log" 2>&1 &
  api_pid="$!"
  wait_for_http "$api_url/readyz" "$api_pid" "Deterministic API" "$api_log"
fi

"$python_command" - "$api_url" <<'PY'
import json
import sys
from urllib.request import Request, urlopen

base = sys.argv[1].rstrip("/")


def get(path: str):
    request = Request(f"{base}{path}", headers={"Accept": "application/json"})
    with urlopen(request, timeout=5) as response:
        if response.status != 200:
            raise SystemExit(f"{path} returned HTTP {response.status}")
        return json.load(response)


health = get("/healthz")
readiness = get("/readyz")
ledger = get("/api/model-ledger")
summary = ledger.get("summary") or {}

if health.get("status") != "ok" or health.get("model_mode") != "deterministic_reference":
    raise SystemExit("local API is not healthy deterministic_reference")
if readiness.get("status") != "ready":
    raise SystemExit("local API is not ready")
if readiness.get("model_budget", {}).get("credential_configured") is not False:
    raise SystemExit("local API exposes a provider credential; refusing preflight")
expected_zero = {
    "records": 0,
    "network_calls": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "actual_cost_usd": 0,
    "unknown_cost_call_count": 0,
}
for key, expected in expected_zero.items():
    if summary.get(key) != expected:
        raise SystemExit(f"local model ledger is not fresh: {key}={summary.get(key)!r}")
if ledger.get("items") != []:
    raise SystemExit("local model ledger contains rows")
PY

if [[ ! -d "$qa_directory/node_modules/playwright" ]]; then
  fail_with_log "Pinned Playwright dependencies are unavailable. Run 'cd casepath-qa && npm ci --no-audit --no-fund' first."
fi
[[ -x "$playwright_executable" ]] \
  || fail_with_log "The governed ego lite browser executable is unavailable: $playwright_executable"

(
  cd "$qa_directory"
  env -i \
    HOME="$HOME" \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
    TMPDIR="$qa_tmp_root" \
    TZ=UTC \
    __CF_USER_TEXT_ENCODING="$macos_text_encoding" \
    CASEPATH_QA_OUT="$preflight_output" \
    CASEPATH_ALLOW_PRODUCTION_MUTATION=0 \
    CASEPATH_QA_API_BOOT_RECEIPT="${CASEPATH_QA_API_BOOT_RECEIPT:-}" \
    CASEPATH_QA_SERVICE_ROOT="${CASEPATH_QA_SERVICE_ROOT:-}" \
    PLAYWRIGHT_EXECUTABLE_PATH="$playwright_executable" \
    BASE_URL="$frontend_url" \
    API_URL="$api_url" \
    /usr/local/bin/node browser-focused-v20.mjs
) >"$browser_log" 2>&1 \
  || fail_with_log "Governed desktop browser journey failed." "$browser_log"

"$python_command" "$repository_root/casepath/tools/casepath_release.py" \
  verify-runtime-causal-evidence \
  --report "$preflight_output/report.json" \
  --evidence-manifest "$preflight_output/evidence-manifest.json" \
  >"$verifier_log" 2>&1 \
  || fail_with_log "Causal evidence verification failed." "$verifier_log"

if [[ "${frontend_url%/}" == "http://127.0.0.1:4173" \
  && "${api_url%/}" == "http://127.0.0.1:4173" \
  && -n "${CASEPATH_QA_API_BOOT_RECEIPT:-}" \
  && -n "${CASEPATH_QA_SERVICE_ROOT:-}" \
  && -n "${CASEPATH_QA_RUN_ID:-}" ]]; then
  (
    cd "$qa_directory"
    env -i \
      HOME="$HOME" \
      LANG=C.UTF-8 \
      LC_ALL=C.UTF-8 \
      PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
      TMPDIR="$qa_tmp_root" \
      TZ=UTC \
      __CF_USER_TEXT_ENCODING="$macos_text_encoding" \
      CASEPATH_INSURANCE_QA_OUT="$insurance_output" \
      CASEPATH_ALLOW_PRODUCTION_MUTATION=0 \
      CASEPATH_QA_API_BOOT_RECEIPT="$CASEPATH_QA_API_BOOT_RECEIPT" \
      CASEPATH_QA_SERVICE_ROOT="$CASEPATH_QA_SERVICE_ROOT" \
      CASEPATH_QA_RUN_ID="$CASEPATH_QA_RUN_ID" \
      PLAYWRIGHT_EXECUTABLE_PATH="$playwright_executable" \
      BASE_URL="$frontend_url" \
      API_URL="$api_url" \
      /usr/local/bin/node browser-insurance-protocol-v1.mjs
  ) >"$insurance_browser_log" 2>&1 \
    || fail_with_log "Insurance protocol built-artifact journey failed." "$insurance_browser_log"
  insurance_gate_ran="1"
else
  printf 'Insurance protocol gate requires the exact same-origin ./bin/casepath dev runtime; retained split-origin legacy preflight remains separate.\n'
fi

"$python_command" - "$preflight_output/report.json" "$api_url" <<'PY'
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if report.get("status") != "passed" or report.get("failed") != 0:
    raise SystemExit("browser report is not an exact pass")
legal_trace_check = next(
    (
        item
        for item in report.get("checks", [])
        if item.get("name") == "Run returns four exact official legal-source execution traces"
    ),
    None,
)
if legal_trace_check is None or legal_trace_check.get("passed") is not True:
    raise SystemExit("browser report lacks four accepted official legal-source traces")

request = Request(
    f"{sys.argv[2].rstrip('/')}/api/model-ledger",
    headers={"Accept": "application/json"},
)
with urlopen(request, timeout=5) as response:
    ledger = json.load(response)
summary = ledger.get("summary") or {}
if (
    summary.get("records") != 0
    or summary.get("network_calls") != 0
    or summary.get("actual_cost_usd") != 0
    or summary.get("unknown_cost_call_count") != 0
    or ledger.get("items") != []
):
    raise SystemExit("post-journey model ledger is not exactly empty")
PY

passed="1"
