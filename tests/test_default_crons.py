#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "platform" / "controller-tools" / "install-default-crons.py"


class DefaultCronsTests(unittest.TestCase):
    def setUpHermes(self, directory):
        bin_dir = directory / "bin"
        bin_dir.mkdir()
        jobs = directory / "jobs"
        calls = directory / "calls"
        hermes = bin_dir / "hermes"
        hermes.write_text(
            r"""#!/usr/bin/env bash
set -e
if [[ "$1" == "cron" && "$2" == "list" ]]; then
  [[ -f "$AIDEE_TEST_JOBS" ]] && cat "$AIDEE_TEST_JOBS"
  exit 0
fi
if [[ "$1" == "cron" && "$2" == "create" ]]; then
  printf '%s\n' "$*" >> "$AIDEE_TEST_CALLS"
  shift 2
  while (( $# > 0 )); do
    if [[ "$1" == "--name" ]]; then
      printf '%s\n' "$2" >> "$AIDEE_TEST_JOBS"
      break
    fi
    shift
  done
  exit 0
fi
exit 1
"""
        )
        hermes.chmod(0o755)
        return {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "AIDEE_TEST_JOBS": str(jobs),
            "AIDEE_TEST_CALLS": str(calls),
        }, calls

    def test_creates_both_default_crons_when_approved(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            environment, calls = self.setUpHermes(directory)
            status_path = directory / "status.json"
            status_path.write_text(
                json.dumps(
                    {
                        "telegram_owner_authorized": True,
                        "telegram_profile_status": "deferred",
                        "update_check_status": "pending",
                        "dashboard_verified": True,
                    }
                )
            )

            command = [
                "python3",
                str(TOOL),
                "--status-file",
                str(status_path),
                "--approved",
            ]
            first = subprocess.run(
                command,
                env=environment,
                capture_output=True,
                text=True,
            )
            second = subprocess.run(
                command,
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)

            status = json.loads(status_path.read_text())
            self.assertEqual(status["update_check_status"], "active")
            self.assertEqual(status["health_watchdog_status"], "active")

            create_calls = calls.read_text()
            self.assertEqual(create_calls.count("cron create"), 2)
            self.assertIn("every 24h", create_calls)
            self.assertIn("every 6h", create_calls)
            self.assertIn("--name Aidee daily update check", create_calls)
            self.assertIn("--name Aidee fleet health watchdog", create_calls)
            self.assertIn("--deliver telegram", create_calls)
            self.assertIn("--continuity", create_calls)

    def test_skips_update_check_when_requested(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            environment, calls = self.setUpHermes(directory)
            status_path = directory / "status.json"
            status_path.write_text(
                json.dumps(
                    {
                        "telegram_owner_authorized": True,
                        "telegram_profile_status": "deferred",
                        "update_check_status": "disabled",
                        "dashboard_verified": True,
                    }
                )
            )

            command = [
                "python3",
                str(TOOL),
                "--status-file",
                str(status_path),
                "--skip-update-check",
                "--approved",
            ]
            result = subprocess.run(
                command,
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            status = json.loads(status_path.read_text())
            self.assertEqual(status["update_check_status"], "disabled")
            self.assertEqual(status["health_watchdog_status"], "active")

            create_calls = calls.read_text()
            self.assertEqual(create_calls.count("cron create"), 1)
            self.assertNotIn("every 24h", create_calls)
            self.assertIn("every 6h", create_calls)
            self.assertIn("--name Aidee fleet health watchdog", create_calls)

    def test_requires_owner_approval(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
            status_path.write_text("{}")
            result = subprocess.run(
                [
                    "python3",
                    str(TOOL),
                    "--status-file",
                    str(status_path),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
