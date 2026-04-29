#!/bin/bash
set -u

OPERATOR_USER="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
OPERATOR_HOME="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"
EVENT_TIMEOUT_SECONDS="${GRIDRUNNER_EVENTS_RUN_SECONDS:-75}"
EVENTS_LOG="${GRIDRUNNER_EVENTS_LOG:-$OPERATOR_HOME/$OPERATOR_USER-events.log}"

event_script=""
before_mtime="0"
after_mtime="0"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for candidate in \
  "$OPERATOR_HOME/$OPERATOR_USER-events.sh" \
  "$OPERATOR_HOME/operator-events.sh"; do
  if [ -f "$candidate" ]; then
    event_script="$candidate"
    break
  fi
done

if [ -z "$event_script" ]; then
  echo "events script not found for operator: $OPERATOR_USER"
  exit 1
fi

"$script_dir/rotate-logs.sh" >/dev/null 2>&1 || true

if [ -e "$EVENTS_LOG" ]; then
  before_mtime="$(stat -c %Y "$EVENTS_LOG" 2>/dev/null || stat -f %m "$EVENTS_LOG" 2>/dev/null || echo 0)"
fi

if command -v timeout >/dev/null 2>&1; then
  timeout "${EVENT_TIMEOUT_SECONDS}s" bash "$event_script"
  status=$?
else
  bash "$event_script"
  status=$?
fi

if [ "$status" -eq 124 ]; then
  echo "event collection timed out after ${EVENT_TIMEOUT_SECONDS}s"
fi

if [ -e "$EVENTS_LOG" ]; then
  after_mtime="$(stat -c %Y "$EVENTS_LOG" 2>/dev/null || stat -f %m "$EVENTS_LOG" 2>/dev/null || echo 0)"
fi

if [ "$status" -ne 0 ] && [ "$after_mtime" -gt "$before_mtime" ]; then
  echo "event collection updated log despite legacy script exit $status"
  exit 0
fi

exit "$status"
