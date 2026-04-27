# GRIDRUNNER

Raspberry Pi 5 cyberdeck control panel and radio/sensing node.

GRIDRUNNER provides a local web UI for health checks, backup, radio inventory, ADS-B/SDR mode switching, and event review. It is intended to run on the `gridrunner` host for the `ghost` operator.

## Primary Interfaces

- Web UI: `http://gridrunner.local:8088`
- ADS-B map: `http://gridrunner.local/tar1090/`

## Layout

```text
web/
  app.py
  templates/index.html
scripts/
  ghost-health.sh
  ghost-backup.sh
  radio-inventory.sh
  radio-mode.sh
  wifi-fallback.sh
data/
logs/
state/
radio/
sdr/
```

## Web UI

The web panel is a small FastAPI app.

```bash
cd /home/ghost/gridrunner/web
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8088
```

## Wi-Fi Fallback

`scripts/wifi-fallback.sh` is the maintained copy of the fallback hotspot logic. The installed runtime copy currently lives at:

```text
/home/ghost/wifi-fallback.sh
```

The systemd timer is expected to run the installed script periodically:

```bash
systemctl status gridrunner-wifi.timer
systemctl status gridrunner-wifi.service
```

Expected behavior:

- Stay on a known Wi-Fi network when connected.
- Start `GRIDRUNNER-HOTSPOT` when no known network is visible.
- While hotspot is active, keep scanning and switch back to known Wi-Fi when available.

## Notes

Runtime logs, backups, virtual environments, and generated cache files are intentionally ignored by git.
