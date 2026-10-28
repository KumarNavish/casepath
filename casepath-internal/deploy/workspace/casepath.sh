#!/usr/bin/env bash
# CasePath on the development workspace: one command for each routine step.
#
#   casepath.sh setup        create the environment, install, run the tests
#   casepath.sh start|stop|status|logs
#   casepath.sh update       pull the branch, reinstall, test, restart
#   casepath.sh check-model  one synthetic model call (needs approval; no case data)
#   casepath.sh scorecard    print the content-free scorecard of the latest runs
set -euo pipefail

here="$(cd "$(dirname "$0")/../.." && pwd)"
home="${CASEPATH_HOME:-$HOME/.casepath}"
env_file="$home/env"
venv="$home/venv"
pid_file="$home/casepath.pid"
log_file="$home/casepath.log"

load_env() {
  [ -f "$env_file" ] || { echo "Create $env_file from $here/deploy/workspace/env.example first." >&2; exit 1; }
  set -a; . "$env_file"; set +a
  mkdir -p "${CASEPATH_DATA_DIR:?}" "${CASEPATH_WORKFLOW_CATALOGUE:?}"
}

running() { [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; }

# The development workspace reaches the internet only through a firewall that re-signs TLS. Without its
# certificates, pip and az fail with certificate errors; the platform guide's script installs them.
check_tls() {
  mkdir -p "$home"
  local index="${PIP_INDEX_URL:-https://pypi.org/simple/}"
  if ! curl -sS --max-time 20 -o /dev/null "$index" 2>"$home/tls-check.err"; then
    echo "Cannot reach $index over verified TLS: $(head -c 200 "$home/tls-check.err")" >&2
    echo "On the development workspace, first install the network's TLS certificates as the platform guide" >&2
    echo "describes (paste its script into this terminal), then run setup again." >&2
    exit 1
  fi
}

check_signin() {
  command -v az >/dev/null || { echo "The Azure CLI (az) is not installed on this machine." >&2; exit 1; }
  az account show --query user.name -o tsv >/dev/null 2>&1 || { echo "Sign in first: az login --use-device-code" >&2; exit 1; }
}

case "${1:-}" in
  setup)
    load_env
    check_tls
    python="${CASEPATH_PYTHON:-$(command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3)}"
    "$python" -m venv "$venv"
    "$venv/bin/pip" install --quiet --upgrade pip
    "$venv/bin/pip" install --quiet -e "$here[azure]"
    "$venv/bin/python" -m unittest discover -s "$here/tests" -t "$here"
    "$venv/bin/python" -m casepath_internal check-catalogue "$CASEPATH_WORKFLOW_CATALOGUE"
    ;;
  start)
    load_env
    running && { echo "already running (pid $(cat "$pid_file"))"; exit 0; }
    nohup "$venv/bin/python" -m casepath_internal serve --host 127.0.0.1 --port "${CASEPATH_PORT:-8765}" >>"$log_file" 2>&1 &
    echo $! >"$pid_file"
    sleep 2
    running && echo "started on port ${CASEPATH_PORT:-8765} (pid $(cat "$pid_file"))" || { tail -20 "$log_file"; exit 1; }
    ;;
  stop)
    running && kill "$(cat "$pid_file")" && rm -f "$pid_file" && echo stopped || echo "not running"
    ;;
  status)
    running && echo "running (pid $(cat "$pid_file"))" || echo "not running"
    ;;
  logs)
    tail -n "${2:-50}" "$log_file"
    ;;
  update)
    git -C "$here" pull --ff-only
    "$0" stop || true
    "$0" setup
    "$0" start
    ;;
  check-model)
    load_env
    check_signin
    "$venv/bin/python" "$here/deploy/workspace/check_model.py"
    ;;
  scorecard)
    load_env
    "$venv/bin/python" -m casepath_internal.scorecard "$CASEPATH_DATA_DIR" "${CASEPATH_SCORECARD_SALT:?set a private salt in $env_file}"
    ;;
  *)
    sed -n '2,9p' "$0"; exit 2
    ;;
esac
