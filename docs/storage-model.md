# GRIDRUNNER Storage Model

This document defines the storage layout for future external USB media support.
It is a design contract only; current setup does not move data automatically.

## Goals

- Keep the operating system and service-critical runtime files on fast internal
  storage.
- Allow large or fast-growing data to move to an operator-selected external
  media volume.
- Preserve a safe rollback path if external media is missing, slow, corrupted,
  or removed.
- Keep all paths explicit and inspectable from the web UI before any migration.

## Internal-Only Paths

These must remain on the OS partition:

```text
~/gridrunner/
~/gridrunner/web/
~/gridrunner/scripts/
~/gridrunner/deploy/
~/gridrunner/state/
~/gridrunner/web/.venv/
/etc/systemd/system/gridrunner-*.service
/etc/systemd/system/gridrunner-*.timer
```

Rationale:

- The web UI, installers, health scripts, and service units must continue to
  boot without external media.
- `state/` contains install state and rendered service files that are needed to
  repair or reconfigure the node.
- Python virtual environments and service code should not depend on removable
  media being present.

## Movable Data Classes

The following data classes may move to external media:

| Data class | Current/default path | Future external path |
| --- | --- | --- |
| Backups | `~/gridrunner/data/backups/` | `<volume>/gridrunner/backups/` |
| Operator logs | `/home/<operator>/<operator>-events.log` | `<volume>/gridrunner/logs/<operator>-events.log` |
| Rotated logs | `/home/<operator>/<operator>-events.log.*` | `<volume>/gridrunner/logs/` |
| SDR captures | `~/gridrunner/sdr/` | `<volume>/gridrunner/sdr/` |
| Radio artifacts | `~/gridrunner/radio/` | `<volume>/gridrunner/radio/` |
| ADS-B history | future `~/gridrunner/data/adsb/` | `<volume>/gridrunner/adsb/` |
| Media server library | not installed by default | `<volume>/gridrunner/media/` |

## Required Configuration

Future implementation should write a single environment file:

```text
~/gridrunner/state/storage.env
```

Proposed keys:

```bash
GRIDRUNNER_STORAGE_MODE=internal|external
GRIDRUNNER_STORAGE_VOLUME_UUID=<uuid>
GRIDRUNNER_STORAGE_MOUNT=/media/<operator>/<label>
GRIDRUNNER_STORAGE_ROOT=/media/<operator>/<label>/gridrunner
GRIDRUNNER_BACKUP_DIR=<root>/backups
GRIDRUNNER_EVENTS_LOG=<root>/logs/<operator>-events.log
GRIDRUNNER_SDR_DIR=<root>/sdr
GRIDRUNNER_RADIO_DIR=<root>/radio
GRIDRUNNER_ADSB_HISTORY_DIR=<root>/adsb
GRIDRUNNER_MEDIA_DIR=<root>/media
```

Services should load this file with `EnvironmentFile=-...` only after the
selected paths exist and are writable.

## Web UI Flow

The web UI should present external storage as a guided, reversible workflow:

1. Detect removable mounted volumes with device, label, filesystem, UUID, size,
   free space, mount point, and writable state.
2. Let the operator choose a volume and storage classes to move.
3. Show a preflight checklist:
   - filesystem writable
   - minimum free space available
   - target directory can be created
   - existing target data will not be overwritten silently
   - internal rollback path exists
4. Copy selected data with preserve mode and timestamps.
5. Verify copied file counts and byte counts.
6. Write `state/storage.env`.
7. Restart only affected services.
8. Show active storage mode and rollback action.

The UI must not auto-format drives or erase data.

## Rollback Behavior

If the external volume is missing or not writable:

- Web UI and core services must still start from internal storage.
- Health checks should report storage as degraded, not fatal.
- Event collection should fall back to the internal operator log path.
- Backups should fall back to `~/gridrunner/data/backups/`.
- SDR capture and media server controls should be disabled until storage is
  restored or switched back to internal.

Rollback should:

1. Stop affected services.
2. Rewrite `state/storage.env` to `GRIDRUNNER_STORAGE_MODE=internal`.
3. Restart affected services.
4. Leave external data intact.
5. Report both internal and external paths for manual inspection.

## Implementation Notes

- Prefer UUID-based volume identity over label or mount path.
- Do not symlink service-critical directories.
- Avoid bind mounts for the first implementation; explicit environment paths are
  easier to debug and safer to roll back.
- Never move `~/gridrunner/state`.
- Keep log rotation and backup retention active regardless of storage mode.
- Add tests for missing volume, read-only volume, insufficient free space, and
  rollback.
