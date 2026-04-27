#!/bin/bash
echo "=== GRIDRUNNER HEALTH ==="
date
echo
hostnamectl
echo
echo "--- Network ---"
nmcli -t -f DEVICE,STATE,CONNECTION dev
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
