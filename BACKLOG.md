# GRIDRUNNER Backlog

Project-local backlog for Gridrunner. Keep detailed Gridrunner implementation
work here; roll up only the current priorities to the global backlog tracker.

## Top Priority

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

- Verify GRIDRUNNER events timer in the field.
  - Confirm `gridrunner-events.timer` stays active after reboot.
  - Confirm `gridrunner-events.service` no longer reports failed when the
    bounded collection window times out with exit code `124`.
  - Confirm Recent Events moves from `STALE` to fresh after the timer runs.
  - Confirm `logs` works after the operator logs out and back in, or after a
    reboot applies journal group membership.

- Add service status cards and self-test panel to the web UI.
  - Show status for `gridrunner-web`, `gridrunner-wifi.timer`,
    `gridrunner-wifi.service`, `gridrunner-events.timer`, `readsb`, and
    `lighttpd`.
  - Present fast checks in a boot-log style list: web service, Wi-Fi timer,
    event freshness, ADS-B RTL support, disk space, temperature, and journal
    access.
  - Each line should show `OK`, `WARN`, or `FAIL` with clear color and no
    animation dependency.
  - Reuse existing health scripts where possible instead of duplicating logic.

- Add log rotation and disk guardrails.
  - Rotate `ghost-events.log`.
  - Ensure backups and captures cannot fill the OS partition.
  - Surface disk usage warnings in the web UI.
  - Treat this as prerequisite work before larger storage/offload features.

- Harden web UI exposure.
  - Keep local-only mode as the default.
  - Require/document `GRIDRUNNER_WEB_PASSWORD` before use beyond a trusted local
    device.
  - Document safe use with Tailscale or VPN before remote exposure.

## Recently Completed

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

- Design storage location model.
  - Define which paths are allowed to move off the OS partition.
  - Keep service-critical runtime files on internal storage.
  - Define rollback behavior if an external volume is removed or fails.

- Add external USB storage support.
  - Provide a modern web UI for selecting an external media volume.
  - Move/offload data that does not need to live on the OS partition.
  - Preserve fast OS storage for system/runtime files.
  - Support log, backup, SDR capture, and ADS-B history storage locations.

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
