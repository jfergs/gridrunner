from pathlib import Path
import os
import subprocess
import tempfile
import time
import unittest

import sys

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR / "web"))

import app
import config


class EventHealthTests(unittest.TestCase):
    def setUp(self):
        self.original_events_log = app.EVENTS_LOG
        self.original_stale_seconds = app.EVENTS_STALE_SECONDS

    def tearDown(self):
        app.EVENTS_LOG = self.original_events_log
        app.EVENTS_STALE_SECONDS = self.original_stale_seconds

    def test_event_freshness_reports_missing_log(self):
        app.EVENTS_LOG = Path("/tmp/gridrunner-missing-events.log")

        status = app.event_freshness()

        self.assertEqual(status["status"], "missing")

    def test_recent_events_reports_missing_without_tail_error(self):
        app.EVENTS_LOG = Path("/tmp/gridrunner-missing-events.log")

        output = app.recent_events()

        self.assertIn("events log missing:", output)
        self.assertNotIn("tail:", output)

    def test_resolve_events_log_prefers_operator_named_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_home = config.OPERATOR_HOME
            original_user = config.OPERATOR_USER
            original_env = os.environ.pop("GRIDRUNNER_EVENTS_LOG", None)
            try:
                config.OPERATOR_HOME = Path(temp_dir)
                config.OPERATOR_USER = "ghost"
                operator_log = config.OPERATOR_HOME / "ghost-events.log"
                operator_log.write_text("event\n", encoding="utf-8")

                self.assertEqual(config.resolve_events_log(), operator_log)
            finally:
                config.OPERATOR_HOME = original_home
                config.OPERATOR_USER = original_user
                if original_env is not None:
                    os.environ["GRIDRUNNER_EVENTS_LOG"] = original_env

    def test_event_freshness_reports_stale_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            events_log = Path(temp_dir) / "events.log"
            events_log.write_text("old event\n", encoding="utf-8")
            old_time = time.time() - 120
            os.utime(events_log, (old_time, old_time))
            app.EVENTS_LOG = events_log
            app.EVENTS_STALE_SECONDS = 60

            status = app.event_freshness()

            self.assertEqual(status["status"], "stale")
            self.assertGreaterEqual(status["age_seconds"], 60)

    def test_event_freshness_reports_fresh_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            events_log = Path(temp_dir) / "events.log"
            events_log.write_text("fresh event\n", encoding="utf-8")
            app.EVENTS_LOG = events_log
            app.EVENTS_STALE_SECONDS = 60

            status = app.event_freshness()

            self.assertEqual(status["status"], "fresh")

    def test_event_health_script_reports_stale(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            events_log = Path(temp_dir) / "events.log"
            events_log.write_text("old event\n", encoding="utf-8")
            old_time = time.time() - 120
            os.utime(events_log, (old_time, old_time))

            env = os.environ.copy()
            env.update(
                {
                    "GRIDRUNNER_EVENTS_LOG": str(events_log),
                    "GRIDRUNNER_EVENTS_STALE_SECONDS": "60",
                }
            )
            result = subprocess.run(
                ["bash", str(REPO_DIR / "scripts" / "event-health.sh")],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("status=stale", result.stdout)

    def test_event_health_script_uses_operator_named_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            events_log = Path(temp_dir) / "ghost-events.log"
            events_log.write_text("fresh event\n", encoding="utf-8")

            env = os.environ.copy()
            env.pop("GRIDRUNNER_EVENTS_LOG", None)
            env.update(
                {
                    "GRIDRUNNER_OPERATOR_USER": "ghost",
                    "GRIDRUNNER_OPERATOR_HOME": temp_dir,
                    "GRIDRUNNER_EVENTS_STALE_SECONDS": "86400",
                }
            )
            result = subprocess.run(
                ["bash", str(REPO_DIR / "scripts" / "event-health.sh")],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("status=fresh", result.stdout)


if __name__ == "__main__":
    unittest.main()
