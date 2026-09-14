#!/usr/bin/env python3
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


ROOT = Path(__file__).resolve().parents[1]
RECONCILER_PATH = ROOT / "platform/update/reconcile.py"
STATE_PATH = ROOT / "platform/admin/assistant_state.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reconcile = load_module("aidee_reconcile", RECONCILER_PATH)
assistant_state = load_module("assistant_state_test", STATE_PATH)


class FakeDockerRunner:
    def __init__(self, fail_new_start=False):
        self.images = {
            "aidee-pilot": "sha256:old",
            "aidee-pilot-dashboard-proxy": "sha256:old",
        }
        self.fail_new_start = fail_new_start
        self.failed = False

    def result(self, command, code=0, stdout="", stderr=""):
        return subprocess.CompletedProcess(command, code, stdout, stderr)

    def run(self, command, check=True, stream=False):
        if command[:2] == ["docker", "inspect"]:
            name = command[2]
            if name not in self.images:
                return self.result(command, 1)
            if ".State.Health" in command[-1]:
                return self.result(command, stdout="healthy\n")
            return self.result(command, stdout=self.images[name] + "\n")
        if command[:2] == ["docker", "rename"]:
            self.images[command[3]] = self.images.pop(command[2])
            return self.result(command)
        if command[:2] == ["docker", "create"]:
            name = command[command.index("--name") + 1]
            self.images[name] = "sha256:new"
            return self.result(command)
        if command[:2] == ["docker", "rm"]:
            self.images.pop(command[-1], None)
            return self.result(command)
        if command[:2] == ["docker", "start"]:
            name = command[2]
            if (
                self.fail_new_start
                and name == "aidee-pilot"
                and self.images.get(name) == "sha256:new"
                and not self.failed
            ):
                self.failed = True
                raise reconcile.ReconcileError("injected start failure")
            return self.result(command)
        if command[:1] == ["curl"]:
            return self.result(command, stdout="200")
        return self.result(command)


def legacy_registry():
    return {
        "schema_version": 1,
        "platform": {
            "repository": "https://example.com/aidee.git",
            "default_version": "0.1.0",
        },
        "controller": {"id": "aidee-controller", "state_path": "controller"},
        "assistants": [
            {
                "id": "pilot",
                "name": "Pilot",
                "kind": "coding",
                "status": "provisioning",
                "platform_version": "0.1.0",
                "state_path": "assistants/pilot",
                "container_name": "aidee-pilot",
                "dashboard": {"host_port": 9201},
                "resources": {
                    "cpu_limit": 0.75,
                    "memory_mb": 2048,
                    "storage_gb": 20,
                    "pids_limit": 512,
                },
                "image": {
                    "aidee_version": "v0.1.0-alpha.5",
                    "image_id": "sha256:" + "a" * 64,
                },
            }
        ],
    }


def create_tagged_candidate(root):
    candidate = root / "candidate"
    candidate.mkdir()
    (candidate / "LATEST").write_text("v0.1.0-alpha.13\n")
    commands = [
        ["git", "init", "-q"],
        ["git", "config", "user.email", "tests@example.invalid"],
        ["git", "config", "user.name", "Aidee Tests"],
        ["git", "add", "LATEST"],
        ["git", "commit", "-q", "-m", "test release"],
        ["git", "tag", "v0.1.0-alpha.13"],
    ]
    for command in commands:
        subprocess.run(command, cwd=candidate, check=True)
    return candidate


