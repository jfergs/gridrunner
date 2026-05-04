#!/bin/bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${GRIDRUNNER_HOME:-$(cd "$SCRIPT_DIR/.." && pwd)}"
GRIDRUNNER_HOME="$PROJECT_DIR"
OPERATOR_USER="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
OPERATOR_HOME="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"
STATE_DIR="${GRIDRUNNER_STATE_DIR:-$PROJECT_DIR/state}"
STORAGE_ENV="$STATE_DIR/storage.env"

# shellcheck source=scripts/storage-common.sh
. "$SCRIPT_DIR/storage-common.sh"

usage() {
  cat <<'EOF'
Usage: storage-control.sh status
       storage-control.sh list
       storage-control.sh enable /mounted/usb/path
       storage-control.sh disable
EOF
}

sanitize_field() {
  printf '%s' "$1" | tr ' \t\n=' '____'
}

volume_uuid_for_mount() {
  local mount_path="$1"
  local source=""

  source="$(findmnt -n -o SOURCE --target "$mount_path" 2>/dev/null | head -n 1 || true)"
  if [ -n "$source" ] && command -v blkid >/dev/null 2>&1; then
    blkid -s UUID -o value "$source" 2>/dev/null || true
  fi
}

list_volumes() {
  local found=0
  local mount_path=""
  local source=""
  local fstype=""
  local size=""
  local avail=""
  local used=""
  local used_percent=""
  local selectable="no"
  local writable="no"

  if command -v findmnt >/dev/null 2>&1; then
    while IFS='|' read -r mount_path source fstype size avail used used_percent; do
      [ -n "$mount_path" ] || continue
      case "$fstype" in
        autofs|binfmt_misc|bpf|cgroup*|configfs|debugfs|devpts|devtmpfs|efivarfs|fusectl|hugetlbfs|mqueue|proc|pstore|securityfs|sysfs|tmpfs|tracefs)
          continue
          ;;
      esac
      writable="no"
      selectable="no"
      [ -d "$mount_path" ] && [ -w "$mount_path" ] && writable="yes"
      case "$mount_path" in
        /media/*|/mnt/*|/Volumes/*)
          selectable="yes"
          ;;
      esac
      used_percent="${used_percent%\%}"
      printf 'GRIDRUNNER_STORAGE_VOLUME mount=%s source=%s fstype=%s size_bytes=%s used_bytes=%s avail_bytes=%s used_percent=%s writable=%s selectable=%s uuid=%s\n' \
        "$(sanitize_field "$mount_path")" \
        "$(sanitize_field "$source")" \
        "$(sanitize_field "$fstype")" \
        "$(sanitize_field "$size")" \
        "$(sanitize_field "$used")" \
        "$(sanitize_field "$avail")" \
        "$(sanitize_field "$used_percent")" \
        "$writable" \
        "$selectable" \
        "$(sanitize_field "$(volume_uuid_for_mount "$mount_path")")"
      found=1
    done < <(findmnt -rn -b -o TARGET,SOURCE,FSTYPE,SIZE,AVAIL,USED,USE% | awk 'BEGIN { OFS="|" } { print $1,$2,$3,$4,$5,$6,$7 }')
  fi

  if [ "$found" -eq 0 ]; then
    for mount_path in "/media/$OPERATOR_USER"/* /media/*/* /mnt/* /Volumes/*; do
      [ -d "$mount_path" ] || continue
      writable="no"
      [ -w "$mount_path" ] && writable="yes"
      printf 'GRIDRUNNER_STORAGE_VOLUME mount=%s source=unknown fstype=unknown size_bytes=0 used_bytes=0 avail_bytes=0 used_percent=0 writable=%s selectable=yes uuid=\n' \
        "$(sanitize_field "$mount_path")" \
        "$writable"
      found=1
    done
  fi

  if [ "$found" -eq 0 ]; then
    echo "GRIDRUNNER_STORAGE_VOLUME status=none"
  fi
}

copy_if_present() {
  local source_path="$1"
  local dest_path="$2"

  [ -e "$source_path" ] || return 0
  mkdir -p "$dest_path"
  cp -a "$source_path" "$dest_path/" 2>/dev/null || true
}

enable_storage() {
  local mount_path="$1"
  local root="$mount_path/gridrunner"
  local events_log="$root/logs/$OPERATOR_USER-events.log"
  local uuid=""

  if [ -z "$mount_path" ] || [ ! -d "$mount_path" ]; then
    echo "GRIDRUNNER_STORAGE status=failed reason=mount-not-found mount=$mount_path"
    return 1
  fi
  if [ ! -w "$mount_path" ]; then
    echo "GRIDRUNNER_STORAGE status=failed reason=mount-not-writable mount=$mount_path"
    return 1
  fi

  mkdir -p "$root/backups" "$root/logs" "$root/sdr" "$root/radio" "$root/adsb" "$root/media" || return 1
  : > "$events_log" || return 1
  chmod 0664 "$events_log" 2>/dev/null || true

  copy_if_present "$PROJECT_DIR/data/backups" "$root"
  copy_if_present "$PROJECT_DIR/sdr" "$root"
  copy_if_present "$PROJECT_DIR/radio" "$root"
  if [ -e "$OPERATOR_HOME/$OPERATOR_USER-events.log" ]; then
    cp -a "$OPERATOR_HOME/$OPERATOR_USER-events.log" "$events_log" 2>/dev/null || true
  elif [ -e "$OPERATOR_HOME/operator-events.log" ]; then
    cp -a "$OPERATOR_HOME/operator-events.log" "$events_log" 2>/dev/null || true
  fi

  uuid="$(volume_uuid_for_mount "$mount_path")"
  mkdir -p "$STATE_DIR" || return 1
  {
    echo "GRIDRUNNER_STORAGE_MODE=external"
    echo "GRIDRUNNER_STORAGE_VOLUME_UUID=$uuid"
    echo "GRIDRUNNER_STORAGE_MOUNT=$mount_path"
    echo "GRIDRUNNER_STORAGE_ROOT=$root"
    echo "GRIDRUNNER_BACKUP_DIR=$root/backups"
    echo "GRIDRUNNER_EVENTS_LOG=$events_log"
    echo "GRIDRUNNER_SDR_DIR=$root/sdr"
    echo "GRIDRUNNER_RADIO_DIR=$root/radio"
    echo "GRIDRUNNER_ADSB_HISTORY_DIR=$root/adsb"
    echo "GRIDRUNNER_MEDIA_DIR=$root/media"
  } > "$STORAGE_ENV"

  echo "GRIDRUNNER_STORAGE status=external mode=external root=$root mount=$mount_path uuid=$uuid"
  echo "external storage enabled: $root"
  echo "restart gridrunner-web.service and gridrunner-events.timer to refresh systemd environment"
}

disable_storage() {
  mkdir -p "$STATE_DIR" || return 1
  {
    echo "GRIDRUNNER_STORAGE_MODE=internal"
    echo "GRIDRUNNER_STORAGE_ROOT="
    echo "GRIDRUNNER_STORAGE_MOUNT="
    echo "GRIDRUNNER_STORAGE_VOLUME_UUID="
  } > "$STORAGE_ENV"

  echo "GRIDRUNNER_STORAGE status=internal mode=internal root=internal"
  echo "external storage disabled; external data was left in place"
}

status_storage() {
  gridrunner_read_storage_env "$STORAGE_ENV"
  gridrunner_storage_status_line
  echo "backup dir: $(gridrunner_storage_backup_dir)"
  echo "events log: $(gridrunner_storage_events_log)"
}

case "${1:-status}" in
  status)
    status_storage
    ;;
  list)
    list_volumes
    ;;
  enable)
    enable_storage "${2:-}"
    ;;
  disable)
    disable_storage
    ;;
  *)
    usage
    exit 2
    ;;
esac
