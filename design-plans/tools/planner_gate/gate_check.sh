#!/usr/bin/env bash
# CasePath independent closing gate.
#
#   gate_check.sh <sha> <outdir>
#
# 1. fetches <sha> into the CasePath repository (no branch, no working-tree change) and makes a
#    fresh detached worktree <gate-dir>/wt-<sha7>;
# 2. runs ./bin/casepath prepare and the FULL ./bin/casepath test there (frontend suites required);
# 3. seeds the nine provider-free reference histories into a disposable data root, serves them on a
#    free localhost port and drives headless Chromium (1440x900) through every case (gate_browse.mjs);
# 4. writes <outdir>/summary.json, <outdir>/test.log, <outdir>/browser.json and <outdir>/shots/.
# Exit 0 only when summary.json says "verdict": "pass".
#
# Env: KEEP=1 keeps the worktree (and its seeded data root) afterwards.
#      CASEPATH_REPO (default /home/user/casepath), GATE_PORTS (default 4180-4199),
#      GATE_TOTAL_S (default 6900, the whole run's own deadline; keep it under the caller's timeout).
# Never pushes, posts, deploys or calls a model provider: the server and the seeding run with an empty
# environment in deterministic_reference mode, and the gate refuses to browse a server reporting a ready provider.
set -uo pipefail
umask 022

# Run from a private copy so that editing this file during a run cannot change the running gate.
if [[ -z "${GATE_SELF_COPY:-}" ]]; then
  GATE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  copy=$(mktemp "${TMPDIR:-/tmp}/gate_check.XXXXXX") || exit 2
  cp "${BASH_SOURCE[0]}" "$copy" || exit 2
  GATE_SELF_COPY=$copy GATE_DIR=$GATE_DIR exec bash "$copy" "$@"
fi
rm -f "$GATE_SELF_COPY"
GATE_DIR=${GATE_DIR:?}
REPO=${CASEPATH_REPO:-/home/user/casepath}
NODE=${GATE_NODE:-/opt/node22/bin/node}
export PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}
IDS="clm_314f2d309fea25e6,clm_4a07dbbbd859a3ce,clm_95d08975bc575592,clm_0f4f13b1e3e1328c,clm_393285577dcb12c4,clm_4a53299cfe619303,clm_2c55cdd816b1d0e8,clm_543f08f2415b2a33,clm_7dbd7c7d1c4ddf90"
T0=$(date +%s)
TOTAL_S=${GATE_TOTAL_S:-6900}
DEADLINE=$((T0 + TOTAL_S))

