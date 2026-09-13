#!/usr/bin/env python3
import argparse
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path


COMMAND = re.compile(r"^[a-z0-9_]{1,32}$")
PROFILE_KEYS = {
    "schema_version",
    "name",
    "short_description",
    "description",
    "commands",
    "avatar_path",
    "menu_button",
}


class ProfileError(ValueError):
    pass


def require_text(value, field, maximum):
    if not isinstance(value, str) or not value.strip():
        raise ProfileError(f"{field} must be non-empty text")
    if len(value) > maximum:
        raise ProfileError(f"{field} must be at most {maximum} characters")


def load_profile(path, avatar_root):
    try:
        profile = json.loads(path.read_text())
    except FileNotFoundError as error:
        raise ProfileError(f"profile file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ProfileError(
            f"invalid JSON at line {error.lineno}, column {error.colno}"
        ) from error

    if not isinstance(profile, dict):
        raise ProfileError("profile must be an object")
    missing = PROFILE_KEYS - set(profile)
    unknown = set(profile) - PROFILE_KEYS
    if missing:
        raise ProfileError(f"profile is missing: {', '.join(sorted(missing))}")
    if unknown:
        raise ProfileError(
            f"profile has unknown fields: {', '.join(sorted(unknown))}"
        )
    if profile["schema_version"] != 1:
        raise ProfileError("schema_version must be 1")

    require_text(profile["name"], "name", 64)
    require_text(profile["short_description"], "short_description", 120)
    require_text(profile["description"], "description", 512)

    commands = profile["commands"]
    if not isinstance(commands, list) or len(commands) > 100:
        raise ProfileError("commands must be a list with at most 100 items")
    command_names = []
    for index, command in enumerate(commands):
        if not isinstance(command, dict) or set(command) != {
            "command",
            "description",
        }:
            raise ProfileError(
                f"commands[{index}] must contain command and description"
            )
        if not isinstance(command["command"], str) or not COMMAND.fullmatch(
            command["command"]
        ):
            raise ProfileError(f"commands[{index}].command is invalid")
        require_text(
            command["description"],
            f"commands[{index}].description",
            256,
        )
        command_names.append(command["command"])
    if len(command_names) != len(set(command_names)):
        raise ProfileError("commands cannot contain duplicates")

    avatar = Path(profile["avatar_path"]).expanduser()
    if avatar.suffix.lower() not in {".jpg", ".jpeg"}:
        raise ProfileError("avatar_path must point to a JPG file")
    if not avatar.is_file():
        raise ProfileError(f"avatar file not found: {avatar}")
    avatar = avatar.resolve()
    allowed_root = avatar_root.expanduser().resolve()
    if not avatar.is_relative_to(allowed_root):
        raise ProfileError(f"avatar must be stored under {allowed_root}")
    if avatar.stat().st_size > 10 * 1024 * 1024:
        raise ProfileError("avatar file must not exceed 10 MB")
    profile["avatar_path"] = str(avatar)

    menu = profile["menu_button"]
    if not isinstance(menu, dict) or set(menu) != {"enabled", "text", "url"}:
        raise ProfileError("menu_button must contain enabled, text, and url")
    if not isinstance(menu["enabled"], bool):
        raise ProfileError("menu_button.enabled must be true or false")
    require_text(menu["text"], "menu_button.text", 64)
    if menu["enabled"]:
        require_text(menu["url"], "menu_button.url", 500)
        if not menu["url"].startswith("https://"):
            raise ProfileError("menu_button.url must use HTTPS")
    elif menu["url"] is not None:
        raise ProfileError("menu_button.url must be null when disabled")

    return profile


def read_env_value(path, key):
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError as error:
        raise ProfileError(f"environment file not found: {path}") from error
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.removeprefix("export ").strip() != key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if value:
            return value
    raise ProfileError(f"{key} is not configured")


