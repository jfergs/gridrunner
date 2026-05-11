from pathlib import Path
from types import SimpleNamespace
import asyncio
import json
import tempfile
import unittest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))

import app


class TemplateRenderTests(unittest.TestCase):
    def test_build_node_status_aggregates_health_inputs(self):
        node_status = app.build_node_status(
            {"status": "present", "mode": "hotspot"},
            {"status": "stale", "message": "events stale for 300s"},
            {
                "adsb-tools": {"status": "degraded", "detail": "no-rtl-support"},
                "web-service": {"status": "present", "detail": "active"},
                "events-service": {"status": "present", "detail": "timer-active"},
            },
        )

        self.assertEqual(
            node_status,
            [
                {"label": "NODE ONLINE", "severity": "ok"},
                {"label": "WIFI HOTSPOT", "severity": "ok"},
                {"label": "EVENTS STALE", "severity": "warn"},
                {"label": "EVENT TIMER PRESENT", "severity": "ok"},
                {"label": "ADS-B DEGRADED", "severity": "warn"},
                {"label": "WEB PRESENT", "severity": "ok"},
            ],
        )

    def test_build_self_tests_aggregates_health_inputs(self):
        services = {
            "gridrunner-web": {"status": "active", "unit": "gridrunner-web.service", "enabled": "enabled"},
            "gridrunner-wifi-timer": {"status": "active", "unit": "gridrunner-wifi.timer", "enabled": "enabled"},
            "gridrunner-wifi": {"status": "inactive", "unit": "gridrunner-wifi.service", "enabled": "static"},
            "gridrunner-events-timer": {
                "status": "active",
                "unit": "gridrunner-events.timer",
                "enabled": "enabled",
            },
            "readsb": {"status": "active", "unit": "readsb.service", "enabled": "enabled"},
            "lighttpd": {"status": "inactive", "unit": "lighttpd.service", "enabled": "disabled"},
        }
        self_tests = app.build_self_tests(
            {"status": "present", "mode": "known-wifi", "timer": "active"},
            {"status": "fresh", "message": "events updated 30s ago"},
            {
                "web-service": {"status": "present", "detail": "active"},
                "events-service": {"status": "present", "detail": "timer-active"},
                "adsb-tools": {"status": "present", "detail": "rtl-supported"},
            },
            "GRIDRUNNER_DISK_HEALTH status=warn used_percent=90 available_kb=100 mount=/ path=/home/ghost/gridrunner",
            services,
            True,
        )

        self.assertEqual(self_tests[0]["name"], "WEB AUTH")
        self.assertEqual(self_tests[0]["label"], "OK")
        self.assertEqual(self_tests[1]["name"], "WEB SERVICE")
        self.assertEqual(self_tests[1]["label"], "OK")
        self.assertIn(
            {
                "name": "LIGHTTPD",
                "status": "inactive",
                "detail": "lighttpd.service disabled",
                "severity": "warn",
                "label": "WARN",
            },
            self_tests,
        )
        self.assertIn(
            {"name": "DISK", "status": "warn", "detail": "90", "severity": "warn", "label": "WARN"},
            self_tests,
        )

    def test_web_auth_status_warns_when_password_missing(self):
        self.assertEqual(
            app.web_auth_status(False),
            {"status": "missing", "detail": "local or VPN only"},
        )
        self.assertEqual(
            app.web_auth_status(True),
            {"status": "present", "detail": "password configured"},
        )

    def test_parse_service_health(self):
        services = app.parse_service_health(
            "GRIDRUNNER_SERVICE name=readsb unit=readsb.service status=active active=active enabled=enabled"
        )

        self.assertEqual(services["readsb"]["status"], "active")
        self.assertEqual(services["readsb"]["unit"], "readsb.service")

    def test_run_action_rejects_invalid_form_token(self):
        request = SimpleNamespace(scope={"type": "http", "method": "POST", "path": "/run", "headers": []})

        response = app.run_action(request, action="health", confirm_token="bad-token")

        self.assertIn(b"invalid form token", response.body)

    def test_scan_action_rejects_invalid_form_token(self):
        request = SimpleNamespace(scope={"type": "http", "method": "POST", "path": "/scans", "headers": []})

        response = app.scan_action(request, action="scan-now", confirm_token="bad-token")

        self.assertIn(b"invalid form token", response.body)

    def test_install_action_rejects_invalid_form_token(self):
        request = SimpleNamespace(scope={"type": "http", "method": "POST", "path": "/install", "headers": []})

        response = asyncio.run(app.run_install(request, mode="dry-run", confirm_token="bad-token"))

        self.assertIn(b"invalid form token", response.body)

    def test_install_skip_rejects_invalid_form_token(self):
        request = SimpleNamespace(scope={"type": "http", "method": "POST", "path": "/install/skip", "headers": []})

        response = asyncio.run(app.skip_install(request, confirm_token="bad-token"))

        self.assertIn(b"invalid form token", response.body)

    def test_storage_action_rejects_invalid_form_token(self):
        request = SimpleNamespace(scope={"type": "http", "method": "POST", "path": "/storage", "headers": []})

        response = app.storage_action(request, action="status", confirm_token="bad-token")

        self.assertIn(b"invalid form token", response.body)

    def test_index_template_renders_without_wifi_status_context(self):
        request = SimpleNamespace(scope={"type": "http", "method": "GET", "path": "/", "headers": []})

        response = app.templates.TemplateResponse(
            request,
            "index.html",
            {
                "status": "ok",
                "events": "event",
                "event_status": {"status": "fresh", "message": "events updated 0s ago"},
                "auth_enabled": True,
                "operator_user": "operator",
                "adsb_map_url": "http://gridrunner.local/tar1090/",
                "form_action_token": "token",
                "power_action_token": "token",
                "adsb_summary": {
                    "status": "missing",
                    "count": 0,
                    "message": "aircraft data missing",
                    "updated_message": "aircraft file missing",
                    "aircraft": [],
                },
                "install_items": [],
                "install_state": {},
                "install_statuses": {},
                "component_health": {},
                "node_status": [{"label": "NODE ONLINE", "severity": "ok"}],
                "self_tests": [],
            },
        )

        self.assertIn(b"Wi-Fi status unavailable", response.body)

    def test_index_template_includes_retrofuture_node_strip(self):
        request = SimpleNamespace(scope={"type": "http", "method": "GET", "path": "/", "headers": []})

        response = app.templates.TemplateResponse(
            request,
            "index.html",
            {
                "status": "ok",
                "events": "event",
                "event_status": {"status": "fresh", "message": "events updated 0s ago"},
                "wifi_status": {"status": "present", "mode": "known-wifi"},
                "wifi_output": "GRIDRUNNER_WIFI status=present mode=known-wifi",
                "auth_enabled": True,
                "operator_user": "operator",
                "adsb_map_url": "http://gridrunner.local/tar1090/",
                "form_action_token": "token",
                "power_action_token": "token",
                "adsb_summary": {
                    "status": "present",
                    "count": 1,
                    "message": "1 aircraft tracked",
                    "updated_message": "updated 2s ago",
                    "aircraft": [
                        {
                            "ident": "GRID01",
                            "altitude": "1200",
                            "speed": "145",
                            "track": "87",
                            "seen": "2s",
                        }
                    ],
                },
                "install_items": [],
                "install_state": {},
                "install_statuses": {},
                "component_health": {},
                "node_status": [
                    {"label": "NODE ONLINE", "severity": "ok"},
                    {"label": "WIFI KNOWN-WIFI", "severity": "ok"},
                    {"label": "EVENTS FRESH", "severity": "ok"},
                    {"label": "EVENT TIMER PRESENT", "severity": "ok"},
                    {"label": "ADS-B PRESENT", "severity": "ok"},
                    {"label": "WEB PRESENT", "severity": "ok"},
                ],
                "self_tests": [
                    {
                        "name": "WEB AUTH",
                        "label": "OK",
                        "status": "present",
                        "severity": "ok",
                        "detail": "password configured",
                    },
                    {
                        "name": "WEB SERVICE",
                        "label": "OK",
                        "status": "present",
                        "severity": "ok",
                        "detail": "active",
                    },
                    {
                        "name": "DISK",
                        "label": "WARN",
                        "status": "warn",
                        "severity": "warn",
                        "detail": "90",
                    },
                ],
                "storage": {
                    "status": "external",
                    "mode": "external",
                    "root": "/media/ghost/USB/gridrunner",
                    "mount": "/media/ghost/USB",
                    "uuid": "-",
                    "warnings": ["external storage UUID unavailable"],
                    "backup_dir": "/media/ghost/USB/gridrunner/backups",
                    "events_log": "/media/ghost/USB/gridrunner/logs/ghost-events.log",
                    "sdr_dir": "/media/ghost/USB/gridrunner/sdr",
                    "radio_dir": "/media/ghost/USB/gridrunner/radio",
                    "output": "GRIDRUNNER_STORAGE status=external",
                },
                "storage_volumes": [
                    {
                        "mount": "/media/ghost/USB",
                        "avail_bytes": "12884901888",
                        "writable": "yes",
                    }
                ],
                "storage_meters": [
                    {
                        "mount": "/",
                        "source": "/dev/root",
                        "fstype": "ext4",
                        "severity": "ok",
                        "used_percent": 42,
                        "free_percent": 58,
                        "used_label": "4.2 GB",
                        "free_label": "5.8 GB",
                        "size_label": "10.0 GB",
                        "writable": "yes",
                        "selectable": "no",
                    },
                    {
                        "mount": "/media/ghost/USB",
                        "source": "/dev/sda1",
                        "fstype": "exfat",
                        "severity": "ok",
                        "used_percent": 25,
                        "free_percent": 75,
                        "used_label": "4.0 GB",
                        "free_label": "12.0 GB",
                        "size_label": "16.0 GB",
                        "writable": "yes",
                        "selectable": "yes",
                    },
                ],
            },
        )

        self.assertIn(b"NODE ONLINE", response.body)
        self.assertIn(b"WIFI KNOWN-WIFI", response.body)
        self.assertIn(b"EVENT TIMER PRESENT", response.body)
        self.assertIn(b"ADS-B PRESENT", response.body)
        self.assertIn(b"WEB PRESENT", response.body)
        self.assertIn(b"field terminal active", response.body)
        self.assertIn(b"Quick Actions", response.body)
        self.assertIn(b"Transport Deck", response.body)
        self.assertIn(b"quick-action-map", response.body)
        self.assertIn(b"ADS-B", response.body)
        self.assertIn(b"1 aircraft tracked", response.body)
        self.assertIn(b"updated 2s ago", response.body)
        self.assertIn(b"GRID01", response.body)
        self.assertIn(b"Wi-Fi Telemetry", response.body)
        self.assertIn(b"Wi-Fi controls and raw status", response.body)
        self.assertIn(b"Enable Hotspot", response.body)
        self.assertIn(b"Connect Known Wi-Fi", response.body)
        self.assertIn(b"Refresh Wi-Fi Status", response.body)
        self.assertIn(b"Last Action", response.body)
        self.assertIn(b"Self Test", response.body)
        self.assertIn(b"Self-test lamps", response.body)
        self.assertIn(b"WEB AUTH", response.body)
        self.assertIn(b"WEB SERVICE", response.body)
        self.assertIn(b"DISK", response.body)
        self.assertIn(b"Observe", response.body)
        self.assertIn(b"Operate", response.body)
        self.assertIn(b"Command bank", response.body)
        self.assertIn(b"Scan Controls", response.body)
        self.assertIn(b"Scanner Transport", response.body)
        self.assertIn(b"Low Impact", response.body)
        self.assertIn(b"scan-profile-switch", response.body)
        self.assertIn(b"Low Impact", response.body)
        self.assertIn(b"Field", response.body)
        self.assertIn(b"Modes", response.body)
        self.assertIn(b"Enable Scanning", response.body)
        self.assertIn(b"Scan controls", response.body)
        self.assertIn(b"Bluetooth Scan Now", response.body)
        self.assertIn(b"Network Devices", response.body)
        self.assertIn(b"Wi-Fi Scan Now", response.body)
        self.assertIn(b">Map</a>", response.body)
        self.assertIn(b"Storage", response.body)
        self.assertIn(b"Storage routing and controls", response.body)
        self.assertIn(b"Use USB Storage", response.body)
        self.assertIn(b"/media/ghost/USB/gridrunner/backups", response.body)
        self.assertIn(b"external storage UUID unavailable", response.body)
        self.assertIn(b"42% used", response.body)
        self.assertIn(b"volume-meter-ok", response.body)
        self.assertIn(b"free 12.0 GB", response.body)
        self.assertIn(b"aria-label=\"/media/ghost/USB disk usage\"", response.body)
        self.assertIn(b"Event log tail", response.body)
        self.assertIn(b"Aircraft rows", response.body)
        self.assertIn(b"Install manifest", response.body)
        self.assertIn(b'name="confirm_token" value="token"', response.body)

    def test_storage_volume_meters_parse_disk_usage(self):
        meters = app.storage_volume_meters(
            "\n".join(
                [
                    "GRIDRUNNER_STORAGE_VOLUME mount=/ source=/dev/root fstype=ext4 size_bytes=10737418240 used_bytes=4294967296 avail_bytes=6442450944 used_percent=40 writable=yes selectable=no uuid=root",
                    "GRIDRUNNER_STORAGE_VOLUME mount=/media/ghost/USB source=/dev/sda1 fstype=exfat size_bytes=17179869184 used_bytes=4294967296 avail_bytes=12884901888 used_percent=25 writable=yes selectable=yes uuid=usb",
                    "",
                ]
            )
        )

        self.assertEqual(meters[0]["mount"], "/")
        self.assertEqual(meters[0]["used_percent"], 40)
        self.assertEqual(meters[0]["free_label"], "6.0 GB")
        self.assertEqual(meters[1]["mount"], "/media/ghost/USB")
        self.assertEqual(meters[1]["used_label"], "4.0 GB")

    def test_storage_config_uses_external_events_log_when_ready(self):
        original_storage_state_file = app.STORAGE_STATE_FILE
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir) / "usb" / "gridrunner"
                logs = root / "logs"
                logs.mkdir(parents=True)
                app.STORAGE_STATE_FILE = Path(temp_dir) / "storage.env"
                app.STORAGE_STATE_FILE.write_text(
                    "\n".join(
                        [
                            "GRIDRUNNER_STORAGE_MODE=external",
                            f"GRIDRUNNER_STORAGE_ROOT={root}",
                            f"GRIDRUNNER_EVENTS_LOG={logs / 'operator-events.log'}",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )

                self.assertEqual(app.active_events_log(), logs / "operator-events.log")
                self.assertEqual(app.storage_summary()["status"], "external")
                self.assertEqual(app.storage_summary()["warnings"], ["external storage UUID unavailable"])
        finally:
            app.STORAGE_STATE_FILE = original_storage_state_file

    def test_scan_control_state_round_trips_with_safe_defaults(self):
        original_scan_state_file = app.SCAN_STATE_FILE
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app.SCAN_STATE_FILE = Path(temp_dir) / "scan-controls.env"

                self.assertEqual(
                    app.load_scan_controls(),
                    {
                        "bluetooth_mode": "off",
                        "network_device_mode": "off",
                        "interval_seconds": 300,
                        "last_run": 0,
                    },
                )

                app.save_scan_controls(
                    {
                        "bluetooth_mode": "continuous",
                        "network_device_mode": "invalid",
                        "interval_seconds": 9999,
                        "last_run": 42,
                    }
                )

                self.assertEqual(
                    app.load_scan_controls(),
                    {
                        "bluetooth_mode": "continuous",
                        "network_device_mode": "off",
                        "interval_seconds": 1800,
                        "last_run": 42,
                    },
                )

                state_text = app.SCAN_STATE_FILE.read_text(encoding="utf-8")
                self.assertIn("GRIDRUNNER_SCAN_NETWORK_DEVICE_MODE=off", state_text)
                self.assertIn("GRIDRUNNER_SCAN_NETWORK_MODE=off", state_text)
        finally:
            app.SCAN_STATE_FILE = original_scan_state_file

    def test_scan_control_state_loads_legacy_network_device_mode(self):
        original_scan_state_file = app.SCAN_STATE_FILE
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app.SCAN_STATE_FILE = Path(temp_dir) / "scan-controls.env"
                app.SCAN_STATE_FILE.write_text(
                    "\n".join(
                        [
                            "GRIDRUNNER_SCAN_BLUETOOTH_MODE=off",
                            "GRIDRUNNER_SCAN_NETWORK_MODE=continuous",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )

                self.assertEqual(app.load_scan_controls()["network_device_mode"], "continuous")
        finally:
            app.SCAN_STATE_FILE = original_scan_state_file

    def test_scan_control_description_shows_armed_state_and_age(self):
        described = app.describe_scan_controls(
            {
                "bluetooth_mode": "continuous",
                "network_device_mode": "off",
                "interval_seconds": 300,
                "last_run": 100,
            },
            now=145,
        )

        self.assertEqual(described["state_label"], "armed")
        self.assertEqual(described["active_scanners"], "Bluetooth")
        self.assertEqual(described["last_run_message"], "last scan 45s ago")
        self.assertEqual(described["profile"]["label"], "Custom")

        disabled = app.describe_scan_controls(
            {
                "bluetooth_mode": "off",
                "network_device_mode": "off",
                "interval_seconds": 900,
                "last_run": 0,
            },
            now=145,
        )

        self.assertEqual(disabled["state_label"], "off")
        self.assertEqual(disabled["active_scanners"], "none")
        self.assertEqual(disabled["last_run_message"], "last scan never")
        self.assertEqual(disabled["profile"]["label"], "Low Impact")

    def test_scan_profile_presets_apply_expected_controls(self):
        current = {
            "bluetooth_mode": "continuous",
            "network_device_mode": "off",
            "interval_seconds": 120,
            "last_run": 42,
        }

        low_impact = app.scan_controls_for_profile("low-impact", current)
        self.assertEqual(low_impact["bluetooth_mode"], "off")
        self.assertEqual(low_impact["network_device_mode"], "off")
        self.assertEqual(low_impact["interval_seconds"], 900)
        self.assertEqual(low_impact["last_run"], 42)

        field = app.scan_controls_for_profile("field", current)
        self.assertEqual(field["bluetooth_mode"], "continuous")
        self.assertEqual(field["network_device_mode"], "continuous")
        self.assertEqual(field["interval_seconds"], 300)

    def test_scan_profile_redirects_back_with_visible_notice(self):
        original_scan_state_file = app.SCAN_STATE_FILE
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app.SCAN_STATE_FILE = Path(temp_dir) / "scan-controls.env"
                request = SimpleNamespace(scope={"type": "http", "method": "POST", "path": "/scans", "headers": []})

                response = app.scan_action(
                    request,
                    action="profile:field",
                    confirm_token=app.FORM_ACTION_TOKEN,
                )

                self.assertEqual(response.status_code, 303)
                self.assertIn("#scans", response.headers["location"])
                self.assertIn("scan_notice=", response.headers["location"])
                state_text = app.SCAN_STATE_FILE.read_text(encoding="utf-8")
                self.assertIn("GRIDRUNNER_SCAN_BLUETOOTH_MODE=continuous", state_text)
                self.assertIn("GRIDRUNNER_SCAN_NETWORK_DEVICE_MODE=continuous", state_text)
        finally:
            app.SCAN_STATE_FILE = original_scan_state_file

    def test_scan_api_toggle_updates_state_without_result_page(self):
        original_scan_state_file = app.SCAN_STATE_FILE
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app.SCAN_STATE_FILE = Path(temp_dir) / "scan-controls.env"

                response = app.scan_api_action(
                    action="toggle",
                    confirm_token=app.FORM_ACTION_TOKEN,
                )
                payload = json.loads(response.body)

                self.assertEqual(payload["controls"]["state_label"], "armed")
                self.assertEqual(payload["controls"]["profile"]["label"], "Field")
                self.assertIn("Scanning enabled", payload["notice"])

                response = app.scan_api_action(
                    action="toggle",
                    confirm_token=app.FORM_ACTION_TOKEN,
                )
                payload = json.loads(response.body)

                self.assertEqual(payload["controls"]["state_label"], "off")
                self.assertEqual(payload["controls"]["active_scanners"], "none")
                self.assertEqual(payload["notice"], "Scanning disabled.")
        finally:
            app.SCAN_STATE_FILE = original_scan_state_file

    def test_index_template_warns_for_missing_web_password(self):
        request = SimpleNamespace(scope={"type": "http", "method": "GET", "path": "/", "headers": []})

        response = app.templates.TemplateResponse(
            request,
            "index.html",
            {
                "status": "ok",
                "events": "event",
                "event_status": {"status": "fresh", "message": "events updated 0s ago"},
                "wifi_status": {"status": "present", "mode": "known-wifi"},
                "wifi_output": "GRIDRUNNER_WIFI status=present mode=known-wifi",
                "auth_enabled": False,
                "operator_user": "operator",
                "adsb_map_url": "http://gridrunner.local/tar1090/",
                "form_action_token": "token",
                "power_action_token": "token",
                "adsb_summary": {"status": "missing", "count": 0, "message": "aircraft data missing", "aircraft": []},
                "install_items": [],
                "install_state": {},
                "install_statuses": {},
                "component_health": {},
                "node_status": [{"label": "NODE ONLINE", "severity": "ok"}],
                "self_tests": [
                    {
                        "name": "WEB AUTH",
                        "label": "FAIL",
                        "status": "missing",
                        "severity": "danger",
                        "detail": "local or VPN only",
                    },
                ],
            },
        )

        self.assertIn(b"trusted local network or VPN only", response.body)
        self.assertIn(b"WEB AUTH", response.body)


if __name__ == "__main__":
    unittest.main()
