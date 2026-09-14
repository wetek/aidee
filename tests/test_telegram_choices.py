#!/usr/bin/env python3
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "platform" / "controller-tools" / "send-telegram-choices.py"
SPEC = importlib.util.spec_from_file_location("telegram_choices", TOOL_PATH)
telegram_choices = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(telegram_choices)


class TelegramChoicesTests(unittest.TestCase):
    def test_payload_uses_one_time_reply_buttons(self):
        payload = telegram_choices.build_send_payload(
            "✨ Aidee v0.1.0-alpha.21 is ready",
            ["Start update", "Not now"],
            "123456",
        )
        self.assertEqual(payload["chat_id"], "123456")
        self.assertEqual(payload["text"], "✨ Aidee v0.1.0-alpha.21 is ready")
        self.assertEqual(
            payload["reply_markup"]["keyboard"],
            [[{"text": "Start update"}, {"text": "Not now"}]],
        )
        self.assertTrue(payload["reply_markup"]["one_time_keyboard"])
        self.assertTrue(payload["reply_markup"]["resize_keyboard"])
        self.assertNotIn("Options:", payload["text"])
        serialized = json.dumps(payload)
        self.assertIn("Start update", serialized)
        self.assertNotIn("inline_keyboard", serialized)

    def test_strips_telegram_delivery_prefix(self):
        self.assertEqual(
            telegram_choices.normalize_chat_id("telegram:123456"),
            "123456",
        )

    def test_requires_at_least_two_choices(self):
        with self.assertRaises(telegram_choices.ChoicesError):
            telegram_choices.build_send_payload("ready", ["Start update"], "1")

    def test_sends_through_injected_requester(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / ".env"
            env_file.write_text(
                "TELEGRAM_BOT_TOKEN=test-token\n"
                "TELEGRAM_HOME_CHANNEL=4242\n"
            )
            captured = {}

            def requester(token, method, payload):
                captured["token"] = token
                captured["method"] = method
                captured["payload"] = payload
                return {"message_id": 9}

            telegram_choices.send_choices(
                "Notice body",
                ["Start update", "Not now"],
                env_file=env_file,
                requester=requester,
            )
            self.assertEqual(captured["token"], "test-token")
            self.assertEqual(captured["method"], "sendMessage")
            self.assertEqual(captured["payload"]["chat_id"], "4242")
            self.assertEqual(
                captured["payload"]["reply_markup"]["keyboard"][0][0]["text"],
                "Start update",
            )

    def test_cli_reads_notice_from_stdin(self):
        with mock.patch.object(telegram_choices, "send_choices") as send:
            send.return_value = {}
            with mock.patch(
                "sys.argv",
                [
                    "send-telegram-choices.py",
                    "--choice",
                    "Start update",
                    "--choice",
                    "Not now",
                ],
            ):
                with mock.patch(
                    "sys.stdin",
                    io.StringIO("✨ Aidee v1 is ready\n"),
                ):
                    self.assertEqual(telegram_choices.main(), 0)
            send.assert_called_once_with(
                "✨ Aidee v1 is ready\n",
                ["Start update", "Not now"],
                env_file=None,
                chat_id=None,
            )


if __name__ == "__main__":
    unittest.main()
