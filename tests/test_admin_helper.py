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
        (image_dir / "v0.1.0-alpha.10.json").write_text(
            json.dumps(
                {
                    "aidee_version": "v0.1.0-alpha.10",
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
                    return "v0.1.0-alpha.10"
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
            self.assertIn("Communication Standards (Unslop)", soul_text)
            self.assertIn("120 words or fewer", soul_text)
            self.assertNotIn("Software Engineering Standards", soul_text)
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
                    return "v0.1.0-alpha.10"
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
                    return "v0.1.0-alpha.10"
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
                    return "v0.1.0-alpha.10"
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
                    return "v0.1.0-alpha.10"
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
            self.assertEqual(
                telegram_cfg.get("home_channel"),
                {
                    "platform": "telegram",
                    "chat_id": "987654321",
                    "name": "Example Owner",
                    "user_id": "987654321",
                },
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
        request = json.loads(
            (ROOT / "fleet-template" / "assistant-request.json.example").read_text()
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
                request = json.loads(
                    (ROOT / "fleet-template" / "assistant-request.json.example").read_text()
                )
                request["assistant"]["id"] = f"test-{kind}"
                request["assistant"]["name"] = f"Test {kind.capitalize()}"
                request["assistant"]["kind"] = kind

                def fake_run(command):
                    if command[:3] == ["docker", "image", "inspect"]:
                        if "org.opencontainers.image.revision" in command[-1]:
                            return "testcommit"
                        return "v0.1.0-alpha.10"
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
                self.assertIn("Communication Standards (Unslop)", content)
                self.assertIn("120 words or fewer", content)
                self.assertIn("Software Engineering Standards", content)
                self.assertIn("Test-driven verification", content)
                self.assertIn("Systematic debugging", content)
                self.assertIn("Pre-commit code review", content)
                self.assertIn("Clean documentation", content)


if __name__ == "__main__":
    unittest.main()
