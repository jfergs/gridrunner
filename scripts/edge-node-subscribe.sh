#!/bin/bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MQTT_HOST="${GRIDRUNNER_EDGE_NODE_MQTT_HOST:-${GRIDRUNNER_MQTT_HOST:-localhost}}"
MQTT_PORT="${GRIDRUNNER_EDGE_NODE_MQTT_PORT:-${GRIDRUNNER_MQTT_PORT:-1883}}"
MQTT_TOPIC="${GRIDRUNNER_EDGE_NODE_TOPIC:-gridrunner/nodes/+/telemetry}"

if ! command -v mosquitto_sub >/dev/null 2>&1; then
  echo "mosquitto_sub is required for edge-node MQTT subscription."
  exit 1
fi

echo "GRIDRUNNER_EDGE_NODE_SUBSCRIBE status=starting broker=$MQTT_HOST:$MQTT_PORT topic=$MQTT_TOPIC"

mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" -t "$MQTT_TOPIC" |
  while IFS= read -r payload; do
    if [ -z "$payload" ]; then
      continue
    fi

    if ! printf '%s\n' "$payload" | "$SCRIPT_DIR/edge-node-ingest.sh" -; then
      echo "GRIDRUNNER_EDGE_NODE_SUBSCRIBE status=ingest_failed"
    fi
  done

