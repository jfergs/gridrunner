#!/bin/bash
echo "=== GRIDRUNNER HEALTH ==="
date
echo
if [ "${GRIDRUNNER_SHOW_IDENTIFIERS:-0}" = "1" ]; then
  hostnamectl
else
  echo "--- Host ---"
  uname -srm
fi
echo
echo "--- Network ---"
if [ "${GRIDRUNNER_SHOW_IDENTIFIERS:-0}" = "1" ]; then
  nmcli -t -f DEVICE,STATE,CONNECTION dev
else
  nmcli -t -f DEVICE,STATE dev
fi
"$(dirname "$0")/wifi-status.sh"
echo
echo "--- Services ---"
systemctl --no-pager --failed
echo
echo "--- Events ---"
"$(dirname "$0")/event-health.sh"
echo
echo "--- ADS-B ---"
systemctl is-active readsb 2>/dev/null
"$(dirname "$0")/adsb-health.sh"
echo
echo "--- SDR Devices ---"
rtl_test -t 2>&1 | head -20
echo
echo "--- Disk ---"
df -h
echo
echo "--- Memory ---"
free -h
