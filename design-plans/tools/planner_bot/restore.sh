#!/usr/bin/env bash
# Idempotent restore for planner bot v2. If the v2 bot is not running, rebuild whatever is
# missing (code, north star concepts, venv) and start it detached. Prints exactly one status
# line. Never reads, prints, mines or copies the key: it only points the bot at the existing
# key file. Refuses to start while v1 runs, so the two bots never run together.
#   restore.sh                      restore if needed, then start
#   restore.sh --recover-only DIR   recover the committed files from git into DIR, then exit
set -u

S=/tmp/claude-0/-home-user/e812972b-ebf3-51a0-bcb0-c18d7b98dee7/scratchpad
DIR="$S/steer2"
RECOVER_ONLY=
if [ "${1:-}" = "--recover-only" ]; then RECOVER_ONLY=1; DIR="${2:?usage: restore.sh --recover-only DIR}"; fi
VENV="$DIR/venv"
PY="$VENV/bin/python"
STEER="$DIR/steer.py"
PIDFILE="$DIR/steer.pid"
KEYFILE="${STEER_KEY_FILE:-$S/steer/.key}"
V1_PATTERN="$S/steer/venv/bin/python $S/steer/steer.py"
REPO_DIR=/home/user/casepath
BRANCH=claude/casepath-cues-prototype
TOOLSUBDIR=design-plans/tools/planner_bot
FILES="steer.py system.md restore.sh stop.sh test_steer.py northstar/README.md
  northstar/01-decision-building.png northstar/02-completed-process.png northstar/03-reviewed-memory-payoff.png"
SDK="anthropic==1.17.0"
CABUNDLE=/root/.ccr/ca-bundle.crt

running() {
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then return 0; fi
  pgrep -f "$VENV/bin/python $STEER" >/dev/null 2>&1
}

if [ -z "$RECOVER_ONLY" ] && running; then
  echo "restore: v2 bot already running (pid $(cat "$PIDFILE" 2>/dev/null || pgrep -f "$VENV/bin/python $STEER" | head -1))"
  exit 0
fi

# (a) recover any missing committed file from git (design-plans/tools/planner_bot/ on the branch).
missing=
for f in $FILES; do [ -s "$DIR/$f" ] || missing="$missing $f"; done
if [ -n "$missing" ]; then
  mkdir -p "$DIR/northstar"
  if [ ! -d "$REPO_DIR/.git" ]; then
    gh repo clone KumarNavish/casepath "$REPO_DIR" >/dev/null 2>&1 || git clone https://github.com/KumarNavish/casepath "$REPO_DIR" >/dev/null 2>&1
  fi
  git -C "$REPO_DIR" fetch origin "$BRANCH" >/dev/null 2>&1
  for f in $missing; do
    if git -C "$REPO_DIR" show "origin/$BRANCH:$TOOLSUBDIR/$f" > "$DIR/$f.tmp" 2>/dev/null; then
      mv "$DIR/$f.tmp" "$DIR/$f"
    else
      rm -f "$DIR/$f.tmp"
    fi
  done
  chmod +x "$DIR/steer.py" "$DIR/restore.sh" "$DIR/stop.sh" "$DIR/test_steer.py" 2>/dev/null || true
fi
for f in $FILES; do
  if [ ! -s "$DIR/$f" ]; then
    echo "restore: FAILED — $f missing and not recoverable from git ($BRANCH:$TOOLSUBDIR)"
    exit 1
  fi
done
if [ -n "$RECOVER_ONLY" ]; then
  echo "restore: recovered${missing:- nothing (all present)} into $DIR"
  exit 0
fi

# (b) never run beside v1.
if pgrep -f "$V1_PATTERN" >/dev/null 2>&1; then
  echo "restore: REFUSED — v1 bot is still running; stop it before starting v2"
  exit 1
fi

# (c) create the venv with the SDK version v1 ran, if missing.
if [ ! -x "$PY" ] || ! "$PY" -c "import anthropic" 2>/dev/null; then
  [ -x "$PY" ] || python3 -m venv "$VENV" >/dev/null 2>&1
  SSL_CERT_FILE="$CABUNDLE" PIP_CERT="$CABUNDLE" "$PY" -m pip install --quiet "$SDK" >/dev/null 2>&1
fi
if ! "$PY" -c "import anthropic" 2>/dev/null; then
  echo "restore: FAILED — could not install $SDK into $VENV"
  exit 1
fi

# (d) the key: point the bot at the existing key file; never read, mine or copy it.
if [ ! -s "$KEYFILE" ]; then
  echo "restore: FAILED — key file $KEYFILE missing or empty (set STEER_KEY_FILE to the existing key file)"
  exit 1
fi

# (e) start the bot detached; the key file, not any inherited env key, is used.
cd "$DIR" || { echo "restore: FAILED — cannot cd $DIR"; exit 1; }
env -u ANTHROPIC_API_KEY SSL_CERT_FILE="$CABUNDLE" STEER_KEY_FILE="$KEYFILE" \
  setsid nohup "$PY" "$STEER" >> "$DIR/steer.out" 2>&1 < /dev/null &
sleep 2

# (f) one status line.
if running; then
  echo "restore: started v2 bot (pid $(cat "$PIDFILE" 2>/dev/null || pgrep -f "$VENV/bin/python $STEER" | head -1))"
else
  echo "restore: FAILED — bot did not come up; see $DIR/steer.out and $DIR/steer.log"
  exit 1
fi
