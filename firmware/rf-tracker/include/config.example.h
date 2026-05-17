#pragma once

// Copy this file to include/secrets.h and edit for your GRIDRUNNER network.

#define GRIDRUNNER_WIFI_SSID "GRIDRUNNER"
#define GRIDRUNNER_WIFI_PASSWORD "change-me"

// Use "gridrunner.local" when mDNS works from the ESP32. If it does not,
// use the Pi's hotspot or LAN IP address.
#define GRIDRUNNER_MQTT_HOST "gridrunner.local"
#define GRIDRUNNER_MQTT_PORT 1883

// Unique node ID used in MQTT topic and cached Pi state filename.
#define GRIDRUNNER_NODE_ID "c6-rf-tracker-01"
#define GRIDRUNNER_TRACKER_PROFILE "rf-handheld"

// Passive scan cadence. Keep this conservative so the tracker stays responsive.
#define GRIDRUNNER_WIFI_SCAN_INTERVAL_MS 15000
#define GRIDRUNNER_BLE_SCAN_INTERVAL_MS 30000
#define GRIDRUNNER_BLE_SCAN_SECONDS 2
#define GRIDRUNNER_BLE_IGNORE_RSSI_BELOW -95
#define GRIDRUNNER_TELEMETRY_INTERVAL_MS 10000
