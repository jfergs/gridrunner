# GRIDRUNNER Backlog

Project-local backlog for Gridrunner. Keep detailed Gridrunner implementation
work here; roll up only the current priorities to the global backlog tracker.

## High Priority

- Redesign the web UX/UI around mobile-first field operation.
  - Direction: rugged cassette-cyberdeck field terminal, not a neon poster.
  - Primary target: iPhone Safari; secondary targets: iPad and laptop.
  - Completed foundation:
    - Added sticky horizontal section navigation for phone use.
    - Anchored major control panels for direct jumps.
    - Tightened button, telemetry, and panel sizing for small screens.
    - Added safer wrapping for long storage paths and telemetry values.
    - Reduced decorative background treatment while preserving field-terminal
      identity.
    - Added cassette-futurist quick actions for Wi-Fi, Bluetooth, Network, and
      ADS-B Map.
    - Collapsed less-frequent controls and storage detail into drawers while
      keeping status meters visible.
    - Reworked scan controls with an enable/disable button, profile slider, and
      inline one-shot scan status.
    - Replaced the ADS-B aircraft rows with a newest-first Flight board and
      Track controls.
  - Requirements:
    - Validate the layout on an actual iPhone viewport/device.
    - Confirm all controls remain usable in Safari with no horizontal scrolling.
    - Warning/failure states must be visually dominant.
    - Use restrained cyan/green/amber/red accents; avoid decorative clutter,
      heavy animation, glassmorphism, and excessive magenta/purple.
    - Confirm the drawer-heavy layout keeps common field actions faster than the
      older full-dashboard layout.

- Finish storage UI and health polish.
  - Completed foundation:
    - USB external storage works on-device.
    - Backups and event logs write to the external storage path.
    - Storage panel shows mounted-volume used/free meters.
    - Storage meter output filters pseudo mounts and invalid disk stats.
    - Storage panel warns when external storage UUID is unavailable.
    - Storage meters carry low-space severity.
    - Missing or unwritable external roots fall back to internal paths.
  - Remaining acceptance criteria:
    - Confirm removing or unmounting the USB volume degrades to internal backup
      and event-log paths without breaking the web UI.

- Clarify event freshness and scan-off states.
  - Problem: intentionally skipped event collection can make logs look stale
    even when the timer is healthy and scans are deliberately off.
  - Remaining acceptance criteria:
    - Show when event collection is skipped because Bluetooth and Network Device
      scans are off.
    - Show last successful one-shot or continuous event write.
    - Make the event panel distinguish "healthy but idle" from stale or failed
      event collection.

- Finish security hardening.
  - Completed foundation:
    - `/run`, `/scans`, `/power`, `/install`, and `/install/skip` use shared
      form-token protection.
    - `ruff check web tests`, `shellcheck scripts/*.sh`, and the unit suite pass.
  - Remaining acceptance criteria:
    - Narrow `scripts/setup-sudoers.sh` NOPASSWD rules.
    - Replace shell-sourced Wi-Fi config parsing in `wifi-fallback.sh` and
      `wifi-status.sh` with explicit parsing of expected keys only.
    - Harden ADS-B installer supply chain by downloading before execution and
      pinning or documenting verification.

- Validate Wi-Fi failover and fallback hotspot behavior on device.
  - Completed foundation:
    - Timer and oneshot service are healthy on-device.
    - Manual web controls exist for `Enable Hotspot` and `Connect Known Wi-Fi`.
    - Known-Wi-Fi healthy path is confirmed.
  - Remaining acceptance criteria:
    - Confirm automatic failover starts the fallback hotspot when no known Wi-Fi
      is reachable.
    - Confirm automatic return to known Wi-Fi when a known network returns while
      hotspot mode is active.

- Add scan contention diagnostics and pause controls.
  - Completed foundation:
    - Bluetooth and Network Device scans default to off.
    - One-shot and continuous scan controls are independently gated.
    - Web UI shows which scanners are armed and when the last scan ran.
    - Web UI has an enable/disable scan control and Low Impact/Field profile
      slider.
  - Remaining acceptance criteria:
    - Add diagnostics showing when Wi-Fi, BLE, and network scans start/stop.
    - Provide a temporary mitigation command or web control to pause background
      scanning.
    - Add optional `GRIDRUNNER_WIFI_CONNECTIVITY_CHECK_HOST` for degraded-link
      checks without changing the healthy known-Wi-Fi fast path.

## Recently Completed

- Web form-token hardening for controls.
  - `/run` and `/scans` reject invalid form tokens.
  - `/power` uses the same shared token validation path.
  - Dashboard `/run` and `/scans` forms include hidden form tokens.

- ADS-B dashboard foundation.
  - Dashboard shows a tar1090 link, aircraft count, and a short recent aircraft
    list from local tar1090/readsb aircraft JSON when available.
  - `GRIDRUNNER_ADSB_AIRCRAFT_JSON` can override the local aircraft JSON path.
  - Default aircraft JSON discovery prefers `/run/readsb/aircraft.json` and
    falls back to `/run/tar1090/aircraft.json`.
  - Dashboard shows aircraft JSON data age.
  - Missing or unreadable aircraft data degrades gracefully in the panel.

- ADS-B route enrichment and Flight board.
  - ADS-B panel now uses a newest-first Flight board instead of generic
    aircraft rows.
  - Flight entries show callsign/track identity, route when known, altitude,
    speed, heading, seen age, airline, and Track controls.
  - Optional online route lookup enriches local readsb aircraft with
    origin/destination data when the device has internet access.
  - Route lookup is bounded by request limit, timeout, and in-memory cache
    settings so offline operation stays fast.
  - ADS-B map controls are labeled `Map`.

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
  - Storage meter output filters pseudo mounts and invalid disk stats.
  - Storage panel warns when external storage UUID is unavailable.
  - Storage meters carry low-space severity.
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
  - Event collection appends legacy event script output to the active
    `GRIDRUNNER_EVENTS_LOG`, including external USB log paths.
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
  - Top Quick Actions expose single-tap Wi-Fi, Bluetooth, Network, and Map
    actions.
  - Scan drawer exposes Bluetooth Scan Now and Wi-Fi Scan Now with inline busy
    and result messages.
  - Continuous Bluetooth and Network Device modes are independently gated.
  - Continuous scanning can be enabled or disabled from a single stateful
    control.
  - Scan interval state is stored in `state/scan-controls.env`.
  - Legacy `btmgmt`, `arp-scan`, and `nmap` calls are patched behind the
    dashboard scan controls.
  - Web UI shows which scanners are armed and when the last scan ran.
  - Web UI includes a Low Impact / Field scan profile slider.
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
    - Dashboard shows the tar1090 map link, aircraft count, aircraft JSON data
      age, and a newest-first Flight board from local readsb JSON.
    - Optional online route enrichment adds origin/destination route context
      when internet is available.
  - Remaining acceptance criteria:
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
