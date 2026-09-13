#!/usr/bin/env python3
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
        self.assertIn("HEALTHCHECK", dockerfile)

    def test_image_records_are_root_owned_configuration(self):
        build_script = (
            ROOT / "platform" / "scripts" / "build-assistant-image.sh"
        ).read_text()
        admin_helper = (
            ROOT / "platform" / "admin" / "aidee_admin.py"
        ).read_text()

        self.assertIn('record_dir="/etc/aidee/images"', build_script)
        self.assertIn('"/etc/aidee/images"', admin_helper)
        self.assertIn('"validated"', admin_helper)


if __name__ == "__main__":
    unittest.main()
