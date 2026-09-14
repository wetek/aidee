#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "platform" / "controller-tools" / "install-update-cron.py"


class UpdateCronTests(unittest.TestCase):
    def test_creates_one_approved_daily_job(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
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
  printf '%s\n' "Aidee daily update check" > "$AIDEE_TEST_JOBS"
  exit 0
fi
exit 1
"""
            )
            hermes.chmod(0o755)

            status_path = (
                directory
                / "fleet/controller/CONTROLLER_ONBOARDING_STATUS.json"
            )
            status_path.parent.mkdir(parents=True)
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
            environment = {
                **os.environ,
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "AIDEE_TEST_JOBS": str(jobs),
                "AIDEE_TEST_CALLS": str(calls),
                "AIDEE_STATE_DIR": str(directory),
            }

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
            self.assertEqual(
                json.loads(status_path.read_text())["steps"]["default_crons"]["status"],
                "pending",
            )
            create_calls = calls.read_text()
            self.assertEqual(create_calls.count("cron create"), 1)
            self.assertIn("every 24h", create_calls)
            self.assertIn("--deliver telegram", create_calls)
            self.assertIn("--continuity", create_calls)

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
