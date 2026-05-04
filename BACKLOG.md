# GRIDRUNNER Backlog

Project-local backlog for Gridrunner. Keep detailed Gridrunner implementation
work here; roll up only the current priorities to the global backlog tracker.

## Top Priority

- Finish web/security hardening.
  - Context: May 2026 review found no failing tests, but identified hardening
    items that should be handled before broader remote access.
  - Completed foundation:
    - `/run` and `/scans` use shared form-token protection.
    - `/power` uses the same shared token validation.
    - `ruff check web tests` passes after targeted test import annotations.
    - `shellcheck scripts/*.sh` has one reviewed informational finding in
      `scripts/patch-events-script.sh` for literal shell text matching.
  - Remaining acceptance criteria:
    - Add shared form-token protection to install routes:
      - `/install`
      - `/install/skip`
    - Narrow `scripts/setup-sudoers.sh` NOPASSWD rules:
      - Replace wildcard `apt-get install -y *` with fixed package command
        shapes used by `install-items.sh`.
      - Replace wildcard systemd install source paths with exact generated
        project paths.
      - Replace `bash */scripts/install-adsb-readsb.sh` with an exact script
        path.
      - Replace broad `nmcli connection *` rules with the narrowest practical
        hotspot/known-network command shapes.
    - Replace shell-sourced Wi-Fi config parsing in `wifi-fallback.sh` and
      `wifi-status.sh` with explicit parsing of expected keys only.
    - Harden ADS-B installer supply chain:
      - Prefer pinned installer URL or commit.
      - Download to a file before execution.
      - Add checksum or documented manual verification path.
  - Validation commands:
    - `web/.venv/bin/python -m unittest discover -s tests`
    - `bash -n scripts/*.sh`
    - `python3 -m py_compile web/*.py tests/*.py`
    - `web/.venv/bin/python -m ruff check web tests`
    - `shellcheck scripts/*.sh`

- Validate Wi-Fi failover and fallback hotspot behavior on device.
  - Goal: GRIDRUNNER joins known Wi-Fi networks when available and starts its
    own fallback hotspot when no known networks are reachable.
  - Completed foundation:
    - `wifi-fallback.sh` exits early when connected to known Wi-Fi and
      NetworkManager reports full connectivity.
    - Degraded stale-link checks respect `GRIDRUNNER_WIFI_RESCAN_MIN_SECONDS`.
    - Web UI surfaces mode, IP, timer/service state, and last Wi-Fi action.
    - Web UI includes manual `Enable Hotspot` and `Connect Known Wi-Fi`
      controls with matching `wifi-fallback.sh hotspot|known` commands.
  - Remaining acceptance criteria:
    - Confirm `gridrunner-wifi.timer` runs reliably at boot and on a regular
      interval after `sudo scripts/setup-sudoers.sh` has been rerun on-device.
    - Confirm automatic failover starts `GRIDRUNNER-HOTSPOT` when no known
      Wi-Fi is reachable.
    - Confirm automatic return to known Wi-Fi when a known network returns while
      hotspot mode is active.
    - Confirm manual web controls work from iPhone/laptop against the running
      device.
  - Validation commands:
    - `bash scripts/wifi-fallback.sh hotspot`
    - `bash scripts/wifi-fallback.sh known`
    - `bash scripts/wifi-status.sh`
    - `systemctl status gridrunner-wifi.timer --no-pager`
    - `systemctl status gridrunner-wifi.service --no-pager`
    - `journalctl -u gridrunner-wifi.service -n 80 --no-pager`
    - `nmcli -t -f DEVICE,STATE,CONNECTION dev`

