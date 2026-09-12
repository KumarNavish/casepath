#!/usr/bin/env bash
set -euo pipefail

# One fail-closed local acceptance run for the real Nemotron runtime. This is
# deliberately separate from visual iteration: deterministic QA must pass
# first, the model ledger must start empty, and the browser journey is invoked
# exactly once. Nothing here retries a provider call.

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
qa_directory="$repository_root/casepath-qa"
frontend_root="$repository_root/casepath-public"
preflight_frontend_url="${CASEPATH_LOCAL_PREFLIGHT_FRONTEND_URL:-http://127.0.0.1:4173}"
frontend_port=""
frontend_url=""
api_url=""
database_path=""
qa_tmp_root="${TMPDIR:-/tmp}"
qa_tmp_root="${qa_tmp_root%/}"
acceptance_root=""
evidence_output=""
frontend_pid=""
api_pid=""
passed="0"

if [[ "${CASEPATH_AUTHORIZE_REAL_NEMOTRON:-}" != "1" ]]; then
  printf 'CASEPATH REAL NEMOTRON ACCEPTANCE: REFUSED\n' >&2
  printf 'Set CASEPATH_AUTHORIZE_REAL_NEMOTRON=1 to authorize exactly one fresh six-call model journey.\n' >&2
  exit 2
fi

if [[ -n "${CASEPATH_QA_PYTHON:-}" ]]; then
  python_command="$CASEPATH_QA_PYTHON"
elif [[ -x /private/tmp/casepath-langchain-venv/bin/python ]]; then
  python_command="/private/tmp/casepath-langchain-venv/bin/python"
else
  printf 'Pinned QA Python is unavailable. Set CASEPATH_QA_PYTHON to the Python 3.13.9 lock environment.\n' >&2
  exit 2
fi

terminate_process() {
  local process_id="$1"
  if [[ -n "$process_id" ]] && kill -0 "$process_id" 2>/dev/null; then
    kill "$process_id" 2>/dev/null || true
    wait "$process_id" 2>/dev/null || true
  fi
}

capture_runtime_diagnostics() {
  if [[ -z "$acceptance_root" ]]; then
    return 0
  fi
  if [[ -n "$api_url" && -n "$api_pid" ]] && kill -0 "$api_pid" 2>/dev/null; then
    curl --fail --silent --show-error --max-time 5 "$api_url/healthz" \
      --output "$acceptance_root/final-health.json" 2>/dev/null || true
    curl --fail --silent --show-error --max-time 5 "$api_url/readyz" \
      --output "$acceptance_root/final-readiness.json" 2>/dev/null || true
    curl --fail --silent --show-error --max-time 5 "$api_url/api/model-ledger" \
      --output "$acceptance_root/final-model-ledger.json" 2>/dev/null || true
  fi
  if [[ -n "$database_path" && -s "$database_path" ]]; then
    "$python_command" - "$database_path" "$acceptance_root/final-run.json" <<'PY' 2>/dev/null || true
import json
import sqlite3
import sys
from pathlib import Path

database_path, output_path = sys.argv[1:]
with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True, timeout=2) as connection:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT run_id, session_id, payload, created_at, updated_at "
        "FROM runs ORDER BY updated_at DESC, created_at DESC LIMIT 1"
    ).fetchone()
    if row is not None:
        payload = json.loads(row["payload"])
        events = [
            json.loads(event["payload"])
            for event in connection.execute(
                "SELECT payload FROM events "
                "WHERE session_id=? AND run_id=? ORDER BY ordinal",
                (row["session_id"], row["run_id"]),
            )
        ]
    else:
        payload = None
if payload is not None:
    payload.update(
        events=events,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
    Path(output_path).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
PY
  fi
}

