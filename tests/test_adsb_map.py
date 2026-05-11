from pathlib import Path
from types import SimpleNamespace
import json
import os
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

    def tearDown(self):
        app.ADSB_MAP_URL = self.original_adsb_map_url
        app.DEVICE_HOSTNAME = self.original_device_hostname

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


if __name__ == "__main__":
    unittest.main()
