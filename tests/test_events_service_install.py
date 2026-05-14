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

    def test_manifest_includes_plane_tracker_service(self):
        manifest = json.loads((REPO_DIR / "install-items.json").read_text(encoding="utf-8"))

        item = next(item for item in manifest if item["id"] == "plane-tracker")

        self.assertEqual(item["label"], "ESP32 Plane Tracker")
        self.assertFalse(item["default"])

    def test_manifest_includes_display_profiles(self):
        manifest = json.loads((REPO_DIR / "install-items.json").read_text(encoding="utf-8"))
        items = {item["id"]: item for item in manifest}

        self.assertEqual(items["display-elecrow-rr050"]["label"], "Display: Elecrow RR050")
        self.assertEqual(items["display-waveshare-5hdmi"]["label"], "Display: Waveshare 5-inch HDMI")
        self.assertEqual(items["display-raspberrypi-touch"]["label"], "Display: Raspberry Pi Touch")
        self.assertEqual(items["operator-display"]["label"], "Operator Display Mode")
        self.assertFalse(items["display-elecrow-rr050"]["default"])
        self.assertFalse(items["display-waveshare-5hdmi"]["default"])
        self.assertFalse(items["display-raspberrypi-touch"]["default"])
        self.assertFalse(items["operator-display"]["default"])

    def test_edge_node_mqtt_dry_run_renders_ingest_service(self):
        result = subprocess.run(
            ["bash", str(REPO_DIR / "scripts" / "install-items.sh"), "--dry-run", "edge-node-mqtt"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("gridrunner-edge-node-ingest.service", result.stdout)
        self.assertIn("systemctl enable --now mosquitto.service", result.stdout)
        self.assertIn("systemctl enable --now gridrunner-edge-node-ingest.service", result.stdout)
        self.assertIn("GRIDRUNNER_INSTALL_RESULT item=edge-node-mqtt status=planned", result.stdout)

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

    def test_plane_tracker_dry_run_renders_units_and_enables_timer(self):
        result = subprocess.run(
            ["bash", str(REPO_DIR / "scripts" / "install-items.sh"), "--dry-run", "plane-tracker"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("gridrunner-plane-tracker.service", result.stdout)
        self.assertIn("gridrunner-plane-tracker.timer", result.stdout)
        self.assertIn("systemctl enable --now gridrunner-plane-tracker.timer", result.stdout)
        self.assertIn("GRIDRUNNER_INSTALL_RESULT item=plane-tracker status=planned", result.stdout)

    def test_display_profile_dry_run_calls_configurator(self):
        result = subprocess.run(
            [
                "bash",
                str(REPO_DIR / "scripts" / "install-items.sh"),
                "--dry-run",
                "display-elecrow-rr050",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("install packages: git evtest xinput", result.stdout)
        self.assertIn("configure-display.sh elecrow-rr050", result.stdout)
        self.assertIn("GRIDRUNNER_INSTALL_RESULT item=display-elecrow-rr050 status=planned", result.stdout)

    def test_configure_display_dry_run_lists_supported_profile(self):
        result = subprocess.run(
            [
                "bash",
                str(REPO_DIR / "scripts" / "configure-display.sh"),
                "raspberrypi-touch",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "GRIDRUNNER_DISPLAY_MODE": "dry-run"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Official Raspberry Pi Touch Display selected", result.stdout)

    def test_configure_display_writes_managed_hdmi_block(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            boot_config = temp_path / "config.txt"
            state_dir = temp_path / "state"
            boot_config.write_text(
                "\n".join(
                    [
                        "arm_64bit=1",
                        "# BEGIN GRIDRUNNER display profile",
                        "old=value",
                        "# END GRIDRUNNER display profile",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    "bash",
                    str(REPO_DIR / "scripts" / "configure-display.sh"),
                    "elecrow-rr050",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                env={
                    **os.environ,
                    "GRIDRUNNER_BOOT_CONFIG": str(boot_config),
                    "GRIDRUNNER_STATE_DIR": str(state_dir),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            config_text = boot_config.read_text(encoding="utf-8")
            self.assertIn("arm_64bit=1", config_text)
            self.assertIn("hdmi_cvt=800 480 60 6 0 0 0", config_text)
            self.assertNotIn("old=value", config_text)
            state_text = (state_dir / "display.env").read_text(encoding="utf-8")
            self.assertIn("GRIDRUNNER_DISPLAY_PROFILE='elecrow-rr050'", state_text)

    def test_operator_display_dry_run_renders_service(self):
        result = subprocess.run(
            [
                "bash",
                str(REPO_DIR / "scripts" / "install-items.sh"),
                "--dry-run",
                "operator-display",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("install packages: tmux unclutter chromium-browser", result.stdout)
        self.assertIn("gridrunner-operator-display.service", result.stdout)
        self.assertIn("operator-display.sh configure web", result.stdout)
        self.assertIn("systemctl enable gridrunner-operator-display.service", result.stdout)
        self.assertIn("GRIDRUNNER_INSTALL_RESULT item=operator-display status=planned", result.stdout)

    def test_operator_display_configure_writes_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "operator-display.env"
            result = subprocess.run(
                [
                    "bash",
                    str(REPO_DIR / "scripts" / "operator-display.sh"),
                    "configure",
                    "adsb",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                env={**os.environ, "GRIDRUNNER_OPERATOR_DISPLAY_STATE": str(state_file)},
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            state_text = state_file.read_text(encoding="utf-8")
            self.assertIn("OPERATOR_DISPLAY_MODE='adsb'", state_text)
            self.assertIn("GRIDRUNNER_OPERATOR_DISPLAY mode=adsb", result.stdout)

    def test_operator_display_script_defines_tiled_tmux_layout(self):
        script = (REPO_DIR / "scripts" / "operator-display.sh").read_text(encoding="utf-8")

        self.assertIn('tmux split-window -h -t "$OPERATOR_DISPLAY_TMUX_SESSION:ops"', script)
        self.assertIn('tmux split-window -v -t "$OPERATOR_DISPLAY_TMUX_SESSION:ops.1"', script)
        self.assertIn("tmux select-layout", script)

    def test_plane_tracker_service_publishes_adsb_summary(self):
        service = (REPO_DIR / "deploy" / "systemd" / "gridrunner-plane-tracker.service").read_text(
            encoding="utf-8"
        )

        self.assertIn("adsb-plane-tracker.sh --publish", service)
        self.assertIn("After=network-online.target mosquitto.service readsb.service", service)

    def test_edge_node_ingest_service_subscribes_to_mqtt(self):
        service = (REPO_DIR / "deploy" / "systemd" / "gridrunner-edge-node-ingest.service").read_text(
            encoding="utf-8"
        )

        self.assertIn("edge-node-subscribe.sh", service)
        self.assertIn("After=network-online.target mosquitto.service", service)
        self.assertIn("Restart=always", service)
        self.assertIn("WantedBy=multi-user.target", service)

    def test_operator_display_service_launches_display_script(self):
        service = (REPO_DIR / "deploy" / "systemd" / "gridrunner-operator-display.service").read_text(
            encoding="utf-8"
        )

        self.assertIn("operator-display.sh launch", service)
        self.assertIn("After=graphical.target network-online.target gridrunner-web.service", service)
        self.assertIn("WantedBy=graphical.target", service)

    def test_events_service_accepts_timeout_exit_as_success(self):
        service = (REPO_DIR / "deploy" / "systemd" / "gridrunner-events.service").read_text(
            encoding="utf-8"
        )

        self.assertIn("SuccessExitStatus=124", service)
        self.assertIn("scripts/run-events.sh", service)
        self.assertIn("EnvironmentFile=-{{GRIDRUNNER_HOME}}/state/storage.env", service)

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

    def test_run_events_appends_stdout_to_configured_events_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            operator_home = Path(temp_dir) / "home"
            operator_home.mkdir()
            events_log = Path(temp_dir) / "usb" / "logs" / "ghost-events.log"
            event_script = operator_home / "ghost-events.sh"
            event_script.write_text("#!/bin/bash\necho usb-event-line\n", encoding="utf-8")
            event_script.chmod(0o755)
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
            self.assertIn("usb-event-line", result.stdout)
            self.assertIn("usb-event-line", events_log.read_text(encoding="utf-8"))

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
