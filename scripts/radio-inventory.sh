#!/bin/bash
echo "=== USB DEVICES ==="
lsusb
echo
echo "=== SERIAL DEVICES ==="
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
echo
echo "=== AUDIO DEVICES ==="
aplay -l
echo
echo "=== SDR DEVICES ==="
rtl_test -t 2>&1 | head -40