- Add scan contention diagnostics and pause controls.
  - Symptom: when GRIDRUNNER is connected to the home Wi-Fi network, the whole
    network appears to slow down for roughly 30 seconds every couple of minutes.
  - Completed foundation:
    - Bluetooth and network device scans default to off.
    - Web UI provides separate Bluetooth and Network Device one-shot controls.
    - Continuous Bluetooth and Network Device modes are independently gated.
    - Legacy `btmgmt`, `arp-scan`, and `nmap` calls are patched behind scan
      phase controls.
    - Web UI surfaces armed scanner state and last scan age.
    - Recommended low-contention defaults are documented in README.
  - Remaining acceptance criteria:
    - Add diagnostics that show when Wi-Fi, BLE, and network scans start/stop.
    - Web UI and/or `ghost-health` surfaces active scan timers and last scan
      timestamps.
    - Identify whether `gridrunner-wifi.timer`, event collection, tmux dashboard,
      or manual scripts are triggering periodic slowdown.
    - Provide a temporary mitigation command or web control to pause background
      scanning.
    - Add optional `GRIDRUNNER_WIFI_CONNECTIVITY_CHECK_HOST` for degraded-link
      checks without changing the healthy known-Wi-Fi fast path.
  - Validation commands:
    - `systemctl list-timers --all`
    - `ps aux | grep -E 'wifi|ble|scan|nmap|nmcli|arp-scan|btmgmt'`
    - `journalctl -u gridrunner-wifi.service -f`
    - `journalctl -u gridrunner-events.service -f`
    - `nmcli general connectivity`

## Recently Completed

- Web form-token hardening for controls.
  - `/run` and `/scans` reject invalid form tokens.
  - `/power` uses the same shared token validation path.
  - Dashboard `/run` and `/scans` forms include hidden form tokens.

- ADS-B dashboard foundation.
  - Dashboard shows a tar1090 link, aircraft count, and a short recent aircraft
    list from local tar1090/readsb aircraft JSON when available.
  - `GRIDRUNNER_ADSB_AIRCRAFT_JSON` can override the local aircraft JSON path.
  - Missing or unreadable aircraft data degrades gracefully in the panel.

- Lint/tooling baseline.
  - `ruff` is installed in `web/.venv`.
  - `web/.venv/bin/python -m ruff check web tests` passes.
  - `shellcheck` is installed for shell script linting.
  - `shellcheck scripts/*.sh` passes with the intentional literal shell text
    match documented inline.

- Wi-Fi manual controls.
  - Web UI includes `Enable Hotspot` and `Connect Known Wi-Fi`.
  - `scripts/wifi-fallback.sh hotspot` forces fallback hotspot mode.
  - `scripts/wifi-fallback.sh known` leaves hotspot mode only when a known
    network is visible, avoiding accidental loss of access.
  - `scripts/setup-sudoers.sh` grants NetworkManager write operations needed by
    the web/operator Wi-Fi controls.

- Managed foreground presence scanner.
  - `scripts/ghost-presence.sh` installs as
    `/home/<operator-user>/<operator-user>-presence.sh`.
  - The wrapper respects dashboard Network Device scan controls before running
    `arp-scan --localnet`.
  - Installed wrapper resolves `~/gridrunner/state/scan-controls.env` correctly.

- Web UI exposure hardening.
  - Web UI self-test reports whether `GRIDRUNNER_WEB_PASSWORD` is configured.
  - Missing web password is shown as a warning/failure state.
  - README documents local/trusted LAN/VPN use and warns against direct internet
    exposure.

- Storage location model.
  - Documented internal-only service/runtime paths.
  - Defined movable data classes for backups, logs, SDR captures, radio
    artifacts, ADS-B history, and media libraries.
  - Defined rollback behavior when external media is missing or not writable.
  - Captured the web UI flow and storage environment contract.

- External USB storage controls.
  - Web UI Storage panel detects mounted USB volumes and can enable/disable
    external operator-data storage.
  - `scripts/storage-control.sh` writes `state/storage.env` with explicit
    backup, event log, SDR, radio, ADS-B history, and media paths.
  - Storage panel shows mounted-volume used/free disk-space meters.
  - Backups, event health, log rotation, event collection, and system health
    honor `storage.env` and fall back to internal paths when external storage is
    missing or not writable.
  - Systemd templates load `state/storage.env` for web and events services.

