from pathlib import Path
from types import SimpleNamespace
import json
import os
import subprocess
import tempfile
import unittest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))

import app
import config


class AdsbMapTests(unittest.TestCase):
    def setUp(self):
        self.original_adsb_map_url = app.ADSB_MAP_URL
        self.original_device_hostname = app.DEVICE_HOSTNAME
        self.original_route_lookup_enabled = app.ADSB_ROUTE_LOOKUP_ENABLED

    def tearDown(self):
        app.ADSB_MAP_URL = self.original_adsb_map_url
        app.DEVICE_HOSTNAME = self.original_device_hostname
        app.ADSB_ROUTE_LOOKUP_ENABLED = self.original_route_lookup_enabled

    def test_adsb_map_url_uses_current_request_host(self):
        app.ADSB_MAP_URL = ""
        request = SimpleNamespace(url=SimpleNamespace(hostname="gridrunner.local"))

        self.assertEqual(app.adsb_map_url(request), "http://gridrunner.local/tar1090/")

    def test_adsb_map_url_handles_ipv6_hosts(self):
        app.ADSB_MAP_URL = ""
        request = SimpleNamespace(url=SimpleNamespace(hostname="fe80::1"))

        self.assertEqual(app.adsb_map_url(request), "http://[fe80::1]/tar1090/")

    def test_adsb_map_url_prefers_explicit_override(self):
        app.ADSB_MAP_URL = "http://adsb.local/tar1090/"
        request = SimpleNamespace(url=SimpleNamespace(hostname="gridrunner.local"))

        self.assertEqual(app.adsb_map_url(request), "http://adsb.local/tar1090/")

    def test_adsb_map_control_is_direct_map_link(self):
        template = (Path(__file__).resolve().parents[1] / "web" / "templates" / "index.html").read_text(
            encoding="utf-8"
        )

        self.assertIn('href="{{ adsb_map_url }}"', template)
        self.assertIn(">Map</a>", template)
        self.assertNotIn('name="action" value="adsbmap"', template)

    def test_default_aircraft_json_prefers_readsb_runtime_path(self):
        self.assertEqual(config.ADSB_AIRCRAFT_JSON, Path("/run/readsb/aircraft.json"))
        self.assertLess(
            app.ADSB_AIRCRAFT_CANDIDATES.index(Path("/run/readsb/aircraft.json")),
            app.ADSB_AIRCRAFT_CANDIDATES.index(Path("/run/tar1090/aircraft.json")),
        )

    def test_adsb_aircraft_summary_reads_recent_aircraft(self):
        original_candidates = app.ADSB_AIRCRAFT_CANDIDATES
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                aircraft_file = Path(temp_dir) / "aircraft.json"
                aircraft_file.write_text(
                    json.dumps(
                        {
                            "aircraft": [
                                {
                                    "hex": "abc123",
                                    "flight": "GRID01 ",
                                    "alt_baro": 1200,
                                    "gs": 145.5,
                                    "track": 87,
                                    "seen": 2.4,
                                },
                                {
                                    "hex": "def456",
                                    "alt_geom": 2200,
                                    "seen": 14,
                                },
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                os.utime(aircraft_file, (100, 100))
                app.ADSB_AIRCRAFT_CANDIDATES = [aircraft_file]

                summary = app.adsb_aircraft_summary(now=145)

                self.assertEqual(summary["status"], "present")
                self.assertEqual(summary["count"], 2)
                self.assertEqual(summary["age_seconds"], 45)
                self.assertEqual(summary["updated_message"], "updated 45s ago")
                self.assertEqual(summary["aircraft"][0]["ident"], "GRID01")
                self.assertEqual(summary["aircraft"][0]["seen"], "2s")
                self.assertEqual(summary["aircraft"][1]["ident"], "def456")
        finally:
            app.ADSB_AIRCRAFT_CANDIDATES = original_candidates

    def test_adsb_aircraft_summary_enriches_route_when_enabled(self):
        original_candidates = app.ADSB_AIRCRAFT_CANDIDATES
        original_lookup = app.adsb_route_lookup
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                aircraft_file = Path(temp_dir) / "aircraft.json"
                aircraft_file.write_text(
                    json.dumps(
                        {
                            "aircraft": [
                                {
                                    "hex": "abc123",
                                    "flight": "GRID01 ",
                                    "alt_baro": 1200,
                                    "seen": 1,
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                os.utime(aircraft_file, (100, 100))
                app.ADSB_AIRCRAFT_CANDIDATES = [aircraft_file]
                app.ADSB_ROUTE_LOOKUP_ENABLED = True
                app.adsb_route_lookup = lambda callsign: {
                    "route": "KJFK -> KLAX",
                    "airline": "Grid Air",
                    "map_url": "https://flightaware.com/live/flight/GRID01",
                }

                summary = app.adsb_aircraft_summary(now=145)

                self.assertEqual(summary["aircraft"][0]["route"], "KJFK -> KLAX")
                self.assertEqual(summary["aircraft"][0]["airline"], "Grid Air")
                self.assertEqual(
                    summary["aircraft"][0]["route_map_url"],
                    "https://flightaware.com/live/flight/GRID01",
                )
        finally:
            app.ADSB_AIRCRAFT_CANDIDATES = original_candidates
            app.adsb_route_lookup = original_lookup

    def test_plane_tracker_script_emits_compact_mqtt_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            aircraft_file = Path(temp_dir) / "aircraft.json"
            aircraft_file.write_text(
                json.dumps(
                    {
                        "aircraft": [
                            {
                                "hex": "abc123",
                                "flight": " GRID01 ",
                                "alt_baro": 1200,
                                "gs": 145.5,
                                "track": 87,
                                "seen": 2.4,
                                "squawk": "1200",
                                "category": "A1",
                                "lat": 40.0,
                                "lon": -74.0,
                            },
                            {
                                "hex": "def456",
                                "alt_geom": 2200,
                                "seen": 14,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(
                {
                    "GRIDRUNNER_ADSB_AIRCRAFT_JSON": str(aircraft_file),
                    "GRIDRUNNER_PLANE_TRACKER_TOPIC": "gridrunner/test/planes",
                    "GRIDRUNNER_PLANE_TRACKER_LIMIT": "1",
                }
            )

            result = subprocess.run(
                ["bash", str(Path(__file__).resolve().parents[1] / "scripts" / "adsb-plane-tracker.sh"), "--json"],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema"], "gridrunner.adsb.plane_tracker.v1")
            self.assertEqual(payload["status"], "present")
            self.assertEqual(payload["topic"], "gridrunner/test/planes")
            self.assertEqual(payload["count"], 2)
            self.assertEqual(len(payload["aircraft"]), 1)
            self.assertEqual(payload["aircraft"][0]["ident"], "GRID01")
            self.assertEqual(payload["aircraft"][0]["seen_seconds"], 2)

    def test_parse_adsb_route_payload_accepts_adsbdb_shape(self):
        route = app.parse_adsb_route_payload(
            {
                "response": {
                    "flightroute": {
                        "origin": {"icao_code": "KJFK"},
                        "destination": {"icao_code": "KLAX"},
                        "airline": {"name": "Grid Air"},
                    }
                }
            }
        )

        self.assertEqual(route["route"], "KJFK -> KLAX")
        self.assertEqual(route["airline"], "Grid Air")

    def test_adsb_route_lookup_uses_cache(self):
        original_cache = app.ADSB_ROUTE_CACHE
        original_api_url = app.ADSB_ROUTE_API_URL
        original_urlopen = app.urlopen
        calls = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self, _limit):
                return json.dumps({"response": {"flightroute": {"origin": "KJFK", "destination": "KLAX"}}}).encode(
                    "utf-8"
                )

        try:
            app.ADSB_ROUTE_CACHE = {}
            app.ADSB_ROUTE_API_URL = "https://example.test/{callsign}"

            def fake_urlopen(url, timeout):
                calls.append((url, timeout))
                return FakeResponse()

            app.urlopen = fake_urlopen

            self.assertEqual(app.adsb_route_lookup("GRID01")["route"], "KJFK -> KLAX")
            self.assertEqual(app.adsb_route_lookup("GRID01")["route"], "KJFK -> KLAX")
            self.assertEqual(len(calls), 1)
        finally:
            app.ADSB_ROUTE_CACHE = original_cache
            app.ADSB_ROUTE_API_URL = original_api_url
            app.urlopen = original_urlopen


if __name__ == "__main__":
    unittest.main()