if [[ $# -ne 2 || ! "$1" =~ ^[0-9a-fA-F]{7,40}$ ]]; then
  echo "usage: gate_check.sh <commit-sha> <outdir>   (KEEP=1 keeps the worktree)" >&2; exit 2
fi
SHA_ARG=$(tr 'A-F' 'a-f' <<<"$1")
mkdir -p "$2" || { echo "cannot create outdir $2" >&2; exit 2; }
OUT=$(cd "$2" && pwd)
SHA7=${SHA_ARG:0:7}
WT="$GATE_DIR/wt-$SHA7"
STATE="$OUT/.gate-state.tsv"; NOTES="$OUT/.gate-notes.txt"

# One gate per commit at a time (it owns wt-<sha7>); different commits may run side by side.
# A refused run touches nothing, not even <outdir>.
exec 9>"$GATE_DIR/.lock-$SHA7"
if ! flock -n 9; then echo "another gate run for $SHA7 holds $GATE_DIR/.lock-$SHA7; nothing done" >&2; exit 3; fi
# Idempotent: every run starts from an empty result set in <outdir>.
rm -rf "$OUT/shots" "$OUT/summary.json" "$OUT/browser.json" "$OUT/test.log" "$OUT/prepare.log" \
       "$OUT/seed.log" "$OUT/server.log" "$OUT/browser.log" "$OUT/fetch.log" "$STATE" "$NOTES"
mkdir -p "$OUT/shots"
: >"$STATE"; : >"$NOTES"
log() { printf '[gate %s +%ss] %s\n' "$SHA7" "$(( $(date +%s) - T0 ))" "$*" >&2; }
state() { printf '%s\t%s\n' "$1" "$2" >>"$STATE"; }
note() { printf '%s\n' "$*" >>"$NOTES"; log "note: $*"; }
remaining() { echo $(( DEADLINE - $(date +%s) )); }
state sha "$SHA_ARG"

# ------------------------------------------------------------------ process control (own PIDs only)
SERVER_PID=""; CHILD_PID=""; TEST_PID=""; SUMMARY_DONE=0
remove_worktree() {
  chmod -R u+w "$WT" 2>/dev/null
  git -C "$REPO" worktree remove --force "$WT" >/dev/null 2>&1   # only if an older run registered one
  rm -rf "$WT"
  git -C "$REPO" worktree prune >/dev/null 2>&1
}
descendants() { local c; for c in $(ps -o pid= --ppid "$1" 2>/dev/null); do echo "$c"; descendants "$c"; done; }
kill_tree() {  # kill a process this script started, and everything it started, by PID
  local root=$1 pids p i
  [[ -n "$root" ]] && kill -0 "$root" 2>/dev/null || return 0
  pids="$root $(descendants "$root" | tr '\n' ' ')"
  for p in $pids; do kill -TERM "$p" 2>/dev/null; done
  for i in $(seq 1 20); do
    local alive=0; for p in $pids; do kill -0 "$p" 2>/dev/null && alive=1; done
    [[ $alive -eq 0 ]] && return 0; sleep 0.5
  done
  for p in $pids; do kill -KILL "$p" 2>/dev/null; done
  return 0
}
# run_phase <name> <budget-s> <logfile> <cmd...>: runs cmd in the background under our own deadline,
# so signals reach the trap promptly and a timeout kills the whole child tree. Sets PHASE_RC/PHASE_S.
run_phase() {
  local name=$1 budget=$2 logf=$3; shift 3
  local start; start=$(date +%s)
  local left; left=$(remaining)
  (( budget > left - 60 )) && budget=$(( left - 60 ))
  if (( budget < 30 )); then PHASE_RC=125; PHASE_S=0; note "$name skipped: gate deadline reached"; return; fi
  "$@" >>"$logf" 2>&1 </dev/null &
  CHILD_PID=$!
  local end=$(( start + budget )) timed=0
  while kill -0 "$CHILD_PID" 2>/dev/null; do
    if (( $(date +%s) >= end )); then timed=1; log "$name exceeded ${budget}s; stopping it"; kill_tree "$CHILD_PID"; break; fi
    sleep 2
  done
  wait "$CHILD_PID" 2>/dev/null; PHASE_RC=$?
  (( timed )) && PHASE_RC=124
  CHILD_PID=""
  PHASE_S=$(( $(date +%s) - start ))
  state "${name}_rc" "$PHASE_RC"; state "${name}_s" "$PHASE_S"
}

summarize() {
  [[ $SUMMARY_DONE -eq 1 ]] && return
  SUMMARY_DONE=1
  state total_s "$(( $(date +%s) - T0 ))"
  python3 -I "$GATE_DIR/gate_summary.py" "$OUT" || {
    log "summary writer failed; writing a minimal failing summary"
    printf '{"sha":"%s","test":{"exit":null,"passed":null,"failed":null,"errors":null,"skipped":null,"duration_s":null},"browser":{"cases_total":9,"cases_passed":0,"console_errors":[],"page_errors":[],"write_requests":[],"overlaps":0,"failures":[{"case":"global","step":"summary","reason":"summary writer failed"}]},"verdict":"fail","notes":["summary writer failed"]}\n' "$SHA_ARG" >"$OUT/summary.json"
  }
}
cleanup() {
  local rc=$?
  trap - EXIT INT TERM HUP
  [[ -n "$CHILD_PID" ]] && kill_tree "$CHILD_PID"
  if [[ -n "$TEST_PID" ]]; then kill_tree "$TEST_PID"; log "stopped the full test (pid $TEST_PID)"; fi
  if [[ -n "$SERVER_PID" ]]; then kill_tree "$SERVER_PID"; log "stopped server pid $SERVER_PID"; fi
  summarize
  if [[ "${KEEP:-0}" == "1" ]]; then log "KEEP=1: worktree kept at $WT"
  elif [[ -d "$WT" ]]; then
    remove_worktree; log "removed worktree $WT"
  fi
  local verdict; verdict=$(python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1])).get("verdict"))' "$OUT/summary.json" 2>/dev/null)
  log "verdict: ${verdict:-unknown} ($OUT/summary.json)"
  [[ "$verdict" == "pass" ]] && exit 0
  exit 1
}
on_signal() { note "gate interrupted by signal $1"; exit 1; }
trap cleanup EXIT
trap 'on_signal TERM' TERM; trap 'on_signal INT' INT; trap 'on_signal HUP' HUP


