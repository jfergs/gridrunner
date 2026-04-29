#!/bin/bash
set -u

OPERATOR_USER="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
OPERATOR_HOME="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"
EVENTS_LOG="${GRIDRUNNER_EVENTS_LOG:-}"
STALE_SECONDS="${GRIDRUNNER_EVENTS_STALE_SECONDS:-86400}"

resolve_events_log() {
  if [ -n "$EVENTS_LOG" ]; then
    printf '%s\n' "$EVENTS_LOG"
    return
  fi

  if [ -e "$OPERATOR_HOME/$OPERATOR_USER-events.log" ]; then
    printf '%s\n' "$OPERATOR_HOME/$OPERATOR_USER-events.log"
    return
  fi

  if [ -e "$OPERATOR_HOME/operator-events.log" ]; then
    printf '%s\n' "$OPERATOR_HOME/operator-events.log"
    return
  fi

  printf '%s\n' "$OPERATOR_HOME/$OPERATOR_USER-events.log"
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
