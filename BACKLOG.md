# GRIDRUNNER Backlog

Project-local backlog for Gridrunner. Keep detailed Gridrunner implementation
work here; roll up only the current priorities to the global backlog tracker.

## Top Priority

- Investigate stale GRIDRUNNER events and log access permissions.
  - Symptom: `events` output has not updated since 2026-04-27.
  - Symptom: running `logs` as the operator shows journal permission errors:
    `Users in groups 'adm', 'systemd-journal' can see all messages` and
    `No journal files were opened due to insufficient permissions`.
  - Symptom: `sudo logs` fails because `logs` is likely a shell alias or
    function that is not available in the root command path.
  - Confirm whether event scripts are still scheduled/running:
    `<operator>-events.sh`, `<operator>-ble.sh`, `<operator>-presence.sh`,
    `<operator>-scan.sh`, and the Wi-Fi fallback timer/service.
  - Add setup support for journal access, likely by adding the operator user to
    the appropriate journal group or by replacing alias-only `logs` usage with a
    real script that calls `journalctl`.
  - Surface event freshness and log permission health in the web UI.

- Prevent ADS-B regression from Debian `readsb` package.
  - Background: GRIDRUNNER ADS-B depends on the wiedehopf `readsb` build because
    it supports RTL-SDR devices. The Debian/Trixie `readsb` package does not
    support `--device-type rtlsdr` on this setup.
  - Symptom: `readsb.service` enters an auto-restart failure loop with:
    `ERROR: Unknown device type:0` and supported SDR types listed as only
    `modesbeast`, `gnshulc`, `ifile`, and `none`.
  - Symptom: `/tar1090/data/aircraft.json` returns 404 or no aircraft data
    because `readsb` is not writing JSON.
  - Acceptance criteria:
    - Install/setup scripts must not run `apt install readsb`.
    - Documentation clearly states: do not install Debian `readsb`.
    - ADS-B setup uses the wiedehopf installer:
      `sudo bash -c "$(wget -q -O - https://raw.githubusercontent.com/wiedehopf/adsb-scripts/master/readsb-install.sh)"`
    - Health check detects whether `readsb` supports RTL-SDR.
    - `ghost-health.sh` reports `readsb OK (RTL supported)` or
      `readsb BROKEN (no RTL support)`.
    - Optional: setup script runs `sudo apt-mark hold readsb` after installing
      the correct build.
    - Web UI shows ADS-B degraded if `readsb` is running but lacks RTL-SDR
      support.
  - Validation commands:
    - `systemctl status readsb --no-pager`
    - `sudo journalctl -u readsb -n 30 --no-pager`
    - `readsb --help | grep rtlsdr`
    - `curl -s http://localhost/tar1090/data/aircraft.json | head`

- Stabilize Wi-Fi failover and fallback hotspot behavior.
  - Goal: GRIDRUNNER joins known Wi-Fi networks when available and starts its
    own fallback hotspot when no known networks are reachable.
  - Failure mode observed: failover did not work after leaving known Wi-Fi range
    and rebooting out of range.
  - Acceptance criteria:
    - `gridrunner-wifi.service` runs with permissions sufficient to control
      NetworkManager.
    - `gridrunner-wifi.timer` runs reliably at boot and on a regular interval.
    - If a known Wi-Fi network is reachable, GRIDRUNNER connects to it.
    - If no known Wi-Fi is reachable, GRIDRUNNER starts `GRIDRUNNER-HOTSPOT`.
    - If a known Wi-Fi network returns while hotspot mode is active, GRIDRUNNER
      switches back to known Wi-Fi.
    - Web UI surfaces current network mode, active connection, and hotspot IP.
  - Validation commands:
    - `systemctl status gridrunner-wifi.timer --no-pager`
    - `systemctl status gridrunner-wifi.service --no-pager`
    - `journalctl -u gridrunner-wifi.service -n 80 --no-pager`
    - `nmcli -t -f DEVICE,STATE,CONNECTION dev`

## Web UI / Control Plane

- Add service status cards to the FastAPI web control panel.
  - Show status for `readsb`, `lighttpd`, `gridrunner-web`,
    `gridrunner-wifi.timer`, and `gridrunner-wifi.service`.
  - Use compact mobile-friendly cards for iPhone access.
  - Show degraded state when a service is failed or restarting.

- Add ADS-B integration to the web UI.
  - Provide a link to `http://gridrunner.local/tar1090/`.
  - Display aircraft count from `/tar1090/data/aircraft.json`.
  - Display a short recent aircraft list with flight, altitude, ground speed,
    track, and last seen time.
  - Handle ADS-B unavailable/degraded state gracefully.

