#!/bin/bash
set -u

status_for_commands() {
  local missing=""
  local tool=""

  for tool in "$@"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      missing="$missing $tool"
    fi
  done

  if [ -z "$missing" ]; then
    echo "present"
  else
    echo "missing:${missing# }"
  fi
}

emit() {
  local item="$1"
  local status="$2"
  local detail="${3:-}"

  detail="${detail// /,}"

  echo "GRIDRUNNER_COMPONENT item=$item status=$status detail=$detail"
}

emit_command_health() {
  local item="$1"
  shift

  local status=""
  status="$(status_for_commands "$@")"
  if [ "$status" = "present" ]; then
    emit "$item" present ""
  else
    emit "$item" missing "${status#missing:}"
  fi
}

check_base_tools() {
  emit_command_health base-tools git curl jq tmux htop
}

check_web_runtime() {
  local status=""
  status="$(status_for_commands python3)"
  if [ "$status" != "present" ]; then
    emit web-runtime missing "${status#missing:}"
    return
  fi

  if python3 -m venv --help >/dev/null 2>&1; then
    emit web-runtime present ""
  else
    emit web-runtime missing "python3-venv"
  fi
}

check_operator_dirs() {
  local project_dir="${GRIDRUNNER_HOME:-$HOME/gridrunner}"
  local missing=""
  local dir=""

  for dir in data logs state radio sdr; do
    if [ ! -d "$project_dir/$dir" ]; then
      missing="$missing $dir"
    fi
  done

  if [ -z "$missing" ]; then
    emit operator-dirs present ""
  else
    emit operator-dirs missing "${missing# }"
  fi
}

check_web_service() {
  if ! command -v systemctl >/dev/null 2>&1; then
    emit web-service unknown "systemctl unavailable"
    return
  fi

  if systemctl is-active --quiet gridrunner-web.service; then
    emit web-service present "active"
  elif systemctl is-enabled --quiet gridrunner-web.service 2>/dev/null; then
    emit web-service degraded "enabled-not-active"
  else
    emit web-service missing "not-enabled"
  fi
}

check_events_service() {
  if ! command -v systemctl >/dev/null 2>&1; then
    emit events-service unknown "systemctl unavailable"
    return
  fi

  if systemctl is-active --quiet gridrunner-events.timer; then
    emit events-service present "timer-active"
  elif systemctl is-enabled --quiet gridrunner-events.timer 2>/dev/null; then
    emit events-service degraded "timer-enabled-not-active"
  else
    emit events-service missing "timer-not-enabled"
  fi
}

check_wifi_tools() {
  emit_command_health wifi-tools nmcli
}

check_edge_node_mqtt() {
  local missing=""
  local detail=""

  for tool in mosquitto_sub mosquitto_pub jq; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      missing="$missing $tool"
    fi
  done

  if [ -n "$missing" ]; then
    emit edge-node-mqtt missing "${missing# }"
    return
  fi

  if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet mosquitto.service; then
      detail="broker-active"
    elif systemctl is-enabled --quiet mosquitto.service 2>/dev/null; then
      emit edge-node-mqtt degraded "broker-enabled-not-active"
      return
    else
      emit edge-node-mqtt degraded "broker-not-enabled"
      return
    fi
  else
    detail="broker-unchecked"
  fi

  emit edge-node-mqtt present "$detail"
}

check_plane_tracker() {
  local project_dir="${GRIDRUNNER_HOME:-$HOME/gridrunner}"
  local script="$project_dir/scripts/adsb-plane-tracker.sh"

  if [ ! -x "$script" ]; then
    emit plane-tracker missing "adsb-plane-tracker.sh"
    return
  fi

  if ! command -v jq >/dev/null 2>&1; then
    emit plane-tracker missing "jq"
    return
  fi

  if ! command -v mosquitto_pub >/dev/null 2>&1; then
    emit plane-tracker missing "mosquitto_pub"
    return
  fi

  if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet gridrunner-plane-tracker.timer; then
      emit plane-tracker present "timer-active"
    elif systemctl is-enabled --quiet gridrunner-plane-tracker.timer 2>/dev/null; then
      emit plane-tracker degraded "timer-enabled-not-active"
    else
      emit plane-tracker degraded "timer-not-enabled"
    fi
    return
  fi

  emit plane-tracker present "timer-unchecked"
}

check_display_profile() {
  local item="$1"
  local expected_profile="$2"
  local project_dir="${GRIDRUNNER_HOME:-$HOME/gridrunner}"
  local state_file="${GRIDRUNNER_STATE_DIR:-$project_dir/state}/display.env"

  if [ ! -f "$state_file" ]; then
    emit "$item" missing "not-configured"
    return
  fi

  while IFS='=' read -r key value; do
    [ "$key" = "GRIDRUNNER_DISPLAY_PROFILE" ] || continue
    value="${value%\'}"
    value="${value#\'}"
    value="${value%\"}"
    value="${value#\"}"
    if [ "$value" = "$expected_profile" ]; then
      emit "$item" present "reboot-required"
      return
    fi
  done < "$state_file"

  emit "$item" missing "different-profile"
}

check_operator_display() {
  local project_dir="${GRIDRUNNER_HOME:-$HOME/gridrunner}"
  local state_file="${GRIDRUNNER_STATE_DIR:-$project_dir/state}/operator-display.env"

  if [ ! -f "$state_file" ]; then
    emit operator-display missing "not-configured"
    return
  fi

  if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-enabled --quiet gridrunner-operator-display.service 2>/dev/null; then
      emit operator-display present "service-enabled"
    else
      emit operator-display degraded "service-not-enabled"
    fi
    return
  fi

  emit operator-display present "service-unchecked"
}

check_radio_tools() {
  emit_command_health radio-tools rtl_test SoapySDRUtil
}

check_adsb_tools() {
  local output=""

  if ! command -v readsb >/dev/null 2>&1; then
    emit adsb-tools missing "readsb"
    return
  fi

  output="$(readsb --help 2>&1 || true)"
  if printf '%s\n' "$output" | grep -qi 'rtlsdr'; then
    emit adsb-tools present "rtl-supported"
  else
    emit adsb-tools degraded "no-rtl-support"
  fi
}

check_ham_tools() {
  emit_command_health ham-tools flrig pat
}

check_base_tools
check_web_runtime
check_operator_dirs
check_web_service
check_events_service
check_wifi_tools
check_edge_node_mqtt
check_plane_tracker
check_display_profile display-elecrow-rr050 elecrow-rr050
check_display_profile display-waveshare-5hdmi waveshare-5hdmi
check_display_profile display-raspberrypi-touch raspberrypi-touch
check_operator_display
check_radio_tools
check_adsb_tools
check_ham_tools
