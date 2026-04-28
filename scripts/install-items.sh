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

sudo_step() {
  if [ "$MODE" = "apply" ]; then
    echo "+ sudo -n $*"
    sudo -n "$@"
  else
    echo "[skip] sudo -n $*"
  fi
}

require_sudo() {
  if [ "$MODE" != "apply" ]; then
    return 0
  fi

  if sudo -n true 2>/dev/null; then
    return 0
  fi

  cat <<'EOF'
sudo is not available non-interactively.

The web installer cannot type a sudo password. Run this once from a terminal:

  cd ~/gridrunner
  sudo scripts/setup-sudoers.sh

Then return to the web panel and install again.
EOF
  return 1
}

install_apt() {
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "apt-get not found; package install unavailable: $*"
    return 1
  fi

  require_sudo || return 1
  sudo_step apt-get update && sudo_step apt-get install -y "$@"
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

install_web_service() {
  local project_dir="${GRIDRUNNER_HOME:-$HOME/gridrunner}"
  local operator_user="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
  local operator_home="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"
  local device_hostname="${GRIDRUNNER_DEVICE_HOSTNAME:-$(hostname -s)}"
  local template="$project_dir/deploy/systemd/gridrunner-web.service"
  local rendered="$project_dir/state/gridrunner-web.service"

  if [ ! -f "$template" ]; then
    echo "service template not found: $template"
    return 1
  fi

  run_step mkdir -p "$project_dir/state" || return 1

  if [ "$MODE" = "apply" ]; then
    sed \
      -e "s|{{GRIDRUNNER_HOME}}|$project_dir|g" \
      -e "s|{{OPERATOR_USER}}|$operator_user|g" \
      -e "s|{{OPERATOR_HOME}}|$operator_home|g" \
      -e "s|{{DEVICE_HOSTNAME}}|$device_hostname|g" \
      "$template" > "$rendered" || return 1
    require_sudo || return 1
    sudo_step install -m 0644 "$rendered" /etc/systemd/system/gridrunner-web.service || return 1
  else
    echo "[skip] render $template -> $rendered"
    echo "[skip] sudo -n install -m 0644 $rendered /etc/systemd/system/gridrunner-web.service"
  fi

  sudo_step systemctl daemon-reload &&
    sudo_step systemctl enable gridrunner-web.service

  echo "gridrunner-web.service installed and enabled; restart the device or start the service after stopping the current web process."
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
    web-service)
      install_web_service
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
