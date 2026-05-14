#!/bin/bash
set -u

MODE="dry-run"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

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

sudo_env_step() {
  if [ "$MODE" = "apply" ]; then
    echo "+ sudo -n env $*"
    sudo -n env "$@"
  else
    echo "[skip] sudo -n env $*"
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
  if [ "$MODE" != "apply" ]; then
    echo "[skip] install packages: $*"
    return 0
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    echo "apt-get not found; package install unavailable: $*"
    return 1
  fi

  require_sudo || return 1
  sudo_env_step DEBIAN_FRONTEND=noninteractive apt-get update &&
    sudo_env_step DEBIAN_FRONTEND=noninteractive apt-get install -y \
      -o Dpkg::Options::=--force-confdef \
      -o Dpkg::Options::=--force-confold \
      "$@"
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
  local project_dir="${GRIDRUNNER_HOME:-$DEFAULT_PROJECT_DIR}"

  if [ "$MODE" = "apply" ]; then
    require_sudo || return 1
    sudo_step bash "$project_dir/scripts/install-adsb-readsb.sh"
  else
    echo "[skip] sudo -n bash $project_dir/scripts/install-adsb-readsb.sh"
  fi
}

install_wifi_tools() {
  local project_dir="${GRIDRUNNER_HOME:-$DEFAULT_PROJECT_DIR}"

  if [ "$MODE" = "apply" ]; then
    "$project_dir/scripts/configure-wifi-hotspot.sh" || return 1
  else
    echo "[skip] configure fallback hotspot"
  fi
  install_apt network-manager
}

install_edge_node_mqtt() {
  local project_dir="${GRIDRUNNER_HOME:-$DEFAULT_PROJECT_DIR}"
  local operator_user="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
  local operator_home="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"
  local device_hostname="${GRIDRUNNER_DEVICE_HOSTNAME:-$(hostname -s)}"
  local state_dir="${GRIDRUNNER_STATE_DIR:-$project_dir/state}"
  local service_template="$project_dir/deploy/systemd/gridrunner-edge-node-ingest.service"
  local service_rendered="$project_dir/state/gridrunner-edge-node-ingest.service"

  install_apt mosquitto mosquitto-clients jq || return 1
  run_step mkdir -p "$state_dir/edge-nodes" "$project_dir/data/edge-nodes" || return 1

  if [ ! -f "$service_template" ]; then
    echo "edge-node ingest service template not found: $service_template"
    return 1
  fi

  if [ "$MODE" = "apply" ]; then
    render_template "$service_template" "$service_rendered" "$project_dir" "$operator_user" "$operator_home" "$device_hostname" || return 1
    require_sudo || return 1
    sudo_step install -m 0644 "$service_rendered" /etc/systemd/system/gridrunner-edge-node-ingest.service || return 1
  else
    echo "[skip] render $service_template -> $service_rendered"
    echo "[skip] sudo -n install -m 0644 $service_rendered /etc/systemd/system/gridrunner-edge-node-ingest.service"
  fi

  if [ "$MODE" = "dry-run" ] || command -v systemctl >/dev/null 2>&1; then
    sudo_step systemctl enable --now mosquitto.service || return 1
    sudo_step systemctl daemon-reload || return 1
    sudo_step systemctl enable --now gridrunner-edge-node-ingest.service || return 1
  fi

  echo "edge-node MQTT ingest installed and subscribed to gridrunner/nodes/+/telemetry."
}

install_plane_tracker() {
  local project_dir="${GRIDRUNNER_HOME:-$DEFAULT_PROJECT_DIR}"
  local operator_user="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
  local operator_home="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"
  local device_hostname="${GRIDRUNNER_DEVICE_HOSTNAME:-$(hostname -s)}"
  local service_template="$project_dir/deploy/systemd/gridrunner-plane-tracker.service"
  local timer_template="$project_dir/deploy/systemd/gridrunner-plane-tracker.timer"
  local service_rendered="$project_dir/state/gridrunner-plane-tracker.service"
  local timer_rendered="$project_dir/state/gridrunner-plane-tracker.timer"

  if [ "$MODE" = "apply" ]; then
    install_apt mosquitto-clients jq || return 1
  else
    echo "[skip] install packages: mosquitto-clients jq"
  fi

  if [ ! -f "$service_template" ]; then
    echo "plane tracker service template not found: $service_template"
    return 1
  fi
  if [ ! -f "$timer_template" ]; then
    echo "plane tracker timer template not found: $timer_template"
    return 1
  fi

  run_step mkdir -p "$project_dir/state" "$project_dir/data/adsb" || return 1

  if [ "$MODE" = "apply" ]; then
    render_template "$service_template" "$service_rendered" "$project_dir" "$operator_user" "$operator_home" "$device_hostname" || return 1
    render_template "$timer_template" "$timer_rendered" "$project_dir" "$operator_user" "$operator_home" "$device_hostname" || return 1
    require_sudo || return 1
    sudo_step install -m 0644 "$service_rendered" /etc/systemd/system/gridrunner-plane-tracker.service || return 1
    sudo_step install -m 0644 "$timer_rendered" /etc/systemd/system/gridrunner-plane-tracker.timer || return 1
  else
    echo "[skip] render $service_template -> $service_rendered"
    echo "[skip] render $timer_template -> $timer_rendered"
    echo "[skip] sudo -n install -m 0644 $service_rendered /etc/systemd/system/gridrunner-plane-tracker.service"
    echo "[skip] sudo -n install -m 0644 $timer_rendered /etc/systemd/system/gridrunner-plane-tracker.timer"
  fi

  sudo_step systemctl daemon-reload &&
    sudo_step systemctl enable --now gridrunner-plane-tracker.timer

  echo "gridrunner-plane-tracker.timer installed and enabled."
}

