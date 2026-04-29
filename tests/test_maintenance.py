from pathlib import Path
import os
import stat
import subprocess
import tempfile
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]
ROTATE_LOGS = REPO_DIR / "scripts" / "rotate-logs.sh"
DISK_HEALTH = REPO_DIR / "scripts" / "disk-health.sh"
SERVICE_HEALTH = REPO_DIR / "scripts" / "service-health.sh"
SYSTEM_BACKUP = REPO_DIR / "scripts" / "system-backup.sh"


class MaintenanceTests(unittest.TestCase):
    def test_rotate_logs_skips_small_event_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            events_log = Path(temp_dir) / "ghost-events.log"
            events_log.write_text("event\n", encoding="utf-8")
            env = os.environ.copy()
            env.update(
                {
                    "GRIDRUNNER_EVENTS_LOG": str(events_log),
                    "GRIDRUNNER_EVENTS_LOG_MAX_BYTES": "1000",
                }
            )

            result = subprocess.run(
                ["bash", str(ROTATE_LOGS)],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("status=skipped", result.stdout)
            self.assertEqual(events_log.read_text(encoding="utf-8"), "event\n")

    def test_rotate_logs_rotates_large_event_log_and_keeps_current_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            events_log = Path(temp_dir) / "ghost-events.log"
            events_log.write_text("0123456789\n", encoding="utf-8")
            env = os.environ.copy()
            env.update(
                {
                    "GRIDRUNNER_EVENTS_LOG": str(events_log),
                    "GRIDRUNNER_EVENTS_LOG_MAX_BYTES": "5",
                    "GRIDRUNNER_EVENTS_LOG_KEEP": "2",
                }
            )

            result = subprocess.run(
                ["bash", str(ROTATE_LOGS)],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("status=rotated", result.stdout)
            self.assertTrue(events_log.exists())
            self.assertEqual(events_log.read_text(encoding="utf-8"), "")
            self.assertTrue(list(Path(temp_dir).glob("ghost-events.log.*")))

    def test_disk_health_reports_warn_from_df_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_bin = Path(temp_dir) / "bin"
            fake_bin.mkdir()
            fake_df = fake_bin / "df"
            fake_df.write_text(
                "\n".join(
                    [
                        "#!/bin/bash",
                        "echo 'Filesystem 1024-blocks Used Available Capacity Mounted on'",
                        "echo '/dev/root 1000 900 100 90% /'",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            fake_df.chmod(fake_df.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}:{env['PATH']}",
                    "GRIDRUNNER_DISK_CHECK_PATH": temp_dir,
                    "GRIDRUNNER_DISK_WARN_PERCENT": "85",
                    "GRIDRUNNER_DISK_CRITICAL_PERCENT": "95",
                }
            )

            result = subprocess.run(
                ["bash", str(DISK_HEALTH)],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("GRIDRUNNER_DISK_HEALTH status=warn", result.stdout)
            self.assertIn("used_percent=90", result.stdout)

    def test_system_backup_prunes_old_backups(self):
        script = SYSTEM_BACKUP.read_text(encoding="utf-8")

        self.assertIn("GRIDRUNNER_BACKUP_KEEP", script)
        self.assertIn("pruned old backup", script)

    def test_service_health_reports_units(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_bin = Path(temp_dir) / "bin"
            fake_bin.mkdir()
            fake_systemctl = fake_bin / "systemctl"
            fake_systemctl.write_text(
                "\n".join(
                    [
                        "#!/bin/bash",
                        'if [ "$1" = "is-active" ]; then',
                        '  [ "$2" = "readsb.service" ] && echo active && exit 0',
                        "  echo inactive",
                        "  exit 3",
                        "fi",
                        'if [ "$1" = "is-enabled" ]; then',
                        "  echo enabled",
                        "  exit 0",
                        "fi",
                        "exit 1",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            fake_systemctl.chmod(fake_systemctl.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env['PATH']}"

            result = subprocess.run(
                ["bash", str(SERVICE_HEALTH)],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("name=readsb unit=readsb.service status=active", result.stdout)
            self.assertIn("name=gridrunner-web unit=gridrunner-web.service status=inactive", result.stdout)


if __name__ == "__main__":
    unittest.main()
