from pathlib import Path
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]


class SudoersTests(unittest.TestCase):
    def test_sudoers_allows_web_service_restart(self):
        script = (REPO_DIR / "scripts" / "setup-sudoers.sh").read_text(encoding="utf-8")

        self.assertIn("/usr/bin/systemctl restart gridrunner-web.service", script)


if __name__ == "__main__":
    unittest.main()
