from pathlib import Path
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]


class SudoersTests(unittest.TestCase):
    def test_sudoers_allows_web_service_restart(self):
        script = (REPO_DIR / "scripts" / "setup-sudoers.sh").read_text(encoding="utf-8")

        self.assertIn("/usr/bin/true", script)
        self.assertIn("/usr/bin/systemctl restart gridrunner-web.service", script)
        self.assertIn("/usr/bin/systemctl enable --now mosquitto.service", script)
        self.assertIn("/usr/bin/systemctl enable --now gridrunner-edge-node-ingest.service", script)
        self.assertIn("/etc/systemd/system/gridrunner-edge-node-ingest.service", script)
        self.assertIn("/usr/bin/systemctl enable --now gridrunner-plane-tracker.timer", script)
        self.assertIn("/etc/systemd/system/gridrunner-plane-tracker.service", script)
        self.assertIn("/usr/bin/systemctl enable gridrunner-operator-display.service", script)
        self.assertIn("/etc/systemd/system/gridrunner-operator-display.service", script)

    def test_sudoers_allows_networkmanager_wifi_controls(self):
        script = (REPO_DIR / "scripts" / "setup-sudoers.sh").read_text(encoding="utf-8")

        self.assertIn("/usr/bin/nmcli radio wifi on", script)
        self.assertIn("/usr/bin/nmcli connection up *", script)
        self.assertIn("/usr/bin/nmcli connection down *", script)
        self.assertIn("/usr/bin/nmcli connection modify *", script)
        self.assertIn("/usr/bin/nmcli connection add *", script)

    def test_sudoers_allows_display_configurator(self):
        script = (REPO_DIR / "scripts" / "setup-sudoers.sh").read_text(encoding="utf-8")

        self.assertIn("/usr/bin/bash */gridrunner/scripts/configure-display.sh *", script)

    def test_sudoers_does_not_allow_arbitrary_apt_install(self):
        script = (REPO_DIR / "scripts" / "setup-sudoers.sh").read_text(encoding="utf-8")

        self.assertNotIn("/usr/bin/apt-get install -y *", script)
        self.assertIn("apt-get install -y -o Dpkg::Options::=--force-confdef", script)


if __name__ == "__main__":
    unittest.main()