- Add safe script controls to the web UI.
  - Keep command execution restricted to a whitelist.
  - Buttons should include health, backup, inventory, ham check, ADS-B mode,
    SDR mode, run events, and Wi-Fi status.
  - Do not add arbitrary shell execution.
  - Add clear warnings for disruptive actions such as switching SDR mode or
    stopping ADS-B.

- Add event log viewer and freshness indicator.
  - Show recent `ghost-events.log` lines.
  - Show last event timestamp.
  - Warn if events are stale.
  - Provide a download link for event logs if feasible.

- Add basic authentication before exposing the web UI beyond the local network.
  - Keep local-only mode as the default.
  - Document safe use with Tailscale or VPN before remote exposure.

## CLI / Operator Workflow

- Create a `ghostctl` CLI wrapper.
  - Commands:
    - `ghostctl health`
    - `ghostctl backup`
    - `ghostctl inventory`
    - `ghostctl hamcheck`
    - `ghostctl adsb`
    - `ghostctl sdr`
    - `ghostctl events`
    - `ghostctl wifi status`
  - Wrap existing scripts in `~/gridrunner/scripts` and legacy scripts in
    `/home/ghost`.
  - Update README and AGENTS.md with usage.

- Improve tmux dashboard layout.
  - Keep core dashboard separate from sensor/radio dashboard.
  - Add an airspace/network window with ADS-B and network scan panes.
  - Add a radio utilities window for SDR, `rtl_433`, JS8Call/Winlink notes,
    and ham checks.

- Normalize aliases into scripts.
  - Replace alias-only commands such as `logs` with real scripts in
    `~/gridrunner/scripts`.
  - Ensure commands work under systemd, web UI, and interactive shells.

## Radio / SDR / Ham Utilities

- Add SDR mode management.
  - Preserve ADS-B as the default mode using `readsb`.
  - Stop `readsb` before launching SDR++ when only one RTL-SDR is present.
  - Restart `readsb` after SDR exploration.
  - Detect multiple SDR dongles and support assigning one to ADS-B and one to
    general SDR exploration.

- Add SDR++ documentation and launcher support.
  - Document build dependencies for Debian/Raspberry Pi OS.
  - Note disabled optional modules such as Airspy HF and PlutoSDR if not used.
  - Add launcher instructions for GUI/local use.

- Add ham radio readiness checks.
  - Detect serial devices: `/dev/ttyUSB*`, `/dev/ttyACM*`, and
    `/dev/serial/by-id/*`.
  - Detect audio devices with `aplay -l` and `arecord -l`.
  - Include `rigctl`/hamlib checks for Xiegu G90 compatibility.
  - Prepare for newer Xiegu G90 CAT/audio interface card.

- Add JS8Call and Winlink integration plan.
  - Document G90 requirements:
    - CAT interface device path
    - USB audio input/output
    - radio mode `U-D` / USB data mode
    - low-power transmit testing
  - Add Pat Winlink config backup paths to the backup script.
  - Add future RF Winlink support via Dire Wolf or other supported modem stack.

## Time, GPS, RTC, and Field Reliability

- Add GPS integration.
  - Prefer USB GPS initially for modularity.
  - Install and configure `gpsd`, `gpsd-clients`, and `chrony`.
  - Add a GPS status panel to the web UI.
  - Add GPS/time status to `ham-check.sh`.

- Add RTC support.
  - Evaluate DS3231 RTC HAT or small I2C DS3231 module.
  - Add setup documentation for kernel overlay configuration.
  - Define time source priority: NTP when online, GPS when available, RTC when
    offline.

- Add power/battery readiness checks.
  - Track under-voltage, throttling, temperature, and uptime.
  - Surface power warnings in web UI and `ghost-health.sh`.

## Storage / Data Retention

- Add external USB storage support.
  - Provide a modern web UI for selecting an external media volume.
  - Move/offload data that does not need to live on the OS partition.
  - Preserve fast OS storage for system/runtime files.
  - Support log, backup, SDR capture, and ADS-B history storage locations.

- Add log rotation and retention policy.
  - Rotate `ghost-events.log`.
  - Ensure backups and captures cannot fill the OS partition.
  - Surface disk usage warnings in the web UI.

## Planned Enhancements

- Add media streaming server support.
  - Evaluate DLNA as the initial option.
  - Let the user choose internal card storage or external media storage.

- Add GPIO touchscreen setup support.
  - Prompt during setup for popular GPIO touchscreen models.
  - Install the selected screen drivers.
  - When a screen is present, provide a startup display mode for ADS-B map,
    tmux dashboard, or the web UI.

- Add Codex/automation hardening.
  - Ensure AGENTS.md warns against installing Debian `readsb`.
  - Add testing checklist for ADS-B, Wi-Fi fallback, web UI, and radio scripts.
  - Keep changes small and reversible.
  - Prefer explicit rollback commands for networking and radio changes.
