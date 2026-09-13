#!/usr/bin/env python3
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "platform" / "admin" / "aidee_admin.py"
SPEC = importlib.util.spec_from_file_location("aidee_admin", MODULE_PATH)
aidee_admin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(aidee_admin)


class AdminHelperTests(unittest.TestCase):
    def create_state(self, state_root):
        image_id = "sha256:" + "a" * 64
        image_dir = state_root / "runtime" / "images"
        image_dir.mkdir(parents=True)
        (image_dir / "v0.1.0-alpha.5.json").write_text(
            json.dumps(
                {
                    "aidee_version": "v0.1.0-alpha.5",
                    "image_id": image_id,
                    "source_commit": "testcommit",
                    "validation": "validated",
                }
            )
        )
        setup_dir = state_root / "setup"
        setup_dir.mkdir()
        (setup_dir / "setup-plan.json").write_text(
            json.dumps({"owner": {"name": "Example Owner"}})
        )
        (state_root / "owner.json").write_text(
            json.dumps({"name": "Example Owner"})
        )
        fleet_dir = state_root / "fleet"
        fleet_dir.mkdir()
        registry = {
            "schema_version": 1,
            "platform": {
                "repository": "https://example.com/aidee.git",
                "default_version": "0.1.0",
            },
            "controller": {
                "id": "aidee-controller",
                "state_path": "controller",
                "dashboard_hostname": None,
                "telegram_username": None,
            },
            "assistants": [],
        }
        (fleet_dir / "registry.yaml").write_text(
            yaml.safe_dump(registry, sort_keys=False)
        )
        return image_id

    def test_creates_fixed_isolated_container_commands(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_root = Path(temporary_directory)
            image_id = self.create_state(state_root)
            commands = []

            def fake_run(command):
                commands.append(command)
                if command[:3] == ["docker", "image", "inspect"]:
                    if "org.opencontainers.image.revision" in command[-1]:
                        return "testcommit"
                    return "v0.1.0-alpha.5"
                if command[:3] == ["git", "-C", str(ROOT)]:
                    return "testcommit"
                if command[:2] == ["docker", "ps"]:
                    return ""
                if command[:3] == ["tailscale", "status", "--json"]:
                    return json.dumps(
                        {"Self": {"DNSName": "pilot.example.ts.net."}}
                    )
                return ""

            def fake_directory(path, uid, gid, mode):
                path.mkdir(parents=True, exist_ok=True)
                path.chmod(mode)

            request = json.loads(
                (ROOT / "fleet-template" / "assistant-request.json.example").read_text()
            )

            with (
                mock.patch.object(aidee_admin, "STATE_ROOT", state_root),
                mock.patch.object(
                    aidee_admin,
                    "IMAGE_RECORD_ROOT",
                    state_root / "runtime" / "images",
                ),
                mock.patch.object(
                    aidee_admin,
                    "OWNER_RECORD",
                    state_root / "owner.json",
                ),
                mock.patch.object(aidee_admin, "SOURCE_ROOT", ROOT),
                mock.patch.object(
                    aidee_admin,
                    "controller_identity",
                    return_value=(os.getuid(), os.getgid()),
                ),
                mock.patch.object(aidee_admin, "run", side_effect=fake_run),
                mock.patch.object(aidee_admin, "validate_capacity_and_ports"),
                mock.patch.object(aidee_admin.os, "chown"),
                mock.patch.object(
                    aidee_admin,
                    "ensure_directory",
                    side_effect=fake_directory,
                ),
            ):
                result = aidee_admin.create_assistant(request)

            self.assertEqual(result["status"], "provisioning")
            self.assertEqual(result["image_id"], image_id)
            self.assertEqual(
                result["dashboard_url"],
                "https://pilot.example.ts.net:8443",
            )

            docker_create = [
                command
                for command in commands
                if command[:2] == ["docker", "create"]
            ]
            self.assertEqual(len(docker_create), 2)
            flattened = " ".join(" ".join(command) for command in docker_create)
            self.assertNotIn("--privileged", flattened)
            self.assertNotIn("/var/run/docker.sock", flattened)
            self.assertNotIn("--network host", flattened)
            self.assertIn("--read-only", flattened)
            self.assertIn("no-new-privileges:true", flattened)

            registry = yaml.safe_load(
                (state_root / "fleet" / "registry.yaml").read_text()
            )
            self.assertEqual(registry["assistants"][0]["id"], "personal")
            self.assertEqual(
                registry["assistants"][0]["image"]["image_id"],
                image_id,
            )

    def test_rejects_unapproved_request(self):
        request = json.loads(
            (ROOT / "fleet-template" / "assistant-request.json.example").read_text()
        )
        request["owner_approved"] = False
        with mock.patch.object(aidee_admin, "SOURCE_ROOT", ROOT):
            with self.assertRaises(aidee_admin.AdminError):
                aidee_admin.validate_request(request)


if __name__ == "__main__":
    unittest.main()
