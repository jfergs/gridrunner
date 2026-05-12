# GRIDRUNNER Edge-Node Architecture

This note sketches the first ESP32-C6 wearable edge-node layer for
GRIDRUNNER. The Raspberry Pi 5 remains the primary compute node, web UI, SDR
host, ADS-B host, and storage system. ESP32-C6 nodes provide low-power sensing
and local operator status where a full Pi is too expensive to keep awake.

## Goals

- Keep ambient sensing alive while the Pi is sleeping, busy, or power limited.
- Move BLE presence observation closer to the physical area being monitored.
- Preserve the Pi web UI as the single operator surface for summaries, history,
  controls, and future AI-assisted review.
- Make node behavior asynchronous and tolerant of weak Wi-Fi or mesh links.
- Avoid putting sensitive identifiers on small displays unless explicitly
  configured in a trusted environment.

## Initial Hardware

- Waveshare ESP32-C6 1.47in Display Development Board.
- Raspberry Pi 5 GRIDRUNNER base node.
- Optional Meshtastic-compatible radios for future relay profiles.
- Portable battery pack or wearable cell with voltage telemetry.

## System Roles

### ESP32-C6 Edge Node

The first firmware profile should stay intentionally narrow:

- Passive BLE scan summaries.
- RSSI peak tracking.
- Known, unknown, and ignored device counters.
- Short local cache of observations when disconnected.
- Battery and charging state reporting.
- Sync status and last successful uplink timestamp.
- Small local display for operator-glance state.

The edge node should avoid storing raw long-term history. It can keep a bounded
rolling cache for retransmit, but the Pi owns durable storage and analysis.

### Raspberry Pi 5 Base Node

The Pi aggregates and interprets edge-node data:

- Receives node telemetry by MQTT first, with ESPHome as an acceptable future
  management path if it does not constrain the firmware profile.
- Writes normalized events into the existing GRIDRUNNER event/log model.
- Tracks node freshness, battery status, scan counts, and link quality.
- Presents edge-node state in the existing web panel.
- Correlates node BLE observations with local Pi scans, Wi-Fi status, ADS-B,
  SDR mode, and future radio workflows.

## Telemetry Contract

Use a versioned JSON payload so firmware and Pi-side ingestion can evolve
without lockstep deploys.

```json
{
  "schema": "gridrunner.edge_node.v1",
  "node_id": "node-03",
  "profile": "ble-presence",
  "timestamp": "2026-05-12T17:30:00Z",
  "uptime_seconds": 18422,
  "battery": {
    "percent": 82,
    "voltage": 3.98,
    "charging": false
  },
  "link": {
    "transport": "mqtt",
    "rssi": -61,
    "last_sync_seconds": 12
  },
  "ble": {
    "window_seconds": 60,
    "known_count": 5,
    "unknown_count": 13,
    "ignored_count": 2,
    "rssi_peak": -48
  }
}
```

The node should publish summaries rather than raw device identifiers by
default. A future trusted-debug mode may include hashed identifiers, but that
mode should be explicit and visible in the UI.

Suggested MQTT topic layout:

```text
gridrunner/nodes/<node-id>/telemetry
gridrunner/nodes/<node-id>/status
gridrunner/nodes/<node-id>/events
gridrunner/nodes/<node-id>/command
```

## Display Layout

The small display should prioritize glanceable state over decoration.

```text
GRIDRUNNER NODE-03
BLE   18
KNOWN 5
UNK   13
PEAK  -48
SYNC  OK 12s
BATT  82%
```

Failure states should be terse and dominant:

```text
NODE-03
SYNC LOST
LAST 18m
CACHE 42
BATT 77%
```

## Pi Integration Plan

1. Add an optional MQTT install item for a local broker.
2. Add a Pi-side edge-node ingest script that validates telemetry schema,
   normalizes timestamps, and appends summary events.
3. Store latest node state under `state/edge-nodes/` for fast web rendering.
4. Add a compact web panel showing node freshness, battery, link, and BLE
   counts.
5. Add retention and redaction rules before storing any identifier-bearing
   debug payloads.

Initial Pi-side support now exists:

- `edge-node-mqtt` is an optional install item for Mosquitto, MQTT clients, and
  `jq`.
- `scripts/edge-node-ingest.sh` accepts telemetry JSON from stdin or a file,
  validates the `gridrunner.edge_node.v1` summary payload, caches latest state
  under `state/edge-nodes/`, and appends a redacted event summary.
- The web UI reads cached node state and shows freshness, battery, link, and
  BLE summary counts.

The remaining integration gap is the always-on MQTT subscription service that
connects `gridrunner/nodes/+/telemetry` to the ingest script.

## Firmware Profiles

Start with one profile and leave room for later mode switching:

- `ble-presence`: passive BLE summary and local display.
- `mesh-relay`: future low-bandwidth relay status.
- `radio-companion`: future G90/JS8Call/Winlink operator companion.
- `home-assistant-remote`: future local control/status panel.

Profile changes should be commanded from the Pi and acknowledged by the node.
Nodes should fall back to their last known profile after reboot.

## Open Questions

- Whether MQTT should be mandatory for edge nodes or one install option among
  MQTT, ESPHome, and serial ingest.
- Whether hashed BLE identifiers are useful enough to justify handling them.
- How much event history should be cached on the ESP32-C6 when disconnected.
- Which power states should be visible in the main node strip versus a detail
  panel.
