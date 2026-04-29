from pathlib import Path
from types import SimpleNamespace
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
            },
        )

        self.assertIn(b"NODE ONLINE", response.body)
        self.assertIn(b"WIFI KNOWN-WIFI", response.body)
        self.assertIn(b"EVENT TIMER PRESENT", response.body)
        self.assertIn(b"ADS-B PRESENT", response.body)
        self.assertIn(b"WEB PRESENT", response.body)
        self.assertIn(b"field terminal active", response.body)
        self.assertIn(b"Wi-Fi Telemetry", response.body)
        self.assertIn(b"Observe", response.body)
        self.assertIn(b"Operate", response.body)


if __name__ == "__main__":
    unittest.main()
