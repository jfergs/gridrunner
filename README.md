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

During interactive setup, GRIDRUNNER prompts for the fallback hotspot SSID and
password. The Wi-Fi network is created only when known Wi-Fi is unavailable.
The password must be at least 8 characters. To configure it again:

```bash
cd ~/gridrunner
bash scripts/configure-wifi-hotspot.sh
```

Before using the web panel to install packages or service files, run this once
from a terminal on the device:

```bash
cd ~/gridrunner
sudo scripts/setup-sudoers.sh
```

This also adds the operator user to available journal-reading groups such as
`systemd-journal` or `adm`. Log out and back in, or reboot, before using the
`logs` control if journal permissions were just changed.

Set a web password before exposing the panel on a shared network:

```bash
export GRIDRUNNER_WEB_PASSWORD='choose-a-local-password'
curl -fsSL https://raw.githubusercontent.com/jfergs/gridrunner/main/scripts/bootstrap-web.sh | bash
```

The panel is intended for local device, trusted LAN, or VPN use. Do not expose
port `8088` directly to the internet. Use Tailscale, WireGuard, or another VPN
for remote access, and set `GRIDRUNNER_WEB_PASSWORD` before using any shared
network.

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
deploy/
  systemd/gridrunner-web.service
  systemd/gridrunner-events.service
  systemd/gridrunner-events.timer
scripts/
  adsb-health.sh
  bootstrap-web.sh
  component-health.sh
  disk-health.sh
  event-health.sh
  install-adsb-readsb.sh
  install-items.sh
  logs.sh
  patch-events-script.sh
  rotate-logs.sh
  run-events.sh
  wifi-status.sh
  system-health.sh
  system-backup.sh
  ham-check.sh
  power-control.sh
  radio-inventory.sh
  setup-sudoers.sh
  service-health.sh
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
on Wi-Fi, and prefer VPN access for remote administration. Override these for
the target device:

```bash
export GRIDRUNNER_HOME=/path/to/gridrunner
export GRIDRUNNER_OPERATOR_USER='<operator-user>'
export GRIDRUNNER_OPERATOR_HOME=/path/to/operator-home
export GRIDRUNNER_DEVICE_HOSTNAME='<device-hostname>'
export GRIDRUNNER_ADSB_MAP_URL='http://<device-hostname>.local/tar1090/'
export GRIDRUNNER_ADSB_ROUTE_LOOKUP_ENABLED=1
export GRIDRUNNER_ADSB_ROUTE_API_URL='https://api.adsbdb.com/v0/callsign/{callsign}'
export GRIDRUNNER_ADSB_ROUTE_LOOKUP_LIMIT=3
export GRIDRUNNER_ADSB_ROUTE_LOOKUP_TIMEOUT=0.8
export GRIDRUNNER_ADSB_ROUTE_CACHE_SECONDS=900
export GRIDRUNNER_EVENTS_LOG=/path/to/operator-events.log
export GRIDRUNNER_WEB_USER='<operator-user>'
export GRIDRUNNER_WEB_PASSWORD='choose-a-local-password'
```

If `GRIDRUNNER_ADSB_MAP_URL` is unset, the panel builds the ADS-B map link from
the current request host as `http://<current-host>/tar1090/`. Set the variable
above when tar1090 lives somewhere else.

The ADS-B Flight board always uses the local readsb aircraft JSON as its
baseline. When internet access is available, the panel can optionally enrich a
small number of visible flights with route information by callsign. Route lookup
is enabled by default, bounded by the limit, timeout, and cache settings above,
and fails quietly when the device is offline.

If aircraft data is missing or degraded, the ADS-B panel shows the aircraft JSON
path it expected, `readsb.service` state, `lighttpd.service` state, and the
device command to run next:

```bash
bash scripts/adsb-health.sh
```

Health and Wi-Fi scripts hide hostname and Wi-Fi connection names by default.
Set this only on trusted consoles when full identifiers are needed:

```bash
export GRIDRUNNER_SHOW_IDENTIFIERS=1
```

## Events And Logs

The web panel shows recent events and warns when the events log is missing or
stale. The stale threshold defaults to 15 minutes and can be adjusted with:

```bash
export GRIDRUNNER_EVENTS_STALE_SECONDS=900
```

When Bluetooth and Network Device scanning are both disabled, the dashboard
shows Events as `idle` instead of stale. That means the timer can be healthy
while no new event lines are expected. Enable scanning or run a one-shot scan
from Quick Actions or the scan drawer to write fresh events.

Use the real log wrapper instead of an alias-only `logs` command:

```bash
cd ~/gridrunner
bash scripts/logs.sh
```

If journal access is denied, rerun setup and restart the session:

```bash
cd ~/gridrunner
sudo scripts/setup-sudoers.sh
```

Install periodic event collection with the `Events Service` install item, or
from the device:

```bash
cd ~/gridrunner
bash scripts/install-items.sh --apply events-service
```

This installs:

```text
/etc/systemd/system/gridrunner-events.service
/etc/systemd/system/gridrunner-events.timer
```

