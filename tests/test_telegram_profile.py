#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = (
    ROOT
    / "platform"
    / "controller-tools"
    / "update-telegram-profile.py"
)
SPEC = importlib.util.spec_from_file_location("telegram_profile", TOOL_PATH)
telegram_profile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(telegram_profile)


class FakeTelegramClient:
    def __init__(self, profile):
        self.profile = profile
        self.calls = []
        self.avatar_uploaded = False

    def request(self, method, payload=None):
        self.calls.append((method, payload))
        responses = {
            "getMyName": {"name": self.profile["name"]},
            "getMyShortDescription": {
                "short_description": self.profile["short_description"]
            },
            "getMyDescription": {
                "description": self.profile["description"]
            },
            "getMyCommands": self.profile["commands"],
            "getMe": {"id": 123456789},
            "getUserProfilePhotos": {"total_count": 1, "photos": [[]]},
            "getChatMenuButton": {
                "type": "web_app",
                "text": self.profile["menu_button"]["text"],
                "web_app": {"url": self.profile["menu_button"]["url"]},
            },
        }
        return responses.get(method, True)

    def upload_avatar(self, avatar_path):
        self.avatar_uploaded = Path(avatar_path).is_file()
        return True


class TelegramProfileTests(unittest.TestCase):
    def create_profile(self, directory):
        avatar = directory / "avatar.jpg"
        avatar.write_bytes(b"\xff\xd8\xff\xd9")
        profile = {
            "schema_version": 1,
            "name": "Example Controller",
            "short_description": "Private assistant controller.",
            "description": "Operates an approved Aidee fleet.",
            "commands": [
                {"command": "start", "description": "Start a conversation"}
            ],
            "avatar_path": str(avatar),
            "menu_button": {
                "enabled": True,
                "text": "Open dashboard",
                "url": "https://example.example-tailnet.ts.net",
            },
        }
        path = directory / "profile.json"
        path.write_text(json.dumps(profile))
        return path

    def test_validates_applies_and_verifies_profile(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            profile_path = self.create_profile(directory)
            profile = telegram_profile.load_profile(profile_path, directory)
            client = FakeTelegramClient(profile)

            telegram_profile.apply_profile(client, profile)
            telegram_profile.verify_profile(client, profile)

            self.assertTrue(client.avatar_uploaded)
            methods = [method for method, _ in client.calls]
            self.assertIn("setMyName", methods)
            self.assertIn("setChatMenuButton", methods)
            self.assertIn("getChatMenuButton", methods)

    def test_marks_profile_as_applied(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
            status_path.write_text(
                json.dumps(
                    {
                        "telegram_owner_authorized": True,
                        "telegram_profile_status": "pending",
                        "update_check_status": "active",
                        "dashboard_verified": False,
                    }
                )
            )

            telegram_profile.mark_profile_applied(status_path)

            status = json.loads(status_path.read_text())
            self.assertEqual(status["telegram_profile_status"], "applied")
            self.assertFalse(status["dashboard_verified"])

    def test_rejects_non_https_menu_url(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            profile_path = self.create_profile(directory)
            profile = json.loads(profile_path.read_text())
            profile["menu_button"]["url"] = "http://example.test"
            profile_path.write_text(json.dumps(profile))

            with self.assertRaises(telegram_profile.ProfileError):
                telegram_profile.load_profile(profile_path, directory)

    def test_rejects_avatar_outside_allowed_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            allowed = directory / "allowed"
            allowed.mkdir()
            profile_path = self.create_profile(directory)

            with self.assertRaises(telegram_profile.ProfileError):
                telegram_profile.load_profile(profile_path, allowed)


if __name__ == "__main__":
    unittest.main()