install_display_profile() {
  local profile="$1"
  local project_dir="${GRIDRUNNER_HOME:-$DEFAULT_PROJECT_DIR}"

  if [ "$MODE" = "apply" ]; then
    install_apt git evtest xinput || return 1
    require_sudo || return 1
    sudo_step env \
      GRIDRUNNER_HOME="$project_dir" \
      GRIDRUNNER_STATE_DIR="${GRIDRUNNER_STATE_DIR:-$project_dir/state}" \
      GRIDRUNNER_DISPLAY_VENDOR_DRIVER="${GRIDRUNNER_DISPLAY_VENDOR_DRIVER:-0}" \
      GRIDRUNNER_LCD_SHOW_URL="${GRIDRUNNER_LCD_SHOW_URL:-https://github.com/waveshareteam/LCD-show.git}" \
      /usr/bin/bash "$project_dir/scripts/configure-display.sh" "$profile" || return 1
  else
    echo "[skip] install packages: git evtest xinput"
    echo "[skip] sudo -n env GRIDRUNNER_HOME=$project_dir GRIDRUNNER_STATE_DIR=${GRIDRUNNER_STATE_DIR:-$project_dir/state} GRIDRUNNER_DISPLAY_VENDOR_DRIVER=${GRIDRUNNER_DISPLAY_VENDOR_DRIVER:-0} GRIDRUNNER_LCD_SHOW_URL=${GRIDRUNNER_LCD_SHOW_URL:-https://github.com/waveshareteam/LCD-show.git} /usr/bin/bash $project_dir/scripts/configure-display.sh $profile"
  fi
}

install_operator_display() {
  local project_dir="${GRIDRUNNER_HOME:-$DEFAULT_PROJECT_DIR}"
  local operator_user="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
  local operator_home="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"
  local device_hostname="${GRIDRUNNER_DEVICE_HOSTNAME:-$(hostname -s)}"
  local display_mode="${GRIDRUNNER_OPERATOR_DISPLAY_MODE:-web}"
  local service_template="$project_dir/deploy/systemd/gridrunner-operator-display.service"
  local service_rendered="$project_dir/state/gridrunner-operator-display.service"

  if [ "$MODE" = "apply" ]; then
    install_apt tmux unclutter chromium-browser || return 1
  else
    echo "[skip] install packages: tmux unclutter chromium-browser"
  fi

  if [ ! -f "$service_template" ]; then
    echo "operator display service template not found: $service_template"
    return 1
  fi

  run_step mkdir -p "$project_dir/state" || return 1

  if [ "$MODE" = "apply" ]; then
    bash "$project_dir/scripts/operator-display.sh" configure "$display_mode" || return 1
    render_template "$service_template" "$service_rendered" "$project_dir" "$operator_user" "$operator_home" "$device_hostname" || return 1
    require_sudo || return 1
    sudo_step install -m 0644 "$service_rendered" /etc/systemd/system/gridrunner-operator-display.service || return 1
  else
    echo "[skip] bash $project_dir/scripts/operator-display.sh configure $display_mode"
    echo "[skip] render $service_template -> $service_rendered"
    echo "[skip] sudo -n install -m 0644 $service_rendered /etc/systemd/system/gridrunner-operator-display.service"
  fi

  sudo_step systemctl daemon-reload &&
    sudo_step systemctl enable gridrunner-operator-display.service

  echo "gridrunner-operator-display.service installed. Start it after a graphical session is available, or reboot into the local display."
}

install_ham_tools() {
  install_apt flrig pat
}

