from pathlib import Path
from types import SimpleNamespace
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
                "power_action_token": "token",
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
                "power_action_token": "token",
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
            },
        )

        self.assertIn(b"NODE ONLINE", response.body)
        self.assertIn(b"WIFI KNOWN-WIFI", response.body)
        self.assertIn(b"EVENT TIMER PRESENT", response.body)
        self.assertIn(b"ADS-B PRESENT", response.body)
        self.assertIn(b"WEB PRESENT", response.body)
        self.assertIn(b"field terminal active", response.body)
        self.assertIn(b"Wi-Fi Telemetry", response.body)
        self.assertIn(b"Last Action", response.body)
        self.assertIn(b"Self Test", response.body)
        self.assertIn(b"WEB AUTH", response.body)
        self.assertIn(b"WEB SERVICE", response.body)
        self.assertIn(b"DISK", response.body)
        self.assertIn(b"Observe", response.body)
        self.assertIn(b"Operate", response.body)
        self.assertIn(b"Scan Controls", response.body)
        self.assertIn(b"Low Impact", response.body)
        self.assertIn(b"Field Scan", response.body)
        self.assertIn(b"Bluetooth Scan", response.body)
        self.assertIn(b"Network Devices", response.body)
        self.assertIn(b"Network Device Scan", response.body)

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
                "power_action_token": "token",
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
