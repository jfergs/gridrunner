#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${GRIDRUNNER_HOME:-$(cd "$SCRIPT_DIR/.." && pwd)}"
GRIDRUNNER_HOME="$PROJECT_DIR"
STAMP=$(date '+%Y%m%d-%H%M%S')
OPERATOR_LABEL="${OPERATOR_LABEL:-operator}"
BACKUP_KEEP="${GRIDRUNNER_BACKUP_KEEP:-5}"

# shellcheck source=scripts/storage-common.sh
. "$PROJECT_DIR/scripts/storage-common.sh"
gridrunner_read_storage_env
DEST="$(gridrunner_storage_backup_dir)"
mkdir -p "$DEST"

tar -czf "$DEST/gridrunner-config-$STAMP.tar.gz" \
  ~/.bashrc \
  ~/.bash_aliases \
  ~/.tmux-gridrunner.sh \
  ~/.config/foot \
  ~/.config/labwc \
  "$PROJECT_DIR" \
  ~/operator-events.log \
  ~/operator-events.sh \
  ~/operator-ble.sh \
  ~/operator-presence.sh \
  ~/wifi-fallback.sh \
  2>/dev/null

echo "$OPERATOR_LABEL: backup created:"
ls -lh "$DEST/gridrunner-config-$STAMP.tar.gz"

find "$DEST" -maxdepth 1 -name 'gridrunner-config-*.tar.gz' -type f \
  | sort -r \
  | awk -v keep="$BACKUP_KEEP" 'NR > keep' \
  | while IFS= read -r old_backup; do
      rm -f "$old_backup"
      echo "$OPERATOR_LABEL: pruned old backup: $old_backup"
    done
