#!/bin/bash

case "$1" in
  adsb)
    echo "operator: enabling ADS-B mode"
    sudo systemctl start readsb
    ;;
  sdr)
    echo "operator: enabling SDR exploration mode"
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
