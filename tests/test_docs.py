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
        self.assertIn("GRIDRUNNER_MQTT_TOPIC", source)
        self.assertIn("drawRadarGrid", source)


if __name__ == "__main__":
    unittest.main()
