#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "platform" / "controller-tools"


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
                        "telegram_profile_applied": False,
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
            self.assertFalse(status["telegram_profile_applied"])

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
