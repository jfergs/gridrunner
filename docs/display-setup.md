# GRIDRUNNER Display Setup

GRIDRUNNER can record and configure a small local display from the Initial
Install panel.

## Supported Profiles

### Elecrow RR050 5-inch HDMI Touch

Use `Display: Elecrow RR050` for the Elecrow RR050 5-inch 800x480
HDMI/GPIO-touch display. GRIDRUNNER applies a managed HDMI 800x480 block to the
Raspberry Pi boot config and records the selected profile in
`state/display.env`.

Reference: https://www.elecrow.com/hdmi-5-inch-800x480-tft-display-for-raspberry-pi-b-p-1384.html

### Waveshare 5-inch HDMI LCD

Use `Display: Waveshare 5-inch HDMI` for common Waveshare-compatible 5-inch
800x480 HDMI/GPIO-touch displays. This uses the same managed HDMI 800x480
configuration as the Elecrow RR050 profile.

Reference: https://github.com/waveshareteam/LCD-show

### Official Raspberry Pi Touch Display

Use `Display: Raspberry Pi Touch` for the official DSI Touch Display. Raspberry
Pi OS normally handles this display without a vendor driver script, so
GRIDRUNNER records the profile and leaves display detection to the OS.

Reference: https://www.raspberrypi.com/documentation/accessories/display.html

## Vendor Driver Opt-In

Elecrow and Waveshare documentation often points to the `LCD-show` driver helper
for GPIO touch support. GRIDRUNNER does not run that external script by default
from the web installer. To opt in during an apply install:

```bash
export GRIDRUNNER_DISPLAY_VENDOR_DRIVER=1
```

Then select the Elecrow or Waveshare display item in the Initial Install panel.
The dashboard `Operator Display` panel shows the selected display profile and
lets you choose the startup mode after the install item is available.

## Manual Preview

```bash
GRIDRUNNER_DISPLAY_MODE=dry-run bash scripts/configure-display.sh elecrow-rr050
GRIDRUNNER_DISPLAY_MODE=dry-run bash scripts/configure-display.sh waveshare-5hdmi
GRIDRUNNER_DISPLAY_MODE=dry-run bash scripts/configure-display.sh raspberrypi-touch
```

Reboot after applying a display profile.

## Startup Operator Display Mode

The `Operator Display Mode` install item installs
`gridrunner-operator-display.service`, which launches one of the local screen
modes after the graphical target is available. It installs `tmux`, `unclutter`,
and `chromium-browser` for the local display workflow.

Default mode is the GRIDRUNNER web UI:

```bash
export GRIDRUNNER_OPERATOR_DISPLAY_MODE=web
```

Other modes:

```bash
export GRIDRUNNER_OPERATOR_DISPLAY_MODE=adsb
export GRIDRUNNER_OPERATOR_DISPLAY_MODE=tmux
export GRIDRUNNER_OPERATOR_DISPLAY_MODE=off
```

Manual configuration:

```bash
bash scripts/operator-display.sh configure web
bash scripts/operator-display.sh configure adsb
bash scripts/operator-display.sh configure tmux
bash scripts/operator-display.sh status
```

`web` opens `http://<device-hostname>.local:8088` in kiosk mode. The web UI also
has a `Fullscreen` button for browser sessions that are not already kiosked.
`adsb` opens `http://<device-hostname>.local/tar1090/`. `tmux` opens a local
`gridrunner` tmux session with tiled health, ADS-B, and events panes.
