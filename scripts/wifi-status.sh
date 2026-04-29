#!/bin/bash
set -u

CONFIG_FILE="${GRIDRUNNER_WIFI_CONFIG:-$HOME/.config/gridrunner/wifi-fallback.env}"
if [ -r "$CONFIG_FILE" ]; then
  # shellcheck disable=SC1090
  . "$CONFIG_FILE"
fi

IFACE="${IFACE:-wlan0}"
HOTSPOT="${HOTSPOT:-GRIDRUNNER-HOTSPOT}"
HOTSPOT_ALIASES="${HOTSPOT_ALIASES:-Gridrunner-hotspot DEVICE-HOTSPOT}"

field() {
  local value="$1"

  if [ -z "$value" ]; then
    printf 'unknown'
  else
    printf '%s' "$value" | tr ' ' '_'
  fi
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

service_state() {
  local unit="$1"

  if ! command -v systemctl >/dev/null 2>&1; then
    printf 'unknown'
    return
  fi

  systemctl is-active "$unit" 2>/dev/null || true
}

service_enabled() {
  local unit="$1"

  if ! command -v systemctl >/dev/null 2>&1; then
    printf 'unknown'
    return
  fi

  systemctl is-enabled "$unit" 2>/dev/null || true
}

if ! command -v nmcli >/dev/null 2>&1; then
  echo "GRIDRUNNER_WIFI status=missing detail=nmcli-not-found"
  echo "wifi tools missing: nmcli"
  exit 1
fi

device_line="$(nmcli -t -f DEVICE,STATE,CONNECTION dev 2>/dev/null | awk -F: -v iface="$IFACE" '$1 == iface {print; exit}')"
device_state="$(printf '%s' "$device_line" | awk -F: '{print $2}')"
active_connection="$(printf '%s' "$device_line" | awk -F: '{print $3}')"
ip_address="$(nmcli -g IP4.ADDRESS dev show "$IFACE" 2>/dev/null | head -1 | cut -d/ -f1)"
timer_state="$(service_state gridrunner-wifi.timer)"
timer_enabled="$(service_enabled gridrunner-wifi.timer)"
service_active="$(service_state gridrunner-wifi.service)"

mode="disconnected"
status="degraded"

if [ -n "$active_connection" ] && is_hotspot_name "$active_connection"; then
  mode="hotspot"
  status="present"
elif [ -n "$active_connection" ]; then
  mode="known-wifi"
  status="present"
elif [ "$device_state" = "connected" ]; then
  mode="connected"
  status="present"
fi

if [ "$timer_state" != "active" ] && [ "$timer_enabled" != "enabled" ]; then
  status="degraded"
fi

if [ "${GRIDRUNNER_SHOW_IDENTIFIERS:-0}" = "1" ]; then
  echo "GRIDRUNNER_WIFI status=$(field "$status") mode=$(field "$mode") device=$(field "$IFACE") state=$(field "$device_state") connection=$(field "$active_connection") ip=$(field "$ip_address") timer=$(field "$timer_state") timer_enabled=$(field "$timer_enabled") service=$(field "$service_active")"
else
  echo "GRIDRUNNER_WIFI status=$(field "$status") mode=$(field "$mode") device=$(field "$IFACE") state=$(field "$device_state") ip=$(field "$ip_address") timer=$(field "$timer_state") timer_enabled=$(field "$timer_enabled") service=$(field "$service_active")"
fi

echo "mode: $mode"
echo "device state: ${device_state:-unknown}"
if [ "${GRIDRUNNER_SHOW_IDENTIFIERS:-0}" = "1" ]; then
  echo "active connection: ${active_connection:-none}"
fi
echo "ip: ${ip_address:-unknown}"
echo "timer: $timer_state ($timer_enabled)"
echo "service: $service_active"