The timer runs shortly after boot and every five minutes. Bluetooth and
network device discovery scans default to off, so the timer skips legacy scan
work until scan controls are enabled from the web panel. The top Quick Actions
deck provides one-tap Wi-Fi, Bluetooth, Network, and ADS-B Map actions. The
scan drawer provides `Bluetooth Scan Now` and `Wi-Fi Scan Now`; each button
stays on the page, shows a scanning state while active, and returns to its idle
label when the run finishes. Use the drawer's `Enable Scanning` /
`Disable Scanning` control to arm or park continuous scanning. The runner
stores those controls in:

```text
~/gridrunner/state/scan-controls.env
```

The dashboard also provides scan profiles:

- `Low Impact`: continuous Bluetooth and network device scans off, interval
  saved as 15 minutes for future continuous use.
- `Field`: continuous Bluetooth and network device scans on, interval 5 minutes.

The profile control is a Low Impact / Field slider in the scan drawer.

Recommended defaults for low-contention field use:

- Keep continuous Bluetooth and Network Devices off unless actively surveying.
- Use `Low Impact` as the parked/default profile.
- Use `Field` for short survey windows, then return to `Low Impact`.
- Keep Bluetooth bursts bounded to 8-12 seconds with
  `GRIDRUNNER_BTMGMT_FIND_SECONDS`.
- Prefer ARP-only network device discovery; avoid heavier `nmap` sweeps unless
  intentionally troubleshooting.

When scans are enabled, the timer calls `scripts/run-events.sh`, which
resolves the operator event script at:

```text
/home/<operator-user>/<operator-user>-events.sh
```

During `events-service` install, `scripts/patch-events-script.sh` bounds legacy
`btmgmt find` calls and gates known Bluetooth/network discovery commands behind
the dashboard scan controls. Override the Bluetooth scanner timeout with:

```bash
export GRIDRUNNER_BTMGMT_FIND_SECONDS=12
```

Check it with:

```bash
systemctl status gridrunner-events.timer
systemctl status gridrunner-events.service
journalctl -u gridrunner-events.service -n 80 --no-pager
```

Event log rotation is handled by:

```bash
bash scripts/rotate-logs.sh
```

Defaults:

```bash
export GRIDRUNNER_EVENTS_LOG_MAX_BYTES=5242880
export GRIDRUNNER_EVENTS_LOG_KEEP=5
```

Install the managed foreground presence scanner with:

```bash
cd ~/gridrunner
bash scripts/install-items.sh --apply presence-script
```

That installs the wrapper at:

```text
/home/<operator-user>/<operator-user>-presence.sh
```

You can also run the maintained copy directly:

```bash
cd ~/gridrunner
bash scripts/ghost-presence.sh
```

It reads the same `state/scan-controls.env` file as the dashboard and skips
`arp-scan --localnet` unless Network scanning is set to `Continuous` or the
process is explicitly launched with `GRIDRUNNER_SCAN_NETWORK_ENABLED=1`.
Avoid unmanaged `arp-scan --localnet` loops on `wlan0`; they put the Wi-Fi
interface into promiscuous mode and can trigger Broadcom scan errors while the
device is connected to known Wi-Fi.

Disk usage guardrails are reported by:

```bash
bash scripts/disk-health.sh
```

Defaults:

```bash
export GRIDRUNNER_DISK_WARN_PERCENT=85
export GRIDRUNNER_DISK_CRITICAL_PERCENT=95
export GRIDRUNNER_BACKUP_KEEP=5
```

## Storage Model

GRIDRUNNER keeps service-critical files on internal storage. The web dashboard
Storage panel can use an already-mounted writable USB volume for operator data:
backups, event logs, SDR captures, radio artifacts, ADS-B history, and media
libraries. It writes explicit paths to `state/storage.env`; it does not format
drives, erase data, move `state/`, or make boot depend on removable media. The
same panel shows horizontal used/free meters for mounted volumes.

The Storage panel also shows an operator message for the active mode:

- `internal`: internal paths are active.
- `external`: USB storage is active for operator data.
- `degraded`: external storage is configured but missing or not writable, so
  runtime scripts fall back to internal backup and event-log paths.

CLI equivalents:

```bash
bash scripts/storage-control.sh list
bash scripts/storage-control.sh enable /media/<operator>/<label>
bash scripts/storage-control.sh status
bash scripts/storage-control.sh disable
```

If the selected USB root is missing or not writable, runtime scripts fall back
to internal backup and event-log paths. See
[docs/storage-model.md](docs/storage-model.md) for the storage design, allowed
movable paths, internal-only paths, and rollback behavior.

## Initial Install

The dashboard includes an initial install pane with selectable components.
Checked items are installed, unchecked items are skipped. Use `Preview` to
print the planned commands before using `Install Selected`.
Skipped and pending components remain visible in the panel and can be selected
for installation later.
The panel also runs `scripts/component-health.sh` to show whether each component
is currently detected on the device.

