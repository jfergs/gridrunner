#!/bin/bash
set -u

OPERATOR_USER="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
OPERATOR_HOME="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"
EVENTS_LOG="${GRIDRUNNER_EVENTS_LOG:-}"
MAX_BYTES="${GRIDRUNNER_EVENTS_LOG_MAX_BYTES:-5242880}"
KEEP="${GRIDRUNNER_EVENTS_LOG_KEEP:-5}"

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

file_size() {
  stat -c %s "$1" 2>/dev/null || stat -f %z "$1" 2>/dev/null || echo 0
}

EVENTS_LOG="$(resolve_events_log)"

if [ ! -e "$EVENTS_LOG" ]; then
  echo "GRIDRUNNER_LOG_ROTATE status=missing path=$EVENTS_LOG"
  echo "events log missing: $EVENTS_LOG"
  exit 0
fi

size="$(file_size "$EVENTS_LOG")"
if [ "$size" -lt "$MAX_BYTES" ]; then
  echo "GRIDRUNNER_LOG_ROTATE status=skipped size_bytes=$size max_bytes=$MAX_BYTES path=$EVENTS_LOG"
  exit 0
fi

stamp="$(date '+%Y%m%d-%H%M%S')"
rotated="$EVENTS_LOG.$stamp"
mv "$EVENTS_LOG" "$rotated" || exit 1
: > "$EVENTS_LOG" || exit 1
chmod 0664 "$EVENTS_LOG" 2>/dev/null || true

if command -v gzip >/dev/null 2>&1; then
  gzip -f "$rotated"
  rotated="$rotated.gz"
fi

find "$(dirname "$EVENTS_LOG")" -maxdepth 1 -name "$(basename "$EVENTS_LOG").*" -type f \
  | sort -r \
  | awk -v keep="$KEEP" 'NR > keep' \
  | while IFS= read -r old_log; do
      rm -f "$old_log"
    done

echo "GRIDRUNNER_LOG_ROTATE status=rotated size_bytes=$size path=$EVENTS_LOG rotated=$rotated"
