#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform/setup/onboarding-report.py"
sys.path.insert(0, str(ROOT / "platform/setup"))
from onboarding_state import default_status  # noqa: E402


class OnboardingReportTests(unittest.TestCase):
    def prepare(self, root):
        controller = root / "fleet/controller"
        controller.mkdir(parents=True)
        controller_status = default_status("controller")
        controller_status["steps"]["identity_skin"]["note"] = "private note"
        (controller / "CONTROLLER_ONBOARDING_STATUS.json").write_text(
            json.dumps(controller_status)
        )

        assistant_root = root / "runtime/assistants/pilot/data/aidee"
        assistant_root.mkdir(parents=True)
        assistant_status = default_status("assistant", "personal")
        assistant_status["steps"]["identity"]["note"] = "sensitive evidence"
        (assistant_root / "onboarding-status.json").write_text(
            json.dumps(assistant_status)
        )
        (root / "fleet/registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "assistants": [
                        {
                            "id": "pilot",
                            "onboarding": {
                                "status_path": "aidee/onboarding-status.json"
                            },
                        }
                    ]
                }
            )
        )

    def test_report_contains_counts_but_no_notes_or_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare(root)
            result = subprocess.run(
                [sys.executable, str(REPORT), "--state-root", str(root)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("private note", result.stdout)
            self.assertNotIn("sensitive evidence", result.stdout)
            report = json.loads(result.stdout)
            self.assertIn(
                "required_remaining", report["assistants"][0]["rollup"]
            )

    def test_report_rejects_symlinked_assistant_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare(root)
            status = (
                root
                / "runtime/assistants/pilot/data/aidee/onboarding-status.json"
            )
            outside = root / "outside.json"
            outside.write_text(json.dumps(default_status("assistant", "personal")))
            status.unlink()
            status.symlink_to(outside)
            result = subprocess.run(
                [sys.executable, str(REPORT), "--state-root", str(root)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlink", result.stderr)


if __name__ == "__main__":
    unittest.main()
