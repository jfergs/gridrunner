#!/bin/bash
set -u

COMMAND="${1:-status}"
MODE="${2:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${GRIDRUNNER_HOME:-$(cd "$SCRIPT_DIR/.." && pwd)}"
STATE_DIR="${GRIDRUNNER_STATE_DIR:-$PROJECT_DIR/state}"
STATE_FILE="${GRIDRUNNER_OPERATOR_DISPLAY_STATE:-$STATE_DIR/operator-display.env}"
DEVICE_HOSTNAME="${GRIDRUNNER_DEVICE_HOSTNAME:-$(hostname -s 2>/dev/null || echo gridrunner)}"
WEB_URL="${GRIDRUNNER_OPERATOR_DISPLAY_WEB_URL:-http://$DEVICE_HOSTNAME.local:8088}"
ADSB_URL="${GRIDRUNNER_OPERATOR_DISPLAY_ADSB_URL:-http://$DEVICE_HOSTNAME.local/tar1090/}"
TMUX_SESSION="${GRIDRUNNER_OPERATOR_DISPLAY_TMUX_SESSION:-gridrunner}"

usage() {
  cat <<'EOF'
Usage: operator-display.sh <command> [mode]

Commands:
  configure <web|adsb|tmux|off>   Save the startup display mode.
  launch                          Launch the configured display mode.
  status                          Print the configured display mode.

Environment overrides:
  GRIDRUNNER_OPERATOR_DISPLAY_WEB_URL
  GRIDRUNNER_OPERATOR_DISPLAY_ADSB_URL
  GRIDRUNNER_OPERATOR_DISPLAY_TMUX_SESSION
EOF
}

load_state() {
  OPERATOR_DISPLAY_MODE="web"
  OPERATOR_DISPLAY_WEB_URL="$WEB_URL"
  OPERATOR_DISPLAY_ADSB_URL="$ADSB_URL"
  OPERATOR_DISPLAY_TMUX_SESSION="$TMUX_SESSION"

  if [ -f "$STATE_FILE" ]; then
    # shellcheck disable=SC1090
    . "$STATE_FILE"
  fi
}

save_state() {
  local mode="$1"

  mkdir -p "$STATE_DIR" || return 1
  cat > "$STATE_FILE" <<EOF
OPERATOR_DISPLAY_MODE='$mode'
OPERATOR_DISPLAY_WEB_URL='$WEB_URL'
OPERATOR_DISPLAY_ADSB_URL='$ADSB_URL'
OPERATOR_DISPLAY_TMUX_SESSION='$TMUX_SESSION'
EOF
}

browser_command() {
  if command -v chromium-browser >/dev/null 2>&1; then
    printf '%s\n' chromium-browser
  elif command -v chromium >/dev/null 2>&1; then
    printf '%s\n' chromium
  elif command -v firefox >/dev/null 2>&1; then
    printf '%s\n' firefox
  else
    return 1
  fi
}

detect_x_display() {
  local display=""
  local socket=""

  if [ -n "${DISPLAY:-}" ] && [ -S "/tmp/.X11-unix/X${DISPLAY#:}" ]; then
    return 0
  fi

  display="$(ps -u "$(id -un)" -o args= 2>/dev/null | sed -n 's/.*Xorg \(:[0-9][0-9]*\).*/\1/p' | head -n 1)"
  if [ -z "$display" ]; then
    display="$(ps -eo args= 2>/dev/null | sed -n 's/.*Xorg \(:[0-9][0-9]*\).*/\1/p' | head -n 1)"
  fi
  if [ -n "$display" ]; then
    export DISPLAY="$display"
    return 0
  fi

  for socket in /tmp/.X11-unix/X*; do
    if [ -S "$socket" ]; then
      export DISPLAY=":${socket##*X}"
      return 0
    fi
  done

  return 1
}

launch_browser() {
  local url="$1"
  local browser=""

  detect_x_display || {
    echo "No local X display found. Start the graphical session or use tmux display mode."
    return 1
  }

  browser="$(browser_command)" || {
    echo "No supported browser found. Install chromium-browser, chromium, or firefox."
    return 1
  }

  echo "Launching operator display on DISPLAY=$DISPLAY url=$url"

  if command -v unclutter >/dev/null 2>&1; then
    unclutter -idle 1 >/dev/null 2>&1 &
  fi

  exec "$browser" \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --check-for-update-interval=31536000 \
    "$url"
}

launch_tmux() {
  if ! command -v tmux >/dev/null 2>&1; then
    echo "tmux is required for operator display tmux mode."
    return 1
  fi

  tmux has-session -t "$OPERATOR_DISPLAY_TMUX_SESSION" 2>/dev/null || {
    tmux new-session -d -s "$OPERATOR_DISPLAY_TMUX_SESSION" -n ops "$PROJECT_DIR/scripts/system-health.sh"
    tmux split-window -h -t "$OPERATOR_DISPLAY_TMUX_SESSION:ops" "$PROJECT_DIR/scripts/adsb-health.sh"
    tmux split-window -v -t "$OPERATOR_DISPLAY_TMUX_SESSION:ops.1" "$PROJECT_DIR/scripts/event-health.sh"
    tmux select-layout -t "$OPERATOR_DISPLAY_TMUX_SESSION:ops" tiled
    tmux set-option -t "$OPERATOR_DISPLAY_TMUX_SESSION" status on
    tmux set-option -t "$OPERATOR_DISPLAY_TMUX_SESSION" status-left " GRIDRUNNER "
    tmux set-option -t "$OPERATOR_DISPLAY_TMUX_SESSION" status-right " %H:%M "
  }

  exec tmux attach-session -t "$OPERATOR_DISPLAY_TMUX_SESSION"
}

emit_status() {
  local configured="0"
  if [ -f "$STATE_FILE" ]; then
    configured="1"
  fi
  load_state
  echo "GRIDRUNNER_OPERATOR_DISPLAY mode=$OPERATOR_DISPLAY_MODE configured=$configured state_file=$STATE_FILE web_url=$OPERATOR_DISPLAY_WEB_URL adsb_url=$OPERATOR_DISPLAY_ADSB_URL"
}

case "$COMMAND" in
  configure)
    case "$MODE" in
      web|adsb|tmux|off)
        save_state "$MODE"
        emit_status
        ;;
      *)
        echo "Unknown operator display mode: $MODE"
        usage
        exit 2
        ;;
    esac
    ;;
  launch)
    load_state
    case "$OPERATOR_DISPLAY_MODE" in
      web)
        launch_browser "$OPERATOR_DISPLAY_WEB_URL"
        ;;
      adsb)
        launch_browser "$OPERATOR_DISPLAY_ADSB_URL"
        ;;
      tmux)
        launch_tmux
        ;;
      off)
        echo "Operator display mode is off."
        exit 0
        ;;
      *)
        echo "Unknown configured operator display mode: $OPERATOR_DISPLAY_MODE"
        exit 2
        ;;
    esac
    ;;
  status)
    emit_status
    ;;
  *)
    usage
    exit 2
    ;;
esac
