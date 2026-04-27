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
echo
echo "--- Services ---"
systemctl --no-pager --failed
echo
echo "--- ADS-B ---"
systemctl is-active readsb 2>/dev/null
echo
echo "--- SDR Devices ---"
rtl_test -t 2>&1 | head -20
echo
echo "--- Disk ---"
df -h
echo
echo "--- Memory ---"
free -h
