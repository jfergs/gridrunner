from pathlib import Path
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]


class SudoersTests(unittest.TestCase):
    def test_sudoers_allows_web_service_restart(self):
        script = (REPO_DIR / "scripts" / "setup-sudoers.sh").read_text(encoding="utf-8")

        self.assertIn("/usr/bin/systemctl restart gridrunner-web.service", script)
        self.assertIn("/usr/bin/systemctl enable --now mosquitto.service", script)
        self.assertIn("/usr/bin/systemctl enable --now gridrunner-plane-tracker.timer", script)
        self.assertIn("/etc/systemd/system/gridrunner-plane-tracker.service", script)

    def test_sudoers_allows_networkmanager_wifi_controls(self):
        script = (REPO_DIR / "scripts" / "setup-sudoers.sh").read_text(encoding="utf-8")

        self.assertIn("/usr/bin/nmcli radio wifi on", script)
        self.assertIn("/usr/bin/nmcli connection up *", script)
        self.assertIn("/usr/bin/nmcli connection down *", script)
        self.assertIn("/usr/bin/nmcli connection modify *", script)
        self.assertIn("/usr/bin/nmcli connection add *", script)


if __name__ == "__main__":
    unittest.main()
