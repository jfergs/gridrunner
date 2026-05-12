#!/bin/bash
set -u

ADSB_AIRCRAFT_JSON="${GRIDRUNNER_ADSB_AIRCRAFT_JSON:-/run/readsb/aircraft.json}"
PLANE_TRACKER_TOPIC="${GRIDRUNNER_PLANE_TRACKER_TOPIC:-gridrunner/adsb/plane-tracker}"
PLANE_TRACKER_BROKER="${GRIDRUNNER_MQTT_HOST:-localhost}"
PLANE_TRACKER_PORT="${GRIDRUNNER_MQTT_PORT:-1883}"
PLANE_TRACKER_LIMIT="${GRIDRUNNER_PLANE_TRACKER_LIMIT:-5}"
MODE="json"

if [ "${1:-}" = "--publish" ]; then
  MODE="publish"
elif [ "${1:-}" = "--status" ]; then
  MODE="status"
elif [ "${1:-}" = "--json" ] || [ -z "${1:-}" ]; then
  MODE="json"
else
  echo "Usage: $0 [--json|--publish|--status]"
  exit 2
fi

file_mtime() {
  stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0
}

json_payload() {
  local now=""
  local now_epoch=""
  local mtime=""
  local age=""

  now="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  now_epoch="$(date +%s)"

  if [ ! -f "$ADSB_AIRCRAFT_JSON" ]; then
    jq -n \
      --arg generated_at "$now" \
      --arg source "$ADSB_AIRCRAFT_JSON" \
      --arg topic "$PLANE_TRACKER_TOPIC" \
      '{
        schema: "gridrunner.adsb.plane_tracker.v1",
        status: "missing",
        generated_at: $generated_at,
        source: $source,
        topic: $topic,
        age_seconds: null,
        count: 0,
        aircraft: []
      }'
    return
  fi

  mtime="$(file_mtime "$ADSB_AIRCRAFT_JSON")"
  age=$((now_epoch - mtime))
  if [ "$age" -lt 0 ]; then
    age=0
  fi

  if ! jq empty "$ADSB_AIRCRAFT_JSON" >/dev/null 2>&1; then
    jq -n \
      --arg generated_at "$now" \
      --arg source "$ADSB_AIRCRAFT_JSON" \
      --arg topic "$PLANE_TRACKER_TOPIC" \
      --argjson age "$age" \
      '{
        schema: "gridrunner.adsb.plane_tracker.v1",
        status: "degraded",
        generated_at: $generated_at,
        source: $source,
        topic: $topic,
        age_seconds: $age,
        count: 0,
        aircraft: []
      }'
    return
  fi

  jq \
    --arg generated_at "$now" \
    --arg source "$ADSB_AIRCRAFT_JSON" \
    --arg topic "$PLANE_TRACKER_TOPIC" \
    --argjson age "$age" \
    --argjson limit "$PLANE_TRACKER_LIMIT" \
    '
      def clean_ident:
        tostring | gsub("^\\s+|\\s+$"; "") | if length == 0 then "-" else . end;

      (.aircraft // []) as $aircraft
      | ($aircraft | map(select(type == "object"))) as $valid
      | {
          schema: "gridrunner.adsb.plane_tracker.v1",
          status: "present",
          generated_at: $generated_at,
          source: $source,
          topic: $topic,
          age_seconds: $age,
          count: ($valid | length),
          aircraft: (
            $valid
            | sort_by(if (.seen | type) == "number" then .seen else 999999 end)
            | .[:$limit]
            | map({
                ident: ((.flight // .hex // "-") | clean_ident),
                altitude: (.alt_baro // .alt_geom // null),
                speed: (.gs // null),
                track: (.track // null),
                seen_seconds: (if (.seen | type) == "number" then (.seen | floor) else null end),
                squawk: ((.squawk // "") | tostring),
                category: ((.category // "") | tostring),
                lat: (.lat // null),
                lon: (.lon // null)
              })
          )
        }
    ' "$ADSB_AIRCRAFT_JSON"
}

payload="$(json_payload)"

if [ "$MODE" = "status" ]; then
  printf 'GRIDRUNNER_PLANE_TRACKER status=%s count=%s topic=%s broker=%s source=%s\n' \
    "$(printf '%s' "$payload" | jq -r '.status')" \
    "$(printf '%s' "$payload" | jq -r '.count')" \
    "$PLANE_TRACKER_TOPIC" \
    "$PLANE_TRACKER_BROKER:$PLANE_TRACKER_PORT" \
    "$ADSB_AIRCRAFT_JSON"
  exit 0
fi

if [ "$MODE" = "json" ]; then
  printf '%s\n' "$payload"
  exit 0
fi

if ! command -v mosquitto_pub >/dev/null 2>&1; then
  echo "mosquitto_pub is required to publish plane tracker payloads."
  exit 1
fi

printf '%s' "$payload" | mosquitto_pub \
  -h "$PLANE_TRACKER_BROKER" \
  -p "$PLANE_TRACKER_PORT" \
  -t "$PLANE_TRACKER_TOPIC" \
  -r \
  -s

printf 'GRIDRUNNER_PLANE_TRACKER_PUBLISH status=ok topic=%s broker=%s count=%s\n' \
  "$PLANE_TRACKER_TOPIC" \
  "$PLANE_TRACKER_BROKER:$PLANE_TRACKER_PORT" \
  "$(printf '%s' "$payload" | jq -r '.count')"