ADS-B setup intentionally does not install the Debian `readsb` package. On this
GRIDRUNNER setup, Debian/Trixie `readsb` can lack RTL-SDR support and fail with
`ERROR: Unknown device type:0`. Use the wiedehopf installer path instead:

```bash
cd ~/gridrunner
sudo bash scripts/install-adsb-readsb.sh
```

That helper runs the wiedehopf installer:

```bash
sudo bash -c "$(wget -q -O - https://raw.githubusercontent.com/wiedehopf/adsb-scripts/master/readsb-install.sh)"
```

Then it marks `readsb` held with `apt-mark hold readsb` when available. Check
RTL-SDR support with:

```bash
bash scripts/adsb-health.sh
readsb --help | grep rtlsdr
```

Package and service installation from the web panel requires non-interactive
sudo. If an install item fails with a sudo password/terminal error, run:

```bash
cd ~/gridrunner
sudo scripts/setup-sudoers.sh
```

If an apt package fails on a config-file prompt, repair the interrupted install
from a terminal with:

```bash
sudo DEBIAN_FRONTEND=noninteractive apt-get install -f -y \
  -o Dpkg::Options::=--force-confdef \
  -o Dpkg::Options::=--force-confold
```

Install component labels and defaults are defined in `install-items.json`.
Install state is written to `state/install.json` by default. Override the state
directory when needed:

```bash
export GRIDRUNNER_STATE_DIR=/path/to/state
```

## Pi Update Smoke Test

After pulling an update on the Pi, use this quick path to confirm privileged web
actions, Wi-Fi mode controls, and ADS-B are still healthy:

```bash
cd ~/gridrunner
git pull --ff-only
sudo scripts/setup-sudoers.sh
sudo systemctl restart gridrunner-web.service
bash scripts/wifi-status.sh
bash scripts/wifi-fallback.sh hotspot
bash scripts/wifi-status.sh
bash scripts/wifi-fallback.sh known
bash scripts/adsb-health.sh
```

Then open `http://<device-hostname>.local:8088`, confirm the ADS-B data age is
current, confirm Events shows either `fresh` or intentional `idle`, and test the
Quick Actions, `Enable Hotspot`, `Connect Known Wi-Fi`, `ADS-B Mode`, and
`SDR Mode` controls from the web UI. For a fuller pass, use
[docs/device-validation.md](docs/device-validation.md).

## Web Service

The `Web Service` install item renders `deploy/systemd/gridrunner-web.service`
with the current operator, install path, and hostname, then installs it as:

```text
/etc/systemd/system/gridrunner-web.service
```

After installation, the panel should start on boot. The installer enables the
service but does not restart it immediately, so it does not collide with a
bootstrap web process already using port `8088`. Check it with:

```bash
systemctl status gridrunner-web.service
journalctl -u gridrunner-web.service -n 100 --no-pager
```

## Power Controls

The web panel includes Restart and Shutdown controls in the upper-right power
tray. Each action uses a browser confirmation popup before it submits. The
runtime user must have non-interactive sudo permission for:

```text
systemctl reboot
systemctl poweroff
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

Check current Wi-Fi mode, timer state, service state, and hotspot IP with:

```bash
cd ~/gridrunner
bash scripts/wifi-status.sh
```

The web dashboard Wi-Fi panel includes `Enable Hotspot` for manually switching
to the configured fallback hotspot. The same action is available from a
terminal with:

```bash
cd ~/gridrunner
bash scripts/wifi-fallback.sh hotspot
```

Use `Connect Known Wi-Fi` from the same panel to leave hotspot mode and join a
visible known network. The terminal equivalent is:

```bash
cd ~/gridrunner
bash scripts/wifi-fallback.sh known
```

Configure or repair the hotspot profile from the device:

```bash
cd ~/gridrunner
bash scripts/configure-wifi-hotspot.sh
bash scripts/wifi-fallback.sh
```

The script defaults to `GRIDRUNNER-HOTSPOT` and also recognizes legacy
`Gridrunner-hotspot` and `DEVICE-HOTSPOT` NetworkManager profile names as the
fallback hotspot. The persisted fallback configuration is written to:

```text
~/.config/gridrunner/wifi-fallback.env
```

To inspect the NetworkManager profile:

```bash
nmcli connection show 'Gridrunner-hotspot'
nmcli connection up 'Gridrunner-hotspot'
```

Expected behavior:

- Stay on a known Wi-Fi network when connected.
- Start the configured fallback hotspot when no known network is visible.
- While hotspot is active, keep scanning and switch back to known Wi-Fi when available.

When NetworkManager reports full connectivity on a known Wi-Fi network, the
fallback check exits without rescanning. Degraded connectivity checks use a
minimum local rescan interval to reduce radio churn:

```bash
export GRIDRUNNER_WIFI_RESCAN_MIN_SECONDS=60
```

The last rescan timestamp is stored in `~/gridrunner/state/wifi-rescan.last` by
default.

The last fallback action is stored in `~/gridrunner/state/wifi-action.env` and
shown by `scripts/wifi-status.sh` and the web dashboard.

## Notes

Runtime logs, backups, virtual environments, and generated cache files are intentionally ignored by git.
