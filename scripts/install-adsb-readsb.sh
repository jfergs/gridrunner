#!/bin/bash
set -eu

INSTALL_URL="${GRIDRUNNER_READSB_INSTALL_URL:-https://raw.githubusercontent.com/wiedehopf/adsb-scripts/master/readsb-install.sh}"
INSTALL_SHA256="${GRIDRUNNER_READSB_INSTALL_SHA256:-}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo $0"
  exit 1
fi

echo "Installing wiedehopf readsb build."
echo "Do not install the Debian readsb package for GRIDRUNNER ADS-B."

installer="$(mktemp)"
trap 'rm -f "$installer"' EXIT

if command -v wget >/dev/null 2>&1; then
  wget -q -O "$installer" "$INSTALL_URL"
elif command -v curl >/dev/null 2>&1; then
  curl -fsSL "$INSTALL_URL" -o "$installer"
else
  echo "wget or curl is required to install readsb."
  exit 1
fi

if [ ! -s "$installer" ]; then
  echo "Downloaded readsb installer is empty."
  exit 1
fi

if [ -n "$INSTALL_SHA256" ]; then
  if ! command -v sha256sum >/dev/null 2>&1; then
    echo "sha256sum is required when GRIDRUNNER_READSB_INSTALL_SHA256 is set."
    exit 1
  fi
  printf '%s  %s\n' "$INSTALL_SHA256" "$installer" | sha256sum -c -
else
  echo "No GRIDRUNNER_READSB_INSTALL_SHA256 set; executing downloaded installer without checksum pinning."
fi

bash "$installer"

if command -v apt-mark >/dev/null 2>&1; then
  apt-mark hold readsb || true
fi

if command -v readsb >/dev/null 2>&1 && readsb --help 2>&1 | grep -qi 'rtlsdr'; then
  echo "readsb OK (RTL supported)"
else
  echo "readsb install completed, but RTL-SDR support was not detected."
  exit 1
fi
