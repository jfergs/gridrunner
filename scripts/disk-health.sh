#!/bin/bash
set -u

CHECK_PATH="${GRIDRUNNER_DISK_CHECK_PATH:-${GRIDRUNNER_HOME:-$HOME/gridrunner}}"
WARN_PERCENT="${GRIDRUNNER_DISK_WARN_PERCENT:-85}"
CRITICAL_PERCENT="${GRIDRUNNER_DISK_CRITICAL_PERCENT:-95}"

if [ ! -e "$CHECK_PATH" ]; then
  CHECK_PATH="$HOME"
fi

line="$(df -Pk "$CHECK_PATH" 2>/dev/null | awk 'NR == 2 {print}')"
if [ -z "$line" ]; then
  echo "GRIDRUNNER_DISK_HEALTH status=unknown detail=df-unavailable path=$CHECK_PATH"
  echo "disk health unavailable: $CHECK_PATH"
  exit 1
fi

used_percent="$(printf '%s\n' "$line" | awk '{gsub(/%/, "", $5); print $5}')"
available_kb="$(printf '%s\n' "$line" | awk '{print $4}')"
mount_point="$(printf '%s\n' "$line" | awk '{print $6}')"

status="ok"
exit_code=0
if [ "$used_percent" -ge "$CRITICAL_PERCENT" ]; then
  status="critical"
  exit_code=1
elif [ "$used_percent" -ge "$WARN_PERCENT" ]; then
  status="warn"
  exit_code=1
fi

echo "GRIDRUNNER_DISK_HEALTH status=$status used_percent=$used_percent available_kb=$available_kb mount=$mount_point path=$CHECK_PATH"
echo "disk $status: ${used_percent}% used, ${available_kb}KB available on $mount_point"
exit "$exit_code"
