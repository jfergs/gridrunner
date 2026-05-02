#!/bin/bash
set -u

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "$script_dir/.." && pwd)"
STATE_FILE="${GRIDRUNNER_SCAN_STATE_FILE:-$project_dir/state/scan-controls.env}"
PRESENCE_INTERVAL_SECONDS="${GRIDRUNNER_PRESENCE_INTERVAL_SECONDS:-30}"
PRESENCE_SCAN_TIMEOUT_SECONDS="${GRIDRUNNER_PRESENCE_SCAN_TIMEOUT_SECONDS:-25}"
PRESENCE_RUN_ONCE="${GRIDRUNNER_PRESENCE_RUN_ONCE:-0}"

scan_network_mode="off"

load_scan_state() {
  local key=""
  local value=""

  scan_network_mode="${GRIDRUNNER_SCAN_NETWORK_MODE:-off}"
  if [ ! -f "$STATE_FILE" ]; then
    return
  fi

  while IFS='=' read -r key value; do
    case "$key" in
      GRIDRUNNER_SCAN_NETWORK_MODE)
        scan_network_mode="$value"
        ;;
    esac
  done < "$STATE_FILE"
}

network_scan_enabled() {
  load_scan_state
  [ "$scan_network_mode" = "continuous" ] || [ "${GRIDRUNNER_SCAN_NETWORK_ENABLED:-0}" = "1" ]
}

case "$PRESENCE_INTERVAL_SECONDS" in
  ''|*[!0-9]*)
    PRESENCE_INTERVAL_SECONDS=30
    ;;
esac

case "$PRESENCE_SCAN_TIMEOUT_SECONDS" in
  ''|*[!0-9]*)
    PRESENCE_SCAN_TIMEOUT_SECONDS=25
    ;;
esac

while true; do
  if network_scan_enabled; then
    if ! command -v arp-scan >/dev/null 2>&1; then
      echo "presence network scan skipped: arp-scan not found"
    elif command -v timeout >/dev/null 2>&1; then
      timeout "${PRESENCE_SCAN_TIMEOUT_SECONDS}s" arp-scan --localnet || true
    else
      arp-scan --localnet || true
    fi
  else
    echo "presence network scan skipped: network scans are off"
  fi

  [ "$PRESENCE_RUN_ONCE" = "1" ] && exit 0
  sleep "$PRESENCE_INTERVAL_SECONDS"
done
