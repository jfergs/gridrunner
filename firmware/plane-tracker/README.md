# GRIDRUNNER ESP32-C6 Plane Tracker

Tiny radar-style MQTT display for the Waveshare `ESP32-C6-LCD-1.47`
non-touch board. It subscribes to the Pi publisher at
`gridrunner/adsb/plane-tracker` and renders the newest ADS-B aircraft summary.

The firmware target uses the Waveshare non-touch 1.47 inch ST7789 wiring:

| LCD | ESP32-C6 |
| --- | --- |
| MOSI | GPIO6 |
| SCLK | GPIO7 |
| CS | GPIO14 |
| DC | GPIO15 |
| RST | GPIO21 |
| BL | GPIO22 |

## Build Setup

Install PlatformIO, then create local credentials:

```bash
cd firmware/plane-tracker
cp include/config.example.h include/secrets.h
```

Edit `include/secrets.h`:

```c
#define GRIDRUNNER_WIFI_SSID "your-gridrunner-wifi"
#define GRIDRUNNER_WIFI_PASSWORD "your-password"
#define GRIDRUNNER_MQTT_HOST "gridrunner.local"
```

Build and flash:

```bash
pio run
pio run --target upload
pio device monitor
```

If `gridrunner.local` does not resolve from the ESP32, set
`GRIDRUNNER_MQTT_HOST` to the Pi's hotspot or LAN IP address.

## Pi Check

The Pi should already publish retained MQTT updates:

```bash
mosquitto_sub -h localhost -t gridrunner/adsb/plane-tracker -C 1 -v
```

The display renders `null` altitude, speed, or heading values as `---`.

## Touch/JD9853 Variant

If your board is `ESP32-C6-Touch-LCD-1.47`, it uses a different display driver
from the non-touch ST7789 board. Keep this firmware as the MQTT/rendering
reference, but swap the display initialization for the Waveshare touch-board
driver or LVGL demo base.
