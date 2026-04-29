# AGENTS.md — GRIDRUNNER

## Project identity

GRIDRUNNER is a Raspberry Pi 5 cyberdeck / portable sensing and radio-comms node.

Operator user: configured by `GRIDRUNNER_OPERATOR_USER`  
Hostname: configured by `GRIDRUNNER_DEVICE_HOSTNAME`  
Primary web UI: `http://<device-hostname>.local:8088`  
ADS-B map: `http://<device-hostname>.local/tar1090/`

Do not install Debian/Trixie `readsb` for ADS-B. GRIDRUNNER expects the
wiedehopf `readsb` build because it supports RTL-SDR devices on this setup.
Use `scripts/install-adsb-readsb.sh` and verify with `scripts/adsb-health.sh`.

Health and Wi-Fi scripts hide hostname and Wi-Fi connection names unless
`GRIDRUNNER_SHOW_IDENTIFIERS=1` is set in a trusted environment.

## System goals

GRIDRUNNER should provide:

- Local web control panel for iPhone/laptop
- Initial install pane with selectable install/skip components
- Script buttons for health, backup, inventory, SDR/ADS-B mode switching
- ADS-B aircraft monitoring using readsb + tar1090
- SDR exploration mode using SDR++
- BLE scanning and presence/event logging
- Wi-Fi known-network mode with fallback hotspot
- Ham radio utilities for future G90 / JS8Call / Winlink integration

## Existing important paths

```text
/home/<operator-user>/gridrunner/
├── web/
│   ├── app.py
│   ├── templates/index.html
│   └── .venv/
├── scripts/
│   ├── system-health.sh
│   ├── system-backup.sh
│   ├── radio-inventory.sh
│   ├── radio-mode.sh
│   └── ham-check.sh
├── data/
├── logs/
├── state/
├── radio/
└── sdr/

/home/<operator-user>/
├── operator-events.sh
├── operator-events.log
├── operator-ble.sh
├── operator-presence.sh
├── wifi-fallback.sh
└── .tmux-gridrunner.sh
```