- GRIDRUNNER node status strip.
  - Web UI shows compact chips for node, Wi-Fi, events, event timer, ADS-B, and
    web service state.
  - Chip severity is derived from existing health data instead of hardcoded
    labels.
  - Mobile chip sizing is tuned for iPhone and iPad use.

- ADS-B regression prevention.
  - ADS-B Map control resolves directly to the tar1090 map URL.
  - ADS-B map navigation is covered separately from ADS-B mode switching.
  - Default map URL resolution and explicit `GRIDRUNNER_ADSB_MAP_URL` overrides
    are covered by tests.

- Prevent ADS-B regression from Debian `readsb` package.
  - Install/setup scripts use the wiedehopf installer helper instead of
    `apt install readsb`.
  - Documentation warns against the Debian `readsb` package for GRIDRUNNER
    ADS-B.
  - Component health degrades ADS-B when `readsb` lacks RTL-SDR support.

- Stale events and log access foundation.
  - Event log resolution prefers the active `<operator>-events.log` file.
  - Recent Events reports missing logs without leaking raw `tail` errors.
  - Setup adds the operator to journal access groups when available.
  - `logs` is available as a real script path for web UI and shell use.
  - `gridrunner-events.timer` installs periodic event collection.

- Event timer and legacy scanner cleanup.
  - `gridrunner-events.service` calls the repo-managed `scripts/run-events.sh`.
  - Legacy `btmgmt find` calls are bounded during `events-service` install.
  - Event collection reports success when the log updates despite known legacy
    script cleanup errors.
  - Recent Events correctly reports stale/fresh with a 15-minute default
    threshold.

- Log rotation and disk guardrails.
  - `scripts/rotate-logs.sh` rotates the operator events log.
  - Scheduled event collection runs log rotation before writing new events.
  - `scripts/system-backup.sh` prunes old backups with `GRIDRUNNER_BACKUP_KEEP`.
  - `scripts/disk-health.sh` reports warning and critical disk usage states.

- Service status cards and self-test panel.
  - Web UI shows self-test cards for `gridrunner-web`, `gridrunner-wifi.timer`,
    `gridrunner-wifi.service`, `gridrunner-events.timer`, `readsb`, `lighttpd`,
    event freshness, ADS-B RTL support, and disk state.
  - `scripts/service-health.sh` emits machine-readable service unit health.
  - `scripts/system-health.sh` includes service and disk guardrail output.

- Dashboard scan controls.
  - Bluetooth and network discovery scans default to off.
  - Web UI supports separate Bluetooth and Network Device one-shot scan controls.
  - Continuous Bluetooth and Network Device modes are independently gated.
  - Scan interval state is stored in `state/scan-controls.env`.
  - Legacy `btmgmt`, `arp-scan`, and `nmap` calls are patched behind the
    dashboard scan controls.
  - Web UI shows which scanners are armed and when the last scan ran.
  - Web UI includes Low Impact and Field scan profile presets.
  - Recommended low-contention scan defaults are documented in README.

- Wi-Fi rescan throttling.
  - `wifi-fallback.sh` skips healthy known Wi-Fi without rescanning.
  - Degraded stale-link checks respect `GRIDRUNNER_WIFI_RESCAN_MIN_SECONDS`.
  - Last Wi-Fi rescan timestamp is stored in `state/wifi-rescan.last`.

- Wi-Fi fallback action visibility.
  - `wifi-fallback.sh` records the last fallback action in `state/wifi-action.env`.
  - `wifi-status.sh` emits `last_action` and `last_action_age_seconds`.
  - Web UI Wi-Fi Telemetry shows the last fallback action.

## Web UI / Control Plane

- Continue retrofuture field terminal refinement.
  - Direction: portable cyberdeck control surface, not a marketing page.
  - Use dark terminal panels, restrained CRT/scanline texture, subtle chrome or
    metal borders, and neon green/cyan/amber status accents.
  - Preserve field usability: dense information, large iPhone/iPad touch
    targets, predictable navigation, and no decorative clutter over controls.
  - Avoid chaotic 90s collage, sound effects, heavy animation, and experimental
    navigation that slows down device operation.

