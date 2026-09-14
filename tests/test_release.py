#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "platform"))
from release import bind_latest, latest, pin_schema  # noqa: E402


class ReleaseHelperTests(unittest.TestCase):
    def test_latest_matches_latest_file(self):
        self.assertEqual(latest(), (ROOT / "LATEST").read_text().strip())

    def test_bind_latest_expands_example_tokens(self):
        release = latest()
        plan = bind_latest(
            json.loads(
                (ROOT / "fleet-template" / "setup-plan.json.example").read_text()
            )
        )
        request = bind_latest(
            json.loads(
                (
                    ROOT / "fleet-template" / "assistant-request.json.example"
                ).read_text()
            )
        )
        self.assertEqual(plan["release"], release)
        self.assertEqual(request["assistant"]["image_version"], release)

    def test_pinned_schema_rejects_other_release(self):
        release = latest()
        plan = bind_latest(
            json.loads(
                (ROOT / "fleet-template" / "setup-plan.json.example").read_text()
            )
        )
        schema = pin_schema(
            json.loads(
                (ROOT / "platform" / "schemas" / "setup-plan.schema.json").read_text()
            )
        )
        jsonschema.validate(plan, schema)
        plan["release"] = "v0.1.0-alpha.1"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(plan, schema)
        self.assertEqual(schema["properties"]["release"]["const"], release)

    def test_plan_tool_rejects_other_release(self):
        plan = bind_latest(
            json.loads(
                (ROOT / "fleet-template" / "setup-plan.json.example").read_text()
            )
        )
        plan["release"] = "v0.1.0-alpha.1"
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "setup-plan.json"
            path.write_text(json.dumps(plan))
            result = subprocess.run(
                ["python3", str(ROOT / "platform" / "setup" / "plan.py"), str(path)],
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(latest(), result.stderr)
