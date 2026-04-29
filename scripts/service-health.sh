#!/bin/bash
set -u

emit_service() {
  local name="$1"
  local unit="$2"
  local active="unknown"
  local enabled="unknown"
  local status="unknown"

  if command -v systemctl >/dev/null 2>&1; then
    active="$(systemctl is-active "$unit" 2>/dev/null || true)"
    enabled="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
  fi

  if [ "$active" = "active" ]; then
    status="active"
  elif [ "$active" = "failed" ]; then
    status="failed"
  elif [ "$enabled" = "enabled" ]; then
    status="inactive"
  elif [ "$active" = "inactive" ]; then
    status="inactive"
  fi

  echo "GRIDRUNNER_SERVICE name=$name unit=$unit status=$status active=$active enabled=$enabled"
}

emit_service gridrunner-web gridrunner-web.service
emit_service gridrunner-wifi-timer gridrunner-wifi.timer
emit_service gridrunner-wifi gridrunner-wifi.service
emit_service gridrunner-events-timer gridrunner-events.timer
emit_service readsb readsb.service
emit_service lighttpd lighttpd.service
