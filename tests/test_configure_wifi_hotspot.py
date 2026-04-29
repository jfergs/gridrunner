from pathlib import Path
import os
import stat
import subprocess
import tempfile
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT = REPO_DIR / "scripts" / "configure-wifi-hotspot.sh"


class ConfigureWifiHotspotTests(unittest.TestCase):
    def test_noninteractive_env_writes_private_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "wifi-fallback.env"
            env = os.environ.copy()
            env.update(
                {
                    "GRIDRUNNER_WIFI_CONFIG": str(config_file),
                    "HOTSPOT": "GRIDRUNNER-HOTSPOT",
                    "HOTSPOT_SSID": "Field Runner",
                    "HOTSPOT_PASSWORD": "password123",
                    "GRIDRUNNER_NONINTERACTIVE": "1",
                }
            )

            result = subprocess.run(
                ["bash", str(SCRIPT)],
                input="",
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            contents = config_file.read_text(encoding="utf-8")
            mode = stat.S_IMODE(config_file.stat().st_mode)

            self.assertEqual(mode, 0o600)
            self.assertIn("HOTSPOT='GRIDRUNNER-HOTSPOT'", contents)
            self.assertIn("HOTSPOT_SSID='Field Runner'", contents)
            self.assertIn("HOTSPOT_PASSWORD='password123'", contents)

    def test_shell_quotes_single_quotes_in_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "wifi-fallback.env"
            env = os.environ.copy()
            env.update(
                {
                    "GRIDRUNNER_WIFI_CONFIG": str(config_file),
                    "HOTSPOT_SSID": "Runner's Hotspot",
                    "HOTSPOT_PASSWORD": "password123",
                    "GRIDRUNNER_NONINTERACTIVE": "1",
                }
            )

            result = subprocess.run(
                ["bash", str(SCRIPT)],
                input="",
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            source_result = subprocess.run(
                ["bash", "-c", f". {config_file}; printf '%s' \"$HOTSPOT_SSID\""],
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(source_result.returncode, 0, source_result.stderr)
            self.assertEqual(source_result.stdout, "Runner's Hotspot")


if __name__ == "__main__":
    unittest.main()
