#!/bin/bash
set -u

case "${1:-}" in
  shutdown)
    echo "operator: shutting down device"
    sudo systemctl poweroff
    ;;
  restart)
    echo "operator: restarting device"
    sudo systemctl reboot
    ;;
  *)
    echo "Usage: $0 {shutdown|restart}"
    exit 2
    ;;
esac
