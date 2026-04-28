from pathlib import Path
import tempfile
import unittest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))

import install


class InstallStateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_state_dir = install.STATE_DIR
        self.original_state_file = install.INSTALL_STATE_FILE
        install.STATE_DIR = Path(self.temp_dir.name)
        install.INSTALL_STATE_FILE = install.STATE_DIR / "install.json"

    def tearDown(self):
        install.STATE_DIR = self.original_state_dir
        install.INSTALL_STATE_FILE = self.original_state_file
        self.temp_dir.cleanup()

    def test_parse_install_results(self):
        output = "\n".join(
            [
                "regular output",
                "GRIDRUNNER_INSTALL_RESULT item=base-tools status=installed",
                "GRIDRUNNER_INSTALL_RESULT item=ham-tools status=failed",
            ]
        )

        self.assertEqual(
            install.parse_install_results(output),
            {"base-tools": "installed", "ham-tools": "failed"},
        )

    def test_parse_component_health(self):
        output = "\n".join(
            [
                "GRIDRUNNER_COMPONENT item=base-tools status=present detail=",
                "GRIDRUNNER_COMPONENT item=radio-tools status=missing detail=rtl_test,SoapySDRUtil",
            ]
        )

        self.assertEqual(
            install.parse_component_health(output),
            {
                "base-tools": {"status": "present", "detail": ""},
                "radio-tools": {"status": "missing", "detail": "rtl_test,SoapySDRUtil"},
            },
        )

    def test_apply_marks_only_successful_items_installed(self):
        state = install.update_install_state(
            "apply",
            ["base-tools", "ham-tools"],
            {"base-tools": "installed", "ham-tools": "failed"},
        )

        self.assertEqual(state["items"]["base-tools"]["status"], "installed")
        self.assertEqual(state["items"]["ham-tools"]["status"], "failed")
        self.assertIn("ham-tools", state["failed"])

    def test_skipped_items_remain_available(self):
        state = install.update_install_state("skipped", ["base-tools"])

        self.assertEqual(state["items"]["base-tools"]["status"], "pending")
        self.assertIn("web-runtime", state["skipped"])


if __name__ == "__main__":
    unittest.main()
