#!/bin/bash
set -eu

INSTALL_URL="${GRIDRUNNER_READSB_INSTALL_URL:-https://raw.githubusercontent.com/wiedehopf/adsb-scripts/master/readsb-install.sh}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo $0"
  exit 1
fi

echo "Installing wiedehopf readsb build."
echo "Do not install the Debian readsb package for GRIDRUNNER ADS-B."

if command -v wget >/dev/null 2>&1; then
  bash -c "$(wget -q -O - "$INSTALL_URL")"
elif command -v curl >/dev/null 2>&1; then
  bash -c "$(curl -fsSL "$INSTALL_URL")"
else
  echo "wget or curl is required to install readsb."
  exit 1
fi

if command -v apt-mark >/dev/null 2>&1; then
  apt-mark hold readsb || true
fi

if command -v readsb >/dev/null 2>&1 && readsb --help 2>&1 | grep -qi 'rtlsdr'; then
  echo "readsb OK (RTL supported)"
else
  echo "readsb install completed, but RTL-SDR support was not detected."
  exit 1
fi
