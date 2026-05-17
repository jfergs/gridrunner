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

The project uses the community `pioarduino` Espressif platform because
PlatformIO's stock ESP32-C6 board support is ESP-IDF-only at the time this was
added.

If `gridrunner.local` does not resolve from the ESP32, set
`GRIDRUNNER_MQTT_HOST` to the Pi's hotspot or LAN IP address.

## Pi Check

The Pi should already publish retained MQTT updates:

```bash
mosquitto_sub -h localhost -t gridrunner/adsb/plane-tracker -C 1 -v
```

The display renders `null` altitude, speed, or heading values as `---`.

## Display UI

The normal display is intentionally compact:

- Top: spinning radar sweep with aircraft blips.
- Middle/lower: aircraft list with `ID`, `ALT`, `SPD`, and `HDG`.
- Bottom: compact status strip.

The bottom status strip uses short codes to avoid crowding the radar:

| Code | Meaning |
| --- | --- |
| `A<count>` | Total aircraft reported by the Pi payload |
| `<age>s` | Payload age in seconds |
| `W+` / `W-` | Wi-Fi connected / disconnected |
| `M+` / `M-` | MQTT connected / disconnected |
| `B<level>` | Current backlight level |
| `L` / `D` | List view / detail view |
| `P<page>/<pages>` | Current aircraft list page, only shown when needed |

Color meanings:

| Color | Meaning |
| --- | --- |
| Green | Normal radar grid, status, and live text |
| Dim green | Secondary grid and placeholder text |
| Yellow | Active aircraft row text |
| Red | Selected aircraft blip or stale/bad status |
| Amber | Aircraft not seen for more than 20 seconds |

The list keeps up to 12 aircraft from the MQTT payload and shows 5 at a time.
Single-tapping through the aircraft advances onto the next page automatically.

## Side Button

The side button is configured on GPIO9 with the internal pull-up enabled:

| Gesture | Action |
| --- | --- |
| Single tap | Select next aircraft in list view; return to list from detail view |
| Double tap | Return to list view |
| Long press | Open detail view for the selected aircraft |
| Triple tap | Cycle backlight brightness through `0`, `25`, `50`, `75`, `100` |

## Touch/JD9853 Variant

If your board is `ESP32-C6-Touch-LCD-1.47`, it uses a different display driver
from the non-touch ST7789 board. Keep this firmware as the MQTT/rendering
reference, but swap the display initialization for the Waveshare touch-board
driver or LVGL demo base.
