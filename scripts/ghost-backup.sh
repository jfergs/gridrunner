#!/bin/bash
DEST="$HOME/gridrunner/data/backups"
STAMP=$(date '+%Y%m%d-%H%M%S')
mkdir -p "$DEST"

tar -czf "$DEST/gridrunner-config-$STAMP.tar.gz" \
  ~/.bashrc \
  ~/.bash_aliases \
  ~/.tmux-gridrunner.sh \
  ~/.config/foot \
  ~/.config/labwc \
  ~/gridrunner \
  ~/ghost-events.log \
  ~/ghost-events.sh \
  ~/ghost-ble.sh \
  ~/ghost-presence.sh \
  ~/wifi-fallback.sh \
  2>/dev/null

echo "ghost: backup created:"
ls -lh "$DEST/gridrunner-config-$STAMP.tar.gz"
