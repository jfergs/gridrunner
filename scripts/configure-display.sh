#!/bin/bash
set -u

PROFILE="${1:-}"
MODE="${GRIDRUNNER_DISPLAY_MODE:-apply}"
PROJECT_DIR="${GRIDRUNNER_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
STATE_DIR="${GRIDRUNNER_STATE_DIR:-$PROJECT_DIR/state}"
BOOT_CONFIG="${GRIDRUNNER_BOOT_CONFIG:-}"
VENDOR_DRIVER="${GRIDRUNNER_DISPLAY_VENDOR_DRIVER:-0}"
LCD_SHOW_URL="${GRIDRUNNER_LCD_SHOW_URL:-https://github.com/waveshareteam/LCD-show.git}"
LCD_SHOW_DIR="${GRIDRUNNER_LCD_SHOW_DIR:-$STATE_DIR/LCD-show}"

usage() {
  cat <<'EOF'
Usage: configure-display.sh <profile>

Profiles:
  elecrow-rr050          Elecrow RR050 5-inch 800x480 HDMI/GPIO touch display.
  waveshare-5hdmi       Waveshare 5-inch 800x480 HDMI/GPIO touch display.
  raspberrypi-touch     Official Raspberry Pi Touch Display.

Set GRIDRUNNER_DISPLAY_MODE=dry-run to preview changes.
Set GRIDRUNNER_DISPLAY_VENDOR_DRIVER=1 to run the vendor LCD-show helper for
Elecrow/Waveshare HDMI touch profiles after the managed boot config is applied.
EOF
}

if [ -z "$PROFILE" ]; then
  usage
  exit 2
fi

run_step() {
  if [ "$MODE" = "dry-run" ]; then
    echo "[skip] $*"
  else
    echo "+ $*"
    "$@"
  fi
}

write_file() {
  local path="$1"
  local content="$2"

  if [ "$MODE" = "dry-run" ]; then
    echo "[skip] write $path"
  else
    printf '%s\n' "$content" > "$path"
  fi
}

detect_boot_config() {
  if [ -n "$BOOT_CONFIG" ]; then
    printf '%s\n' "$BOOT_CONFIG"
  elif [ -f /boot/firmware/config.txt ]; then
    printf '%s\n' /boot/firmware/config.txt
  else
    printf '%s\n' /boot/config.txt
  fi
}

managed_config_block() {
  cat <<'EOF'
# BEGIN GRIDRUNNER display profile
# HDMI 800x480 panel profile for compact Raspberry Pi touch displays.
hdmi_group=2
hdmi_mode=87
hdmi_cvt=800 480 60 6 0 0 0
hdmi_drive=2
# END GRIDRUNNER display profile
EOF
}

apply_managed_block() {
  local config_file="$1"
  local temp_file=""

  if [ "$MODE" = "dry-run" ]; then
    echo "[skip] update $config_file with managed GRIDRUNNER display block"
    return 0
  fi

  mkdir -p "$(dirname "$config_file")"
  touch "$config_file"
  temp_file="$(mktemp)"
  awk '
    /^# BEGIN GRIDRUNNER display profile$/ { skip = 1; next }
    /^# END GRIDRUNNER display profile$/ { skip = 0; next }
    !skip { print }
  ' "$config_file" > "$temp_file" || {
    rm -f "$temp_file"
    return 1
  }
  {
    cat "$temp_file"
    printf '\n'
    managed_config_block
  } > "$config_file"
  rm -f "$temp_file"
}

record_profile() {
  local profile="$1"
  local label="$2"
  local config_file="$3"

  run_step mkdir -p "$STATE_DIR" || return 1
  write_file "$STATE_DIR/display.env" "GRIDRUNNER_DISPLAY_PROFILE='$profile'
GRIDRUNNER_DISPLAY_LABEL='$label'
GRIDRUNNER_DISPLAY_BOOT_CONFIG='$config_file'
GRIDRUNNER_DISPLAY_REBOOT_REQUIRED=1"
}

run_lcd_show() {
  local helper="$1"

  if [ "$VENDOR_DRIVER" != "1" ]; then
    echo "Vendor LCD-show driver not run. Set GRIDRUNNER_DISPLAY_VENDOR_DRIVER=1 to opt in."
    return 0
  fi

  if [ "$MODE" = "dry-run" ]; then
    echo "[skip] git clone $LCD_SHOW_URL $LCD_SHOW_DIR"
    echo "[skip] bash $LCD_SHOW_DIR/$helper"
    return 0
  fi

  if [ ! -d "$LCD_SHOW_DIR/.git" ]; then
    git clone "$LCD_SHOW_URL" "$LCD_SHOW_DIR" || return 1
  fi
  git -C "$LCD_SHOW_DIR" pull --ff-only || return 1
  chmod -R u+rwX,go+rX "$LCD_SHOW_DIR" || return 1
  bash "$LCD_SHOW_DIR/$helper"
}

configure_hdmi_800x480() {
  local label="$1"
  local helper="$2"
  local config_file=""

  config_file="$(detect_boot_config)"
  apply_managed_block "$config_file" || return 1
  record_profile "$PROFILE" "$label" "$config_file" || return 1
  run_lcd_show "$helper" || return 1
  echo "$label configured. Reboot the device for display settings to take effect."
}

case "$PROFILE" in
  elecrow-rr050)
    configure_hdmi_800x480 "Elecrow RR050 5-inch HDMI touch" "LCD5-show"
    ;;
  waveshare-5hdmi)
    configure_hdmi_800x480 "Waveshare 5-inch HDMI LCD" "LCD5-show"
    ;;
  raspberrypi-touch)
    record_profile "$PROFILE" "Official Raspberry Pi Touch Display" "kernel-managed"
    echo "Official Raspberry Pi Touch Display selected. Raspberry Pi OS normally handles this DSI display without vendor driver scripts."
    ;;
  *)
    echo "Unknown display profile: $PROFILE"
    usage
    exit 2
    ;;
esac
