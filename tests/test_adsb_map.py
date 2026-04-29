from pathlib import Path
from types import SimpleNamespace
import unittest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))

import app


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
        self.assertIn("ADS-B Map", template)
        self.assertNotIn('name="action" value="adsbmap"', template)


if __name__ == "__main__":
    unittest.main()
