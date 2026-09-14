#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "platform/hermes-plugins/aidee-onboarding/__init__.py"


def load_plugin():
    spec = importlib.util.spec_from_file_location("aidee_onboarding_plugin", PLUGIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OnboardingPluginTests(unittest.TestCase):
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

    def test_pre_llm_call_injects_only_when_gate_offers(self):
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
                    },
                ):
                    silent = plugin.on_pre_llm_call(user_message="hi")
        self.assertIn("identity", offered["context"])
        self.assertIsNone(silent)

    def test_pre_llm_call_fails_open(self):
        plugin = load_plugin()
        with mock.patch.object(plugin, "resolve_target", side_effect=RuntimeError):
            self.assertIsNone(plugin.on_pre_llm_call())


if __name__ == "__main__":
    unittest.main()
