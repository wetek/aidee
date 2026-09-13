#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SYNC_TOOL = ROOT / "platform" / "controller-tools" / "sync-fleet-assistants.py"


class SyncFleetAssistantsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_root = Path(self.temp_dir.name)
        self.fleet_dir = self.state_root / "fleet"
        self.runtime_dir = self.state_root / "runtime"
        self.fleet_dir.mkdir(parents=True)
        self.runtime_dir.mkdir(parents=True)

        self.owner_record = self.state_root / "owner.json"
        self.owner_record.write_text(json.dumps({"name": "Test Owner"}))

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_sync(self, *args, env=None):
        cmd = [
            sys.executable,
            str(SYNC_TOOL),
            "--state-root",
            str(self.state_root),
            "--owner-record",
            str(self.owner_record),
            *args,
        ]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env={**os.environ, **(env or {})},
        )

    def test_requires_approval_or_dry_run(self):
        result = self.run_sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("owner approval is required", result.stderr)

    def test_missing_registry_graceful_exit(self):
        non_existent = self.state_root / "nonexistent-registry.yaml"
        result = self.run_sync(
            "--registry", str(non_existent), "--approved"
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Fleet registry not found", result.stderr)

    def test_empty_registry(self):
        registry_path = self.fleet_dir / "registry.yaml"
        registry_path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "platform": {
                        "repository": "https://example.com/aidee.git",
                        "default_version": "0.1.0",
                    },
                    "controller": {
                        "id": "aidee-controller",
                        "state_path": "controller",
                    },
                    "assistants": [],
                }
            )
        )
        result = self.run_sync("--approved")
        self.assertEqual(result.returncode, 0)
        self.assertIn("No assistants found", result.stdout)

    def test_dry_run_does_not_modify_files(self):
        asst_fleet = self.fleet_dir / "assistants" / "pilot"
        asst_runtime = self.runtime_dir / "assistants" / "pilot" / "data"
        asst_fleet.mkdir(parents=True)
        asst_runtime.mkdir(parents=True)

        fleet_soul = asst_fleet / "SOUL.md"
        runtime_soul = asst_runtime / "SOUL.md"
        old_content = "# Old Soul\n"
        fleet_soul.write_text(old_content)
        runtime_soul.write_text(old_content)

        registry_path = self.fleet_dir / "registry.yaml"
        registry_path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "assistants": [
                        {
                            "id": "pilot",
                            "name": "Pilot",
                            "kind": "personal",
                            "state_path": "assistants/pilot",
                        }
                    ],
                }
            )
        )

        result = self.run_sync("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[dry-run] Would update SOUL.md", result.stdout)
        self.assertEqual(fleet_soul.read_text(), old_content)
        self.assertEqual(runtime_soul.read_text(), old_content)

    def test_sync_personal_and_coding_assistants(self):
        # Setup personal assistant
        personal_fleet = self.fleet_dir / "assistants" / "personal"
        personal_runtime = (
            self.runtime_dir / "assistants" / "personal" / "data"
        )
        personal_fleet.mkdir(parents=True)
        personal_runtime.mkdir(parents=True)
        (personal_fleet / "assistant.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "assistant": {
                        "id": "personal",
                        "name": "Personal Assistant",
                        "kind": "personal",
                        "purpose": "Help with personal daily workflows.",
                    },
                }
            )
        )

        # Setup coding assistant
        coding_fleet = self.fleet_dir / "assistants" / "dev"
        coding_runtime = self.runtime_dir / "assistants" / "dev" / "data"
        coding_fleet.mkdir(parents=True)
        coding_runtime.mkdir(parents=True)
        (coding_fleet / "assistant.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "assistant": {
                        "id": "dev",
                        "name": "Dev Agent",
                        "kind": "coding",
                        "purpose": "Execute software development tasks.",
                    },
                }
            )
        )

        registry_path = self.fleet_dir / "registry.yaml"
        registry_path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "assistants": [
                        {
                            "id": "personal",
                            "name": "Personal Assistant",
                            "kind": "personal",
                            "state_path": "assistants/personal",
                        },
                        {
                            "id": "dev",
                            "name": "Dev Agent",
                            "kind": "coding",
                            "state_path": "assistants/dev",
                        },
                    ],
                }
            )
        )

        result = self.run_sync("--approved")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Synced 2 assistant(s) successfully", result.stdout)

        # Verify Personal SOUL.md
        p_fleet_soul = (personal_fleet / "SOUL.md").read_text()
        p_runtime_soul = (personal_runtime / "SOUL.md").read_text()
        self.assertEqual(p_fleet_soul, p_runtime_soul)
        self.assertIn("# Personal Assistant", p_fleet_soul)
        self.assertIn("Test Owner", p_fleet_soul)
        self.assertIn("Purpose: Help with personal daily workflows.", p_fleet_soul)
        self.assertIn("Communication Standards (Unslop)", p_fleet_soul)
        self.assertIn("120 words or fewer", p_fleet_soul)
        self.assertIn("Interactive Telegram Choices", p_fleet_soul)
        self.assertIn(
            "interactive clarify tool with clickable options", p_fleet_soul
        )
        self.assertNotIn("Software Engineering Standards", p_fleet_soul)

        # Verify Coding SOUL.md
        c_fleet_soul = (coding_fleet / "SOUL.md").read_text()
        c_runtime_soul = (coding_runtime / "SOUL.md").read_text()
        self.assertEqual(c_fleet_soul, c_runtime_soul)
        self.assertIn("# Dev Agent", c_fleet_soul)
        self.assertIn("Test Owner", c_fleet_soul)
        self.assertIn(
            "Purpose: Execute software development tasks.", c_fleet_soul
        )
        self.assertIn("Communication Standards (Unslop)", c_fleet_soul)
        self.assertIn("Interactive Telegram Choices", c_fleet_soul)
        self.assertIn("Software Engineering Standards", c_fleet_soul)
        self.assertIn("Test-driven verification", c_fleet_soul)
        self.assertIn("Systematic debugging (`diagnosing-bugs`)", c_fleet_soul)
        self.assertIn(
            "Requirements interrogation (`grill-me`, `grill-with-docs`, `grilling`, `to-spec`)",
            c_fleet_soul,
        )
        self.assertIn(
            "Architecture & domain design (`codebase-design`, `domain-modeling`)",
            c_fleet_soul,
        )
        self.assertIn("Pre-commit code review (`code-review`)", c_fleet_soul)
        self.assertIn("Clean documentation & handoff (`handoff`)", c_fleet_soul)

        # Verify shared skills copied to runtime
        for r_dir in (personal_runtime, coding_runtime):
            skills_dir = r_dir / "skills"
            self.assertTrue(skills_dir.is_dir())
            for skill_name in [
                "code-review",
                "codebase-design",
                "diagnosing-bugs",
                "domain-modeling",
                "grill-me",
                "grill-with-docs",
                "grilling",
                "handoff",
                "to-spec",
                "unslop",
            ]:
                skill_file = skills_dir / skill_name / "SKILL.md"
                self.assertTrue(
                    skill_file.is_file(),
                    f"Missing skill file: {skill_file}",
                )
                self.assertGreater(len(skill_file.read_text()), 0)


if __name__ == "__main__":
    unittest.main()
