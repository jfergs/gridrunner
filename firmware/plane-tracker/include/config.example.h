#pragma once

// Copy this file to include/secrets.h and edit for your GRIDRUNNER network.

#define GRIDRUNNER_WIFI_SSID "GRIDRUNNER"
#define GRIDRUNNER_WIFI_PASSWORD "change-me"

// Use "gridrunner.local" when mDNS works from the ESP32. If it does not,
// use the Pi's hotspot or LAN IP address.
#define GRIDRUNNER_MQTT_HOST "gridrunner.local"
#define GRIDRUNNER_MQTT_PORT 1883
#define GRIDRUNNER_MQTT_TOPIC "gridrunner/adsb/plane-tracker"

// Optional receiver/home position. Set GRIDRUNNER_HAS_HOME_POSITION to 1
// after entering the approximate ADS-B antenna location.
#define GRIDRUNNER_HAS_HOME_POSITION 0
#define GRIDRUNNER_HOME_LAT 0.0
#define GRIDRUNNER_HOME_LON 0.0
