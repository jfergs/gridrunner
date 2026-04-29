from pathlib import Path
import os
import stat
import subprocess
import tempfile
import textwrap
import unittest

import sys

REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT = REPO_DIR / "scripts" / "wifi-status.sh"
sys.path.insert(0, str(REPO_DIR / "web"))

import app


class WifiStatusTests(unittest.TestCase):
    def run_with_fakes(self, connection):
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_bin = Path(temp_dir) / "bin"
            fake_bin.mkdir()

            nmcli = fake_bin / "nmcli"
            nmcli.write_text(
                textwrap.dedent(
                    f"""\
                    #!/bin/bash
                    if [ "$*" = "-t -f DEVICE,STATE,CONNECTION dev" ]; then
                      echo "wlan0:connected:{connection}"
                    elif [ "$*" = "-g IP4.ADDRESS dev show wlan0" ]; then
                      echo "192.168.8.1/24"
                    fi
                    """
                ),
                encoding="utf-8",
            )
            nmcli.chmod(nmcli.stat().st_mode | stat.S_IXUSR)

            systemctl = fake_bin / "systemctl"
            systemctl.write_text(
                textwrap.dedent(
                    """\
                    #!/bin/bash
                    if [ "$1" = "is-active" ] && [ "$2" = "gridrunner-wifi.timer" ]; then
                      echo active
                    elif [ "$1" = "is-enabled" ] && [ "$2" = "gridrunner-wifi.timer" ]; then
                      echo enabled
                    elif [ "$1" = "is-active" ] && [ "$2" = "gridrunner-wifi.service" ]; then
                      echo inactive
                    else
                      echo unknown
                    fi
                    """
                ),
                encoding="utf-8",
            )
            systemctl.chmod(systemctl.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env['PATH']}"

            return subprocess.run(
                ["bash", str(SCRIPT)],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

    def test_known_wifi_status(self):
        result = self.run_with_fakes("HomeWiFi")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status=present", result.stdout)
        self.assertIn("mode=known-wifi", result.stdout)
        self.assertIn("ip=192.168.8.1", result.stdout)
        self.assertNotIn("connection=HomeWiFi", result.stdout)

    def test_hotspot_status(self):
        result = self.run_with_fakes("GRIDRUNNER-HOTSPOT")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status=present", result.stdout)
        self.assertIn("mode=hotspot", result.stdout)

    def test_parse_keyed_status(self):
        parsed = app.parse_keyed_status(
            "noise\nGRIDRUNNER_WIFI status=present mode=known-wifi ip=192.168.8.1\n",
            "GRIDRUNNER_WIFI ",
        )

        self.assertEqual(parsed["status"], "present")
        self.assertEqual(parsed["mode"], "known-wifi")
        self.assertEqual(parsed["ip"], "192.168.8.1")


if __name__ == "__main__":
    unittest.main()
