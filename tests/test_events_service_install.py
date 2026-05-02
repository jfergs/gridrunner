from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]


class EventsServiceInstallTests(unittest.TestCase):
    def test_manifest_includes_events_service(self):
        manifest = json.loads((REPO_DIR / "install-items.json").read_text(encoding="utf-8"))

        events_item = next(item for item in manifest if item["id"] == "events-service")

        self.assertEqual(events_item["label"], "Events Service")
        self.assertTrue(events_item["default"])

    def test_events_service_dry_run_renders_units_and_enables_timer(self):
        result = subprocess.run(
            ["bash", str(REPO_DIR / "scripts" / "install-items.sh"), "--dry-run", "events-service"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("gridrunner-events.service", result.stdout)
        self.assertIn("gridrunner-events.timer", result.stdout)
        self.assertIn("systemctl enable --now gridrunner-events.timer", result.stdout)
        self.assertIn("GRIDRUNNER_INSTALL_RESULT item=events-service status=planned", result.stdout)

    def test_events_service_accepts_timeout_exit_as_success(self):
        service = (REPO_DIR / "deploy" / "systemd" / "gridrunner-events.service").read_text(
            encoding="utf-8"
        )

        self.assertIn("SuccessExitStatus=124", service)
        self.assertIn("scripts/run-events.sh", service)

    def test_events_service_dry_run_patches_legacy_event_script(self):
        result = subprocess.run(
            ["bash", str(REPO_DIR / "scripts" / "install-items.sh"), "--dry-run", "events-service"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("patch-events-script.sh", result.stdout)

    def test_patch_events_script_bounds_btmgmt_find(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            event_script = Path(temp_dir) / "ghost-events.sh"
            event_script.write_text(
                "\n".join(
                    [
                        "#!/bin/bash",
                        "sudo btmgmt find",
                        "echo done",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            event_script.chmod(0o755)

            result = subprocess.run(
                [
                    "bash",
                    str(REPO_DIR / "scripts" / "patch-events-script.sh"),
                    str(event_script),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            patched = event_script.read_text(encoding="utf-8")
            self.assertIn('GRIDRUNNER_SCAN_BLUETOOTH_ENABLED', patched)
            self.assertIn('timeout "${GRIDRUNNER_BTMGMT_FIND_SECONDS:-12}s" sudo btmgmt find', patched)
            self.assertTrue((Path(str(event_script) + ".gridrunner-pre-legacy-patch")).exists())

    def test_patch_events_script_gates_network_scanners(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            event_script = Path(temp_dir) / "ghost-events.sh"
            event_script.write_text(
                "\n".join(
                    [
                        "#!/bin/bash",
                        "sudo arp-scan --localnet",
                        "nmap -sn 10.0.0.0/24",
                        "echo done",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            event_script.chmod(0o755)

            result = subprocess.run(
                [
                    "bash",
                    str(REPO_DIR / "scripts" / "patch-events-script.sh"),
                    str(event_script),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            patched = event_script.read_text(encoding="utf-8")
            self.assertEqual(patched.count('GRIDRUNNER_SCAN_NETWORK_ENABLED'), 2)
            self.assertIn("sudo arp-scan --localnet", patched)
            self.assertIn("nmap -sn 10.0.0.0/24", patched)
            self.assertIn("gated network scan commands", result.stdout)

    def test_patch_events_script_repairs_corrupted_air_copy_line(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            event_script = Path(temp_dir) / "ghost-events.sh"
            event_script.write_text(
                "\n".join(
                    [
                        "#!/bin/bash",
                        'timeout "${GRIDRUNNER_BTMGMT_FIND_SECONDS:-12}s" sudo btmgmt find',
                        'cp "$AIR_NOW" "$AIR_LAST"0;177;25M0;177;25m',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            event_script.chmod(0o755)

            result = subprocess.run(
                [
                    "bash",
                    str(REPO_DIR / "scripts" / "patch-events-script.sh"),
                    str(event_script),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            patched = event_script.read_text(encoding="utf-8")
            self.assertIn('cp "$AIR_NOW" "$AIR_LAST"', patched)
            self.assertNotIn("0;177;25M0;177;25m", patched)
            self.assertIn("repaired corrupted AIR_LAST copy", result.stdout)

    def test_run_events_uses_operator_named_script(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            operator_home = Path(temp_dir)
            event_script = operator_home / "ghost-events.sh"
            event_script.write_text("#!/bin/bash\necho ran-events\n", encoding="utf-8")
            event_script.chmod(0o755)
            env = os.environ.copy()
            env.update(
                {
                    "GRIDRUNNER_OPERATOR_USER": "ghost",
                    "GRIDRUNNER_OPERATOR_HOME": str(operator_home),
                    "GRIDRUNNER_EVENTS_RUN_SECONDS": "5",
                    "GRIDRUNNER_SCAN_RUN_ONCE": "1",
                }
            )

            result = subprocess.run(
                ["bash", str(REPO_DIR / "scripts" / "run-events.sh")],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ran-events", result.stdout)

    def test_run_events_tolerates_legacy_failure_when_log_updates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            operator_home = Path(temp_dir)
            event_script = operator_home / "ghost-events.sh"
            events_log = operator_home / "ghost-events.log"
            event_script.write_text(
                "\n".join(
                    [
                        "#!/bin/bash",
                        f"echo updated >> {events_log}",
                        "not-a-real-command",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            event_script.chmod(0o755)
            events_log.write_text("old\n", encoding="utf-8")
            os.utime(events_log, (1, 1))
            env = os.environ.copy()
            env.update(
                {
                    "GRIDRUNNER_OPERATOR_USER": "ghost",
                    "GRIDRUNNER_OPERATOR_HOME": str(operator_home),
                    "GRIDRUNNER_EVENTS_LOG": str(events_log),
                    "GRIDRUNNER_EVENTS_RUN_SECONDS": "5",
                    "GRIDRUNNER_SCAN_RUN_ONCE": "1",
                }
            )

            result = subprocess.run(
                ["bash", str(REPO_DIR / "scripts" / "run-events.sh")],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("legacy script exit 127", result.stdout)

    def test_run_events_skips_legacy_script_when_scans_are_off(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            operator_home = Path(temp_dir)
            event_script = operator_home / "ghost-events.sh"
            event_script.write_text("#!/bin/bash\necho should-not-run\n", encoding="utf-8")
            event_script.chmod(0o755)
            env = os.environ.copy()
            env.update(
                {
                    "GRIDRUNNER_OPERATOR_USER": "ghost",
                    "GRIDRUNNER_OPERATOR_HOME": str(operator_home),
                    "GRIDRUNNER_SCAN_STATE_FILE": str(operator_home / "scan-controls.env"),
                }
            )

            result = subprocess.run(
                ["bash", str(REPO_DIR / "scripts" / "run-events.sh")],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Bluetooth and network device scans are off", result.stdout)
            self.assertNotIn("should-not-run", result.stdout)

    def test_run_events_honors_continuous_interval(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            operator_home = Path(temp_dir)
            state_file = operator_home / "scan-controls.env"
            event_script = operator_home / "ghost-events.sh"
            event_script.write_text("#!/bin/bash\necho ran-continuous\n", encoding="utf-8")
            event_script.chmod(0o755)
            state_file.write_text(
                "\n".join(
                    [
                        "GRIDRUNNER_SCAN_BLUETOOTH_MODE=continuous",
                        "GRIDRUNNER_SCAN_NETWORK_MODE=off",
                        "GRIDRUNNER_SCAN_INTERVAL_SECONDS=60",
                        "GRIDRUNNER_SCAN_LAST_RUN=0",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(
                {
                    "GRIDRUNNER_OPERATOR_USER": "ghost",
                    "GRIDRUNNER_OPERATOR_HOME": str(operator_home),
                    "GRIDRUNNER_SCAN_STATE_FILE": str(state_file),
                    "GRIDRUNNER_EVENTS_RUN_SECONDS": "5",
                }
            )

            first = subprocess.run(
                ["bash", str(REPO_DIR / "scripts" / "run-events.sh")],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )
            second = subprocess.run(
                ["bash", str(REPO_DIR / "scripts" / "run-events.sh")],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("ran-continuous", first.stdout)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("next scan interval has not elapsed", second.stdout)

    def test_run_events_exports_single_scan_phase(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            operator_home = Path(temp_dir)
            event_script = operator_home / "ghost-events.sh"
            event_script.write_text(
                "\n".join(
                    [
                        "#!/bin/bash",
                        'echo bluetooth=$GRIDRUNNER_SCAN_BLUETOOTH_ENABLED',
                        'echo network=$GRIDRUNNER_SCAN_NETWORK_ENABLED',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            event_script.chmod(0o755)
            env = os.environ.copy()
            env.update(
                {
                    "GRIDRUNNER_OPERATOR_USER": "ghost",
                    "GRIDRUNNER_OPERATOR_HOME": str(operator_home),
                    "GRIDRUNNER_EVENTS_RUN_SECONDS": "5",
                    "GRIDRUNNER_SCAN_RUN_ONCE": "1",
                    "GRIDRUNNER_SCAN_ONCE_TARGET": "network",
                }
            )

            result = subprocess.run(
                ["bash", str(REPO_DIR / "scripts" / "run-events.sh")],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("bluetooth=0", result.stdout)
            self.assertIn("network=1", result.stdout)


if __name__ == "__main__":
    unittest.main()