finish() {
  local exit_code="$?"
  capture_runtime_diagnostics
  terminate_process "$api_pid"
  terminate_process "$frontend_pid"
  if [[ "$exit_code" -eq 0 && "$passed" == "1" ]]; then
    printf '\nCASEPATH REAL NEMOTRON ACCEPTANCE: PASS\n'
    printf 'Evidence: %s\n' "$evidence_output"
    printf 'Diagnostics and fresh database: %s\n' "$acceptance_root"
  else
    printf '\nCASEPATH REAL NEMOTRON ACCEPTANCE: FAIL\n' >&2
    if [[ -n "$acceptance_root" ]]; then
      printf 'Evidence and diagnostics were preserved: %s\n' "$acceptance_root" >&2
    fi
  fi
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

wait_for_http() {
  local url="$1"
  local process_id="$2"
  local label="$3"
  local log_path="$4"
  local attempt
  # Readiness polling does not retry or invoke a model operation.
  for ((attempt = 0; attempt < 240; attempt += 1)); do
    if ! kill -0 "$process_id" 2>/dev/null; then
      printf '%s stopped before becoming ready. See %s\n' "$label" "$log_path" >&2
      return 1
    fi
    if curl --fail --silent --show-error --max-time 1 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  printf '%s did not become ready. See %s\n' "$label" "$log_path" >&2
  return 1
}

"$python_command" - <<'PY'
import sys

expected = (3, 13, 9)
if sys.version_info[:3] != expected:
    raise SystemExit(
        f"QA Python must be {'.'.join(map(str, expected))}; got {sys.version.split()[0]}"
    )
PY

if [[ ! -d "$qa_directory/node_modules/playwright" ]]; then
  printf 'Pinned Playwright dependencies are unavailable. Run npm ci in casepath-qa first.\n' >&2
  exit 2
fi
if [[ ! -f "$repository_root/casepath-api/.env.local" || -L "$repository_root/casepath-api/.env.local" ]]; then
  printf 'casepath-api/.env.local must be a regular local credential file.\n' >&2
  exit 2
fi
if [[ -n "$(git -C "$repository_root" status --porcelain --untracked-files=normal)" ]]; then
  printf 'The acceptance checkout must be clean so retained evidence names the exact tested commit.\n' >&2
  exit 2
fi
source_commit="$(git -C "$repository_root" rev-parse HEAD)"
if [[ ! "$source_commit" =~ ^[0-9a-f]{40}$ ]]; then
  printf 'The acceptance source commit is not an exact Git identity.\n' >&2
  exit 2
fi

acceptance_root="$(mktemp -d "$qa_tmp_root/casepath-qa-real.XXXXXX")"
evidence_output="$acceptance_root/evidence"
preflight_log="$acceptance_root/deterministic-preflight.log"
frontend_log="$acceptance_root/frontend.log"
api_log="$acceptance_root/api.log"
browser_log="$acceptance_root/browser.log"
verifier_log="$acceptance_root/causal-verifier.log"
database_path="$acceptance_root/fresh-real-nemotron.db"

printf 'Running the mandatory deterministic, zero-provider preflight first.\n'
preflight_api_port="$("$python_command" - <<'PY'
import socket

with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
CASEPATH_EXPECT_REAL_NEMOTRON=0 \
CASEPATH_LOCAL_FRONTEND_URL="$preflight_frontend_url" \
CASEPATH_LOCAL_API_URL="http://127.0.0.1:$preflight_api_port" \
CASEPATH_QA_PYTHON="$python_command" \
  bash "$qa_directory/run-local-preflight-v20.sh" \
  2>&1 | tee "$preflight_log"

# Build a commit-bound local public tree only after deterministic QA passes.
CASEPATH_SOURCE_COMMIT="$source_commit" \
  "$python_command" "$repository_root/casepath/tools/build_static_site.py" \
  --require-known-commit \
  >"$acceptance_root/static-build.json"

frontend_port="$("$python_command" - <<'PY'
import socket

with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
frontend_url="http://127.0.0.1:$frontend_port"
"$python_command" -m http.server "$frontend_port" \
  --bind 127.0.0.1 \
  --directory "$frontend_root" \
  >"$frontend_log" 2>&1 &
frontend_pid="$!"
wait_for_http "$frontend_url/deployment.json" "$frontend_pid" "Isolated commit-bound frontend" "$frontend_log"

openrouter_api_key="$("$python_command" - "$repository_root/casepath-api/.env.local" <<'PY'
import shlex
import sys
from pathlib import Path

value = None
for raw_line in Path(sys.argv[1]).read_text(encoding="utf-8-sig").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("export "):
        line = line[7:].lstrip()
    key, separator, raw_value = line.partition("=")
    if separator and key.strip() == "OPENROUTER_API_KEY":
        parts = shlex.split(raw_value, comments=True, posix=True)
        if len(parts) != 1:
            raise SystemExit("OPENROUTER_API_KEY must contain one dotenv value")
        value = parts[0]
        break
if value is None or len(value) < 20 or any(character.isspace() for character in value):
    raise SystemExit("OPENROUTER_API_KEY is absent or malformed in .env.local")
print(value, end="")
PY
)"

api_port="$("$python_command" - <<'PY'
import socket

with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
api_url="http://127.0.0.1:$api_port"

if [[ -e "$database_path" ]]; then
  printf 'Fresh acceptance database already exists; refusing reuse.\n' >&2
  exit 2
fi

