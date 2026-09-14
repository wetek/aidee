#!/usr/bin/env python3
import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "platform/setup"))
import onboarding_state  # noqa: E402


NOW = "2026-09-14T03:00:00+00:00"


class OnboardingStatusTests(unittest.TestCase):
    def write(self, directory, value):
        path = Path(directory) / "status.json"
        path.write_text(json.dumps(value))
        return path

    def resolve_all(self, path, role="controller", kind=None, config=None):
        with onboarding_state.locked_status(path, role, kind, config, NOW) as state:
            steps = list(state["steps"])
        for step_id in steps:
            with onboarding_state.locked_status(
                path, role, kind, config, NOW
            ) as state:
                step = dict(state["steps"][step_id])
            if step["status"] in onboarding_state.RESOLVED_STATUSES:
                continue
            if step["evidence_policy"] == "external":
                source = "owner_confirmation"
            else:
                source = "reconciler"
            onboarding_state.mark_step(
                path,
                role,
                step_id,
                "completed",
                assistant_kind=kind,
                config=config,
                evidence_source=source,
                evidence_detail="verified onboarding step",
                now=NOW,
            )

    def test_legacy_controller_migration_preserves_only_verified_facts(self):
        legacy = {
            "telegram_owner_authorized": True,
            "telegram_profile_status": "deferred",
            "update_check_status": "active",
            "dashboard_verified": True,
        }
        migrated = onboarding_state.migrate_status(legacy, "controller", now=NOW)
        self.assertEqual(migrated["schema_version"], 2)
        self.assertEqual(
            migrated["steps"]["owner_authorization"]["status"], "completed"
        )
        self.assertEqual(
            migrated["steps"]["dashboard_phone_access"]["status"], "completed"
        )
        self.assertEqual(
            migrated["steps"]["telegram_profile_avatar"]["status"], "pending"
        )
        self.assertEqual(migrated["steps"]["default_crons"]["status"], "pending")
        self.assertEqual(migrated["steps"]["model_messaging"]["status"], "pending")

    def test_legacy_profile_completion_does_not_infer_menu_completion(self):
        migrated = onboarding_state.migrate_status(
            {"telegram_profile_status": "applied"},
            "controller",
            now=NOW,
        )
        self.assertEqual(
            migrated["steps"]["telegram_profile_avatar"]["status"],
            "completed",
        )
        self.assertEqual(
            migrated["steps"]["telegram_menu_button"]["status"],
            "pending",
        )

    def test_legacy_assistant_migration_maps_terminal_states(self):
        legacy = {
            "schema_version": 1,
            "steps": {
                "identity": {"status": "complete"},
                "dashboard": {"status": "not_applicable", "note": "disabled"},
                "model": {"status": "deferred"},
                "telegram": {"status": "skipped", "note": "owner choice"},
                "repository": {"status": "complete"},
            },
        }
        migrated = onboarding_state.migrate_status(
            legacy, "assistant", "coding", now=NOW
        )
        self.assertEqual(migrated["steps"]["identity"]["status"], "completed")
        self.assertEqual(
            migrated["steps"]["dashboard_branding"]["status"], "skipped"
        )
        self.assertEqual(migrated["steps"]["model_messaging"]["status"], "pending")
        self.assertEqual(
            migrated["steps"]["owner_authorization"]["status"], "skipped"
        )
        self.assertEqual(
            migrated["steps"]["telegram_menu_button"]["status"], "pending"
        )
        self.assertEqual(migrated["steps"]["repositories"]["status"], "completed")
        self.assertEqual(
            migrated["steps"]["coding_tools_scripts"]["status"], "pending"
        )

    def test_legacy_telegram_completion_does_not_complete_new_profile_work(self):
        legacy = {
            "schema_version": 1,
            "steps": {"telegram": {"status": "complete"}},
        }
        migrated = onboarding_state.migrate_status(
            legacy, "assistant", "personal", now=NOW
        )
        self.assertEqual(
            migrated["steps"]["owner_authorization"]["status"], "completed"
        )
        self.assertEqual(
            migrated["steps"]["telegram_profile_avatar"]["status"], "pending"
        )
        self.assertEqual(
            migrated["steps"]["telegram_menu_button"]["status"], "pending"
        )

    def test_completed_and_skipped_states_do_not_prompt(self):
        for terminal in ("completed", "skipped"):
            with self.subTest(terminal=terminal), tempfile.TemporaryDirectory() as tmp:
                path = self.write(
                    tmp, onboarding_state.default_status("controller", now=NOW)
                )
                with onboarding_state.locked_status(
                    path, "controller", now=NOW
                ) as state:
                    for step in state["steps"].values():
                        step["status"] = terminal
                        if terminal == "skipped":
                            step["reason"] = "owner confirmed skip"
                result = onboarding_state.gate(
                    path, "controller", action="decide", now=NOW
                )
                self.assertEqual(result["decision"], "complete")

    def test_pending_prompts_once_and_not_now_suppresses_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            first = onboarding_state.gate(
                path, "controller", action="decide", now=NOW
            )
            second = onboarding_state.gate(
                path, "controller", action="decide", now=NOW
            )
            answered = onboarding_state.gate(
                path, "controller", action="not_now", now=NOW
            )
            third = onboarding_state.gate(
                path, "controller", action="decide", now=NOW
            )
            self.assertEqual(first["decision"], "offer")
            self.assertEqual(second["decision"], "silent")
            self.assertEqual(answered["prompt"]["response"], "not_now")
            self.assertEqual(third["decision"], "silent")

    def test_manual_reopen_allows_a_new_offer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            onboarding_state.gate(path, "controller", action="decide", now=NOW)
            onboarding_state.gate(path, "controller", action="not_now", now=NOW)
            reopened = onboarding_state.gate(
                path, "controller", action="reopen", now=NOW
            )
            result = onboarding_state.gate(
                path, "controller", action="decide", now=NOW
            )
            self.assertEqual(reopened["decision"], "offer")
            self.assertIsNone(reopened["prompt"]["last_prompted_at"])
            self.assertEqual(result["decision"], "offer")

    def test_new_required_step_changes_prompt_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            onboarding_state.gate(path, "controller", action="decide", now=NOW)
            onboarding_state.gate(path, "controller", action="not_now", now=NOW)
            extra = ("new_release_check", True, "local")
            with mock.patch.object(
                onboarding_state,
                "CONTROLLER_STEPS",
                onboarding_state.CONTROLLER_STEPS + (extra,),
            ):
                result = onboarding_state.gate(
                    path, "controller", action="decide", now=NOW
                )
            self.assertEqual(result["decision"], "offer")

    def test_prompt_version_change_allows_one_new_offer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            onboarding_state.gate(path, "controller", action="decide", now=NOW)
            onboarding_state.gate(path, "controller", action="not_now", now=NOW)
            with mock.patch.object(
                onboarding_state,
                "PROMPT_VERSION",
                onboarding_state.PROMPT_VERSION + 1,
            ):
                first = onboarding_state.gate(
                    path, "controller", action="decide", now=NOW
                )
                second = onboarding_state.gate(
                    path, "controller", action="decide", now=NOW
                )
            self.assertEqual(first["decision"], "offer")
            self.assertEqual(second["decision"], "silent")

    def test_schema_bump_preserves_existing_step_facts_and_reoffers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            state = onboarding_state.default_status("controller", now=NOW)
            state["steps"]["dashboard_phone_access"]["status"] = "completed"
            state["steps"]["dashboard_phone_access"]["evidence"] = [
                {
                    "source": "owner_confirmation",
                    "detail": "owner verified private dashboard access",
                    "recorded_at": NOW,
                }
            ]
            path.write_text(json.dumps(state))
            onboarding_state.gate(
                path, "controller", action="decide", now=NOW
            )
            onboarding_state.gate(
                path, "controller", action="not_now", now=NOW
            )
            with mock.patch.object(
                onboarding_state,
                "SCHEMA_VERSION",
                onboarding_state.SCHEMA_VERSION + 1,
            ):
                result = onboarding_state.gate(
                    path, "controller", action="decide", now=NOW
                )
                migrated = json.loads(path.read_text())
            self.assertEqual(result["decision"], "offer")
            self.assertEqual(
                migrated["steps"]["dashboard_phone_access"]["status"],
                "completed",
            )

    def test_newly_applicable_step_reopens_instead_of_preserving_auto_skip(self):
        disabled = {
            "telegram_enabled": False,
            "dashboard_menu_enabled": False,
        }
        state = onboarding_state.default_status(
            "assistant", "personal", disabled, now=NOW
        )
        migrated = onboarding_state.migrate_status(
            state,
            "assistant",
            "personal",
            {"telegram_enabled": True, "dashboard_menu_enabled": True},
            now=NOW,
        )
        self.assertEqual(
            migrated["steps"]["owner_authorization"]["status"], "pending"
        )
        self.assertEqual(
            migrated["steps"]["telegram_profile_avatar"]["status"], "pending"
        )

    def test_optional_steps_must_resolve_but_do_not_trigger_offer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            state = onboarding_state.default_status("assistant", "personal", now=NOW)
            path.write_text(json.dumps(state))
            with onboarding_state.locked_status(
                path, "assistant", "personal", now=NOW
            ) as current:
                for step in current["steps"].values():
                    if step["required"]:
                        step["status"] = "completed"
            result = onboarding_state.gate(
                path, "assistant", "personal", action="decide", now=NOW
            )
            self.assertEqual(result["decision"], "silent")
            self.assertFalse(result["rollup"]["complete"])
            self.assertTrue(result["rollup"]["incomplete_optional"])
            self.resolve_all(path, "assistant", "personal")
            complete = onboarding_state.gate(
                path, "assistant", "personal", action="inspect", now=NOW
            )
            self.assertEqual(complete["decision"], "complete")

    def test_role_and_kind_step_policy(self):
        controller = onboarding_state.default_status("controller", now=NOW)
        coding = onboarding_state.default_status("assistant", "coding", now=NOW)
        personal = onboarding_state.default_status("assistant", "personal", now=NOW)
        disabled = onboarding_state.default_status(
            "assistant",
            "personal",
            {"telegram_enabled": False, "dashboard_menu_enabled": False},
            now=NOW,
        )
        self.assertIn("dashboard_phone_access", controller["steps"])
        self.assertTrue(coding["steps"]["repositories"]["required"])
        self.assertFalse(personal["steps"]["repositories"]["required"])
        self.assertEqual(
            disabled["steps"]["owner_authorization"]["status"], "skipped"
        )

    def test_concurrent_decisions_return_at_most_one_offer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"

            def decide(_):
                return onboarding_state.gate(
                    path, "controller", action="decide"
                )["decision"]

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                decisions = list(executor.map(decide, range(16)))
            self.assertEqual(decisions.count("offer"), 1)

    def test_concurrent_processes_return_exactly_one_offer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            script = (
                "import sys;"
                f"sys.path.insert(0, {str(ROOT / 'platform/setup')!r});"
                "from onboarding_state import gate;"
                f"print(gate({str(path)!r}, 'controller', action='decide')['decision'])"
            )
            processes = [
                subprocess.Popen(
                    [sys.executable, "-c", script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for _ in range(16)
            ]
            results = [process.communicate() for process in processes]
            self.assertTrue(
                all(process.returncode == 0 for process in processes),
                results,
            )
            decisions = [stdout.strip() for stdout, _ in results]
            self.assertEqual(decisions.count("offer"), 1)

    def test_completion_and_skip_require_accepted_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            with self.assertRaises(onboarding_state.OnboardingError):
                onboarding_state.mark_step(
                    path, "controller", "owner_authorization", "completed"
                )
            with self.assertRaises(onboarding_state.OnboardingError):
                onboarding_state.mark_step(
                    path,
                    "controller",
                    "owner_authorization",
                    "completed",
                    evidence_source="reconciler",
                    evidence_detail="cannot prove an external action",
                )
            with self.assertRaises(onboarding_state.OnboardingError):
                onboarding_state.mark_step(
                    path,
                    "controller",
                    "telegram_profile_avatar",
                    "skipped",
                    evidence_source="owner_confirmation",
                    evidence_detail="owner choice",
                )
            onboarding_state.mark_step(
                path,
                "controller",
                "telegram_profile_avatar",
                "skipped",
                evidence_source="owner_confirmation",
                evidence_detail="owner choice",
                reason="Owner kept the existing profile",
            )

    def test_notes_reject_secret_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            for detail in (
                "token=should-not-be-stored",
                "123456789:abcdefghijklmnopqrstuvwxyz123456",
            ):
                with self.subTest(detail=detail), self.assertRaises(
                    onboarding_state.OnboardingError
                ):
                    onboarding_state.mark_step(
                        Path(tmp) / "status.json",
                        "controller",
                        "identity_skin",
                        "completed",
                        evidence_source="reconciler",
                        evidence_detail=detail,
                    )

    def test_locked_status_rejects_symlinked_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            outside.mkdir()
            (root / "linked").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(
                onboarding_state.OnboardingError, "symlink"
            ):
                onboarding_state.gate(
                    root / "linked/status.json",
                    "controller",
                    action="decide",
                )
            self.assertEqual(list(outside.iterdir()), [])

    def test_command_status_path_is_confined_to_configured_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = (
                root / "fleet/controller/CONTROLLER_ONBOARDING_STATUS.json"
            )
            expected.parent.mkdir(parents=True)
            assistant_host = (
                root
                / "runtime/assistants/control-tower/data/aidee/onboarding-status.json"
            )
            assistant_host.parent.mkdir(parents=True)
            with mock.patch.dict(os.environ, {"AIDEE_STATE_DIR": str(root)}):
                self.assertEqual(
                    onboarding_state.validate_status_path(expected, "controller"),
                    expected,
                )
                with self.assertRaisesRegex(
                    onboarding_state.OnboardingError, "approved"
                ):
                    onboarding_state.validate_status_path(
                        root / "other.json", "controller"
                    )
                self.assertEqual(
                    onboarding_state.validate_status_path(
                        assistant_host, "assistant"
                    ),
                    assistant_host,
                )
                self.assertEqual(
                    onboarding_state.validate_status_path(
                        onboarding_state.ASSISTANT_STATUS_PATH, "assistant"
                    ),
                    onboarding_state.ASSISTANT_STATUS_PATH,
                )
                with self.assertRaisesRegex(
                    onboarding_state.OnboardingError, "approved"
                ):
                    onboarding_state.validate_status_path(
                        root / "runtime/assistants/../etc/passwd", "assistant"
                    )
                with self.assertRaisesRegex(
                    onboarding_state.OnboardingError, "approved"
                ):
                    onboarding_state.validate_status_path(
                        root / "runtime/assistants/bad_id/data/aidee/onboarding-status.json",
                        "assistant",
                    )

    def test_marker_cli_rejects_untrusted_reconciler_evidence(self):
        if os.geteuid() == 0:
            self.skipTest("root is the trusted reconciler authority")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status = (
                root / "fleet/controller/CONTROLLER_ONBOARDING_STATUS.json"
            )
            status.parent.mkdir(parents=True)
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "platform/setup/mark-onboarding-step.py"),
                    "--status-file",
                    str(status),
                    "--role",
                    "controller",
                    "--step",
                    "identity_skin",
                    "--status",
                    "completed",
                    "--evidence-source",
                    "reconciler",
                    "--evidence-detail",
                    "local state converged",
                ],
                env={**os.environ, "AIDEE_STATE_DIR": str(root)},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("trusted root authority", result.stderr)

    def test_legacy_profile_skip_tool_resolves_profile_and_menu_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status = (
                root / "fleet/controller/CONTROLLER_ONBOARDING_STATUS.json"
            )
            status.parent.mkdir(parents=True)
            status.write_text(
                json.dumps(onboarding_state.default_status("controller"))
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "platform/controller-tools"
                        / "set-telegram-profile-status.py"
                    ),
                    "--status-file",
                    str(status),
                    "--status",
                    "skipped",
                    "--confirmed",
                ],
                env={**os.environ, "AIDEE_STATE_DIR": str(root)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            updated = json.loads(status.read_text())
            self.assertEqual(
                updated["steps"]["telegram_profile_avatar"]["status"],
                "skipped",
            )
            self.assertEqual(
                updated["steps"]["telegram_menu_button"]["status"],
                "skipped",
            )


if __name__ == "__main__":
    unittest.main()
