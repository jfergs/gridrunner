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

## Planned Enhancements

- Add external USB storage support.
  - Provide a modern web UI for selecting an external media volume.
  - Move/offload data that does not need to live on the OS partition.
  - Preserve fast OS storage for system/runtime files.

- Add media streaming server support.
  - Evaluate DLNA as the initial option.
  - Let the user choose internal card storage or external media storage.

- Add GPIO touchscreen setup support.
  - Prompt during setup for popular GPIO touchscreen models.
  - Install the selected screen drivers.
  - When a screen is present, provide a startup display mode for ADS-B map,
    tmux dashboard, or the web UI.
