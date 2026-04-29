from pathlib import Path
from types import SimpleNamespace
import unittest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))

import app


class TemplateRenderTests(unittest.TestCase):
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
            },
        )

        self.assertIn(b"Wi-Fi status unavailable", response.body)


if __name__ == "__main__":
    unittest.main()
