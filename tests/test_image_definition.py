#!/usr/bin/env python3
import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ImageDefinitionTests(unittest.TestCase):
    def test_uses_pinned_hermes_image_and_common_tools(self):
        dockerfile = (
            ROOT / "platform" / "container" / "Dockerfile"
        ).read_text()

        self.assertIn(
            "nousresearch/hermes-agent@sha256:"
            "9469b3e78b9545b6d576eb8887a95352"  # pragma: allowlist secret
            "e9a0ea83730eaf31431cf862ca1010e1",  # pragma: allowlist secret
            dockerfile,
        )
        self.assertNotIn("hermes-agent:latest", dockerfile)
        self.assertIn("opencode-ai@${OPENCODE_VERSION}", dockerfile)
        for tool in ["gh", "jq", "socat"]:
            self.assertIn(tool, dockerfile)
        self.assertIn("org.opencontainers.image.revision", dockerfile)
        self.assertIn("io.aidee.hermes.commit", dockerfile)
        self.assertIn("io.aidee.hermes.patch-sha256", dockerfile)
        self.assertIn("apply-hermes-runtime-patch.sh /opt/hermes", dockerfile)
        self.assertIn("hermes-plugins/aidee-onboarding", dockerfile)
        self.assertIn("/opt/hermes/plugins/aidee-onboarding", dockerfile)
        self.assertIn("dashboard-plugins/aidee-assistant-home", dockerfile)
        self.assertIn("/opt/hermes/plugins/aidee-assistant-home", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertNotIn("ENV HOME=", dockerfile)
        self.assertNotIn("ENV HERMES_HOME=", dockerfile)

    def test_hermes_patch_is_pinned_and_fail_closed(self):
        patch_sha = (ROOT / "platform/HERMES_PATCH_SHA256").read_text().strip()
        base_commit = (ROOT / "platform/HERMES_COMMIT").read_text().strip()
        patch_file = ROOT / "platform/hermes-runtime-context.patch"
        apply_script = (
            ROOT / "platform/scripts/apply-hermes-runtime-patch.sh"
        ).read_text()

        self.assertEqual(hashlib.sha256(patch_file.read_bytes()).hexdigest(), patch_sha)
        self.assertEqual(base_commit, "939e45c91d751fadd94dcd1b873ac3cb44846213")
        self.assertIn("Hermes runtime patch checksum mismatch", apply_script)
        self.assertIn("Hermes source files do not match audited base", apply_script)
        self.assertIn("Hermes patched file checksum mismatch", apply_script)
        self.assertIn('"--include=hermes_state_sessions.py"', apply_script)
        self.assertIn('if [[ "${1:-}" == "--check" ]]', apply_script)

        base_paths = {
            line.split(maxsplit=1)[1]
            for line in (
                ROOT / "platform/HERMES_BASE_FILES_SHA256"
            ).read_text().splitlines()
        }
        patched_paths = {
            line.split(maxsplit=1)[1]
            for line in (
                ROOT / "platform/HERMES_PATCHED_FILES_SHA256"
            ).read_text().splitlines()
        }
        expected = {
            "agent/conversation_loop.py",
            "agent/system_prompt.py",
            "gateway/run_agent_cache.py",
            "hermes_state_sessions.py",
        }
        self.assertEqual(base_paths, expected)
        self.assertEqual(patched_paths, expected)

    def test_image_records_are_root_owned_configuration(self):
        build_script = (
            ROOT / "platform" / "scripts" / "build-assistant-image.sh"
        ).read_text()
        admin_helper = (
            ROOT / "platform" / "admin" / "aidee_admin.py"
        ).read_text()

        self.assertIn('record_dir="/etc/aidee/images"', build_script)
        self.assertIn('temporary="${record}.tmp.$$"', build_script)
        self.assertIn('mv "${temporary}" "${record}"', build_script)
        self.assertIn('"/etc/aidee/images"', admin_helper)
        self.assertIn('"validated"', admin_helper)


if __name__ == "__main__":
    unittest.main()