- Add a BIOS-style startup/status header.
  - Inspired by Quentin.XYZ's BIOS boot sequence, show a compact system identity
    block with device role, software version, boot time, uptime, CPU/temp, memory,
    storage, Wi-Fi mode, and radio state.
  - Use the treatment as a real status surface, not a fake loading screen that
    delays access to controls.
  - Keep values sanitized by default and reveal host/network identifiers only
    when `GRIDRUNNER_SHOW_IDENTIFIERS=1`.

- Add retrofuture ADS-B and Wi-Fi visual treatments.
  - ADS-B: show aircraft count, RTL support state, readsb state, and tar1090
    link as an instrument panel.
  - Wi-Fi: show mode, IP, timer, and service state as field-radio telemetry.
  - Use motion only for meaningful state such as scanning, live, degraded, or
    reconnecting.

- Deepen ADS-B integration in the web UI.
  - Current foundation:
    - Dashboard shows tar1090 link, aircraft count, and a short recent aircraft
      list from local tar1090/readsb aircraft JSON when available.
  - Remaining acceptance criteria:
    - Add aircraft freshness/age for the aircraft JSON file itself.
    - Display readsb/lighttpd service state alongside aircraft count.
    - Add richer aircraft fields when available, such as squawk, category,
      vertical rate, and emergency state.
    - Handle ADS-B unavailable/degraded state with explicit operator guidance.

- Add safe script controls to the web UI.
  - Keep command execution restricted to a whitelist.
  - Current foundation:
    - Buttons include health, backup, inventory, ham check, ADS-B mode, SDR
      mode, logs, Wi-Fi status, Wi-Fi hotspot, known Wi-Fi, and scan controls.
  - Remaining acceptance criteria:
    - Add clearer warnings for disruptive radio actions such as switching SDR
      mode or stopping ADS-B.
  - Do not add arbitrary shell execution.

- Add event log viewer and freshness indicator.
  - Show recent `ghost-events.log` lines.
  - Show last event timestamp.
  - Warn if events are stale.
  - Provide a download link for event logs if feasible.

- Add sparse terminal navigation affordances.
  - Use compact keyboard-like labels for major sections: `F1 HEALTH`, `F2 WIFI`,
    `F3 ADS-B`, `F4 LOGS`, while keeping current touch buttons visible.
  - Do not require keyboard navigation; this is visual orientation and optional
    shortcut support.
  - Preserve iPhone/iPad tap ergonomics.

- Add an optional fullscreen operator mode.
  - Provide a clear fullscreen control for iPad/kiosk/touchscreen use, similar
    to the Quentin.XYZ fullscreen prompt.
  - Keep the regular browser layout fully usable without fullscreen.
  - Make the fullscreen mode rememberable per browser if practical.

- Restyle command controls as hardware-console buttons.
  - Keep the existing whitelisted command model.
  - Make Health, Wi-Fi Status, Logs, ADS-B Mode, SDR Mode, and Backup feel like
    console controls with clear pressed/disabled/danger states.
  - Keep touch targets large and stable on iPhone and iPad.

- Restyle output panels as command-console readouts.
  - Use monospace output, compact headers, scan-friendly section dividers, and
    severity badges.
  - Preserve copy/paste friendly text output for logs, events, and health.
  - Add subtle boot/check styling for startup or refresh states without hiding
    live operational data.

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

- Validate external USB storage on device.
  - Confirm the web UI detects the mounted USB volume on Raspberry Pi OS.
  - Confirm enabling USB storage writes `state/storage.env` and creates
    `<volume>/gridrunner/{backups,logs,sdr,radio,adsb,media}`.
  - Confirm event collection writes to the external event log after service
    restart.
  - Confirm removing or unmounting the USB volume degrades to internal backup
    and event-log paths without breaking the web UI.
  - Add storage warnings for low free space and missing selected UUID.

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
