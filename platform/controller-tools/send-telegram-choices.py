#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


class ChoicesError(ValueError):
    pass


def read_env_value(path, key):
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError as error:
        raise ChoicesError(f"environment file not found: {path}") from error
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
    raise ChoicesError(f"{key} is not configured")


def default_env_files():
    paths = []
    override = os.environ.get("AIDEE_CONTROLLER_ENV")
    if override:
        paths.append(Path(override))
    home = os.environ.get("AIDEE_CONTROLLER_HOME")
    if home:
        paths.append(Path(home) / ".hermes" / ".env")
    state = Path(
        os.environ.get(
            "AIDEE_STATE_DIR",
            os.environ.get("AIDEE_STATE_ROOT", "/var/lib/aidee"),
        )
    )
    paths.append(state / "controller-home" / ".hermes" / ".env")
    paths.append(Path.home() / ".hermes" / ".env")
    return paths


def first_existing(paths):
    for path in paths:
        if path.is_file():
            return path
    return None


def normalize_chat_id(value):
    chat_id = str(value).strip()
    if chat_id.lower().startswith("telegram:"):
        chat_id = chat_id.split(":", 1)[1]
    if not chat_id:
        raise ChoicesError("chat id is required")
    return chat_id


def resolve_chat_id(explicit=None, env_file=None):
    if explicit:
        return normalize_chat_id(explicit)
    if env_file is not None:
        try:
            return normalize_chat_id(read_env_value(env_file, "TELEGRAM_HOME_CHANNEL"))
        except ChoicesError:
            pass
    raise ChoicesError("Telegram home chat is not configured")


def build_send_payload(text, choices, chat_id):
    if not isinstance(text, str) or not text.strip():
        raise ChoicesError("message text is required")
    if len(text) > 4096:
        raise ChoicesError("message text must be at most 4096 characters")
    if not isinstance(choices, list) or not (2 <= len(choices) <= 8):
        raise ChoicesError("provide between 2 and 8 choices")
    labels = []
    for choice in choices:
        if not isinstance(choice, str) or not choice.strip():
            raise ChoicesError("each choice must be non-empty text")
        label = choice.strip()
        if len(label) > 64:
            raise ChoicesError("each choice must be at most 64 characters")
        if label in labels:
            raise ChoicesError(f"duplicate choice: {label}")
        labels.append(label)
    if not chat_id or not str(chat_id).strip():
        raise ChoicesError("chat id is required")
    return {
        "chat_id": str(chat_id).strip(),
        "text": text.strip(),
        "reply_markup": {
            "keyboard": [[{"text": label} for label in labels]],
            "one_time_keyboard": True,
            "resize_keyboard": True,
        },
    }


def telegram_request(token, method, payload):
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
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
        raise ChoicesError(f"Telegram {method} failed: {detail}") from error
    except urllib.error.URLError as error:
        raise ChoicesError(f"Telegram {method} failed: {error.reason}") from error
    if result.get("ok") is not True:
        raise ChoicesError(
            f"Telegram {method} failed: {result.get('description', 'unknown error')}"
        )
    return result.get("result")


def build_notice_payload(text, chat_id):
    if not isinstance(text, str) or not text.strip():
        raise ChoicesError("message text is required")
    if len(text) > 4096:
        raise ChoicesError("message text must be at most 4096 characters")
    if not chat_id or not str(chat_id).strip():
        raise ChoicesError("chat id is required")
    return {
        "chat_id": str(chat_id).strip(),
        "text": text.strip(),
    }


def resolve_telegram_env(env_file=None, chat_id=None):
    if env_file is None:
        env_file = first_existing(default_env_files())
    if env_file is None:
        raise ChoicesError("controller Telegram environment file was not found")
    token = read_env_value(env_file, "TELEGRAM_BOT_TOKEN")
    target = resolve_chat_id(explicit=chat_id, env_file=env_file)
    return token, target


def send_choices(text, choices, env_file=None, chat_id=None, requester=telegram_request):
    token, target = resolve_telegram_env(env_file=env_file, chat_id=chat_id)
    payload = build_send_payload(text, choices, target)
    requester(token, "sendMessage", payload)
    return payload


def send_notice(text, env_file=None, chat_id=None, requester=telegram_request):
    token, target = resolve_telegram_env(env_file=env_file, chat_id=chat_id)
    payload = build_notice_payload(text, target)
    requester(token, "sendMessage", payload)
    return payload


def main():
    parser = argparse.ArgumentParser(
        description="Send a Telegram notice, with optional tap-to-send choice buttons."
    )
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--chat-id")
    parser.add_argument("--text")
    parser.add_argument("--choice", action="append", dest="choices")
    arguments = parser.parse_args()
    text = arguments.text
    if text is None:
        text = sys.stdin.read()
    try:
        if arguments.choices:
            send_choices(
                text,
                arguments.choices,
                env_file=arguments.env_file,
                chat_id=arguments.chat_id,
            )
            print("Telegram choices sent.")
        else:
            send_notice(
                text,
                env_file=arguments.env_file,
                chat_id=arguments.chat_id,
            )
            print("Telegram notice sent.")
    except ChoicesError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
