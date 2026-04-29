from pathlib import Path
import json
import subprocess
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]


class EventsServiceInstallTests(unittest.TestCase):
    def test_manifest_includes_events_service(self):
        manifest = json.loads((REPO_DIR / "install-items.json").read_text(encoding="utf-8"))

        events_item = next(item for item in manifest if item["id"] == "events-service")

        self.assertEqual(events_item["label"], "Events Service")
        self.assertTrue(events_item["default"])

    def test_events_service_dry_run_renders_units_and_enables_timer(self):
        result = subprocess.run(
            ["bash", str(REPO_DIR / "scripts" / "install-items.sh"), "--dry-run", "events-service"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("gridrunner-events.service", result.stdout)
        self.assertIn("gridrunner-events.timer", result.stdout)
        self.assertIn("systemctl enable --now gridrunner-events.timer", result.stdout)
        self.assertIn("GRIDRUNNER_INSTALL_RESULT item=events-service status=planned", result.stdout)


if __name__ == "__main__":
    unittest.main()
