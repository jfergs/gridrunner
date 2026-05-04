#!/bin/bash
set -u

OPERATOR_USER="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
OPERATOR_HOME="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"
export OPERATOR_USER OPERATOR_HOME
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${GRIDRUNNER_HOME:-$(cd "$SCRIPT_DIR/.." && pwd)}"
GRIDRUNNER_HOME="$PROJECT_DIR"
EVENTS_LOG="${GRIDRUNNER_EVENTS_LOG:-}"
MAX_BYTES="${GRIDRUNNER_EVENTS_LOG_MAX_BYTES:-5242880}"
KEEP="${GRIDRUNNER_EVENTS_LOG_KEEP:-5}"

# shellcheck source=scripts/storage-common.sh
. "$PROJECT_DIR/scripts/storage-common.sh"
gridrunner_read_storage_env

resolve_events_log() {
  gridrunner_storage_events_log
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
