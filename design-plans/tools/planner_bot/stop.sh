#!/usr/bin/env bash
# Stop ONLY the planner bot v2, by its PID file. Never uses pkill -f patterns that could
# match this shell or v1. Prints one status line.
set -u

DIR=/tmp/claude-0/-home-user/e812972b-ebf3-51a0-bcb0-c18d7b98dee7/scratchpad/steer2
PIDFILE="$DIR/steer.pid"

if [ ! -f "$PIDFILE" ]; then
  echo "stop: no pid file at $PIDFILE; v2 bot not tracked as running"
  exit 0
fi

PID=$(cat "$PIDFILE" 2>/dev/null)
if [ -z "$PID" ] || ! kill -0 "$PID" 2>/dev/null; then
  echo "stop: pid $PID not alive; removing stale pid file"
  rm -f "$PIDFILE"
  exit 0
fi

# Confirm the pid really is our v2 steer.py before signalling it.
if ! tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null | grep -q "$DIR/steer.py"; then
  echo "stop: pid $PID does not look like the v2 bot; leaving it alone"
  exit 1
fi

kill "$PID" 2>/dev/null
for _ in 1 2 3 4 5; do
  kill -0 "$PID" 2>/dev/null || break
  sleep 1
done
if kill -0 "$PID" 2>/dev/null; then
  kill -9 "$PID" 2>/dev/null
fi
rm -f "$PIDFILE"
echo "stop: stopped v2 bot (pid $PID)"
