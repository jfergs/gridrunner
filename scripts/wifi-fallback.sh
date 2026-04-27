#!/bin/bash
set -u

IFACE="${IFACE:-wlan0}"
HOTSPOT="${HOTSPOT:-DEVICE-HOTSPOT}"
OPERATOR_LABEL="${OPERATOR_LABEL:-operator}"
LOG="${LOG:-$HOME/operator-events.log}"
SCAN_SETTLE_SECONDS="${SCAN_SETTLE_SECONDS:-5}"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $OPERATOR_LABEL: wifi: $1" | tee -a "$LOG"
}

nm() {
  nmcli "$@"
}

wait_for_networkmanager() {
  local state=""

  for _ in 1 2 3 4 5 6; do
    state="$(nm -t -f RUNNING general 2>/dev/null || true)"
    [ "$state" = "running" ] && return 0
    sleep 5
  done

  log "NetworkManager is not ready"
  return 1
}

wifi_enabled() {
  local wifi_state=""

  wifi_state="$(nm -t -f WIFI general 2>/dev/null || true)"
  if [ "$wifi_state" != "enabled" ]; then
    log "wifi radio is $wifi_state; enabling"
    nm radio wifi on >/dev/null 2>&1 || return 1
    sleep 2
  fi

  return 0
}

current_connection() {
  nm -t -f NAME,DEVICE connection show --active 2>/dev/null \
    | awk -F: -v iface="$IFACE" '$2 == iface {print $1; exit}'
}

known_wifi_profiles() {
  nm -t -f NAME,TYPE connection show 2>/dev/null \
    | awk -F: -v hotspot="$HOTSPOT" '$2 == "802-11-wireless" && $1 != hotspot {print $1}'
}

profile_ssid() {
  local profile="$1"
  local ssid=""

  ssid="$(nm -g 802-11-wireless.ssid connection show "$profile" 2>/dev/null || true)"
  if [ -z "$ssid" ] || [ "$ssid" = "--" ]; then
    ssid="$profile"
  fi

  printf '%s\n' "$ssid"
}

scan_wifi() {
  nm dev wifi rescan ifname "$IFACE" >/dev/null 2>&1 || true
  sleep "$SCAN_SETTLE_SECONDS"
}

ssid_visible() {
  local ssid="$1"

  nm -t -f SSID dev wifi list ifname "$IFACE" 2>/dev/null | grep -Fxq "$ssid"
}

join_known_network() {
  local from_hotspot="${1:-no}"
  local profile=""
  local ssid=""

  while IFS= read -r profile; do
    [ -n "$profile" ] || continue

    ssid="$(profile_ssid "$profile")"
    [ -n "$ssid" ] || continue

    if ssid_visible "$ssid"; then
      if [ "${GRIDRUNNER_SHOW_IDENTIFIERS:-0}" = "1" ]; then
        log "joining known network: $ssid"
      else
        log "joining known network"
      fi
      if [ "$from_hotspot" = "yes" ]; then
        nm connection down "$HOTSPOT" >/dev/null 2>&1 || true
        sleep 2
      fi
      if nm connection up "$profile" >/dev/null 2>&1; then
        return 0
      fi
      if [ "${GRIDRUNNER_SHOW_IDENTIFIERS:-0}" = "1" ]; then
        log "failed to join known network: $ssid"
      else
        log "failed to join known network"
      fi
      if [ "$from_hotspot" = "yes" ]; then
        start_hotspot >/dev/null 2>&1 || true
      fi
    fi
  done < <(known_wifi_profiles)

  return 1
}

start_hotspot() {
  log "starting hotspot"

  nm connection down "$HOTSPOT" >/dev/null 2>&1 || true
  sleep 1

  if nm connection up "$HOTSPOT" >/dev/null 2>&1; then
    return 0
  fi

  log "failed to start hotspot profile: $HOTSPOT"
  return 1
}

main() {
  local current=""

  wait_for_networkmanager || exit 1
  wifi_enabled || {
    log "failed to enable wifi radio"
    exit 1
  }

  current="$(current_connection)"

  if [ -n "$current" ] && [ "$current" != "$HOTSPOT" ]; then
    if [ "${GRIDRUNNER_SHOW_IDENTIFIERS:-0}" = "1" ]; then
      echo "$OPERATOR_LABEL: wifi connected to $current"
    else
      echo "$OPERATOR_LABEL: wifi connected"
    fi
    exit 0
  fi

  if [ "$current" = "$HOTSPOT" ]; then
    echo "$OPERATOR_LABEL: hotspot active, scanning for known networks..."
    scan_wifi

    if join_known_network yes; then
      exit 0
    fi

    echo "$OPERATOR_LABEL: no known networks found, staying hotspot"
    exit 0
  fi

  echo "$OPERATOR_LABEL: disconnected, scanning known networks..."
  scan_wifi

  if join_known_network no; then
    exit 0
  fi

  log "no known wifi found"
  start_hotspot
}

main "$@"
