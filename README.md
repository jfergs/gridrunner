# GRIDRUNNER

Raspberry Pi 5 cyberdeck control panel and radio/sensing node.

GRIDRUNNER provides a local web UI for health checks, backup, radio inventory, ADS-B/SDR mode switching, and event review. Hostname, operator user, hotspot SSID, and event paths are deployment-specific and configured with environment variables.

## Primary Interfaces

- Web UI: `http://<device-hostname>.local:8088`
- ADS-B map: `http://<device-hostname>.local/tar1090/`

## Quick Start

Run this on the Linux device you want to turn into a GRIDRUNNER node:

```bash
curl -fsSL https://raw.githubusercontent.com/jfergs/gridrunner/main/scripts/bootstrap-web.sh | bash
```

The script downloads GRIDRUNNER to `~/gridrunner`, creates the web virtual
environment, installs Python dependencies, and starts the web panel. Open:

```text
http://<device-hostname>.local:8088
```

Then use the Initial Install panel to preview, install, or skip optional
components.

Set a web password before exposing the panel on a shared network:

```bash
export GRIDRUNNER_WEB_PASSWORD='choose-a-local-password'
curl -fsSL https://raw.githubusercontent.com/jfergs/gridrunner/main/scripts/bootstrap-web.sh | bash
```

Common bootstrap overrides:

```bash
export GRIDRUNNER_REPO_URL='https://github.com/jfergs/gridrunner.git'
export GRIDRUNNER_INSTALL_DIR="$HOME/gridrunner"
export GRIDRUNNER_WEB_HOST='0.0.0.0'
export GRIDRUNNER_WEB_PORT='8088'
export GRIDRUNNER_OPERATOR_USER="$(id -un)"
export GRIDRUNNER_DEVICE_HOSTNAME="$(hostname -s)"
```

## Layout

```text
web/
  app.py
  templates/index.html
scripts/
  bootstrap-web.sh
  install-items.sh
  system-health.sh
  system-backup.sh
  ham-check.sh
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

The web panel is a small FastAPI app. On the Pi, run it from the project
directory:

```bash
cd /home/<operator-user>/gridrunner/web
source .venv/bin/activate
export GRIDRUNNER_OPERATOR_USER='<operator-user>'
export GRIDRUNNER_OPERATOR_HOME='/home/<operator-user>'
export GRIDRUNNER_DEVICE_HOSTNAME='<device-hostname>'
export GRIDRUNNER_WEB_PASSWORD='choose-a-local-password'
uvicorn app:app --host 0.0.0.0 --port 8088
```

For local development from a checkout:

```bash
cd web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8088
```

The app defaults to the local checkout for `scripts/` and `/home/operator` for
runtime operator files. Set `GRIDRUNNER_WEB_PASSWORD` before exposing the panel
on Wi-Fi. Override these for the target device:

```bash
export GRIDRUNNER_HOME=/path/to/gridrunner
export GRIDRUNNER_OPERATOR_USER='<operator-user>'
export GRIDRUNNER_OPERATOR_HOME=/path/to/operator-home
export GRIDRUNNER_DEVICE_HOSTNAME='<device-hostname>'
export GRIDRUNNER_ADSB_MAP_URL='http://<device-hostname>.local/tar1090/'
export GRIDRUNNER_EVENTS_LOG=/path/to/operator-events.log
export GRIDRUNNER_WEB_USER='<operator-user>'
export GRIDRUNNER_WEB_PASSWORD='choose-a-local-password'
```

Health and Wi-Fi scripts hide hostname and Wi-Fi connection names by default.
Set this only on trusted consoles when full identifiers are needed:

```bash
export GRIDRUNNER_SHOW_IDENTIFIERS=1
```

## Initial Install

The dashboard includes an initial install pane with selectable components.
Checked items are installed, unchecked items are skipped. Use `Preview` to
print the planned commands before using `Install Selected`.
Skipped and pending components remain visible in the panel and can be selected
for installation later.

Install component labels and defaults are defined in `install-items.json`.
Install state is written to `state/install.json` by default. Override the state
directory when needed:

```bash
export GRIDRUNNER_STATE_DIR=/path/to/state
```

## Wi-Fi Fallback

`scripts/wifi-fallback.sh` is the maintained copy of the fallback hotspot logic. The installed runtime copy currently lives at:

```text
/home/<operator-user>/wifi-fallback.sh
```

The systemd timer is expected to run the installed script periodically:

```bash
systemctl status gridrunner-wifi.timer
systemctl status gridrunner-wifi.service
```

Expected behavior:

- Stay on a known Wi-Fi network when connected.
- Start the configured fallback hotspot when no known network is visible.
- While hotspot is active, keep scanning and switch back to known Wi-Fi when available.

## Notes

Runtime logs, backups, virtual environments, and generated cache files are intentionally ignored by git.
