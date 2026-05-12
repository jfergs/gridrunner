#!/bin/bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${GRIDRUNNER_HOME:-$(cd "$SCRIPT_DIR/.." && pwd)}"
STATE_DIR="${GRIDRUNNER_STATE_DIR:-$PROJECT_DIR/state}"
EDGE_NODE_STATE_DIR="${GRIDRUNNER_EDGE_NODE_STATE_DIR:-$STATE_DIR/edge-nodes}"

# shellcheck source=scripts/storage-common.sh
. "$SCRIPT_DIR/storage-common.sh"
gridrunner_read_storage_env

status_line() {
  local count=0
  local newest=0
  local now=0
  local file=""
  local mtime=0
  local status="missing"
  local age="unknown"

  if [ -d "$EDGE_NODE_STATE_DIR" ]; then
    for file in "$EDGE_NODE_STATE_DIR"/*.json; do
      [ -e "$file" ] || continue
      count=$((count + 1))
      mtime="$(stat -c %Y "$file" 2>/dev/null || stat -f %m "$file" 2>/dev/null || echo 0)"
      if [ "$mtime" -gt "$newest" ]; then
        newest="$mtime"
      fi
    done
  fi

  if [ "$count" -gt 0 ]; then
    now="$(date +%s)"
    age=$((now - newest))
    status="present"
    if [ "$age" -gt "${GRIDRUNNER_EDGE_NODE_STALE_SECONDS:-900}" ]; then
      status="stale"
    fi
  fi

  printf 'GRIDRUNNER_EDGE_NODES status=%s count=%s newest_age_seconds=%s state_dir=%s\n' \
    "$status" "$count" "$age" "$EDGE_NODE_STATE_DIR"
}

if [ "${1:-}" = "--status" ]; then
  status_line
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for edge-node ingest."
  exit 1
fi

payload_file="${1:--}"
payload="$(mktemp)"
trap 'rm -f "$payload"' EXIT

if [ "$payload_file" = "-" ]; then
  cat > "$payload"
else
  cat "$payload_file" > "$payload"
fi

validation_filter='
  .schema == "gridrunner.edge_node.v1"
  and (.node_id | type == "string" and length > 0)
  and (.profile | type == "string" and length > 0)
  and (.timestamp | type == "string" and length > 0)
  and (.battery.percent | type == "number")
  and (.link.transport | type == "string" and length > 0)
  and (.ble.window_seconds | type == "number")
  and (.ble.known_count | type == "number")
  and (.ble.unknown_count | type == "number")
  and (.ble.ignored_count | type == "number")
  and (.ble.rssi_peak | type == "number")
'

if ! jq -e "$validation_filter" "$payload" >/dev/null 2>&1; then
  echo "Invalid edge-node telemetry payload."
  exit 2
fi

node_id="$(jq -r '.node_id' "$payload")"
safe_node_id="$(printf '%s' "$node_id" | tr -c 'A-Za-z0-9_.-' '_')"
received_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
state_file="$EDGE_NODE_STATE_DIR/$safe_node_id.json"
events_log="$(gridrunner_storage_events_log)"

mkdir -p "$EDGE_NODE_STATE_DIR"
jq --arg received_at "$received_at" '. + {received_at: $received_at}' "$payload" > "$state_file.tmp" || exit 1
mv "$state_file.tmp" "$state_file"

mkdir -p "$(dirname "$events_log")"
printf '%s edge-node node=%s profile=%s transport=%s battery=%s ble_known=%s ble_unknown=%s ble_ignored=%s rssi_peak=%s\n' \
  "$received_at" \
  "$safe_node_id" \
  "$(jq -r '.profile' "$payload")" \
  "$(jq -r '.link.transport' "$payload")" \
  "$(jq -r '.battery.percent' "$payload")" \
  "$(jq -r '.ble.known_count' "$payload")" \
  "$(jq -r '.ble.unknown_count' "$payload")" \
  "$(jq -r '.ble.ignored_count' "$payload")" \
  "$(jq -r '.ble.rssi_peak' "$payload")" >> "$events_log"

printf 'GRIDRUNNER_EDGE_NODE_INGEST status=ok node=%s state_file=%s events_log=%s\n' \
  "$safe_node_id" "$state_file" "$events_log"
