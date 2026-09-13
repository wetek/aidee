#!/usr/bin/env python3
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "platform" / "controller-tools" / "draft-feedback-issue.py"


class DraftFeedbackIssueTests(unittest.TestCase):
    def run_tool(self, *arguments):
        return subprocess.run(
            ["python3", str(TOOL), *arguments],
            capture_output=True,
            text=True,
        )

    def test_prints_preview_and_submit_url(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            body = Path(temporary_directory) / "body.md"
            body.write_text(
                "Setup asked me to rerun after branding, but the status stayed pending.\n"
            )
            result = self.run_tool(
                "--title",
                "Onboarding status stays pending after branding",
                "--kind",
                "bug",
                "--body-file",
                str(body),
                "--host-release",
                "v0.1.0-alpha.5",
                "--knowledge-release",
                "v0.1.0-alpha.5",
                "--channel",
                "telegram",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.strip().splitlines()
        self.assertEqual(
            lines[0],
            "Onboarding status stays pending after branding",
        )
        composed = "\n".join(lines[1:-1])
        url = lines[-1]
        self.assertIn("Kind: bug", composed)
        self.assertIn("Host release: v0.1.0-alpha.5", composed)
        self.assertIn("Knowledge release: v0.1.0-alpha.5", composed)
        self.assertIn("Channel: telegram", composed)
        self.assertIn("status stayed pending", composed)
        parsed = urlparse(url)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "github.com")
        self.assertEqual(parsed.path, "/wetek/aidee/issues/new")
        query = parse_qs(parsed.query)
        self.assertEqual(
            query["title"],
            ["Onboarding status stays pending after branding"],
        )
        self.assertEqual(query["labels"], ["feedback"])
        self.assertIn("Kind: bug", query["body"][0])

    def test_rejects_secret_shaped_body(self):
        result = self.run_tool(
            "--title",
            "Bot token handling",
            "--kind",
            "bug",
            "--body",
            "The token is 123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("secret", result.stderr)

    def test_rejects_missing_body_source(self):
        result = self.run_tool("--title", "Missing body", "--kind", "docs")
        self.assertEqual(result.returncode, 1)
        self.assertIn("--body", result.stderr)
