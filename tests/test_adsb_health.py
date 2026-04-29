from pathlib import Path
import os
import stat
import subprocess
import tempfile
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]
ADSB_HEALTH = REPO_DIR / "scripts" / "adsb-health.sh"
COMPONENT_HEALTH = REPO_DIR / "scripts" / "component-health.sh"
INSTALL_ITEMS = REPO_DIR / "scripts" / "install-items.sh"


class AdsbHealthTests(unittest.TestCase):
    def run_with_fake_readsb(self, help_output):
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_bin = Path(temp_dir) / "bin"
            fake_bin.mkdir()
            readsb = fake_bin / "readsb"
            readsb.write_text(
                "#!/bin/bash\n"
                "if [ \"${1:-}\" = \"--help\" ]; then\n"
                f"  cat <<'EOF'\n{help_output}\nEOF\n"
                "fi\n",
                encoding="utf-8",
            )
            readsb.chmod(readsb.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env['PATH']}"

            return subprocess.run(
                ["bash", str(ADSB_HEALTH)],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

    def test_adsb_health_reports_rtl_supported(self):
        result = self.run_with_fake_readsb("supported device types: rtlsdr modesbeast")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("readsb OK (RTL supported)", result.stdout)

    def test_adsb_health_reports_no_rtl_support(self):
        result = self.run_with_fake_readsb("supported device types: modesbeast gnshulc ifile none")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("readsb BROKEN (no RTL support)", result.stdout)

    def test_component_health_degrades_adsb_without_rtl_support(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_bin = Path(temp_dir) / "bin"
            fake_bin.mkdir()
            readsb = fake_bin / "readsb"
            readsb.write_text(
                "#!/bin/bash\n"
                "echo 'supported device types: modesbeast gnshulc ifile none'\n",
                encoding="utf-8",
            )
            readsb.chmod(readsb.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env['PATH']}"

            result = subprocess.run(
                ["bash", str(COMPONENT_HEALTH)],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("GRIDRUNNER_COMPONENT item=adsb-tools status=degraded detail=no-rtl-support", result.stdout)

    def test_adsb_install_dry_run_uses_wiedehopf_helper_not_apt_readsb(self):
        result = subprocess.run(
            ["bash", str(INSTALL_ITEMS), "--dry-run", "adsb-tools"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("install-adsb-readsb.sh", result.stdout)
        self.assertNotIn("apt-get install -y readsb", result.stdout)


if __name__ == "__main__":
    unittest.main()