class FleetUpdateTests(unittest.TestCase):
    def test_preview_lists_actions_without_applying(self):
        actions = reconcile.action_plan(legacy_registry(), "v0.1.0-alpha.13")
        self.assertIn("activate exact host release v0.1.0-alpha.13", actions)
        self.assertIn("reconcile and replace assistant pilot", actions)
        self.assertTrue(actions[-1].startswith("verify host"))

    def test_preview_interface_does_not_change_fleet_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = create_tagged_candidate(root)
            state_root = root / "state"
            fleet = state_root / "fleet"
            fleet.mkdir(parents=True)
            registry = fleet / "registry.yaml"
            registry.write_text(yaml.safe_dump(legacy_registry()))
            before = registry.read_bytes()
            result = subprocess.run(
                [
                    sys.executable,
                    str(RECONCILER_PATH),
                    "--release", "v0.1.0-alpha.13",
                    "--candidate", str(candidate),
                    "--mode", "preview",
                    "--state-root", str(state_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Preview complete", result.stdout)
            self.assertEqual(registry.read_bytes(), before)

    def test_preview_rejects_a_dirty_or_untagged_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = create_tagged_candidate(root)
            (candidate / "untracked").write_text("not part of the release\n")
            with self.assertRaises(reconcile.ReconcileError):
                reconcile.validate_candidate(candidate, "v0.1.0-alpha.13")

    def test_apply_requires_explicit_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "LATEST").write_text("v0.1.0-alpha.13\n")
            state = root / "state/fleet"
            state.mkdir(parents=True)
            (state / "registry.yaml").write_text(yaml.safe_dump(legacy_registry()))
            with mock.patch(
                "sys.argv",
                [
                    "reconcile.py",
                    "--release", "v0.1.0-alpha.13",
                    "--candidate", str(root),
                    "--mode", "apply",
                    "--state-root", str(root / "state"),
                ],
            ):
                self.assertEqual(reconcile.main(), 2)

    def test_migration_ledger_and_backup_are_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary) / "state"
            fleet = state_root / "fleet"
            fleet.mkdir(parents=True)
            registry = fleet / "registry.yaml"
            registry.write_text(yaml.safe_dump(legacy_registry()))
            controller_status = (
                state_root
                / "fleet/controller/CONTROLLER_ONBOARDING_STATUS.json"
            )
            controller_status.parent.mkdir()
            controller_status.write_text(
                json.dumps({"telegram_profile_status": "deferred"})
            )
            assistant_status = (
                state_root
                / "runtime/assistants/pilot/data/aidee/onboarding-status.json"
            )
            assistant_status.parent.mkdir(parents=True)
            assistant_status.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "steps": {"model": {"status": "deferred"}},
                    }
                )
            )

            first = reconcile.run_migrations(ROOT, state_root)
            first_result = registry.read_text()
            second = reconcile.run_migrations(ROOT, state_root)

            self.assertEqual(
                first,
                [
                    "001_alpha13_onboarding_registry",
                    "002_alpha14_onboarding_status",
                    "003_alpha18_relocate_home_repos",
                ],
            )
            self.assertEqual(second, [])
            self.assertEqual(registry.read_text(), first_result)
            self.assertTrue(
                (
                    state_root
                    / "backups/migrations/001_alpha13_onboarding_registry/registry.yaml"
                ).is_file()
            )
            self.assertTrue(
                (
                    state_root
                    / "migrations/001_alpha13_onboarding_registry.json"
                ).is_file()
            )
            controller_backup = (
                state_root
                / "backups/migrations/002_alpha14_onboarding_status"
                / "controller/CONTROLLER_ONBOARDING_STATUS.json"
            )
            assistant_backup = (
                state_root
                / "backups/migrations/002_alpha14_onboarding_status"
                / "assistants/pilot/onboarding-status.json"
            )
            self.assertEqual(controller_backup.read_bytes(), controller_status.read_bytes())
            self.assertEqual(assistant_backup.read_bytes(), assistant_status.read_bytes())
            self.assertEqual(controller_backup.stat().st_mode & 0o777, 0o600)
            self.assertEqual(assistant_backup.stat().st_mode & 0o777, 0o600)

    def test_invalid_legacy_status_is_backed_up_before_migration_stops(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary) / "state"
            fleet = state_root / "fleet"
            fleet.mkdir(parents=True)
            (fleet / "registry.yaml").write_text(
                yaml.safe_dump({"assistants": []})
            )
            status = (
                state_root
                / "fleet/controller/CONTROLLER_ONBOARDING_STATUS.json"
            )
            status.parent.mkdir()
            status.write_text("{invalid")
            with self.assertRaisesRegex(RuntimeError, "status is invalid"):
                reconcile.run_migrations(ROOT, state_root)
            backup = (
                state_root
                / "backups/migrations/002_alpha14_onboarding_status"
                / "controller/CONTROLLER_ONBOARDING_STATUS.json"
            )
            self.assertEqual(backup.read_bytes(), status.read_bytes())
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)

    def test_legacy_fixture_reconciliation_preserves_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            fleet = state_root / "fleet/assistants/pilot"
            runtime = state_root / "runtime/assistants/pilot/data"
            fleet.mkdir(parents=True)
            runtime.mkdir(parents=True)
            config = runtime / "config.yaml"
            env = runtime / ".env"
            config.write_text("model: owner-selected\n")
            env.write_text("TOKEN=preserved\n")

            with mock.patch("os.chown"):
                changed = assistant_state.reconcile_assistant_files(
                    legacy_registry()["assistants"][0],
                    "Test Owner",
                    fleet,
                    runtime,
                    gid=os.getgid(),
                )
                second = assistant_state.reconcile_assistant_files(
                    legacy_registry()["assistants"][0],
                    "Test Owner",
                    fleet,
                    runtime,
                    gid=os.getgid(),
                )

            self.assertTrue(changed)
            self.assertEqual(second, [])
            repaired_config = yaml.safe_load(config.read_text())
            self.assertEqual(repaired_config["model"], "owner-selected")
            self.assertEqual(repaired_config["display"]["skin"], "pilot")
            self.assertIn(
                "aidee-onboarding",
                repaired_config["plugins"]["enabled"],
            )
            self.assertTrue(
                (runtime / "plugins/aidee-onboarding/plugin.yaml").is_file()
            )
            self.assertEqual(env.read_text(), "TOKEN=preserved\n")
            self.assertTrue((runtime / "aidee/repos").is_dir())
            self.assertEqual((runtime / "aidee/repos").stat().st_mode & 0o777, 0o770)
            status = json.loads(
                (runtime / "aidee/onboarding-status.json").read_text()
            )
            self.assertFalse(assistant_state.onboarding_complete(status))
            self.assertEqual(
                status["steps"]["dashboard_branding"]["status"], "completed"
            )
            status["steps"]["identity"]["status"] = "completed"
            merged = assistant_state.merge_onboarding_status(status)
            self.assertEqual(merged["steps"]["identity"]["status"], "completed")
            self.assertEqual(
                merged["steps"]["dashboard_branding"]["status"], "completed"
            )
            status["steps"]["identity"]["status"] = "invented"
            repaired = assistant_state.merge_onboarding_status(status)
            self.assertEqual(repaired["steps"]["identity"]["status"], "pending")
            soul = (runtime / "SOUL.md").read_text()
            for expected in (
                "interactive clarify tool",
                "command approvals on Telegram",
                "/opt/data/aidee/repos",
                "Software engineering standards",
                "first incomplete",
                "including greetings",
                "dashboard.public_url",
            ):
                self.assertIn(expected, soul)

    def test_reconciliation_copies_registry_dashboard_url_into_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            fleet = Path(temporary) / "fleet/assistants/pilot"
            runtime = Path(temporary) / "runtime/assistants/pilot/data"
            fleet.mkdir(parents=True)
            runtime.mkdir(parents=True)
            config = runtime / "config.yaml"
            config.write_text(
                "model: owner-selected\ndashboard:\n  public_url: https://old.example.ts.net:8444\n"
            )
            assistant = legacy_registry()["assistants"][0]
            assistant["dashboard"]["url"] = "https://pilot.example.test/"
            with mock.patch("os.chown"):
                assistant_state.reconcile_assistant_files(
                    assistant,
                    "Test Owner",
                    fleet,
                    runtime,
                    gid=os.getgid(),
                )
            repaired = yaml.safe_load(config.read_text())
            self.assertEqual(
                repaired["dashboard"]["public_url"],
                "https://pilot.example.test",
            )
            self.assertEqual(repaired["model"], "owner-selected")

    def test_reconciliation_relocates_home_git_checkouts_into_aidee_repos(self):
        with tempfile.TemporaryDirectory() as temporary:
            fleet = Path(temporary) / "fleet/assistants/pilot"
            runtime = Path(temporary) / "runtime/assistants/pilot/data"
            fleet.mkdir(parents=True)
            runtime.mkdir(parents=True)
            leftover = runtime / "control-tower"
            leftover.mkdir()
            (leftover / ".git").mkdir()
            (leftover / "README.md").write_text("old clone\n")
            duplicate = runtime / "workspace" / "other"
            duplicate.mkdir(parents=True)
            (duplicate / ".git").mkdir()
            existing = runtime / "aidee" / "repos" / "other"
            existing.mkdir(parents=True)
            (existing / "kept.txt").write_text("canonical\n")
            with mock.patch("os.chown"):
                assistant_state.relocate_legacy_home_repos(
                    runtime, gid=os.getgid()
                )
            self.assertFalse(leftover.exists())
            self.assertTrue(
                (runtime / "aidee/repos/control-tower/README.md").is_file()
            )
            self.assertTrue((existing / "kept.txt").is_file())
            legacy = list((runtime / "aidee/legacy-home-repos").iterdir())
            self.assertEqual(len(legacy), 1)
            self.assertTrue((legacy[0] / ".git").exists())
            self.assertFalse((runtime / "workspace").exists())

    def test_reconciliation_relocates_when_canonical_name_is_a_dangling_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "runtime/assistants/control-tower/data"
            leftover = runtime / "control-tower"
            leftover.mkdir(parents=True)
            (leftover / ".git").mkdir()
            (leftover / "README.md").write_text("old clone\n")
            dest = runtime / "aidee" / "repos" / "control-tower"
            dest.parent.mkdir(parents=True)
            dest.symlink_to("/opt/data/control-tower")
            with mock.patch("os.chown"):
                moved = assistant_state.relocate_legacy_home_repos(
                    runtime, gid=os.getgid()
                )
            self.assertFalse(leftover.exists())
            canonical = runtime / "aidee/repos/control-tower"
            self.assertTrue((canonical / "README.md").is_file())
            self.assertFalse(canonical.is_symlink())
            legacy = list((runtime / "aidee/legacy-home-repos").iterdir())
            self.assertEqual(len(legacy), 1)
            self.assertTrue(legacy[0].is_symlink())
            self.assertTrue(any(str(canonical) == item for item in moved))

    def test_reconciliation_relocates_when_canonical_name_is_a_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "runtime/assistants/control-tower/data"
            leftover = runtime / "control-tower"
            leftover.mkdir(parents=True)
            (leftover / ".git").mkdir()
            (leftover / "README.md").write_text("old clone\n")
            dest = runtime / "aidee" / "repos" / "control-tower"
            dest.parent.mkdir(parents=True)
            dest.write_text("not a checkout\n")
            with mock.patch("os.chown"):
                assistant_state.relocate_legacy_home_repos(
                    runtime, gid=os.getgid()
                )
            self.assertFalse(leftover.exists())
            canonical = runtime / "aidee/repos/control-tower"
            self.assertTrue((canonical / "README.md").is_file())
            legacy = list((runtime / "aidee/legacy-home-repos").iterdir())
            self.assertEqual(len(legacy), 1)
            self.assertTrue(legacy[0].is_file())

    def test_reconciliation_rejects_assistant_controlled_directory_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fleet = root / "fleet"
            runtime = root / "runtime"
            outside = root / "outside"
            fleet.mkdir()
            runtime.mkdir()
            outside.mkdir()
            (runtime / "aidee").symlink_to(outside, target_is_directory=True)

            with mock.patch("os.chown"):
                with self.assertRaisesRegex(RuntimeError, "symlink"):
                    assistant_state.reconcile_assistant_files(
                        legacy_registry()["assistants"][0],
                        "Test Owner",
                        fleet,
                        runtime,
                        gid=os.getgid(),
                    )
            self.assertEqual(list(outside.iterdir()), [])

    def test_create_and_sync_paths_use_central_instruction_generator(self):
        admin_source = (
            ROOT / "platform/admin/aidee_admin.py"
        ).read_text()
        sync_source = (
            ROOT / "platform/controller-tools/sync-fleet-assistants.py"
        ).read_text()
        self.assertNotIn("def build_soul_document", admin_source)
        self.assertNotIn("def build_soul_document", sync_source)
        self.assertIn("from assistant_state import", admin_source)
        self.assertIn("from assistant_state import", sync_source)

    def test_controller_runtime_applies_patch_as_controller_user(self):
        runtime_source = (
            ROOT / "platform/scripts/update-controller-runtime.sh"
        ).read_text()
        self.assertIn(
            '"${script_dir}/apply-hermes-runtime-patch.sh" "${active_source}"',
            runtime_source,
        )
        self.assertIn(
            '"${script_dir}/apply-hermes-runtime-patch.sh" "${target}"',
            runtime_source,
        )

    def test_fleet_update_syncs_controller_from_activated_source(self):
        reconcile_source = RECONCILER_PATH.read_text()
        self.assertIn(
            'f"AIDEE_REPOSITORY={source.as_uri()}"',
            reconcile_source,
        )
        self.assertIn(
            '"platform/scripts/apply-hermes-runtime-patch.sh"',
            reconcile_source,
        )
        self.assertIn('"--check"', reconcile_source)
        self.assertIn("SessionDB.update_runtime_context", reconcile_source)
        self.assertIn(
            'command.extend(["--header", f"Host: {hostname}"])',
            reconcile_source,
        )

    def test_registry_image_and_onboarding_updates_are_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry_path = Path(temporary) / "registry.yaml"
            registry = legacy_registry()
            registry_path.write_text(yaml.safe_dump(registry))
            image_id = "sha256:" + "b" * 64
            self.assertTrue(
                reconcile.update_registry(
                    registry_path, registry, "v0.1.0-alpha.13", image_id
                )
            )
            self.assertFalse(
                reconcile.update_registry(
                    registry_path, registry, "v0.1.0-alpha.13", image_id
                )
            )
            updated = yaml.safe_load(registry_path.read_text())
            self.assertEqual(updated["assistants"][0]["image"]["image_id"], image_id)
            self.assertEqual(
                updated["assistants"][0]["onboarding"]["status_path"],
                "aidee/onboarding-status.json",
            )
            self.assertIn(
                "required_remaining", updated["assistants"][0]["onboarding"]
            )
            self.assertIn(
                "optional_remaining", updated["assistants"][0]["onboarding"]
            )

    def test_controller_onboarding_reconciliation_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            controller = state_root / "fleet/controller"
            controller.mkdir(parents=True)
            (controller / "SOUL.md").write_text("legacy instructions\n")
            status_path = reconcile.reconcile_controller_onboarding(
                ROOT, state_root, "Test Owner"
            )
            first_status = status_path.read_bytes()
            first_soul = (controller / "SOUL.md").read_bytes()
            reconcile.reconcile_controller_onboarding(
                ROOT, state_root, "Test Owner"
            )
            self.assertEqual(status_path.read_bytes(), first_status)
            self.assertEqual((controller / "SOUL.md").read_bytes(), first_soul)

    def test_reconcile_proxy_uses_explicit_socat_entrypoint_before_image(self):
        assistant = legacy_registry()["assistants"][0]
        image_id = "sha256:" + "b" * 64
        _, _, _, proxy_command = reconcile.create_container_commands(
            assistant,
            image_id,
            Path("/var/lib/aidee"),
            1000,
        )
        entrypoint_index = proxy_command.index("--entrypoint")
        self.assertEqual(
            proxy_command[entrypoint_index : entrypoint_index + 3],
            ["--entrypoint", "socat", image_id],
        )
        self.assertEqual(
            proxy_command[entrypoint_index + 3 :],
            [
                "TCP-LISTEN:9121,fork,reuseaddr",
                "TCP:127.0.0.1:9119",
            ],
        )

    def test_failed_container_replacement_restores_old_pair(self):
        runner = FakeDockerRunner(fail_new_start=True)
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(reconcile.ReconcileError):
                reconcile.replace_container_pair(
                    runner,
                    legacy_registry()["assistants"][0],
                    "sha256:new",
                    Path(temporary),
                    os.getgid(),
                )
        self.assertEqual(runner.images["aidee-pilot"], "sha256:old")
        self.assertEqual(
            runner.images["aidee-pilot-dashboard-proxy"], "sha256:old"
        )
        self.assertFalse(any("rollback" in name for name in runner.images))

    def test_retained_container_backup_can_roll_back_after_later_failure(self):
        runner = FakeDockerRunner()
        assistant = legacy_registry()["assistants"][0]
        with tempfile.TemporaryDirectory() as temporary:
            self.assertTrue(
                reconcile.replace_container_pair(
                    runner,
                    assistant,
                    "sha256:new",
                    Path(temporary),
                    os.getgid(),
                    retain_backup=True,
                )
            )
            self.assertEqual(runner.images["aidee-pilot"], "sha256:new")
            self.assertIn("aidee-pilot-aidee-rollback", runner.images)
            reconcile.rollback_container_pair(runner, assistant)

        self.assertEqual(runner.images["aidee-pilot"], "sha256:old")
        self.assertEqual(
            runner.images["aidee-pilot-dashboard-proxy"], "sha256:old"
        )

    def test_progress_lines_are_numbered(self):
        output = io.StringIO()
        reporter = reconcile.StepReporter(
            ["build the image", "verify the fleet"], stream=output
        )
        self.assertEqual(reporter.next(), "build the image")
        self.assertEqual(reporter.next(), "verify the fleet")
        self.assertEqual(
            output.getvalue(),
            "[1/2] build the image\n[2/2] verify the fleet\n",
        )

    def test_wait_healthy_prints_while_polling(self):
        class Delayed:
            def __init__(self):
                self.calls = 0

            def run(self, command, check=True, stream=False):
                self.calls += 1
                status = "healthy" if self.calls > 16 else "starting"
                return subprocess.CompletedProcess(command, 0, status + "\n", "")

        clock = [0]

        def now():
            return clock[0]

        def sleep(_seconds):
            clock[0] += 1

        output = io.StringIO()
        with mock.patch("sys.stdout", output):
            reconcile.wait_healthy(
                Delayed(), "aidee-pilot", attempts=20, now=now, sleep=sleep
            )
        self.assertIn("Still waiting for aidee-pilot (15s)...", output.getvalue())

    def test_streamed_command_keeps_zero_exit(self):
        result = reconcile.Runner().run(
            [sys.executable, "-c", "raise SystemExit(0)"], stream=True
        )
        self.assertEqual(result.returncode, 0)

    def test_captured_commands_do_not_inherit_the_terminal(self):
        with mock.patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(["true"], 0, "", "")
            reconcile.Runner().run(["true"])
        kwargs = run.call_args.kwargs
        self.assertTrue(kwargs.get("capture_output"))
        self.assertEqual(kwargs.get("stdin"), subprocess.DEVNULL)

    def test_plugin_enable_skips_the_tool_override_prompt(self):
        install = (
            ROOT / "platform/scripts/install-dashboard-plugins.sh"
        ).read_text()
        sync = (ROOT / "platform/scripts/sync-controller.sh").read_text()
        self.assertIn("plugins enable", install)
        self.assertIn("--no-allow-tool-override", install)
        self.assertNotIn('printf "n\\n"', install)
        self.assertIn("--no-allow-tool-override", sync)
        self.assertNotIn('printf "n\\n"', sync)


if __name__ == "__main__":
    unittest.main()