(
  unset RENDER_GIT_COMMIT LANGSMITH_API_KEY LANGCHAIN_API_KEY \
    LANGSMITH_TRACING LANGCHAIN_TRACING LANGCHAIN_TRACING_V2
  export OPENROUTER_API_KEY="$openrouter_api_key"
  export CASEPATH_MODEL_MODE=openrouter_nemotron
  export CASEPATH_AGENT_RUNTIME_PROFILE=nemotron_langgraph_multi_agent_hybrid_guarded
  export CASEPATH_SOURCE_COMMIT="$source_commit"
  export CASEPATH_RELEASE_ID=casepath-v20-reference-20260811
  export CASEPATH_MODEL_CUMULATIVE_USD_CAP=1
  export CASEPATH_DB_PATH="$database_path"
  export LANGSMITH_TRACING=false
  export LANGCHAIN_TRACING=false
  export LANGCHAIN_TRACING_V2=false
  exec "$python_command" -m uvicorn casepath_api.app:app \
    --app-dir "$repository_root/casepath-api" \
    --host 127.0.0.1 \
    --port "$api_port"
) >"$api_log" 2>&1 &
api_pid="$!"
wait_for_http "$api_url/healthz" "$api_pid" "Fresh real Nemotron API" "$api_log"

curl --fail --silent --show-error --max-time 10 "$frontend_url/deployment.json" \
  --output "$acceptance_root/initial-frontend-deployment.json"
curl --fail --silent --show-error --max-time 10 "$api_url/healthz" \
  --output "$acceptance_root/initial-health.json"
curl --fail --silent --show-error --max-time 10 "$api_url/readyz" \
  --output "$acceptance_root/initial-readiness.json"
curl --fail --silent --show-error --max-time 10 "$api_url/api/model-ledger" \
  --output "$acceptance_root/initial-model-ledger.json"

"$python_command" - "$acceptance_root" "$source_commit" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
commit = sys.argv[2]
frontend = json.loads((root / "initial-frontend-deployment.json").read_text())
health = json.loads((root / "initial-health.json").read_text())
readiness = json.loads((root / "initial-readiness.json").read_text())
ledger = json.loads((root / "initial-model-ledger.json").read_text())

agents = {
    "canonical_facts",
    "orchestrator_plan",
    "document_source_integrity",
    "process_decision_mapping",
    "evidence_checklist",
    "final_claim_brief_audit",
}
gates = {
    "deterministic_process_gate",
    "deterministic_evidence_gate",
    "whole_playbook_gate",
}
runtime = health.get("agentic_runtime") or {}
safety = runtime.get("safety") or {}
expected_routing = {
    "endpoint_tag": "together",
    "expected_upstream_provider": "Together",
    "allow_fallbacks": False,
    "require_parameters": True,
    "data_collection": "deny",
}
expected_framework = {
    "langchain": "1.3.14",
    "langgraph": "1.2.9",
    "langchain_openrouter": "0.2.7",
}
assert frontend.get("source_commit") == commit and frontend.get("alignment_eligible") is True
assert health.get("status") == "ok"
assert health.get("source_commit") == commit and health.get("source_commit_aligned") is True
assert health.get("source_commit_conflict") is False
assert health.get("model_mode") == "openrouter_nemotron"
assert health.get("model") == "nvidia/nemotron-3-ultra-550b-a55b"
assert health.get("runtime_profile") == "nemotron_langgraph_multi_agent_hybrid_guarded"
assert runtime.get("profile") == "nemotron_langgraph_multi_agent_hybrid_guarded"
assert runtime.get("configured_profile") == "nemotron_langgraph_multi_agent_hybrid_guarded"
assert runtime.get("profile_aligned") is True and runtime.get("trace_policy_aligned") is True
assert runtime.get("execution_mode") == "nemotron_multi_agent"
assert runtime.get("authority_mode") == "multi_agent_hybrid_guarded"
assert runtime.get("implementation") == "langgraph_stategraph_langchain_openrouter"
assert runtime.get("schema") == "casepath.nemotron-agent-dag/1.0.0"
assert runtime.get("framework") == expected_framework
assert set(runtime.get("required_agent_ids") or []) == agents
assert len(runtime.get("required_agent_ids") or []) == 6
assert set(runtime.get("deterministic_gate_ids") or []) == gates
assert len(runtime.get("deterministic_gate_ids") or []) == 3
assert safety.get("credential_configured") is True
assert safety.get("provider_max_in_flight") == 1
assert safety.get("deterministic_contract_authority") is True
assert safety.get("external_tracing") is False
assert safety.get("prompt_storage") is False and safety.get("raw_output_storage") is False
assert safety.get("model_fallback") is False and safety.get("automatic_inference_retry") is False
assert safety.get("provider_routing") == expected_routing
assert readiness.get("status") == "ready"
assert readiness.get("agentic_runtime") == runtime
budget = readiness.get("model_budget") or {}
assert budget.get("credential_configured") is True
assert budget.get("cumulative_usd_cap") == 1
expected_zero = {
    "records": 0,
    "network_calls": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "actual_cost_usd": 0,
    "actual_cost_complete": True,
    "unknown_cost_call_count": 0,
    "outcomes": {},
}
assert ledger.get("scope") == "global_budget_ledger"
assert ledger.get("summary") == expected_zero
assert ledger.get("items") == []
print("Fresh API passed exact health, readiness, and zero-ledger admission gates.")
PY

