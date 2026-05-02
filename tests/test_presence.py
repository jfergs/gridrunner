from pathlib import Path
import json
import os
import stat
import subprocess
import tempfile
import textwrap
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT = REPO_DIR / "scripts" / "ghost-presence.sh"


class PresenceTests(unittest.TestCase):
    def test_manifest_includes_presence_script(self):
        manifest = json.loads((REPO_DIR / "install-items.json").read_text(encoding="utf-8"))

        item = next(item for item in manifest if item["id"] == "presence-script")

        self.assertEqual(item["label"], "Presence Script")
        self.assertTrue(item["default"])

    def test_presence_script_dry_run_installs_operator_named_script(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env = os.environ.copy()
            env.update(
                {
                    "GRIDRUNNER_OPERATOR_USER": "ghost",
                    "GRIDRUNNER_OPERATOR_HOME": temp_dir,
                }
            )

            result = subprocess.run(
                [
                    "bash",
                    str(REPO_DIR / "scripts" / "install-items.sh"),
                    "--dry-run",
                    "presence-script",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("scripts/ghost-presence.sh", result.stdout)
            self.assertIn(f"{temp_dir}/ghost-presence.sh", result.stdout)
            self.assertIn(
                "GRIDRUNNER_INSTALL_RESULT item=presence-script status=planned",
                result.stdout,
            )

    def run_presence(self, state_text="", env=None):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fake_bin = temp_path / "bin"
            fake_bin.mkdir()
            calls = temp_path / "calls.log"
            state_file = temp_path / "scan-controls.env"
            state_file.write_text(state_text, encoding="utf-8")

            arp_scan = fake_bin / "arp-scan"
            arp_scan.write_text(
                "#!/bin/bash\n"
                'echo "$*" >> "$GRIDRUNNER_TEST_CALLS"\n',
                encoding="utf-8",
            )
            arp_scan.chmod(arp_scan.stat().st_mode | stat.S_IXUSR)

            timeout = fake_bin / "timeout"
            timeout.write_text(
                textwrap.dedent(
                    """\
                    #!/bin/bash
                    shift
                    "$@"
                    """
                ),
                encoding="utf-8",
            )
            timeout.chmod(timeout.stat().st_mode | stat.S_IXUSR)

            sleep = fake_bin / "sleep"
            sleep.write_text("#!/bin/bash\nexit 42\n", encoding="utf-8")
            sleep.chmod(sleep.stat().st_mode | stat.S_IXUSR)

            run_env = os.environ.copy()
            run_env.update(
                {
                    "PATH": f"{fake_bin}:{run_env['PATH']}",
                    "GRIDRUNNER_SCAN_STATE_FILE": str(state_file),
                    "GRIDRUNNER_TEST_CALLS": str(calls),
                    "GRIDRUNNER_PRESENCE_RUN_ONCE": "1",
                }
            )
            if env:
                run_env.update(env)

            result = subprocess.run(
                ["bash", str(SCRIPT)],
                capture_output=True,
                text=True,
                timeout=10,
                env=run_env,
            )
            calls_output = calls.read_text(encoding="utf-8") if calls.exists() else ""
            return result, calls_output

    def test_installed_presence_script_defaults_to_home_gridrunner_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            home = temp_path / "home"
            gridrunner = home / "gridrunner"
            scripts = gridrunner / "scripts"
            state_dir = gridrunner / "state"
            fake_bin = temp_path / "bin"
            scripts.mkdir(parents=True)
            state_dir.mkdir()
            fake_bin.mkdir()

            installed_script = home / "ghost-presence.sh"
            installed_script.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
            installed_script.chmod(installed_script.stat().st_mode | stat.S_IXUSR)
            (scripts / "ghost-presence.sh").write_text("# repo marker\n", encoding="utf-8")
            (state_dir / "scan-controls.env").write_text(
                "GRIDRUNNER_SCAN_NETWORK_MODE=continuous\n",
                encoding="utf-8",
            )

            calls = temp_path / "calls.log"
            arp_scan = fake_bin / "arp-scan"
            arp_scan.write_text(
                "#!/bin/bash\n"
                'echo "$*" >> "$GRIDRUNNER_TEST_CALLS"\n',
                encoding="utf-8",
            )
            arp_scan.chmod(arp_scan.stat().st_mode | stat.S_IXUSR)

            timeout = fake_bin / "timeout"
            timeout.write_text("#!/bin/bash\nshift\n\"$@\"\n", encoding="utf-8")
            timeout.chmod(timeout.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "PATH": f"{fake_bin}:{env['PATH']}",
                    "GRIDRUNNER_TEST_CALLS": str(calls),
                    "GRIDRUNNER_PRESENCE_RUN_ONCE": "1",
                }
            )

            result = subprocess.run(
                ["bash", str(installed_script)],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--localnet", calls.read_text(encoding="utf-8"))

    def test_presence_skips_network_scan_when_controls_are_off(self):
        result, calls = self.run_presence(
            "\n".join(
                [
                    "GRIDRUNNER_SCAN_BLUETOOTH_MODE=off",
                    "GRIDRUNNER_SCAN_NETWORK_MODE=off",
                    "",
                ]
            )
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("presence network scan skipped", result.stdout)
        self.assertEqual(calls, "")

    def test_presence_runs_network_scan_when_continuous_network_enabled(self):
        result, calls = self.run_presence(
            "\n".join(
                [
                    "GRIDRUNNER_SCAN_BLUETOOTH_MODE=off",
                    "GRIDRUNNER_SCAN_NETWORK_MODE=continuous",
                    "",
                ]
            )
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("--localnet", calls)


if __name__ == "__main__":
    unittest.main()
