#!/bin/bash
# shellcheck disable=SC2034

GRIDRUNNER_STORAGE_MODE_CONFIG=""
GRIDRUNNER_STORAGE_ROOT_CONFIG=""
GRIDRUNNER_STORAGE_MOUNT_CONFIG=""
GRIDRUNNER_STORAGE_VOLUME_UUID_CONFIG=""
GRIDRUNNER_BACKUP_DIR_CONFIG=""
GRIDRUNNER_EVENTS_LOG_CONFIG=""
GRIDRUNNER_SDR_DIR_CONFIG=""
GRIDRUNNER_RADIO_DIR_CONFIG=""
GRIDRUNNER_ADSB_HISTORY_DIR_CONFIG=""
GRIDRUNNER_MEDIA_DIR_CONFIG=""

gridrunner_storage_state_file() {
  local project_dir="${GRIDRUNNER_HOME:-$HOME/gridrunner}"
  local state_dir="${GRIDRUNNER_STATE_DIR:-$project_dir/state}"
  printf '%s\n' "$state_dir/storage.env"
}

gridrunner_read_storage_env() {
  local storage_file="${1:-$(gridrunner_storage_state_file)}"
  local key=""
  local value=""

  [ -f "$storage_file" ] || return 0

  while IFS='=' read -r key value; do
    case "$key" in
      GRIDRUNNER_STORAGE_MODE)
        GRIDRUNNER_STORAGE_MODE_CONFIG="$value"
        ;;
      GRIDRUNNER_STORAGE_ROOT)
        GRIDRUNNER_STORAGE_ROOT_CONFIG="$value"
        ;;
      GRIDRUNNER_STORAGE_MOUNT)
        GRIDRUNNER_STORAGE_MOUNT_CONFIG="$value"
        ;;
      GRIDRUNNER_STORAGE_VOLUME_UUID)
        GRIDRUNNER_STORAGE_VOLUME_UUID_CONFIG="$value"
        ;;
      GRIDRUNNER_BACKUP_DIR)
        GRIDRUNNER_BACKUP_DIR_CONFIG="$value"
        ;;
      GRIDRUNNER_EVENTS_LOG)
        GRIDRUNNER_EVENTS_LOG_CONFIG="$value"
        ;;
      GRIDRUNNER_SDR_DIR)
        GRIDRUNNER_SDR_DIR_CONFIG="$value"
        ;;
      GRIDRUNNER_RADIO_DIR)
        GRIDRUNNER_RADIO_DIR_CONFIG="$value"
        ;;
      GRIDRUNNER_ADSB_HISTORY_DIR)
        GRIDRUNNER_ADSB_HISTORY_DIR_CONFIG="$value"
        ;;
      GRIDRUNNER_MEDIA_DIR)
        GRIDRUNNER_MEDIA_DIR_CONFIG="$value"
        ;;
    esac
  done < "$storage_file"
}

gridrunner_storage_external_ready() {
  [ "$GRIDRUNNER_STORAGE_MODE_CONFIG" = "external" ] || return 1
  [ -n "$GRIDRUNNER_STORAGE_ROOT_CONFIG" ] || return 1
  [ -d "$GRIDRUNNER_STORAGE_ROOT_CONFIG" ] || return 1
  [ -w "$GRIDRUNNER_STORAGE_ROOT_CONFIG" ] || return 1
}

gridrunner_storage_backup_dir() {
  local project_dir="${GRIDRUNNER_HOME:-$HOME/gridrunner}"

  if [ -n "${GRIDRUNNER_BACKUP_DIR:-}" ]; then
    printf '%s\n' "$GRIDRUNNER_BACKUP_DIR"
  elif [ -n "${BACKUP_DIR:-}" ]; then
    printf '%s\n' "$BACKUP_DIR"
  elif gridrunner_storage_external_ready && [ -n "$GRIDRUNNER_BACKUP_DIR_CONFIG" ]; then
    printf '%s\n' "$GRIDRUNNER_BACKUP_DIR_CONFIG"
  else
    printf '%s\n' "$project_dir/data/backups"
  fi
}

gridrunner_storage_events_log() {
  local operator_user="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
  local operator_home="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"

  if [ -n "${GRIDRUNNER_EVENTS_LOG:-}" ]; then
    printf '%s\n' "$GRIDRUNNER_EVENTS_LOG"
  elif gridrunner_storage_external_ready && [ -n "$GRIDRUNNER_EVENTS_LOG_CONFIG" ]; then
    printf '%s\n' "$GRIDRUNNER_EVENTS_LOG_CONFIG"
  elif [ -n "${EVENTS_LOG:-}" ]; then
    printf '%s\n' "$EVENTS_LOG"
  elif [ -e "$operator_home/$operator_user-events.log" ]; then
    printf '%s\n' "$operator_home/$operator_user-events.log"
  elif [ -e "$operator_home/operator-events.log" ]; then
    printf '%s\n' "$operator_home/operator-events.log"
  else
    printf '%s\n' "$operator_home/$operator_user-events.log"
  fi
}

gridrunner_storage_status_line() {
  local mode="${GRIDRUNNER_STORAGE_MODE_CONFIG:-internal}"
  local status="internal"
  local root="${GRIDRUNNER_STORAGE_ROOT_CONFIG:-}"

  if [ "$mode" = "external" ]; then
    if gridrunner_storage_external_ready; then
      status="external"
    else
      status="degraded"
    fi
  fi

  printf 'GRIDRUNNER_STORAGE status=%s mode=%s root=%s mount=%s uuid=%s\n' \
    "$status" \
    "${mode:-internal}" \
    "${root:-internal}" \
    "${GRIDRUNNER_STORAGE_MOUNT_CONFIG:-}" \
    "${GRIDRUNNER_STORAGE_VOLUME_UUID_CONFIG:-}"
}
