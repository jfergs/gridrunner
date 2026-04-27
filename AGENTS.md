# AGENTS.md — GRIDRUNNER

## Project identity

GRIDRUNNER is a Raspberry Pi 5 cyberdeck / portable sensing and radio-comms node.

Operator user: `ghost`  
Hostname: `gridrunner`  
Primary web UI: `http://gridrunner.local:8088`  
ADS-B map: `http://gridrunner.local/tar1090/`

## System goals

GRIDRUNNER should provide:

- Local web control panel for iPhone/laptop
- Script buttons for health, backup, inventory, SDR/ADS-B mode switching
- ADS-B aircraft monitoring using readsb + tar1090
- SDR exploration mode using SDR++
- BLE scanning and presence/event logging
- Wi-Fi known-network mode with fallback hotspot
- Ham radio utilities for future G90 / JS8Call / Winlink integration

## Existing important paths

```text
/home/ghost/gridrunner/
├── web/
│   ├── app.py
│   ├── templates/index.html
│   └── .venv/
├── scripts/
│   ├── ghost-health.sh
│   ├── ghost-backup.sh
│   ├── radio-inventory.sh
│   ├── radio-mode.sh
│   └── ham-check.sh
├── data/
├── logs/
├── state/
├── radio/
└── sdr/

/home/ghost/
├── ghost-events.sh
├── ghost-events.log
├── ghost-ble.sh
├── ghost-presence.sh
├── wifi-fallback.sh
└── .tmux-gridrunner.sh
```
