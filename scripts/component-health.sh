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
check_radio_tools
check_adsb_tools
check_ham_tools
