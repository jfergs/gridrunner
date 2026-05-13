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
            {"status": "present", "count": 1},
        )

        self.assertEqual(
            node_status,
            [
                {"label": "NODE ONLINE", "severity": "ok"},
                {"label": "WIFI HOTSPOT", "severity": "ok"},
                {"label": "EVENTS STALE", "severity": "warn"},
                {"label": "EVENT TIMER PRESENT", "severity": "ok"},
                {"label": "EDGE NODES PRESENT", "severity": "ok"},
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
            "GRIDRUNNER_DISK_HEALTH status=warn used_percent=90 available_kb=100 mount=/ path=/home/operator/gridrunner",
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

    def test_adsb_operator_guidance_shows_device_checks_when_missing(self):
        guidance = app.adsb_operator_guidance(
            {
                "status": "missing",
                "path": "/run/readsb/aircraft.json",
            },
            {
                "readsb": {"status": "active"},
                "lighttpd": {"status": "inactive"},
            },
        )

        self.assertIn("Aircraft file: /run/readsb/aircraft.json", guidance)
        self.assertIn("readsb.service: active", guidance)
        self.assertIn("lighttpd.service: inactive", guidance)
        self.assertIn("Run bash scripts/adsb-health.sh on the device.", guidance)

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
                "edge_nodes": {"status": "missing", "message": "no edge-node telemetry cached", "count": 0, "nodes": []},
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
                            "route": "KJFK -> KLAX",
                            "airline": "Grid Air",
                            "route_map_url": "https://flightaware.com/live/flight/GRID01",
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
                    {"label": "EDGE NODES PRESENT", "severity": "ok"},
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
                    "operator_message": "External USB storage is active for operator data.",
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
                "adsb_guidance": ["Aircraft data is aging; check readsb if the count stops changing."],
                "edge_nodes": {
                    "status": "present",
                    "message": "1 edge node; newest 12s ago",
                    "count": 1,
                    "state_dir": "/tmp/gridrunner/state/edge-nodes",
                    "nodes": [
                        {
                            "node_id": "node-03",
                            "profile": "ble-presence",
                            "age_seconds": 12,
                            "freshness": "present",
                            "battery_percent": "82",
                            "transport": "mqtt",
                            "known_count": "5",
                            "unknown_count": "13",
                            "ignored_count": "2",
                            "rssi_peak": "-48",
                            "wifi_ap_count": "8",
                            "wifi_strongest_rssi": "-42",
                            "wifi_strongest_ssid": "GRIDRUNNER",
                            "drone_candidate_count": "1",
                            "drone_wifi_count": "0",
                            "drone_ble_count": "1",
                            "drone_rssi_peak": "-58",
                            "pending_scan_count": "3",
                        }
                    ],
                    "rf_targets": [
                        {
                            "kind": "wifi",
                            "label": "GRIDRUNNER",
                            "detail": "ch 6 WPA2",
                            "rssi": "-42",
                            "x": "50.0",
                            "y": "32.0",
                        },
                        {
                            "kind": "bluetooth",
                            "label": "BLE 18",
                            "detail": "known 5 unk 13",
                            "rssi": "-48",
                            "x": "62.0",
                            "y": "44.0",
                        },
                        {
                            "kind": "drone",
                            "label": "DRONE 1",
                            "detail": "wifi 0 ble 1",
                            "rssi": "-58",
                            "x": "42.0",
                            "y": "58.0",
                        },
                        {
                            "kind": "deauth",
                            "label": "DEAUTH 2",
                            "detail": "window 15s",
                            "rssi": "-50",
                            "x": "38.0",
                            "y": "38.0",
                        },
                    ],
                    "ble_total": 18,
                    "wifi_ap_total": 8,
                    "drone_candidate_total": 1,
                    "pending_scan_total": 3,
                },
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
        self.assertIn(b"KJFK -&gt; KLAX", response.body)
        self.assertIn(b"Flight board", response.body)
        self.assertIn(b"Track", response.body)
        self.assertIn(b"Aircraft data is aging", response.body)
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
        self.assertIn(b"Edge Nodes", response.body)
        self.assertIn(b"node-03", response.body)
        self.assertIn(b"ble-presence", response.body)
        self.assertIn(b"Drone", response.body)
        self.assertIn(b"aps 8", response.body)
        self.assertIn(b"drone 1", response.body)
        self.assertIn(b"strong GRIDRUNNER", response.body)
        self.assertIn(b"pending 3", response.body)
        self.assertIn(b"RF target radar", response.body)
        self.assertIn(b"rf-target-list", response.body)
        self.assertIn(b"rf-target-wifi", response.body)
        self.assertIn(b"rf-target-bluetooth", response.body)
        self.assertIn(b"rf-target-drone", response.body)
        self.assertIn(b"rf-target-deauth", response.body)
        self.assertIn(b"/edge-nodes/api", response.body)
        self.assertIn(b"setInterval(tickEdgeAges, 1000)", response.body)
        self.assertIn(b"setInterval(refreshEdge, 2000)", response.body)
        self.assertIn(b"Storage routing and controls", response.body)
        self.assertIn(b"Use USB Storage", response.body)
        self.assertIn(b"External USB storage is active", response.body)
        self.assertIn(b"/media/ghost/USB/gridrunner/backups", response.body)
        self.assertIn(b"external storage UUID unavailable", response.body)
        self.assertIn(b"42% used", response.body)
        self.assertIn(b"volume-meter-ok", response.body)
        self.assertIn(b"free 12.0 GB", response.body)
        self.assertIn(b"aria-label=\"/media/ghost/USB disk usage\"", response.body)
        self.assertIn(b"Event log tail", response.body)
        self.assertIn(b"Flight board", response.body)
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

    def test_load_edge_nodes_reads_cached_state(self):
        original_edge_node_state_dir = app.EDGE_NODE_STATE_DIR
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                edge_dir = Path(temp_dir) / "edge-nodes"
                edge_dir.mkdir()
                state_file = edge_dir / "node-03.json"
                state_file.write_text(
                    json.dumps(
                        {
                            "schema": "gridrunner.edge_node.v1",
                            "node_id": "node-03",
                            "profile": "ble-presence",
                            "timestamp": "2026-05-12T17:30:00Z",
                            "received_at": "2026-05-12T17:30:01Z",
                            "battery": {"percent": 82, "voltage": 3.98, "charging": False},
                            "link": {"transport": "mqtt", "rssi": -61, "last_sync_seconds": 12, "pending_scan_count": 3},
                            "ble": {
                                "window_seconds": 60,
                                "known_count": 5,
                                "unknown_count": 13,
                                "ignored_count": 2,
                                "rssi_peak": -48,
                            },
                            "wifi": {
                                "window_seconds": 15,
                                "ap_count": 8,
                                "stored_count": 5,
                                "strongest_rssi": -42,
                                "strongest_ssid": "GRIDRUNNER",
                                "scan_count": 4,
                                "aps": [
                                    {
                                        "ssid": "GRIDRUNNER",
                                        "rssi": -42,
                                        "channel": 6,
                                        "security": "WPA2",
                                        "drone_candidate": False,
                                    },
                                    {
                                        "ssid": "DJI-RID",
                                        "rssi": -58,
                                        "channel": 11,
                                        "security": "OPEN",
                                        "drone_candidate": True,
                                    },
                                ],
                            },
                            "drone": {
                                "candidate_count": 1,
                                "wifi_count": 0,
                                "ble_count": 1,
                                "rssi_peak": -58,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                app.EDGE_NODE_STATE_DIR = edge_dir
                summary = app.load_edge_nodes(now=int(state_file.stat().st_mtime) + 30)

                self.assertEqual(summary["status"], "present")
                self.assertEqual(summary["count"], 1)
                self.assertEqual(summary["nodes"][0]["node_id"], "node-03")
                self.assertEqual(summary["nodes"][0]["battery_percent"], "82")
                self.assertEqual(summary["nodes"][0]["unknown_count"], "13")
                self.assertEqual(summary["ble_total"], 18)
                self.assertEqual(summary["wifi_ap_total"], 8)
                self.assertEqual(summary["drone_candidate_total"], 1)
                self.assertEqual(summary["pending_scan_total"], 3)
                self.assertEqual(summary["nodes"][0]["wifi_strongest_ssid"], "GRIDRUNNER")
                self.assertEqual(summary["nodes"][0]["drone_rssi_peak"], "-58")
                self.assertEqual(summary["rf_targets"][0]["kind"], "drone")
                self.assertIn("DRONE 1", [target["label"] for target in summary["rf_targets"]])
                self.assertIn("GRIDRUNNER", [target["label"] for target in summary["rf_targets"]])
        finally:
            app.EDGE_NODE_STATE_DIR = original_edge_node_state_dir

    def test_edge_nodes_api_returns_live_summary(self):
        original_edge_node_state_dir = app.EDGE_NODE_STATE_DIR
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                edge_dir = Path(temp_dir) / "edge-nodes"
                edge_dir.mkdir()
                (edge_dir / "node-03.json").write_text(
                    json.dumps(
                        {
                            "schema": "gridrunner.edge_node.v1",
                            "node_id": "node-03",
                            "profile": "rf-handheld",
                            "timestamp": "2026-05-12T17:30:00Z",
                            "received_at": "2026-05-12T17:30:01Z",
                            "battery": {"percent": 82, "charging": False},
                            "link": {"transport": "mqtt", "rssi": -61, "last_sync_seconds": 12, "pending_scan_count": 2},
                            "ble": {"window_seconds": 30, "known_count": 1, "unknown_count": 2, "ignored_count": 0, "rssi_peak": -44},
                            "wifi": {
                                "window_seconds": 15,
                                "ap_count": 1,
                                "stored_count": 1,
                                "strongest_rssi": -42,
                                "strongest_ssid": "GRIDRUNNER",
                                "aps": [{"ssid": "GRIDRUNNER", "rssi": -42, "channel": 6, "security": "WPA2"}],
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                app.EDGE_NODE_STATE_DIR = edge_dir

                response = app.edge_nodes_api(_user="operator")
                payload = json.loads(response.body)

                self.assertEqual(payload["status"], "present")
                self.assertEqual(payload["count"], 1)
                self.assertEqual(payload["ble_total"], 3)
                self.assertEqual(payload["wifi_ap_total"], 1)
                self.assertEqual(payload["pending_scan_total"], 2)
                self.assertEqual(payload["rf_targets"][0]["label"], "GRIDRUNNER")
        finally:
            app.EDGE_NODE_STATE_DIR = original_edge_node_state_dir

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
                self.assertIn("External USB storage is active", app.storage_summary()["operator_message"])
        finally:
            app.STORAGE_STATE_FILE = original_storage_state_file

    def test_storage_summary_warns_when_external_root_missing(self):
        original_storage_state_file = app.STORAGE_STATE_FILE
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir) / "missing" / "gridrunner"
                app.STORAGE_STATE_FILE = Path(temp_dir) / "storage.env"
                app.STORAGE_STATE_FILE.write_text(
                    "\n".join(
                        [
                            "GRIDRUNNER_STORAGE_MODE=external",
                            f"GRIDRUNNER_STORAGE_ROOT={root}",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )

                summary = app.storage_summary("")

                self.assertEqual(summary["status"], "degraded")
                self.assertIn("external storage missing or not writable", summary["warnings"])
                self.assertIn("using internal backup and event-log paths", summary["operator_message"])
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

    def test_event_dashboard_status_shows_idle_when_scans_are_off(self):
        original_storage_state_file = app.STORAGE_STATE_FILE
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app.STORAGE_STATE_FILE = Path(temp_dir) / "storage.env"
                status = app.event_dashboard_status(
                    {"status": "stale", "message": "events stale for 900s", "age_seconds": 900},
                    {
                        "bluetooth_mode": "off",
                        "network_device_mode": "off",
                        "interval_seconds": 900,
                        "last_run": 0,
                    },
                )

                self.assertEqual(status["status"], "idle")
                self.assertIn("scans are disabled", status["message"])
                self.assertIn("one-shot scan", status["detail"])
                self.assertIn("log_path", status)
        finally:
            app.STORAGE_STATE_FILE = original_storage_state_file

    def test_event_dashboard_status_keeps_stale_when_scans_are_armed(self):
        status = app.event_dashboard_status(
            {"status": "stale", "message": "events stale for 900s", "age_seconds": 900},
            {
                "bluetooth_mode": "continuous",
                "network_device_mode": "off",
                "interval_seconds": 300,
                "last_run": 100,
            },
        )

        self.assertEqual(status["status"], "stale")
        self.assertIn("writing to", status["detail"])

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
