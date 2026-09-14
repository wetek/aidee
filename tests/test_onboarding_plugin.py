#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "platform/hermes-plugins/aidee-onboarding/__init__.py"
MANIFEST = ROOT / "platform/hermes-plugins/aidee-onboarding/plugin.yaml"


def load_plugin():
    spec = importlib.util.spec_from_file_location("aidee_onboarding_plugin", PLUGIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OnboardingPluginTests(unittest.TestCase):
    def test_manifest_declares_the_pre_llm_hook(self):
        import yaml

        manifest = yaml.safe_load(MANIFEST.read_text())
        self.assertEqual(manifest["name"], "aidee-onboarding")
        self.assertIn("pre_llm_call", manifest.get("provides_hooks") or [])

    def test_offer_context_names_the_gate_command(self):
        plugin = load_plugin()
        assistant = plugin.offer_context("assistant", "coding", "identity")
        controller = plugin.offer_context("controller", None, "model_messaging")
        self.assertIn("AIDEE ONBOARDING OFFER", assistant)
        self.assertIn("--mode decide", assistant)
        self.assertIn("identity", assistant)
        self.assertIn("Resume now", assistant)
        self.assertIn("model_messaging", controller)
        self.assertIn("CONTROLLER_ONBOARDING_STATUS.json", controller)

    def test_pre_llm_call_injects_until_the_owner_answers(self):
        plugin = load_plugin()
        with tempfile.TemporaryDirectory() as tmp:
            status = Path(tmp) / "onboarding-status.json"
            status.write_text(
                json.dumps({"assistant_kind": "coding", "schema_version": 2})
            )
            with mock.patch.object(plugin, "ASSISTANT_STATUS", status):
                with mock.patch.object(
                    plugin,
                    "load_gate",
                    return_value=lambda *args, **kwargs: {
                        "decision": "offer",
                        "first_incomplete_required": "identity",
                    },
                ):
                    offered = plugin.on_pre_llm_call(user_message="hi")
                with mock.patch.object(
                    plugin,
                    "load_gate",
                    return_value=lambda *args, **kwargs: {
                        "decision": "silent",
                        "first_incomplete_required": "identity",
                        "rollup": {"incomplete_required": ["identity"]},
                        "prompt": {"response": None},
                    },
                ):
                    unanswered = plugin.on_pre_llm_call(user_message="hi")
                with mock.patch.object(
                    plugin,
                    "load_gate",
                    return_value=lambda *args, **kwargs: {
                        "decision": "silent",
                        "first_incomplete_required": "identity",
                        "rollup": {"incomplete_required": ["identity"]},
                        "prompt": {"response": "not_now"},
                    },
                ):
                    declined = plugin.on_pre_llm_call(user_message="hi")
        self.assertIn("identity", offered["context"])
        self.assertIn("identity", unanswered["context"])
        self.assertIsNone(declined)

    def test_pre_llm_call_continues_after_resume_now(self):
        plugin = load_plugin()
        with tempfile.TemporaryDirectory() as tmp:
            status = Path(tmp) / "onboarding-status.json"
            status.write_text(
                json.dumps({"assistant_kind": "coding", "schema_version": 2})
            )
            with mock.patch.object(plugin, "ASSISTANT_STATUS", status):
                with mock.patch.object(
                    plugin,
                    "load_gate",
                    return_value=lambda *args, **kwargs: {
                        "decision": "silent",
                        "first_incomplete_required": "owner_authorization",
                        "rollup": {"incomplete_required": ["owner_authorization"]},
                        "prompt": {"response": "resume_now"},
                    },
                ):
                    continued = plugin.on_pre_llm_call(user_message="hi")
        self.assertIn("AIDEE ONBOARDING CONTINUE", continued["context"])
        self.assertIn("owner_authorization", continued["context"])
        self.assertIn("dashboard.public_url", continued["context"])

    def test_pre_llm_call_fails_open(self):
        plugin = load_plugin()
        with mock.patch.object(plugin, "resolve_target", side_effect=RuntimeError):
            self.assertIsNone(plugin.on_pre_llm_call())


if __name__ == "__main__":
    unittest.main()