class TelegramClient:
    def __init__(self, token):
        self.base_url = f"https://api.telegram.org/bot{token}"

    def request(self, method, payload=None, body=None, content_type=None):
        if body is None:
            body = json.dumps(payload or {}).encode()
            content_type = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}/{method}",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read())
        except urllib.error.HTTPError as error:
            try:
                result = json.loads(error.read())
                detail = result.get("description", f"HTTP {error.code}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                detail = f"HTTP {error.code}"
            raise ProfileError(f"Telegram {method} failed: {detail}") from error
        except urllib.error.URLError as error:
            raise ProfileError(f"Telegram {method} failed: {error.reason}") from error
        if result.get("ok") is not True:
            raise ProfileError(
                f"Telegram {method} failed: {result.get('description', 'unknown error')}"
            )
        return result.get("result")

    def upload_avatar(self, avatar_path):
        avatar = Path(avatar_path)
        boundary = f"aidee-{uuid.uuid4().hex}"
        photo = json.dumps({"type": "static", "photo": "attach://avatar"})
        chunks = [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="photo"\r\n',
            b"Content-Type: application/json\r\n\r\n",
            photo.encode(),
            b"\r\n",
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="avatar"; '
                f'filename="avatar.jpg"\r\n'
            ).encode(),
            (
                f"Content-Type: "
                f"{mimetypes.guess_type(avatar.name)[0] or 'image/jpeg'}\r\n\r\n"
            ).encode(),
            avatar.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
        return self.request(
            "setMyProfilePhoto",
            body=b"".join(chunks),
            content_type=f"multipart/form-data; boundary={boundary}",
        )


def apply_profile(client, profile):
    client.request("setMyName", {"name": profile["name"]})
    client.request(
        "setMyShortDescription",
        {"short_description": profile["short_description"]},
    )
    client.request(
        "setMyDescription",
        {"description": profile["description"]},
    )
    client.request("setMyCommands", {"commands": profile["commands"]})
    client.upload_avatar(profile["avatar_path"])

    menu = profile["menu_button"]
    if menu["enabled"]:
        menu_button = {
            "type": "web_app",
            "text": menu["text"],
            "web_app": {"url": menu["url"]},
        }
    else:
        menu_button = {"type": "commands"}
    client.request("setChatMenuButton", {"menu_button": menu_button})


def verify_profile(client, profile):
    if client.request("getMyName").get("name") != profile["name"]:
        raise ProfileError("Telegram bot name verification failed")
    if (
        client.request("getMyShortDescription").get("short_description")
        != profile["short_description"]
    ):
        raise ProfileError("Telegram short description verification failed")
    if (
        client.request("getMyDescription").get("description")
        != profile["description"]
    ):
        raise ProfileError("Telegram description verification failed")
    if client.request("getMyCommands") != profile["commands"]:
        raise ProfileError("Telegram command verification failed")

    bot = client.request("getMe")
    photos = client.request(
        "getUserProfilePhotos", {"user_id": bot["id"], "limit": 1}
    )
    if photos.get("total_count", 0) < 1:
        raise ProfileError("Telegram avatar verification failed")

    actual_menu = client.request("getChatMenuButton")
    menu = profile["menu_button"]
    expected_type = "web_app" if menu["enabled"] else "commands"
    if actual_menu.get("type") != expected_type:
        raise ProfileError("Telegram menu button verification failed")
    if menu["enabled"] and actual_menu.get("web_app", {}).get("url") != menu["url"]:
        raise ProfileError("Telegram dashboard menu URL verification failed")


def mark_profile_applied(status_path):
    try:
        status = json.loads(status_path.read_text())
    except FileNotFoundError as error:
        raise ProfileError(f"onboarding status not found: {status_path}") from error
    status["telegram_profile_status"] = "applied"
    temporary = status_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(status, indent=2) + "\n")
    os.chmod(temporary, 0o640)
    temporary.replace(status_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--avatar-root", required=True, type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--status-file", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--approved", action="store_true")
    arguments = parser.parse_args()

    try:
        profile = load_profile(arguments.profile, arguments.avatar_root)
        if arguments.check:
            print("Telegram profile is valid.")
            return 0
        if not arguments.approved:
            raise ProfileError("owner approval is required; pass --approved")
        if arguments.env_file is None or arguments.status_file is None:
            raise ProfileError("--env-file and --status-file are required")

        token = read_env_value(arguments.env_file, "TELEGRAM_BOT_TOKEN")
        client = TelegramClient(token)
        apply_profile(client, profile)
        verify_profile(client, profile)
        mark_profile_applied(arguments.status_file)
        print("Telegram bot profile applied and verified.")
    except ProfileError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
