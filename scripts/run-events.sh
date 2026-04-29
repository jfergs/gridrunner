#!/bin/bash
set -u

OPERATOR_USER="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
OPERATOR_HOME="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"
EVENT_TIMEOUT_SECONDS="${GRIDRUNNER_EVENTS_RUN_SECONDS:-75}"

event_script=""

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

exit "$status"
