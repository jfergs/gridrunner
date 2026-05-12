# ESP32-C6 Plane Tracker

This note defines the first GRIDRUNNER plane-tracker path for an ESP32-C6
display node. The Raspberry Pi keeps running `readsb` and tar1090. The ESP32-C6
does not decode ADS-B directly; it subscribes to a compact MQTT summary
published by the Pi.

## Pi Setup

Install the optional MQTT and plane-tracker items from the web install pane, or
from the device shell:

```bash
cd ~/gridrunner
bash scripts/install-items.sh --apply edge-node-mqtt plane-tracker
```

The plane-tracker timer publishes every 10 seconds:

```text
gridrunner/adsb/plane-tracker
```

To test without systemd:

```bash
bash scripts/adsb-plane-tracker.sh --json
bash scripts/adsb-plane-tracker.sh --publish
mosquitto_sub -h localhost -t gridrunner/adsb/plane-tracker -v
```

## MQTT Payload

The retained payload is designed for a small display and avoids route lookups or
large aircraft records.

```json
{
  "schema": "gridrunner.adsb.plane_tracker.v1",
  "status": "present",
  "generated_at": "2026-05-12T18:00:00Z",
  "source": "/run/readsb/aircraft.json",
  "topic": "gridrunner/adsb/plane-tracker",
  "age_seconds": 3,
  "count": 12,
  "aircraft": [
    {
      "ident": "GRID01",
      "altitude": 1200,
      "speed": 145.5,
      "track": 87,
      "seen_seconds": 2,
      "squawk": "1200",
      "category": "A1",
      "lat": 40.0,
      "lon": -74.0
    }
  ]
}
```

`status` may be `present`, `missing`, or `degraded`. The ESP32 should keep the
last valid display if a publish is missed, but show `NO ADS-B` when `status` is
not `present` or when `age_seconds` grows beyond the display timeout.

## ESP32-C6 Firmware Target

Minimum firmware behavior:

- Join the GRIDRUNNER Wi-Fi or hotspot network.
- Connect to the Pi MQTT broker.
- Subscribe to `gridrunner/adsb/plane-tracker`.
- Display aircraft count, data age, and the first one to five aircraft rows.
- Prefer callsign/hex, altitude, speed, heading, and seen age.
- Do not store aircraft history on the ESP32.

Recommended display layout:

```text
GRIDRUNNER ADS-B
AIR 12   AGE 3s
GRID01 1200 145 087
DEF456 2200 --- ---
```

Configure these on the Pi if needed:

```bash
export GRIDRUNNER_MQTT_HOST=localhost
export GRIDRUNNER_MQTT_PORT=1883
export GRIDRUNNER_PLANE_TRACKER_TOPIC=gridrunner/adsb/plane-tracker
export GRIDRUNNER_PLANE_TRACKER_LIMIT=5
export GRIDRUNNER_ADSB_AIRCRAFT_JSON=/run/readsb/aircraft.json
```
