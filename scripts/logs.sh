#!/bin/bash
set -u

LINES="${1:-120}"

case "$LINES" in
  ''|*[!0-9]*)
    echo "Usage: $0 [lines]"
    exit 2
    ;;
esac

if ! command -v journalctl >/dev/null 2>&1; then
  echo "journalctl not found"
  exit 1
fi

journalctl -n "$LINES" --no-pager
