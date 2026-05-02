from pathlib import Path
import os
import stat
import subprocess
import tempfile
import textwrap
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT = REPO_DIR / "scripts" / "wifi-fallback.sh"


class WifiFallbackTests(unittest.TestCase):
    def run_with_fake_nmcli(self, nmcli_script, env=None):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fake_bin = temp_path / "bin"
            fake_bin.mkdir()
            nmcli = fake_bin / "nmcli"
            calls = temp_path / "nmcli-calls.log"
            log = temp_path / "events.log"
            nmcli.write_text(nmcli_script, encoding="utf-8")
            nmcli.chmod(nmcli.stat().st_mode | stat.S_IXUSR)

            run_env = os.environ.copy()
            run_env.update(
                {
                    "PATH": f"{fake_bin}:{run_env['PATH']}",
                    "LOG": str(log),
                    "SCAN_SETTLE_SECONDS": "0",
                    "NMCLI_CALLS": str(calls),
                    "GRIDRUNNER_WIFI_RESCAN_STATE": str(temp_path / "wifi-rescan.last"),
                    "GRIDRUNNER_WIFI_ACTION_STATE": str(temp_path / "wifi-action.env"),
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
            log_output = log.read_text(encoding="utf-8") if log.exists() else ""
            return result, calls_output, log_output

    def test_default_hotspot_profile_is_gridrunner(self):
        nmcli_script = textwrap.dedent(
            """\
            #!/bin/bash
            echo "$*" >> "$NMCLI_CALLS"
            if [ "$*" = "-t -f RUNNING general" ]; then
              echo running
            elif [ "$*" = "-t -f WIFI general" ]; then
              echo enabled
            elif [ "$*" = "-t -f NAME,DEVICE connection show --active" ]; then
              exit 0
            elif [ "$*" = "-t -f NAME,TYPE connection show" ]; then
              exit 0
            elif [ "$*" = "-t -f NAME connection show" ]; then
              exit 0
            elif [ "$*" = "dev wifi list ifname wlan0" ]; then
              exit 0
            elif [ "$1 $2 $3" = "connection add type" ]; then
              exit 0
            elif [ "$1 $2" = "connection down" ]; then
              exit 0
            elif [ "$1 $2 $3" = "connection up GRIDRUNNER-HOTSPOT" ]; then
              exit 0
            fi
            exit 0
            """
        )

        result, calls, _log = self.run_with_fake_nmcli(
            nmcli_script,
            {"HOTSPOT_PASSWORD": "password123"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("con-name GRIDRUNNER-HOTSPOT", calls)
        self.assertIn("connection up GRIDRUNNER-HOTSPOT", calls)

    def test_legacy_hotspot_profile_is_reused_and_not_treated_as_known_wifi(self):
        nmcli_script = textwrap.dedent(
            """\
            #!/bin/bash
            echo "$*" >> "$NMCLI_CALLS"
            if [ "$*" = "-t -f RUNNING general" ]; then
              echo running
            elif [ "$*" = "-t -f WIFI general" ]; then
              echo enabled
            elif [ "$*" = "-t -f NAME,DEVICE connection show --active" ]; then
              exit 0
            elif [ "$*" = "-t -f NAME,TYPE connection show" ]; then
              echo "Gridrunner-hotspot:802-11-wireless"
              echo "HomeWiFi:802-11-wireless"
            elif [ "$*" = "-t -f NAME connection show" ]; then
              echo "Gridrunner-hotspot"
              echo "HomeWiFi"
            elif [ "$*" = "dev wifi list ifname wlan0" ]; then
              exit 0
            elif [ "$1 $2 $3" = "connection modify Gridrunner-hotspot" ]; then
              exit 0
            elif [ "$1 $2" = "connection down" ]; then
              exit 0
            elif [ "$1 $2 $3" = "connection up Gridrunner-hotspot" ]; then
              exit 0
            fi
            exit 0
            """
        )

        result, calls, _log = self.run_with_fake_nmcli(nmcli_script)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("connection modify Gridrunner-hotspot", calls)
        self.assertIn("connection up Gridrunner-hotspot", calls)
        self.assertNotIn("connection up HomeWiFi", calls)

    def test_reads_persisted_hotspot_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "wifi-fallback.env"
            config_file.write_text(
                "\n".join(
                    [
                        "HOTSPOT='GRIDRUNNER-HOTSPOT'",
                        "HOTSPOT_SSID='Field Runner'",
                        "HOTSPOT_PASSWORD='password123'",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            nmcli_script = textwrap.dedent(
                """\
                #!/bin/bash
                echo "$*" >> "$NMCLI_CALLS"
                if [ "$*" = "-t -f RUNNING general" ]; then
                  echo running
                elif [ "$*" = "-t -f WIFI general" ]; then
                  echo enabled
                elif [ "$*" = "-t -f NAME,DEVICE connection show --active" ]; then
                  exit 0
                elif [ "$*" = "-t -f NAME,TYPE connection show" ]; then
                  exit 0
                elif [ "$*" = "-t -f NAME connection show" ]; then
                  exit 0
                elif [ "$*" = "dev wifi list ifname wlan0" ]; then
                  exit 0
                elif [ "$1 $2 $3" = "connection add type" ]; then
                  exit 0
                elif [ "$1 $2" = "connection down" ]; then
                  exit 0
                elif [ "$1 $2 $3" = "connection up GRIDRUNNER-HOTSPOT" ]; then
                  exit 0
                fi
                exit 0
                """
            )

            result, calls, _log = self.run_with_fake_nmcli(
                nmcli_script,
                {"GRIDRUNNER_WIFI_CONFIG": str(config_file)},
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ssid Field Runner", calls)
            self.assertIn("wifi-sec.psk password123", calls)

    def test_active_known_wifi_with_full_connectivity_exits_without_rescan(self):
        nmcli_script = textwrap.dedent(
            """\
            #!/bin/bash
            echo "$*" >> "$NMCLI_CALLS"
            if [ "$*" = "-t -f RUNNING general" ]; then
              echo running
            elif [ "$*" = "-t -f WIFI general" ]; then
              echo enabled
            elif [ "$*" = "-t -f NAME,DEVICE connection show --active" ]; then
              echo "HomeWiFi:wlan0"
            elif [ "$*" = "-g 802-11-wireless.ssid connection show HomeWiFi" ]; then
              echo "HomeWiFi"
            elif [ "$*" = "-t -f CONNECTIVITY general" ]; then
              echo full
            elif [ "$*" = "dev wifi rescan ifname wlan0" ]; then
              exit 1
            fi
            exit 0
            """
        )

        result, calls, _log = self.run_with_fake_nmcli(nmcli_script)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("dev wifi rescan ifname wlan0", calls)
        self.assertNotIn("connection up GRIDRUNNER-HOTSPOT", calls)

    def test_active_known_wifi_exits_when_ssid_has_signal_after_rescan(self):
        nmcli_script = textwrap.dedent(
            """\
            #!/bin/bash
            echo "$*" >> "$NMCLI_CALLS"
            if [ "$*" = "-t -f RUNNING general" ]; then
              echo running
            elif [ "$*" = "-t -f WIFI general" ]; then
              echo enabled
            elif [ "$*" = "-t -f NAME,DEVICE connection show --active" ]; then
              echo "HomeWiFi:wlan0"
            elif [ "$*" = "-g 802-11-wireless.ssid connection show HomeWiFi" ]; then
              echo "HomeWiFi"
            elif [ "$*" = "-t -f CONNECTIVITY general" ]; then
              echo none
            elif [ "$*" = "-t -f SSID dev wifi list ifname wlan0" ]; then
              echo "HomeWiFi"
            elif [ "$*" = "-t -f SSID,SIGNAL dev wifi list ifname wlan0" ]; then
              echo "HomeWiFi:70"
            elif [ "$*" = "dev wifi rescan ifname wlan0" ]; then
              exit 0
            fi
            exit 0
            """
        )

        result, calls, _log = self.run_with_fake_nmcli(nmcli_script)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dev wifi rescan ifname wlan0", calls)
        self.assertNotIn("connection up GRIDRUNNER-HOTSPOT", calls)

    def test_stale_active_known_wifi_falls_back_to_hotspot(self):
        nmcli_script = textwrap.dedent(
            """\
            #!/bin/bash
            echo "$*" >> "$NMCLI_CALLS"
            if [ "$*" = "-t -f RUNNING general" ]; then
              echo running
            elif [ "$*" = "-t -f WIFI general" ]; then
              echo enabled
            elif [ "$*" = "-t -f NAME,DEVICE connection show --active" ]; then
              echo "HomeWiFi:wlan0"
            elif [ "$*" = "-g 802-11-wireless.ssid connection show HomeWiFi" ]; then
              echo "HomeWiFi"
            elif [ "$*" = "-t -f SSID dev wifi list ifname wlan0" ]; then
              exit 0
            elif [ "$*" = "-t -f SSID,SIGNAL dev wifi list ifname wlan0" ]; then
              echo "HomeWiFi:0"
            elif [ "$*" = "-t -f CONNECTIVITY general" ]; then
              echo none
            elif [ "$*" = "-t -f NAME,TYPE connection show" ]; then
              echo "HomeWiFi:802-11-wireless"
            elif [ "$*" = "-t -f NAME connection show" ]; then
              exit 0
            elif [ "$*" = "dev wifi rescan ifname wlan0" ]; then
              exit 0
            elif [ "$1 $2" = "connection down" ]; then
              exit 0
            elif [ "$1 $2 $3" = "connection add type" ]; then
              exit 0
            elif [ "$1 $2 $3" = "connection up GRIDRUNNER-HOTSPOT" ]; then
              exit 0
            fi
            exit 0
            """
        )

        result, calls, log = self.run_with_fake_nmcli(
            nmcli_script,
            {"HOTSPOT_PASSWORD": "password123"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("connection down HomeWiFi", calls)
        self.assertIn("connection up GRIDRUNNER-HOTSPOT", calls)
        self.assertIn("known wifi connection appears stale", log)

    def test_limited_connectivity_with_low_signal_falls_back_to_hotspot(self):
        nmcli_script = textwrap.dedent(
            """\
            #!/bin/bash
            echo "$*" >> "$NMCLI_CALLS"
            if [ "$*" = "-t -f RUNNING general" ]; then
              echo running
            elif [ "$*" = "-t -f WIFI general" ]; then
              echo enabled
            elif [ "$*" = "-t -f NAME,DEVICE connection show --active" ]; then
              echo "HomeWiFi:wlan0"
            elif [ "$*" = "-g 802-11-wireless.ssid connection show HomeWiFi" ]; then
              echo "HomeWiFi"
            elif [ "$*" = "-t -f CONNECTIVITY general" ]; then
              echo limited
            elif [ "$*" = "-t -f SSID,SIGNAL dev wifi list ifname wlan0" ]; then
              echo "HomeWiFi:5"
            elif [ "$*" = "-t -f NAME,TYPE connection show" ]; then
              echo "HomeWiFi:802-11-wireless"
            elif [ "$*" = "-t -f NAME connection show" ]; then
              exit 0
            elif [ "$*" = "dev wifi rescan ifname wlan0" ]; then
              exit 0
            elif [ "$1 $2" = "connection down" ]; then
              exit 0
            elif [ "$1 $2 $3" = "connection add type" ]; then
              exit 0
            elif [ "$1 $2 $3" = "connection up GRIDRUNNER-HOTSPOT" ]; then
              exit 0
            fi
            exit 0
            """
        )

        result, calls, log = self.run_with_fake_nmcli(
            nmcli_script,
            {"HOTSPOT_PASSWORD": "password123"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dev wifi rescan ifname wlan0", calls)
        self.assertIn("connection down HomeWiFi", calls)
        self.assertIn("connection up GRIDRUNNER-HOTSPOT", calls)
        self.assertIn("known wifi connection appears stale", log)

    def test_recent_rescan_guard_still_falls_back_when_cached_signal_is_missing(self):
        nmcli_script = textwrap.dedent(
            """\
            #!/bin/bash
            echo "$*" >> "$NMCLI_CALLS"
            if [ "$*" = "-t -f RUNNING general" ]; then
              echo running
            elif [ "$*" = "-t -f WIFI general" ]; then
              echo enabled
            elif [ "$*" = "-t -f NAME,DEVICE connection show --active" ]; then
              echo "HomeWiFi:wlan0"
            elif [ "$*" = "-g 802-11-wireless.ssid connection show HomeWiFi" ]; then
              echo "HomeWiFi"
            elif [ "$*" = "-t -f CONNECTIVITY general" ]; then
              echo limited
            elif [ "$*" = "-t -f SSID,SIGNAL dev wifi list ifname wlan0" ]; then
              exit 0
            elif [ "$*" = "-t -f NAME,TYPE connection show" ]; then
              echo "HomeWiFi:802-11-wireless"
            elif [ "$*" = "-t -f NAME connection show" ]; then
              exit 0
            elif [ "$*" = "dev wifi rescan ifname wlan0" ]; then
              exit 1
            elif [ "$1 $2" = "connection down" ]; then
              exit 0
            elif [ "$1 $2 $3" = "connection add type" ]; then
              exit 0
            elif [ "$1 $2 $3" = "connection up GRIDRUNNER-HOTSPOT" ]; then
              exit 0
            fi
            exit 0
            """
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "wifi-rescan.last"
            state_file.write_text("9999999999\n", encoding="utf-8")

            result, calls, _log = self.run_with_fake_nmcli(
                nmcli_script,
                {
                    "HOTSPOT_PASSWORD": "password123",
                    "GRIDRUNNER_WIFI_RESCAN_MIN_SECONDS": "3600",
                    "GRIDRUNNER_WIFI_RESCAN_STATE": str(state_file),
                },
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("dev wifi rescan ifname wlan0", calls)
        self.assertIn("connection down HomeWiFi", calls)
        self.assertIn("connection up GRIDRUNNER-HOTSPOT", calls)


if __name__ == "__main__":
    unittest.main()
