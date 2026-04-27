#!/bin/bash

case "$1" in
  adsb)
    echo "ghost: enabling ADS-B mode"
    sudo systemctl start readsb
    ;;
  sdr)
    echo "ghost: enabling SDR exploration mode"
    sudo systemctl stop readsb
    ;;
  status)
    echo "--- readsb ---"
    systemctl is-active readsb
    ;;
  *)
    echo "Usage: $0 {adsb|sdr|status}"
    ;;
esac