# ------------------------------------------------------------------ 1. fetch + fresh worktree
log "fetching $SHA_ARG"
run_phase fetch 300 "$OUT/fetch.log" git -C "$REPO" fetch --no-tags --no-write-fetch-head origin "$SHA_ARG"
if [[ $PHASE_RC -ne 0 ]]; then
  if git -C "$REPO" cat-file -e "$SHA_ARG^{commit}" 2>/dev/null; then note "fetch failed (rc $PHASE_RC); using the commit already present locally"
  else note "fetch of $SHA_ARG failed (rc $PHASE_RC) and the commit is not present locally"; state aborted fetch; exit 1; fi
fi
SHA=$(git -C "$REPO" rev-parse --verify --quiet "$SHA_ARG^{commit}") || { note "cannot resolve $SHA_ARG to a commit"; state aborted resolve; exit 1; }
state sha "$SHA"
if [[ -e "$WT" ]]; then log "removing stale worktree $WT"; remove_worktree; fi
# ./bin/casepath requires .git to be a real directory (a `git worktree` gitfile is refused as
# "canonical Git source authority is invalid"), so the detached worktree is a fresh repository that
# borrows the main repository's object store read-only (objects/info/alternates, like clone --shared).
# Nothing in the main repository changes: no ref, branch, index or working-tree file is written.
OBJECTS=$(cd "$REPO" && cd "$(git rev-parse --git-common-dir)/objects" && pwd)
if ! { git init --quiet "$WT" && echo "$OBJECTS" >"$WT/.git/objects/info/alternates" \
       && git -C "$WT" -c advice.detachedHead=false checkout --quiet --detach "$SHA"; } >>"$OUT/fetch.log" 2>&1; then
  note "creating the detached worktree failed (see fetch.log)"; state aborted worktree; exit 1
fi
[[ "$(git -C "$WT" rev-parse HEAD)" == "$SHA" && -z "$(git -C "$WT" status --porcelain)" ]] || { note "worktree is not a clean checkout of $SHA"; state aborted worktree; exit 1; }
state worktree "$WT"

# ------------------------------------------------------------------ 2. prepare + full test
PROVIDER_VARS=(-u OPENROUTER_API_KEY -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u LANGSMITH_API_KEY -u LANGCHAIN_API_KEY -u LANGSMITH_TRACING -u LANGCHAIN_TRACING -u LANGCHAIN_TRACING_V2)
log "prepare"
run_phase prepare 1200 "$OUT/prepare.log" env "${PROVIDER_VARS[@]}" UV_LINK_MODE=copy bash -c 'cd "$1" && exec ./bin/casepath prepare' _ "$WT"
PREPARE_RC=$PHASE_RC
CAP=$(grep -E '^/' "$OUT/prepare.log" | tail -1)
if [[ $PREPARE_RC -ne 0 || -z "$CAP" || ! -d "$CAP/casepath-public" || ! -d "$CAP/casepath-api" ]]; then
  note "prepare failed (rc $PREPARE_RC); no sealed source capsule, so nothing can be served (see prepare.log)"; CAP=""
