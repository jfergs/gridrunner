#!/bin/bash
set -u

OPERATOR_USER="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
OPERATOR_HOME="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"
export OPERATOR_USER OPERATOR_HOME
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${GRIDRUNNER_HOME:-$(cd "$SCRIPT_DIR/.." && pwd)}"
GRIDRUNNER_HOME="$PROJECT_DIR"
EVENTS_LOG="${GRIDRUNNER_EVENTS_LOG:-}"
STALE_SECONDS="${GRIDRUNNER_EVENTS_STALE_SECONDS:-900}"

# shellcheck source=scripts/storage-common.sh
. "$PROJECT_DIR/scripts/storage-common.sh"
gridrunner_read_storage_env

resolve_events_log() {
  gridrunner_storage_events_log
}

EVENTS_LOG="$(resolve_events_log)"

if [ ! -e "$EVENTS_LOG" ]; then
  echo "GRIDRUNNER_EVENT_HEALTH status=missing detail=events-log-not-found"
  echo "events log missing: $EVENTS_LOG"
  exit 1
fi

if [ ! -r "$EVENTS_LOG" ]; then
  echo "GRIDRUNNER_EVENT_HEALTH status=degraded detail=events-log-not-readable"
  echo "events log not readable: $EVENTS_LOG"
  exit 1
fi

now="$(date +%s)"
mtime="$(stat -c %Y "$EVENTS_LOG" 2>/dev/null || stat -f %m "$EVENTS_LOG" 2>/dev/null || echo 0)"
age_seconds=$((now - mtime))

if [ "$age_seconds" -gt "$STALE_SECONDS" ]; then
  echo "GRIDRUNNER_EVENT_HEALTH status=stale age_seconds=$age_seconds detail=events-log-stale"
  echo "events log stale: ${age_seconds}s since last update"
  exit 1
fi

echo "GRIDRUNNER_EVENT_HEALTH status=fresh age_seconds=$age_seconds detail=events-log-fresh"
echo "events log fresh: ${age_seconds}s since last update"
