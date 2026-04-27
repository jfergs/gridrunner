#!/bin/bash
set -u

echo "=== GRIDRUNNER HAM CHECK ==="
date
echo

echo "--- Serial Devices ---"
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "no USB/ACM serial devices found"
echo

echo "--- Audio Devices ---"
if command -v aplay >/dev/null 2>&1; then
  aplay -l
else
  echo "aplay not installed"
fi
echo

echo "--- CAT / Rig Control Tools ---"
for tool in rigctl rigctld flrig js8call pat; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '%-8s %s\n' "$tool" "$(command -v "$tool")"
  else
    printf '%-8s missing\n' "$tool"
  fi
done
echo

echo "--- Relevant Services ---"
for service in rigctld flrig js8call; do
  if systemctl list-unit-files "$service.service" >/dev/null 2>&1; then
    printf '%-12s ' "$service"
    systemctl is-active "$service" 2>/dev/null || true
  fi
done