else state capsule "$CAP"; fi

# The full test runs alone (nothing else of the gate competes for CPU, so timing-sensitive tests are
# not disturbed). It keeps 15 minutes of the gate's deadline for seeding and browsing.
: >"$OUT/test.log"
if [[ $PREPARE_RC -eq 0 ]]; then
  log "full test"
  run_phase test $(( $(remaining) - 900 )) "$OUT/test.log" env "${PROVIDER_VARS[@]}" UV_LINK_MODE=copy \
    CASEPATH_NODE="$NODE" NODE_PATH="${NODE_PATH:-/opt/node22/lib/node_modules}" \
    PLAYWRIGHT_BROWSERS_PATH="$PLAYWRIGHT_BROWSERS_PATH" CASEPATH_REQUIRE_FRONTEND_SUITES=1 \
    bash -c 'cd "$1" && exec ./bin/casepath test' _ "$WT"
  [[ $PHASE_RC -eq 124 ]] && note "full test did not finish within its budget; stopped"
  log "test rc $PHASE_RC in ${PHASE_S}s"
else
  echo "test not run: prepare failed (rc $PREPARE_RC)" >"$OUT/test.log"; note "full test not run because prepare failed"
fi

# ------------------------------------------------------------------ 3. seed + serve + browse
PY="$WT/.runtime/casepath-dev-v2/venv/bin/python"
DATA="$WT/.runtime/gate-seeded"
if [[ -n "$CAP" && -x "$PY" ]]; then
  rm -rf "$DATA"; mkdir -p "$DATA/data" "$DATA/home" "$DATA/tmp"
  CLEAN_ENV=(env -i HOME="$DATA/home" TMPDIR="$DATA/tmp" LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=UTC PATH=/usr/bin:/bin
    PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 CASEPATH_MODEL_MODE=deterministic_reference CASEPATH_SOURCE_COMMIT="$SHA"
    LANGSMITH_TRACING=false LANGCHAIN_TRACING=false LANGCHAIN_TRACING_V2=false)
  log "seeding the nine reference histories"
  run_phase seed 1200 "$OUT/seed.log" "${CLEAN_ENV[@]}" "$PY" -I -B "$GATE_DIR/stage_nine.py" "$CAP/casepath-api" "$DATA/data" "$IDS"
  SEED_RC=$PHASE_RC
  if [[ $SEED_RC -ne 0 ]] || ! grep -q '"staged": 18' "$OUT/seed.log"; then
    note "seeding failed (rc $SEED_RC; see seed.log)"; SEED_OK=0
  else SEED_OK=1; fi
  state seed_ok "$SEED_OK"

  if [[ $SEED_OK -eq 1 ]]; then
    IFS=- read -r PLO PHI <<<"${GATE_PORTS:-4180-4199}"
    port_free() { ! (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && [[ -z "$(lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null)" ]]; }
    PORT=""
    for ((p = PLO; p <= PHI; p++)); do
      port_free "$p" || continue
      : >"$OUT/server.log"
      "${CLEAN_ENV[@]}" CASEPATH_DB_PATH="$DATA/data/casepath.db" CASEPATH_ARTIFACT_REGISTRY_PATH="$DATA/data/artifact-registry" \
        CASEPATH_LOCAL_STATIC_ROOT="$CAP/casepath-public" \
        "$PY" -I -B -P -m uvicorn casepath_api.app:app --app-dir "$CAP/casepath-api" --host 127.0.0.1 --port "$p" --no-access-log \
        >>"$OUT/server.log" 2>&1 </dev/null &
      SERVER_PID=$!
      state server_pid "$SERVER_PID"
      ready=0
      for i in $(seq 1 120); do   # the first start imports the whole API: allow 4 minutes
        kill -0 "$SERVER_PID" 2>/dev/null || break
        if [[ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:$p/api/claim-loops/v1/autonomous/status")" == 200 ]]; then ready=1; break; fi
        sleep 2
      done
      owner=$(lsof -nP -iTCP:"$p" -sTCP:LISTEN -t 2>/dev/null | tr '\n' ' ')
      ours=0; for o in $owner; do [[ "$o" == "$SERVER_PID" || " $(descendants "$SERVER_PID" | tr '\n' ' ') " == *" $o "* ]] && ours=1; done
      if [[ $ready -eq 1 && $ours -eq 1 ]]; then PORT=$p; break; fi
      note "server on port $p not ready or not ours (listener pids: ${owner:-none}); trying the next port"
      kill_tree "$SERVER_PID"; SERVER_PID=""
      (( $(remaining) < 600 )) && break
    done
    if [[ -z "$PORT" ]]; then note "could not start the seeded server on any port in ${GATE_PORTS:-4180-4199}"
    else
      state port "$PORT"; BASE="http://127.0.0.1:$PORT"
      log "serving $BASE (pid $SERVER_PID)"
      # The server must be this commit's sealed capsule and must not be able to reach a provider.
      STATUS=$(curl -s --max-time 10 "$BASE/api/claim-loops/v1/autonomous/status")
      PROVIDER_READY=$(python3 -I -c 'import json,sys; print(json.loads(sys.argv[1]).get("provider_ready"))' "$STATUS" 2>/dev/null)
      SERVED_OK=1
      for f in index.html assets/autonomous-workspace-v1.js; do
        want=$(sha256sum <"$CAP/casepath-public/$f" 2>/dev/null | cut -d' ' -f1)
        got=$(curl -s --max-time 30 "$BASE/$f" | sha256sum | cut -d' ' -f1)
        [[ -n "$want" && "$want" == "$got" ]] || { SERVED_OK=0; note "served /$f does not match the worktree capsule"; }
      done
      state served_matches_capsule "$SERVED_OK"
      if [[ "$PROVIDER_READY" != "False" ]]; then
        note "refusing to browse: server status reports provider_ready=${PROVIDER_READY:-unknown}"
      elif [[ $SERVED_OK -ne 1 ]]; then
        note "refusing to browse: the server on $PORT is not serving this commit"
      else
        log "browser walk-through"
        run_phase browser 2400 "$OUT/browser.log" env GATE_BROWSER_BUDGET_S=2100 "$NODE" "$GATE_DIR/gate_browse.mjs" "$BASE" "$OUT" "$IDS" "$WT"
        log "browser rc $PHASE_RC in ${PHASE_S}s"
      fi
      kill_tree "$SERVER_PID"; log "stopped server pid $SERVER_PID"; SERVER_PID=""
    fi
  fi
else
  note "browser walk-through not run: no prepared capsule or venv"
fi

# ------------------------------------------------------------------ 4. wait for the full test
if [[ -n "$TEST_PID" ]]; then
  log "waiting for the full test"
  timed=0
  while kill -0 "$TEST_PID" 2>/dev/null; do
    if (( $(remaining) <= 90 )); then timed=1; note "full test still running at the gate deadline (${TOTAL_S}s); stopped"; kill_tree "$TEST_PID"; break; fi
    sleep 5
  done
  wait "$TEST_PID" 2>/dev/null; rc=$?
  (( timed )) && rc=124
  state test_rc "$rc"; state test_s "$(( $(date +%s) - TEST_START ))"
  log "test rc $rc in $(( $(date +%s) - TEST_START ))s"
  TEST_PID=""
fi
exit 0   # cleanup (trap) writes summary.json and sets the exit code from the verdict
