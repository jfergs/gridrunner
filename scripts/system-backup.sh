#!/bin/bash
PROJECT_DIR="${GRIDRUNNER_HOME:-$HOME/gridrunner}"
DEST="$PROJECT_DIR/data/backups"
STAMP=$(date '+%Y%m%d-%H%M%S')
OPERATOR_LABEL="${OPERATOR_LABEL:-operator}"
BACKUP_KEEP="${GRIDRUNNER_BACKUP_KEEP:-5}"
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
