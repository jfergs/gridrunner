# GRIDRUNNER ESP32-C6 RF Tracker

Handheld Wi-Fi/BLE/drone tracker MVP for the Waveshare
`ESP32-C6-LCD-1.47` non-touch board.

This is the first vertical slice of GitHub issue `#42`: it performs local-first
passive Wi-Fi access-point discovery and BLE advertisement discovery, shows a
compact radar/list display without requiring the GRIDRUNNER core, and publishes
summary telemetry back to the core over MQTT whenever uplink is available.

## Scope

Current MVP:

- Joins the configured GRIDRUNNER Wi-Fi network.
- Scans nearby Wi-Fi access points even when it is away from the core unit.
- Scans nearby BLE advertisements without publishing device identifiers.
- Shows AP count, BLE count, drone-candidate count, strongest RSSI, selected AP,
  and a radar-style blip view.
- Publishes `gridrunner.edge_node.v1` telemetry to
  `gridrunner/nodes/<node-id>/telemetry`.

Non-goals for this slice:

- No packet injection, deauth, jamming, or offensive Wi-Fi behavior.
- No full drone Remote ID decoding yet. This slice only flags likely drone /
  Remote ID candidates from BLE advertisement metadata and Wi-Fi SSID hints.
- No persistent device history on the ESP32.

## Build Setup

```bash
cd firmware/rf-tracker
cp include/config.example.h include/secrets.h
```

Edit `include/secrets.h`:

```c
#define GRIDRUNNER_WIFI_SSID "your-gridrunner-wifi"
#define GRIDRUNNER_WIFI_PASSWORD "your-password"
#define GRIDRUNNER_MQTT_HOST "gridrunner.local"
#define GRIDRUNNER_NODE_ID "c6-rf-tracker-01"
```

Build and flash:

```bash
pio run
pio run --target upload
```

Local development in this repo can reuse the same PlatformIO cache as the plane
tracker firmware:

```bash
env PLATFORMIO_CORE_DIR=/Users/fergs/dev/gridrunner/.platformio-core ../../.platformio-venv/bin/pio run
```

## MQTT Payload

The tracker publishes compact JSON to:

```text
gridrunner/nodes/<node-id>/telemetry
```

The payload follows the existing edge-node ingest schema and includes a Wi-Fi
summary extension:

```json
{
  "schema": "gridrunner.edge_node.v1",
  "node_id": "c6-rf-tracker-01",
  "profile": "rf-handheld",
  "timestamp": "2026-05-13T14:00:00Z",
  "uptime_seconds": 120,
  "battery": {"percent": 0, "voltage": 0, "charging": false},
  "link": {"transport": "mqtt", "rssi": -55, "last_sync_seconds": 1, "pending_scan_count": 0},
  "ble": {"window_seconds": 30, "known_count": 5, "unknown_count": 11, "ignored_count": 2, "rssi_peak": -48, "scan_count": 4},
  "wifi": {"window_seconds": 15, "ap_count": 8, "strongest_rssi": -42, "strongest_ssid": "GRIDRUNNER"},
  "drone": {"candidate_count": 1, "wifi_count": 0, "ble_count": 1, "rssi_peak": -58}
}
```

The Pi-side `gridrunner-edge-node-ingest.service` stores the full payload under
`state/edge-nodes/`, so the Wi-Fi extension is available for later dashboard
work even before the core event schema is expanded.

The BLE summary treats advertisements with a local name as `known_count`,
unnamed advertisements as `unknown_count`, and signals below
`GRIDRUNNER_BLE_IGNORE_RSSI_BELOW` as `ignored_count`. It intentionally avoids
publishing MAC addresses or raw advertisement payloads.

The tracker is designed to keep scanning and rendering when disconnected from
the core. The footer shows `LOCAL` while away from MQTT and `UP` after telemetry
publishes again. `pending_scan_count` reports how many local scan windows were
observed since the last successful uplink; the firmware does not keep a raw
offline history.
