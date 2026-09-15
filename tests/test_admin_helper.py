#!/usr/bin/env python3
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "platform"))
from release import bind_latest, latest  # noqa: E402

RELEASE = latest()
MODULE_PATH = ROOT / "platform" / "admin" / "aidee_admin.py"
SPEC = importlib.util.spec_from_file_location("aidee_admin", MODULE_PATH)
aidee_admin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(aidee_admin)


class AdminHelperTests(unittest.TestCase):
    def create_state(self, state_root):
        image_id = "sha256:" + "a" * 64
        image_dir = state_root / "runtime" / "images"
        image_dir.mkdir(parents=True)
        (image_dir / f"{RELEASE}.json").write_text(
            json.dumps(
                {
                    "aidee_version": RELEASE,
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
                    return RELEASE
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

            request = bind_latest(
                json.loads(
                    (
                        ROOT / "fleet-template" / "assistant-request.json.example"
                    ).read_text()
                )
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
            self.assertEqual(result["dashboard_username"], "aidee")
            self.assertNotIn("dashboard_password", result)
            self.assertIn("Fleet page", result["next_action"])
            self.assertIn(
                "show-assistant-dashboard-password.sh personal",
                result["dashboard_password_command"],
            )
            self.assertTrue(
                (
                    state_root
                    / "secrets"
                    / "assistants"
                    / "personal"
                    / "dashboard-initial-password"
                ).is_file()
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
            self.assertNotIn("--env HOME=", flattened)
            self.assertNotIn("--env HERMES_HOME=", flattened)
            proxy_create = next(
                command
                for command in docker_create
                if f"container:aidee-{request['assistant']['id']}" in command
            )
            entrypoint_index = proxy_create.index("--entrypoint")
            self.assertEqual(
                proxy_create[entrypoint_index : entrypoint_index + 3],
                ["--entrypoint", "socat", image_id],
            )
            self.assertEqual(
                proxy_create[entrypoint_index + 3 :],
                [
                    "TCP-LISTEN:9121,fork,reuseaddr",
                    "TCP:127.0.0.1:9119",
                ],
            )

            registry = yaml.safe_load(
                (state_root / "fleet" / "registry.yaml").read_text()
            )
            self.assertEqual(registry["assistants"][0]["id"], "personal")
            self.assertEqual(
                registry["assistants"][0]["image"]["image_id"],
                image_id,
            )

            config_data = yaml.safe_load(
                (
                    state_root
                    / "runtime"
                    / "assistants"
                    / "personal"
                    / "data"
                    / "config.yaml"
                ).read_text()
            )
            self.assertEqual(config_data.get("display", {}).get("skin"), "personal")
            self.assertEqual(
                config_data.get("dashboard", {}).get("public_url"),
                "https://pilot.example.ts.net:8443",
            )
            self.assertTrue(
                config_data.get("platforms", {}).get("telegram", {}).get("enabled")
            )
            runtime_memories = (
                state_root
                / "runtime"
                / "assistants"
                / "personal"
                / "data"
                / "memories"
            )
            self.assertTrue(runtime_memories.is_dir())
            self.assertEqual(
                (runtime_memories / "USER.md").read_text(),
                "# User\n\nExample Owner owns and directs this assistant.\n",
            )
            self.assertEqual(
                (runtime_memories / "MEMORY.md").read_text(),
                "# Memory\n",
            )
            runtime_repos = (
                state_root
                / "runtime"
                / "assistants"
                / "personal"
                / "data"
                / "aidee"
                / "repos"
            )
            self.assertTrue(runtime_repos.is_dir())
            runtime_soul = (
                state_root
                / "runtime"
                / "assistants"
                / "personal"
                / "data"
                / "SOUL.md"
            )
            self.assertTrue(runtime_soul.is_file())
            fleet_soul = (
                state_root
                / "fleet"
                / "assistants"
                / "personal"
                / "SOUL.md"
            )
            self.assertTrue(fleet_soul.is_file())
            soul_text = runtime_soul.read_text()
            self.assertEqual(soul_text, fleet_soul.read_text())
            self.assertIn("# Personal", soul_text)
            self.assertIn("Communication standards", soul_text)
            self.assertIn("including greetings", soul_text)
            self.assertIn("120 words or fewer", soul_text)
            self.assertIn("On Telegram, present choices", soul_text)
            self.assertIn("interactive clarify tool with clickable options", soul_text)
            self.assertIn(
                "Store every coding-task repository under /opt/data/aidee/repos.",
                soul_text,
            )
            self.assertNotIn("Software engineering standards", soul_text)
            self.assertNotIn("memories:/opt/data/memories", flattened)
            skin_path = (
                state_root
                / "runtime"
                / "assistants"
                / "personal"
                / "data"
                / "skins"
                / "personal.yaml"
            )
            self.assertTrue(skin_path.is_file())
            skin_data = yaml.safe_load(skin_path.read_text())
            self.assertEqual(skin_data["branding"]["agent_name"], "Personal")
            self.assertEqual(
                skin_data["branding"]["response_label"],
                " ⚕ Personal ",
            )
            env_text = (
                state_root
                / "runtime"
                / "assistants"
                / "personal"
                / "data"
                / ".env"
            ).read_text()
            self.assertIn("HERMES_DASHBOARD_BASIC_AUTH_USERNAME=aidee", env_text)
            self.assertIn(
                "HERMES_DASHBOARD_BASIC_AUTH_TTL_SECONDS=2592000",
                env_text,
            )

    def test_create_assistant_inherits_controller_credentials(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_root = Path(temporary_directory)
            image_id = self.create_state(state_root)
            controller_hermes = state_root / "controller-home" / ".hermes"
            controller_hermes.mkdir(parents=True)
            (controller_hermes / ".env").write_text(
                "HERMES_DASHBOARD_BASIC_AUTH_USERNAME=mehdi\n"
                "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH=scrypt$test$hash\n"
                "HERMES_DASHBOARD_BASIC_AUTH_SECRET=fixedsecret123\n"
            )

            def fake_run(command):
                if command[:3] == ["docker", "image", "inspect"]:
                    if "org.opencontainers.image.revision" in command[-1]:
                        return "testcommit"
                    return RELEASE
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

            request = bind_latest(
                json.loads(
                    (
                        ROOT / "fleet-template" / "assistant-request.json.example"
                    ).read_text()
                )
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
            self.assertEqual(result["dashboard_username"], "mehdi")
            self.assertIn("controller dashboard credentials", result["next_action"])

            env_text = (
                state_root
                / "runtime"
                / "assistants"
                / "personal"
                / "data"
                / ".env"
            ).read_text()
            self.assertIn("HERMES_DASHBOARD_BASIC_AUTH_USERNAME=mehdi", env_text)
            self.assertIn(
                "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH=scrypt$test$hash",
                env_text,
            )
            self.assertIn(
                "HERMES_DASHBOARD_BASIC_AUTH_SECRET=fixedsecret123",
                env_text,
            )
            self.assertIn(
                "HERMES_DASHBOARD_BASIC_AUTH_TTL_SECONDS=2592000",
                env_text,
            )
            self.assertTrue(
                (
                    state_root
                    / "secrets"
                    / "assistants"
                    / "personal"
                    / "dashboard-initial-password"
                ).is_file()
            )

    def test_create_assistant_inherits_install_langfuse(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_root = Path(temporary_directory)
            self.create_state(state_root)
            controller_hermes = state_root / "controller-home" / ".hermes"
            controller_hermes.mkdir(parents=True)
            (controller_hermes / "config.yaml").write_text(
                yaml.safe_dump({"plugins": {"enabled": ["observability/langfuse"]}})
            )
            (controller_hermes / ".env").write_text(
                "HERMES_LANGFUSE_PUBLIC_KEY=pk-lf-create-public\n"
                "HERMES_LANGFUSE_SECRET_KEY=sk-lf-create-secret\n"
                "HERMES_LANGFUSE_BASE_URL=https://cloud.langfuse.com\n"
                "HERMES_LANGFUSE_ENV=controller\n"
            )

            def fake_run(command):
                if command[:3] == ["docker", "image", "inspect"]:
                    if "org.opencontainers.image.revision" in command[-1]:
                        return "testcommit"
                    return RELEASE
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

            request = bind_latest(
                json.loads(
                    (
                        ROOT / "fleet-template" / "assistant-request.json.example"
                    ).read_text()
                )
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
            runtime = state_root / "runtime/assistants/personal/data"
            env_text = (runtime / ".env").read_text()
            self.assertIn("HERMES_LANGFUSE_PUBLIC_KEY=pk-lf-create-public", env_text)
            self.assertIn("HERMES_LANGFUSE_ENV=personal", env_text)
            self.assertNotIn("sk-lf-create-secret", json.dumps(result))
            config = yaml.safe_load((runtime / "config.yaml").read_text())
            self.assertIn("observability/langfuse", config["plugins"]["enabled"])
            soul = (runtime / "SOUL.md").read_text()
            self.assertIn("AIDEE:AIDEE-AGENT-TRACING:BEGIN", soul)
            self.assertIn("not a repository's own Langfuse", soul)

    def test_create_assistant_inherits_controller_custom_ttl(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_root = Path(temporary_directory)
            image_id = self.create_state(state_root)
            controller_hermes = state_root / "controller-home" / ".hermes"
            controller_hermes.mkdir(parents=True)
            (controller_hermes / ".env").write_text(
                "HERMES_DASHBOARD_BASIC_AUTH_USERNAME=mehdi\n"
                "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH=scrypt$test$hash\n"
                "HERMES_DASHBOARD_BASIC_AUTH_SECRET=fixedsecret123\n"
                "HERMES_DASHBOARD_BASIC_AUTH_TTL_SECONDS=86400\n"
            )

            def fake_run(command):
                if command[:3] == ["docker", "image", "inspect"]:
                    if "org.opencontainers.image.revision" in command[-1]:
                        return "testcommit"
                    return RELEASE
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

            request = bind_latest(
                json.loads(
                    (
                        ROOT / "fleet-template" / "assistant-request.json.example"
                    ).read_text()
                )
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
            env_text = (
                state_root
                / "runtime"
                / "assistants"
                / "personal"
                / "data"
                / ".env"
            ).read_text()
            self.assertIn("HERMES_DASHBOARD_BASIC_AUTH_TTL_SECONDS=86400", env_text)

    def test_create_assistant_seeds_runtime_memories_and_home_channel(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_root = Path(temporary_directory)
            image_id = self.create_state(state_root)
            controller_hermes = state_root / "controller-home" / ".hermes"
            controller_hermes.mkdir(parents=True)
            (controller_hermes / "config.yaml").write_text(
                yaml.safe_dump(
                    {
                        "platforms": {
                            "telegram": {
                                "enabled": True,
                                "home_channel": {
                                    "platform": "telegram",
                                    "chat_id": "12345678",
                                    "name": "Owner User",
                                    "user_id": "12345678",
                                },
                            }
                        }
                    }
                )
            )

            chown_calls = []

            def fake_run(command):
                if command[:3] == ["docker", "image", "inspect"]:
                    if "org.opencontainers.image.revision" in command[-1]:
                        return "testcommit"
                    return RELEASE
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
                chown_calls.append((str(path), uid, gid))

            def fake_chown(path, uid, gid):
                chown_calls.append((str(path), uid, gid))

            request = bind_latest(
                json.loads(
                    (
                        ROOT / "fleet-template" / "assistant-request.json.example"
                    ).read_text()
                )
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
                    return_value=(1000, 1000),
                ),
                mock.patch.object(aidee_admin, "run", side_effect=fake_run),
                mock.patch.object(aidee_admin, "validate_capacity_and_ports"),
                mock.patch.object(aidee_admin.os, "chown", side_effect=fake_chown),
                mock.patch.object(
                    aidee_admin,
                    "ensure_directory",
                    side_effect=fake_directory,
                ),
            ):
                result = aidee_admin.create_assistant(request)

            self.assertEqual(result["status"], "provisioning")
            runtime_dir = state_root / "runtime" / "assistants" / "personal" / "data"
            memories_dir = runtime_dir / "memories"
            self.assertTrue(memories_dir.is_dir())
            self.assertEqual(
                (memories_dir / "USER.md").read_text(),
                "# User\n\nExample Owner owns and directs this assistant.\n",
            )
            self.assertEqual(
                (memories_dir / "MEMORY.md").read_text(),
                "# Memory\n",
            )
            config_data = yaml.safe_load((runtime_dir / "config.yaml").read_text())
            telegram_cfg = config_data.get("platforms", {}).get("telegram", {})
            self.assertTrue(telegram_cfg.get("enabled"))
            self.assertIn(
                "aidee-onboarding",
                config_data.get("plugins", {}).get("enabled", []),
            )
            self.assertTrue(
                (runtime_dir / "plugins/aidee-onboarding/plugin.yaml").is_file()
            )
            self.assertTrue(
                (runtime_dir / "plugins/aidee-onboarding/__init__.py").is_file()
            )
            self.assertEqual(
                telegram_cfg.get("home_channel"),
                {
                    "platform": "telegram",
                    "chat_id": "12345678",
                    "name": "Owner User",
                    "user_id": "12345678",
                },
            )

            # Check that container UID 10000 was applied to runtime_dir / memories and SOUL.md
            container_uid_chowns = [
                call for call in chown_calls if call[1] == aidee_admin.CONTAINER_UID
            ]
            self.assertTrue(any(str(memories_dir) in call[0] for call in container_uid_chowns))
            self.assertTrue(any(str(memories_dir / "MEMORY.md") in call[0] for call in container_uid_chowns))
            self.assertTrue((runtime_dir / "SOUL.md").is_file())
            self.assertTrue(any(str(runtime_dir / "SOUL.md") in call[0] for call in container_uid_chowns))

    def test_create_assistant_inherits_owner_record_telegram_id(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_root = Path(temporary_directory)
            image_id = self.create_state(state_root)
            (state_root / "owner.json").write_text(
                json.dumps({"name": "Example Owner", "telegram_id": "987654321"})
            )

            def fake_run(command):
                if command[:3] == ["docker", "image", "inspect"]:
                    if "org.opencontainers.image.revision" in command[-1]:
                        return "testcommit"
                    return RELEASE
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

            request = bind_latest(
                json.loads(
                    (
                        ROOT / "fleet-template" / "assistant-request.json.example"
                    ).read_text()
                )
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
                    return_value=(1000, 1000),
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
            runtime_dir = state_root / "runtime" / "assistants" / "personal" / "data"
            config_data = yaml.safe_load((runtime_dir / "config.yaml").read_text())
            telegram_cfg = config_data.get("platforms", {}).get("telegram", {})
            self.assertTrue(telegram_cfg.get("enabled"))
            self.assertIn(
                "aidee-onboarding",
                config_data.get("plugins", {}).get("enabled", []),
            )
            self.assertEqual(
                telegram_cfg.get("home_channel"),
                {
                    "platform": "telegram",
                    "chat_id": "987654321",
                    "name": "Example Owner",
                    "user_id": "987654321",
                },
            )

    def test_sets_published_dashboard_origin(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_root = Path(temporary_directory)
            self.create_state(state_root)
            registry_path = state_root / "fleet" / "registry.yaml"
            registry = yaml.safe_load(registry_path.read_text())
            registry["assistants"].append(
                {
                    "id": "control-tower",
                    "name": "Control Tower",
                    "kind": "coding",
                    "status": "active",
                    "platform_version": "0.1.0",
                    "state_path": "assistants/control-tower",
                    "container_name": "aidee-control-tower",
                    "dashboard": {
                        "host_port": 9202,
                        "tailscale_https_port": 8444,
                        "url": "https://old.example.ts.net:8444",
                    },
                    "resources": {
                        "cpu_limit": 0.75,
                        "memory_mb": 2048,
                        "storage_gb": 20,
                        "pids_limit": 512,
                    },
                    "image": {
                        "aidee_version": RELEASE,
                        "image_id": "sha256:" + "a" * 64,
                    },
                }
            )
            registry_path.write_text(yaml.safe_dump(registry, sort_keys=False))
            runtime = (
                state_root / "runtime" / "assistants" / "control-tower" / "data"
            )
            runtime.mkdir(parents=True)
            (runtime / "config.yaml").write_text(
                "dashboard:\n  public_url: https://old.example.ts.net:8444\n"
            )
            request = {
                "schema_version": 1,
                "request_id": "set-origin-control-tower",
                "owner_approved": True,
                "operation": "set_dashboard_origin",
                "assistant_id": "control-tower",
                "dashboard_url": "https://control-tower.example.test/",
            }
            with (
                mock.patch.object(aidee_admin, "STATE_ROOT", state_root),
                mock.patch.object(aidee_admin, "SOURCE_ROOT", ROOT),
                mock.patch.object(
                    aidee_admin,
                    "controller_identity",
                    return_value=(os.getuid(), os.getgid()),
                ),
                mock.patch.object(aidee_admin.os, "chown"),
            ):
                result = aidee_admin.execute(request)

            self.assertEqual(result["status"], "updated")
            self.assertEqual(
                result["dashboard_url"], "https://control-tower.example.test"
            )
            updated_registry = yaml.safe_load(registry_path.read_text())
            dashboard = updated_registry["assistants"][0]["dashboard"]
            self.assertEqual(
                dashboard["url"], "https://control-tower.example.test"
            )
            self.assertEqual(dashboard["hostname"], "control-tower.example.test")
            config = yaml.safe_load((runtime / "config.yaml").read_text())
            self.assertEqual(
                config["dashboard"]["public_url"],
                "https://control-tower.example.test",
            )

    def test_upserts_env_values_without_dropping_other_keys(self):
        updated = aidee_admin.upsert_env(
            "KEEP=1\nHERMES_DASHBOARD_BASIC_AUTH_PASSWORD=old\n",
            {"HERMES_DASHBOARD_BASIC_AUTH_PASSWORD": "new"},
        )
        self.assertIn("KEEP=1", updated)
        self.assertIn("HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=new", updated)
        self.assertNotIn("PASSWORD=old", updated)

    def test_reveals_password_from_secret_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_root = Path(temporary_directory)
            self.create_state(state_root)
            registry = yaml.safe_load((state_root / "fleet" / "registry.yaml").read_text())
            registry["assistants"].append(
                {
                    "id": "personal",
                    "name": "Personal",
                    "kind": "personal",
                    "status": "provisioning",
                    "dashboard": {"url": "https://pilot.example.ts.net:8443"},
                }
            )
            (state_root / "fleet" / "registry.yaml").write_text(
                yaml.safe_dump(registry, sort_keys=False)
            )
            secret_dir = state_root / "secrets" / "assistants" / "personal"
            secret_dir.mkdir(parents=True)
            (secret_dir / "dashboard-initial-password").write_text("secret-pass\n")

            with mock.patch.object(aidee_admin, "STATE_ROOT", state_root):
                result = aidee_admin.reveal_dashboard_password("personal")

            self.assertEqual(result["dashboard_username"], "aidee")
            self.assertEqual(result["dashboard_password"], "secret-pass")
            self.assertEqual(
                result["dashboard_url"],
                "https://pilot.example.ts.net:8443",
            )

    def test_reset_updates_env_and_restarts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_root = Path(temporary_directory)
            self.create_state(state_root)
            registry = yaml.safe_load((state_root / "fleet" / "registry.yaml").read_text())
            registry["assistants"].append(
                {
                    "id": "personal",
                    "name": "Personal",
                    "kind": "personal",
                    "status": "running",
                    "dashboard": {"url": "https://pilot.example.ts.net:8443"},
                }
            )
            (state_root / "fleet" / "registry.yaml").write_text(
                yaml.safe_dump(registry, sort_keys=False)
            )
            runtime_dir = state_root / "runtime" / "assistants" / "personal" / "data"
            runtime_dir.mkdir(parents=True)
            (runtime_dir / ".env").write_text(
                "MODEL=keep\nHERMES_DASHBOARD_BASIC_AUTH_PASSWORD=old\n"
            )
            commands = []

            def fake_run(command):
                commands.append(command)
                return ""

            def fake_directory(path, uid, gid, mode):
                path.mkdir(parents=True, exist_ok=True)
                path.chmod(mode)

            with (
                mock.patch.object(aidee_admin, "STATE_ROOT", state_root),
                mock.patch.object(
                    aidee_admin,
                    "controller_identity",
                    return_value=(os.getuid(), os.getgid()),
                ),
                mock.patch.object(aidee_admin, "run", side_effect=fake_run),
                mock.patch.object(aidee_admin.os, "chown"),
                mock.patch.object(
                    aidee_admin,
                    "ensure_directory",
                    side_effect=fake_directory,
                ),
            ):
                result = aidee_admin.reset_dashboard_password("personal")

            env_text = (runtime_dir / ".env").read_text()
            self.assertIn("MODEL=keep", env_text)
            self.assertIn(
                f"HERMES_DASHBOARD_BASIC_AUTH_PASSWORD={result['dashboard_password']}",
                env_text,
            )
            self.assertIn(
                "HERMES_DASHBOARD_BASIC_AUTH_TTL_SECONDS=2592000",
                env_text,
            )
            self.assertNotEqual(result["dashboard_password"], "old")
            self.assertTrue(
                (
                    state_root
                    / "secrets"
                    / "assistants"
                    / "personal"
                    / "dashboard-initial-password"
                ).is_file()
            )
            self.assertIn(["docker", "restart", "aidee-personal"], commands)
            self.assertIn(
                ["docker", "restart", "aidee-personal-dashboard-proxy"],
                commands,
            )

    def test_sets_manual_username_and_password(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_root = Path(temporary_directory)
            self.create_state(state_root)
            registry = yaml.safe_load((state_root / "fleet" / "registry.yaml").read_text())
            registry["assistants"].append(
                {
                    "id": "personal",
                    "name": "Personal",
                    "kind": "personal",
                    "status": "running",
                    "dashboard": {"url": "https://pilot.example.ts.net:8443"},
                }
            )
            (state_root / "fleet" / "registry.yaml").write_text(
                yaml.safe_dump(registry, sort_keys=False)
            )
            runtime_dir = state_root / "runtime" / "assistants" / "personal" / "data"
            runtime_dir.mkdir(parents=True)
            (runtime_dir / ".env").write_text(
                "MODEL=keep\nHERMES_DASHBOARD_BASIC_AUTH_USERNAME=aidee\n"
                "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=oldpass1\n"
            )
            commands = []

            def fake_run(command):
                commands.append(command)
                return ""

            def fake_directory(path, uid, gid, mode):
                path.mkdir(parents=True, exist_ok=True)
                path.chmod(mode)

            request = {
                "assistant_id": "personal",
                "dashboard_username": "owner",
                "dashboard_password": "manual-pass",
            }
            with (
                mock.patch.object(aidee_admin, "STATE_ROOT", state_root),
                mock.patch.object(
                    aidee_admin,
                    "controller_identity",
                    return_value=(os.getuid(), os.getgid()),
                ),
                mock.patch.object(aidee_admin, "run", side_effect=fake_run),
                mock.patch.object(aidee_admin.os, "chown"),
                mock.patch.object(
                    aidee_admin,
                    "ensure_directory",
                    side_effect=fake_directory,
                ),
            ):
                result = aidee_admin.set_dashboard_credentials(request)

            env_text = (runtime_dir / ".env").read_text()
            self.assertIn("MODEL=keep", env_text)
            self.assertIn("HERMES_DASHBOARD_BASIC_AUTH_USERNAME=owner", env_text)
            self.assertIn("HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=manual-pass", env_text)
            self.assertIn("HERMES_DASHBOARD_BASIC_AUTH_TTL_SECONDS=2592000", env_text)
            self.assertEqual(result["dashboard_username"], "owner")
            self.assertEqual(result["dashboard_password"], "manual-pass")
            self.assertIn(["docker", "restart", "aidee-personal"], commands)

    def test_rejects_unapproved_request(self):
        request = bind_latest(
            json.loads(
                (ROOT / "fleet-template" / "assistant-request.json.example").read_text()
            )
        )
        request["owner_approved"] = False
        with mock.patch.object(aidee_admin, "SOURCE_ROOT", ROOT):
            with self.assertRaises(aidee_admin.AdminError):
                aidee_admin.validate_request(request)

    def test_validate_capacity_and_ports_supports_rebalancing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_root = Path(temporary_directory)
            self.create_state(state_root)
            registry = yaml.safe_load(
                (state_root / "fleet" / "registry.yaml").read_text()
            )
            registry["assistants"].append(
                {
                    "id": "personal",
                    "name": "Personal",
                    "kind": "personal",
                    "status": "running",
                    "dashboard": {
                        "host_port": 9121,
                        "tailscale_https_port": 8443,
                    },
                    "resources": {
                        "cpu_limit": 1.0,
                        "memory_mb": 2048,
                    },
                }
            )
            (state_root / "fleet" / "registry.yaml").write_text(
                yaml.safe_dump(registry, sort_keys=False)
            )
            rebalance_assistant = {
                "id": "personal",
                "dashboard": {
                    "host_port": 9121,
                    "tailscale_https_port": 8443,
                },
                "resources": {
                    "cpu_limit": 1.5,
                    "memory_mb": 3072,
                },
            }
            with (
                mock.patch.object(aidee_admin, "STATE_ROOT", state_root),
                mock.patch("pathlib.Path.read_text", return_value="MemTotal:        16384000 kB\n"),
                mock.patch("os.cpu_count", return_value=4),
            ):
                # Should not raise AdminError when rebalancing the same assistant
                aidee_admin.validate_capacity_and_ports(rebalance_assistant)

    def test_handle_connection_allows_controller_and_root(self):
        dummy_conn = mock.MagicMock()
        valid_payload = json.dumps(
            {
                "request_id": "test-req-1",
                "operation": "list_assistants",
                "owner_approved": True,
            }
        ).encode()
        dummy_conn.recv.return_value = valid_payload

        with (
            mock.patch.object(aidee_admin, "peer_uid", return_value=1000),
            mock.patch.object(aidee_admin, "execute_idempotent", return_value={"ok": True}),
        ):
            # Allowed when peer is controller_uid (1000)
            res = aidee_admin.handle_connection(dummy_conn, 1000)
            self.assertEqual(res, {"ok": True})

        with (
            mock.patch.object(aidee_admin, "peer_uid", return_value=0),
            mock.patch.object(aidee_admin, "execute_idempotent", return_value={"ok": True}),
        ):
            # Allowed when peer is root (0)
            res = aidee_admin.handle_connection(dummy_conn, 1000)
            self.assertEqual(res, {"ok": True})

        with mock.patch.object(aidee_admin, "peer_uid", return_value=2000):
            # Rejected for unauthorized uid
            with self.assertRaises(aidee_admin.AdminError):
                aidee_admin.handle_connection(dummy_conn, 1000)

    def test_create_assistant_seeds_coding_and_project_engineering_standards(self):
        for kind in ("coding", "project"):
            with tempfile.TemporaryDirectory() as temporary_directory:
                state_root = Path(temporary_directory)
                self.create_state(state_root)
                request = bind_latest(
                    json.loads(
                        (
                            ROOT / "fleet-template" / "assistant-request.json.example"
                        ).read_text()
                    )
                )
                request["assistant"]["id"] = f"test-{kind}"
                request["assistant"]["name"] = f"Test {kind.capitalize()}"
                request["assistant"]["kind"] = kind

                def fake_run(command):
                    if command[:3] == ["docker", "image", "inspect"]:
                        if "org.opencontainers.image.revision" in command[-1]:
                            return "testcommit"
                        return RELEASE
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
                runtime_soul = (
                    state_root
                    / "runtime"
                    / "assistants"
                    / f"test-{kind}"
                    / "data"
                    / "SOUL.md"
                )
                self.assertTrue(runtime_soul.is_file())
                content = runtime_soul.read_text()
                self.assertIn("Communication standards", content)
                self.assertIn("120 words or fewer", content)
                self.assertIn("On Telegram, present choices", content)
                self.assertIn("interactive clarify tool with clickable options", content)
                self.assertIn("Software engineering standards", content)
                self.assertIn("Run relevant tests", content)
                self.assertIn("`diagnosing-bugs`", content)
                self.assertIn(
                    "requirements and specification skills",
                    content,
                )
                self.assertIn(
                    "`codebase-design` and `domain-modeling`",
                    content,
                )
                self.assertIn("`code-review` before handoff", content)
                self.assertIn("`handoff` to preserve", content)

                skills_dir = (
                    state_root
                    / "runtime"
                    / "assistants"
                    / f"test-{kind}"
                    / "data"
                    / "skills"
                )
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
                        f"Expected skill file missing: {skill_file}",
                    )
                    self.assertGreater(len(skill_file.read_text()), 0)

    def test_installed_helper_imports_without_release_module(self):
        installer = (ROOT / "platform/scripts/install-admin-helper.sh").read_text()
        self.assertNotIn("release.py", installer)
        self.assertNotIn("LATEST", installer)

        with tempfile.TemporaryDirectory() as temporary_directory:
            install_dir = Path(temporary_directory) / "usr" / "local" / "lib" / "aidee"
            install_dir.mkdir(parents=True)
            shutil.copy(
                ROOT / "platform/admin/aidee_admin.py",
                install_dir / "aidee-admin",
            )
            shutil.copy(
                ROOT / "platform/admin/assistant_state.py",
                install_dir / "assistant_state.py",
            )
            shutil.copy(
                ROOT / "platform/admin/fleet_status.py",
                install_dir / "fleet_status.py",
            )
            shutil.copy(
                ROOT / "platform/setup/onboarding_state.py",
                install_dir / "onboarding_state.py",
            )
            self.assertFalse((install_dir / "release.py").exists())
            self.assertFalse((Path(temporary_directory) / "LATEST").exists())

            helper = install_dir / "aidee-admin"
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path\n"
                        f"path = Path({str(helper)!r})\n"
                        "namespace = {'__name__': 'aidee_admin', '__file__': str(path)}\n"
                        "exec(compile(path.read_text(), str(path), 'exec'), namespace)\n"
                        "print('imported')\n"
                    ),
                ],
                cwd=temporary_directory,
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "HOME": temporary_directory,
                    "PYTHONPATH": "",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("imported", result.stdout)
            self.assertNotIn("ModuleNotFoundError", result.stderr)
            self.assertNotIn("No module named 'release'", result.stderr)

    def test_installed_helper_imports_onboarding_from_install_dir(self):
        installer = (ROOT / "platform/scripts/install-admin-helper.sh").read_text()
        self.assertIn(
            'install -m 0644 -o root -g root "${onboarding_module}"',
            installer,
        )
        self.assertIn("${install_dir}/onboarding_state.py", installer)
        self.assertIn("${install_dir}/fleet_status.py", installer)

        with tempfile.TemporaryDirectory() as temporary_directory:
            install_dir = Path(temporary_directory) / "usr" / "local" / "lib" / "aidee"
            install_dir.mkdir(parents=True)
            shutil.copy(
                ROOT / "platform/admin/assistant_state.py",
                install_dir / "assistant_state.py",
            )
            shutil.copy(
                ROOT / "platform/setup/onboarding_state.py",
                install_dir / "onboarding_state.py",
            )
            spec = importlib.util.spec_from_file_location(
                "installed_assistant_state",
                install_dir / "assistant_state.py",
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertTrue(hasattr(module, "default_onboarding_status"))
            status = module.default_onboarding_status("personal")
            self.assertEqual(status["schema_version"], 2)
            self.assertEqual(status["role"], "assistant")


SECRET_KEY = re.compile(
    r"password|secret|token|credential|api_key|authorization|private_key",
    re.I,
)


def assert_public_payload(test, value, path="root"):
    if isinstance(value, dict):
        for key, child in value.items():
            test.assertIsNone(
                SECRET_KEY.search(str(key)),
                f"secret key leaked at {path}.{key}",
            )
            assert_public_payload(test, child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            assert_public_payload(test, child, f"{path}[{index}]")


class FleetOverviewTests(unittest.TestCase):
    def write_registry(self, state_root, assistants=None, extra_platform=None):
        fleet = state_root / "fleet"
        fleet.mkdir(parents=True, exist_ok=True)
        platform = {
            "repository": "https://example.com/aidee.git",
            "default_version": "0.1.0",
            "desired_release": RELEASE,
        }
        if extra_platform:
            platform.update(extra_platform)
        registry = {
            "schema_version": 1,
            "platform": platform,
            "controller": {"id": "aidee-controller", "state_path": "controller"},
            "assistants": assistants or [],
        }
        (fleet / "registry.yaml").write_text(yaml.safe_dump(registry, sort_keys=False))
        return registry

    def overview_request(self):
        return {
            "schema_version": 1,
            "request_id": "fleet-overview-test",
            "owner_approved": True,
            "operation": "fleet_overview",
        }

    def test_overview_filters_secrets_and_renders_empty_fleet(self):
        leaked = aidee_admin.public_payload(
            {
                "dashboard_password": "hidden",
                "session_secret": "hidden",
                "api_token": "hidden",
                "name": "Pilot",
            }
        )
        self.assertEqual(leaked, {"name": "Pilot"})

        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            self.write_registry(state_root)
            (state_root / "LATEST").write_text(f"{RELEASE}\n")
            (state_root / "runtime" / "images").mkdir(parents=True)
            with (
                mock.patch.object(aidee_admin, "STATE_ROOT", state_root),
                mock.patch.object(aidee_admin, "SOURCE_ROOT", ROOT),
                mock.patch.object(
                    aidee_admin,
                    "IMAGE_RECORD_ROOT",
                    state_root / "runtime" / "images",
                ),
                mock.patch.object(
                    aidee_admin,
                    "run_optional",
                    return_value=(None, "docker unavailable"),
                ),
            ):
                aidee_admin.validate_request(self.overview_request())
                result = aidee_admin.fleet_overview()
            self.assertEqual(result["assistants"], [])
            self.assertEqual(result["release"]["desired"], RELEASE)
            self.assertIn("controller", result)
            assert_public_payload(self, result)

    def test_overview_survives_missing_onboarding_and_docker_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            self.write_registry(
                state_root,
                [
                    {
                        "id": "pilot",
                        "name": "Pilot",
                        "kind": "coding",
                        "status": "active",
                        "container_name": "aidee-pilot",
                        "dashboard": {"url": "https://pilot.example.ts.net:8443"},
                        "resources": {
                            "cpu_limit": 0.75,
                            "memory_mb": 2048,
                            "pids_limit": 512,
                        },
                        "image": {
                            "aidee_version": RELEASE,
                            "image_id": "sha256:" + "a" * 64,
                            "dashboard_password": "should-not-leak",
                        },
                    }
                ],
            )
            with (
                mock.patch.object(aidee_admin, "STATE_ROOT", state_root),
                mock.patch.object(aidee_admin, "SOURCE_ROOT", ROOT),
                mock.patch.object(
                    aidee_admin,
                    "IMAGE_RECORD_ROOT",
                    state_root / "missing-images",
                ),
                mock.patch.object(
                    aidee_admin,
                    "probe_assistant_live",
                    return_value={
                        "health_status": "unknown",
                        "running": False,
                        "image_version": None,
                        "usage": {
                            "cpu_percent": None,
                            "memory_mb": None,
                            "error": "docker inspect failed",
                        },
                        "error": "docker inspect failed",
                    },
                ),
            ):
                result = aidee_admin.fleet_overview()
            card = result["assistants"][0]
            self.assertEqual(card["id"], "pilot")
            self.assertEqual(card["health"]["status"], "unknown")
            self.assertEqual(card["health"]["error"], "docker inspect failed")
            self.assertEqual(card["onboarding"]["status"], "unavailable")
            self.assertNotIn("dashboard_password", json.dumps(result))
            assert_public_payload(self, result)

    def test_overview_renders_healthy_and_stopped_assistants(self):
        inspect_healthy = [
            {
                "State": {
                    "Status": "running",
                    "Running": True,
                    "Health": {"Status": "healthy"},
                },
                "Config": {
                    "Env": ["HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=leak"],
                    "Labels": {"org.opencontainers.image.version": RELEASE},
                },
            }
        ]
        inspect_stopped = [
            {
                "State": {"Status": "exited", "Running": False},
                "Config": {"Env": ["TOKEN=leak"], "Labels": {}},
            }
        ]
        stats = {"CPUPerc": "12.5%", "MemUsage": "256MiB / 2GiB"}

        def fake_optional(command, timeout=5):
            if command[:2] == ["docker", "inspect"]:
                if command[2] == "aidee-pilot":
                    return json.dumps(inspect_healthy), None
                if command[2] == "aidee-idle":
                    return json.dumps(inspect_stopped), None
            if command[:2] == ["docker", "stats"]:
                if command[-1] == "aidee-pilot":
                    return json.dumps(stats), None
                return None, "stats unavailable"
            if command[:2] == ["git", "-C"]:
                return RELEASE, None
            return None, "unused"

        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            self.write_registry(
                state_root,
                [
                    {
                        "id": "pilot",
                        "name": "Pilot",
                        "kind": "coding",
                        "status": "active",
                        "container_name": "aidee-pilot",
                        "dashboard": {"url": "https://pilot.example.ts.net:8443"},
                        "resources": {
                            "cpu_limit": 0.75,
                            "memory_mb": 2048,
                            "pids_limit": 512,
                        },
                        "image": {
                            "aidee_version": RELEASE,
                            "image_id": "sha256:" + "b" * 64,
                        },
                    },
                    {
                        "id": "idle",
                        "name": "Idle",
                        "kind": "personal",
                        "status": "stopped",
                        "container_name": "aidee-idle",
                        "resources": {"cpu_limit": 0.5, "memory_mb": 1024},
                        "image": {"aidee_version": RELEASE},
                    },
                ],
            )
            status_dir = state_root / "runtime/assistants/pilot/data/aidee"
            status_dir.mkdir(parents=True)
            (status_dir / "onboarding-status.json").write_text(
                json.dumps(
                    {
                        "rollup": {
                            "status": "complete",
                            "incomplete_required": [],
                            "incomplete_optional": [],
                            "complete": True,
                        }
                    }
                )
            )
            images = state_root / "images"
            images.mkdir()
            (images / f"{RELEASE}.json").write_text(
                json.dumps(
                    {
                        "aidee_version": RELEASE,
                        "validation": "validated",
                    }
                )
            )
            with (
                mock.patch.object(aidee_admin, "STATE_ROOT", state_root),
                mock.patch.object(aidee_admin, "SOURCE_ROOT", ROOT),
                mock.patch.object(aidee_admin, "IMAGE_RECORD_ROOT", images),
                mock.patch.object(
                    aidee_admin, "run_optional", side_effect=fake_optional
                ),
            ):
                result = aidee_admin.fleet_overview()
            healthy, stopped = result["assistants"]
            self.assertEqual(healthy["health"]["status"], "healthy")
            self.assertTrue(healthy["health"]["running"])
            self.assertEqual(healthy["resources"]["usage"]["cpu_percent"], 12.5)
            self.assertEqual(healthy["resources"]["usage"]["memory_mb"], 256.0)
            self.assertEqual(healthy["image"]["installed_version"], RELEASE)
            self.assertEqual(healthy["onboarding"]["status"], "complete")
            self.assertEqual(stopped["health"]["status"], "stopped")
            self.assertFalse(stopped["health"]["running"])
            self.assertNotIn("HERMES_DASHBOARD_BASIC_AUTH_PASSWORD", json.dumps(result))
            self.assertNotIn("TOKEN=leak", json.dumps(result))
            assert_public_payload(self, result)

    def test_overview_rejects_missing_or_malformed_registry(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            with mock.patch.object(aidee_admin, "STATE_ROOT", state_root):
                with self.assertRaises(aidee_admin.AdminError):
                    aidee_admin.fleet_overview()
            (state_root / "fleet").mkdir()
            (state_root / "fleet/registry.yaml").write_text("- not-a-mapping\n")
            with mock.patch.object(aidee_admin, "STATE_ROOT", state_root):
                with self.assertRaises(aidee_admin.AdminError):
                    aidee_admin.fleet_overview()
            (state_root / "fleet/registry.yaml").write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "platform": {"repository": "x", "default_version": "0.1.0"},
                        "controller": {"id": "aidee-controller", "state_path": "c"},
                        "assistants": {"id": "broken"},
                    }
                )
            )
            with (
                mock.patch.object(aidee_admin, "STATE_ROOT", state_root),
                mock.patch.object(aidee_admin, "SOURCE_ROOT", ROOT),
                mock.patch.object(
                    aidee_admin,
                    "IMAGE_RECORD_ROOT",
                    state_root / "images",
                ),
            ):
                result = aidee_admin.fleet_overview()
            self.assertEqual(result["assistants"], [])
            self.assertIn(
                "fleet registry assistants are malformed",
                result["warnings"],
            )

    def test_create_assistant_writes_profile_and_home_plugin(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_root = Path(temporary_directory)
            self_helper = AdminHelperTests()
            self_helper.create_state(state_root)

            def fake_run(command):
                if command[:3] == ["docker", "image", "inspect"]:
                    if "org.opencontainers.image.revision" in command[-1]:
                        return "testcommit"
                    return RELEASE
                if command[:3] == ["git", "-C", str(ROOT)]:
                    return "testcommit"
                if command[:2] == ["docker", "ps"]:
                    return ""
                if command[:3] == ["tailscale", "status", "--json"]:
                    return json.dumps({"Self": {"DNSName": "pilot.example.ts.net."}})
                return ""

            def fake_directory(path, uid, gid, mode):
                path.mkdir(parents=True, exist_ok=True)
                path.chmod(mode)

            request = bind_latest(
                json.loads(
                    (
                        ROOT / "fleet-template" / "assistant-request.json.example"
                    ).read_text()
                )
            )
            with (
                mock.patch.object(aidee_admin, "STATE_ROOT", state_root),
                mock.patch.object(
                    aidee_admin,
                    "IMAGE_RECORD_ROOT",
                    state_root / "runtime" / "images",
                ),
                mock.patch.object(
                    aidee_admin, "OWNER_RECORD", state_root / "owner.json"
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
                    aidee_admin, "ensure_directory", side_effect=fake_directory
                ),
            ):
                aidee_admin.create_assistant(request)

            runtime = state_root / "runtime/assistants/personal/data"
            profile = json.loads((runtime / "aidee/profile.json").read_text())
            self.assertEqual(profile["id"], "personal")
            self.assertEqual(profile["kind"], "personal")
            self.assertEqual(profile["projects"], [])
            self.assertNotIn("password", json.dumps(profile))
            config = yaml.safe_load((runtime / "config.yaml").read_text())
            self.assertIn("aidee-assistant-home", config["plugins"]["enabled"])
            self.assertTrue(
                (runtime / "plugins/aidee-assistant-home/plugin.yaml").is_file()
            )

    def test_assistant_home_reads_only_fixed_memory_files(self):
        spec = importlib.util.spec_from_file_location(
            "assistant_home_api",
            ROOT
            / "platform/dashboard-plugins/aidee-assistant-home/dashboard/plugin_api.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "aidee").mkdir()
            (root / "memories").mkdir()
            (root / "aidee/profile.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "id": "pilot",
                        "name": "Pilot",
                        "kind": "coding",
                        "purpose": "Ship code",
                        "projects": [],
                        "capabilities": ["coding"],
                        "dashboard_password": "hidden",
                    }
                )
            )
            (root / "memories/USER.md").write_text("# User\nOwner\n")
            (root / "memories/MEMORY.md").write_bytes(b"x" * (module.MAX_MEMORY_BYTES + 8))
            (root / "memories/SECRETS.md").write_text("do-not-read\n")
            home = module.load_home(root)
            self.assertEqual(home["profile"]["id"], "pilot")
            self.assertNotIn("dashboard_password", home["profile"])
            self.assertEqual(home["user_md"]["content"], "# User\nOwner\n")
            self.assertTrue(home["memory_md"]["truncated"])
            self.assertEqual(home["memory_md"]["bytes"], module.MAX_MEMORY_BYTES)
            self.assertEqual(home["onboarding"]["error"], "onboarding status is missing")
            self.assertNotIn("SECRETS.md", json.dumps(home))
            (root / "aidee/profile.json").write_text("{")
            broken = module.load_home(root)
            self.assertIsNone(broken["profile"])
            self.assertEqual(broken["profile_error"], "assistant profile is malformed")
            shutil.rmtree(root / "aidee")
            missing = module.load_home(root)
            self.assertEqual(missing["profile_error"], "assistant profile is missing")

    def test_overview_reports_langfuse_and_opencode_without_secrets(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            self.write_registry(
                state_root,
                [
                    {
                        "id": "pilot",
                        "name": "Pilot",
                        "kind": "coding",
                        "status": "active",
                        "container_name": "aidee-pilot",
                        "resources": {"cpu_limit": 0.75, "memory_mb": 2048},
                        "image": {
                            "aidee_version": RELEASE,
                            "image_id": "sha256:" + "c" * 64,
                        },
                    }
                ],
            )
            controller = state_root / "controller-home" / ".hermes"
            controller.mkdir(parents=True)
            (controller / "config.yaml").write_text(
                yaml.safe_dump(
                    {
                        "plugins": {
                            "enabled": [
                                "observability/langfuse",
                                "aidee-overview",
                            ]
                        }
                    }
                )
            )
            (controller / ".env").write_text(
                "HERMES_LANGFUSE_PUBLIC_KEY=pk-lf-test-public\n"
                "HERMES_LANGFUSE_SECRET_KEY=sk-lf-test-secret\n"
                "HERMES_LANGFUSE_ENV=controller\n"
            )
            (controller / "plugins" / "aidee-overview").mkdir(parents=True)
            (controller / "plugins" / "aidee-overview" / "plugin.yaml").write_text(
                "name: aidee-overview\n"
            )
            runtime = state_root / "runtime/assistants/pilot/data"
            runtime.mkdir(parents=True)
            (runtime / "config.yaml").write_text(
                yaml.safe_dump(
                    {
                        "plugins": {
                            "enabled": [
                                "aidee-onboarding",
                                "aidee-assistant-home",
                            ],
                            "disabled": ["observability/langfuse"],
                        }
                    }
                )
            )
            (runtime / "plugins" / "aidee-onboarding").mkdir(parents=True)
            (runtime / "plugins" / "aidee-onboarding" / "plugin.yaml").write_text(
                "name: aidee-onboarding\n"
            )
            images = state_root / "images"
            images.mkdir()
            (images / f"{RELEASE}.json").write_text(
                json.dumps(
                    {
                        "aidee_version": RELEASE,
                        "validation": "validated",
                        "opencode_version": "1.18.3",
                    }
                )
            )
            with (
                mock.patch.object(aidee_admin, "STATE_ROOT", state_root),
                mock.patch.object(aidee_admin, "SOURCE_ROOT", ROOT),
                mock.patch.object(aidee_admin, "IMAGE_RECORD_ROOT", images),
                mock.patch.object(
                    aidee_admin,
                    "probe_assistant_live",
                    return_value={
                        "health_status": "healthy",
                        "running": True,
                        "image_version": RELEASE,
                        "usage": {"cpu_percent": 1.0, "memory_mb": 128},
                        "error": None,
                    },
                ),
            ):
                result = aidee_admin.fleet_overview()
            controller_view = result["controller"]
            self.assertEqual(controller_view["langfuse"]["status"], "enabled")
            self.assertIsNone(controller_view["langfuse"]["reason"])
            self.assertEqual(controller_view["langfuse"]["environment"], "controller")
            self.assertEqual(controller_view["langfuse"]["source"], "controller")
            controller_tools = {
                item["name"]: item for item in controller_view["tools"]
            }
            self.assertTrue(controller_tools["observability/langfuse"]["enabled"])
            self.assertTrue(controller_tools["aidee-overview"]["present"])
            card = result["assistants"][0]
            self.assertEqual(card["langfuse"]["status"], "disabled")
            tools = {item["name"]: item for item in card["tools"]}
            self.assertTrue(tools["opencode"]["present"])
            self.assertTrue(tools["opencode"]["enabled"])
            self.assertFalse(tools["observability/langfuse"]["enabled"])
            self.assertTrue(tools["aidee-onboarding"]["enabled"])
            dumped = json.dumps(result)
            self.assertNotIn("pk-lf-test-public", dumped)
            self.assertNotIn("sk-lf-test-secret", dumped)
            self.assertNotIn("HERMES_LANGFUSE_SECRET_KEY", dumped)
            assert_public_payload(self, result)

    def test_langfuse_unknown_when_plugin_enabled_without_keys(self):
        status = aidee_admin.inspect_hermes_runtime
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "config.yaml").write_text(
                yaml.safe_dump({"plugins": {"enabled": ["observability/langfuse"]}})
            )
            missing = status(
                config_path=root / "config.yaml",
                env_path=root / ".env",
                plugins_dirs=[],
            )
            self.assertEqual(missing["langfuse"]["status"], "unknown")
            self.assertIn("missing", missing["langfuse"]["reason"])
            (root / ".env").write_text("HERMES_LANGFUSE_PUBLIC_KEY=\n")
            empty = status(
                config_path=root / "config.yaml",
                env_path=root / ".env",
                plugins_dirs=[],
            )
            self.assertEqual(empty["langfuse"]["status"], "unknown")
            self.assertIn("keys are not set", empty["langfuse"]["reason"])
            absent = status(
                config_path=root / "missing.yaml",
                env_path=root / ".env",
                plugins_dirs=[],
            )
            self.assertEqual(absent["langfuse"]["status"], "unknown")
            self.assertIn("missing", absent["langfuse"]["reason"])

    def test_assistant_home_reports_runtime_status_without_secrets(self):
        spec = importlib.util.spec_from_file_location(
            "assistant_home_api",
            ROOT
            / "platform/dashboard-plugins/aidee-assistant-home/dashboard/plugin_api.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "aidee").mkdir()
            (root / "memories").mkdir()
            (root / "plugins" / "aidee-assistant-home").mkdir(parents=True)
            (root / "aidee/profile.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "id": "pilot",
                        "name": "Pilot",
                        "kind": "coding",
                        "purpose": "Ship code",
                        "projects": [],
                        "capabilities": ["coding"],
                    }
                )
            )
            (root / "config.yaml").write_text(
                yaml.safe_dump(
                    {
                        "plugins": {
                            "enabled": [
                                "observability/langfuse",
                                "aidee-assistant-home",
                            ]
                        }
                    }
                )
            )
            (root / ".env").write_text(
                "HERMES_LANGFUSE_PUBLIC_KEY=pk-lf-home-public\n"
                "LANGFUSE_SECRET_KEY=sk-lf-home-secret\n"
                "HERMES_LANGFUSE_ENV=pilot\n"
            )
            (root / "plugins" / "aidee-assistant-home" / "plugin.yaml").write_text(
                "name: aidee-assistant-home\n"
            )
            (root / "skills" / "autonomous-ai-agents" / "opencode").mkdir(parents=True)
            (root / "skills" / "autonomous-ai-agents" / "opencode" / "SKILL.md").write_text(
                "name: opencode\n"
            )
            (root / "memories/USER.md").write_text("# User\n")
            (root / "memories/MEMORY.md").write_text("# Memory\n")
            (root / "aidee/onboarding-status.json").write_text(
                json.dumps(
                    {
                        "rollup": {
                            "status": "complete",
                            "incomplete_required": [],
                            "incomplete_optional": [],
                            "complete": True,
                        },
                        "password": "hidden",
                    }
                )
            )
            home = module.load_home(root)
            self.assertEqual(home["langfuse"]["status"], "enabled")
            self.assertEqual(home["langfuse"]["environment"], "pilot")
            self.assertEqual(home["langfuse"]["source"], "controller")
            self.assertEqual(home["onboarding"]["status"], "complete")
            self.assertIsNone(home["onboarding"]["error"])
            tools = {item["name"]: item for item in home["tools"]}
            self.assertTrue(tools["opencode"]["present"])
            self.assertTrue(tools["aidee-assistant-home"]["enabled"])
            dumped = json.dumps(home)
            self.assertNotIn("pk-lf-home-public", dumped)
            self.assertNotIn("sk-lf-home-secret", dumped)
            self.assertNotIn("SECRETS.md", dumped)
            self.assertNotIn("hidden", dumped)
            self.assertTrue(home["langfuse"]["keys_set"])
            self.assertFalse(home["langfuse"].get("host_set"))


class LangfuseOpencodeWriteTests(unittest.TestCase):
    def write_registry(self, state_root, assistants=None):
        fleet = state_root / "fleet"
        fleet.mkdir(parents=True, exist_ok=True)
        registry = {
            "schema_version": 1,
            "platform": {
                "repository": "https://example.com/aidee.git",
                "default_version": "0.1.0",
                "desired_release": RELEASE,
            },
            "controller": {"id": "aidee-controller", "state_path": "controller"},
            "assistants": assistants or [],
        }
        (fleet / "registry.yaml").write_text(yaml.safe_dump(registry, sort_keys=False))

    def patch_writes(self, state_root):
        return (
            mock.patch.object(aidee_admin, "STATE_ROOT", state_root),
            mock.patch.object(aidee_admin, "SOURCE_ROOT", ROOT),
            mock.patch.object(
                aidee_admin,
                "controller_identity",
                return_value=(os.getuid(), os.getgid()),
            ),
            mock.patch.object(aidee_admin.os, "chown"),
            mock.patch.object(
                aidee_admin, "schedule_controller_restart", return_value=True
            ),
            mock.patch.object(aidee_admin, "restart_assistant_containers"),
        )

    def test_controller_langfuse_enable_writes_env_without_returning_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            self.write_registry(state_root)
            home = state_root / "controller-home" / ".hermes"
            home.mkdir(parents=True)
            (home / "config.yaml").write_text(yaml.safe_dump({"plugins": {"enabled": []}}))
            (home / ".env").write_text("MODEL=keep\n")
            request = {
                "schema_version": 1,
                "request_id": "set-controller-langfuse",
                "owner_approved": True,
                "operation": "set_controller_langfuse",
                "enabled": True,
                "public_key": "pk-lf-controller-public",
                "secret_key": "sk-lf-controller-secret",
                "base_url": "https://cloud.langfuse.com",
            }
            patches = self.patch_writes(state_root)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                aidee_admin.validate_request(request)
                result = aidee_admin.set_controller_langfuse(request)
            env_text = (home / ".env").read_text()
            config = yaml.safe_load((home / "config.yaml").read_text())
            self.assertIn("HERMES_LANGFUSE_PUBLIC_KEY=pk-lf-controller-public", env_text)
            self.assertIn("HERMES_LANGFUSE_SECRET_KEY=sk-lf-controller-secret", env_text)
            self.assertIn("HERMES_LANGFUSE_ENV=controller", env_text)
            self.assertIn("observability/langfuse", config["plugins"]["enabled"])
            self.assertEqual(result["langfuse"]["status"], "enabled")
            self.assertEqual(result["langfuse"]["environment"], "controller")
            self.assertTrue(result["langfuse"]["keys_set"])
            dumped = json.dumps(result)
            self.assertNotIn("pk-lf-controller-public", dumped)
            self.assertNotIn("sk-lf-controller-secret", dumped)
            overview = aidee_admin.inspect_hermes_runtime(
                config_path=home / "config.yaml",
                env_path=home / ".env",
            )
            self.assertNotIn("pk-lf-controller-public", json.dumps(overview))

    def test_controller_langfuse_rejects_credential_url_and_disable_keeps_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            self.write_registry(state_root)
            home = state_root / "controller-home" / ".hermes"
            home.mkdir(parents=True)
            (home / "config.yaml").write_text(
                yaml.safe_dump({"plugins": {"enabled": ["observability/langfuse"]}})
            )
            (home / ".env").write_text(
                "HERMES_LANGFUSE_PUBLIC_KEY=pk-lf-keep\n"
                "HERMES_LANGFUSE_SECRET_KEY=sk-lf-keep\n"
            )
            bad = {
                "schema_version": 1,
                "request_id": "bad-langfuse-url",
                "owner_approved": True,
                "operation": "set_controller_langfuse",
                "enabled": True,
                "public_key": "pk-lf-controller-public",
                "secret_key": "sk-lf-controller-secret",
                "base_url": "https://user:pass@cloud.langfuse.com",
            }
            disable = {
                "schema_version": 1,
                "request_id": "disable-controller-langfuse",
                "owner_approved": True,
                "operation": "set_controller_langfuse",
                "enabled": False,
            }
            patches = self.patch_writes(state_root)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                with self.assertRaises(aidee_admin.AdminError):
                    aidee_admin.validate_request(bad)
                aidee_admin.validate_request(disable)
                result = aidee_admin.set_controller_langfuse(disable)
            env_text = (home / ".env").read_text()
            self.assertIn("HERMES_LANGFUSE_SECRET_KEY=sk-lf-keep", env_text)
            self.assertFalse(
                any(line.startswith("HERMES_LANGFUSE_ENV=") for line in env_text.splitlines())
            )
            self.assertEqual(result["langfuse"]["status"], "disabled")
            self.assertTrue(result["langfuse"]["keys_set"])
            self.assertNotIn("sk-lf-keep", json.dumps(result))

    def test_langfuse_admin_record_hashes_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            self.write_registry(state_root)
            records = state_root / "runtime" / "admin-requests"
            records.mkdir(parents=True)
            home = state_root / "controller-home" / ".hermes"
            home.mkdir(parents=True)
            (home / "config.yaml").write_text("{}\n")
            request = {
                "schema_version": 1,
                "request_id": "hash-langfuse-keys",
                "owner_approved": True,
                "operation": "set_controller_langfuse",
                "enabled": True,
                "public_key": "pk-lf-hashed-public",
                "secret_key": "sk-lf-hashed-secret",
            }
            patches = self.patch_writes(state_root)
            with (
                patches[0],
                patches[1],
                patches[2],
                patches[3],
                patches[4],
                patches[5],
                mock.patch.object(
                    aidee_admin,
                    "controller_identity",
                    return_value=(os.getuid(), os.getgid()),
                ),
            ):
                result = aidee_admin.execute_idempotent(request)
                again = aidee_admin.execute_idempotent(request)
            self.assertEqual(result, again)
            stored = json.loads((records / "hash-langfuse-keys.json").read_text())
            self.assertTrue(stored["request"]["secret_key"].startswith("sha256:"))
            self.assertNotIn("sk-lf-hashed-secret", json.dumps(stored))

    def test_controller_langfuse_write_is_inherited_with_unique_environments(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            self.write_registry(
                state_root,
                [
                    {
                        "id": "pilot",
                        "name": "Pilot",
                        "kind": "coding",
                        "status": "active",
                        "image": {"aidee_version": RELEASE},
                    },
                    {
                        "id": "idle",
                        "name": "Idle",
                        "kind": "personal",
                        "status": "active",
                        "image": {"aidee_version": RELEASE},
                    },
                ],
            )
            home = state_root / "controller-home" / ".hermes"
            home.mkdir(parents=True)
            (home / "config.yaml").write_text(yaml.safe_dump({"plugins": {"enabled": []}}))
            (home / ".env").write_text("MODEL=keep\n")
            controller_soul = state_root / "fleet/controller/SOUL.md"
            controller_soul.parent.mkdir(parents=True)
            controller_soul.write_text("# Aidee controller\n\nYou operate Aidee.\n")
            images = state_root / "images"
            images.mkdir()
            (images / f"{RELEASE}.json").write_text(
                json.dumps(
                    {
                        "aidee_version": RELEASE,
                        "validation": "validated",
                        "opencode_version": "1.18.3",
                    }
                )
            )
            runtimes = {}
            for assistant_id in ("pilot", "idle"):
                runtime = state_root / f"runtime/assistants/{assistant_id}/data"
                runtime.mkdir(parents=True)
                (runtime / "config.yaml").write_text("{}\n")
                (runtime / ".env").write_text("MODEL=keep\n")
                (runtime / "SOUL.md").write_text(f"# {assistant_id}\n")
                fleet = state_root / f"fleet/assistants/{assistant_id}"
                fleet.mkdir(parents=True)
                (fleet / "SOUL.md").write_text(f"# {assistant_id}\n")
                runtimes[assistant_id] = runtime
            enable = {
                "schema_version": 1,
                "request_id": "set-controller-langfuse-inherit",
                "owner_approved": True,
                "operation": "set_controller_langfuse",
                "enabled": True,
                "public_key": "pk-lf-install-public",
                "secret_key": "sk-lf-install-secret",
                "base_url": "https://cloud.langfuse.com",
            }
            install = {
                "schema_version": 1,
                "request_id": "install-assistant-opencode",
                "owner_approved": True,
                "operation": "set_assistant_opencode",
                "assistant_id": "pilot",
                "action": "install",
            }
            uninstall = {
                "schema_version": 1,
                "request_id": "set-assistant-opencode",
                "owner_approved": True,
                "operation": "set_assistant_opencode",
                "assistant_id": "pilot",
                "action": "uninstall",
            }
            disable = {
                "schema_version": 1,
                "request_id": "disable-controller-langfuse",
                "owner_approved": True,
                "operation": "set_controller_langfuse",
                "enabled": False,
            }
            inherit = {
                "schema_version": 1,
                "request_id": "inherit-pilot-langfuse",
                "owner_approved": True,
                "operation": "set_assistant_langfuse",
                "assistant_id": "pilot",
            }
            patches = self.patch_writes(state_root)
            with (
                patches[0],
                patches[1],
                patches[2],
                patches[3],
                patches[4],
                patches[5],
                mock.patch.object(aidee_admin, "IMAGE_RECORD_ROOT", images),
            ):
                aidee_admin.validate_request(enable)
                langfuse = aidee_admin.set_controller_langfuse(enable)
                aidee_admin.validate_request(inherit)
                inherited = aidee_admin.set_assistant_langfuse(inherit)
                aidee_admin.validate_request(install)
                installed = aidee_admin.set_assistant_opencode(install)
                controller_env = (home / ".env").read_text()
                self.assertIn("HERMES_LANGFUSE_ENV=controller", controller_env)
                self.assertIn("HERMES_LANGFUSE_SECRET_KEY=sk-lf-install-secret", controller_env)
                environments = set()
                for assistant_id, runtime in runtimes.items():
                    env_text = (runtime / ".env").read_text()
                    self.assertIn("HERMES_LANGFUSE_PUBLIC_KEY=pk-lf-install-public", env_text)
                    self.assertIn(f"HERMES_LANGFUSE_ENV={assistant_id}", env_text)
                    self.assertIn("AIDEE:AIDEE-AGENT-TRACING:BEGIN", (runtime / "SOUL.md").read_text())
                    environments.add(assistant_id)
                    config = yaml.safe_load((runtime / "config.yaml").read_text())
                    self.assertIn("observability/langfuse", config["plugins"]["enabled"])
                self.assertEqual(environments, {"pilot", "idle"})
                env_enabled = (runtimes["pilot"] / ".env").read_text()
                self.assertIn("LANGFUSE_PUBLIC_KEY=pk-lf-install-public", env_enabled)
                self.assertIn("LANGFUSE_ENVIRONMENT=pilot", env_enabled)
                self.assertIn("LANGFUSE_BASEURL=https://cloud.langfuse.com", env_enabled)
                self.assertNotIn("OTEL_EXPORTER_OTLP_ENDPOINT=", env_enabled)
                credentials_path = (
                    runtimes["pilot"] / ".config/opencode/opencode-langfuse.json"
                )
                config_path = runtimes["pilot"] / ".config/opencode/opencode.json"
                self.assertEqual(
                    aidee_admin.assistant_opencode_config_path(runtimes["pilot"]),
                    config_path,
                )
                self.assertEqual(
                    aidee_admin.ASSISTANT_CONTAINER_HOME, Path("/opt/data")
                )
                self.assertTrue(credentials_path.is_file())
                self.assertEqual(stat.S_IMODE(credentials_path.stat().st_mode), 0o600)
                credentials = json.loads(credentials_path.read_text())
                self.assertEqual(
                    credentials,
                    {
                        "publicKey": "pk-lf-install-public",
                        "secretKey": "sk-lf-install-secret",
                        "baseUrl": "https://cloud.langfuse.com",
                        "environment": "pilot",
                    },
                )
                opencode_config = json.loads(config_path.read_text())
                self.assertTrue(opencode_config["experimental"]["openTelemetry"])
                self.assertIn(
                    "@langfuse/opencode-observability-plugin@latest",
                    opencode_config["plugin"],
                )
                self.assertIn(
                    "AIDEE:OPENCODE-DELEGATION:BEGIN",
                    (runtimes["pilot"] / "SOUL.md").read_text(),
                )
                self.assertIn("delegate coding to OpenCode", installed["note"])
                self.assertIn(
                    "AIDEE:AIDEE-AGENT-TRACING:BEGIN",
                    controller_soul.read_text(),
                )
                aidee_admin.validate_request(uninstall)
                opencode = aidee_admin.set_assistant_opencode(uninstall)
                env_disabled = (runtimes["pilot"] / ".env").read_text()
                self.assertIn("HERMES_LANGFUSE_SECRET_KEY=sk-lf-install-secret", env_disabled)
                self.assertIn("HERMES_LANGFUSE_ENV=pilot", env_disabled)
                self.assertFalse(
                    any(
                        line.startswith("LANGFUSE_PUBLIC_KEY=")
                        for line in env_disabled.splitlines()
                    )
                )
                self.assertFalse(credentials_path.exists())
                self.assertNotIn(
                    "AIDEE:OPENCODE-DELEGATION:BEGIN",
                    (runtimes["pilot"] / "SOUL.md").read_text(),
                )
                desired = json.loads((runtimes["pilot"] / "aidee/opencode.json").read_text())
                self.assertEqual(desired["desired"], "absent")
                tools = {item["name"]: item for item in opencode["tools"]}
                self.assertTrue(tools["opencode"]["present"])
                self.assertFalse(tools["opencode"]["enabled"])
                aidee_admin.validate_request(install)
                aidee_admin.set_assistant_opencode(install)
                aidee_admin.validate_request(disable)
                aidee_admin.set_controller_langfuse(disable)
                env_no_trace = (runtimes["pilot"] / ".env").read_text()
                self.assertFalse(
                    (runtimes["pilot"] / ".config/opencode/opencode-langfuse.json").exists()
                )
                self.assertNotIn("HERMES_LANGFUSE_SECRET_KEY=", env_no_trace)
                self.assertNotIn("HERMES_LANGFUSE_ENV=", env_no_trace)
                self.assertNotIn(
                    "AIDEE:AIDEE-AGENT-TRACING:BEGIN",
                    (runtimes["pilot"] / "SOUL.md").read_text(),
                )
                self.assertIn(
                    "AIDEE:OPENCODE-DELEGATION:BEGIN",
                    (runtimes["pilot"] / "SOUL.md").read_text(),
                )
                self.assertIn("HERMES_LANGFUSE_SECRET_KEY=sk-lf-install-secret", (home / ".env").read_text())
                self.assertNotIn(
                    "AIDEE:AIDEE-AGENT-TRACING:BEGIN",
                    controller_soul.read_text(),
                )
            self.assertEqual(langfuse["langfuse"]["status"], "enabled")
            self.assertEqual(inherited["langfuse"]["environment"], "pilot")
            dumped = json.dumps(langfuse) + json.dumps(inherited) + json.dumps(installed)
            self.assertNotIn("sk-lf-install-secret", dumped)
            self.assertNotIn("pk-lf-install-public", dumped)
            self.assertIn("stays in the assistant image", opencode["note"])
            self.assertIn("coding-delegation instruction", opencode["note"])

    def test_controller_opencode_installs_pinned_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            self.write_registry(state_root)
            home = state_root / "controller-home" / ".hermes"
            node = home / "node" / "bin"
            node.mkdir(parents=True)
            npm = node / "npm"
            npm.write_text("#!/bin/sh\n")
            npm.chmod(0o755)
            commands = []

            def fake_run(command):
                commands.append(command)
                return ""

            patches = self.patch_writes(state_root)
            request = {
                "schema_version": 1,
                "request_id": "install-controller-opencode",
                "owner_approved": True,
                "operation": "set_controller_opencode",
                "action": "install",
            }
            with (
                patches[0],
                patches[1],
                patches[2],
                patches[3],
                patches[4],
                patches[5],
                mock.patch.object(aidee_admin, "run", side_effect=fake_run),
                mock.patch.object(aidee_admin.shutil, "which", return_value=None),
            ):
                aidee_admin.validate_request(request)
                result = aidee_admin.set_controller_opencode(request)
            npm_command = commands[0]
            self.assertEqual(npm_command[0], "runuser")
            self.assertIn("install", npm_command)
            self.assertIn("opencode-ai@1.18.3", npm_command)
            self.assertTrue((state_root / "fleet/controller/opencode.json").is_file())
            self.assertIn("1.18.3", result["note"])
            self.assertTrue(result["restarted"])
            self.assertIn("gateway will restart", result["next_action"])
            self.assertTrue((home / "skills/opencode/SKILL.md").is_file())
            self.assertIn("Delegate that work to OpenCode", (home / "skills/opencode/SKILL.md").read_text())

    def test_assistant_home_cannot_write_install_langfuse_keys(self):
        spec = importlib.util.spec_from_file_location(
            "assistant_home_api",
            ROOT
            / "platform/dashboard-plugins/aidee-assistant-home/dashboard/plugin_api.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "config.yaml").write_text(
                yaml.safe_dump({"plugins": {"enabled": ["observability/langfuse"]}})
            )
            (root / ".env").write_text(
                "HERMES_LANGFUSE_PUBLIC_KEY=pk-lf-local-public\n"
                "HERMES_LANGFUSE_SECRET_KEY=sk-lf-local-secret\n"
                "HERMES_LANGFUSE_BASE_URL=https://cloud.langfuse.com\n"
                "HERMES_LANGFUSE_ENV=pilot\n"
            )
            (root / "aidee").mkdir()
            (root / "aidee/profile.json").write_text(
                json.dumps({"schema_version": 1, "id": "pilot", "name": "Pilot"})
            )
            with self.assertRaisesRegex(ValueError, "controller dashboard"):
                module.save_langfuse(
                    root,
                    {
                        "enabled": True,
                        "public_key": "pk-lf-other-public",
                        "secret_key": "sk-lf-other-secret",
                        "base_url": "https://cloud.langfuse.com",
                    },
                )
            self.assertIn(
                "HERMES_LANGFUSE_SECRET_KEY=sk-lf-local-secret",
                (root / ".env").read_text(),
            )
            with self.assertRaisesRegex(ValueError, "does not include OpenCode"):
                module.save_opencode(root, {"action": "install"})
            (root / "skills/autonomous-ai-agents/opencode").mkdir(parents=True)
            (root / "skills/autonomous-ai-agents/opencode/SKILL.md").write_text(
                "name: opencode\n"
            )
            (root / "SOUL.md").write_text("# Pilot\n\nYou are Pilot.\n")
            enabled = module.save_opencode(root, {"action": "install"})
            self.assertEqual(enabled["status"], "updated")
            soul = (root / "SOUL.md").read_text()
            self.assertIn("AIDEE:OPENCODE-DELEGATION:BEGIN", soul)
            self.assertIn("do not write or edit the code yourself", soul)
            env_text = (root / ".env").read_text()
            self.assertIn("HERMES_LANGFUSE_PUBLIC_KEY=pk-lf-local-public", env_text)
            self.assertIn("LANGFUSE_PUBLIC_KEY=pk-lf-local-public", env_text)
            self.assertIn("LANGFUSE_ENVIRONMENT=pilot", env_text)
            self.assertIn("LANGFUSE_BASEURL=https://cloud.langfuse.com", env_text)
            self.assertNotIn("OTEL_EXPORTER_OTLP_ENDPOINT=", env_text)
            self.assertNotIn("OPENCODE_CONFIG=", env_text)
            credentials_path = root / ".config/opencode/opencode-langfuse.json"
            self.assertTrue(credentials_path.is_file())
            self.assertEqual(stat.S_IMODE(credentials_path.stat().st_mode), 0o600)
            credentials = json.loads(credentials_path.read_text())
            self.assertEqual(
                credentials,
                {
                    "publicKey": "pk-lf-local-public",
                    "secretKey": "sk-lf-local-secret",
                    "baseUrl": "https://cloud.langfuse.com",
                    "environment": "pilot",
                },
            )
            self.assertNotIn("sk-lf-local-secret", json.dumps(enabled))
            home_payload = module.load_home(root)
            dumped_home = json.dumps(home_payload)
            self.assertNotIn("sk-lf-local-secret", dumped_home)
            self.assertNotIn("pk-lf-local-public", dumped_home)
            disabled = module.save_opencode(root, {"action": "uninstall"})
            self.assertIn("stays in the assistant image", disabled["note"])
            self.assertNotIn(
                "AIDEE:OPENCODE-DELEGATION:BEGIN", (root / "SOUL.md").read_text()
            )
            self.assertFalse(credentials_path.exists())
            env_after = (root / ".env").read_text()
            self.assertIn("HERMES_LANGFUSE_SECRET_KEY=sk-lf-local-secret", env_after)
            self.assertIn("HERMES_LANGFUSE_ENV=pilot", env_after)
            self.assertNotIn("OTEL_EXPORTER_OTLP_ENDPOINT=", env_after)
            self.assertFalse(
                any(line.startswith("LANGFUSE_PUBLIC_KEY=") for line in env_after.splitlines())
            )

    def test_opencode_instruction_markers_and_langfuse_env_mapping(self):
        soul = "# Pilot\n\nYou are Pilot.\n"
        enabled = aidee_admin.apply_opencode_instruction(soul, True)
        self.assertIn("AIDEE:OPENCODE-DELEGATION:BEGIN", enabled)
        self.assertIn("do not write or edit the code yourself", enabled)
        self.assertTrue(enabled.startswith("# Pilot\n"))
        disabled = aidee_admin.apply_opencode_instruction(enabled, False)
        self.assertEqual(disabled, soul)
        env = (
            "HERMES_LANGFUSE_PUBLIC_KEY=pk-lf-map\n"
            "HERMES_LANGFUSE_SECRET_KEY=sk-lf-map\n"
            "HERMES_LANGFUSE_BASE_URL=https://cloud.langfuse.com\n"
            "HERMES_LANGFUSE_ENV=controller\n"
        )
        stale = env + (
            "OTEL_EXPORTER_OTLP_ENDPOINT=https://cloud.langfuse.com/api/public/otel\n"
            "OPENCODE_CONFIG=/opt/data/.config/opencode/opencode.json\n"
        )
        mapped = aidee_admin.apply_opencode_langfuse_env(
            stale, "/opt/data/.config/opencode/opencode.json"
        )
        self.assertIn("LANGFUSE_PUBLIC_KEY=pk-lf-map", mapped)
        self.assertIn("LANGFUSE_SECRET_KEY=sk-lf-map", mapped)
        self.assertIn("LANGFUSE_ENVIRONMENT=controller", mapped)
        self.assertIn("LANGFUSE_BASEURL=https://cloud.langfuse.com", mapped)
        self.assertNotIn("OTEL_EXPORTER_OTLP_ENDPOINT=", mapped)
        self.assertNotIn("OPENCODE_CONFIG=", mapped)
        credentials = aidee_admin.opencode_langfuse_credentials_document(
            mapped, environment="controller"
        )
        self.assertEqual(
            credentials,
            {
                "publicKey": "pk-lf-map",
                "secretKey": "sk-lf-map",
                "baseUrl": "https://cloud.langfuse.com",
                "environment": "controller",
            },
        )
        runtime = Path("/var/lib/aidee/runtime/assistants/pilot/data")
        self.assertEqual(
            aidee_admin.assistant_opencode_host_dir(runtime),
            runtime / ".config/opencode",
        )
        self.assertEqual(
            aidee_admin.assistant_opencode_host_dir(runtime, "/opt/data"),
            runtime / ".config/opencode",
        )
        self.assertEqual(
            aidee_admin.assistant_opencode_host_dir(runtime, "/opt/data/user"),
            runtime / "user/.config/opencode",
        )
        stripped = aidee_admin.strip_opencode_langfuse_env(mapped)
        self.assertIn("HERMES_LANGFUSE_SECRET_KEY=sk-lf-map", stripped)
        self.assertFalse(
            any(line.startswith("LANGFUSE_PUBLIC_KEY=") for line in stripped.splitlines())
        )
        self.assertNotIn("OTEL_EXPORTER_OTLP_ENDPOINT=", stripped)
        fallback = "LANGFUSE_PUBLIC_KEY=pk-lf-only\nLANGFUSE_SECRET_KEY=sk-lf-only\n"
        kept = aidee_admin.strip_opencode_langfuse_env(fallback)
        self.assertIn("LANGFUSE_PUBLIC_KEY=pk-lf-only", kept)
        self.assertIn("LANGFUSE_SECRET_KEY=sk-lf-only", kept)
        traced = aidee_admin.apply_tracing_instruction(soul, True)
        self.assertIn("AIDEE:AIDEE-AGENT-TRACING:BEGIN", traced)
        self.assertIn("Aidee agent tracing", traced)
        self.assertEqual(aidee_admin.apply_tracing_instruction(traced, False), soul)
        config, next_env = aidee_admin.apply_langfuse_settings(
            {},
            "MODEL=keep\n",
            enabled=True,
            public_key="pk-lf-both",
            secret_key="sk-lf-both",
            base_url="https://cloud.langfuse.com",
            environment="controller",
            opencode_enabled=True,
        )
        self.assertIn("observability/langfuse", config["plugins"]["enabled"])
        self.assertIn("LANGFUSE_PUBLIC_KEY=pk-lf-both", next_env)
        self.assertIn("LANGFUSE_ENVIRONMENT=controller", next_env)
        self.assertIn("HERMES_LANGFUSE_ENV=controller", next_env)
        self.assertIn("HERMES_LANGFUSE_SECRET_KEY=sk-lf-both", next_env)
        off_config, off_env = aidee_admin.apply_langfuse_settings(
            config,
            next_env,
            enabled=False,
            opencode_enabled=True,
        )
        self.assertIn("observability/langfuse", off_config["plugins"]["disabled"])
        self.assertIn("HERMES_LANGFUSE_SECRET_KEY=sk-lf-both", off_env)
        self.assertNotIn("OTEL_EXPORTER_OTLP_ENDPOINT=", off_env)

    def test_controller_opencode_writes_soul_and_langfuse_env(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            self.write_registry(state_root)
            home = state_root / "controller-home" / ".hermes"
            node = home / "node" / "bin"
            node.mkdir(parents=True)
            npm = node / "npm"
            npm.write_text("#!/bin/sh\n")
            npm.chmod(0o755)
            (home / "config.yaml").write_text(
                yaml.safe_dump({"plugins": {"enabled": ["observability/langfuse"]}})
            )
            (home / ".env").write_text(
                "HERMES_LANGFUSE_PUBLIC_KEY=pk-lf-controller-public\n"
                "HERMES_LANGFUSE_SECRET_KEY=sk-lf-controller-secret\n"
                "HERMES_LANGFUSE_BASE_URL=https://cloud.langfuse.com\n"
            )
            soul = state_root / "fleet/controller/SOUL.md"
            soul.parent.mkdir(parents=True)
            soul.write_text("# Aidee controller\n\nYou operate Aidee.\n")
            commands = []

            def fake_run(command):
                commands.append(command)
                return ""

            patches = self.patch_writes(state_root)
            request = {
                "schema_version": 1,
                "request_id": "install-controller-opencode-soul",
                "owner_approved": True,
                "operation": "set_controller_opencode",
                "action": "install",
            }
            restart = mock.Mock(return_value=True)
            with (
                patches[0],
                patches[1],
                patches[2],
                patches[3],
                patches[5],
                mock.patch.object(aidee_admin, "schedule_controller_restart", restart),
                mock.patch.object(
                    aidee_admin,
                    "controller_home_dir",
                    return_value=state_root / "controller-home",
                ),
                mock.patch.object(aidee_admin, "run", side_effect=fake_run),
                mock.patch.object(
                    aidee_admin.shutil, "which", return_value="/usr/bin/opencode"
                ),
            ):
                result = aidee_admin.set_controller_opencode(request)
            self.assertIn("opencode-ai@1.18.3", commands[0])
            self.assertIn("AIDEE:OPENCODE-DELEGATION:BEGIN", soul.read_text())
            env_text = (home / ".env").read_text()
            self.assertIn("LANGFUSE_PUBLIC_KEY=pk-lf-controller-public", env_text)
            self.assertIn("HERMES_LANGFUSE_SECRET_KEY=sk-lf-controller-secret", env_text)
            self.assertNotIn("sk-lf-controller-secret", json.dumps(result))
            self.assertTrue(result["restarted"])
            restart.assert_called_once()
            credentials_path = (
                state_root / "controller-home/.config/opencode/opencode-langfuse.json"
            )
            config_path = state_root / "controller-home/.config/opencode/opencode.json"
            self.assertTrue(credentials_path.is_file())
            self.assertEqual(stat.S_IMODE(credentials_path.stat().st_mode), 0o600)
            self.assertEqual(
                json.loads(credentials_path.read_text()),
                {
                    "publicKey": "pk-lf-controller-public",
                    "secretKey": "sk-lf-controller-secret",
                    "baseUrl": "https://cloud.langfuse.com",
                    "environment": "controller",
                },
            )
            self.assertTrue(json.loads(config_path.read_text())["experimental"]["openTelemetry"])
            overview = aidee_admin.inspect_hermes_runtime(
                config_path=home / "config.yaml",
                env_path=home / ".env",
            )
            self.assertNotIn("pk-lf-controller-public", json.dumps(overview))
            self.assertNotIn("sk-lf-controller-secret", json.dumps(overview))
            uninstall = dict(request)
            uninstall["request_id"] = "uninstall-controller-opencode-soul"
            uninstall["action"] = "uninstall"
            restart.reset_mock()
            with (
                patches[0],
                patches[1],
                patches[2],
                patches[3],
                patches[5],
                mock.patch.object(aidee_admin, "schedule_controller_restart", restart),
                mock.patch.object(
                    aidee_admin,
                    "controller_home_dir",
                    return_value=state_root / "controller-home",
                ),
                mock.patch.object(aidee_admin, "run", side_effect=fake_run),
                mock.patch.object(aidee_admin.shutil, "which", return_value=None),
            ):
                disabled = aidee_admin.set_controller_opencode(uninstall)
            self.assertTrue(disabled["restarted"])
            restart.assert_called_once()
            self.assertNotIn("AIDEE:OPENCODE-DELEGATION:BEGIN", soul.read_text())
            env_after = (home / ".env").read_text()
            self.assertIn("HERMES_LANGFUSE_SECRET_KEY=sk-lf-controller-secret", env_after)
            self.assertNotIn("OTEL_EXPORTER_OTLP_ENDPOINT=", env_after)
            self.assertFalse((home / "skills/opencode/SKILL.md").is_file())
            self.assertFalse(credentials_path.exists())


