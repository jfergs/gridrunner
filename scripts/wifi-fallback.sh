#!/bin/bash
set -u

IFACE="${IFACE:-wlan0}"
HOTSPOT="${HOTSPOT:-GRIDRUNNER-HOTSPOT}"
HOTSPOT_SSID="${HOTSPOT_SSID:-$HOTSPOT}"
HOTSPOT_PASSWORD="${HOTSPOT_PASSWORD:-}"
HOTSPOT_ALIASES="${HOTSPOT_ALIASES:-Gridrunner-hotspot DEVICE-HOTSPOT}"
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
  local name=""
  local type=""

  while IFS=: read -r name type; do
    [ "$type" = "802-11-wireless" ] || continue
    is_hotspot_name "$name" && continue
    printf '%s\n' "$name"
  done < <(nm -t -f NAME,TYPE connection show 2>/dev/null)
}

is_hotspot_name() {
  local name="$1"
  local alias=""

  [ "$name" = "$HOTSPOT" ] && return 0
  for alias in $HOTSPOT_ALIASES; do
    [ "$name" = "$alias" ] && return 0
  done

  return 1
}

hotspot_profile_exists() {
  local profile="$1"

  nm -t -f NAME connection show 2>/dev/null | grep -Fxq "$profile"
}

hotspot_profile_name() {
  local alias=""

  if hotspot_profile_exists "$HOTSPOT"; then
    printf '%s\n' "$HOTSPOT"
    return 0
  fi

  for alias in $HOTSPOT_ALIASES; do
    if hotspot_profile_exists "$alias"; then
      printf '%s\n' "$alias"
      return 0
    fi
  done

  printf '%s\n' "$HOTSPOT"
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
        nm connection down "$(hotspot_profile_name)" >/dev/null 2>&1 || true
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
  local output=""
  local profile=""

  log "starting hotspot"

  profile="$(hotspot_profile_name)"
  ensure_hotspot_profile "$profile" || return 1

  nm connection down "$profile" >/dev/null 2>&1 || true
  sleep 1

  if output="$(nm connection up "$profile" 2>&1)"; then
    return 0
  fi

  log "failed to start hotspot profile: $profile"
  log "$output"
  return 1
}

ensure_hotspot_profile() {
  local output=""
  local profile="${1:-$HOTSPOT}"

  if hotspot_profile_exists "$profile"; then
    if ! output="$(nm connection modify "$profile" \
      connection.autoconnect no \
      connection.interface-name "$IFACE" \
      802-11-wireless.mode ap \
      802-11-wireless.ssid "$HOTSPOT_SSID" \
      ipv4.method shared \
      ipv6.method disabled 2>&1)"; then
      log "failed to update hotspot profile: $profile"
      log "$output"
      return 1
    fi
    if [ -n "$HOTSPOT_PASSWORD" ]; then
      if ! output="$(nm connection modify "$profile" \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "$HOTSPOT_PASSWORD" 2>&1)"; then
        log "failed to update hotspot password: $profile"
        log "$output"
        return 1
      fi
    fi
    return 0
  fi

  if [ -z "$HOTSPOT_PASSWORD" ]; then
    log "hotspot profile missing: $HOTSPOT"
    log "set HOTSPOT_PASSWORD, then rerun to create the profile"
    return 1
  fi

  if [ "${#HOTSPOT_PASSWORD}" -lt 8 ]; then
    log "HOTSPOT_PASSWORD must be at least 8 characters"
    return 1
  fi

  log "creating hotspot profile: $HOTSPOT"
  if output="$(nm connection add \
    type wifi \
    ifname "$IFACE" \
    con-name "$HOTSPOT" \
    ssid "$HOTSPOT_SSID" \
    802-11-wireless.mode ap \
    802-11-wireless.band bg \
    ipv4.method shared \
    ipv6.method disabled \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$HOTSPOT_PASSWORD" \
    connection.autoconnect no 2>&1)"; then
    return 0
  fi

  log "failed to create hotspot profile: $HOTSPOT"
  log "$output"
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

  if [ -n "$current" ] && ! is_hotspot_name "$current"; then
    if [ "${GRIDRUNNER_SHOW_IDENTIFIERS:-0}" = "1" ]; then
      echo "$OPERATOR_LABEL: wifi connected to $current"
    else
      echo "$OPERATOR_LABEL: wifi connected"
    fi
    exit 0
  fi

  if [ -n "$current" ] && is_hotspot_name "$current"; then
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