install_operator_dirs() {
  local project_dir="${GRIDRUNNER_HOME:-$DEFAULT_PROJECT_DIR}"

  run_step mkdir -p \
    "$project_dir/data" \
    "$project_dir/data/adsb" \
    "$project_dir/data/edge-nodes" \
    "$project_dir/data/media" \
    "$project_dir/logs" \
    "$project_dir/state" \
    "$project_dir/state/edge-nodes" \
    "$project_dir/radio" \
    "$project_dir/sdr"
}

install_web_service() {
  local project_dir="${GRIDRUNNER_HOME:-$DEFAULT_PROJECT_DIR}"
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

render_template() {
  local template="$1"
  local rendered="$2"
  local project_dir="$3"
  local operator_user="$4"
  local operator_home="$5"
  local device_hostname="$6"

  sed \
    -e "s|{{GRIDRUNNER_HOME}}|$project_dir|g" \
    -e "s|{{OPERATOR_USER}}|$operator_user|g" \
    -e "s|{{OPERATOR_HOME}}|$operator_home|g" \
    -e "s|{{DEVICE_HOSTNAME}}|$device_hostname|g" \
    "$template" > "$rendered"
}

install_events_service() {
  local project_dir="${GRIDRUNNER_HOME:-$DEFAULT_PROJECT_DIR}"
  local operator_user="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
  local operator_home="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"
  local device_hostname="${GRIDRUNNER_DEVICE_HOSTNAME:-$(hostname -s)}"
  local service_template="$project_dir/deploy/systemd/gridrunner-events.service"
  local timer_template="$project_dir/deploy/systemd/gridrunner-events.timer"
  local service_rendered="$project_dir/state/gridrunner-events.service"
  local timer_rendered="$project_dir/state/gridrunner-events.timer"
  local event_script="$operator_home/$operator_user-events.sh"

  if [ ! -f "$service_template" ]; then
    echo "events service template not found: $service_template"
    return 1
  fi
  if [ ! -f "$timer_template" ]; then
    echo "events timer template not found: $timer_template"
    return 1
  fi

  if [ "$MODE" = "apply" ] && [ ! -f "$event_script" ]; then
    echo "events script not found: $event_script"
    return 1
  fi

  run_step mkdir -p "$project_dir/state" || return 1

  if [ "$MODE" = "apply" ]; then
    bash "$project_dir/scripts/patch-events-script.sh" "$event_script" || return 1
    render_template "$service_template" "$service_rendered" "$project_dir" "$operator_user" "$operator_home" "$device_hostname" || return 1
    render_template "$timer_template" "$timer_rendered" "$project_dir" "$operator_user" "$operator_home" "$device_hostname" || return 1
    require_sudo || return 1
    sudo_step install -m 0644 "$service_rendered" /etc/systemd/system/gridrunner-events.service || return 1
    sudo_step install -m 0644 "$timer_rendered" /etc/systemd/system/gridrunner-events.timer || return 1
  else
    echo "[skip] render $service_template -> $service_rendered"
    echo "[skip] render $timer_template -> $timer_rendered"
    echo "[skip] bash $project_dir/scripts/patch-events-script.sh $event_script"
    echo "[skip] sudo -n install -m 0644 $service_rendered /etc/systemd/system/gridrunner-events.service"
    echo "[skip] sudo -n install -m 0644 $timer_rendered /etc/systemd/system/gridrunner-events.timer"
  fi

  sudo_step systemctl daemon-reload &&
    sudo_step systemctl enable --now gridrunner-events.timer

  echo "gridrunner-events.timer installed and enabled."
}

install_presence_script() {
  local project_dir="${GRIDRUNNER_HOME:-$DEFAULT_PROJECT_DIR}"
  local operator_user="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
  local operator_home="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"
  local source_script="$project_dir/scripts/ghost-presence.sh"
  local installed_script="$operator_home/$operator_user-presence.sh"

  if [ ! -f "$source_script" ]; then
    echo "presence script not found: $source_script"
    return 1
  fi

  run_step install -m 0755 "$source_script" "$installed_script"
  echo "presence script installed: $installed_script"
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
    edge-node-mqtt)
      install_edge_node_mqtt
      ;;
    plane-tracker)
      install_plane_tracker
      ;;
    display-elecrow-rr050)
      install_display_profile elecrow-rr050
      ;;
    display-waveshare-5hdmi)
      install_display_profile waveshare-5hdmi
      ;;
    display-raspberrypi-touch)
      install_display_profile raspberrypi-touch
      ;;
    operator-display)
      install_operator_display
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
    events-service)
      install_events_service
      ;;
    presence-script)
      install_presence_script
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
