# GRIDRUNNER Device Validation

Use this after pulling a new `main` on the Raspberry Pi. Record failures as
specific backlog cards instead of leaving broad validation work open.

## Update

```bash
cd ~/gridrunner
git pull --ff-only
sudo scripts/setup-sudoers.sh
sudo systemctl restart gridrunner-web.service
sudo systemctl restart gridrunner-events.timer
```

## Service Health

```bash
bash scripts/wifi-status.sh
bash scripts/storage-control.sh status
bash scripts/storage-control.sh list
bash scripts/adsb-health.sh
bash scripts/event-health.sh
systemctl status gridrunner-web.service --no-pager
systemctl status gridrunner-events.timer --no-pager
systemctl status gridrunner-wifi.timer --no-pager
```

Expected:

- Web service is active.
- Wi-Fi status reports known Wi-Fi or intentional hotspot mode.
- Storage reports internal, external, or degraded with a clear fallback path.
- ADS-B health reports readsb OK with RTL support.
- Event health is fresh when scans recently wrote events, or the web UI shows
  Events as idle when scans are parked.

## iPhone Web UI

Open:

```text
http://<device-hostname>.local:8088
```

Check:

- No horizontal scrolling in iPhone Safari.
- Quick Actions are visible near the top: Wi-Fi, Bluetooth, Network, Map.
- Drawers open and close without hiding essential status.
- Warning/failure states stand out more than normal telemetry.
- Storage meters stay visible without opening the storage drawer.
- Events shows `idle` when Bluetooth and Network scans are disabled.
- ADS-B panel shows Flight board rows when aircraft data exists.

## Scans

From the web UI:

- Tap `Bluetooth`; the button shows scanning state and returns to idle.
- Tap `Network`; the button shows scanning state and returns to idle.
- Move the Low Impact / Field slider and confirm the state message updates.
- Use `Enable Scanning` and `Disable Scanning`; confirm the button reflects the
  current state.

CLI spot check:

```bash
GRIDRUNNER_SCAN_RUN_ONCE=1 GRIDRUNNER_SCAN_ONCE_TARGET=all bash scripts/run-events.sh
bash scripts/event-health.sh
```

## ADS-B

```bash
ls -l /run/readsb/aircraft.json
bash scripts/adsb-health.sh
systemctl status readsb lighttpd --no-pager
```

Expected:

- `/run/readsb/aircraft.json` exists and updates.
- Web UI ADS-B data age is current.
- Map button opens tar1090.
- Missing/degraded ADS-B state shows aircraft path, readsb state, lighttpd
  state, and the ADS-B health command.

## External USB Storage

Enable external storage from the web UI or CLI:

```bash
bash scripts/storage-control.sh list
bash scripts/storage-control.sh enable /media/<operator>/<label>
sudo systemctl restart gridrunner-web.service
sudo systemctl restart gridrunner-events.timer
bash scripts/storage-control.sh status
```

Expected:

- `<volume>/gridrunner/{backups,logs,sdr,radio,adsb,media}` exists.
- Storage panel shows external mode and mounted-volume meters.
- Event log path points to `<volume>/gridrunner/logs/<operator>-events.log`.

Fallback check:

```bash
bash scripts/storage-control.sh disable
sudo systemctl restart gridrunner-web.service
sudo systemctl restart gridrunner-events.timer
bash scripts/storage-control.sh status
```

Expected:

- Storage reports internal mode.
- External data remains in place.
- Web UI still loads.

## Wi-Fi Fallback

Known-Wi-Fi path:

```bash
bash scripts/wifi-status.sh
bash scripts/wifi-fallback.sh known
bash scripts/wifi-status.sh
```

Manual hotspot path:

```bash
bash scripts/wifi-fallback.sh hotspot
bash scripts/wifi-status.sh
```

Expected:

- Known Wi-Fi remains healthy when available.
- Hotspot command either enables configured hotspot mode or reports a clear
  NetworkManager permission/profile error.
- `Connect Known Wi-Fi` returns to a visible known network.

Automatic failover still needs a controlled field test with known Wi-Fi made
unavailable, then restored.
