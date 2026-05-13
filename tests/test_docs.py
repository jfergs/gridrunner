from pathlib import Path
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]


class DocsTests(unittest.TestCase):
    def test_storage_model_documents_internal_paths_and_rollback(self):
        doc = (REPO_DIR / "docs" / "storage-model.md").read_text(encoding="utf-8")

        self.assertIn("~/gridrunner/state/", doc)
        self.assertIn("GRIDRUNNER_STORAGE_MODE=internal|external", doc)
        self.assertIn("Backups", doc)
        self.assertIn("Operator logs", doc)
        self.assertIn("Rollback Behavior", doc)
        self.assertIn("The UI must not auto-format drives or erase data.", doc)

    def test_plane_tracker_firmware_documents_setup(self):
        readme = (REPO_DIR / "firmware" / "plane-tracker" / "README.md").read_text(encoding="utf-8")
        source = (REPO_DIR / "firmware" / "plane-tracker" / "src" / "main.cpp").read_text(encoding="utf-8")

        self.assertIn("gridrunner/adsb/plane-tracker", readme)
        self.assertIn("GPIO14", readme)
        self.assertIn("pioarduino", readme)
        self.assertIn("GRIDRUNNER_MQTT_TOPIC", source)
        self.assertIn("Arduino_HWSPI", source)
        self.assertIn("GRIDRUNNER_LCD_DIAGNOSTIC", source)
        self.assertIn("drawRadarGrid", source)

    def test_rf_tracker_firmware_documents_setup(self):
        readme = (REPO_DIR / "firmware" / "rf-tracker" / "README.md").read_text(encoding="utf-8")
        source = (REPO_DIR / "firmware" / "rf-tracker" / "src" / "main.cpp").read_text(encoding="utf-8")

        self.assertIn("GitHub issue `#42`", readme)
        self.assertIn("gridrunner/nodes/<node-id>/telemetry", readme)
        self.assertIn("Wi-Fi access-point discovery", readme)
        self.assertIn("BLE advertisement discovery", readme)
        self.assertIn("without requiring the GRIDRUNNER core", readme)
        self.assertIn("pending_scan_count", readme)
        self.assertIn("without publishing device identifiers", readme)
        self.assertIn("Remote ID candidates", readme)
        self.assertIn("GRIDRUNNER_NODE_ID", source)
        self.assertIn("scanWifi", source)
        self.assertIn("scanBle", source)
        self.assertIn("textSuggestsDrone", source)
        self.assertIn("droneCandidateCount", source)
        self.assertIn("GRIDRUNNER_BLE_SCAN_INTERVAL_MS", source)
        self.assertIn("publishTelemetry", source)


if __name__ == "__main__":
    unittest.main()
