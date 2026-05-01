#!/bin/bash
set -u

OPERATOR_USER="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
OPERATOR_HOME="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"
EVENT_TIMEOUT_SECONDS="${GRIDRUNNER_EVENTS_RUN_SECONDS:-75}"
EVENTS_LOG="${GRIDRUNNER_EVENTS_LOG:-$OPERATOR_HOME/$OPERATOR_USER-events.log}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "$script_dir/.." && pwd)"
STATE_FILE="${GRIDRUNNER_SCAN_STATE_FILE:-$project_dir/state/scan-controls.env}"
SCAN_INTERVAL_SECONDS="${GRIDRUNNER_SCAN_INTERVAL_SECONDS:-300}"
SCAN_BLUETOOTH_MODE="${GRIDRUNNER_SCAN_BLUETOOTH_MODE:-off}"
SCAN_NETWORK_MODE="${GRIDRUNNER_SCAN_NETWORK_MODE:-off}"
SCAN_LAST_RUN="${GRIDRUNNER_SCAN_LAST_RUN:-0}"
SCAN_RUN_ONCE="${GRIDRUNNER_SCAN_RUN_ONCE:-0}"

event_script=""
before_mtime="0"
after_mtime="0"
now_seconds="$(date +%s)"

if [ -f "$STATE_FILE" ]; then
  while IFS='=' read -r key value; do
    case "$key" in
      GRIDRUNNER_SCAN_INTERVAL_SECONDS)
        GRIDRUNNER_SCAN_INTERVAL_SECONDS="$value"
        ;;
      GRIDRUNNER_SCAN_BLUETOOTH_MODE)
        GRIDRUNNER_SCAN_BLUETOOTH_MODE="$value"
        ;;
      GRIDRUNNER_SCAN_NETWORK_MODE)
        GRIDRUNNER_SCAN_NETWORK_MODE="$value"
        ;;
      GRIDRUNNER_SCAN_LAST_RUN)
        GRIDRUNNER_SCAN_LAST_RUN="$value"
        ;;
    esac
  done < "$STATE_FILE"
fi

SCAN_INTERVAL_SECONDS="${GRIDRUNNER_SCAN_INTERVAL_SECONDS:-300}"
SCAN_BLUETOOTH_MODE="${GRIDRUNNER_SCAN_BLUETOOTH_MODE:-off}"
SCAN_NETWORK_MODE="${GRIDRUNNER_SCAN_NETWORK_MODE:-off}"
SCAN_LAST_RUN="${GRIDRUNNER_SCAN_LAST_RUN:-0}"
SCAN_RUN_ONCE="${GRIDRUNNER_SCAN_RUN_ONCE:-0}"

case "$SCAN_INTERVAL_SECONDS" in
  ''|*[!0-9]*)
    SCAN_INTERVAL_SECONDS=300
    ;;
esac

case "$SCAN_LAST_RUN" in
  ''|*[!0-9]*)
    SCAN_LAST_RUN=0
    ;;
esac

write_scan_state() {
  mkdir -p "$(dirname "$STATE_FILE")"
  {
    printf 'GRIDRUNNER_SCAN_BLUETOOTH_MODE=%s\n' "$SCAN_BLUETOOTH_MODE"
    printf 'GRIDRUNNER_SCAN_NETWORK_MODE=%s\n' "$SCAN_NETWORK_MODE"
    printf 'GRIDRUNNER_SCAN_INTERVAL_SECONDS=%s\n' "$SCAN_INTERVAL_SECONDS"
    printf 'GRIDRUNNER_SCAN_LAST_RUN=%s\n' "$1"
  } > "$STATE_FILE"
}

if [ "$SCAN_RUN_ONCE" != "1" ]; then
  if [ "$SCAN_BLUETOOTH_MODE" != "continuous" ] && [ "$SCAN_NETWORK_MODE" != "continuous" ]; then
    echo "event collection skipped: Bluetooth and network scans are off"
    exit 0
  fi

  if [ $((now_seconds - SCAN_LAST_RUN)) -lt "$SCAN_INTERVAL_SECONDS" ]; then
    echo "event collection skipped: next scan interval has not elapsed"
    exit 0
  fi
fi

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
  write_scan_state "$now_seconds"
  echo "event collection updated log despite legacy script exit $status"
  exit 0
fi

if [ "$status" -eq 0 ]; then
  write_scan_state "$now_seconds"
fi

exit "$status"