printf 'Admission cleared; invoking exactly one uncached real Nemotron browser journey.\n'
(
  cd "$qa_directory"
  env \
    -u OPENROUTER_API_KEY \
    CASEPATH_EXPECT_REAL_NEMOTRON=1 \
    CASEPATH_EXPECTED_SOURCE_COMMIT="$source_commit" \
    CASEPATH_QA_OUT="$evidence_output" \
    CASEPATH_ALLOW_PRODUCTION_MUTATION=0 \
    RENDER_GIT_COMMIT="$source_commit" \
    BASE_URL="$frontend_url" \
    API_URL="$api_url" \
    node browser-guided-v13-smoke.mjs
) >"$browser_log" 2>&1

curl --fail --silent --show-error --max-time 10 "$api_url/api/model-ledger" \
  --output "$acceptance_root/final-model-ledger.json"

"$python_command" - "$evidence_output/report.json" "$acceptance_root/final-model-ledger.json" "$source_commit" "$frontend_url" "$api_url" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
ledger = json.loads(Path(sys.argv[2]).read_text())
commit, frontend_url, api_url = sys.argv[3:]
assert report.get("status") == "passed" and report.get("failed") == 0
assert report.get("baseUrl") == frontend_url and report.get("apiUrl") == api_url
deployment = report.get("deployment") or {}
assert (deployment.get("frontend") or {}).get("source_commit") == commit
assert (deployment.get("api") or {}).get("source_commit") == commit
assert (deployment.get("qa") or {}).get("source_commit") == commit

summary = ledger.get("summary") or {}
items = ledger.get("items") or []
agents = {
    "canonical_facts",
    "orchestrator_plan",
    "document_source_integrity",
    "process_decision_mapping",
    "evidence_checklist",
    "final_claim_brief_audit",
}
assert ledger.get("scope") == "global_budget_ledger"
assert len(items) == 12 and summary.get("records") == 12
assert summary.get("network_calls") == 6
assert summary.get("outcomes", {}).get("cache_hit") == 6
assert summary.get("actual_cost_complete") is True
assert summary.get("unknown_cost_call_count") == 0
assert summary.get("prompt_tokens", 0) > 0
assert summary.get("completion_tokens", 0) > 0
assert summary.get("total_tokens", 0) > 0
assert summary.get("actual_cost_usd", 0) > 0
cold = [item for item in items if item.get("call_count") == 1]
warm = [item for item in items if item.get("outcome") == "cache_hit"]
assert len(cold) == 6 and len(warm) == 6
assert {item.get("agent_id") for item in cold} == agents
assert {item.get("agent_id") for item in warm} == agents
assert all(item.get("outcome") == "succeeded" for item in cold)
assert all(item.get("deterministic_fallback_applied") is False for item in cold)
assert all(item.get("rejected_fact_count", 0) == 0 for item in cold)
assert all(item.get("rejected_item_count", 0) == 0 for item in cold)
assert all(item.get("source_reference_projection_count", 0) == 0 for item in cold)
assert all(
    item.get("accepted_fact_count", item.get("accepted_item_count", 0)) > 0
    for item in cold
)
assert all(
    len(item.get("accepted_fact_ids", item.get("accepted_item_ids", [])))
    == item.get("accepted_fact_count", item.get("accepted_item_count", 0))
    for item in cold
)
assert all(item.get("actual_cost_usd", 0) > 0 for item in cold)
assert all(item.get("prompt_tokens", 0) > 0 and item.get("completion_tokens", 0) > 0 for item in cold)
assert all(item.get("call_count") == 0 and item.get("origin_call_id") for item in warm)
print("Final ledger is exact clean cold6 + warm6: no fallback, rejection, or citation projection.")
PY

"$python_command" "$repository_root/casepath/tools/casepath_release.py" \
  verify-runtime-causal-evidence \
  --report "$evidence_output/report.json" \
  --evidence-manifest "$evidence_output/evidence-manifest.json" \
  >"$verifier_log" 2>&1

passed="1"
