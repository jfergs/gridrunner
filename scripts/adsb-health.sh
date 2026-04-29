#!/bin/bash
set -u

if ! command -v readsb >/dev/null 2>&1; then
  echo "readsb MISSING"
  exit 1
fi

if readsb --help 2>&1 | grep -qi 'rtlsdr'; then
  echo "readsb OK (RTL supported)"
  exit 0
fi

echo "readsb BROKEN (no RTL support)"
exit 1
