#!/bin/bash
set -u

CONFIG_FILE="${GRIDRUNNER_WIFI_CONFIG:-$HOME/.config/gridrunner/wifi-fallback.env}"

config_value() {
  local value="$1"

  case "$value" in
    \'*\')
      value="${value#\'}"
      value="${value%\'}"
      value="$(printf '%s' "$value" | sed "s/'\\\\''/'/g")"
      ;;
    \"*\")
      value="${value#\"}"
      value="${value%\"}"
      ;;
  esac

  printf '%s' "$value"
}

load_config() {
  local key=""
  local value=""

  [ -r "$CONFIG_FILE" ] || return 0

  while IFS='=' read -r key value; do
    case "$key" in
      IFACE|HOTSPOT|HOTSPOT_ALIASES)
        value="$(config_value "$value")"
        printf -v "$key" '%s' "$value"
        ;;
    esac
  done < "$CONFIG_FILE"
}

load_config

IFACE="${IFACE:-wlan0}"
HOTSPOT="${HOTSPOT:-GRIDRUNNER-HOTSPOT}"
HOTSPOT_ALIASES="${HOTSPOT_ALIASES:-Gridrunner-hotspot DEVICE-HOTSPOT}"
WIFI_ACTION_STATE="${GRIDRUNNER_WIFI_ACTION_STATE:-${GRIDRUNNER_STATE_DIR:-$HOME/gridrunner/state}/wifi-action.env}"
last_action="unknown"
last_action_at="0"

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

load_last_action() {
  local key=""
  local value=""

  if [ ! -r "$WIFI_ACTION_STATE" ]; then
    return
  fi

  while IFS='=' read -r key value; do
    case "$key" in
      GRIDRUNNER_WIFI_LAST_ACTION)
        last_action="$value"
        ;;
      GRIDRUNNER_WIFI_LAST_ACTION_AT)
        last_action_at="$value"
        ;;
    esac
  done < "$WIFI_ACTION_STATE"

  case "$last_action_at" in
    ''|*[!0-9]*)
      last_action_at=0
      ;;
  esac
}

last_action_age() {
  local now_seconds=""

  if [ "$last_action_at" = "0" ]; then
    printf 'unknown'
    return
  fi

  now_seconds="$(date +%s)"
  printf '%s' "$((now_seconds - last_action_at))"
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
load_last_action
last_action_age_seconds="$(last_action_age)"

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
  echo "GRIDRUNNER_WIFI status=$(field "$status") mode=$(field "$mode") device=$(field "$IFACE") state=$(field "$device_state") connection=$(field "$active_connection") ip=$(field "$ip_address") timer=$(field "$timer_state") timer_enabled=$(field "$timer_enabled") service=$(field "$service_active") last_action=$(field "$last_action") last_action_age_seconds=$(field "$last_action_age_seconds")"
else
  echo "GRIDRUNNER_WIFI status=$(field "$status") mode=$(field "$mode") device=$(field "$IFACE") state=$(field "$device_state") ip=$(field "$ip_address") timer=$(field "$timer_state") timer_enabled=$(field "$timer_enabled") service=$(field "$service_active") last_action=$(field "$last_action") last_action_age_seconds=$(field "$last_action_age_seconds")"
fi

echo "mode: $mode"
echo "device state: ${device_state:-unknown}"
if [ "${GRIDRUNNER_SHOW_IDENTIFIERS:-0}" = "1" ]; then
  echo "active connection: ${active_connection:-none}"
fi
echo "ip: ${ip_address:-unknown}"
echo "timer: $timer_state ($timer_enabled)"
echo "service: $service_active"
echo "last action: $last_action"
echo "last action age: ${last_action_age_seconds}s"
