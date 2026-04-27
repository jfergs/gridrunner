#!/bin/bash
set -u

MODE="dry-run"

if [ "${1:-}" = "--apply" ]; then
  MODE="apply"
  shift
elif [ "${1:-}" = "--dry-run" ]; then
  shift
fi

run_step() {
  if [ "$MODE" = "apply" ]; then
    echo "+ $*"
    "$@"
  else
    echo "[skip] $*"
  fi
}

record_result() {
  local item="$1"
  local result="$2"

  echo "GRIDRUNNER_INSTALL_RESULT item=$item status=$result"
}

install_apt() {
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "apt-get not found; package install unavailable: $*"
    return 1
  fi

  run_step sudo apt-get update && run_step sudo apt-get install -y "$@"
}

install_base_tools() {
  install_apt git curl jq tmux htop
}

install_web_runtime() {
  install_apt python3 python3-venv python3-pip
}

install_radio_tools() {
  install_apt rtl-sdr soapysdr-tools
}

install_adsb_tools() {
  install_apt readsb
}

install_wifi_tools() {
  install_apt network-manager
}

install_ham_tools() {
  install_apt flrig pat
}

install_operator_dirs() {
  local project_dir="${GRIDRUNNER_HOME:-$HOME/gridrunner}"

  run_step mkdir -p \
    "$project_dir/data" \
    "$project_dir/logs" \
    "$project_dir/state" \
    "$project_dir/radio" \
    "$project_dir/sdr"
}

if [ "$#" -eq 0 ]; then
  echo "No install items selected."
  exit 0
fi

for item in "$@"; do
  case "$item" in
    base-tools)
      install_base_tools
      ;;
    web-runtime)
      install_web_runtime
      ;;
    radio-tools)
      install_radio_tools
      ;;
    adsb-tools)
      install_adsb_tools
      ;;
    wifi-tools)
      install_wifi_tools
      ;;
    ham-tools)
      install_ham_tools
      ;;
    operator-dirs)
      install_operator_dirs
      ;;
    *)
      echo "Unknown install item: $item"
      exit 2
      ;;
  esac

  result=$?
  if [ "$MODE" = "dry-run" ]; then
    record_result "$item" planned
  elif [ "$result" -eq 0 ]; then
    record_result "$item" installed
  else
    record_result "$item" failed
  fi
done
