#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "platform" / "controller-tools"
ONBOARDING_CHECK = ROOT / "platform" / "setup" / "onboarding.py"


class OnboardingStatusTests(unittest.TestCase):
    def test_marks_owner_and_dashboard_verified(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            status_path = directory / "status.json"
            dashboard_path = directory / "dashboard-url"
            status_path.write_text(
                json.dumps(
                    {
                        "telegram_owner_authorized": False,
                        "telegram_profile_status": "pending",
                        "update_check_status": "pending",
                        "dashboard_verified": False,
                    }
                )
            )
            dashboard_path.write_text(
                "https://example.example-tailnet.ts.net\n"
            )

            commands = [
                [
                    "python3",
                    str(TOOLS / "mark-telegram-authorized.py"),
                    "--status-file",
                    str(status_path),
                    "--confirmed",
                ],
                [
                    "python3",
                    str(TOOLS / "mark-dashboard-verified.py"),
                    "--status-file",
                    str(status_path),
                    "--dashboard-url-file",
                    str(dashboard_path),
                    "--confirmed",
                ],
            ]
            for command in commands:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            status = json.loads(status_path.read_text())
            self.assertTrue(status["telegram_owner_authorized"])
            self.assertTrue(status["dashboard_verified"])
            self.assertEqual(status["telegram_profile_status"], "pending")

    def test_records_deferred_and_skipped_profile_choices(self):
        for profile_status in ("deferred", "skipped"):
            with self.subTest(profile_status=profile_status):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    status_path = Path(temporary_directory) / "status.json"
                    status_path.write_text(
                        json.dumps(
                            {
                                "telegram_owner_authorized": True,
                                "telegram_profile_status": "pending",
                                "update_check_status": "active",
                                "dashboard_verified": True,
                            }
                        )
                    )

                    result = subprocess.run(
                        [
                            "python3",
                            str(TOOLS / "set-telegram-profile-status.py"),
                            "--status-file",
                            str(status_path),
                            "--status",
                            profile_status,
                            "--confirmed",
                        ],
                        capture_output=True,
                        text=True,
                    )

                    self.assertEqual(result.returncode, 0, result.stderr)
                    status = json.loads(status_path.read_text())
                    self.assertEqual(
                        status["telegram_profile_status"],
                        profile_status,
                    )
                    complete = subprocess.run(
                        ["python3", str(ONBOARDING_CHECK), str(status_path)],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(complete.returncode, 0, complete.stderr)

    def test_pending_profile_choice_blocks_completion(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
            status_path.write_text(
                json.dumps(
                    {
                        "telegram_owner_authorized": True,
                        "telegram_profile_status": "pending",
                        "update_check_status": "active",
                        "dashboard_verified": True,
                    }
                )
            )

            result = subprocess.run(
                ["python3", str(ONBOARDING_CHECK), str(status_path)],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)

    def test_rejects_public_http_dashboard(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            status_path = directory / "status.json"
            dashboard_path = directory / "dashboard-url"
            status_path.write_text(json.dumps({"dashboard_verified": False}))
            dashboard_path.write_text("http://example.test\n")

            result = subprocess.run(
                [
                    "python3",
                    str(TOOLS / "mark-dashboard-verified.py"),
                    "--status-file",
                    str(status_path),
                    "--dashboard-url-file",
                    str(dashboard_path),
                    "--confirmed",
                ],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
